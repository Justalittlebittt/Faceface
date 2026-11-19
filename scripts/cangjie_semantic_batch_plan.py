#!/usr/bin/env python3
"""M16.23: deterministic per-shard *private* OCR cue selection for real Cangjie.

Avoid first-N source-page bias when bounding expensive 268-page semantic runs.
Keep unobservable historical outcome domains (including wealth/longevity/virtue)
in the candidate pool, even when the OCR line has no facial morphology term.
This does not validate the original classical claim.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from scripts.cangjie_private_ocr_semantic_batch import read_private_cues
from scripts.cangjie_review_core import atomic_write

DOMAIN_ORDER = (
    "longevity", "wealth", "moral_character", "marriage", "career",
    "fortune", "family", "offspring", "social_status", "temperament",
)


def plan_private_shard(paths: list[Path], limit: int = 8) -> tuple[list[dict], dict]:
    if type(limit) is not int or limit < 1:
        raise ValueError("Model budget must be a positive integer")
    # Run the existing security, source-hash and anti-promotion gate FIRST.
    accepted, stats = read_private_cues(paths)
    if not accepted:
        raise ValueError("No eligible real private OCR excerpts")
    # Preserve exact original private OCR row, not a synthesized or modern quote.
    original = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                original["m1622-ocr:" + r["cue_id"]] = r
    groups = defaultdict(list)
    for entry in accepted:
        for domain in entry["candidate_lexical_domains"]:
            if domain in DOMAIN_ORDER:
                groups[domain].append(entry)
    # Spread each category across the shard, rather than always selecting
    # its earliest original page. Deterministic median first.
    for domain in groups:
        rows = sorted(groups[domain], key=lambda x: (
            x["pdf_page_zero_based"], x["id"]))
        n = len(rows)
        groups[domain] = sorted(rows, key=lambda x: (
            abs(rows.index(x) - (n-1)/2),
            x["pdf_page_zero_based"], x["id"]))
    chosen, ids, pages = [], set(), set()
    # Pick one diverse page per category; include domain-only records.
    for domain in DOMAIN_ORDER:
        options = groups.get(domain, [])
        if not options or len(chosen) >= limit:
            continue
        next_entry = next((e for e in options if e["id"] not in ids
                           and e["page_id"] not in pages), None)
        if next_entry is None:
            next_entry = next((e for e in options if e["id"] not in ids), None)
        if next_entry is None:
            continue
        chosen.append(next_entry)
        ids.add(next_entry["id"])
        pages.add(next_entry["page_id"])
    # Fill remaining slots from different pages, then allow page repeats.
    remaining = [e for e in accepted if e["id"] not in ids]
    remaining.sort(key=lambda e: (
        e["page_id"] in pages,
        -len(e["candidate_lexical_domains"]),
        e["source_id"], e["pdf_page_zero_based"], e["id"]))
    for entry in remaining:
        if len(chosen) >= limit:
            break
        chosen.append(entry)
        ids.add(entry["id"])
        pages.add(entry["page_id"])
    selected_rows = [original[e["id"]] for e in chosen]
    domain_counts = Counter(d for e in chosen for d in e["candidate_lexical_domains"])
    result = {
        "source_private_cues_before_policy": stats["available_private_cues"],
        "source_modelable_cues": stats["selected_cues"],
        "private_cues_selected_for_model": len(chosen),
        "distinct_original_scan_pages_selected": len(pages),
        "selected_OCR_lexical_domains": dict(domain_counts),
        "source_original_page_verified_against_image": False,
        "selector_does_not_run_Cangjie_models": True,
        "selector_does_not_create_live_rules": True,
    }
    return selected_rows, result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cues", nargs="+", type=Path)
    p.add_argument("--max-cues", type=int, default=8)
    p.add_argument("--private-selection", type=Path, required=True)
    p.add_argument("--public-selection-metadata", type=Path, required=True)
    args = p.parse_args()
    private = args.private_selection.resolve()
    public = args.public_selection_metadata.resolve()
    if private == public or private.exists() or public.exists():
        raise ValueError("Refuse to overwrite private OCR selection or public metadata")
    rows, stats = plan_private_shard(args.cues, args.max_cues)
    atomic_write(private, ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows)+"\n").encode())
    atomic_write(public, (json.dumps(stats, ensure_ascii=False, indent=2)+"\n").encode())
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
