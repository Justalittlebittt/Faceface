"""M16.26: reconstruct exact original OCR target line and neighboring context.

Synthetic fixtures model unreviewed OCR; no original page has been manually
proofread, no historical or personal prediction is authorized.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.cangjie_private_context_quality import audit_context, html_report
from scripts.cangjie_private_ocr_semantic_batch import BATCH_KIND
from scripts.cangjie_real_historical_relations import translate_model_relations
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, file_sha256
from scripts.cangjie_paddleocr_candidates import OCR_ID, ENGINE
from scripts.cangjie_morphology_mine import han_only


class OCRContextQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.ocr=self.root/"ocr"
        self.selected=self.root/"selected.jsonl"
        self.model=self.root/"private-model.json"
        self.sid="nlc-44091"
        self.page=33
        self.lines=["山根為主", "鼻長有壽", "耳厚乃貴", "另有五官"]
        self.write_case()

    def tearDown(self):
        self.temp.cleanup()

    def write_case(self, model_claim="有壽"):
        path=self.ocr/"transcripts"/self.sid/f"{self.page:03d}.txt"
        atomic_write(path,("\n".join(self.lines)+"\n").encode())
        sha=file_sha256(path)
        target=han_only(self.lines[1])
        cue_id=hashlib.sha256(
            f"{self.sid}:p{self.page:03d}|{sha}|1|{target}".encode()
        ).hexdigest()[:24]
        cue={
            "cue_id":cue_id,
            "source_id":self.sid,
            "pdf_page_zero_based":self.page,
            "source_pdf_sha256":KNOWN_SCAN_SHA256[self.sid],
            "unreviewed_ocr_text_sha256":sha,
            "ocr_line_index_zero_based":1,
            "short_ocr_line_unverified":target[:80],
            "outcome_terms_UNVERIFIED":{"longevity":["壽"]},
            "same_OCR_line_morphology_regions":["nose"],
            "source_image_human_verified":False,
            "historical_relation_established":False,
            "eligible_for_live_rules":False,
        }
        atomic_write(self.selected,(json.dumps(cue,ensure_ascii=False)+"\n").encode())
        source={
            "id":"m1622-ocr:"+cue_id,
            "legacy_entry_kind":"unverified_ocr_page_line",
            "source_id":self.sid,
            "pdf_page_zero_based":self.page,
            "page_id":f"{self.sid}:p{self.page:03d}",
            "original_pdf_sha256":KNOWN_SCAN_SHA256[self.sid],
            "source_excerpt":target,
            "source_excerpt_sha256":hashlib.sha256(target.encode()).hexdigest(),
            "unreviewed_ocr_text_sha256":sha,
            "candidate_lexical_domains":["longevity"],
            "source_excerpt_newly_human_reviewed":False,
            "this_experiment_may_add_live_rule":False,
        }
        model_rows,rejections=translate_model_relations({"relations":[{
            "quote_id":0,"morphology_span":"鼻長","claim_span":model_claim,
            "condition_span":"","exception_span":"",
            "relation_type":"explicit_in_source","claim_domain":"longevity"
        }]},[source])
        self.assertEqual(rejections,[])
        raw={
            "kind":BATCH_KIND,
            "full_book_source_text_verified":False,
            "no_live_rules_created":True,
            "source_records_UNVERIFIED":[source],
            "archival_ledger_SOURCE_UNVERIFIED":{
                "schema":"faceface-historical-claims-v1","relations":model_rows},
            "rejections_private":[],
            "actual_model_requests_attempted":1
        }
        atomic_write(self.model,(json.dumps(raw,ensure_ascii=False)+"\n").encode())
        meta={
            "source_id":self.sid,"pdf_page_zero_based":self.page,
            "source_pdf_sha256":KNOWN_SCAN_SHA256[self.sid],
            "ocr_version":OCR_ID,"engine":ENGINE,"state":"ocr_candidate",
            "candidate_text_sha256":sha,
            "eligible_for_cangjie_verified_corpus":False,
            "requires_manual_page_review":True
        }
        atomic_write(path.with_suffix(".ocr.json"),(json.dumps(meta)+"\n").encode())

    def test_actual_ocr_line_index_and_neighborhood_are_retained(self):
        rows,stats=audit_context(self.selected,self.model,self.ocr)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["exact_target_OCR_line_unreviewed"],"鼻長有壽")
        self.assertEqual(rows[0]["preceding_OCR_lines_unreviewed"],["山根為主"])
        self.assertEqual(rows[0]["following_OCR_lines_unreviewed"],["耳厚乃貴","另有五官"])
        self.assertIn("neighboring_OCR_line_contains_outcome",
                      rows[0]["lexical_risk_flags_NOT_probabilities"])
        self.assertEqual(stats["verified_source_image_transcriptions"],0)
        self.assertEqual(stats["new_live_Faceface_rules"],0)

    def test_changed_full_page_ocr_text_is_rejected(self):
        path=self.ocr/"transcripts"/self.sid/f"{self.page:03d}.txt"
        path.write_text("鼻長有壽\n",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Tampered"):
            audit_context(self.selected,self.model,self.ocr)

    def test_wrong_real_line_index_and_forged_cue_id_rejected(self):
        row=json.loads(self.selected.read_text(encoding="utf-8"))
        row["ocr_line_index_zero_based"]=0
        atomic_write(self.selected,(json.dumps(row,ensure_ascii=False)+"\n").encode())
        with self.assertRaisesRegex(ValueError,"line/index"):
            audit_context(self.selected,self.model,self.ocr)

    def test_model_source_references_must_equal_selected_source(self):
        model=json.loads(self.model.read_text(encoding="utf-8"))
        model["source_records_UNVERIFIED"][0]["source_excerpt"]="鼻短有壽"
        atomic_write(self.model,(json.dumps(model,ensure_ascii=False)+"\n").encode())
        with self.assertRaises(ValueError):
            audit_context(self.selected,self.model,self.ocr)

    def test_ocr_context_order_is_not_claimed_verified(self):
        rows,stats=audit_context(self.selected,self.model,self.ocr,neighbor_radius=1)
        self.assertEqual(rows[0]["following_OCR_lines_unreviewed"],["耳厚乃貴"])
        self.assertIs(stats["OCR_reading_order_human_verified"],False)
        html=html_report(rows,stats)
        self.assertIn("非可靠古籍阅读顺序",html)
        self.assertNotIn("<script>",html)

    def test_radius_restriction(self):
        with self.assertRaises(ValueError):
            audit_context(self.selected,self.model,self.ocr,0)


if __name__=="__main__":
    unittest.main()
