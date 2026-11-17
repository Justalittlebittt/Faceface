"""M16.2 OCR tests: staged text must never be silently promoted as verified."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import cangjie_ocr_candidates as ocr
from scripts.cangjie_corpus_stage import verify_page_review


class OcrTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.scan = self.root / "scans"
        self.scan.mkdir()
        self.scan.joinpath("part1.pdf").write_bytes(b"%PDF-synthetic-only")

    @staticmethod
    def fake_tool(args):
        if args[0] == "pdftoppm":
            Path(args[-1] + ".png").write_bytes(b"fake-image")
        elif args[0] == "tesseract":
            target = Path(args[2])
            target.with_suffix(".txt").write_text("面相五官口須方大\n", encoding="utf-8")
            target.with_suffix(".tsv").write_text(
                "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t95.0\t面相\n"
                "5\t1\t1\t1\t1\t2\t0\t10\t10\t10\t75.0\t五官\n"
                "5\t1\t1\t1\t1\t3\t0\t20\t10\t10\t-1\t\n", encoding="utf-8")
        else:
            raise AssertionError("Unexpected tool " + str(args[0]))

    def test_real_provenance_fields_and_unreviewed_gate(self):
        with patch.object(ocr, "run", side_effect=self.fake_tool):
            page = ocr.ocr_page(self.scan / "part1.pdf", "nlc-44091", 27,
                                self.root / "output", "fixed-pdf-hash", dpi=175)
        self.assertEqual(page["page_id"], "nlc-44091:p027")
        self.assertEqual(page["pdf_page_zero_based"], 27)
        self.assertEqual(page["mean_word_confidence"], 85.0)
        self.assertEqual(page["state"], "ocr_candidate")
        self.assertTrue(page["requires_manual_page_review"])
        self.assertFalse(page["eligible_for_cangjie_verified_corpus"])
        candidate = self.root / "output" / "transcripts" / "nlc-44091" / "027.txt"
        self.assertTrue(candidate.exists())
        self.assertFalse(verify_page_review(candidate, "fixed-pdf-hash", 27))
        meta = json.loads(candidate.with_suffix(".ocr.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["candidate_text_sha256"], ocr.digest(candidate))
        self.assertFalse(candidate.with_suffix(".review.json").exists())

    def test_range_metadata_and_no_agent_extraction(self):
        with patch.object(ocr, "pdf_pages", return_value=153), \
             patch.object(ocr, "run", side_effect=self.fake_tool):
            r = ocr.batch(self.scan, self.root / "output", "nlc-44091", 27, 28)
        self.assertEqual(r["processed_pages"], 2)
        self.assertEqual(r["expected_processed_pages"], 2)
        self.assertEqual(r["pages_with_candidate_text"], 2)
        self.assertEqual(r["human_reviewed_pages_from_this_run"], 0)
        self.assertEqual(r["cangjie_active_rules_created"], 0)
        self.assertFalse(r["cangjie_agent_extraction_performed"])

    def test_bad_range_and_dpi_rejected(self):
        with patch.object(ocr, "pdf_pages", return_value=153):
            with self.assertRaises(ValueError):
                ocr.batch(self.scan, self.root / "out", "nlc-44091", 150, 154)
            with self.assertRaises(ValueError):
                ocr.ocr_page(self.scan / "part1.pdf", "nlc-44091", 2,
                             self.root / "out", "hash", dpi=60)

    def test_empty_ocr_does_not_masquerade_as_transcribed(self):
        def empty_tool(args):
            if args[0] == "pdftoppm":
                Path(args[-1] + ".png").write_bytes(b"fake")
            else:
                target = Path(args[2])
                target.with_suffix(".txt").write_text(" \n", encoding="utf-8")
                target.with_suffix(".tsv").write_text(
                    "level\tconf\ttext\n", encoding="utf-8")
        with patch.object(ocr, "run", side_effect=empty_tool):
            page = ocr.ocr_page(self.scan / "part1.pdf", "nlc-44091", 0,
                                self.root / "out", "hash")
        self.assertEqual(page["state"], "empty_ocr_candidate")
        self.assertEqual(page["han_char_count"], 0)
        self.assertIsNone(page["candidate_text_sha256"])
        self.assertFalse((self.root/"out"/"transcripts"/"nlc-44091"/"000.txt").exists())


if __name__ == "__main__":
    unittest.main()
