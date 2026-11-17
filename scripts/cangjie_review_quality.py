#!/usr/bin/env python3
"""M16.5: real full-page OCR CER against *reviewed* 1925 scan transcriptions.

All scoring is read-only. A complete original image and signed local review
record are required; existing V5 snippets and unreviewed OCR don't count.
Chinese han-only CER deliberately keeps traditional/simplified distinctions.
Full-page OCR stream ordering is part of the edit distance. OCR scores from
different models cannot replace actual ground-truth comparisons.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from scripts.cangjie_review_core import ReviewWorkspace

HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def characters(text: str) -> str:
    return "".join(HAN.findall(text))


def edit_distance(reference: str, candidate: str) -> int:
    """Full Levenshtein distance, order-sensitive, with O(min(n,m)) memory."""
    if len(reference) < len(candidate):
        reference, candidate = candidate, reference
    prev = list(range(len(candidate)+1))
    for i, a in enumerate(reference, start=1):
        curr = [i]
        for j, b in enumerate(candidate, start=1):
            curr.append(min(
                prev[j] + 1,    # deleted
                curr[-1] + 1, # inserted
                prev[j-1] + (a != b), # substituted
            ))
        prev = curr
    return prev[-1]


def ordered_han_metrics(reference: str, candidate: str) -> dict:
    ref, hyp = characters(reference), characters(candidate)
    if not ref:
        raise ValueError("Cannot score a reviewed full page with no Han characters")
    distance = edit_distance(ref, hyp)
    ref_counts, hyp_counts = Counter(ref), Counter(hyp)
    multiset_overlap = sum((ref_counts & hyp_counts).values())
    return {
        "verified_reference_han_chars": len(ref),
        "candidate_han_chars": len(hyp),
        "levenshtein_edits": distance,
        "han_character_error_rate_order_sensitive": round(distance / len(ref), 6),
        "han_bag_recall_order_insensitive_diagnostic": round(
            multiset_overlap / len(ref), 6
        ),
        "warning": "Bag recall disregards reading order; NOT an OCR accuracy certificate.",
    }


def evaluate(workspace: ReviewWorkspace) -> dict:
    entries = []
    for source, info in workspace.sources.items():
        for index in range(info["page_count"]):
            page = workspace.page_info(source, index)
            if not page["is_reviewed_full_page"]:
                continue
            result = {
                "page_id": f"{source}:p{index:03d}",
                "source_pdf_sha256": info["pdf_sha256"],
                "reviewed_transcription_sha256": page["review"]["text_sha256"],
                "ocr_candidate_sha256": page["ocr_diagnostic"].get("text_sha256"),
                "has_valid_candidate_provenance": page["ocr_candidate_provenance_ok"],
            }
            if page["ocr_candidate_provenance_ok"]:
                result.update(ordered_han_metrics(
                    page["reviewed_text"], page["ocr_candidate"]
                ))
                result["scored"] = True
            else:
                result["scored"] = False
                result["reason"] = "missing or provenance-mismatched OCR candidate"
            entries.append(result)
    scored = [p for p in entries if p["scored"]]
    denom = sum(p["verified_reference_han_chars"] for p in scored)
    edits = sum(p["levenshtein_edits"] for p in scored)
    total = sum(s["page_count"] for s in workspace.sources.values())
    return {
        "kind": "faceface_m16_5_full_page_reference_CER",
        "original_scan_pages": total,
        "pages_with_page_specific_review_attestation": len(entries),
        "pages_compared_with_source_provenance_ocr": len(scored),
        "pages_with_review_but_unusable_candidate": len(entries) - len(scored),
        "verified_reference_han_characters_scored": denom,
        "summed_edit_distance": edits,
        "micro_average_han_CER_on_reviewed_pages_only": (
            round(edits/denom, 6) if denom else None
        ),
        "whole_book_review_gate_met": len(entries) == total,
        "whole_book_CER_available": len(scored) == total and bool(denom),
        "actual_cangjie_agent_extraction_performed": False,
        "runtime_rules_added": 0,
        "source_method": (
            "A reviewer explicitly compared the entire original page image, "
            "saved a text hash and a matching PDF hash. The edit distance "
            "preserves Chinese character order, strips all non-Han symbols, "
            "and does not normalize traditional/simplified variants."
        ),
        "important_limitation": (
            "Review records are self-attestation, not independent proof of human accuracy; "
            "unreviewed and source-mismatched pages are not scored. "
            "Page layout/figure completeness still requires visual checks."
        ),
        "pages": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-dir", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, required=True)
    parser.add_argument("--reviewed-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-scored-reference", action="store_true")
    args = parser.parse_args()
    w = ReviewWorkspace(args.scan_dir, args.ocr_dir, args.reviewed_dir)
    result = evaluate(w)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
    )
    print(json.dumps({k:v for k,v in result.items() if k!="pages"},ensure_ascii=False))
    if args.require_scored_reference and not result["pages_compared_with_source_provenance_ocr"]:
        raise SystemExit("NO SCORED PAGES: no real full-page reference attestation exists")


if __name__ == "__main__":
    main()
