#!/usr/bin/env python3
"""M16.11 held-out original-scan PP-OCRv5 170 vs 220 DPI comparison.

A TRUE independent development/holdout split:
 Development: 13 AI-visually-read M16.10 phrases on 6 source pages.
 Holdout: 12 PRE-EXISTING V5 original-source-checked short fragments on
          seven DIFFERENT first-PDF pages 28/34/35/52/66/77/89.

Do not use the holdout to tune further image transformations. Match only
within ONE OCR line to prevent fake matches by concatenating unrelated regions.
This is short-phrase retrieval, not full-page CER or a historical source review.
Original book text remains local/private; CI uploads only metadata and hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.cangjie_original_phrase_probe import source_pages,validate_pilot
from scripts.cangjie_ocr_benchmark import reference_anchors, only_han
from scripts.cangjie_paddleocr_benchmark import SETTINGS, extract_lines
from scripts.cangjie_paddleocr_candidates import render_page
from scripts.cangjie_review_core import ReviewWorkspace, atomic_write

SOURCE="nlc-44091"
EXPECTED_HOLDOUT_PAGES=(28,34,35,52,66,77,89)
EXPECTED_HOLDOUT_ANCHORS=12
VARIANTS=(("baseline_original_170",170),("enhanced_full_original_220",220))


def holdout_pages(catalog:dict, preliminary_dev_pilot:dict)->dict[int,list[str]]:
    anchors=reference_anchors(catalog,SOURCE)
    dev=set(source_pages(validate_pilot(preliminary_dev_pilot)))
    held={page:phrases for page,phrases in anchors.items()
          if (SOURCE,page) not in dev}
    if tuple(sorted(held))!=EXPECTED_HOLDOUT_PAGES:
        raise ValueError("Independent holdout page set changed or leaked development pages")
    if sum(map(len,held.values()))!=EXPECTED_HOLDOUT_ANCHORS:
        raise ValueError("Independent V5 original-reference anchor set changed")
    if any(len(phrase)<2 or not only_han(phrase)==phrase
           for phrases in held.values() for phrase in phrases):
        raise ValueError("Unexpected historical phrase reference format")
    return held


def score_one(text:str, anchors:list[str], source_page_id:str,source_sha:str,
              variant:str)->dict:
    lines=[only_han(line) for line in text.splitlines()]
    whole=only_han(text)
    scored=[]
    for phrase in anchors:
        key=hashlib.sha256((source_page_id+"|"+phrase).encode("utf-8")).hexdigest()[:18]
        scored.append({
            "source_phrase_id_hash":key,
            "exact_same_OCR_line":any(phrase in line for line in lines),
            "exact_whole_OCR_page":phrase in whole,
        })
    return {
        "page_id":source_page_id,
        "original_pdf_sha256":source_sha,
        "variant":variant,
        "PaddleOCR_source_text_SHA256":hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "short_reference_anchors":[x["source_phrase_id_hash"] for x in scored],
        "per_source_phrase_boolean_retrieval":scored,
        "exact_single_line_hits":sum(x["exact_same_OCR_line"] for x in scored),
        "exact_whole_page_hits":sum(x["exact_whole_OCR_page"] for x in scored),
        "full_page_human_reviewed":False,
        "auto_activated_Faceface_rules":0,
    }


def summarize(rows:dict[str,list[dict]],holdout:dict[int,list[str]])->dict:
    expected={f"{SOURCE}:p{i:03d}" for i in holdout}
    if set(rows)!=set(v for v,_ in VARIANTS):
        raise ValueError("Missing fixed 170 vs 220 source benchmark")
    for name,group in rows.items():
        ids=[r["page_id"] for r in group]
        if len(ids)!=len(expected) or set(ids)!=expected:
            raise ValueError("Missing/duplicated held-out source page")
        if any(r["variant"]!=name or r["full_page_human_reviewed"] is not False
               or r["auto_activated_Faceface_rules"]!=0 for r in group):
            raise ValueError("False review/promotion or wrong tested variant")
    out={name:{"original_pages":len(group),
               "source_checked_short_anchors":sum(
                    len(r["per_source_phrase_boolean_retrieval"]) for r in group),
               "exact_single_OCR_line_hits":sum(r["exact_single_line_hits"] for r in group),
               "exact_whole_page_hits":sum(r["exact_whole_page_hits"] for r in group)}
         for name,group in rows.items()}
    if any(o["source_checked_short_anchors"]!=EXPECTED_HOLDOUT_ANCHORS for o in out.values()):
        raise ValueError("Holdout reference snippets not fully compared")
    per_anchor=[]
    for page in sorted(expected):
        a=next(r for r in rows[VARIANTS[0][0]] if r["page_id"]==page)
        b=next(r for r in rows[VARIANTS[1][0]] if r["page_id"]==page)
        one={x["source_phrase_id_hash"]:x for x in a["per_source_phrase_boolean_retrieval"]}
        two={x["source_phrase_id_hash"]:x for x in b["per_source_phrase_boolean_retrieval"]}
        if set(one)!=set(two):
            raise ValueError("Reference IDs differ across original image DPI settings")
        for key in one:
            per_anchor.append({
                "page_id":page,
                "original_reference_hash":key,
                "original_170_exact_in_one_OCR_line":one[key]["exact_same_OCR_line"],
                "enhanced_220_exact_in_one_OCR_line":two[key]["exact_same_OCR_line"],
                "newly_recovered_by_220":not one[key]["exact_same_OCR_line"]
                                       and two[key]["exact_same_OCR_line"],
                "regressed_when_using_220":one[key]["exact_same_OCR_line"]
                                           and not two[key]["exact_same_OCR_line"],
            })
    base=out[VARIANTS[0][0]]["exact_single_OCR_line_hits"]
    higher=out[VARIANTS[1][0]]["exact_single_OCR_line_hits"]
    return {
        "kind":"M16.11_HELDOUT_REAL_1925_SOURCE_OCR_SHORT_PHRASE_RETRIEVAL",
        "old_13_phrase_development_set_not_used_to_select_or_modify_this_holdout":True,
        "reference_source":"existing source-checked v5 data, not new M16.10 AI visual reads",
        "source_ID":SOURCE,
        "original_pdf_sha256":rows[VARIANTS[0][0]][0]["original_pdf_sha256"],
        "heldout_original_pdf_page_zero_based":list(EXPECTED_HOLDOUT_PAGES),
        "heldout_original_pages_tested":len(EXPECTED_HOLDOUT_PAGES),
        "heldout_historical_short_reference_anchors":EXPECTED_HOLDOUT_ANCHORS,
        "results":out,
        "baseline_170dpi_same_line_hits":base,
        "enhanced_220dpi_same_line_hits":higher,
        "net_220dpi_improvement_in_exact_phrase_hits":higher-base,
        "newly_recovered_by_220":sum(x["newly_recovered_by_220"] for x in per_anchor),
        "regressed_when_using_220":sum(x["regressed_when_using_220"] for x in per_anchor),
        "per_heldout_source_phrase_metadata":per_anchor,
        "validates_original_OCR_full_page_character_error_rate":False,
        "source_quoted_original_text_uploaded":False,
        "production_OCR_default_modified":False,
        "human_full_page_transcriptions_added":0,
        "actual_Cangjie_five_extractor_semantic_agents_run":False,
        "new_live_Faceface_historical_rules":0,
        "warning":"Twelve legacy V5 short quoted fragments on seven heldout original source pages; "
                  "does not validate the full 268 scans or all 922 lexical candidates."
    }


def run(scan_dir:Path,private_dir:Path,report_path:Path,
        catalog:dict,pilot:dict)->dict:
    holdout=holdout_pages(catalog,pilot)
    workspace=ReviewWorkspace(scan_dir,private_dir/"ocr",
                              private_dir/"reviewed-must-stay-empty")
    from paddleocr import PaddleOCR
    engine=PaddleOCR(**SETTINGS)
    report_rows={variant:[] for variant,_ in VARIANTS}
    with tempfile.TemporaryDirectory(prefix="faceface-m1611-holdout-") as temp:
        root=Path(temp)
        for index,phrases in sorted(holdout.items()):
            pageid=f"{SOURCE}:p{index:03d}"
            source=workspace.sources[SOURCE]
            for variant,dpi in VARIANTS:
                image=render_page(source["pdf"],index,
                                  root/f"page-{index:03d}-{dpi}",dpi)
                outputs=list(engine.predict(str(image)))
                if len(outputs)!=1:
                    raise ValueError("PaddleOCR returned unexpected number of original page outputs")
                lines,_,_=extract_lines(outputs[0])
                ocr="\n".join(str(line).strip() for line in lines if str(line).strip())
                local=private_dir/"original-page-OCR-holdout"/f"{index:03d}-{variant}.txt"
                atomic_write(local,(ocr+"\n").encode("utf-8"))
                scored=score_one(ocr,phrases,pageid,source["pdf_sha256"],variant)
                report_rows[variant].append(scored)
                print(json.dumps({
                    "source_page":pageid,"variant":variant,
                    "actual_original_image_PaddleOCR_inference":True,
                    "same_line_original_phrase_hits":scored["exact_single_line_hits"],
                    "reference_count":len(phrases),
                },ensure_ascii=False),flush=True)
    result=summarize(report_rows,holdout)
    atomic_write(report_path,(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("per_heldout_source_phrase_metadata","warning")},
                     ensure_ascii=False),flush=True)
    return result


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",required=True,type=Path)
    p.add_argument("--private-dir",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--catalog",type=Path,default=Path(
        "src/knowledge/maiyi-source-checked-v5.json"
    ))
    p.add_argument("--dev-anchors",type=Path,default=Path(
        "research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"
    ))
    args=p.parse_args()
    run(args.scan_dir,args.private_dir,args.out,
        json.loads(args.catalog.read_text(encoding="utf-8")),
        json.loads(args.dev_anchors.read_text(encoding="utf-8")))


if __name__=="__main__":
    main()
