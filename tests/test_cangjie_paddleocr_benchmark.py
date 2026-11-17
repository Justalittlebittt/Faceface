"""M16.4: verify PP-OCRv5 adapter, scan page order, and evidence isolation.

No model is downloaded during tests; integration workflow exercises real PaddleOCR.
"""
import unittest
from types import SimpleNamespace

from scripts.cangjie_paddleocr_benchmark import (
    LABEL, SETTINGS, column_order, extract_lines, summarize
)


class PaddleOcrBenchmarkTests(unittest.TestCase):
    def test_uses_specific_cpu_ppocrv5_models_not_unpinned_default(self):
        self.assertEqual(SETTINGS["device"],"cpu")
        self.assertEqual(SETTINGS["ocr_version"],"PP-OCRv5")
        self.assertEqual(SETTINGS["text_recognition_model_name"],"PP-OCRv5_server_rec")

    def test_extract_upstream_res_schema(self):
        mock=SimpleNamespace(json={"res":{
            "rec_texts":["相法","面圓光澤"],
            "rec_scores":[.91,.85],
            "rec_boxes":[[90,10,100,60],[40,10,50,90]]
        }})
        text,conf,boxes=extract_lines(mock)
        self.assertEqual(text,["相法","面圓光澤"])
        self.assertEqual(conf,[.91,.85])
        self.assertEqual(len(boxes),2)
        with self.assertRaisesRegex(ValueError,"rec_texts"):
            extract_lines(SimpleNamespace(json={"res":{}}))

    def test_read_columns_right_to_left_with_vertical_y_order(self):
        texts=["左下","右下","右上","左上"]
        boxes=[[20,80,32,100],[130,75,143,90],
               [130,10,143,32],[20,10,32,30]]
        reading,n=column_order(texts,boxes)
        self.assertEqual(n,2)
        self.assertEqual(reading.splitlines(),["右上","右下","左上","左下"])

    def test_geometry_missing_is_not_faked(self):
        reading,n=column_order(["test","second"],[])
        self.assertEqual(n,0)
        self.assertEqual(reading,"test\nsecond")

    def test_summary_never_promotes_ocr_or_invents_CER(self):
        rows=[
            {"source_id":"nlc-44091","page_id":"nlc-44091:p027",
             "pdf_page_zero_based":27,"ocr_han_characters":16,
             "mean_recognition_score_0_to_1":.5,
             "source_anchor_probe_raw":{"reference_phrase_count":2,"exact_phrase_count":1},
             "source_anchor_probe_right_to_left_columns":{"exact_phrase_count":1}},
            {"source_id":"nlc-44091","page_id":"nlc-44091:p035",
             "pdf_page_zero_based":35,"ocr_han_characters":19,
             "mean_recognition_score_0_to_1":.75,
             "source_anchor_probe_raw":{"reference_phrase_count":1,"exact_phrase_count":0},
             "source_anchor_probe_right_to_left_columns":{"exact_phrase_count":0}}
        ]
        report=summarize(rows,2,"nlc-44091","mock-hash")
        self.assertEqual(report["configuration"],LABEL)
        self.assertEqual(report["reference_anchor_count"],3)
        self.assertEqual(report["raw_anchor_exact_hits"],1)
        self.assertFalse(report["full_page_CER_measured"])
        self.assertTrue(report["needs_page_image_review"])
        self.assertEqual(report["human_reviewed_full_pages"],0)
        self.assertFalse(report["agent_cangjie_extraction_performed"])
        rows[1]["page_id"]=rows[0]["page_id"]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            summarize(rows,2,"nlc-44091","mock-hash")


if __name__=="__main__":
    unittest.main()
