"""M16.25: durable local-private pipeline crash recovery, authenticity and nonoverwriting.

Synthetic OCR/model fixtures are labeled explicitly; these tests do not run
Cangjie inference or claim human source verification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.cangjie_durable_private_batch import (
    run_persistent_batch, private_paths, VERSION, canonical_bytes,
)
from scripts.cangjie_private_ocr_semantic_batch import BATCH_KIND, read_private_cues
from scripts.cangjie_private_review_pack import assemble_review_items
from scripts.cangjie_real_historical_relations import translate_model_relations
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write


class FakeVerifiedOriginalScans:
    def __init__(self, scan_dir, ocr_dir, reviewed_dir):
        self.sources = {sid: {"pdf_sha256":sha} for sid,sha in KNOWN_SCAN_SHA256.items()}


class DurableLocalPrivateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.destination=self.root/"persistent-private-batch"
        self.scans=self.root/"originals"
        self.upstream=self.root/"cangjie"
        self.sid="nlc-44091"
        self.page=44
        self.sha=KNOWN_SCAN_SHA256[self.sid]
        self.original="鼻長有壽"
        self.calls={"ocr":0,"lexical":0,"model":0,"pack":0}

    def tearDown(self):
        self.tmp.cleanup()

    def fake_ocr(self, scans, target, source, first, last, dpi):
        self.calls["ocr"]+=1
        p=target/"transcripts"/source/f"{first:03d}.txt"
        atomic_write(p,(self.original+"\n").encode("utf-8"))
        meta=p.with_suffix(".ocr.json")
        atomic_write(meta,b'{"source_id":"nlc-44091","state":"ocr_candidate"}')
        data={"source_id":source,"first_pdf_page_zero_based":first,
              "last_pdf_page_zero_based":last,"processed_pages":1,
              "source_pdf_sha256":self.sha,
              "pages":[{"source_id":source,"pdf_page_zero_based":first,"state":"ocr_candidate"}]}
        report=target/"reports"/f"{source}-p{first:03d}-{last:03d}.json"
        atomic_write(report,canonical_bytes(data))
        return data

    def fake_audit(self, scans, ocr_dir, private_dir, public_dir, source, first, last):
        self.calls["lexical"]+=1
        cue={"cue_id":"a"*24,"source_id":source,"pdf_page_zero_based":first,
             "source_pdf_sha256":self.sha,
             "unreviewed_ocr_text_sha256":"b"*64,
             "short_ocr_line_unverified":self.original,
             "outcome_terms_UNVERIFIED":{"longevity":["壽"]},
             "same_OCR_line_morphology_regions":["nose"],
             "source_image_human_verified":False,
             "historical_relation_established":False,
             "eligible_for_live_rules":False}
        stem=f"{source}-p{first:03d}-{last:03d}"
        atomic_write(private_dir/f"{stem}.jsonl",(json.dumps(cue,ensure_ascii=False)+"\n").encode())
        atomic_write(public_dir/f"lexical-{stem}.json",canonical_bytes({
            "source_id":source,"first_pdf_page_zero_based":first,
            "last_pdf_page_zero_based":last,"source_pdf_sha256":self.sha
        }))

    def fake_model(self, sources, scans, upstream, private_out, public_out, *args, **kwargs):
        self.calls["model"]+=1
        selected, _=read_private_cues(sources)
        self.assertEqual(len(selected),1)
        result, rejected=translate_model_relations({"relations":[{
            "quote_id":0,"morphology_span":"鼻長","claim_span":"有壽",
            "condition_span":"","exception_span":"",
            "relation_type":"explicit_in_source","claim_domain":"longevity"
        }]},selected)
        self.assertEqual(rejected,[])
        private={"kind":BATCH_KIND,"full_book_source_text_verified":False,
                 "no_live_rules_created":True,"source_records_UNVERIFIED":selected,
                 "archival_ledger_SOURCE_UNVERIFIED":{
                     "schema":"faceface-historical-claims-v1","relations":result
                 },"rejections_private":[],"actual_model_requests_attempted":1}
        atomic_write(private_out,canonical_bytes(private))
        atomic_write(public_out,canonical_bytes({
            "selected_private_OCR_cues":1,"real_model_requests_attempted":1,
            "OCR_literal_draft_relations":1,"new_live_Faceface_rules":0
        }))

    def fake_pack(self, model_path, scans, output):
        self.calls["pack"]+=1
        private=json.loads(model_path.read_text(encoding="utf-8"))
        rows,summary=assemble_review_items(private)
        summary["real_original_PDF_images_rendered"]=1
        atomic_write(output/"private-OCR-model-evidence.json",canonical_bytes({"items":rows}))
        atomic_write(output/"private-review-decisions.json",canonical_bytes({"status":"pending"}))
        atomic_write(output/"private-pack-manifest.json",canonical_bytes(summary))
        atomic_write(output/"index.html",b"<html><body>PRIVATE SYNTHETIC TEST</body></html>")
        atomic_write(output/"pages"/"nlc-44091-p044.png",b"PNG SYNTHETIC ONLY - NO REAL IMAGE CLAIM")

    def pipeline(self, resume=False):
        with (patch("scripts.cangjie_durable_private_batch.ReviewWorkspace", FakeVerifiedOriginalScans),
              patch("scripts.cangjie_durable_private_batch.run_original_ocr",self.fake_ocr),
              patch("scripts.cangjie_durable_private_batch.audit_shard",self.fake_audit),
              patch("scripts.cangjie_durable_private_batch.run_private_batch",self.fake_model),
              patch("scripts.cangjie_durable_private_batch.build_pack",self.fake_pack)):
            return run_persistent_batch(self.destination,self.scans,self.upstream,
                                        self.sid,self.page,self.page,1,170,resume)

    def test_whole_private_batch_preserves_evidence_and_resume_skips_inference(self):
        report=self.pipeline()
        self.assertEqual(report["actual_Qwen_requests"],1)
        self.assertEqual(report["source_human_verified_pages"],0)
        self.assertEqual(self.calls,{"ocr":1,"lexical":1,"model":1,"pack":1})
        manifest=json.loads((self.destination/"batch-manifest.json").read_text())
        self.assertEqual(len(manifest["completed"]),5)
        self.assertIn("inferred",manifest["completed"])
        self.pipeline(resume=True)
        self.assertEqual(self.calls,{"ocr":1,"lexical":1,"model":1,"pack":1})

    def test_rejects_tampered_ocr_before_reusing_model(self):
        self.pipeline()
        paths=private_paths(self.destination,self.sid,self.page,self.page)
        ocr_text=paths["ocr_root"]/"transcripts"/self.sid/"044.txt"
        ocr_text.write_text("OCR changed",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"PRIVATE EVIDENCE CHANGED"):
            self.pipeline(resume=True)
        self.assertEqual(self.calls["model"],1)

    def test_recovers_completed_inference_and_workpack_not_in_manifest(self):
        self.pipeline()
        path=self.destination/"batch-manifest.json"
        data=json.loads(path.read_text(encoding="utf-8"))
        del data["completed"]["inferred"]
        del data["completed"]["review_pack"]
        atomic_write(path,canonical_bytes(data))
        self.pipeline(resume=True)
        self.assertEqual(self.calls,{"ocr":1,"lexical":1,"model":1,"pack":1})

    def test_refuses_replacement_and_changed_run_parameters(self):
        self.pipeline()
        with self.assertRaises(ValueError):
            self.pipeline(resume=False)
        with patch("scripts.cangjie_durable_private_batch.ReviewWorkspace",FakeVerifiedOriginalScans):
            with self.assertRaisesRegex(ValueError,"parameters"):
                run_persistent_batch(self.destination,self.scans,self.upstream,
                                     self.sid,self.page,self.page,2,170,True)

    def test_partial_workpack_is_not_destroyed_or_replaced(self):
        self.pipeline()
        path=self.destination/"batch-manifest.json"
        data=json.loads(path.read_text(encoding="utf-8"))
        del data["completed"]["review_pack"]
        atomic_write(path,canonical_bytes(data))
        work=private_paths(self.destination,self.sid,self.page,self.page)["review_pack"]
        (work/"private-pack-manifest.json").unlink()
        with self.assertRaisesRegex(ValueError,"PARTIAL PRIVATE STAGE"):
            self.pipeline(resume=True)
        self.assertEqual(self.calls["pack"],1)

    def test_no_private_files_inside_repository(self):
        from scripts.cangjie_durable_private_batch import verify_scope
        with patch("scripts.cangjie_durable_private_batch.ReviewWorkspace",FakeVerifiedOriginalScans):
            repo=Path(__file__).resolve().parents[1]
            with self.assertRaisesRegex(ValueError,"OUTSIDE"):
                verify_scope(repo/"user-faceface-ocr",self.scans,self.sid,44,44,1,170,False)


if __name__=="__main__":
    unittest.main()
