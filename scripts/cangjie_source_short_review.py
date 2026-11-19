#!/usr/bin/env python3
"""M16.12 local ONLY, human-attested original short-column phrase review.

Unlike whole-page review, this creates a separately named SINGLE-ROI review
record. It is NOT counted as any fully-reviewed original scanned page and
CANNOT automatically activate a Faceface facial knowledge/report rule.

The user must open the original page + region crops stored by
scripts.cangjie_original_column_roi and personally check characters and
reading direction. A named reviewer must explicitly approve the small ROI.
No automated LLM/OCR inference is authorized to call this sign-off.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from scripts.cangjie_original_column_roi import validate_targets
from scripts.cangjie_review_core import (
    ReviewWorkspace, REJECTED_REVIEWERS, atomic_write, file_sha256
)
from scripts.cangjie_ocr_benchmark import only_han

CLASSIFICATIONS = {
    "observable_morphology","historical_assertion","figure_label","uncertain"
}


def create_source_short_review(
    target:dict, expected_source_sha:str,
    private_ocr_provenance:dict, private_root:Path,
    reviewer:str, corrected_text:str, classification:str,
    explicitly_checked_original_image:bool,
    note:str=""
) ->dict:
    reviewer=reviewer.strip() if isinstance(reviewer,str) else ""
    if len(reviewer)<3 or len(reviewer)>120 or reviewer.lower() in REJECTED_REVIEWERS:
        raise ValueError("Explicit non-automated named source-image reviewer required")
    if explicitly_checked_original_image is not True:
        raise ValueError("Must personally compare original image and actual cropped columns")
    if classification not in CLASSIFICATIONS:
        raise ValueError("Classify short ROI text, including uncertainty, before saving")
    if not isinstance(corrected_text,str) or \
       not 3<=len(only_han(corrected_text))<=150:
        raise ValueError("A short original scanned image transcription is required")
    if not isinstance(note,str) or len(note)>800:
        raise ValueError("Review note invalid or too long")
    sid,index=target["source_id"],target["pdf_page_zero_based"]
    if private_ocr_provenance.get("page_id")!=f"{sid}:p{index:03d}" or \
       private_ocr_provenance.get("original_pdf_sha256")!=expected_source_sha or \
       private_ocr_provenance.get("approved_by_human") is not False:
        raise ValueError("OCR crop provenance mismatched source or forged approval")
    crop_details=private_ocr_provenance.get("source_column_rectangles")
    if not isinstance(crop_details,list) or \
       len(crop_details)!=len(target["column_boxes_right_to_left_normalized"]):
        raise ValueError("Missing source-column crop records")
    hashes=[]
    for col,meta in enumerate(crop_details):
        expected=meta.get("real_private_crop_image_sha256")
        name=(private_root/"original-source-column-crops"/sid
              /f"{index:03d}"/f"{target['target_id']}-col{col:02d}-rotated.png")
        if (not name.is_file() or not isinstance(expected,str)
            or file_sha256(name)!=expected):
            raise ValueError("Original scanned-page column crop is missing or altered")
        hashes.append(expected)
    return {
        "kind":"M16.12_HUMAN_CONFIRMED_SHORT_SOURCE_ROI_NOT_COMPLETE_PAGE",
        "target_id":target["target_id"],
        "source_id":sid,"original_pdf_page_zero_based":index,
        "source_pdf_sha256":expected_source_sha,
        "human_confirmed_original_column_crop_sha256":hashes,
        "locators_are_AI_preliminary_not_independently_verified_without_review":True,
        "source_reading_direction":"vertical_top_down_columns_right_to_left",
        "transcribed_original_short_phrase_by_reviewer":corrected_text.strip(),
        "transcribed_source_quote_sha256":hashlib.sha256(
            corrected_text.strip().encode("utf-8")
        ).hexdigest(),
        "text_classification":classification,
        "reviewer":reviewer,
        "image_region_verified_explicitly_by_reviewer":True,
        "reviewed_at_UTC":datetime.now(timezone.utc).isoformat(),
        "review_note":note.strip(),
        "full_page_1925_original_reviewed":False,
        "eligible_for_further_SOURCE_SCOPED_Cangjie_research":
            classification=="observable_morphology",
        "Faceface_public_report_rule_automatically_created":False,
        "eligible_for_Faceface_live_rules":False,
        "cangjie_Adler_or_five_agents_already_run":False,
    }


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--private-root",type=Path,required=True)
    p.add_argument("--source-phrases",type=Path,default=Path(
        "research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json"
    ))
    p.add_argument("--source-region-locators",type=Path,default=Path(
        "research/M16_12_SOURCE_COLUMN_LOCATORS.json"
    ))
    p.add_argument("--target-id",required=True)
    p.add_argument("--reviewer",required=True)
    p.add_argument("--text",required=True,help="Characters manually checked against actual scanned original")
    p.add_argument("--classification",choices=sorted(CLASSIFICATIONS),required=True)
    p.add_argument("--confirmed-from-image",action="store_true")
    p.add_argument("--note",default="")
    args=p.parse_args()
    pilot=json.loads(args.source_phrases.read_text(encoding="utf-8"))
    locators=json.loads(args.source_region_locators.read_text(encoding="utf-8"))
    targets=validate_targets(locators,pilot)
    chosen=next((t for t in targets if t["target_id"]==args.target_id),None)
    if chosen is None:
        raise ValueError("Unknown locked original source ROI target")
    ws=ReviewWorkspace(args.scan_dir,args.private_root/"OCR-private",
                       args.private_root/"reviewed-ORIGINAL-FULL-PAGE-NOT-USED")
    sid,index=chosen["source_id"],chosen["pdf_page_zero_based"]
    saved=(args.private_root/"original-source-column-crops"/sid
           /f"{index:03d}"/f"{args.target_id}-OCR-private.json")
    provenance=json.loads(saved.read_text(encoding="utf-8"))
    review=create_source_short_review(
        chosen,ws.sources[sid]["pdf_sha256"],provenance,args.private_root,
        args.reviewer,args.text,args.classification,args.confirmed_from_image,args.note
    )
    outfile=args.private_root/"human-checked-source-SHORT-ROIs"/f"{args.target_id}.review.json"
    if outfile.exists():
        raise ValueError("Original short-ROI review already exists; cannot silently overwrite signed review")
    atomic_write(outfile,(json.dumps(review,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({
        "private_short_review_saved":str(outfile),
        "source_page_id":f"{sid}:p{index:03d}",
        "only_short_ROI_reviewed_not_full_page":True,
        "ancient_rule_activated":False
    },ensure_ascii=False))


if __name__=="__main__":
    main()
