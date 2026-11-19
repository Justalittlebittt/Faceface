"""M16.12 original 1925 PDF source-column OCR crop and review gate tests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.cangjie_original_column_roi import (
    validate_targets, crop_actual_original_page, evaluate_region_ocr, audit
)
from scripts.cangjie_original_phrase_probe import validate_pilot


class SourceColumnCropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot=json.loads(Path(
            "research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"
        ).read_text(encoding="utf-8"))
        cls.locators=json.loads(Path(
            "research/M16_12_SOURCE_COLUMN_LOCATORS.json"
        ).read_text(encoding="utf-8"))

    def test_exact_original_source_page_and_anchor_consistency(self):
        targets=validate_targets(self.locators,self.pilot)
        self.assertEqual(len(targets),3)
        self.assertEqual(
            {t["original_phrase_anchor_id"] for t in targets},
            {"M1610-A08","M1610-A03","M1610-A01"}
        )
        self.assertEqual(len(targets[0]["column_boxes_right_to_left_normalized"]),2)
        self.assertTrue(all(t["eligible_live_rule"] is False for t in targets))

    def test_two_columns_are_distinct_from_one_exact_OCR_line(self):
        target=validate_targets(self.locators,self.pilot)[0]
        # Given the actually visually observed original p086 physical arrangement,
        # the historical phrase runs from the end of right to start of left column.
        text_right="口角光明唇兩齊兩頭略仰不"
        text_left="垂低聰明更又多才學富貴應"
        metas=[{"real_private_crop_image_sha256":"a"*64}]*2
        row=evaluate_region_ocr(
            target,self.locators["original_pdf_sha256"]["nlc-44091"],
            [text_right,text_left],metas
        )
        self.assertFalse(row["exact_original_phrase_within_one_OCR_line"])
        self.assertFalse(row["exact_original_phrase_within_one_physical_column"])
        self.assertTrue(row["only_if_two_explicitly_adjacent_original_columns_joined"])
        self.assertTrue(row["requires_human_to_check_crop_and_ancient_wording"])
        self.assertFalse(row["produced_public_faceface_rule"])
        self.assertNotIn("口角光明",json.dumps(row,ensure_ascii=False))
        summary=audit([row], [target])
        self.assertEqual(summary["retrieval_only_by_joining_explicit_source_adjacent_columns"],1)
        self.assertEqual(summary["new_live_Faceface_historical_rules"],0)

    def test_source_eye_reference_cannot_be_spliced_from_unrelated_segments(self):
        target=validate_targets(self.locators,self.pilot)[1]
        # Only ONE physically located column is allowed in this target;
        # cannot concatenate multiple OCR images to engineer a phrase hit.
        with self.assertRaisesRegex(ValueError,"Different number"):
            evaluate_region_ocr(target,"a"*64,["眼須要含","藏不露"],[
                {"real_private_crop_image_sha256":"a"*64},
                {"real_private_crop_image_sha256":"b"*64}
            ])
        row=evaluate_region_ocr(
            target,"a"*64,["眼須要含藏不露其他描述"],
            [{"real_private_crop_image_sha256":"a"*64}]
        )
        self.assertTrue(row["exact_original_phrase_within_one_OCR_line"])
        self.assertFalse(row["only_if_two_explicitly_adjacent_original_columns_joined"])

    def test_locator_forgery_wrong_source_order_or_fake_review_fails(self):
        for edit,term in [
            (lambda d: d.update(full_page_human_reviewed_count=1),"human approval"),
            (lambda d: d["targets"][0].update(original_phrase_preliminary="人必富貴"),
             "modified or fabricated"),
            (lambda d: d["targets"][0]["column_boxes_right_to_left_normalized"].reverse(),
             "right-to-left"),
            (lambda d: d["targets"][0].update(eligible_live_rule=True),
             "Unverified source"),
        ]:
            with self.subTest(term=term):
                d=json.loads(json.dumps(self.locators))
                edit(d)
                with self.assertRaisesRegex(ValueError,term):
                    validate_targets(d,self.pilot)

    def test_actual_normalized_original_raster_crop_rotates_and_hashes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            image=folder/"mock-original-scanned-page.png"
            Image.new("L",(800,1400),color=255).save(image)
            destination=folder/"private"/"single-column-CCW90.png"
            info=crop_actual_original_page(
                image,[0.79,0.56,0.87,0.81],destination,scale=2
            )
            self.assertEqual(info["rotated_for_horizontal_detection_degrees_CCW"],90)
            self.assertEqual(info["absolute_rectangle_in_original_raster_px"],
                             [632,784,696,1134])
            self.assertEqual(len(info["real_private_crop_image_sha256"]),64)
            with Image.open(destination) as result:
                self.assertEqual(result.size,(700,128))

    def test_audit_does_not_approve_missing_or_failed_source_crops(self):
        target=validate_targets(self.locators,self.pilot)[0]
        row=evaluate_region_ocr(
            target,"a"*64,["字不完整","无关"],[
                {"real_private_crop_image_sha256":"a"*64},
                {"real_private_crop_image_sha256":"b"*64}
            ]
        )
        self.assertTrue(row["phrase_still_missing_in_this_targeted_OCR"])
        self.assertEqual(audit([row],[target])["unmatched_priority_source_crop_targets"],1)
        other=validate_targets(self.locators,self.pilot)[1]
        with self.assertRaisesRegex(ValueError,"Missing or duplicate"):
            audit([row],[target,other])


if __name__=="__main__":
    unittest.main()
