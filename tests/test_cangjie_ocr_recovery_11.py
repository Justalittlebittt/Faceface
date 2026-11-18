"""M16.11 real original OCR preprocessing comparison: tests without a fake model success claim."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.cangjie_ocr_recovery_11 import (
    VARIANTS, compare_experiments, score_variant, source_image_strips,
)
from scripts.cangjie_original_phrase_probe import validate_pilot, source_pages

PILOT=Path("research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json")


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot=json.loads(PILOT.read_text("utf-8"))
        cls.anchors=validate_pilot(cls.pilot)
        cls.pages=source_pages(cls.anchors)

    def fake_rows(self):
        rows={}
        for name in VARIANTS:
            page_list=[]
            for sid,index in self.pages:
                refs=[a for a in self.anchors if
                      (a["source_id"],a["pdf_page_zero_based"])==(sid,index)]
                content="\n".join(a["short_original_image_phrase_preliminary"] for a in refs)
                # In baseline, erase the last phrase from each page.
                if name==VARIANTS[0] and len(refs)>1:
                    content="\n".join(a["short_original_image_phrase_preliminary"]
                                      for a in refs[:-1])
                page_list.append(score_variant(sid,index,refs,[content],name))
            rows[name]=page_list
        return rows

    def test_predeclared_variant_comparison_preserves_13_anchors_and_all_pages(self):
        rows=self.fake_rows()
        stats=compare_experiments(rows,self.anchors)
        self.assertEqual(stats["original_scan_pages"],6)
        self.assertEqual(stats["same_thirteen_AI_visually_read_preliminary_original_short_anchors"],13)
        self.assertGreater(
            stats["best_single_enhanced_exact_short_phrase_hits"],
            stats["baseline_170dpi_exact_short_phrase_hits"]
        )
        self.assertTrue(stats["only_short_phrase_exact_retrieval_measured_NOT_full_page_CER"])
        self.assertTrue(stats["variant_selection_requires_new_heldout_sources"])
        self.assertFalse(stats["enhanced_variant_should_replace_current_original_book_OCR"])
        self.assertEqual(stats["new_live_faceface_rules"],0)
        self.assertEqual(stats["independent_human_page_reviews_added"],0)
        dump=json.dumps(stats,ensure_ascii=False)
        for a in self.anchors:
            self.assertNotIn(a["short_original_image_phrase_preliminary"],dump)

    def test_per_segment_scoring_never_fabricates_cross_tile_matches(self):
        reference=self.anchors[0]
        text=reference["short_original_image_phrase_preliminary"]
        chars=list(text)
        split=len(chars)//2
        result=score_variant(
            reference["source_id"],reference["pdf_page_zero_based"],
            [reference],["".join(chars[:split]),"".join(chars[split:])],
            "vertical_strips_220_overlap"
        )
        self.assertEqual(result["exact_single_OCR_line_hits"],0)
        self.assertEqual(result["exact_image_segment_hits"],0)
        self.assertEqual(result["source_image_segment_count"],2)
        self.assertEqual(result["original_pdf_sha256"],reference["original_pdf_sha256"])

    def test_line_match_count_is_narrower_than_page_segment_match(self):
        reference=self.anchors[0]
        phrase=reference["short_original_image_phrase_preliminary"]
        text="\n".join((phrase[:2],phrase[2:]))
        result=score_variant(reference["source_id"],reference["pdf_page_zero_based"],
                             [reference],[text],"full_220_original")
        self.assertEqual(result["exact_image_segment_hits"],1)
        self.assertEqual(result["exact_single_OCR_line_hits"],0)

    def test_fail_closed_missing_original_page_or_variant(self):
        rows=self.fake_rows()
        del rows[VARIANTS[1]]
        with self.assertRaisesRegex(ValueError,"Missing or unknown"):
            compare_experiments(rows,self.anchors)
        rows=self.fake_rows()
        rows[VARIANTS[2]].pop()
        with self.assertRaisesRegex(ValueError,"missing/duplicated"):
            compare_experiments(rows,self.anchors)

    def test_actual_strip_generation_covers_source_pixels_with_overlap(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            original=root/"original.png"
            Image.new("L",(1200,1800),color=255).save(original)
            strips=source_image_strips(original,root/"strips")
            self.assertGreaterEqual(len(strips),4)
            self.assertEqual(strips[0]["rectangle_in_source_pixels"][0],0)
            self.assertEqual(strips[-1]["rectangle_in_source_pixels"][2],1200)
            prev_right=None
            for strip in strips:
                l,t,r,b=strip["rectangle_in_source_pixels"]
                self.assertEqual((t,b),(0,1800))
                self.assertTrue(strip["path"].is_file())
                self.assertLess(l,r)
                if prev_right is not None:
                    self.assertLess(l,prev_right)
                prev_right=r

    def test_too_small_page_crop_fails_instead_of_pretending_to_run(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            path=root/"tiny.png"
            Image.new("L",(200,300),255).save(path)
            with self.assertRaisesRegex(ValueError,"too small"):
                source_image_strips(path,root/"strips")


if __name__=="__main__":
    unittest.main()
