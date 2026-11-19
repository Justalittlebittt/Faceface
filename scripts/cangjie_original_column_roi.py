#!/usr/bin/env python3
"""M16.12 exact original-source column-localized OCR pilot (1925 vertical script).

UNREVIEWED ONLY: the crop coordinates came from direct AI inspection of
the original PDF page screenshot. A human must inspect the private crop
and confirm its correct position and complete historical text to approve
any content.

This is a targeted source-region workflow, NOT a global OCR hyperparameter
sweep. It distinguishes:
  * text found in exactly ONE recognized OCR text line;
  * text found within ONE explicitly scoped original page column;
  * text only reconstructable across TWO MANUALLY LOCATED adjacent physical
    vertical columns in RIGHT-TO-LEFT classical reading order.
A reconstructed cross-column string is NOT counted as single-line OCR.
Never concatenate random page strips or cross distinct page sources.

For every region this script saves the actual source-image crop, rotated
image and real model output in --private-dir, while --out has ONLY original
PDF SHA, page/crop coordinates, OCR content hashes and boolean diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.cangjie_original_phrase_probe import validate_pilot
from scripts.cangjie_paddleocr_benchmark import SETTINGS, extract_lines
from scripts.cangjie_paddleocr_candidates import render_page
from scripts.cangjie_ocr_benchmark import only_han
from scripts.cangjie_review_core import ReviewWorkspace, KNOWN_SCAN_SHA256, atomic_write

VERSION = "M16.12_AI_LOCATED_ORIGINAL_SCAN_COLUMN_CROPS_V1"
SOURCE_LOCATOR_SCHEMA = "M16.12_AI_PRELIMINARY_VISIBLE_ORIGINAL_COLUMN_LOCATORS_V1"
ALLOWED_PHOTO_METRICS = {"mouth.width","mouth.corner","eyes.openness"}
ALLOWED_LAYOUTS = {
    "adjacent_vertical_columns_in_illustrated_mouth_type_verse",
    "single_vertical_column_in_facial_feature_paragraph",
}


def validate_targets(locators: dict, source_pilot: dict) -> list[dict]:
    if locators.get("schema") != SOURCE_LOCATOR_SCHEMA:
        raise ValueError("Invalid original-page locator schema")
    if locators.get("original_pdf_sha256") != KNOWN_SCAN_SHA256:
        raise ValueError("Original source SHA256 mismatches fixed 1925 PDFs")
    if locators.get("full_page_human_reviewed_count") != 0 or \
       locators.get("user_report_rules_activated") != 0:
        raise ValueError("Provisional OCR locators may not claim human approval or active rules")
    original={r["id"]:r for r in validate_pilot(source_pilot)}
    targets=locators.get("targets")
    if not isinstance(targets,list) or not targets:
        raise ValueError("Expected original-image region targets")
    ids=set()
    for target in targets:
        sid=target.get("source_id")
        idx=target.get("pdf_page_zero_based")
        target_id=target.get("target_id")
        ref=original.get(target.get("original_phrase_anchor_id"))
        if not isinstance(target_id,str) or target_id in ids:
            raise ValueError("Duplicate or invalid crop target ID")
        ids.add(target_id)
        if ref is None or (ref["source_id"],ref["pdf_page_zero_based"])!=(sid,idx):
            raise ValueError("Page locator disagrees with original source phrase page")
        if (ref["short_original_image_phrase_preliminary"] !=
                target.get("original_phrase_preliminary")):
            raise ValueError("Original image short phrase was modified or fabricated")
        if (ref["region"] != target.get("region") or
            target.get("phrase_source_status")!="AI_visual_short_phrase_preliminary_only" or
            target.get("eligible_live_rule") is not False):
            raise ValueError("Unverified source status must remain explicit")
        if not isinstance(target.get("photo_observability"),str) or \
           not target["photo_observability"].strip():
            raise ValueError("Source region observability must be recorded")
        boxes=target.get("column_boxes_right_to_left_normalized")
        layout=target.get("original_layout")
        if (layout not in ALLOWED_LAYOUTS or not isinstance(boxes,list)
            or len(boxes) not in (1,2)):
            raise ValueError("Invalid original page columns/layout")
        if (layout.startswith("adjacent_") and len(boxes)!=2 or
            layout.startswith("single_") and len(boxes)!=1):
            raise ValueError("Column count mismatches image layout type")
        centers=[]
        for box in boxes:
            if (not isinstance(box,list) or len(box)!=4
                or any(type(v) not in (float,int) for v in box)):
                raise ValueError("Image region coordinates must be normalized numbers")
            l,top,right,bottom=box
            if (not 0<=l<right<=1 or not 0<=top<bottom<=1
                or right-l<0.025 or bottom-top<0.14):
                raise ValueError("Invalid rectangle extent or bounds")
            centers.append((l+right)*0.5)
        if any(left<=right for left,right in zip(centers,centers[1:])):
            raise ValueError("Ancient original vertical columns MUST be right-to-left")
        if len(boxes)==2 and boxes[0][0]-boxes[1][2]>0.025:
            raise ValueError("Source-image columns are not physically adjacent")
    return targets


def crop_actual_original_page(
    original_page_png:Path, normalized_box:list[float],
    output:Path, scale:int=2
) -> dict:
    """Create a real physical-column crop and rotated horizontal-text view.

    PIL's +90deg CCW mapping changes TOP->BOTTOM source vertical script to
    LEFT->RIGHT text, without retyping/correcting OCR answers.
    """
    from PIL import Image
    if type(scale) is not int or not 1<=scale<=3:
        raise ValueError("Invalid original crop upscale")
    with Image.open(original_page_png) as image:
        image=image.convert("L")
        w,h=image.size
        if min(w,h)<500:
            raise ValueError("Original source page raster is too small")
        l,t,r,b=normalized_box
        box=(
            max(0,round(l*w)),max(0,round(t*h)),
            min(w,round(r*w)),min(h,round(b*h))
        )
        left,top,right,bottom=box
        if right-left<18 or bottom-top<60:
            raise ValueError("Source crop too narrow for actual OCR")
        output.parent.mkdir(parents=True,exist_ok=True)
        region=image.crop(box)
        # Vertical text top->bottom becomes left->right on CCW rotation.
        horizontal=region.rotate(90,expand=True)
        if scale>1:
            horizontal=horizontal.resize((horizontal.width*scale,
                                          horizontal.height*scale),
                                         resample=Image.Resampling.LANCZOS)
        horizontal.save(output)
    return {
        "absolute_rectangle_in_original_raster_px":list(box),
        "rotated_for_horizontal_detection_degrees_CCW":90,
        "resample_scale_after_rotation":scale,
        "rendered_source_raster_sha256":hashlib.sha256(
            original_page_png.read_bytes()
        ).hexdigest(),
        "real_private_crop_image_sha256":hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def actual_engine_text(engine:object, private_crop:Path)->str:
    result=list(engine.predict(str(private_crop)))
    if len(result)!=1:
        raise ValueError("Source region must have precisely one real OCR result")
    strings,_,_=extract_lines(result[0])
    return "\n".join(s.strip() for s in strings if s.strip())


def evaluate_region_ocr(
    target:dict, source_pdf_hash:str,
    column_texts_right_to_left:list[str],
    source_crop_metadata:list[dict]
)->dict:
    texts=column_texts_right_to_left
    if not texts or len(texts)!=len(target["column_boxes_right_to_left_normalized"]):
        raise ValueError("Different number of OCR outputs than actual source columns")
    if len(source_crop_metadata)!=len(texts):
        raise ValueError("Missing original-PDF image crop provenance")
    expected=only_han(target["original_phrase_preliminary"])
    individual_lines=[
        only_han(line) for text in texts for line in text.splitlines()
    ]
    single_line=any(expected in line for line in individual_lines)
    in_one_column=any(expected in only_han(text) for text in texts)
    # Rightmost physical vertical source column is earlier in the text,
    # provided the SOURCE layout was explicitly inspected and declared.
    adjacent_source_columns_joined=(
        len(texts)==2 and expected in "".join(only_han(s) for s in texts)
    )
    # NOT the same as one OCR line; this is a layout hypothesis requiring
    # human confirmation and should never qualify a historical rule.
    source_id,page=target["source_id"],target["pdf_page_zero_based"]
    return {
        "target_id":target["target_id"],
        "source_page_id":f"{source_id}:p{page:03d}",
        "source_pdf_sha256":source_pdf_hash,
        "region":target["region"],
        "source_image_layout":target["original_layout"],
        "original_image_phrase_model_visual_only":True,
        "source_column_count":len(texts),
        "source_crop_rectangles_normalized":
            target["column_boxes_right_to_left_normalized"],
        "real_original_crop_image_sha256":[
            x["real_private_crop_image_sha256"] for x in source_crop_metadata
        ],
        "PaddleOCR_text_segment_sha256":[
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts
        ],
        "raw_OCR_han_character_count_not_source_accuracy":
            sum(len(only_han(text)) for text in texts),
        "exact_original_phrase_within_one_OCR_line":single_line,
        "exact_original_phrase_within_one_physical_column":in_one_column,
        "only_if_two_explicitly_adjacent_original_columns_joined":
            bool(adjacent_source_columns_joined and not in_one_column),
        "phrase_still_missing_in_this_targeted_OCR":
            not (single_line or in_one_column or adjacent_source_columns_joined),
        "requires_human_to_check_crop_and_ancient_wording":True,
        "verified_complete_original_page":False,
        "produced_public_faceface_rule":False,
    }


def audit(results:list[dict], targets:list[dict])->dict:
    if len(results)!=len(targets) or len({r["target_id"] for r in results})!=len(targets):
        raise ValueError("Missing or duplicate source target OCR results")
    if {r["target_id"] for r in results}!={t["target_id"] for t in targets}:
        raise ValueError("Actual scanned original source target list incomplete")
    if any(r["verified_complete_original_page"] is not False
           or r["produced_public_faceface_rule"] is not False
           or r["requires_human_to_check_crop_and_ancient_wording"] is not True
           for r in results):
        raise ValueError("Unverified source image crop must not enter production knowledge")
    return {
        "kind":"M16.12_REAL_SOURCE_COLUMN_CROP_OCR_AND_REVIEW_PROVENANCE",
        "original_scan_page_count":len(set(r["source_page_id"] for r in results)),
        "source_page_ids":sorted(set(r["source_page_id"] for r in results)),
        "real_original_image_column_crops_OCR_inferred":sum(r["source_column_count"] for r in results),
        "short_AI_visually_read_ancient_references_tested":len(results),
        "exact_match_in_any_single_crop_OCR_line":sum(
            r["exact_original_phrase_within_one_OCR_line"] for r in results
        ),
        "exact_match_within_single_source_column":sum(
            r["exact_original_phrase_within_one_physical_column"] for r in results
        ),
        "retrieval_only_by_joining_explicit_source_adjacent_columns":sum(
            r["only_if_two_explicitly_adjacent_original_columns_joined"] for r in results
        ),
        "unmatched_priority_source_crop_targets":sum(
            r["phrase_still_missing_in_this_targeted_OCR"] for r in results
        ),
        "per_original_page_source_region_retrieval":results,
        "all_locations_AIon_screenshot_and_need_human_confirmation":True,
        "human_verified_original_short_quotes":0,
        "full_original_page_human_transcriptions_added":0,
        "official_Cangjie_semantic_extractor_calls_from_this_run":0,
        "new_live_Faceface_historical_rules":0,
        "public_artifact_contains_original_OCR_text_or_crop_image":False,
        "boundary":"Cross-column ordered text is a layout hypothesis, not a verified "
                   "historical phrase until a human checks its actual scanned positions."
    }


def run_real(
    scan_dir:Path, private_root:Path, out:Path,
    locators:dict, pilot:dict
)->dict:
    targets=validate_targets(locators,pilot)
    work=ReviewWorkspace(scan_dir,private_root/"OCR-private",
                         private_root/"reviewed-do-not-auto-approve")
    from paddleocr import PaddleOCR
    engine=PaddleOCR(**SETTINGS)
    source_pages=sorted({(t["source_id"],t["pdf_page_zero_based"]) for t in targets})
    with tempfile.TemporaryDirectory(prefix="faceface-m1612-orig-") as temp:
        root=Path(temp)
        images={}
        for sid,index in source_pages:
            original=work.sources[sid]
            if original["pdf_sha256"] != KNOWN_SCAN_SHA256[sid]:
                raise ValueError("1925 original PDF scan SHA256 changed")
            images[(sid,index)]=render_page(
                original["pdf"],index,root/f"{sid}-{index:03d}",220
            )
        results=[]
        for target in targets:
            sid,index=target["source_id"],target["pdf_page_zero_based"]
            crops=[]
            words=[]
            for i,coords in enumerate(target["column_boxes_right_to_left_normalized"]):
                dest=(private_root/"original-source-column-crops"/sid
                      /f"{index:03d}"/f"{target['target_id']}-col{i:02d}-rotated.png")
                meta=crop_actual_original_page(images[(sid,index)],coords,dest)
                crops.append(meta)
                words.append(actual_engine_text(engine,dest))
            result=evaluate_region_ocr(
                target,work.sources[sid]["pdf_sha256"],words,crops
            )
            original_only_private=(private_root/"original-source-column-crops"/sid
                                   /f"{index:03d}"/f"{target['target_id']}-OCR-private.json")
            atomic_write(original_only_private,
                         (json.dumps({
                             "original_pdf_sha256":work.sources[sid]["pdf_sha256"],
                             "page_id":f"{sid}:p{index:03d}",
                             "source_column_rectangles":crops,
                             "provisional_AI_visual_source_phrase":
                                 target["original_phrase_preliminary"],
                             "recognition_text_unreviewed":words,
                             "approved_by_human":False,
                         },ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
            print(json.dumps({
                "target_id":target["target_id"],
                "source_page_id":result["source_page_id"],
                "single_OCR_line_hit":result["exact_original_phrase_within_one_OCR_line"],
                "adjacent_original_columns_layout_only":
                    result["only_if_two_explicitly_adjacent_original_columns_joined"],
                "source_column_inferences":len(words),
            },ensure_ascii=False),flush=True)
            results.append(result)
    report=audit(results,targets)
    atomic_write(out,(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    return report


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--private-root",type=Path,required=True)
    p.add_argument("--source-region-locators",type=Path,default=Path(
        "research/M16_12_SOURCE_COLUMN_LOCATORS.json"
    ))
    p.add_argument("--source-phrases",type=Path,default=Path(
        "research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"
    ))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=run_real(
        a.scan_dir,a.private_root,a.out,
        json.loads(a.source_region_locators.read_text(encoding="utf-8")),
        json.loads(a.source_phrases.read_text(encoding="utf-8"))
    )
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("per_original_page_source_region_retrieval",
                                   "boundary")},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
