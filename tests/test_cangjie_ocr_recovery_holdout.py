"""M16.11 held-out original 1925 scans: predeclared reference integrity."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.cangjie_ocr_recovery_holdout import (
    EXPECTED_HOLDOUT_ANCHORS,EXPECTED_HOLDOUT_PAGES,SOURCE,
    VARIANTS,holdout_pages,score_one,summarize
)

class HeldoutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads(Path(
            "src/knowledge/maiyi-source-checked-v5.json"
        ).read_text(encoding="utf-8"))
        cls.pilot=json.loads(Path(
            "research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"
        ).read_text(encoding="utf-8"))

    def test_heldout_references_are_existing_V5_not_M1610_development_pages(self):
        found=holdout_pages(self.catalog,self.pilot)
        self.assertEqual(tuple(sorted(found)),EXPECTED_HOLDOUT_PAGES)
        self.assertEqual(sum(len(x) for x in found.values()),12)
        self.assertEqual(len(found),7)
        self.assertFalse(set(found)&{27,36,86,87})

    def fake_groups(self):
        found=holdout_pages(self.catalog,self.pilot)
        groups={v:[] for v,_ in VARIANTS}
        for page,phrases in found.items():
            for variant,_ in VARIANTS:
                text="\n".join(phrases if variant==VARIANTS[1][0] else phrases[:-1])
                groups[variant].append(score_one(
                    text,phrases,f"{SOURCE}:p{page:03d}","a"*64,variant
                ))
        return groups,found

    def test_exact_same_line_and_real_holdout_coverage(self):
        groups,found=self.fake_groups()
        report=summarize(groups,found)
        self.assertEqual(report["heldout_original_pages_tested"],7)
        self.assertEqual(report["heldout_historical_short_reference_anchors"],12)
        self.assertEqual(report["enhanced_220dpi_same_line_hits"],12)
        self.assertEqual(report["baseline_170dpi_same_line_hits"],5)
        self.assertEqual(report["net_220dpi_improvement_in_exact_phrase_hits"],7)
        self.assertEqual(report["new_live_Faceface_historical_rules"],0)
        self.assertFalse(report["production_OCR_default_modified"])
        self.assertFalse(report["validates_original_OCR_full_page_character_error_rate"])
        serialized=json.dumps(report,ensure_ascii=False)
        for phrases in found.values():
            for p in phrases:
                self.assertNotIn(p,serialized)

    def test_wrong_divergent_data_is_not_valid(self):
        groups,found=self.fake_groups()
        groups[VARIANTS[1][0]].pop()
        with self.assertRaisesRegex(ValueError,"Missing/duplicated"):
            summarize(groups,found)
        groups,found=self.fake_groups()
        groups[VARIANTS[1][0]][0]["full_page_human_reviewed"]=True
        with self.assertRaisesRegex(ValueError,"False review"):
            summarize(groups,found)

    def test_catalog_changes_cannot_silently_broaden_holdout(self):
        modified=json.loads(json.dumps(self.catalog))
        first=next(x for x in modified["cards"]+modified.get("framework_notes",[])
                   if x["source"]["pdf_page_zero_based"]==28)
        key="source_phrase" if "source_phrase" in first else "quote"
        first[key]=first[key]+"；額角比較"
        with self.assertRaisesRegex(ValueError,"original-reference anchor"):
            holdout_pages(modified,self.pilot)


if __name__=="__main__":
    unittest.main()
