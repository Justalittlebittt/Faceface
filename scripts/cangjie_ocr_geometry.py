#!/usr/bin/env python3
"""M16.27: PRIVATE PaddleOCR recognition rectangles and alternate reading order.

This produces a *geometric hypothesis*, never a corrected ancient transcription.
M16.4's geometric right-to-left sorting had worse exact-anchor recall (4 vs 5),
so original PaddleOCR text order remains canonical for cue IDs and Qwen input.
The suggested order is for image comparison ONLY.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median

from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, file_sha256, atomic_write

VERSION = "M16.27_PRIVATE_OCR_GEOMETRY_UNVERIFIED_V1"


def geometry_sidecar(source: str, page: int, pdf_sha: str, ocr_sha: str,
                     raw_lines: list[str], scores: list[float],
                     boxes: list[list[int]]) -> dict:
    if (source not in KNOWN_SCAN_SHA256 or pdf_sha != KNOWN_SCAN_SHA256[source]
        or type(page) is not int or not 0 <= page < (153 if source=="nlc-44091" else 115)
        or not isinstance(ocr_sha,str) and ocr_sha is not None):
        raise ValueError("Geometry source identity invalid")
    if scores and len(scores)!=len(raw_lines):
        raise ValueError("OCR scores not aligned to recognition outputs")
    if boxes and len(boxes)!=len(raw_lines):
        raise ValueError("OCR rectangles not aligned to recognition outputs")
    kept=[i for i,line in enumerate(raw_lines) if line.strip()]
    entries=[]
    for index,raw_index in enumerate(kept):
        box=boxes[raw_index] if boxes else None
        if box is not None:
            if (not isinstance(box,list) or len(box)!=4
                or any(type(v) is not int or v<0 for v in box)
                or box[2]<=box[0] or box[3]<=box[1]):
                raise ValueError("Invalid PaddleOCR rectangle")
        score=scores[raw_index] if scores else None
        if score is not None and not 0<=score<=1:
            raise ValueError("Invalid OCR confidence")
        entries.append({"ocr_text_line_index_zero_based":index,
                        "ocr_recognition_index":raw_index,
                        "box_xyxy_pixels":box,
                        "ocr_recognition_score":score})
    return {
        "schema":VERSION,"source_id":source,"pdf_page_zero_based":page,
        "source_pdf_sha256":pdf_sha,"ocr_candidate_text_sha256":ocr_sha,
        "line_count":len(kept),
        "coordinate_coverage_complete":bool(boxes) or not kept,
        "read_order_authoritative":False,
        "human_verified_ancient_column_order":False,
        "recognition_rectangles":entries,
    }


def infer_columns(geometry: dict) -> dict:
    """Conservative alternate box order, not a replacement for OCR sequence."""
    rows=geometry.get("recognition_rectangles")
    if not isinstance(rows,list) or geometry.get("line_count")!=len(rows):
        raise ValueError("Unaligned original image recognition boxes")
    if [r.get("ocr_text_line_index_zero_based") for r in rows]!=list(range(len(rows))):
        raise ValueError("Broken original OCR text-line index sequence")
    boxes=[r.get("box_xyxy_pixels") for r in rows]
    if not boxes or any(b is None for b in boxes):
        return {
            "suggestion_available":False,"suggested_line_indices":[],
            "ocr_original_line_indices":list(range(len(rows))),
            "approx_column_count":0,
            "flags":["missing_recognition_rectangles"],
            "read_order_human_verified":False,
        }
    widths=[b[2]-b[0] for b in boxes]
    tol=max(12.0,median(widths)*0.75)
    sorted_points=sorted(((i,(b[0]+b[2])/2,(b[1]+b[3])/2,b)
                          for i,b in enumerate(boxes)),key=lambda t:-t[1])
    columns=[]
    for i,x,y,b in sorted_points:
        if columns and abs(x-columns[-1]["x"])<=tol:
            current=columns[-1]
            current["members"].append((i,y,b))
            current["x"]=(current["x"]*(len(current["members"])-1)+x)/len(current["members"])
        else:
            columns.append({"x":x,"members":[(i,y,b)]})
    alternate=[i for col in columns for i,_,_ in
               sorted(col["members"],key=lambda t:(t[1],t[0]))]
    flags=[]
    if any((b[2]-b[0]) > 2.5*median(widths) for b in boxes):
        flags.append("very_wide_region_may_be_title_or_illustration")
    if len(columns)>len(rows)//2+1:
        flags.append("many_isolated_columns_may_indicate_horizontal_lines")
    if alternate!=list(range(len(rows))):
        flags.append("geometric_order_differs_from_original_OCR_order")
    if len(columns)==1 and len(rows)>2:
        flags.append("single_column_does_not_establish_classical_layout")
    return {
        "suggestion_available":True,
        "suggested_line_indices":alternate,
        "ocr_original_line_indices":list(range(len(rows))),
        "approx_column_count":len(columns),
        "flags":flags,
        "read_order_human_verified":False,
        "do_not_replace_model_input_order":True,
    }


def audit_saved_page(ocr_root: Path, sid: str, page: int) -> tuple[dict,dict]:
    if sid not in KNOWN_SCAN_SHA256 or type(page) is not int:
        raise ValueError("Unknown original page")
    base=ocr_root/"transcripts"/sid/f"{page:03d}"
    txt=base.with_suffix(".txt")
    meta_path=base.with_suffix(".ocr.json")
    geometry_path=base.with_suffix(".geometry.json")
    if not all(p.is_file() for p in (txt,meta_path,geometry_path)):
        raise ValueError("Missing private original OCR/rectangle evidence")
    meta=json.loads(meta_path.read_text(encoding="utf-8"))
    geometry=json.loads(geometry_path.read_text(encoding="utf-8"))
    if (geometry.get("schema")!=VERSION
        or meta.get("source_id")!=sid or geometry.get("source_id")!=sid
        or meta.get("pdf_page_zero_based")!=page
        or geometry.get("pdf_page_zero_based")!=page
        or geometry.get("source_pdf_sha256")!=KNOWN_SCAN_SHA256[sid]
        or meta.get("source_pdf_sha256")!=KNOWN_SCAN_SHA256[sid]
        or meta.get("candidate_text_sha256")!=file_sha256(txt)
        or geometry.get("ocr_candidate_text_sha256")!=file_sha256(txt)
        or meta.get("geometry_sidecar_sha256")!=file_sha256(geometry_path)
        or meta.get("geometry_candidate_status")!="source_unverified"):
        raise ValueError("Geometry source, original OCR hash, or page lineage changed")
    lines=txt.read_text(encoding="utf-8").splitlines()
    if geometry.get("line_count")!=len(lines):
        raise ValueError("Geometry count mismatches source OCR text lines")
    result=infer_columns(geometry)
    return result,{"source_id":sid,"pdf_page_zero_based":page,
                   "recognition_region_count":len(lines),
                   "geometry_available":result["suggestion_available"],
                   "approx_column_count":result["approx_column_count"],
                   "geometric_order_differs_from_OCR":(
                       result["suggestion_available"]
                       and result["suggested_line_indices"]!=result["ocr_original_line_indices"]),
                   "diagnostic_flags":result["flags"],
                   "human_original_reading_order_verified":False,
                   "new_live_Faceface_rules":0}


def audit_pages(ocr_root: Path, sid: str, pages: list[int], output_private: Path,
                output_public: Path) -> dict:
    if (output_private.resolve()==output_public.resolve() or
        output_private.exists() or output_public.exists()):
        raise ValueError("Private/public outputs must be new and distinct")
    details=[]
    reports=[]
    for page in pages:
        result,meta=audit_saved_page(ocr_root,sid,page)
        details.append({"page":page,"suggested_geometry":result})
        reports.append(meta)
    summary={
        "schema":"M16.27_ORIGINAL_OCR_UNVERIFIED_COLUMN_DIAGNOSTICS_V1",
        "source_id":sid,"actual_pages_with_geometry_checked":len(reports),
        "pages_with_complete_box_suggestions":sum(x["geometry_available"] for x in reports),
        "pages_with_different_geometric_order":sum(x["geometric_order_differs_from_OCR"] for x in reports),
        "recognition_region_count":sum(x["recognition_region_count"] for x in reports),
        "pages_by_diagnostic_flag":dict(Counter(f for r in reports for f in r["diagnostic_flags"])),
        "private_original_OCR_text_uploaded":False,
        "proposed_order_human_verified":False,"official_Cangjie_model_calls":0,
        "verified_original_page_transcriptions":0,"new_live_Faceface_rules":0,
    }
    atomic_write(output_private,(json.dumps({"details":details,"pages":reports},
                  ensure_ascii=False,indent=2)+"\n").encode())
    atomic_write(output_public,(json.dumps(summary,ensure_ascii=False,indent=2)+"\n").encode())
    print(json.dumps(summary,ensure_ascii=False))
    return summary


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-root",required=True,type=Path)
    parser.add_argument("--source",required=True,choices=list(KNOWN_SCAN_SHA256))
    parser.add_argument("--start",required=True,type=int)
    parser.add_argument("--end",required=True,type=int)
    parser.add_argument("--private-output",required=True,type=Path)
    parser.add_argument("--public-output",required=True,type=Path)
    a=parser.parse_args()
    maximum=153 if a.source=="nlc-44091" else 115
    if not 0<=a.start<=a.end<maximum:
        parser.error("Invalid original scan page interval")
    audit_pages(a.ocr_root,a.source,list(range(a.start,a.end+1)),
                a.private_output,a.public_output)


if __name__=="__main__":
    main()
