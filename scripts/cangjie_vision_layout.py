#!/usr/bin/env python3
"""M16.7: lightweight original-page layout classification with local vision AI.

This deliberately does NOT ask a small vision model to emit every ancient
Chinese character as giant JSON; real CPU Qwen3-VL full-page attempts repeatedly
produced truncated JSON in M16.7. The existing PaddleOCR/Tesseract pipeline
supplies DRAFT text. This model only helps prioritize figure/blank/damaged pages.

All images stay on localhost; annotations are NOT source-verified transcription.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request

from scripts.cangjie_review_core import ReviewWorkspace, atomic_write, file_sha256
from scripts.cangjie_vision_agent_batch import OllamaLoopback, selected_pages

LAYOUT_VERSION = "m16.7-layout-classification-v1"
LAYOUT_TYPES = ("text", "text_and_figures", "title_or_verse", "figure_only",
                "blank", "damaged", "uncertain")
SCHEMA = {
    "type":"object",
    "properties":{
        "page_type":{"type":"string","enum":list(LAYOUT_TYPES)},
        "has_illustration":{"type":"boolean"},
        "vertical_text":{"type":"boolean"},
        "column_count_estimate":{"type":"integer","minimum":0,"maximum":40},
        "needs_human_layout_check":{"type":"boolean"}
    },
    "required":["page_type","has_illustration","vertical_text",
                "column_count_estimate","needs_human_layout_check"],
    "additionalProperties":False
}
SYSTEM = (
    "请仅观察一张1925年繁体古籍扫描页的整体版式，不识别、不誊写正文，不输出解释。"
    "只返回JSON的5个字段：page_type、has_illustration、vertical_text、"
    "column_count_estimate、needs_human_layout_check。"
    "版式不确定时page_type设为uncertain且needs_human_layout_check为true。"
    "如果图谱和文字混排就设text_and_figures，不能凭图片以外信息推断。"
)
MAX_JSON_RESPONSE = 16000


def validate_layout(content: str) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Vision model layout response was empty")
    data = json.loads(content)
    if not isinstance(data, dict) or set(data) != set(SCHEMA["required"]):
        raise ValueError("Vision layout response did not match schema")
    if data["page_type"] not in LAYOUT_TYPES:
        raise ValueError("Invalid page type")
    if any(type(data[field]) is not bool for field in
           ("has_illustration","vertical_text","needs_human_layout_check")):
        raise ValueError("Boolean layout fields required")
    if (type(data["column_count_estimate"]) is not int
            or not 0 <= data["column_count_estimate"] <= 40):
        raise ValueError("Column count must be integer within 0..40")
    return data


def annotate_image(engine: OllamaLoopback, image: bytes, page_id: str) -> dict:
    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Input is not a rendered source-page PNG")
    payload = {
        "model":engine.model,
        "stream":False,
        "format":SCHEMA,
        "options":{"temperature":0,"num_predict":256},
        "messages":[
            {"role":"system","content":SYSTEM},
            {"role":"user","content":f"古籍扫描页：{page_id}。仅分析图文版式。不要转录文字。",
             "images":[base64.b64encode(image).decode("ascii")]}
        ]
    }
    request=Request(
        engine.url+"/api/chat",
        json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json"},method="POST"
    )
    with engine.opener.open(request, timeout=engine.timeout) as response:
        result=json.loads(response.read(MAX_JSON_RESPONSE))
    if result.get("done") is not True:
        raise ValueError("Vision model did not finish layout classification")
    if result.get("model") not in (None,engine.model):
        raise ValueError("Wrong vision model served the request")
    return validate_layout(result["message"]["content"])


def layout_paths(out: Path, sid: str, index: int) -> Path:
    return out/sid/f"{index:03d}.layout.json"


def valid_previous(workspace: ReviewWorkspace, out: Path, sid: str,
                   index: int, model: str) -> bool:
    target=layout_paths(out,sid,index)
    if not target.is_file():
        return False
    meta=json.loads(target.read_text(encoding="utf-8"))
    page=workspace.page_info(sid,index)
    return bool(
        meta.get("pipeline")==LAYOUT_VERSION
        and meta.get("source_id")==sid
        and meta.get("pdf_page_zero_based")==index
        and meta.get("source_pdf_sha256")==page["source_pdf_sha256"]
        and meta.get("model")==model
        and meta.get("human_reviewed") is False
        and meta.get("eligible_for_cangjie_verified_corpus") is False
        and isinstance(meta.get("layout"),dict)
        and validate_layout(json.dumps(meta["layout"]))==meta["layout"]
    )


def classify_batch(workspace: ReviewWorkspace, engine: OllamaLoopback,
                   pages: list[tuple[str,int]], out: Path,
                   dpi: int = 120, keep_going: bool = False) -> dict:
    if dpi not in (120,150,200,250):
        raise ValueError("Unsupported render resolution")
    if engine.model not in engine.models():
        raise ValueError("The requested actual vision model is not installed in local Ollama")
    results=[]
    skipped=0
    errors=[]
    for sid,index in pages:
        page_id=f"{sid}:p{index:03d}"
        if valid_previous(workspace,out,sid,index,engine.model):
            skipped+=1
            continue
        try:
            image=workspace.image_path(sid,index,dpi).read_bytes()
            layout=annotate_image(engine,image,page_id)
            entry={
                "pipeline":LAYOUT_VERSION,
                "model":engine.model,
                "source_id":sid,
                "page_id":page_id,
                "pdf_page_zero_based":index,
                "source_pdf_sha256":workspace.sources[sid]["pdf_sha256"],
                "original_rendered_page_sha256":hashlib.sha256(image).hexdigest(),
                "layout":layout,
                "created_at_utc":datetime.now(timezone.utc).isoformat(),
                "human_reviewed":False,
                "eligible_for_cangjie_verified_corpus":False,
                "source_truth_claim":False,
                "note":"AI layout suggestion only; not OCR text, not book proofreading."
            }
            target=layout_paths(out,sid,index)
            atomic_write(target,(json.dumps(entry,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
            results.append(entry)
            print(json.dumps({"page_id":page_id,"real_vision_layout_created":True,
                              "page_type":layout["page_type"]},ensure_ascii=False),flush=True)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            errors.append({"page_id":page_id,"error":f"{type(exc).__name__}: {exc}"})
            print(json.dumps({"page_id":page_id,"real_vision_layout_created":False,
                              "error":f"{type(exc).__name__}: {exc}"},ensure_ascii=False),flush=True)
            if not keep_going:
                break
    return {
        "kind":"M16.7_ACTUAL_VISION_LAYOUT_NOT_TEXT_TRANSCRIPTION",
        "attempted_original_pages":len(pages),
        "new_real_model_layout_annotations":len(results),
        "skipped_existing_source_bound_annotations":skipped,
        "errors":errors,
        "model":engine.model,
        "page_types":{"text":sum(x["layout"]["page_type"]=="text" for x in results),
                      "text_and_figures":sum(x["layout"]["page_type"]=="text_and_figures" for x in results),
                      "other":sum(x["layout"]["page_type"] not in ("text","text_and_figures") for x in results)},
        "pages_promoted_to_reviewed":0,
        "book_transcription_performed_by_this_command":False,
        "cangjie_agent_extraction_performed":False
    }


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir",type=Path,required=True)
    parser.add_argument("--ocr-dir",type=Path,required=True)
    parser.add_argument("--reviewed-dir",type=Path,required=True)
    parser.add_argument("--draft-dir",type=Path,required=True)
    parser.add_argument("--layout-dir",type=Path,required=True)
    parser.add_argument("--source",default="all",
                        choices=("all","nlc-44091","nlc-44092"))
    parser.add_argument("--start",type=int)
    parser.add_argument("--end",type=int)
    parser.add_argument("--model",default="qwen3-vl:2b-instruct")
    parser.add_argument("--ollama-url",default="http://127.0.0.1:11434")
    parser.add_argument("--timeout",type=int,default=240)
    parser.add_argument("--dpi",type=int,default=120)
    parser.add_argument("--keep-going",action="store_true")
    a=parser.parse_args()
    workspace=ReviewWorkspace(a.scan_dir,a.ocr_dir,a.reviewed_dir,draft_dir=a.draft_dir)
    pages=selected_pages(workspace,a.source,a.start,a.end)
    result=classify_batch(workspace,OllamaLoopback(a.ollama_url,a.model,a.timeout),
                          pages,a.layout_dir,a.dpi,a.keep_going)
    a.layout_dir.mkdir(parents=True,exist_ok=True)
    report=a.layout_dir/"m16-7-layout-run-report.json"
    atomic_write(report,(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps(result,ensure_ascii=False))
    if result["errors"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
