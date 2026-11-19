#!/usr/bin/env python3
"""Aggregate exactly 268 source-hashed unreviewed outcome lexical audit pages."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.cangjie_corpus_stage import SCANS
from scripts.cangjie_outcome_ocr_audit import VERSION, OUTCOME_TERMS
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write


def aggregate(reports: list[dict]) -> dict:
    if not reports:
        raise ValueError("Missing actual shard reports")
    expected = {f"{s['id']}:p{i:03d}" for s in SCANS for i in range(s["expected_pages"])}
    seen = {}
    for report in reports:
        sid = report.get("source_id")
        scan = next((s for s in SCANS if s["id"] == sid), None)
        if (scan is None or report.get("kind") != VERSION
            or report.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[sid]
            or report.get("actual_human_confirmed_historical_relations") != 0
            or report.get("new_live_Faceface_rules") != 0
            or report.get("official_Cangjie_model_calls") != 0
            or report.get("metadata_contains_ancient_ocr_text") is not False):
            raise ValueError("Untrusted source/report status")
        first, last = report.get("first_pdf_page_zero_based"), report.get("last_pdf_page_zero_based")
        if (type(first) is not int or type(last) is not int
            or not 0 <= first <= last < scan["expected_pages"]
            or report.get("processed_original_pages") != last-first+1
            or len(report.get("pages", [])) != last-first+1):
            raise ValueError("Incorrect page coverage for shard")
        for offset, page in enumerate(report["pages"]):
            index = first+offset
            pid = f"{sid}:p{index:03d}"
            if (pid in seen or page.get("page_id") != pid
                or page.get("source_id") != sid
                or page.get("pdf_page_zero_based") != index
                or page.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[sid]
                or page.get("human_reviewed") is not False
                or page.get("historical_relation_confirmed") is not False):
                raise ValueError("Duplicate, reordered or misattributed page")
            by_domain = page.get("outcome_ocr_line_hits_by_domain")
            prox = page.get("outcome_ocr_line_with_morphology_proximity_by_domain")
            if not isinstance(by_domain, dict) or not isinstance(prox, dict):
                raise ValueError("Invalid outcome page counts")
            if any(k not in OUTCOME_TERMS or type(v) is not int or v < 0
                   for k,v in [*by_domain.items(), *prox.items()]):
                raise ValueError("Unknown outcome domain/count")
            if any(n > by_domain.get(domain, 0) for domain, n in prox.items()):
                raise ValueError("Proximity exceeds OCR outcome hits")
            if page.get("OCR_state") not in ("ocr_candidate", "empty_ocr_candidate"):
                raise ValueError("Bad OCR page state")
            if page["OCR_state"] == "empty_ocr_candidate" and (by_domain or prox or page.get("ocr_text_sha256")):
                raise ValueError("Empty source page has invented signals")
            seen[pid] = page
        if report.get("pages_with_any_outcome_lexical_signal") != sum(
            bool(p["outcome_ocr_line_hits_by_domain"]) for p in report["pages"]
        ):
            raise ValueError("Incorrect positive-page count")
    if set(seen) != expected:
        raise ValueError(f"Not exact full original 268 pages: {len(seen)} / {len(expected)}")
    domain_pages = Counter()
    domain_hits = Counter()
    proximity_hits = Counter()
    pages_with_outcomes = 0
    pages_with_proximity = 0
    for page in seen.values():
        outcomes = page["outcome_ocr_line_hits_by_domain"]
        prox = page["outcome_ocr_line_with_morphology_proximity_by_domain"]
        pages_with_outcomes += bool(outcomes)
        pages_with_proximity += any(prox.values())
        for domain, count in outcomes.items():
            domain_hits[domain] += count
            domain_pages[domain] += 1
        for domain, count in prox.items():
            proximity_hits[domain] += count
    ranked = sorted(
        seen.values(), key=lambda p: (
            -len(p["outcome_ocr_line_hits_by_domain"]),
            -sum(p["outcome_ocr_line_hits_by_domain"].values()),
            p["source_id"], p["pdf_page_zero_based"],
        )
    )
    return {
        "kind": "M16.21_ACTUAL_WHOLE_BOOK_OUTCOME_OCR_LEXICAL_COVERAGE",
        "actual_source_pages_processed": 268,
        "source_pdf_sha256": KNOWN_SCAN_SHA256,
        "shards_checked": len(reports),
        "pages_with_any_outcome_lexical_signal": pages_with_outcomes,
        "pages_with_no_outcome_lexical_signal": 268-pages_with_outcomes,
        "pages_with_same_line_face_outcome_proximity": pages_with_proximity,
        "pages_by_domain": {k:domain_pages[k] for k in OUTCOME_TERMS},
        "OCR_line_hits_by_domain": {k:domain_hits[k] for k in OUTCOME_TERMS},
        "same_OCR_line_morphology_proximity_by_domain": {k:proximity_hits[k] for k in OUTCOME_TERMS},
        "review_priority_source_page_ids": [
            {"page_id":p["page_id"],
             "lexical_domains":sorted(p["outcome_ocr_line_hits_by_domain"]),
             "outcome_OCR_lines":sum(p["outcome_ocr_line_hits_by_domain"].values()),
             "contains_same_line_morphology_cues":bool(p["outcome_ocr_line_with_morphology_proximity_by_domain"])}
            for p in ranked[:20] if p["outcome_ocr_line_hits_by_domain"]
        ],
        "new_human_verified_original_pages": 0,
        "historically_valid_morphology_outcome_relations": 0,
        "official_Cangjie_model_calls": 0,
        "new_live_Faceface_rules": 0,
        "unreviewed_original_text_or_short_quotes_in_public_report": False,
        "warning": "OCR word hits and same-line proximity have ZERO semantic/accuracy guarantee. Do not equate count with classical claims.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = aggregate([json.loads(p.read_text(encoding="utf-8")) for p in args.reports])
    atomic_write(args.out, (json.dumps(result, ensure_ascii=False, indent=2)+"\n").encode())
    print(json.dumps({k:v for k,v in result.items() if k != "review_priority_source_page_ids"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
