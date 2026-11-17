"""M16.7 source-bound full-book OCR -> private unverified Cangjie corpus."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from scripts.cangjie_review_core import ReviewWorkspace, atomic_write, file_sha256
from scripts.cangjie_working_corpus import (
    PINNED_CANGJIE_COMMIT, compile_corpus, official_chunks
)


class WorkingCorpusTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.scans=self.root/"scans"
        self.scans.mkdir()
        (self.scans/"part1.pdf").write_bytes(b"%PDF-synthetic-A")
        (self.scans/"part2.pdf").write_bytes(b"%PDF-synthetic-B")
        self.ocr=self.root/"ocr"
        self.reviewed=self.root/"reviewed"
        self.out=self.root/"private-working"
        hash_map={
            "nlc-44091":file_sha256(self.scans/"part1.pdf"),
            "nlc-44092":file_sha256(self.scans/"part2.pdf"),
        }
        with patch("scripts.cangjie_review_core.pdf_pages",
                   side_effect=lambda f:153 if f.name=="part1.pdf" else 115):
            self.w=ReviewWorkspace(self.scans,self.ocr,self.reviewed,
                                   expected_hashes=hash_map)

    def candidate(self,source,index,content,correct=True):
        p=self.w.page_paths(source,index)
        atomic_write(p["candidate"],content.encode("utf-8"))
        meta={
            "source_pdf_sha256":self.w.sources[source]["pdf_sha256"] if correct else "bad",
            "pdf_page_zero_based":index,
            "candidate_text_sha256":file_sha256(p["candidate"]),
            "eligible_for_cangjie_verified_corpus":False
        }
        atomic_write(p["candidate_meta"],json.dumps(meta).encode("utf-8"))

    def test_all_268_page_ledger_is_truthful_with_zero_source_content(self):
        r=compile_corpus(self.w,self.out)
        self.assertEqual(r["original_pages"],268)
        self.assertEqual(r["private_working_text_pages"],0)
        self.assertEqual(r["text_states"]["missing_or_invalid"],268)
        self.assertFalse(r["official_cangjie_agent_extraction_executed"])
        self.assertEqual(r["published_faceface_rules_added"],0)
        doc=(self.out/"working-corpus-OCR-UNVERIFIED.md").read_text("utf-8")
        self.assertIn("UNVERIFIED",doc)
        self.assertNotIn("## ORIGINAL SCAN PAGE",doc)

    def test_page_bound_unreviewed_candidates_and_reviewed_precedence(self):
        self.candidate("nlc-44091",27,"口須方大\n")
        self.candidate("nlc-44092",40,"或細長\n")
        self.candidate("nlc-44091",28,"不正确来源\n",correct=False)
        self.w.save_review("nlc-44091",27,"口須方大正本","actual-reviewer",True)
        r=compile_corpus(self.w,self.out)
        self.assertEqual(r["private_working_text_pages"],2)
        self.assertEqual(r["text_states"],{
            "reviewed":1,"ocr_unreviewed":1,"missing_or_invalid":266
        })
        doc=(self.out/"working-corpus-OCR-UNVERIFIED.md").read_text("utf-8")
        self.assertIn("口須方大正本",doc)
        self.assertNotIn("不正确来源",doc)
        self.assertIn("Evidence status: reviewed",doc)
        self.assertIn("Evidence status: ocr_unreviewed",doc)
        p=[x for x in r["original_page_status_ledger"]
           if x["page_id"]=="nlc-44092:p040"][0]
        self.assertTrue(p["cannot_activate_without_original_image_review"])
        review=[x for x in r["original_page_status_ledger"]
                if x["page_id"]=="nlc-44091:p027"][0]
        self.assertFalse(review["cannot_activate_without_original_image_review"])

    def test_official_Cangjie_chunker_requires_real_pinned_checkout(self):
        fake=self.root/"cangjie"
        (fake/"scripts").mkdir(parents=True)
        (fake/"SKILL.md").write_text("original pinned skill",encoding="utf-8")
        (fake/"scripts"/"build_chunks.py").write_text("# tool",encoding="utf-8")
        self.candidate("nlc-44091",27,"面有五官\n")
        compile_corpus(self.w,self.out)
        with patch("scripts.cangjie_working_corpus.subprocess.run") as run:
            run.return_value=MagicMock(stdout="definitely-wrong-commit\n")
            with self.assertRaisesRegex(ValueError,"Wrong Cangjie commit"):
                official_chunks(fake,self.out)
        with patch("scripts.cangjie_working_corpus.subprocess.run") as run:
            run.side_effect=[
                MagicMock(stdout=PINNED_CANGJIE_COMMIT+"\n"),
                MagicMock(returncode=0),
            ]
            result=official_chunks(fake,self.out)
        self.assertTrue(result["actual_upstream_build_chunks_executed"])
        self.assertFalse(result["five_semantic_agent_extractors_executed"])
        self.assertEqual(run.call_count,2)


if __name__=="__main__":
    unittest.main()
