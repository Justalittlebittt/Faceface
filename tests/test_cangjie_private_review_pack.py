"""M16.24: private original image review workpack source proof and no promotions."""
import hashlib
import json
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from scripts.cangjie_private_review_pack import assemble_review_items, build_pack, make_review_html, audit_manual_decisions
from scripts.cangjie_private_ocr_semantic_batch import BATCH_KIND
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256
from scripts.cangjie_real_historical_relations import translate_model_relations


class PrivateOriginalReviewPackTests(unittest.TestCase):
    def setUp(self):
        self.sid = "nlc-44091"
        self.quote = "鼻長有壽"
        self.src = {
            "id":"m1622-ocr:"+"a"*24,
            "source_id": self.sid,
            "pdf_page_zero_based": 44,
            "page_id":"nlc-44091:p044",
            "original_pdf_sha256":KNOWN_SCAN_SHA256[self.sid],
            "source_excerpt":self.quote,
            "source_excerpt_sha256":hashlib.sha256(self.quote.encode()).hexdigest(),
            "unreviewed_ocr_text_sha256":"b"*64,
            "candidate_lexical_domains":["longevity"],
            "source_excerpt_newly_human_reviewed":False,
            "this_experiment_may_add_live_rule":False,
        }
        matched,_=translate_model_relations({"relations":[{
            "quote_id":0,"morphology_span":"鼻長","claim_span":"有壽",
            "condition_span":"","exception_span":"",
            "relation_type":"explicit_in_source","claim_domain":"longevity",
        }]},[self.src])
        self.private = {
            "kind":BATCH_KIND,
            "full_book_source_text_verified":False,
            "no_live_rules_created":True,
            "source_records_UNVERIFIED":[self.src],
            "archival_ledger_SOURCE_UNVERIFIED":{"schema":"faceface-historical-claims-v1","relations":matched},
            "rejections_private":[{"source_id":self.src["id"],"reason":"model_span_not_literal_original"}],
            "actual_model_requests_attempted":1,
        }

    def test_archive_candidate_produces_reviewable_private_source_item(self):
        items,audit=assemble_review_items(self.private)
        self.assertEqual(audit["source_count"],1)
        self.assertEqual(audit["literal_OCR_model_drafts"],1)
        self.assertEqual(audit["rejected_model_events"],1)
        self.assertEqual(audit["human_full_page_reviews_by_this_build"],0)
        self.assertEqual(items[0]["unreviewed_OCR_excerpt"],"鼻長有壽")
        self.assertFalse(items[0]["eligible_for_live_rules"])

    def test_unknown_source_or_model_quote_refused(self):
        forged=json.loads(json.dumps(self.private,ensure_ascii=False))
        forged["source_records_UNVERIFIED"][0]["original_pdf_sha256"]="0"*64
        with self.assertRaises(ValueError):
            assemble_review_items(forged)
        forged=json.loads(json.dumps(self.private,ensure_ascii=False))
        forged["archival_ledger_SOURCE_UNVERIFIED"]["relations"][0]["source_passage_id"]="unknown"
        with self.assertRaises(ValueError):
            assemble_review_items(forged)

    def test_only_public_summary_has_no_unreviewed_text(self):
        rows,stats=assemble_review_items(self.private)
        self.assertNotIn("鼻長有壽", json.dumps(stats,ensure_ascii=False))
        html=make_review_html(rows,stats)
        self.assertIn("鼻長有壽",html)
        self.assertIn("pages/nlc-44091-p044.png",html)

    def test_html_escapes_untrusted_ocr_text(self):
        row = {
            "candidate_id":"m1622-ocr:"+"a"*24,
            "source_id":self.sid,
            "pdf_page_zero_based":44,
            "page_id":"nlc-44091:p044",
            "unreviewed_OCR_excerpt":"<script>alert(1)</script>",
            "accepted_model_relations_unverified":[],
            "model_rejections":[],
        }
        markup=make_review_html([row],{"source_count":1,"distinct_original_pages":1})
        self.assertNotIn("<script>alert",markup)
        self.assertIn("&lt;script&gt;",markup)

    def test_manual_short_review_decision_requires_real_named_attestation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            pack=root/"workpack"
            pack.mkdir()
            items,summary=assemble_review_items(self.private)
            (pack/"private-OCR-model-evidence.json").write_text(
                json.dumps(items,ensure_ascii=False),encoding="utf-8")
            (pack/"private-pack-manifest.json").write_text(
                json.dumps(summary,ensure_ascii=False),encoding="utf-8")
            decision={
                "schema":"M16.24_PRIVATE_SHORT_EXCERPT_DECISIONS_TEMPLATE_V1",
                "full_page_transcription_reviewed":False,
                "items":[{
                    "candidate_id":items[0]["candidate_id"],
                    "source_id":items[0]["source_id"],
                    "pdf_page_zero_based":items[0]["pdf_page_zero_based"],
                    "original_pdf_sha256":items[0]["original_pdf_sha256"],
                    "ocr_excerpt_sha256":items[0]["unreviewed_OCR_excerpt_sha256"],
                    "status":"short_span_confirmed",
                    "reviewer":"agent",
                    "manually_corrected_original_text":"鼻長有壽",
                    "confirmed_against_original_page_image":True,
                    "review_notes":""
                }]
            }
            path=pack/"private-review-decisions.json"
            path.write_text(json.dumps(decision,ensure_ascii=False),encoding="utf-8")
            with self.assertRaises(ValueError):
                audit_manual_decisions(pack,root/"bad.json")
            decision["items"][0]["reviewer"]="human-auditor-001"
            path.write_text(json.dumps(decision,ensure_ascii=False),encoding="utf-8")
            result=audit_manual_decisions(pack,root/"manual-audit.json")
            self.assertEqual(result["named_human_short_span_attestations"],1)
            self.assertEqual(result["new_full_page_verified_transcriptions"],0)
            self.assertEqual(result["live_rules_created"],0)
            with self.assertRaises(ValueError):
                audit_manual_decisions(pack,root/"manual-audit.json")

    def test_manual_decision_cannot_change_ocr_source_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            pack=root/"workpack"
            pack.mkdir()
            items,summary=assemble_review_items(self.private)
            (pack/"private-OCR-model-evidence.json").write_text(
                json.dumps(items,ensure_ascii=False),encoding="utf-8")
            (pack/"private-pack-manifest.json").write_text(
                json.dumps(summary,ensure_ascii=False),encoding="utf-8")
            (pack/"private-review-decisions.json").write_text(json.dumps({
                "schema":"M16.24_PRIVATE_SHORT_EXCERPT_DECISIONS_TEMPLATE_V1",
                "full_page_transcription_reviewed":False,
                "items":[{
                    "candidate_id":items[0]["candidate_id"],
                    "source_id":items[0]["source_id"],
                    "pdf_page_zero_based":items[0]["pdf_page_zero_based"],
                    "original_pdf_sha256":"0"*64,
                    "ocr_excerpt_sha256":items[0]["unreviewed_OCR_excerpt_sha256"],
                    "status":"pending","reviewer":"",
                    "manually_corrected_original_text":"",
                    "confirmed_against_original_page_image":False,
                    "review_notes":""
                }]
            },ensure_ascii=False),encoding="utf-8")
            with self.assertRaises(ValueError):
                audit_manual_decisions(pack,root/"audit.json")

    def test_missing_real_scans_cannot_forge_png(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            record=root/"private.json"
            record.write_text(json.dumps(self.private,ensure_ascii=False),encoding="utf-8")
            with self.assertRaises(ValueError):
                build_pack(record,root/"nonexistent-originals",root/"review")

    def test_existing_manual_review_workpack_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            record=root/"private.json"
            record.write_text(json.dumps(self.private,ensure_ascii=False),encoding="utf-8")
            (root/"review").mkdir()
            with self.assertRaises(ValueError):
                build_pack(record,root/"nonexistent-originals",root/"review")


if __name__=="__main__":
    unittest.main()
