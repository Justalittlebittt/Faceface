#!/usr/bin/env python3
"""M16.2: audit all six OCR shard metadata reports; never claim text is reviewed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.cangjie_corpus_stage import SCANS


def aggregate(paths: list[Path]) -> dict:
    seen: dict[str, dict] = {}
    hashes: dict[str, str] = {}
    total_han = 0
    incomplete = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = data["source_id"]
        source = next((s for s in SCANS if s["id"] == sid), None)
        if source is None:
            raise ValueError(f"Unknown source id: {sid}")
        if data["total_pdf_pages"] != source["expected_pages"]:
            raise ValueError(f"Scan page count mismatch: {sid}")
        if sid in hashes and hashes[sid] != data["source_pdf_sha256"]:
            raise ValueError(f"Conflicting original PDF sha256: {sid}")
        hashes[sid] = data["source_pdf_sha256"]
        if data["processed_pages"] != len(data["pages"]):
            raise ValueError(f"Shard count mismatch: {path}")
        for page in data["pages"]:
            page_id = page["page_id"]
            index = page["pdf_page_zero_based"]
            if not (0 <= index < source["expected_pages"]):
                raise ValueError(f"Page out of bounds: {page_id}")
            if page_id != f"{sid}:p{index:03d}" or page_id in seen:
                raise ValueError(f"Duplicate or invalid page id: {page_id}")
            if page.get("source_pdf_sha256") != hashes[sid]:
                raise ValueError(f"Incorrect per-page PDF provenance: {page_id}")
            if page.get("requires_manual_page_review") is not True or \
               page.get("eligible_for_cangjie_verified_corpus") is not False:
                raise ValueError(f"Unreviewed OCR was promoted: {page_id}")
            if page.get("state") not in ("ocr_candidate", "empty_ocr_candidate"):
                raise ValueError(f"Unexpected OCR result: {page_id}")
            seen[page_id] = page
            total_han += page["han_char_count"]
            if page["state"] == "empty_ocr_candidate":
                incomplete.append(page_id)
    expected = {f"{s['id']}:p{i:03d}" for s in SCANS for i in range(s["expected_pages"])}
    missing = sorted(expected - set(seen))
    if missing:
        raise ValueError(f"Missing OCR attempts ({len(missing)}): {missing[:8]}")
    if len(seen) != len(expected):
        raise ValueError("Unexpected OCR attempt set")
    for s in SCANS:
        if s["id"] not in hashes:
            raise ValueError(f"No scan provenance: {s['id']}")
    all_pages = sorted(seen.values(), key=lambda x: (x["source_id"], x["pdf_page_zero_based"]))
    confidences = [x["mean_word_confidence"] for x in all_pages
                   if x["mean_word_confidence"] is not None]
    low_confidence_pages = [x["page_id"] for x in all_pages
                            if x["mean_word_confidence"] is not None
                            and x["mean_word_confidence"] < 50]
    return {
        "status": "all_scanned_pages_ocr_attempted_but_unreviewed",
        "ocr_attempted_pages": len(all_pages),
        "expected_pages": len(expected),
        "candidate_text_pages": len(all_pages) - len(incomplete),
        "empty_ocr_pages": incomplete,
        "ocr_candidate_han_chars": total_han,
        "mean_ocr_word_confidence_across_pages": round(sum(confidences) / len(confidences), 1)
            if confidences else None,
        "low_confidence_pages_below_50": low_confidence_pages,
        "source_pdf_sha256": hashes,
        "human_reviewed_pages": 0,
        "full_book_agent_extraction_performed": False,
        "cangjie_active_rules_created": 0,
        "notice": "These are unreviewed OCR candidates. Not original-checked text, not Cangjie distillation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    audit = aggregate(args.reports)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
