#!/usr/bin/env python3
"""M16.16: validate private archival face-shape -> classical-claim relations.

The ledger retains historical claims even when a photograph cannot measure the
feature. No entry is a prediction about a living person or a live website rule.
This validator does not run OCR/Cangjie, attest readings or create examples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write

DOMAINS = {
    "wealth", "longevity", "moral_character", "temperament", "marriage",
    "family", "offspring", "career", "social_status", "fortune",
    "health", "other", "none"
}
SOURCE_STATES = {"source_unverified", "human_attested_short_roi", "human_reviewed_full_page"}
OBSERVABILITY = {"measurable", "partial", "unavailable", "unknown"}
CLAIM_LINKS = {"explicit_in_source", "contextual", "ambiguous", "not_linked"}
REPORT_STATES = {"archive_only", "research_candidate", "source_reference_only"}


def _required_text(item: dict, field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 600:
        raise ValueError(f"Missing/invalid {field}")
    return value.strip()


def _optional_text(item: dict, field: str) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 1200:
        raise ValueError(f"Invalid {field}")
    return value


def validate_relations(document: dict) -> dict:
    if document.get("schema") != "faceface-historical-claims-v1":
        raise ValueError("Unknown historical claim ledger schema")
    entries = document.get("relations")
    if not isinstance(entries, list):
        raise ValueError("Relations must be a list")
    seen = set()
    counts = {domain: 0 for domain in sorted(DOMAINS)}
    pages = set()
    source_states = {state: 0 for state in SOURCE_STATES}
    for relation in entries:
        if not isinstance(relation, dict):
            raise ValueError("Relation must be an object")
        rid = _required_text(relation, "relation_id")
        if rid in seen:
            raise ValueError(f"Duplicate relation_id: {rid}")
        seen.add(rid)
        _required_text(relation, "source_passage_id")
        _required_text(relation, "edition_id")
        sid = _required_text(relation, "source_id")
        page = relation.get("pdf_page_zero_based")
        if (sid not in KNOWN_SCAN_SHA256 or type(page) is not int
                or not 0 <= page < (153 if sid == "nlc-44091" else 115)
                or relation.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[sid]):
            raise ValueError(f"Unpinned source or invalid page: {rid}")
        pages.add(f"{sid}:p{page:03d}")
        status = relation.get("transcription_review_status")
        if status not in SOURCE_STATES:
            raise ValueError(f"Unknown transcription status: {rid}")
        source_states[status] += 1
        quote = _required_text(relation, "quote_original")
        if relation.get("quote_sha256") != hashlib.sha256(quote.encode("utf-8")).hexdigest():
            raise ValueError(f"Historical quote SHA256 mismatch: {rid}")
        morphology = _optional_text(relation, "morphology_original")
        claim = _optional_text(relation, "historical_claim_original")
        _optional_text(relation, "conditions_original")
        _optional_text(relation, "exception_original")
        _optional_text(relation, "context_original")
        _optional_text(relation, "modern_explanation")
        if morphology is None and claim is None:
            raise ValueError(f"Both morphology and claim missing: {rid}")
        if relation.get("traditional_relation_type") not in CLAIM_LINKS:
            raise ValueError(f"Unknown classical relation type: {rid}")
        if relation["traditional_relation_type"] == "explicit_in_source" and (not morphology or not claim):
            raise ValueError(f"Explicit link must have both sides: {rid}")
        domains = relation.get("historical_claim_domains")
        if not isinstance(domains, list) or not domains or len(domains) != len(set(domains)):
            raise ValueError(f"Historical domains required and nonduplicated: {rid}")
        if any(domain not in DOMAINS for domain in domains):
            raise ValueError(f"Unknown historical domain: {rid}")
        if claim is None and domains != ["none"]:
            raise ValueError(f"No claim cannot be classified as outcome: {rid}")
        if claim is not None and "none" in domains:
            raise ValueError(f"Outcome claim must have a meaningful domain: {rid}")
        for domain in domains:
            counts[domain] += 1
        if relation.get("photo_observability") not in OBSERVABILITY:
            raise ValueError(f"Invalid photo observability: {rid}")
        if relation.get("report_eligibility") not in REPORT_STATES:
            raise ValueError(f"Invalid report eligibility: {rid}")
        conflicts = relation.get("conflicting_sources")
        if not isinstance(conflicts, list) or any(not isinstance(c, str) for c in conflicts):
            raise ValueError(f"Invalid source conflict list: {rid}")
        if status == "source_unverified" and relation["report_eligibility"] != "archive_only":
            raise ValueError(f"Unverified original cannot be report candidate: {rid}")
        if relation.get("eligible_for_Faceface_live_rules") is not False:
            raise ValueError(f"Archival records must never activate live rules: {rid}")
        if relation.get("claims_real_person_outcome") is not False:
            raise ValueError(f"Classical beliefs cannot become factual personal verdicts: {rid}")
    return {
        "schema": "faceface-historical-claims-audit-v1",
        "relation_count": len(entries),
        "unique_source_page_count": len(pages),
        "historical_domain_membership_counts": counts,
        "source_review_status_counts": source_states,
        "full_book_coverage_proven": False,
        "cangjie_extractor_runs_by_validator": 0,
        "runtime_rules_created": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--audit-output", type=Path, required=True)
    a = p.parse_args()
    src, dst = a.input.resolve(), a.audit_output.resolve()
    if src == dst or dst.exists():
        raise ValueError("Refuse to overwrite source or existing audit")
    result = validate_relations(json.loads(src.read_text(encoding="utf-8")))
    atomic_write(dst, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
