#!/usr/bin/env python3
"""M16.6: batch vision-agent DRAFTS for the two fixed 1925 《麻衣相法》 scans.

One repeatable command can plan all 268 pages, then (when the user has a local
vision model) transcribe every unreviewed page in order. NOT a Cangjie
semantic extractor, not human proofreading and never an automatic review.

Only sends the original page and matching OCR candidate to a LOOPBACK Ollama
vision endpoint. Does not send images to remote APIs or GitHub. No external
Python dependencies; local Tesseract/Paddle OCR candidates are optional.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

from scripts.cangjie_review_core import ReviewWorkspace, atomic_write, file_sha256

PROMPT_VERSION = "m16.6-source-page-vertical-columns-v1"
DRAFT_PIPELINE = "m16.6-vision-agent-draft"
DEFAULT_MODEL = "qwen3-vl:4b"
MAX_OCR_CONTEXT = 10000

# Ollama's official structured-output format: JSON Schema via /api/chat.
SCHEMA = {
    "type": "object",
    "properties": {
        "page_type": {"type": "string", "enum": [
            "text", "text_and_figures", "title_or_verse",
            "figure_only", "blank", "damaged"
        ]},
        "columns_right_to_left": {"type": "array", "items": {"type": "string"}},
        "figure_notes": {"type": "array", "items": {"type": "string"}},
        "uncertain_spans": {"type": "array", "items": {"type": "string"}},
        "printed_volume_guess": {"type": "string"},
        "section_guess": {"type": "string"},
        "reading_order_notes": {"type": "string"}
    },
    "required": [
        "page_type", "columns_right_to_left", "figure_notes", "uncertain_spans",
        "printed_volume_guess", "section_guess", "reading_order_notes"
    ],
    "additionalProperties": False
}
SYSTEM = (
    "你是古籍扫描图像转录助手，不是相术预测器。请逐像素阅读给出的1925年《麻衣相法》"
    "原版扫描页，严格从右到左的纵列、每列自上而下，依真实版面重建文字列。"
    "仅转录真正可见的原始繁体字形与标点；不得凭历史知识、OCR候选或常识补写缺字、"
    "现代改写或相貌判断。若看不清，用'□'占位并在uncertain_spans明确标出。"
    "图谱、版心标题与边注分别标明；如果是空白或纯图谱页面，columns可为空。"
    "OCR候选是未经校勘的参考线索，可与图片交叉检查但不能覆盖图片。"
    "以JSON Schema返回，columns_right_to_left按真实阅读顺序排列；"
    "卷次/篇章只能标为猜测，不能冒充已核实的印刷卷次。"
    "输出的是待审核的Agent草稿，绝不写'已人工审核'。"
)


def base_url(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost")
            or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment
            or parts.port is None or not (1 <= parts.port <= 65535)):
        raise ValueError("Vision API must be http://127.0.0.1:PORT or http://localhost:PORT")
    return f"http://{parts.hostname}:{parts.port}"


def input_fingerprint(source_sha: str, page: int, ocr_sha: str | None,
                      model: str) -> str:
    return hashlib.sha256(json.dumps(
        [DRAFT_PIPELINE, PROMPT_VERSION, source_sha, page, ocr_sha, model],
        ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def selected_pages(workspace: ReviewWorkspace, source: str = "all",
                   start: int | None = None, end: int | None = None) -> list[tuple[str, int]]:
    if source == "all":
        if start is not None or end is not None:
            raise ValueError("For a page range select one --source; all means both full PDFs")
        return [(sid, index) for sid, info in workspace.sources.items()
                for index in range(info["page_count"])]
    if source not in workspace.sources:
        raise ValueError(f"Unknown source: {source}")
    size = workspace.sources[source]["page_count"]
    first = 0 if start is None else start
    last = size-1 if end is None else end
    if not 0 <= first <= last < size:
        raise ValueError(f"Page range must be 0..{size-1}, inclusive")
    return [(source,index) for index in range(first,last+1)]


def draft_paths(draft_dir: Path, source: str, index: int) -> tuple[Path, Path]:
    base = draft_dir / source / f"{index:03d}"
    return base.with_suffix(".draft.txt"), base.with_suffix(".draft.json")


def draft_valid(workspace: ReviewWorkspace, draft_dir: Path, source: str,
                index: int, model: str) -> bool:
    info = workspace.page_info(source,index)
    txt, meta_file = draft_paths(draft_dir,source,index)
    if not (txt.is_file() and meta_file.is_file()):
        return False
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    expected = input_fingerprint(
        info["source_pdf_sha256"],index,info["ocr_diagnostic"]["text_sha256"],model
    )
    return bool(
        meta.get("pipeline")==DRAFT_PIPELINE
        and meta.get("input_fingerprint")==expected
        and meta.get("source_id")==source and meta.get("pdf_page_zero_based")==index
        and meta.get("source_pdf_sha256")==info["source_pdf_sha256"]
        and meta.get("ocr_candidate_sha256")==info["ocr_diagnostic"]["text_sha256"]
        and meta.get("draft_text_sha256")==file_sha256(txt)
        and meta.get("eligible_for_cangjie_verified_corpus") is False
        and meta.get("human_reviewed") is False
    )


def prepare_plan(workspace: ReviewWorkspace, draft_dir: Path, model: str,
                 pages: list[tuple[str,int]]) -> dict:
    jobs = []
    for source,index in pages:
        info = workspace.page_info(source,index)
        reviewed = info["is_reviewed_full_page"]
        complete = draft_valid(workspace,draft_dir,source,index,model)
        jobs.append({
            "page_id":f"{source}:p{index:03d}",
            "source_id":source,"pdf_page_zero_based":index,
            "source_pdf_sha256":info["source_pdf_sha256"],
            "matched_ocr_candidate_sha256":info["ocr_diagnostic"]["text_sha256"],
            "status":"already_human_reviewed" if reviewed else
                     "draft_reusable" if complete else "needs_agent_draft"
        })
    summary = {
        "kind":"M16.6_VISUAL_AGENT_QUEUE_NOT_TEXT_TRANSCRIPTION",
        "selected_original_scan_pages":len(jobs),
        "already_human_reviewed":sum(x["status"]=="already_human_reviewed" for x in jobs),
        "existing_valid_agent_drafts":sum(x["status"]=="draft_reusable" for x in jobs),
        "needs_agent_draft":sum(x["status"]=="needs_agent_draft" for x in jobs),
        "model":model,"pipeline":DRAFT_PIPELINE,"prompt_version":PROMPT_VERSION,
        "cangjie_agents_executed":False,
        "auto_approved_source_pages":0,
        "jobs":jobs
    }
    return summary


def parse_model_content(content: str) -> dict:
    if not isinstance(content,str) or not content.strip():
        raise ValueError("Model returned empty transcription draft")
    obj = json.loads(content)
    if not isinstance(obj,dict) or set(obj)!=set(SCHEMA["required"]):
        raise ValueError("Vision model schema mismatch")
    if obj["page_type"] not in SCHEMA["properties"]["page_type"]["enum"]:
        raise ValueError("Invalid page classification")
    for key in ("columns_right_to_left","figure_notes","uncertain_spans"):
        if not isinstance(obj[key],list) or len(obj[key])>100 or \
           any(not isinstance(s,str) or len(s)>12000 for s in obj[key]):
            raise ValueError(f"Invalid {key}")
    for key in ("printed_volume_guess","section_guess","reading_order_notes"):
        if not isinstance(obj[key],str) or len(obj[key])>1000:
            raise ValueError(f"Invalid {key}")
    text = "\n".join(s.strip() for s in obj["columns_right_to_left"] if s.strip()).strip()
    if len(text)>25000:
        raise ValueError("Vision draft is too long for full-page review")
    # Page classification is provisional, never substitutes for source review.
    if not text and obj["page_type"] not in ("figure_only","blank","damaged"):
        raise ValueError("Expected text columns or explicit figure/blank/damaged classification")
    return {**obj,"draft_text":text}


class NoRemoteRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("Local vision API redirect refused; page images never leave loopback")


class OllamaLoopback:
    def __init__(self, url: str, model: str, timeout: int = 240):
        self.url = base_url(url)
        if not isinstance(model,str) or not model or len(model)>120:
            raise ValueError("Invalid vision model name")
        self.model = model
        if not 10 <= timeout <= 900:
            raise ValueError("Timeout must be 10..900 seconds")
        self.timeout = timeout
        # Disable proxy environment for source images. Localhost only.
        self.opener = build_opener(ProxyHandler({}), NoRemoteRedirect())

    def models(self) -> set[str]:
        req = Request(self.url+"/api/tags",method="GET")
        with self.opener.open(req,timeout=20) as response:
            data=json.loads(response.read(2_000_000))
        return {m["name"] for m in data["models"]}

    def transcribe(self, png: bytes, page_id: str,
                   ocr_hint: str | None) -> tuple[dict, str]:
        # Base64 image is sent only to a user-started service on this machine.
        context = (
            f"原始PDF页面标识: {page_id}。\n"
            "图像是固定1925年古籍底本，使用严格视觉转录。"
            "原图的正确阅读顺序和旧字形优先。"
        )
        if ocr_hint:
            context += (
                "\n未校勘OCR候选（有错误、漏字和错列风险，千万不要照抄；以图为准）：\n"
                + ocr_hint[:MAX_OCR_CONTEXT]
            )
        body = {
            "model":self.model,"stream":False,"format":SCHEMA,
            "options":{"temperature":0},
            "messages":[
                {"role":"system","content":SYSTEM},
                {"role":"user","content":context,
                 "images":[base64.b64encode(png).decode("ascii")]}
            ]
        }
        req=Request(
            self.url+"/api/chat",
            json.dumps(body,ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST"
        )
        with self.opener.open(req,timeout=self.timeout) as response:
            data=json.loads(response.read(3_000_000))
        if data.get("done") is not True:
            raise ValueError("Ollama did not finish a nonstreaming response")
        text=data["message"]["content"]
        return parse_model_content(text),data.get("model","")


def run_batch(workspace: ReviewWorkspace, draft_dir: Path,
              pages: list[tuple[str,int]], engine: OllamaLoopback,
              max_pages: int | None = None, dpi: int = 200,
              overwrite: bool = False, keep_going: bool = False) -> dict:
    if max_pages is not None and max_pages<=0:
        raise ValueError("--max-pages must be positive")
    if dpi not in (120,150,200,250):
        raise ValueError("Unsupported DPI")
    installed=engine.models()
    if engine.model not in installed:
        raise ValueError(
            f"Model {engine.model} is NOT installed locally; "
            f"run: ollama pull {engine.model}"
        )
    produced, skipped_reviewed, skipped_existing, failed = 0,0,0,[]
    for source,index in pages:
        info=workspace.page_info(source,index)
        if info["is_reviewed_full_page"]:
            skipped_reviewed+=1
            continue
        if not overwrite and draft_valid(workspace,draft_dir,source,index,engine.model):
            skipped_existing+=1
            continue
        if max_pages is not None and produced>=max_pages:
            break
        page_id=f"{source}:p{index:03d}"
        try:
            image=workspace.image_path(source,index,dpi).read_bytes()
            if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Rendered page was not PNG")
            ocr=info["ocr_candidate"] if info["ocr_candidate_provenance_ok"] else None
            draft, actual_model=engine.transcribe(image,page_id,ocr)
            if actual_model and actual_model!=engine.model:
                raise ValueError("Returned model differs from selected model")
            text_content=(draft.pop("draft_text")+"\n").encode("utf-8")
            source_sha=info["source_pdf_sha256"]
            ocr_sha=info["ocr_diagnostic"]["text_sha256"]
            metadata = {
                "pipeline":DRAFT_PIPELINE,
                "prompt_version":PROMPT_VERSION,
                "source_id":source,"page_id":page_id,
                "pdf_page_zero_based":index,
                "source_pdf_sha256":source_sha,
                "ocr_candidate_sha256":ocr_sha,
                "input_fingerprint":input_fingerprint(source_sha,index,ocr_sha,engine.model),
                "model":engine.model,"created_at_utc":datetime.now(timezone.utc).isoformat(),
                "draft_text_sha256":hashlib.sha256(text_content).hexdigest(),
                **draft,
                "human_reviewed":False,
                "requires_source_image_review":True,
                "eligible_for_cangjie_verified_corpus":False
            }
            output_text,output_meta=draft_paths(draft_dir,source,index)
            atomic_write(output_text,text_content)
            atomic_write(output_meta,
                         (json.dumps(metadata,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
            produced+=1
            print(json.dumps({
                "page_id":page_id,"status":"agent_draft_saved_not_reviewed",
                "draft_characters":len(text_content),"model":engine.model
            },ensure_ascii=False),flush=True)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            failed.append({"page_id":page_id,"error":f"{type(exc).__name__}: {exc}"})
            print(json.dumps({
                "page_id":page_id,"status":"failed_no_review",
                "error":f"{type(exc).__name__}: {exc}"
            },ensure_ascii=False),flush=True)
            if not keep_going:
                break
    return {
        "kind":"M16.6_VISUAL_AGENT_DRAFT_RUN",
        "selected_source_pages":len(pages),
        "new_drafts_produced":produced,
        "already_reviewed_skipped":skipped_reviewed,
        "existing_valid_drafts_skipped":skipped_existing,
        "errors":failed,"model":engine.model,
        "pages_promoted_to_reviewed_by_agent":0,
        "cangjie_five_extractor_agents_executed":False,
        "notice":"Drafts need full-image verification. Never treat as original-reviewed book."
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--ocr-dir",type=Path,required=True)
    p.add_argument("--reviewed-dir",type=Path,required=True)
    p.add_argument("--draft-dir",type=Path,required=True)
    p.add_argument("--mode",choices=("plan","run"),default="plan")
    p.add_argument("--source",choices=("all","nlc-44091","nlc-44092"),default="all")
    p.add_argument("--start",type=int)
    p.add_argument("--end",type=int)
    p.add_argument("--model",default=DEFAULT_MODEL)
    p.add_argument("--ollama-url",default="http://127.0.0.1:11434")
    p.add_argument("--timeout",type=int,default=240)
    p.add_argument("--max-pages",type=int)
    p.add_argument("--dpi",type=int,default=200)
    p.add_argument("--overwrite-drafts",action="store_true")
    p.add_argument("--keep-going",action="store_true")
    a=p.parse_args()
    w=ReviewWorkspace(a.scan_dir,a.ocr_dir,a.reviewed_dir,draft_dir=a.draft_dir)
    pages=selected_pages(w,a.source,a.start,a.end)
    plan=prepare_plan(w,a.draft_dir,a.model,pages)
    a.draft_dir.mkdir(parents=True,exist_ok=True)
    atomic_write(
        a.draft_dir/"m16.6-queue.json",
        (json.dumps(plan,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    )
    print(json.dumps({k:v for k,v in plan.items() if k!="jobs"},ensure_ascii=False))
    if a.mode=="run":
        result=run_batch(w,a.draft_dir,pages,
                         OllamaLoopback(a.ollama_url,a.model,a.timeout),
                         a.max_pages,a.dpi,a.overwrite_drafts,a.keep_going)
        atomic_write(
            a.draft_dir/"m16.6-run-report.json",
            (json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
        )
        print(json.dumps(result,ensure_ascii=False))
        if result["errors"]:
            raise SystemExit(1)


if __name__=="__main__":
    main()
