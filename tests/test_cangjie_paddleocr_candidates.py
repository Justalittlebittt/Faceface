"""M16.7 real PP-OCRv5 whole-book candidate pipeline regression tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import cangjie_paddleocr_candidates as ocr
from scripts.cangjie_corpus_stage import verify_page_review


class FakePaddle:
    def __init__(self,lines):
        self.lines=lines
        self.calls=0

    def predict(self,image):
        self.calls+=1
        return [SimpleNamespace(json={"res":{
            "rec_texts":self.lines,
            "rec_scores":[.95 for x in self.lines],
            "rec_boxes": []
        }})]


class PaddleWholeBookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.scans=self.root/"scans"
        self.scans.mkdir()
        self.pdf=self.scans/"part1.pdf"
        self.pdf.write_bytes(b"%PDF-synthetic-original-A")
        self.hash=hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.out=self.root/"out"

    def render(self,pdf,page,stem,dpi):
        path=stem.with_suffix(".png")
        path.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
        return path

    def test_two_real_codepath_candidates_are_unreviewed_with_source_hash(self):
        engine=FakePaddle(["口須方大","眼或細長"])
        with patch.object(ocr,"pdf_pages",return_value=153), \
             patch.object(ocr,"render_page",side_effect=self.render), \
             patch("scripts.cangjie_ocr_geometry.KNOWN_SCAN_SHA256",{"nlc-44091":self.hash}):
            report=ocr.batch(self.scans,self.out,"nlc-44091",27,28,
                             engine=engine,expected_hash=self.hash)
        self.assertEqual(report["processed_pages"],2)
        self.assertEqual(report["pages_with_candidate_text"],2)
        self.assertEqual(engine.calls,2)
        self.assertEqual(report["human_reviewed_pages_from_this_run"],0)
        self.assertFalse(report["cangjie_agent_extraction_performed"])
        page=self.out/"transcripts"/"nlc-44091"/"027.txt"
        self.assertEqual(page.read_text(encoding="utf-8"),"口須方大\n眼或細長\n")
        meta=json.loads(page.with_suffix(".ocr.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["source_pdf_sha256"],self.hash)
        self.assertEqual(meta["pdf_page_zero_based"],27)
        self.assertEqual(meta["candidate_text_sha256"],ocr.digest(page))
        self.assertEqual(meta["mean_recognition_score_0_to_1"],.95)
        self.assertIsNone(meta["mean_word_confidence"])
        self.assertFalse(meta["eligible_for_cangjie_verified_corpus"])
        self.assertEqual(meta["geometry_candidate_status"],"source_unverified")
        geometry=page.with_suffix(".geometry.json")
        self.assertTrue(geometry.is_file())
        self.assertEqual(meta["geometry_sidecar_sha256"],ocr.digest(geometry))
        self.assertFalse(json.loads(geometry.read_text())["read_order_authoritative"])
        self.assertFalse(verify_page_review(page,self.hash,27))

    def test_empty_ocr_does_not_leave_stale_candidate(self):
        engine=FakePaddle(["二字"])
        with patch.object(ocr,"render_page",side_effect=self.render), \
             patch("scripts.cangjie_ocr_geometry.KNOWN_SCAN_SHA256",{"nlc-44091":self.hash}):
            first=ocr.candidate_page(self.pdf,"nlc-44091",27,self.hash,
                                     self.out,engine,170,self.root)
        self.assertEqual(first["state"],"ocr_candidate")
        engine.lines=[]
        with patch.object(ocr,"render_page",side_effect=self.render), \
             patch("scripts.cangjie_ocr_geometry.KNOWN_SCAN_SHA256",{"nlc-44091":self.hash}):
            second=ocr.candidate_page(self.pdf,"nlc-44091",27,self.hash,
                                      self.out,engine,170,self.root)
        self.assertEqual(second["state"],"empty_ocr_candidate")
        self.assertIsNone(second["candidate_text_sha256"])
        self.assertFalse((self.out/"transcripts"/"nlc-44091"/"027.txt").exists())

    def test_other_pdf_hash_rejected_and_invalid_range(self):
        engine=FakePaddle(["含字"])
        with patch.object(ocr,"pdf_pages",return_value=153):
            with self.assertRaisesRegex(ValueError,"sha256"):
                ocr.batch(self.scans,self.out,"nlc-44091",0,1,
                          engine=engine,expected_hash="bad")
            with self.assertRaisesRegex(ValueError,"range"):
                ocr.batch(self.scans,self.out,"nlc-44091",152,153,
                          engine=engine,expected_hash=self.hash)
        self.assertEqual(engine.calls,0)


if __name__=="__main__":
    unittest.main()
