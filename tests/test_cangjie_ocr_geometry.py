"""M16.27 private original OCR recognition boxes and order diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.cangjie_ocr_geometry import (
    geometry_sidecar, infer_columns, audit_saved_page, audit_pages
)
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, file_sha256
from scripts.cangjie_paddleocr_candidates import OCR_ID, ENGINE


class OriginalOCRGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.sid="nlc-44091"
        self.page=77
        self.original_pdf_sha=KNOWN_SCAN_SHA256[self.sid]
        self.lines=["鼻長有壽","耳厚有福","山根主事"]
        self.boxes=[[70,10,86,90],[120,10,136,90],[118,100,137,180]]
        self.scores=[0.92,0.83,0.75]

    def tearDown(self):
        self.temp.cleanup()

    def write_source(self, boxes=None):
        base=self.root/"transcripts"/self.sid/f"{self.page:03d}"
        text=base.with_suffix(".txt")
        atomic_write(text,("\n".join(self.lines)+"\n").encode())
        actual= self.boxes if boxes is None else boxes
        record=geometry_sidecar(self.sid,self.page,self.original_pdf_sha,
                                 file_sha256(text),self.lines,self.scores,actual)
        geom=base.with_suffix(".geometry.json")
        atomic_write(geom,(json.dumps(record,ensure_ascii=False)+"\n").encode())
        meta={
            "source_id":self.sid,"pdf_page_zero_based":self.page,
            "source_pdf_sha256":self.original_pdf_sha,
            "ocr_version":OCR_ID,"engine":ENGINE,
            "candidate_text_sha256":file_sha256(text),
            "geometry_sidecar_sha256":file_sha256(geom),
            "geometry_candidate_status":"source_unverified",
        }
        atomic_write(base.with_suffix(".ocr.json"),
                     (json.dumps(meta)+"\n").encode())
        return record,geom

    def test_retains_original_recognition_line_indices_with_boxes(self):
        g=geometry_sidecar(self.sid,self.page,self.original_pdf_sha,
                           "b"*64,["","鼻長有壽","耳厚有福"],
                           [0.1,0.95,0.85],
                           [[0,0,10,20],[10,30,20,60],[30,40,40,80]])
        self.assertEqual(g["line_count"],2)
        self.assertEqual(g["recognition_rectangles"][0]["ocr_recognition_index"],1)
        self.assertEqual(g["recognition_rectangles"][0]["ocr_text_line_index_zero_based"],0)
        self.assertFalse(g["human_verified_ancient_column_order"])

    def test_alternate_order_is_not_original_order(self):
        record,_=self.write_source()
        result=infer_columns(record)
        self.assertTrue(result["suggestion_available"])
        self.assertEqual(result["ocr_original_line_indices"],[0,1,2])
        self.assertEqual(sorted(result["suggested_line_indices"]),[0,1,2])
        self.assertNotEqual(result["suggested_line_indices"],[0,1,2])
        self.assertTrue(result["do_not_replace_model_input_order"])
        self.assertFalse(result["read_order_human_verified"])

    def test_no_boxes_does_not_invent_order(self):
        g=geometry_sidecar(self.sid,self.page,self.original_pdf_sha,
                           "b"*64,["鼻長有壽"],[],[])
        r=infer_columns(g)
        self.assertFalse(r["suggestion_available"])
        self.assertEqual(r["suggested_line_indices"],[])

    def test_wrong_box_count_or_forged_pdf_rejected(self):
        with self.assertRaises(ValueError):
            geometry_sidecar(self.sid,self.page,self.original_pdf_sha,
                             "b"*64,self.lines,self.scores,[self.boxes[0]])
        with self.assertRaises(ValueError):
            geometry_sidecar(self.sid,self.page,"0"*64,
                             "b"*64,self.lines,self.scores,self.boxes)

    def test_recognition_geometry_hash_is_bound_to_real_OCR_text(self):
        self.write_source()
        order,metadata=audit_saved_page(self.root,self.sid,self.page)
        self.assertTrue(order["suggestion_available"])
        self.assertEqual(metadata["recognition_region_count"],3)
        self.assertFalse(metadata["human_original_reading_order_verified"])
        txt=self.root/"transcripts"/self.sid/"077.txt"
        txt.write_text("bad source\n",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"changed"):
            audit_saved_page(self.root,self.sid,self.page)

    def test_modified_boxes_are_detected(self):
        _,geometry_file=self.write_source()
        geometry_file.write_text(geometry_file.read_text()+"\n",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"changed"):
            audit_saved_page(self.root,self.sid,self.page)

    def test_public_aggregate_excludes_original_source_content(self):
        self.write_source()
        private=self.root/"private"/"full-geometry.json"
        public=self.root/"metadata"/"geometry-counts.json"
        metadata=audit_pages(self.root,self.sid,[self.page],private,public)
        self.assertEqual(metadata["actual_pages_with_geometry_checked"],1)
        self.assertEqual(metadata["verified_original_page_transcriptions"],0)
        self.assertNotIn("鼻長有壽",public.read_text(encoding="utf-8"))
        self.assertTrue(private.exists())
        with self.assertRaises(ValueError):
            audit_pages(self.root,self.sid,[self.page],private,public)


if __name__=="__main__":
    unittest.main()
