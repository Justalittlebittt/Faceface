#!/usr/bin/env python3
"""M16.4: CPU PaddleOCR PP-OCRv5 on the SAME 1925 scan-page benchmark as M16.3.

This is an unreviewed OCR quality probe, not a Cangjie extraction or a faithful
classical transcription. It cannot produce an approved Faceface knowledge rule.

External runtime (CI only): paddlepaddle 3.2.x + paddleocr 3.3.x.
Uses existing reference_anchors / anchor_probe for apples-to-apples diagnostics.
Writes ONLY page-level metadata; source text and images remain ephemeral.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from scripts.cangjie_corpus_stage import SCANS, pdf_pages
from scripts.cangjie_ocr_benchmark import (
    SECOND_SCAN_TEST_PAGES, anchor_probe, only_han, reference_anchors
)

LABEL = "PP-OCRv5_mobile_det_server_rec_CPU_170dpi"
SETTINGS = {
    "ocr_version": "PP-OCRv5",
    "text_detection_model_name": "PP-OCRv5_mobile_det",
    "text_recognition_model_name": "PP-OCRv5_server_rec",
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
    "lang": "ch",
    "device": "cpu",
}


def extract_lines(result: object) -> tuple[list[str], list[float], list[list[int]]]:
    """Normalize the documented 3.x PaddleOCR OCRResult.json shape.

    Do not silently report zero words for a broken adapter: schema mismatches
    are actual failed experiments, not evidence of zero text on the page.
    """
    data = result.json  # upstream OCRResult property
    if not isinstance(data, dict):
        raise TypeError("PaddleOCR result.json must be a dict")
    entry = data.get("res", data)
    if not isinstance(entry, dict) or "rec_texts" not in entry:
        raise ValueError("PaddleOCR result schema missing rec_texts")
    words = entry["rec_texts"]
    scores = entry.get("rec_scores", [])
    boxes = entry.get("rec_boxes", [])
    if words is None:
        raise ValueError("PaddleOCR rec_texts must not be null")
    words = list(words)
    scores = list(scores) if scores is not None else []
    boxes = list(boxes) if boxes is not None else []
    if scores and len(scores) != len(words):
        raise ValueError("PaddleOCR rec_scores and rec_texts count mismatch")
    if boxes and len(boxes) != len(words):
        raise ValueError("PaddleOCR rec_boxes and rec_texts count mismatch")
    texts = [str(s) for s in words]
    conf = [float(s) for s in scores]
    cleaned_boxes = []
    for box in boxes:
        b = [int(v) for v in box]
        if len(b) != 4 or b[2] < b[0] or b[3] < b[1]:
            raise ValueError("PaddleOCR rec_boxes has invalid coordinates")
        cleaned_boxes.append(b)
    return texts, conf, cleaned_boxes


def column_order(texts: list[str], boxes: list[list[int]]) -> tuple[str, int]:
    """Approximate RIGHT-to-LEFT page column order, TOP-to-BOTTOM within col.

    A heuristic for diagnostics, NOT an audited restoration of classical reading
    order, since headings/illustrations and marginalia require visual review.
    """
    if not boxes or len(boxes) != len(texts):
        return "\n".join(texts), 0
    lengths = [max(1, b[2]-b[0]) for b in boxes]
    column_width = sorted(lengths)[len(lengths)//2]
    tolerance = max(12.0, column_width*0.75)
    regions = [(idx,(b[0]+b[2])/2,(b[1]+b[3])/2) for idx,b in enumerate(boxes)]
    regions.sort(key=lambda r: -r[1])
    columns: list[tuple[float,list[tuple[int,float]]]] = []
    for i,x,y in regions:
        if columns and abs(x-columns[-1][0]) <= tolerance:
            old_x, members = columns[-1]
            # running average prevents drift to adjacent far columns
            members.append((i,y))
            columns[-1] = ((old_x*(len(members)-1)+x)/len(members), members)
        else:
            columns.append((x,[(i,y)]))
    return "\n".join(texts[i] for _,col in columns
                     for i,_ in sorted(col,key=lambda item:item[1])),len(columns)


def sample_page(pdf: Path, source_id: str, index: int, ocr_engine: object,
                root: Path, anchors: list[str], dpi: int = 170) -> dict:
    filename = root / f"page-{source_id}-{index:03d}"
    subprocess.run(
        ["pdftoppm", "-f", str(index+1), "-l", str(index+1),
         "-r", str(dpi), "-gray", "-singlefile", "-png",
         str(pdf), str(filename)],
        check=True, capture_output=True, text=True
    )
    img = filename.with_suffix(".png")
    if not img.is_file() or not img.stat().st_size:
        raise RuntimeError(f"Could not render {source_id} page {index}")
    outputs = list(ocr_engine.predict(str(img)))
    if len(outputs) != 1:
        raise ValueError(f"PaddleOCR returned {len(outputs)} pages for one PNG")
    texts,scores,boxes = extract_lines(outputs[0])
    raw = "\n".join(texts)
    vertical, columns = column_order(texts,boxes)
    raw_probe = anchor_probe(raw,anchors)
    vert_probe = anchor_probe(vertical,anchors)
    return {
        "source_id": source_id,
        "page_id": f"{source_id}:p{index:03d}",
        "pdf_page_zero_based": index,
        "configuration": LABEL,
        "ocr_han_characters": len(only_han(raw)),
        "ocr_line_count": len(texts),
        "mean_recognition_score_0_to_1": (
            round(sum(scores)/len(scores),4) if scores else None
        ),
        "approx_vertical_column_count": columns,
        "source_anchor_probe_raw": raw_probe,
        "source_anchor_probe_right_to_left_columns": vert_probe,
        "reviewed_source_page": False,
        "eligible_for_cangjie_verified_corpus": False
    }


def summarize(rows: list[dict], anchor_page_count: int, source_id: str,
              source_hash: str) -> dict:
    if len({r["page_id"] for r in rows})!=len(rows):
        raise ValueError("Duplicate source-page result")
    count = sum(r["source_anchor_probe_raw"]["reference_phrase_count"] for r in rows)
    mean_scores=[r["mean_recognition_score_0_to_1"] for r in rows
                 if r["mean_recognition_score_0_to_1"] is not None]
    return {
        "status": "M16.4_UNREVIEWED_OCR_BENCHMARK_NOT_KNOWLEDGE",
        "source_id": source_id,
        "original_pdf_sha256": source_hash,
        "engine": "PaddleOCR",
        "configuration": LABEL,
        "pages_sampled": len(rows),
        "sample_pages_zero_based": [r["pdf_page_zero_based"] for r in rows],
        "anchor_reference_pages": anchor_page_count,
        "reference_anchor_count": count,
        "raw_anchor_exact_hits": sum(r["source_anchor_probe_raw"]["exact_phrase_count"] for r in rows),
        "column_order_anchor_exact_hits": sum(
            r["source_anchor_probe_right_to_left_columns"]["exact_phrase_count"] for r in rows),
        "mean_recognition_score_0_to_1": (
            round(sum(mean_scores)/len(mean_scores),4) if mean_scores else None
        ),
        "total_ocr_han_characters": sum(r["ocr_han_characters"] for r in rows),
        "page_level_results": rows,
        "needs_page_image_review": True,
        "full_page_CER_measured": False,
        "agent_cangjie_extraction_performed": False,
        "human_reviewed_full_pages": 0,
        "new_knowledge_rules_activated": 0,
        "evidence_note": (
            "Uses the same 10 source-checked pages and 20 short fragment anchors as M16.3. "
            "Second scan has three fixed pages and NO verified reference phrases. "
            "Exact substring hits and model scores are NOT character error rate. "
            "Column order is a geometric hypothesis and needs image review."
        )
    }


def benchmark(pdf: Path, source_id: str, catalog: dict, out: Path) -> dict:
    source = next((s for s in SCANS if s["id"] == source_id), None)
    if source is None:
        raise ValueError("Unknown source ID")
    if pdf_pages(pdf) != source["expected_pages"]:
        raise ValueError("Original PDF page count mismatch")
    anchors=reference_anchors(catalog,source_id)
    pages=sorted(anchors) if anchors else list(SECOND_SCAN_TEST_PAGES)
    hashval=hashlib.sha256(pdf.read_bytes()).hexdigest()
    # Import only inside benchmark: package is an optional heavy CI dependency.
    from paddleocr import PaddleOCR
    ocr=PaddleOCR(**SETTINGS)
    outputs=[]
    with tempfile.TemporaryDirectory(prefix="faceface-m16-paddle-") as tmp:
        work=Path(tmp)
        for i in pages:
            row=sample_page(pdf,source_id,i,ocr,work,anchors.get(i,[]))
            outputs.append(row)
            print(json.dumps({"processed":row["page_id"],"han_chars":row["ocr_han_characters"],
                              "anchors":row["source_anchor_probe_raw"]},ensure_ascii=False),flush=True)
    result=summarize(outputs,len(anchors),source_id,hashval)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="page_level_results"},
                     ensure_ascii=False),flush=True)
    return result


def main() -> None:
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--scan",type=Path,required=True)
    cli.add_argument("--source",required=True,choices=[s["id"] for s in SCANS])
    cli.add_argument("--catalog",type=Path,required=True)
    cli.add_argument("--out",type=Path,required=True)
    a=cli.parse_args()
    benchmark(a.scan,a.source,json.loads(a.catalog.read_text(encoding="utf-8")),a.out)


if __name__=="__main__":
    main()
