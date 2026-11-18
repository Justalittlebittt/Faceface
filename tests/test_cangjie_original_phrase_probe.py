"""M16.10: source-image phrase vs actual-page OCR provenance/metric gating."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.cangjie_original_phrase_probe import (
    SCHEMA, compare_to_actual_ocr, source_pages, validate_pilot
)


PILOT=Path("research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json")


class OriginalPhrasePilotTests(unittest.TestCase):
    def setUp(self):
        self.doc=json.loads(PILOT.read_text(encoding="utf-8"))
        self.a=self.doc["anchors"]

    def test_real_image_reference_ledger_has_two_sources_and_six_distinct_pages(self):
        refs=validate_pilot(self.doc)
        self.assertEqual(len(refs),13)
        self.assertEqual(len(source_pages(refs)),6)
        self.assertEqual(set(x["source_id"] for x in refs),
                         {"nlc-44091","nlc-44092"})
        self.assertTrue(all(x["full_page_transcription_reviewed"] is False for x in refs))
        self.assertTrue(all(x["automatically_publish_rule"] is False for x in refs))

    def test_exact_page_matching_is_not_cer_or_whole_book_precision(self):
        pages=source_pages(self.a)
        texts={(sid,page):"\n".join(
            x["short_original_image_phrase_preliminary"] for x in self.a
            if x["source_id"]==sid and x["pdf_page_zero_based"]==page
        ) for sid,page in pages}
        hashes={key:"a"*64 for key in pages}
        result=compare_to_actual_ocr(self.a,texts,hashes)
        self.assertEqual(result["preliminarily_visual_read_short_anchors_compared"],13)
        self.assertEqual(result["exact_original_short_phrases_retrieved_in_page_OCR"],13)
        self.assertEqual(result["exact_original_short_phrases_retrieved_in_single_OCR_line"],13)
        self.assertFalse(result["OCR_Han_character_error_rate_measured"])
        self.assertFalse(result["precision_of_all_922_M16_9_lexical_hits_measured"])
        self.assertEqual(result["full_page_original_human_transcriptions_approved"],0)
        self.assertEqual(result["new_live_faceface_rules"],0)
        data=json.dumps(result,ensure_ascii=False)
        for row in self.a:
            self.assertNotIn(row["short_original_image_phrase_preliminary"],data)

    def test_short_phrase_missed_by_OCR_does_not_get_auto_promoted(self):
        pages=source_pages(self.a)
        texts={(sid,i):"" for sid,i in pages}
        hashes={key:"" for key in pages}
        result=compare_to_actual_ocr(self.a,texts,hashes)
        self.assertEqual(result["exact_original_short_phrases_retrieved_in_page_OCR"],0)
        self.assertEqual(result["full_page_original_human_transcriptions_approved"],0)
        self.assertFalse(result["actual_Cangjie_five_agent_semantic_extraction"])

    def test_lack_of_page_OCR_is_hard_failure(self):
        pages=source_pages(self.a)
        texts={key:"口須方大" for key in pages[:-1]}
        hashes={key:"a"*64 for key in pages}
        with self.assertRaisesRegex(ValueError,"Every reviewed image-page"):
            compare_to_actual_ocr(self.a,texts,hashes)

    def test_fake_human_review_status_rejected(self):
        self.doc["anchors"][0]["full_page_transcription_reviewed"]=True
        with self.assertRaisesRegex(ValueError,"cannot be promoted"):
            validate_pilot(self.doc)

    def test_unsupported_photo_metric_rejected(self):
        self.doc["anchors"][0]["existing_faceface_metric"]="ear.shape"
        with self.assertRaisesRegex(ValueError,"Unimplemented browser"):
            validate_pilot(self.doc)

    def test_unmeasured_phrase_cannot_claim_a_photo_metric(self):
        self.doc["anchors"][0]["current_photo_overlap"]="not_measured"
        with self.assertRaisesRegex(ValueError,"Unmeasured"):
            validate_pilot(self.doc)

    def test_original_pdf_hash_mismatch_rejected(self):
        self.doc["pdf_sha256"]["nlc-44091"]="wrong"
        with self.assertRaisesRegex(ValueError,"Wrong original"):
            validate_pilot(self.doc)


if __name__=="__main__":
    unittest.main()
