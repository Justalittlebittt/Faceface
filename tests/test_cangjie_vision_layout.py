"""M16.7 real vision-layout pathway contracts, never source transcription or review."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from scripts.cangjie_review_core import ReviewWorkspace, file_sha256
from scripts.cangjie_vision_agent_batch import OllamaLoopback
from scripts.cangjie_vision_layout import (
    LAYOUT_VERSION, annotate_image, classify_batch, layout_paths,
    valid_previous, validate_layout
)


def layout_payload():
    return {
        "page_type":"text_and_figures",
        "has_illustration":True,
        "vertical_text":True,
        "column_count_estimate":9,
        "needs_human_layout_check":True,
    }


class RealHttpMockLayout(BaseHTTPRequestHandler):
    captured=[]
    def log_message(self,*args):
        pass

    def _json(self,obj):
        body=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path=="/api/tags":
            self._json({"models":[{"name":"qwen3-vl:2b-instruct"}]})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path!="/api/chat":
            self.send_error(404)
            return
        payload=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).captured.append(payload)
        self._json({"done":True,"model":"qwen3-vl:2b-instruct",
                    "message":{"content":json.dumps(layout_payload())}})


class LayoutTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.scan=self.root/"scans"
        self.scan.mkdir()
        (self.scan/"part1.pdf").write_bytes(b"%PDF-synthetic-A")
        (self.scan/"part2.pdf").write_bytes(b"%PDF-synthetic-B")
        hashes={
            "nlc-44091":file_sha256(self.scan/"part1.pdf"),
            "nlc-44092":file_sha256(self.scan/"part2.pdf")
        }
        with patch("scripts.cangjie_review_core.pdf_pages",
                   side_effect=lambda p:153 if p.name=="part1.pdf" else 115):
            self.workspace=ReviewWorkspace(
                self.scan,self.root/"ocr",self.root/"reviewed",
                expected_hashes=hashes,draft_dir=self.root/"drafts"
            )
        self.output=self.root/"layout"
        self.model="qwen3-vl:2b-instruct"
        png=self.root/"img.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n"+"image-data".encode())
        self.png=png

    def server(self):
        RealHttpMockLayout.captured=[]
        server=ThreadingHTTPServer(("127.0.0.1",0),RealHttpMockLayout)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join(3)))
        return OllamaLoopback(f"http://127.0.0.1:{server.server_port}",
                              self.model,timeout=60)

    def test_schema_is_short_and_explicitly_disallows_transcriptions(self):
        self.assertEqual(validate_layout(json.dumps(layout_payload())),
                         layout_payload())
        with self.assertRaisesRegex(ValueError,"schema"):
            validate_layout('{"page_type":"text"}')
        x=layout_payload()
        x["vertical_text"]=1
        with self.assertRaisesRegex(ValueError,"Boolean"):
            validate_layout(json.dumps(x))
        x=layout_payload()
        x["column_count_estimate"]=41
        with self.assertRaisesRegex(ValueError,"Column count"):
            validate_layout(json.dumps(x))

    def test_actual_local_http_request_is_image_and_only_short_classification(self):
        engine=self.server()
        layout=annotate_image(engine,self.png.read_bytes(),"nlc-44091:p027")
        self.assertEqual(layout["page_type"],"text_and_figures")
        payload=RealHttpMockLayout.captured[0]
        self.assertEqual(payload["options"]["num_predict"],256)
        self.assertEqual(payload["model"],self.model)
        self.assertEqual(payload["format"]["required"],
                         list(layout_payload().keys()))
        self.assertEqual(base64.b64decode(payload["messages"][1]["images"][0]),
                         self.png.read_bytes())
        self.assertNotIn("columns_right_to_left",payload["format"]["properties"])

    def test_batch_writes_unreviewed_metadata_and_resumes(self):
        engine=self.server()
        pages=[("nlc-44091",27),("nlc-44092",40)]
        with patch.object(self.workspace,"image_path",return_value=self.png):
            r=classify_batch(self.workspace,engine,pages,self.output,dpi=120)
        self.assertEqual(r["new_real_model_layout_annotations"],2)
        self.assertFalse(r["book_transcription_performed_by_this_command"])
        self.assertEqual(r["pages_promoted_to_reviewed"],0)
        self.assertEqual(self.workspace.summary()["full_page_reviewed"],0)
        self.assertEqual(len(RealHttpMockLayout.captured),2)
        self.assertTrue(valid_previous(self.workspace,self.output,
                                       "nlc-44091",27,self.model))
        entry=json.loads(layout_paths(self.output,"nlc-44091",27).read_text("utf-8"))
        self.assertFalse(entry["eligible_for_cangjie_verified_corpus"])
        self.assertFalse(entry["human_reviewed"])
        self.assertEqual(entry["source_pdf_sha256"],
                         self.workspace.sources["nlc-44091"]["pdf_sha256"])
        with patch.object(self.workspace,"image_path",return_value=self.png):
            r2=classify_batch(self.workspace,engine,pages,self.output,dpi=120)
        self.assertEqual(r2["new_real_model_layout_annotations"],0)
        self.assertEqual(r2["skipped_existing_source_bound_annotations"],2)
        self.assertEqual(len(RealHttpMockLayout.captured),2)

    def test_source_mismatched_layout_cannot_be_reused(self):
        engine=self.server()
        with patch.object(self.workspace,"image_path",return_value=self.png):
            classify_batch(self.workspace,engine,[("nlc-44091",35)],self.output)
        meta=layout_paths(self.output,"nlc-44091",35)
        data=json.loads(meta.read_text("utf-8"))
        data["source_pdf_sha256"]="tampered"
        meta.write_text(json.dumps(data),encoding="utf-8")
        self.assertFalse(valid_previous(self.workspace,self.output,
                                        "nlc-44091",35,self.model))
        with patch.object(self.workspace,"image_path",return_value=self.png):
            r=classify_batch(self.workspace,engine,[("nlc-44091",35)],self.output)
        self.assertEqual(r["new_real_model_layout_annotations"],1)
        self.assertEqual(len(RealHttpMockLayout.captured),2)


if __name__=="__main__":
    unittest.main()
