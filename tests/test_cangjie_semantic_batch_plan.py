"""M16.23 source-diverse semantic model selection, never made-up ancient text."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.cangjie_semantic_batch_plan import plan_private_shard
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


class BatchPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "private.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def cues(self, rows):
        records=[]
        for i,(page,domain,text) in enumerate(rows):
            records.append({
                "cue_id": f"{i+1:024x}",
                "source_id":"nlc-44091", "pdf_page_zero_based":page,
                "source_pdf_sha256":KNOWN_SCAN_SHA256["nlc-44091"],
                "unreviewed_ocr_text_sha256":"b"*64,
                "short_ocr_line_unverified":text,
                "outcome_terms_UNVERIFIED":{domain:[text[-1]]},
                "same_OCR_line_morphology_regions":[],
                "source_image_human_verified":False,
                "historical_relation_established":False,
                "eligible_for_live_rules":False
            })
        self.path.write_text("\n".join(json.dumps(r,ensure_ascii=False) for r in records)+"\n",encoding="utf-8")

    def test_balance_longevity_wealth_and_moral_even_without_face_word(self):
        self.cues([(11,"wealth","富貴"),(12,"wealth","貧賤"),
                   (32,"longevity","長壽"),(54,"moral_character","忠厚"),
                   (86,"career","功名"),(89,"fortune","吉凶")])
        chosen, stats = plan_private_shard([self.path], 4)
        domains=set(d for x in chosen for d in x["outcome_terms_UNVERIFIED"])
        self.assertEqual(len(chosen),4)
        self.assertIn("longevity",domains)
        self.assertIn("wealth",domains)
        self.assertIn("moral_character",domains)
        self.assertEqual(stats["distinct_original_scan_pages_selected"],4)
        self.assertTrue(all(r["eligible_for_live_rules"] is False for r in chosen))

    def test_no_auto_promotion_and_first_page_bias_control(self):
        self.cues([(7,"wealth","富貴"),(7,"wealth","財祿"),
                   (25,"longevity","長壽"),(90,"moral_character","仁義")])
        chosen, stats=plan_private_shard([self.path],3)
        self.assertEqual(len({r["pdf_page_zero_based"] for r in chosen}),3)
        self.assertFalse(stats["source_original_page_verified_against_image"])
        self.assertTrue(stats["selector_does_not_create_live_rules"])

    def test_single_character_is_excluded_not_fabricated(self):
        self.cues([(1,"longevity","壽"),(3,"wealth","富貴")])
        chosen, stats=plan_private_shard([self.path],8)
        self.assertEqual(len(chosen),1)
        self.assertEqual(stats["source_private_cues_before_policy"],2)

    def test_invalid_budget_rejected(self):
        self.cues([(1,"wealth","富貴")])
        with self.assertRaises(ValueError):
            plan_private_shard([self.path],0)


if __name__=="__main__":
    unittest.main()
