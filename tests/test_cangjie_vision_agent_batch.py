"""M16.6: private batch queue, real localhost Ollama API protocol, provenance & UI isolation.

Synthetic PDFs/outputs are fixtures. Test success NEVER implies that a real
vision model has transcribed or source-checked the 268 original book pages.
"""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts.cangjie_review_core import ReviewWorkspace, atomic_write, file_sha256
from scripts.cangjie_vision_agent_batch import (
    DRAFT_PIPELINE, DEFAULT_MODEL, OllamaLoopback,
    base_url, draft_paths, draft_valid, input_fingerprint,
    parse_model_content, prepare_plan, run_batch, selected_pages
)


def fake_answer(text="額為衡山") -> str:
    return json.dumps({
        "page_type":"text", "columns_right_to_left":[text],
        "figure_notes":["本頁有面相圖示，須核對"],
        "uncertain_spans":["右下側一字不明"],
        "printed_volume_guess":"卷一",
        "section_guess":"五官",
        "reading_order_notes":"按右起縱列轉寫"
    },ensure_ascii=False)


class LocalMockModel(BaseHTTPRequestHandler):
    captured: list[dict] = []
    model = DEFAULT_MODEL

    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.path != "/api/tags":
            self.send_error(404)
            return
        self._write({"models":[{"name":self.model}]})

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).captured.append(body)
        self._write({
            "done":True, "model":self.model,
            "message":{"role":"assistant","content":fake_answer()}
        })

    def _write(self, obj):
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class VisionDraftTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.scans = self.root/"scans"
        self.scans.mkdir()
        (self.scans/"part1.pdf").write_bytes(b"%PDF-1.4 synthetic 153")
        (self.scans/"part2.pdf").write_bytes(b"%PDF-1.4 synthetic 115")
        self.ocr_dir = self.root/"ocr"
        self.reviewed_dir = self.root/"reviewed"
        self.draft_dir = self.root/"agent-drafts"
        hashes = {
            "nlc-44091":file_sha256(self.scans/"part1.pdf"),
            "nlc-44092":file_sha256(self.scans/"part2.pdf")
        }
        with patch("scripts.cangjie_review_core.pdf_pages",
                   side_effect=lambda path:153 if path.name=="part1.pdf" else 115):
            self.workspace = ReviewWorkspace(
                self.scans,self.ocr_dir,self.reviewed_dir,
                expected_hashes=hashes,draft_dir=self.draft_dir
            )

    def with_mock_model(self):
        LocalMockModel.captured=[]
        server=ThreadingHTTPServer(("127.0.0.1",0),LocalMockModel)
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),worker.join(3)))
        return OllamaLoopback(f"http://127.0.0.1:{server.server_port}",DEFAULT_MODEL)

    def test_full_268_queue_and_source_range(self):
        jobs=selected_pages(self.workspace)
        self.assertEqual(len(jobs),268)
        self.assertEqual(len(set(jobs)),268)
        plan=prepare_plan(self.workspace,self.draft_dir,DEFAULT_MODEL,jobs)
        self.assertEqual(plan["selected_original_scan_pages"],268)
        self.assertEqual(plan["needs_agent_draft"],268)
        self.assertEqual(plan["already_human_reviewed"],0)
        self.assertFalse(plan["cangjie_agents_executed"])
        self.assertEqual(
            selected_pages(self.workspace,"nlc-44092",39,77)[-1],
            ("nlc-44092",77)
        )
        with self.assertRaisesRegex(ValueError,"one --source"):
            selected_pages(self.workspace,"all",0,2)
        with self.assertRaisesRegex(ValueError,"range"):
            selected_pages(self.workspace,"nlc-44091",152,153)

    def test_deny_external_model_host_or_proxy(self):
        for url in (
            "https://127.0.0.1:11434","http://attacker.com:11434",
            "http://localhost.attacker.com:11434",
            "http://user@127.0.0.1:11434",
            "http://127.0.0.1:11434/path",
            "http://127.0.0.1"
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    base_url(url)
        self.assertEqual(base_url("http://localhost:11434"),"http://localhost:11434")

    def test_parse_strict_model_json_and_blank_pages(self):
        x=parse_model_content(fake_answer())
        self.assertEqual(x["draft_text"],"額為衡山")
        with self.assertRaisesRegex(ValueError,"schema"):
            parse_model_content('{"columns_right_to_left":["甲"]}')
        with self.assertRaisesRegex(ValueError,"Expected text columns"):
            parse_model_content(fake_answer("").replace('"columns_right_to_left": [""]','"columns_right_to_left": []'))
        blank=json.loads(fake_answer())
        blank["page_type"]="figure_only"
        blank["columns_right_to_left"]=[]
        self.assertEqual(parse_model_content(json.dumps(blank))["draft_text"],"")

    def test_actual_http_chat_images_schema_resume_and_unreviewed(self):
        png=self.root/"test.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-image")
        engine=self.with_mock_model()
        with patch.object(self.workspace,"image_path",return_value=png):
            r=run_batch(self.workspace,self.draft_dir,
                        [("nlc-44091",27)],engine,max_pages=1,dpi=120)
        self.assertEqual(r["new_drafts_produced"],1)
        self.assertFalse(r["cangjie_five_extractor_agents_executed"])
        self.assertEqual(r["pages_promoted_to_reviewed_by_agent"],0)
        payload=LocalMockModel.captured[0]
        self.assertEqual(payload["model"],DEFAULT_MODEL)
        self.assertEqual(payload["stream"],False)
        self.assertEqual(payload["format"]["type"],"object")
        self.assertEqual(
            base64.b64decode(payload["messages"][1]["images"][0]),
            png.read_bytes()
        )
        self.assertTrue(draft_valid(
            self.workspace,self.draft_dir,"nlc-44091",27,DEFAULT_MODEL
        ))
        self.assertFalse(
            (self.reviewed_dir/"nlc-44091"/"027.review.json").exists()
        )
        info=self.workspace.page_info("nlc-44091",27)
        self.assertTrue(info["agent_draft_provenance_ok"])
        self.assertFalse(info["is_reviewed_full_page"])
        self.assertIn("額為衡山",info["agent_draft"])
        self.assertIn("右下",info["agent_diagnostic"]["uncertain_spans"][0])
        self.assertEqual(self.workspace.summary()["agent_draft_provenance_ok"],1)
        again=run_batch(self.workspace,self.draft_dir,[("nlc-44091",27)],engine)
        self.assertEqual(again["new_drafts_produced"],0)
        self.assertEqual(again["existing_valid_drafts_skipped"],1)
        self.assertEqual(len(LocalMockModel.captured),1)

    def test_replacing_ocr_candidate_invalidates_old_agent_draft(self):
        png=self.root/"test.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\nmock")
        engine=self.with_mock_model()
        source,index="nlc-44091",28
        paths=self.workspace.page_paths(source,index)
        raw="額為衡山\n"
        paths["candidate"].parent.mkdir(parents=True,exist_ok=True)
        atomic_write(paths["candidate"],raw.encode("utf-8"))
        meta={
            "source_pdf_sha256":self.workspace.sources[source]["pdf_sha256"],
            "pdf_page_zero_based":index,
            "candidate_text_sha256":file_sha256(paths["candidate"]),
            "eligible_for_cangjie_verified_corpus":False,
        }
        atomic_write(paths["candidate_meta"],json.dumps(meta).encode())
        with patch.object(self.workspace,"image_path",return_value=png):
            report=run_batch(self.workspace,self.draft_dir,[(source,index)],engine)
        self.assertEqual(report["new_drafts_produced"],1)
        self.assertIn("額為衡山",LocalMockModel.captured[-1]["messages"][1]["content"])
        paths["candidate"].write_text("鼻為嵩山\n",encoding="utf-8")
        meta["candidate_text_sha256"]=file_sha256(paths["candidate"])
        paths["candidate_meta"].write_text(json.dumps(meta),encoding="utf-8")
        self.assertFalse(draft_valid(self.workspace,self.draft_dir,source,index,DEFAULT_MODEL))
        page=self.workspace.page_info(source,index)
        self.assertFalse(page["agent_draft_provenance_ok"])
        self.assertEqual(page["agent_draft"],"")
        self.assertTrue(prepare_plan(
            self.workspace,self.draft_dir,DEFAULT_MODEL,[(source,index)]
        )["needs_agent_draft"]==1)
        with patch.object(self.workspace,"image_path",return_value=png):
            rerun=run_batch(self.workspace,self.draft_dir,[(source,index)],engine)
        self.assertEqual(rerun["new_drafts_produced"],1)
        self.assertEqual(len(LocalMockModel.captured),2)

    def test_reviewed_page_is_skipped_never_modified_by_agent(self):
        self.workspace.save_review("nlc-44091",27,"原始校勘全文","actual-human",True)
        engine=self.with_mock_model()
        result=run_batch(self.workspace,self.draft_dir,[("nlc-44091",27)],engine)
        self.assertEqual(result["new_drafts_produced"],0)
        self.assertEqual(result["already_reviewed_skipped"],1)
        self.assertEqual(len(LocalMockModel.captured),0)
        self.assertTrue(self.workspace.page_info("nlc-44091",27)["is_reviewed_full_page"])


if __name__=="__main__":
    unittest.main()
