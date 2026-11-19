#!/usr/bin/env python3
"""M16.14: compile signed, source-scoped PRIVATE ROI input to research chunks.

This tool prepares a small batch for human-supervised official Cangjie
extractors. It does NOT run any AI, approve original text or activate rules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.cangjie_review_core import atomic_write, KNOWN_SCAN_SHA256
from scripts.cangjie_ocr_benchmark import only_han

SCHEMA = "M16.13_PRIVATE_SOURCE_SCOPED_CANGJIE_INPUT_V1"


def compile_source_scoped_chunks(manifest: dict) -> tuple[str, dict]:
    if manifest.get("schema") != SCHEMA or manifest.get("scope") != "human_attested_short_ROIs_only_not_complete_book":
        raise ValueError("Wrong signed source manifest type")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list):
        raise ValueError("Missing signed short ROI input list")
    if (manifest.get("human_attested_source_short_ROIs") != len(inputs)
            or manifest.get("full_pages_human_reviewed_by_this_tool") != 0
            or manifest.get("cangjie_agent_calls_performed_by_this_tool") != 0
            or manifest.get("live_rules_created") != 0):
        raise ValueError("Signed source manifest count/status mismatch")
    parts = [
        "# Faceface M16.14 — short, source-scoped traditional morphology research",
        "",
        "PRIVATE SOURCE-BOUNDED RESEARCH INPUT ONLY. Not whole-book text.",
        "The passages below are human-ATTESTED short image regions, not independently",
        "certified complete-page transcriptions. Do not infer personality, health,",
        "wealth, moral character or real fate from photographed appearance.",
        "Extraction result must remain a candidate pending independent source review;",
        "never create or activate a Faceface website rule from this document.",
        "",
    ]
    audit = {"schema": "M16.14_SOURCE_SCOPED_CHUNKS_AUDIT_V1",
             "short_roi_chunk_count": 0, "full_page_reviewed_count": 0,
             "cangjie_extractor_calls_performed": 0, "live_rules_created": 0,
             "target_ids": [], "page_ids": []}
    seen = set()
    for entry in inputs:
        if not isinstance(entry, dict):
            raise ValueError("Invalid short ROI entry")
        tid, sid, page = entry.get("target_id"), entry.get("source_id"), entry.get("pdf_page_zero_based")
        phrase = entry.get("human_attested_short_quote")
        if (not isinstance(tid, str) or not tid.startswith("M1612-T") or tid in seen
                or sid not in KNOWN_SCAN_SHA256 or type(page) is not int or page < 0
                or (sid == "nlc-44091" and page >= 153)
                or (sid == "nlc-44092" and page >= 115)
                or entry.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[sid]
                or not isinstance(phrase, str) or not 3 <= len(only_han(phrase)) <= 150
                or hashlib.sha256(phrase.encode("utf-8")).hexdigest() != entry.get("original_quote_sha256")
                or entry.get("historical_description_only") is not True
                or entry.get("verified_complete_page") is not False
                or entry.get("cangjie_extraction_executed") is not False
                or entry.get("website_rule_eligible") is not False):
            raise ValueError("Invalid signed source-scoped passage or unsafe approval")
        seen.add(tid)
        page_id = f"{sid}:p{page:03d}"
        parts.extend([
            f"## {tid} | {page_id}", "",
            f"Original 1925 scan identifier: {sid}",
            f"Original PDF SHA256: {KNOWN_SCAN_SHA256[sid]}",
            f"PDF page (zero-based): {page}",
            f"Human-attested short-region transcription: {phrase}",
            f"Quote SHA256: {entry['original_quote_sha256']}",
            "Source scope: short ROI only; page not completely reviewed.",
            "Cangjie tasks: distinguish visible morphology from historical",
            "interpretations, identify omitted conditions and ambiguities;",
            "flag all unsupported claims as needs_review rather than verified.",
            "Output status: RESEARCH_CANDIDATE_ONLY.", ""
        ])
        audit["target_ids"].append(tid)
        audit["page_ids"].append(page_id)
    audit["short_roi_chunk_count"] = len(inputs)
    if not inputs:
        parts.append("NO ADMITTED SHORT ROI EVIDENCE. Do not run extraction on this empty batch.")
    return "\n".join(parts) + "\n", audit


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--audit", type=Path, required=True)
    a = p.parse_args()
    root = a.private_root.resolve()
    inp, out, audit_path = (x.resolve() for x in (a.input, a.output, a.audit))
    if any(not p.is_relative_to(root) for p in (inp, out, audit_path)):
        raise ValueError("All signed source artifacts must remain in private root")
    if out == audit_path or any(x.exists() for x in (out, audit_path)):
        raise ValueError("Distinct, new output and audit paths required; never silently overwrite")
    manifest = json.loads(inp.read_text(encoding="utf-8"))
    markdown, audit = compile_source_scoped_chunks(manifest)
    atomic_write(out, markdown.encode("utf-8"))
    atomic_write(audit_path, (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
