#!/usr/bin/env python3
"""M16.11: REAL original-image PP-OCRv5 targeted recovery benchmark.

Compare predeclared 170dpi baseline to 220dpi full-page, autocontrast and
overlapping vertical-strips on the SAME 13 M16.10 short, AI visually read
original-image anchors (6 1925 scanned pages).

These are PRELIMINARY AI-read original short phrases; independent human
original-source proofreading and 922-hit mining precision are NOT measured.
All recognized OCR text and cropped scan images are kept in a PRIVATE folder.
Public output contains only hashes, boolean per-anchor hits and aggregate stats.
No model-generated text/rules enter the Faceface website.

Example:
 python -m scripts.cangjie_ocr_recovery_11 \
   --scan-dir private/scans --anchors research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json \
   --private-dir private/m16-11 --out private/m16-11-metadata.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.cangjie_original_phrase_probe import (
    source_pages, validate_pilot
)
from scripts.cangjie_ocr_benchmark import only_han
from scripts.cangjie_paddleocr_benchmark import SETTINGS, extract_lines
from scripts.cangjie_paddleocr_candidates import render_page
from scripts.cangjie_review_core import (
    ReviewWorkspace, KNOWN_SCAN_SHA256, atomic_write
)

VARIANTS = (
    "baseline_170_original",
    "full_220_original",
    "full_220_autocontrast",
    "vertical_strips_220_overlap",
)
VERSION = "M16.11_FIXED_13_PHRASE_ORIGINAL_IMAGE_RECOVERY_V1"


def source_image_strips(image: Path, output_dir: Path) -> list[dict]:
    """Deterministic overlapping FULL-HEIGHT vertical regions, not anchor crops.

    Critical: the locations are predetermined from image WIDTH only, never
    selected using the reference answers (no hidden access to target position).
    This handles right-to-left historical multi-column layouts without
    claiming that the sequence of columns has been restored.
    """
    from PIL import Image
    with Image.open(image) as source:
        w,h=source.size
        if w<400 or h<400:
            raise ValueError("Original scan too small for deterministic OCR strips")
        width=max(240, round(w*0.34))
        width=min(width,w)
        step=max(60,round(w*0.19))
        starts=list(range(0,w-width+1,step))
        if not starts or starts[-1] != w-width:
            starts.append(w-width)
        # There must not be gaps between the source-image strips.
        if any(right-left>width for left,right in zip(starts,starts[1:])):
            raise ValueError("Tiled scan source coverage gap")
        output_dir.mkdir(parents=True,exist_ok=True)
        out=[]
        for i,left in enumerate(starts):
            right=min(left+width,w)
            path=output_dir/f"strip-{i:02d}.png"
            source.crop((left,0,right,h)).save(path)
            out.append({
                "path":path,
                "rectangle_in_source_pixels":[left,0,right,h],
                "source_image_width":w,
                "source_image_height":h,
            })
    return out


def prepare_autocontrast(original: Path, output: Path) -> Path:
    from PIL import Image, ImageOps
    with Image.open(original) as img:
        # Predeclared image-only contrast; no text/reference feedback.
        gray=img.convert("L")
        altered=ImageOps.autocontrast(gray,cutoff=2)
        altered.save(output)
    return output


def recognize(engine: object, image: Path) -> str:
    result=list(engine.predict(str(image)))
    if len(result)!=1:
        raise ValueError("PaddleOCR must return exactly one OCRResult per original/crop")
    lines,_,_=extract_lines(result[0])
    return "\n".join(line.strip() for line in lines if line.strip())


def score_variant(
    source: str,
    page: int,
    anchor_rows: list[dict],
    text_segments: list[str],
    variant: str,
) -> dict:
    """Any-segment matches cannot fraudulently concatenate adjacent strips."""
    if not text_segments:
        raise ValueError("OCR variant requires at least one real image inference")
    snippets=[only_han(s) for s in text_segments]
    lines=[only_han(line) for s in text_segments for line in s.splitlines()]
    results=[]
    for a in anchor_rows:
        if (a["source_id"],a["pdf_page_zero_based"])!=(source,page):
            raise ValueError("Mixed original-source pages in one OCR comparison")
        phrase=only_han(a["short_original_image_phrase_preliminary"])
        # On tiled images each segment is independent. Joining segments
        # could manufacture matches at tile boundaries, so never do so.
        on_one_image=any(phrase in text for text in snippets)
        on_one_line=any(phrase in line for line in lines)
        results.append({
            "anchor_id":a["id"],
            "exact_hit_in_one_OCR_image_segment":on_one_image,
            "exact_hit_in_one_OCR_line":on_one_line,
        })
    return {
        "variant":variant,
        "page_id":f"{source}:p{page:03d}",
        "source_id":source,
        "pdf_page_zero_based":page,
        "original_pdf_sha256":KNOWN_SCAN_SHA256[source],
        "source_image_segment_count":len(text_segments),
        "OCR_han_characters_in_segments_NOT_deduplicated":sum(len(t) for t in snippets),
        "recognition_segment_text_hashes":[
            hashlib.sha256(t.encode("utf-8")).hexdigest() for t in text_segments
        ],
        "anchor_results":results,
        "exact_image_segment_hits":sum(x["exact_hit_in_one_OCR_image_segment"] for x in results),
        "exact_single_OCR_line_hits":sum(x["exact_hit_in_one_OCR_line"] for x in results),
        "original_image_independently_human_reviewed":False,
        "ancient_rule_activated":False,
    }


def compare_experiments(
    per_variant_page: dict[str,list[dict]],
    anchors: list[dict]
) -> dict:
    if set(per_variant_page)!=set(VARIANTS):
        raise ValueError("Missing or unknown predeclared OCR experimental variant")
    pages=set(source_pages(anchors))
    all_ids={a["id"] for a in anchors}
    for name,records in per_variant_page.items():
        keys={(p["source_id"],p["pdf_page_zero_based"]) for p in records}
        if keys!=pages or len(records)!=len(pages):
            raise ValueError(f"{name} missing/duplicated source pages")
        ids=[x["anchor_id"] for page in records for x in page["anchor_results"]]
        if len(ids)!=len(all_ids) or set(ids)!=all_ids:
            raise ValueError(f"{name} returned missing or duplicate original anchors")
        if any(page.get("original_image_independently_human_reviewed") is not False
               or page.get("ancient_rule_activated") is not False for page in records):
            raise ValueError("OCR experiments cannot be human-approved or published")
    per_variant={}
    hit_maps={}
    for name,records in per_variant_page.items():
        mapping={
            row["anchor_id"]:row["exact_hit_in_one_OCR_line"]
            for page in records for row in page["anchor_results"]
        }
        hit_maps[name]=mapping
        per_variant[name]={
            "actual_source_pages_inferred":len(records),
            "actual_PaddleOCR_image_inferences":sum(p["source_image_segment_count"]
                                                    for p in records),
            "short_original_anchors_compared":len(mapping),
            "exact_same_OCR_line_hits":sum(mapping.values()),
            "exact_same_OCR_image_segment_hits":sum(
                p["exact_image_segment_hits"] for p in records
            ),
        }
    base=hit_maps[VARIANTS[0]]
    detail=[]
    for a in anchors:
        name=a["id"]
        matches={v:hit_maps[v][name] for v in VARIANTS}
        detail.append({
            "anchor_id":name,
            "page_id":f"{a['source_id']}:p{a['pdf_page_zero_based']:03d}",
            "region":a["region"],
            "existing_Faceface_metric":a["existing_faceface_metric"],
            "existing_photo_overlap":a["current_photo_overlap"],
            "baseline_exact_line":base[name],
            "per_configuration_exact_line":matches,
            "recovered_by_any_nonbaseline_variant":not base[name] and any(
                matches[v] for v in VARIANTS[1:]
            ),
            "regressed_in_any_variant":base[name] and any(
                not matches[v] for v in VARIANTS[1:]
            ),
            "original_quote_text_deliberately_excluded":True,
        })
    nonbaseline=VARIANTS[1:]
    variant_preference=sorted(nonbaseline,key=lambda v:(
        -per_variant[v]["exact_same_OCR_line_hits"],v
    ))[0]
    best=per_variant[variant_preference]["exact_same_OCR_line_hits"]
    baseline=per_variant[VARIANTS[0]]["exact_same_OCR_line_hits"]
    return {
        "kind":"M16.11_REAL_PP_OCR_FIXED_REFERENCE_PREPROCESSING_COMPARISON",
        "version":VERSION,
        "original_pdf_source_sha256":dict(KNOWN_SCAN_SHA256),
        "original_scan_pages":len(pages),
        "original_page_ids":[f"{s}:p{p:03d}" for s,p in sorted(pages)],
        "same_thirteen_AI_visually_read_preliminary_original_short_anchors":len(anchors),
        "variant_results":per_variant,
        "baseline_170dpi_exact_short_phrase_hits":baseline,
        "best_single_predeclared_enhanced_variant":variant_preference,
        "best_single_enhanced_exact_short_phrase_hits":best,
        "additional_phrases_detected_in_any_enhanced_configuration":sum(
            x["recovered_by_any_nonbaseline_variant"] for x in detail
        ),
        "any_enhanced_variant_recovered_the_priority_mouth_width_or_corner_reference":any(
            x["recovered_by_any_nonbaseline_variant"]
            for x in detail if x["anchor_id"] in ("M1610-A01","M1610-A08")
        ),
        "variant_selection_requires_new_heldout_sources":True,
        "enhanced_variant_should_replace_current_original_book_OCR":False,
        "all_13_short_phrase_statuses":detail,
        "only_short_phrase_exact_retrieval_measured_NOT_full_page_CER":True,
        "not_a_measure_of_precision_for_all_922_M16_9_lexical_hits":True,
        "independent_human_page_reviews_added":0,
        "new_live_faceface_rules":0,
        "official_Cangjie_semantic_agents_executed":False,
        "no_original_OCR_text_in_public_metadata":True,
        "evidence_note":"Changing image DPI, contrast and fixed geometric strips does not "
                        "verify original book text; even a higher count may be overfit "
                        "to 13 preliminary AI visually read phrases and needs held-out testing."
    }


def run(scan_dir: Path, private_dir: Path, out: Path, pilot: dict) -> dict:
    anchors=validate_pilot(pilot)
    pages=source_pages(anchors)
    workspace=ReviewWorkspace(scan_dir,private_dir/"ocr-candidates",
                              private_dir/"no-auto-human-review")
    for sid in workspace.sources:
        if workspace.sources[sid]["pdf_sha256"]!=KNOWN_SCAN_SHA256[sid]:
            raise ValueError("Unexpected original book scan SHA256")
    from paddleocr import PaddleOCR
    engine=PaddleOCR(**SETTINGS)
    records={v:[] for v in VARIANTS}
    with tempfile.TemporaryDirectory(prefix="faceface-m1611-") as tmp:
        folder=Path(tmp)
        for sid,index in pages:
            anchors_for_page=[a for a in anchors
                              if (a["source_id"],a["pdf_page_zero_based"])==(sid,index)]
            pdf=workspace.sources[sid]["pdf"]
            work=folder/f"{sid}-{index:03d}"
            work.mkdir(parents=True,exist_ok=True)
            baseline=render_page(pdf,index,work/"baseline170",170)
            higher=render_page(pdf,index,work/"original220",220)
            altered=prepare_autocontrast(higher,work/"autocontrast220.png")
            strips=source_image_strips(higher,work/"strips")
            images_by_variant={
                VARIANTS[0]:[baseline],
                VARIANTS[1]:[higher],
                VARIANTS[2]:[altered],
                VARIANTS[3]:[strip["path"] for strip in strips],
            }
            for variant,images in images_by_variant.items():
                texts=[recognize(engine,image) for image in images]
                private_path=(private_dir/"private-variant-OCR"/sid
                              /f"{index:03d}-{variant}.json")
                atomic_write(private_path,
                             (json.dumps({
                                 "source_id":sid,
                                 "pdf_page_zero_based":index,
                                 "original_pdf_sha256":workspace.sources[sid]["pdf_sha256"],
                                 "variant":variant,
                                 "source_image_rectangles":
                                     [s["rectangle_in_source_pixels"] for s in strips]
                                     if variant==VARIANTS[3] else None,
                                 "OCR_text_segments_UNREVIEWED":texts,
                                 "original_image_reviewed":False,
                             },ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
                result=score_variant(sid,index,anchors_for_page,texts,variant)
                records[variant].append(result)
                print(json.dumps({
                    "page_id":result["page_id"],"variant":variant,
                    "actual_image_inferences":len(images),
                    "exact_original_short_phrases_in_single_OCR_line":
                        result["exact_single_OCR_line_hits"],
                    "reference_anchor_count":len(anchors_for_page),
                },ensure_ascii=False),flush=True)
    comparison=compare_experiments(records,anchors)
    atomic_write(out,(json.dumps(comparison,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:v for k,v in comparison.items()
                      if k not in ("all_13_short_phrase_statuses","evidence_note")},
                     ensure_ascii=False),flush=True)
    return comparison


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--anchors",type=Path,default=Path(
        "research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"
    ))
    p.add_argument("--private-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    run(args.scan_dir,args.private_dir,args.out,
        json.loads(args.anchors.read_text(encoding="utf-8")))


if __name__=="__main__":
    main()
