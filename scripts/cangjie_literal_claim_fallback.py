#!/usr/bin/env python3
"""M16.20: exact-character archival candidate fallback for short source phrases.

The local Qwen3 4B model made three genuine requests in M16.19 but did not
produce the obvious traditional longevity relation in 鼻長有壽. This module
isolates narrow, contiguous morphology+outcome expressions as an independent
source-literal *candidate*, never declaring a verified historical passage
or a user's real lifespan, wealth, or moral character.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write
from scripts.cangjie_historical_claim_ledger import validate_relations

# Intentionally tiny high-precision grammar: two immediately adjacent chunks,
# an anatomy + shape character followed by 有 + literal auspicious outcome.
# Broader semantics must be processed by upstream Cangjie and source review.
PAIR = re.compile(
    r"(?P<morph>[鼻耳眼目口眉額頦面][長短大小方圓厚薄高低直闊豐])"
    r"(?P<claim>有[壽寿富貴贵祿禄])"
)
DOMAIN = {
    "壽": "longevity", "寿": "longevity",
    "富": "wealth", "貴": "wealth", "贵": "wealth",
    "祿": "wealth", "禄": "wealth",
}


def scan_catalog(catalog: dict) -> dict:
    if catalog.get("dataset") != "faceface-source-checked-v5":
        raise ValueError("Expected original legacy source-checked V5 catalog")
    entries = []
    stats = {"source_count": 0, "literal_pair_hits": 0, "unmatched_short_sources": 0}
    for row in catalog.get("cards", []):
        src = row.get("source") or {}
        if not isinstance(src, dict) or "44091_" not in src.get("source_url", ""):
            raise ValueError("Unexpected legacy source record")
        page = src.get("pdf_page_zero_based")
        if type(page) is not int or not 0 <= page < 153:
            raise ValueError("Invalid source page")
        quote = row.get("source_phrase")
        if not isinstance(quote, str) or not quote:
            raise ValueError("Missing original short phrase")
        rid = row.get("id")
        if not isinstance(rid, str) or not rid:
            raise ValueError("Missing source item ID")
        stats["source_count"] += 1
        matches = list(PAIR.finditer(quote))
        if not matches:
            stats["unmatched_short_sources"] += 1
        for match in matches:
            morph = match.group("morph")
            claim = match.group("claim")
            domain = DOMAIN[claim[-1]]
            digest = hashlib.sha256((rid + "|" + morph + "|" + claim).encode()).hexdigest()[:24]
            entries.append({
                "relation_id": "m1620:" + digest,
                "source_passage_id": rid,
                "edition_id": "1925-Wenming-QinShenan",
                "source_id": "nlc-44091",
                "source_pdf_sha256": KNOWN_SCAN_SHA256["nlc-44091"],
                "pdf_page_zero_based": page,
                "quote_original": quote,
                "quote_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                "transcription_review_status": "source_unverified",
                "morphology_original": morph,
                "historical_claim_original": claim,
                "conditions_original": "",
                "exception_original": "",
                "context_original": "",
                "traditional_relation_type": "explicit_in_source",
                "historical_claim_domains": [domain],
                "photo_observability": "unknown",
                "report_eligibility": "archive_only",
                "conflicting_sources": [],
                "modern_explanation": "",
                "eligible_for_Faceface_live_rules": False,
                "claims_real_person_outcome": False,
            })
            stats["literal_pair_hits"] += 1
    ledger = {"schema": "faceface-historical-claims-v1", "relations": entries}
    audited = validate_relations(ledger)
    return {
        "ledger": ledger,
        "audit": audited,
        "stats": stats,
        "method": "tiny_contiguous_literal_pair_grammar_not_Cangjie_model",
        "human_original_scan_verified_by_this_run": False,
        "full_original_book_coverage": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", type=Path, default=Path("src/knowledge/maiyi-source-checked-v5.json"))
    p.add_argument("--private-output", type=Path, required=True)
    p.add_argument("--public-audit", type=Path, required=True)
    args = p.parse_args()
    private, public = args.private_output.resolve(), args.public_audit.resolve()
    if private == public or private.exists() or public.exists():
        raise ValueError("Do not overwrite source, private ledger or existing audit")
    result = scan_catalog(json.loads(args.catalog.read_text(encoding="utf-8")))
    atomic_write(private, (json.dumps(result["ledger"], ensure_ascii=False, indent=2) + "\n").encode())
    audit = {**result["stats"], "domain_counts": result["audit"]["historical_domain_membership_counts"],
             "source_verification": "legacy_AI_visual_only_not_human_signed",
             "method": result["method"], "new_live_rules": 0,
             "complete_source_book_coverage": False,
             "official_cangjie_model_calls": 0}
    atomic_write(public, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
