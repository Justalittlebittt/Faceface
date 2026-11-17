"""M16.5 proofread-only gate, exact PDF SHA provenance, real CER and local HTTP protection.

Synthetic %PDF- test bytes never count toward real historical transcription.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import cangjie_corpus_stage as stage
from scripts.cangjie_page_review import ReviewServer
from scripts.cangjie_review_core import (
    ReviewWorkspace, atomic_write, file_sha256
)
from scripts.cangjie_review_quality import (
    characters, edit_distance, evaluate, ordered_han_metrics
)


class M165PageReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.scans = self.base / "scans"
        self.scans.mkdir()
        (self.scans / "part1.pdf").write_bytes(b"%PDF-1.4 synthetic A")
        (self.scans / "part2.pdf").write_bytes(b"%PDF-1.4 synthetic B")
        self.ocr = self.base / "ocr"
        self.reviewed = self.base / "reviewed"
        hashes = {
            "nlc-44091": file_sha256(self.scans / "part1.pdf"),
            "nlc-44092": file_sha256(self.scans / "part2.pdf"),
        }
        self.fake_pages = lambda p: 153 if p.name == "part1.pdf" else 115
        with patch("scripts.cangjie_review_core.pdf_pages", side_effect=self.fake_pages):
            self.workspace = ReviewWorkspace(
                self.scans, self.ocr, self.reviewed, expected_hashes=hashes
            )
        self.source = "nlc-44091"
        self.index = 27

    def put_candidate(self, text="口須方小\n", source=None, page=None, valid=True):
        source = source or self.source
        page = self.index if page is None else page
        p = self.workspace.page_paths(source, page)
        atomic_write(p["candidate"], text.encode("utf-8"))
        meta = {
            "source_pdf_sha256": self.workspace.sources[source]["pdf_sha256"]
                if valid else "WRONG_PDF",
            "pdf_page_zero_based": page,
            "candidate_text_sha256": file_sha256(p["candidate"]),
            "eligible_for_cangjie_verified_corpus": False,
            "engine": "tesseract",
        }
        atomic_write(p["candidate_meta"], json.dumps(meta).encode("utf-8"))

    def save(self, text="口須方大\n鼻梁端直", reviewer="actual-reviewer"):
        return self.workspace.save_review(
            self.source, self.index, text, reviewer, True,
            content_type="text_and_figures", printed_volume="卷一",
            section="五官", notes="逐列核对扫描"
        )

    def test_provenance_gate_and_readable_full_page_review(self):
        self.put_candidate()
        before = self.workspace.page_info(self.source, self.index)
        self.assertFalse(before["is_reviewed_full_page"])
        self.assertTrue(before["ocr_candidate_provenance_ok"])
        saved = self.save()
        self.assertTrue(saved["confirmed_against_full_original_image"])
        self.assertEqual(saved["printed_volume"], "卷一")
        self.assertEqual(saved["source_pdf_sha256"],
                         self.workspace.sources[self.source]["pdf_sha256"])
        after = self.workspace.page_info(self.source, self.index)
        self.assertTrue(after["is_reviewed_full_page"])
        self.assertEqual(after["reviewed_text"], "口須方大\n鼻梁端直\n")
        self.assertEqual(self.workspace.summary()["full_page_reviewed"], 1)
        self.assertEqual(self.workspace.summary()["unreviewed_or_missing"], 267)
        self.assertEqual(self.workspace.summary()["ocr_provenance_ok"], 1)
        self.assertFalse(self.workspace.summary()["all_full_pages_reviewed"])
        # The existing M16.1 official-Cangjie staging gate consumes the reviewed
        # directory directly; it must not accept the original OCR directory.
        with patch.object(stage, "pdf_pages", side_effect=self.fake_pages):
            sources, pages, reviewed = stage.index_scans(self.scans, self.reviewed)
        self.assertEqual(len(sources), 2)
        self.assertEqual(sum(p["text_status"] == "reviewed" for p in pages), 1)
        self.assertEqual(len(reviewed), 1)
        self.assertIn("口須方大", reviewed[0])

    def test_no_auto_approval_or_anonymous_ghost_reviewer(self):
        for who in ("ocr", "auto", "agent", "anonymous", "bot"):
            with self.subTest(who=who):
                with self.assertRaises(ValueError):
                    self.workspace.save_review(self.source, self.index, "面相",
                                               who, True)
        with self.assertRaisesRegex(ValueError, "Explicit visual comparison"):
            self.workspace.save_review(self.source, self.index, "原字",
                                       "named-reviewer", False)
        with self.assertRaisesRegex(ValueError, "nonempty"):
            self.workspace.save_review(self.source, self.index, "",
                                       "named-reviewer", True)
        self.assertEqual(self.workspace.summary()["full_page_reviewed"], 0)

    def test_tampered_text_or_replaced_source_is_rejected(self):
        self.save()
        reviewed = self.workspace.page_paths(self.source, self.index)["reviewed"]
        reviewed.write_text("篡改后的文字", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.workspace.page_info(self.source, self.index)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            evaluate(self.workspace)
        (self.scans / "part1.pdf").write_bytes(b"%PDF-1.4 changed while open")
        with self.assertRaisesRegex(ValueError, "modified"):
            self.workspace.save_review(self.source, 28, "面相",
                                       "human-reviewer", True)

    def test_wrong_original_scan_is_not_accepted(self):
        with patch("scripts.cangjie_review_core.pdf_pages", side_effect=self.fake_pages):
            with self.assertRaisesRegex(ValueError, "Wrong scan SHA256"):
                ReviewWorkspace(
                    self.scans, self.ocr, self.reviewed,
                    expected_hashes={"nlc-44091": "bad", "nlc-44092": "bad"}
                )
        with self.assertRaises(ValueError):
            self.workspace.page_paths("../files", 1)
        with self.assertRaises(ValueError):
            self.workspace.page_paths(self.source, 153)
        with self.assertRaises(ValueError):
            self.workspace.page_paths(self.source, True)

    def test_bad_candidate_provenance_does_not_influence_review(self):
        self.put_candidate(valid=False)
        page = self.workspace.page_info(self.source, self.index)
        self.assertTrue(page["ocr_candidate_available"])
        self.assertFalse(page["ocr_candidate_provenance_ok"])
        self.assertFalse(page["ocr_candidate"])
        review = self.save("傳統字義")
        self.assertEqual(review["page_id"], "nlc-44091:p027")

    def test_real_order_sensitive_CER_versus_order_blind_bag(self):
        self.assertEqual(characters("口、須  方大。"), "口須方大")
        result = ordered_han_metrics("口須方大", "口須方小")
        self.assertEqual(result["levenshtein_edits"], 1)
        self.assertEqual(result["han_character_error_rate_order_sensitive"], 0.25)
        self.assertEqual(result["han_bag_recall_order_insensitive_diagnostic"], 0.75)
        bad_order = ordered_han_metrics("甲乙丙丁", "丙丁甲乙")
        self.assertGreater(bad_order["han_character_error_rate_order_sensitive"], 0)
        self.assertEqual(bad_order["han_bag_recall_order_insensitive_diagnostic"], 1.0)
        self.assertEqual(edit_distance("", "面"), 1)
        with self.assertRaisesRegex(ValueError, "no Han"):
            ordered_han_metrics("123", "口須")

    def test_full_page_quality_reports_only_attested_comparable_pages(self):
        self.put_candidate("口須方小\n鼻梁端直\n")
        self.save("口須方大\n鼻梁端直")
        result = evaluate(self.workspace)
        self.assertEqual(result["original_scan_pages"], 268)
        self.assertEqual(result["pages_with_page_specific_review_attestation"], 1)
        self.assertEqual(result["pages_compared_with_source_provenance_ocr"], 1)
        self.assertFalse(result["whole_book_review_gate_met"])
        self.assertFalse(result["whole_book_CER_available"])
        self.assertFalse(result["actual_cangjie_agent_extraction_performed"])
        self.assertEqual(result["runtime_rules_added"], 0)
        self.assertEqual(result["summed_edit_distance"], 1)

    def test_local_HTTP_rejects_cross_origin_and_missing_write_token(self):
        server = ReviewServer(0, self.workspace)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(lambda: (server.shutdown(),server.server_close(),worker.join(3)))
        host = f"127.0.0.1:{server.server_port}"
        req = {"source": self.source, "index": self.index,
               "text": "口須方大", "reviewer": "human-reviewer",
               "confirmed_against_image": True}
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            body = json.dumps(req)
            conn.request("POST", "/api/review", body=body,
                         headers={"Host": host, "Content-Type": "application/json"})
            response = conn.getresponse()
            self.assertEqual(response.status,403)
            response.read()
            conn.request(
                "POST", "/api/review", body=body,
                headers={"Host":host,"Content-Type":"application/json",
                         "X-Faceface-Review-Token":server.edit_token,
                         "Origin":"https://attacker.invalid"}
            )
            response = conn.getresponse()
            self.assertEqual(response.status,403)
            response.read()
            self.assertEqual(self.workspace.summary()["full_page_reviewed"],0)
            conn.request("GET", "/api/status", headers={"Host":host})
            response = conn.getresponse()
            self.assertEqual(response.status,200)
            data=json.loads(response.read())
            self.assertEqual(data["total_original_scan_pages"],268)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
