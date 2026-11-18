#!/usr/bin/env python3
"""M16.10: REAL original-image short-phrase probe against source-bound PP-OCRv5.

Checks short phrases PRELIMINARILY read directly from original 1925 image
screenshots against actual OCR generated again on those exact original pages.
Measures only short phrase retrieval diagnostics, NOT OCR CER, whole-page review,
the 922 M16.9 candidates' precision, or full-book Cangjie distillation.

Never uploads full PDF, OCR source text, short original quotes or images to public
CI artifacts. Source-linked *diagnostic metadata* can be uploaded; full OCR stays
in a private Runner local path.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from scripts.cangjie_corpus_stage import SCANS
from scripts.cangjie_ocr_benchmark import only_han
from scripts.cangjie_paddleocr_candidates import (
    SETTINGS, candidate_page, RENDER_DPI,
)
from scripts.cangjie_review_core import (
    ReviewWorkspace, KNOWN_SCAN_SHA256, atomic_write, file_sha256
)

SCHEMA = "faceface-m16-10-original-image-short-anchor-pilot-v1"
VALID_VISIBILITY = {"partial_photo_overlap","weak_photo_overlap","not_measured"}
ALLOWED_METRICS = {
    None,"mouth.width","eyes.openness","mouth.corner","mouth.lip",
    "face.aspect","jaw.width","eyes.spacing","nose.width","nose.length","chin.height",
}
REGIONS = {"eye","nose","mouth","ear","brow","face_structure"}


def validate_pilot(doc: dict) -> list[dict]:
    if doc.get("schema") != SCHEMA or doc.get("full_page_human_verified_count")!=0:
        raise ValueError("Unexpected source phrase pilot schema or fabricated human review")
    if doc.get("live_faceface_cards_added") != 0:
        raise ValueError("Unreviewed original phrases cannot be activated on Faceface")
    if doc.get("pdf_sha256") != KNOWN_SCAN_SHA256:
        raise ValueError("Wrong original 1925 PDF hashes")
    items = doc.get("anchors")
    if not isinstance(items,list) or not items:
        raise ValueError("Original-image short phrases are required")
    ids=set()
    for item in items:
        sid = item.get("source_id")
        source=next((x for x in SCANS if x["id"]==sid),None)
        index=item.get("pdf_page_zero_based")
        if (source is None or type(index) is not int
            or not 0 <= index < source["expected_pages"]
            or item.get("original_pdf_sha256") != KNOWN_SCAN_SHA256[sid]):
            raise ValueError("Bad original PDF provenance or page index")
        phrase=item.get("short_original_image_phrase_preliminary")
        if not isinstance(phrase,str) or not (3<=len(only_han(phrase))<=35):
            raise ValueError("Short direct-image anchor is missing or out of bounds")
        if item.get("region") not in REGIONS:
            raise ValueError("Invalid facial morphology region")
        if item.get("existing_faceface_metric") not in ALLOWED_METRICS:
            raise ValueError("Unimplemented browser face measurement was claimed")
        if item.get("current_photo_overlap") not in VALID_VISIBILITY:
            raise ValueError("Photo observability must be explicitly gated")
        if item.get("current_photo_overlap") == "not_measured" and \
           item.get("existing_faceface_metric") is not None:
            raise ValueError("Unmeasured reference must not claim an existing face metric")
        if (item.get("explicit_source_check_status")
            != "model_direct_original_image_short_phrase_visual_read_only"
            or item.get("full_page_transcription_reviewed") is not False
            or item.get("semantic_agent_approval") is not False
            or item.get("automatically_publish_rule") is not False):
            raise ValueError("AI visual pre-read cannot be promoted to reviewed source")
        name=item.get("id")
        if not isinstance(name,str) or name in ids:
            raise ValueError("Duplicate short-anchor identifier")
        ids.add(name)
    return items


def source_pages(anchors: list[dict]) -> list[tuple[str,int]]:
    return sorted(set((a["source_id"],a["pdf_page_zero_based"]) for a in anchors))


def compare_to_actual_ocr(anchors: list[dict],
                          source_text_by_page: dict[tuple[str,int],str],
                          source_text_sha_by_page: dict[tuple[str,int],str]) -> dict:
    page_ids=source_pages(anchors)
    if set(page_ids) != set(source_text_by_page) or \
       set(page_ids)!=set(source_text_sha_by_page):
        raise ValueError("Every reviewed image-page reference must have actual OCR result")
    rows=[]
    for a in anchors:
        sid,index=a["source_id"],a["pdf_page_zero_based"]
        text=source_text_by_page[(sid,index)]
        quote=only_han(a["short_original_image_phrase_preliminary"])
        normalized=only_han(text)
        exact_on_page=quote in normalized
        exact_same_OCR_line=any(quote in only_han(line) for line in text.splitlines())
        rows.append({
            "anchor_id":a["id"],
            "page_id":f"{sid}:p{index:03d}",
            "original_pdf_sha256":a["original_pdf_sha256"],
            "source_page_OCR_text_sha256":source_text_sha_by_page[(sid,index)],
            "region":a["region"],
            "photo_overlap":a["current_photo_overlap"],
            "existing_metric":a["existing_faceface_metric"],
            "exact_original_image_short_phrase_found_in_page_OCR":exact_on_page,
            "exact_original_image_short_phrase_found_within_single_OCR_line":
                exact_same_OCR_line,
            "model_visual_source_read_is_not_human_review":True,
            "source_phrase_text_not_in_metadata":True
        })
    region=Counter()
    region_totals=Counter()
    by_source=Counter()
    by_source_totals=Counter()
    for r in rows:
        region_totals[r["region"]]+=1
        by_source_totals[r["page_id"].split(":")[0]]+=1
        if r["exact_original_image_short_phrase_found_in_page_OCR"]:
            region[r["region"]]+=1
            by_source[r["page_id"].split(":")[0]]+=1
    result={
        "kind":"M16.10_REAL_ORIGINAL_SCAN_SHORT_PHRASE_RETRIEVAL_NOT_CER",
        "original_pdf_sha256":dict(KNOWN_SCAN_SHA256),
        "original_scanned_pages_tested":len(page_ids),
        "original_scan_page_ids":[f"{sid}:p{index:03d}" for sid,index in page_ids],
        "preliminarily_visual_read_short_anchors_compared":len(rows),
        "exact_original_short_phrases_retrieved_in_page_OCR":sum(
            r["exact_original_image_short_phrase_found_in_page_OCR"] for r in rows
        ),
        "exact_original_short_phrases_retrieved_in_single_OCR_line":sum(
            r["exact_original_image_short_phrase_found_within_single_OCR_line"] for r in rows
        ),
        "source_phrase_recall_by_region":{
            r:{"tested":region_totals[r],"exact_found":region[r]}
            for r in sorted(region_totals)
        },
        "source_phrase_recall_by_scan":{
            sid:{"tested":by_source_totals[sid],"exact_found":by_source[sid]}
            for sid in sorted(by_source_totals)
        },
        "short_anchor_diagnostic_rows":rows,
        "OCR_Han_character_error_rate_measured":False,
        "precision_of_all_922_M16_9_lexical_hits_measured":False,
        "full_page_original_human_transcriptions_approved":0,
        "true_original_image_source_quote_independent_human_reviewed":False,
        "actual_Cangjie_five_agent_semantic_extraction":False,
        "new_live_faceface_rules":0,
        "original_PDF_images_OR_source_text_uploaded":False,
        "notice":(
            "Exact-match counts only compare a small, AI-visually-read set of "
            "original image phrases to unreviewed PP-OCRv5 text on the same "
            "original page. Neither a full-book accuracy estimate nor proof of "
            "original text checked by an independent human reviewer."
        )
    }
    return result


def run_real_probe(scan_dir: Path, ocr_dir: Path,
                   pilot: dict, report_path: Path) -> dict:
    anchors=validate_pilot(pilot)
    pages=source_pages(anchors)
    workspace=ReviewWorkspace(
        scan_dir,ocr_dir,ocr_dir.parent/"private-original-phrase-review"
    )
    from paddleocr import PaddleOCR  # only load heavy CPU models in real jobs
    engine=PaddleOCR(**SETTINGS)
    private_work=ocr_dir/"_rendered"
    private_work.mkdir(parents=True,exist_ok=True)
    content={}
    hashes={}
    for sid,index in pages:
        source=workspace.sources[sid]
        result=candidate_page(
            source["pdf"],sid,index,source["pdf_sha256"],
            ocr_dir,engine,RENDER_DPI,private_work
        )
        if result["source_pdf_sha256"] != source["pdf_sha256"] or \
           result["pdf_page_zero_based"]!=index:
            raise RuntimeError("Original PDF source changed during sample OCR")
        paths=workspace.page_paths(sid,index)
        info=workspace.page_info(sid,index)
        if not info["ocr_candidate_provenance_ok"]:
            if result["state"]=="empty_ocr_candidate":
                content[(sid,index)]=""
                hashes[(sid,index)]=""
                continue
            raise RuntimeError("OCR candidate source integrity verification failed")
        text=info["ocr_candidate"]
        digest=file_sha256(paths["candidate"])
        if digest != result["candidate_text_sha256"]:
            raise RuntimeError("Candidate OCR hash differs from metadata")
        content[(sid,index)]=text
        hashes[(sid,index)]=digest
        print(json.dumps({
            "page_id":f"{sid}:p{index:03d}",
            "actual_original_page_OCR_executed":True,
            "candidate_han_chars":len(only_han(text))
        }),flush=True)
    report=compare_to_actual_ocr(anchors,content,hashes)
    report_path.parent.mkdir(parents=True,exist_ok=True)
    atomic_write(report_path,(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("short_anchor_diagnostic_rows","notice")},
                     ensure_ascii=False),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir",type=Path,required=True)
    parser.add_argument("--ocr-dir",type=Path,required=True)
    parser.add_argument("--source-anchors",type=Path,
                        default=Path("research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"))
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    pilot=json.loads(a.source_anchors.read_text(encoding="utf-8"))
    run_real_probe(a.scan_dir,a.ocr_dir,pilot,a.out)


if __name__=="__main__":
    main()
