#!/usr/bin/env python3
"""M16.7: batch REAL PP-OCRv5 candidate text for the 1925 whole book.

This is the practical text engine after Qwen3-VL 2B full-page JSON failed
in 3 of 4 real original-image tests. The model is installed once per shard.
EVERY output is source-bound, unreviewed and isolated from the Faceface site.

Example (run once per scanned fascicle, private output directory):
  python -m scripts.cangjie_paddleocr_candidates --scan-dir scans --out-dir private-paddle \
      --source nlc-44091
  python -m scripts.cangjie_paddleocr_candidates --scan-dir scans --out-dir private-paddle \
      --source nlc-44092
Requires Poppler and the pinned Python dependencies from M16.4.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from scripts.cangjie_corpus_stage import SCANS, pdf_pages
from scripts.cangjie_ocr_candidates import digest
from scripts.cangjie_ocr_benchmark import only_han
from scripts.cangjie_paddleocr_benchmark import SETTINGS, extract_lines
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write

OCR_ID = "m16.7-paddleocr-v5-cpu-original-scan"
ENGINE = "PaddleOCR_PP-OCRv5_mobile_det_server_rec"
RENDER_DPI = 170


def render_page(pdf: Path, index: int, image_stem: Path, dpi: int) -> Path:
    result = subprocess.run(
        ["pdftoppm", "-f", str(index+1), "-l", str(index+1), "-r", str(dpi),
         "-gray", "-singlefile", "-png", str(pdf), str(image_stem)],
        capture_output=True, text=True, timeout=75
    )
    path = image_stem.with_suffix(".png")
    if result.returncode or not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"Unable to render PDF page {index} from {pdf.name}")
    return path


def candidate_page(pdf: Path, source_id: str, index: int, pdf_sha: str,
                   target: Path, engine: object, dpi: int,
                   work_dir: Path) -> dict:
    image = render_page(pdf,index,work_dir/"page",dpi)
    results=list(engine.predict(str(image)))
    if len(results)!=1:
        raise ValueError(f"Expected one OCRResult for {source_id} page {index}")
    lines,scores,boxes=extract_lines(results[0])
    # Use OCR engine output order. A hand-written right-to-left geometric
    # reorder matched FEWER verified original phrases in M16.4 (4 vs 5).
    # Do not auto-reorder columns or invent text for figures.
    text = "\n".join(x.strip() for x in lines if x.strip()).strip()
    base = target/"transcripts"/source_id/f"{index:03d}"
    txt = base.with_suffix(".txt")
    meta = base.with_suffix(".ocr.json")
    if text:
        atomic_write(txt,(text+"\n").encode("utf-8"))
    else:
        txt.unlink(missing_ok=True)
    conf=round(sum(scores)/len(scores),4) if scores else None
    record={
        "source_id":source_id,
        "page_id":f"{source_id}:p{index:03d}",
        "pdf_page_zero_based":index,
        "source_pdf_sha256":pdf_sha,
        "ocr_version":OCR_ID,
        "engine":ENGINE,
        "render_dpi":dpi,
        "state":"ocr_candidate" if text else "empty_ocr_candidate",
        "candidate_text_sha256":digest(txt) if text else None,
        "han_char_count":len(only_han(text)),
        "ocr_line_count":len(lines),
        "mean_recognition_score_0_to_1":conf,
        "mean_word_confidence":None,
        "requires_manual_page_review":True,
        "eligible_for_cangjie_verified_corpus":False,
        "provenance_note":"OCR CANDIDATE ONLY; original scan must be image-reviewed before source confirmation."
    }
    atomic_write(meta,(json.dumps(record,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    image.unlink(missing_ok=True)
    return record


def batch(scan_dir: Path, out_dir: Path, source_id: str,
          start: int = 0, end: int | None = None, dpi: int = RENDER_DPI,
          engine: object | None = None, expected_hash: str | None = None) -> dict:
    source=next((s for s in SCANS if s["id"]==source_id),None)
    if source is None:
        raise ValueError("Unknown original scan ID")
    if dpi not in (120,150,170,200,220):
        raise ValueError("Allowed DPI values are 120,150,170,200,220")
    pdf=scan_dir/source["file"]
    count=pdf_pages(pdf)
    if count!=source["expected_pages"]:
        raise ValueError(f"Original PDF page count changed: {source_id}")
    if end is None:
        end=count-1
    if not 0<=start<=end<count:
        raise ValueError(f"Invalid source page range {start}..{end}")
    sha=digest(pdf)
    if sha!=(expected_hash or KNOWN_SCAN_SHA256[source_id]):
        raise ValueError(f"Wrong original PDF sha256 for {source_id}")
    if engine is None:
        from paddleocr import PaddleOCR
        engine=PaddleOCR(**SETTINGS)
    pages=[]
    with tempfile.TemporaryDirectory(prefix="m16-7-ppocr-") as tmp:
        work=Path(tmp)
        for index in range(start,end+1):
            page=candidate_page(pdf,source_id,index,sha,out_dir,engine,dpi,work)
            pages.append(page)
            # Printed page identifiers and counts ONLY, no unreviewed original text.
            print(json.dumps({
                "page_id":page["page_id"],
                "state":page["state"],
                "han_char_count":page["han_char_count"]
            },ensure_ascii=False),flush=True)
    summary={
        "source_id":source_id,
        "source_pdf_sha256":sha,
        "total_pdf_pages":count,
        "first_pdf_page_zero_based":start,
        "last_pdf_page_zero_based":end,
        "expected_processed_pages":end-start+1,
        "processed_pages":len(pages),
        "pages_with_candidate_text":sum(x["state"]=="ocr_candidate" for x in pages),
        "pages_without_candidate_text":sum(x["state"]=="empty_ocr_candidate" for x in pages),
        "candidate_han_character_count":sum(x["han_char_count"] for x in pages),
        "candidate_characters_are_unreviewed":True,
        "model":ENGINE,
        "human_reviewed_pages_from_this_run":0,
        "cangjie_agent_extraction_performed":False,
        "cangjie_active_rules_created":0,
        "pages":pages
    }
    report=out_dir/"reports"/f"{source_id}-p{start:03d}-{end:03d}.json"
    atomic_write(report,(json.dumps(summary,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:v for k,v in summary.items() if k!="pages"},ensure_ascii=False))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--source",choices=[x["id"] for x in SCANS],required=True)
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--end",type=int)
    p.add_argument("--dpi",type=int,default=RENDER_DPI)
    a=p.parse_args()
    batch(a.scan_dir,a.out_dir,a.source,a.start,a.end,a.dpi)


if __name__=="__main__":
    main()
