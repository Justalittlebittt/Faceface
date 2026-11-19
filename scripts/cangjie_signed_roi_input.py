#!/usr/bin/env python3
"""M16.13: build a PRIVATE, provenance-checked short-ROI input for Cangjie.

This is an input gate, NOT an extractor or source approval system.
Only original-image human-attested short ROI records are eligible. OCR,
AI-transcribed preliminary text, figures, uncertain passages, and historical
claims are excluded from semantic morphology input. No live rules are written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, file_sha256
from scripts.cangjie_ocr_benchmark import only_han


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_signed_short_roi_inputs(locators: dict, private_root: Path) -> dict:
    targets = locators.get("targets")
    if not isinstance(targets, list):
        raise ValueError("Invalid source locator manifest")
    accepted, rejected = [], []
    seen = set()
    for target in targets:
        tid, sid, page = target["target_id"], target["source_id"], target["pdf_page_zero_based"]
        if tid in seen:
            raise ValueError("Duplicate target ID")
        seen.add(tid)
        expected = KNOWN_SCAN_SHA256.get(sid)
        if expected is None or locators["original_pdf_sha256"].get(sid) != expected:
            raise ValueError("Unpinned source in locator manifest")
        path = private_root / "human-checked-source-SHORT-ROIs" / f"{tid}.review.json"
        if not path.is_file():
            rejected.append({"target_id": tid, "reason": "missing_human_roi_review"})
            continue
        review = json.loads(path.read_text(encoding="utf-8"))
        phrase = review.get("transcribed_original_short_phrase_by_reviewer")
        hashes = review.get("human_confirmed_original_column_crop_sha256")
        reviewer = review.get("reviewer")
        fields_match = (
            review.get("kind") == "M16.12_HUMAN_CONFIRMED_SHORT_SOURCE_ROI_NOT_COMPLETE_PAGE"
            and review.get("target_id") == tid
            and review.get("source_id") == sid
            and type(review.get("original_pdf_page_zero_based")) is int
            and review["original_pdf_page_zero_based"] == page
            and review.get("source_pdf_sha256") == expected
            and review.get("image_region_verified_explicitly_by_reviewer") is True
            and review.get("full_page_1925_original_reviewed") is False
            and review.get("eligible_for_Faceface_live_rules") is False
            and review.get("Faceface_public_report_rule_automatically_created") is False
            and review.get("cangjie_Adler_or_five_agents_already_run") is False
            and isinstance(reviewer, str) and len(reviewer.strip()) >= 3
            and reviewer.strip().lower() not in {"auto", "ocr", "agent", "bot", "model", "anonymous"}
            and isinstance(phrase, str) and 3 <= len(only_han(phrase)) <= 150
            and review.get("transcribed_source_quote_sha256") == _digest(phrase)
            and isinstance(hashes, list)
            and len(hashes) == len(target["column_boxes_right_to_left_normalized"])
        )
        if not fields_match:
            rejected.append({"target_id": tid, "reason": "invalid_or_changed_signed_metadata"})
            continue
        crops_ok = True
        for i, expected_crop_sha in enumerate(hashes):
            png = (private_root / "original-source-column-crops" / sid
                   / f"{page:03d}" / f"{tid}-col{i:02d}-rotated.png")
            if not png.is_file() or file_sha256(png) != expected_crop_sha:
                crops_ok = False
                break
        if not crops_ok:
            rejected.append({"target_id": tid, "reason": "source_crop_missing_or_changed"})
            continue
        if (review.get("text_classification") != "observable_morphology"
                or review.get("eligible_for_further_SOURCE_SCOPED_Cangjie_research") is not True):
            rejected.append({"target_id": tid, "reason": "not_observable_morphology"})
            continue
        accepted.append({
            "target_id": tid, "source_id": sid, "pdf_page_zero_based": page,
            "source_pdf_sha256": expected, "crop_sha256": hashes,
            "human_attested_short_quote": phrase,
            "original_quote_sha256": _digest(phrase),
            "reviewed_at_UTC": review.get("reviewed_at_UTC"),
            "reviewer": reviewer,
            "historical_description_only": True,
            "verified_complete_page": False,
            "cangjie_extraction_executed": False,
            "website_rule_eligible": False,
        })
    return {
        "schema": "M16.13_PRIVATE_SOURCE_SCOPED_CANGJIE_INPUT_V1",
        "scope": "human_attested_short_ROIs_only_not_complete_book",
        "human_attested_source_short_ROIs": len(accepted),
        "full_pages_human_reviewed_by_this_tool": 0,
        "cangjie_agent_calls_performed_by_this_tool": 0,
        "live_rules_created": 0,
        "inputs": accepted,
        "not_admitted": rejected,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--locators", type=Path, default=Path(
        "research/M16_12_SOURCE_COLUMN_LOCATORS.json"))
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    root = args.private_root.resolve()
    out = args.out.resolve()
    if not out.is_relative_to(root):
        raise ValueError("Source quotes may only be written inside private-root")
    locators = json.loads(args.locators.read_text(encoding="utf-8"))
    report = collect_signed_short_roi_inputs(locators, root)
    if out.exists():
        raise ValueError("Output already exists; do not silently overwrite private research")
    atomic_write(out, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({
        "private_output": str(out), "eligible_short_rois": len(report["inputs"]),
        "excluded_short_rois": len(report["not_admitted"]),
        "cangjie_calls": 0, "live_rules_created": 0
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
