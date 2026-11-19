"""M16.12 local original SHORT-ROI human review ledger, never full-page auto-review."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest

from scripts.cangjie_original_column_roi import validate_targets
from scripts.cangjie_source_short_review import create_source_short_review
from scripts.cangjie_review_core import file_sha256

class HumanShortRegionReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pilot=json.loads(Path("research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json").read_text("utf-8"))
        regions=json.loads(Path("research/M16_12_SOURCE_COLUMN_LOCATORS.json").read_text("utf-8"))
        cls.t=validate_targets(regions,pilot)[0]
        cls.source_sha=regions["original_pdf_sha256"]["nlc-44091"]

    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        sid,index=self.t["source_id"],self.t["pdf_page_zero_based"]
        crop_base=self.root/"original-source-column-crops"/sid/f"{index:03d}"
        crop_base.mkdir(parents=True)
        self.details=[]
        for i in range(2):
            image=crop_base/f"{self.t['target_id']}-col{i:02d}-rotated.png"
            image.write_bytes(f"synthetic image {i}".encode("utf-8"))
            self.details.append({"real_private_crop_image_sha256":file_sha256(image)})
        self.meta={"page_id":f"{sid}:p{index:03d}",
                   "original_pdf_sha256":self.source_sha,
                   "approved_by_human":False,
                   "source_column_rectangles":self.details}

    def signed(self,**kwargs):
        fields=dict(
            target=self.t,expected_source_sha=self.source_sha,
            private_ocr_provenance=self.meta,private_root=self.root,
            reviewer="named-human-editor",corrected_text="兩頭略仰不垂低",
            classification="observable_morphology",
            explicitly_checked_original_image=True,note="Only a short original region"
        )
        fields.update(kwargs)
        return create_source_short_review(**fields)

    def test_only_human_checked_short_region_can_enter_private_semantic_research(self):
        record=self.signed()
        self.assertEqual(record["source_pdf_sha256"],self.source_sha)
        self.assertTrue(record["image_region_verified_explicitly_by_reviewer"])
        self.assertTrue(record["eligible_for_further_SOURCE_SCOPED_Cangjie_research"])
        self.assertFalse(record["full_page_1925_original_reviewed"])
        self.assertFalse(record["Faceface_public_report_rule_automatically_created"])
        self.assertFalse(record["eligible_for_Faceface_live_rules"])
        self.assertFalse(record["cangjie_Adler_or_five_agents_already_run"])
        self.assertEqual(len(record["human_confirmed_original_column_crop_sha256"]),2)

    def test_model_ocr_bot_or_no_explicit_image_check_cannot_fake_signature(self):
        for reviewer in ("auto","OCR","agent","bot","anonymous",""):
            with self.subTest(reviewer=reviewer),self.assertRaisesRegex(ValueError,"non-automated"):
                self.signed(reviewer=reviewer)
        with self.assertRaisesRegex(ValueError,"Must personally compare"):
            self.signed(explicitly_checked_original_image=False)

    def test_changed_png_or_mismatched_source_sha_is_rejected(self):
        wrong=dict(self.meta,original_pdf_sha256="bad")
        with self.assertRaisesRegex(ValueError,"provenance mismatched"):
            self.signed(private_ocr_provenance=wrong)
        sid,index=self.t["source_id"],self.t["pdf_page_zero_based"]
        png=self.root/"original-source-column-crops"/sid/f"{index:03d}"/f"{self.t['target_id']}-col00-rotated.png"
        png.write_bytes(b"tamper")
        with self.assertRaisesRegex(ValueError,"missing or altered"):
            self.signed()

    def test_unconfirmed_ambiguous_or_historical_assertion_does_not_feed_semantic_candidates(self):
        for cls in ("uncertain","historical_assertion","figure_label"):
            with self.subTest(cls=cls):
                r=self.signed(classification=cls)
                self.assertFalse(r["eligible_for_further_SOURCE_SCOPED_Cangjie_research"])
                self.assertFalse(r["eligible_for_Faceface_live_rules"])
        with self.assertRaisesRegex(ValueError,"Classify short ROI"):
            self.signed(classification="magically_verified_forecast")

if __name__=="__main__":
    unittest.main()
