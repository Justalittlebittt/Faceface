"""M16.14 private short source-chunk formatting checks (synthetic data only)."""
import hashlib
import unittest
from scripts.cangjie_source_scoped_chunks import compile_source_scoped_chunks
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


class ScopedChunksTests(unittest.TestCase):
    def setUp(self):
        phrase = "兩頭略仰不垂低"
        self.entry = {
            "target_id": "M1612-T01", "source_id": "nlc-44091",
            "pdf_page_zero_based": 86,
            "source_pdf_sha256": KNOWN_SCAN_SHA256["nlc-44091"],
            "human_attested_short_quote": phrase,
            "original_quote_sha256": hashlib.sha256(phrase.encode()).hexdigest(),
            "historical_description_only": True,
            "verified_complete_page": False,
            "cangjie_extraction_executed": False,
            "website_rule_eligible": False,
        }
        self.manifest = {
            "schema": "M16.13_PRIVATE_SOURCE_SCOPED_CANGJIE_INPUT_V1",
            "scope": "human_attested_short_ROIs_only_not_complete_book",
            "human_attested_source_short_ROIs": 1,
            "full_pages_human_reviewed_by_this_tool": 0,
            "cangjie_agent_calls_performed_by_this_tool": 0,
            "live_rules_created": 0,
            "inputs": [self.entry]
        }

    def test_positive_source_scoped_chunk_not_a_rule(self):
        md, audit = compile_source_scoped_chunks(self.manifest)
        self.assertIn("nlc-44091:p086", md)
        self.assertIn("兩頭略仰不垂低", md)
        self.assertIn("RESEARCH_CANDIDATE_ONLY", md)
        self.assertEqual(audit["short_roi_chunk_count"], 1)
        self.assertEqual(audit["cangjie_extractor_calls_performed"], 0)
        self.assertEqual(audit["live_rules_created"], 0)

    def test_empty_batch_must_not_claim_extraction(self):
        self.manifest["inputs"] = []
        self.manifest["human_attested_source_short_ROIs"] = 0
        md, audit = compile_source_scoped_chunks(self.manifest)
        self.assertIn("NO ADMITTED SHORT ROI EVIDENCE", md)
        self.assertEqual(audit["short_roi_chunk_count"], 0)

    def test_unverified_or_mutated_phrase_fails(self):
        self.entry["human_attested_short_quote"] = "偽造原文"
        with self.assertRaises(ValueError):
            compile_source_scoped_chunks(self.manifest)

    def test_unsafe_upgrade_fails(self):
        for key in ("verified_complete_page", "website_rule_eligible", "cangjie_extraction_executed"):
            original = self.entry[key]
            self.entry[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                compile_source_scoped_chunks(self.manifest)
            self.entry[key] = original

    def test_duplicate_and_wrong_source_fails(self):
        self.manifest["inputs"].append(dict(self.entry))
        self.manifest["human_attested_source_short_ROIs"] = 2
        with self.assertRaises(ValueError):
            compile_source_scoped_chunks(self.manifest)
        self.manifest["inputs"].pop()
        self.manifest["human_attested_source_short_ROIs"] = 1
        self.entry["source_pdf_sha256"] = "tampered"
        with self.assertRaises(ValueError):
            compile_source_scoped_chunks(self.manifest)


if __name__ == "__main__":
    unittest.main()
