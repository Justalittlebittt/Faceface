"""Private OCR → Cangjie research batch: provenance and no false attestations."""
from pathlib import Path
import json
import tempfile
import unittest

from scripts.cangjie_private_ocr_semantic_batch import read_private_cues
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


class PrivateOCRBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "cues.jsonl"
        self.row = {
            "cue_id": "a"*24,
            "source_id": "nlc-44091", "pdf_page_zero_based": 77,
            "source_pdf_sha256": KNOWN_SCAN_SHA256["nlc-44091"],
            "unreviewed_ocr_text_sha256": "b"*64,
            "short_ocr_line_unverified": "鼻長有壽",
            "outcome_terms_UNVERIFIED": {"longevity": ["壽"]},
            "same_OCR_line_morphology_regions": ["nose"],
            "source_image_human_verified": False,
            "historical_relation_established": False,
            "eligible_for_live_rules": False,
        }
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self, rows=None):
        rows = [self.row] if rows is None else rows
        self.path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    def test_real_private_source_excerpt_is_retained_without_false_review(self):
        rows, stats = read_private_cues([self.path])
        self.assertEqual(len(rows), 1)
        self.assertEqual(stats["raw_lexical_domain_memberships"]["longevity"], 1)
        self.assertEqual(rows[0]["page_id"], "nlc-44091:p077")
        self.assertFalse(rows[0]["source_excerpt_newly_human_reviewed"])
        self.assertFalse(rows[0]["this_experiment_may_add_live_rule"])

    def test_cap_and_deterministic_order(self):
        second = dict(self.row, cue_id="c"*24, pdf_page_zero_based=3)
        self.save([self.row, second])
        rows, stats = read_private_cues([self.path], max_cues=1)
        self.assertEqual(stats["available_private_cues"], 2)
        self.assertEqual(rows[0]["pdf_page_zero_based"], 3)

    def test_no_private_text_is_replaced_by_page_counts(self):
        self.row.pop("short_ocr_line_unverified")
        self.save()
        with self.assertRaises(ValueError):
            read_private_cues([self.path])

    def test_forged_source_sha_and_human_review_fail_closed(self):
        self.row["source_pdf_sha256"] = "c"*64
        self.save()
        with self.assertRaises(ValueError):
            read_private_cues([self.path])
        self.row["source_pdf_sha256"] = KNOWN_SCAN_SHA256["nlc-44091"]
        self.row["source_image_human_verified"] = True
        self.save()
        with self.assertRaises(ValueError):
            read_private_cues([self.path])

    def test_duplicated_candidate_id_fails(self):
        self.save([self.row, self.row])
        with self.assertRaises(ValueError):
            read_private_cues([self.path])

    def test_missing_file_or_empty_source_does_not_create_fake_progress(self):
        with self.assertRaises(ValueError):
            read_private_cues([Path(self.temp.name)/"missing.jsonl"])
        self.path.write_text("", encoding="utf-8")
        _, stats = read_private_cues([self.path])
        self.assertEqual(stats["selected_cues"], 0)


if __name__ == "__main__":
    unittest.main()
