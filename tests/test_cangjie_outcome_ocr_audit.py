"""M16.21 ancient outcome scan and exactly 268 page evidence contract."""
import copy
import hashlib
import unittest

from scripts.cangjie_outcome_ocr_audit import audit_source_page, outcome_terms_for_line
from scripts.cangjie_outcome_ocr_aggregate import aggregate
from scripts.cangjie_corpus_stage import SCANS
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256


class OutcomeLexicalAuditTests(unittest.TestCase):
    def test_longevity_shape_and_no_shape_are_preserved_independently(self):
        p, private = audit_source_page(
            "鼻長有壽\n長壽\n目清", "nlc-44091", 77,
            KNOWN_SCAN_SHA256["nlc-44091"], "a"*64
        )
        self.assertEqual(p["outcome_ocr_line_hits_by_domain"]["longevity"], 2)
        self.assertEqual(p["outcome_ocr_line_with_morphology_proximity_by_domain"]["longevity"], 1)
        self.assertEqual(len(private), 2)
        self.assertTrue(all(x["historical_relation_established"] is False for x in private))

    def test_nose_anatomical_term_is_not_longevity_evidence(self):
        self.assertNotIn("longevity", outcome_terms_for_line("鼻之年壽須平"))
        self.assertIn("longevity", outcome_terms_for_line("年壽長壽"))

    def test_shape_only_does_not_create_outcomes(self):
        p, cues = audit_source_page(
            "口須方大", "nlc-44091", 27,
            KNOWN_SCAN_SHA256["nlc-44091"], "b"*64
        )
        self.assertEqual(p["outcome_ocr_line_hits_by_domain"], {})
        self.assertEqual(cues, [])

    def test_wealth_and_moral_markers_remain_separate_candidates(self):
        p, cues = audit_source_page(
            "鼻豐富貴\n忠厚", "nlc-44091", 27,
            KNOWN_SCAN_SHA256["nlc-44091"], "b"*64
        )
        self.assertIn("wealth", p["outcome_ocr_line_hits_by_domain"])
        self.assertIn("moral_character", p["outcome_ocr_line_hits_by_domain"])
        self.assertEqual(len(cues), 2)
        self.assertFalse(cues[1]["historical_relation_established"])

    def _full_reports(self):
        reports = []
        for src in SCANS:
            sid = src["id"]
            pages=[]
            for index in range(src["expected_pages"]):
                pid=f"{sid}:p{index:03d}"
                pages.append({
                    "page_id":pid, "source_id":sid,
                    "pdf_page_zero_based":index,
                    "source_pdf_sha256":KNOWN_SCAN_SHA256[sid],
                    "ocr_text_sha256":None, "OCR_state":"empty_ocr_candidate",
                    "outcome_ocr_line_hits_by_domain":{},
                    "outcome_ocr_line_with_morphology_proximity_by_domain":{},
                    "historical_relation_confirmed":False, "human_reviewed":False,
                })
            reports.append({
                "kind":"M16.21_REAL_1925_UNREVIEWED_OCR_TRADITIONAL_OUTCOME_V1",
                "source_id":sid,
                "source_pdf_sha256":KNOWN_SCAN_SHA256[sid],
                "first_pdf_page_zero_based":0,
                "last_pdf_page_zero_based":src["expected_pages"]-1,
                "processed_original_pages":len(pages),
                "pages_with_any_outcome_lexical_signal":0,
                "pages":pages,
                "actual_human_confirmed_historical_relations":0,
                "official_Cangjie_model_calls":0,
                "new_live_Faceface_rules":0,
                "metadata_contains_ancient_ocr_text":False
            })
        return reports

    def test_aggregate_exact_268_count(self):
        result=aggregate(self._full_reports())
        self.assertEqual(result["actual_source_pages_processed"], 268)
        self.assertEqual(result["pages_with_no_outcome_lexical_signal"], 268)
        self.assertEqual(result["historically_valid_morphology_outcome_relations"], 0)

    def test_missing_or_duplicate_page_fails(self):
        docs=self._full_reports()
        docs[0]["pages"].pop()
        with self.assertRaises(ValueError):
            aggregate(docs)
        docs=self._full_reports()
        docs[0]["pages"][1]=copy.deepcopy(docs[0]["pages"][0])
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            aggregate(docs)

    def test_unreviewed_must_not_be_silently_promoted(self):
        docs=self._full_reports()
        docs[0]["pages"][0]["historical_relation_confirmed"]=True
        with self.assertRaises(ValueError):
            aggregate(docs)


if __name__ == "__main__":
    unittest.main()
