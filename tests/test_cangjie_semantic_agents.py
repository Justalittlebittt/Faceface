"""M16.8: true Cangjie five-role extraction, no fake quotes or source approvals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.cangjie_review_core import ReviewWorkspace, file_sha256, atomic_write
from scripts.cangjie_semantic_agents import (
    ADLER_SCHEMA, CANDIDATE_SCHEMA, MODEL, ROLE_FILES,
    TextModel, page_evidence, parse_pages, upstream_prompts,
    validate_adler, validate_candidates, run_agents
)
from scripts.cangjie_working_corpus import PINNED_CANGJIE_COMMIT


class FakeCangjieModel:
    model=MODEL
    def __init__(self):
        self.called=[]

    def installed(self):
        return True

    def infer(self,system,user,schema):
        self.called.append((system,user,schema))
        if schema==ADLER_SCHEMA:
            return {
                "one_sentence_thesis":"仅供校核的样本结构假说",
                "structure_hypotheses":["五官形态"],
                "key_term_hypotheses":["口"],
                "critical_limitations":["OCR可能错列"],
                "faceface_applicability":"只描述可观察形态",
                "missing_evidence":["未读完整268页"]
            }
        if "原书如无有步骤的观察框架" in system:
            # Official framework extractor should be allowed to find nothing.
            return {"candidates":[]}
        return {"candidates":[{
            "title":"传统口形描述",
            "quote_id":0,
            "summary":"古籍页面中出现传统口部形态词，需回原图校核。",
            "observability":"photo_partial",
            "interference":"角度和表情"
        }]}


class CangjieSemanticTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root=Path(root.name)
        self.scans=self.root/"scans"
        self.scans.mkdir()
        (self.scans/"part1.pdf").write_bytes(b"%PDF-synthetic-first")
        (self.scans/"part2.pdf").write_bytes(b"%PDF-synthetic-second")
        known={
            "nlc-44091":file_sha256(self.scans/"part1.pdf"),
            "nlc-44092":file_sha256(self.scans/"part2.pdf")
        }
        self.ocr=self.root/"ocr"
        self.reviewed=self.root/"reviewed"
        with patch("scripts.cangjie_review_core.pdf_pages",
                   side_effect=lambda x:153 if x.name=="part1.pdf" else 115):
            self.workspace=ReviewWorkspace(self.scans,self.ocr,self.reviewed,
                                           expected_hashes=known)
        self.upstream=self.root/"upstream"
        (self.upstream/"methodology").mkdir(parents=True)
        (self.upstream/"extractors").mkdir()
        (self.upstream/"SKILL.md").write_text("official skill",encoding="utf-8")
        (self.upstream/"methodology"/"01-stage0-adler.md").write_text(
            "官方Adler结构假说\n"*100,encoding="utf-8"
        )
        for filename in ROLE_FILES.values():
            (self.upstream/"extractors"/filename).write_text(
                f"官方角色提示文件{filename}\n"*100,encoding="utf-8"
            )
        self.out=self.root/"research"

    def put_ocr(self,sid,index,text):
        paths=self.workspace.page_paths(sid,index)
        atomic_write(paths["candidate"],text.encode("utf-8"))
        atomic_write(paths["candidate_meta"],json.dumps({
            "source_id":sid,
            "source_pdf_sha256":self.workspace.sources[sid]["pdf_sha256"],
            "pdf_page_zero_based":index,
            "candidate_text_sha256":file_sha256(paths["candidate"]),
            "eligible_for_cangjie_verified_corpus":False,
        }).encode("utf-8"))

    def mock_git(self):
        return patch("scripts.cangjie_semantic_agents.subprocess.run",
                     return_value=MagicMock(stdout=PINNED_CANGJIE_COMMIT+"\n"))

    def test_page_id_validation_and_full_book_268_page_coverage(self):
        pages=parse_pages(self.workspace,None)
        self.assertEqual(len(pages),268)
        self.assertEqual(len(set(pages)),268)
        self.assertEqual(
            parse_pages(self.workspace,"nlc-44091:p027,nlc-44092:p040"),
            [("nlc-44091",27),("nlc-44092",40)]
        )
        for bad in ("nlc-44091:p153","nlc-44091:p027,nlc-44091:p027",
                    "../bad", "nlc-44092:p115"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                parse_pages(self.workspace,bad)

    def test_source_hash_binds_ocr_and_wrong_hash_cannot_be_extracted(self):
        self.put_ocr("nlc-44091",27,"口須方大，或細長。")
        records=page_evidence(self.workspace,[("nlc-44091",27),("nlc-44091",28)])
        self.assertEqual(records[0]["source_text_status"],"ocr_unreviewed")
        self.assertEqual(records[0]["ocr_candidate_sha256"],
                         file_sha256(self.workspace.page_paths("nlc-44091",27)["candidate"]))
        self.assertEqual(records[1]["source_text_status"],"missing_source_text")
        paths=self.workspace.page_paths("nlc-44091",27)
        paths["candidate"].write_text("偷偷替換",encoding="utf-8")
        records=page_evidence(self.workspace,[("nlc-44091",27)])
        self.assertEqual(records[0]["source_text_status"],"missing_source_text")

    def test_upstream_pinned_and_real_prompts_not_fake_short_stub(self):
        with self.mock_git():
            adler,roles=upstream_prompts(self.upstream)
        self.assertIn("Adler",adler)
        self.assertEqual(set(roles),set(ROLE_FILES))
        with patch("scripts.cangjie_semantic_agents.subprocess.run",
                   return_value=MagicMock(stdout="wrong-sha\n")):
            with self.assertRaisesRegex(ValueError,"Wrong upstream Cangjie"):
                upstream_prompts(self.upstream)

    def test_long_ambiguous_or_non_source_quote_is_rejected(self):
        self.put_ocr("nlc-44091",27,"口須方大，或細長。")
        record=page_evidence(self.workspace,[("nlc-44091",27)])[0]
        row={
            "title":"口形","quote_id":0,
            "summary":"古籍口形描述",
            "observability":"photo_partial","interference":"表情"
        }
        accepted,rejected=validate_candidates({"candidates":[row]},record,"principle")
        self.assertEqual(len(accepted),1)
        self.assertEqual(len(rejected),0)
        self.assertFalse(accepted[0]["quote_original_scan_verified"])
        self.assertFalse(accepted[0]["auto_activated_faceface_rule"])
        row["quote_id"]=99
        accepted,rejected=validate_candidates({"candidates":[row]},record,"principle")
        self.assertEqual(len(accepted),0)
        self.assertEqual(rejected[0]["reason"],"unknown_OCR_quote_ID")

    def test_real_agent_orchestrator_invokes_five_independent_roles_and_adler(self):
        self.put_ocr("nlc-44091",27,"口須方大，或細長。")
        with self.mock_git():
            model=FakeCangjieModel()
            report=run_agents(
                self.workspace,[("nlc-44091",27)],self.upstream,
                model,self.out,run_adler=True
            )
        self.assertEqual(len(model.called),6)
        self.assertTrue(report["actual_Adler_model_completed"])
        self.assertEqual(report["actual_extractor_calls_successful"],5)
        self.assertEqual(set(report["independent_extractor_roles_invoked"]),set(ROLE_FILES))
        self.assertEqual(report["source_OCR_pages_in_this_execution"],1)
        self.assertFalse(report["Adler_is_whole_book"])
        self.assertEqual(report["new_live_faceface_rules"],0)
        # 4 named extractor roles yielded valid literal source quote; framework empty
        self.assertEqual(sum(report["OCR_quote_match_candidates"].values()),4)
        ov=json.loads((self.out/"BOOK_OVERVIEW_SOURCE_UNVERIFIED_PILOT.json").read_text("utf-8"))
        self.assertFalse(ov["whole_book_understood"])
        results=json.loads((self.out/"five-extractor-candidates-SOURCE_UNVERIFIED.json").read_text("utf-8"))
        self.assertEqual(len(results["candidates"]),4)
        self.assertTrue(all(not c["quote_original_scan_verified"] for c in results["candidates"]))
        self.assertTrue(all(not c["auto_activated_faceface_rule"] for c in results["candidates"]))
        # Actual role calls must NOT get prior role-generated outputs.
        for system,user,schema in model.called[1:]:
            self.assertNotIn("OCR_quote_match_candidates",user)
            self.assertIn("口須方大",user)

    def test_text_model_rejects_nonloopback(self):
        with self.assertRaisesRegex(ValueError,"localhost"):
            TextModel("https://example.com:443",MODEL)


if __name__=="__main__":
    unittest.main()
