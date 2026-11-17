"""M16.6 independent audit: 268 source pages, draft source fidelity and review risk."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.cangjie_review_core import ReviewWorkspace, file_sha256, atomic_write
from scripts.cangjie_vision_agent_batch import (
    DEFAULT_MODEL, DRAFT_PIPELINE, PROMPT_VERSION,
    draft_paths, input_fingerprint
)
from scripts.cangjie_vision_draft_audit import audit


class VisionDraftAuditTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.scans=self.root/"scans"
        self.scans.mkdir()
        (self.scans/"part1.pdf").write_bytes(b"%PDF-synthetic-one")
        (self.scans/"part2.pdf").write_bytes(b"%PDF-synthetic-two")
        self.drafts=self.root/"agent-drafts"
        self.ocr=self.root/"ocr"
        self.reviewed=self.root/"reviewed"
        hashes={
            "nlc-44091":file_sha256(self.scans/"part1.pdf"),
            "nlc-44092":file_sha256(self.scans/"part2.pdf")
        }
        with patch("scripts.cangjie_review_core.pdf_pages",
                   side_effect=lambda p:153 if p.name=="part1.pdf" else 115):
            self.w=ReviewWorkspace(
                self.scans,self.ocr,self.reviewed,
                expected_hashes=hashes,draft_dir=self.drafts
            )
        self.catalog={"cards":[{
            "source_phrase":"額為衡山；鼻為嵩山",
            "source":{"source_url":"https://commons.wikimedia.org/wiki/44091",
                      "pdf_page_zero_based":27}
        }],"framework_notes":[]}

    def add_draft(self):
        sid,index="nlc-44091",27
        sha=self.w.sources[sid]["pdf_sha256"]
        txt,meta=draft_paths(self.drafts,sid,index)
        raw="額為衡山\n".encode("utf-8")
        atomic_write(txt,raw)
        m={
            "pipeline":DRAFT_PIPELINE,"prompt_version":PROMPT_VERSION,
            "source_id":sid,"pdf_page_zero_based":index,
            "source_pdf_sha256":sha,"ocr_candidate_sha256":None,
            "input_fingerprint":input_fingerprint(sha,index,None,DEFAULT_MODEL),
            "model":DEFAULT_MODEL,
            "draft_text_sha256":hashlib.sha256(raw).hexdigest(),
            "page_type":"text_and_figures",
            "uncertain_spans":["鼻旁一字未辨"],
            "figure_notes":["含五官示意"],
            "reading_order_notes":"右起左行",
            "printed_volume_guess":"卷一",
            "section_guess":"五官",
            "eligible_for_cangjie_verified_corpus":False,
            "human_reviewed":False
        }
        atomic_write(meta,(json.dumps(m,ensure_ascii=False)+"\n").encode("utf-8"))
        return txt,meta

    def test_all_268_missing_is_not_fake_success(self):
        a=audit(self.w,self.drafts,self.catalog,DEFAULT_MODEL)
        self.assertEqual(a["original_pdf_pages"],268)
        self.assertEqual(a["states"]["missing_agent_draft"],268)
        self.assertEqual(a["reference_anchors_on_scored_draft_pages"],0)
        self.assertEqual(a["source_checked_reference_anchor_total"],2)
        self.assertTrue(a["reference_anchor_metric_is_diagnostic_not_CER"])
        self.assertEqual(a["agent_promotions_to_original_reviewed"],0)

    def test_detects_page_types_ambiguous_figures_and_reference_exact_hits(self):
        self.add_draft()
        a=audit(self.w,self.drafts,self.catalog,DEFAULT_MODEL)
        self.assertEqual(a["states"]["valid_unreviewed_agent_draft"],1)
        self.assertEqual(a["states"]["missing_agent_draft"],267)
        self.assertEqual(a["source_checked_reference_anchor_total"],2)
        self.assertEqual(a["reference_anchors_on_scored_draft_pages"],2)
        self.assertEqual(a["reference_anchors_found_in_valid_agent_drafts"],1)
        self.assertEqual(a["agent_draft_page_types"]["text_and_figures"],1)
        self.assertEqual(a["priority_review_pages"],1)
        self.assertIn("uncertain_characters",a["priority"][0]["reason"])
        self.assertEqual(a["agent_promotions_to_original_reviewed"],0)

    def test_tampered_agent_draft_is_blocked_not_scored(self):
        txt,meta=self.add_draft()
        txt.write_text("篡改內容\n",encoding="utf-8")
        a=audit(self.w,self.drafts,self.catalog,DEFAULT_MODEL)
        self.assertEqual(a["states"]["invalid_or_stale_agent_draft"],1)
        self.assertEqual(a["reference_anchors_found_in_valid_agent_drafts"],0)
        self.assertEqual(a["priority"][0]["priority"],"blocked")
        self.assertEqual(a["priority_review_pages"],1)

    def test_human_review_takes_precedence_over_agent(self):
        self.add_draft()
        self.w.save_review("nlc-44091",27,"額為衡山","actual-human",True)
        a=audit(self.w,self.drafts,self.catalog,DEFAULT_MODEL)
        self.assertEqual(a["states"]["human_reviewed"],1)
        self.assertNotIn("valid_unreviewed_agent_draft",a["states"])
        self.assertEqual(a["priority_review_pages"],0)


if __name__=="__main__":
    unittest.main()
