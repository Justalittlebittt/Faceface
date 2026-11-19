"""M16.13 signed short ROI research gate: no OCR/AI promotion or live rules."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.cangjie_signed_roi_input import collect_signed_short_roi_inputs
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, file_sha256


class SignedRoiInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = {
            "target_id": "M1612-T01", "source_id": "nlc-44091",
            "pdf_page_zero_based": 86,
            "column_boxes_right_to_left_normalized": [[.8,.5,.9,.8], [.7,.5,.8,.8]]
        }
        self.locators = {
            "targets": [self.target],
            "original_pdf_sha256": {"nlc-44091": KNOWN_SCAN_SHA256["nlc-44091"]}
        }
        self.review_file = self.root / "human-checked-source-SHORT-ROIs" / "M1612-T01.review.json"
        self.review_file.parent.mkdir(parents=True)
        crop_dir = self.root / "original-source-column-crops" / "nlc-44091" / "086"
        crop_dir.mkdir(parents=True)
        hashes = []
        for i in range(2):
            f = crop_dir / f"M1612-T01-col{i:02d}-rotated.png"
            f.write_bytes(f"synthetic-crop-{i}".encode())
            hashes.append(file_sha256(f))
        phrase = "兩頭略仰不垂低"
        self.review = {
            "kind": "M16.12_HUMAN_CONFIRMED_SHORT_SOURCE_ROI_NOT_COMPLETE_PAGE",
            "target_id": "M1612-T01", "source_id": "nlc-44091",
            "original_pdf_page_zero_based": 86,
            "source_pdf_sha256": KNOWN_SCAN_SHA256["nlc-44091"],
            "image_region_verified_explicitly_by_reviewer": True,
            "full_page_1925_original_reviewed": False,
            "eligible_for_Faceface_live_rules": False,
            "Faceface_public_report_rule_automatically_created": False,
            "cangjie_Adler_or_five_agents_already_run": False,
            "reviewer": "named-human-editor",
            "transcribed_original_short_phrase_by_reviewer": phrase,
            "transcribed_source_quote_sha256": hashlib.sha256(phrase.encode()).hexdigest(),
            "human_confirmed_original_column_crop_sha256": hashes,
            "text_classification": "observable_morphology",
            "eligible_for_further_SOURCE_SCOPED_Cangjie_research": True,
            "reviewed_at_UTC": "2026-11-19T00:00:00+00:00"
        }

    def export(self):
        return collect_signed_short_roi_inputs(self.locators, self.root)

    def save(self):
        self.review_file.write_text(json.dumps(self.review, ensure_ascii=False), encoding="utf-8")

    def test_missing_review_does_not_promote_preliminary_text(self):
        result = self.export()
        self.assertEqual(result["inputs"], [])
        self.assertEqual(result["not_admitted"][0]["reason"], "missing_human_roi_review")

    def test_signed_short_review_only_creates_private_research_input(self):
        self.save()
        result = self.export()
        self.assertEqual(len(result["inputs"]), 1)
        self.assertEqual(result["live_rules_created"], 0)
        self.assertEqual(result["full_pages_human_reviewed_by_this_tool"], 0)
        self.assertFalse(result["inputs"][0]["website_rule_eligible"])
        self.assertFalse(result["inputs"][0]["cangjie_extraction_executed"])

    def test_tampered_crop_or_quote_hash_rejected(self):
        self.save()
        self.review["transcribed_original_short_phrase_by_reviewer"] = "偽造的文字"
        self.save()
        self.assertEqual(len(self.export()["inputs"]), 0)
        self.review["transcribed_original_short_phrase_by_reviewer"] = "兩頭略仰不垂低"
        self.save()
        image = self.root / "original-source-column-crops/nlc-44091/086/M1612-T01-col00-rotated.png"
        image.write_bytes(b"tampered")
        self.assertEqual(self.export()["not_admitted"][0]["reason"], "source_crop_missing_or_changed")

    def test_non_morphology_or_fake_human_is_rejected(self):
        self.review["text_classification"] = "historical_assertion"
        self.review["eligible_for_further_SOURCE_SCOPED_Cangjie_research"] = False
        self.save()
        self.assertEqual(self.export()["not_admitted"][0]["reason"], "not_observable_morphology")
        self.review["text_classification"] = "observable_morphology"
        self.review["eligible_for_further_SOURCE_SCOPED_Cangjie_research"] = True
        self.review["reviewer"] = "agent"
        self.save()
        self.assertEqual(self.export()["not_admitted"][0]["reason"], "invalid_or_changed_signed_metadata")

    def test_unknown_source_or_duplicate_locator_rejected(self):
        self.locators["original_pdf_sha256"]["nlc-44091"] = "bad"
        with self.assertRaisesRegex(ValueError, "Unpinned source"):
            self.export()
        self.locators["original_pdf_sha256"]["nlc-44091"] = KNOWN_SCAN_SHA256["nlc-44091"]
        self.locators["targets"].append(self.target)
        with self.assertRaisesRegex(ValueError, "Duplicate target"):
            self.export()


if __name__ == "__main__":
    unittest.main()
