#!/usr/bin/env python3
"""M16.22 private unreviewed OCR -> genuine pinned Cangjie-guided model batches.

Runs *research only* on source-fingerprinted M16.21 private OCR cue JSONL,
not on the aggregate GitHub report. OCR is not verified classical quotation.
A model response must cite an exact substring of that OCR cue and may still be
wrong about the original page, the relation, or the ancient claim's meaning.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.cangjie_clean_source_agents import OllamaClient, official_role_texts
from scripts.cangjie_real_historical_relations import run_relation_agents
from scripts.cangjie_historical_claim_ledger import validate_relations
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, atomic_write, ReviewWorkspace

BATCH_KIND = "faceface-m16-22-source-unverified-private-OCR-semantic-research"


def read_private_cues(paths: list[Path], max_cues: int = 0) -> tuple[list[dict], dict]:
    """All source IDs and fragments must originate from M16.21's private OCR."""
    if not paths or type(max_cues) is not int or max_cues < 0:
        raise ValueError("Need private OCR JSONL paths and a nonnegative cap")
    sources, seen = [], set()
    counts = Counter()
    excluded = Counter()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Missing private outcome OCR cue file: {path}")
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                raise ValueError("Unexpected private OCR cue record")
            sid = obj.get("source_id")
            page = obj.get("pdf_page_zero_based")
            cue_id = obj.get("cue_id")
            excerpt = obj.get("short_ocr_line_unverified")
            if (sid not in KNOWN_SCAN_SHA256
                or type(page) is not int
                or page < 0
                or page >= (153 if sid == "nlc-44091" else 115)
                or obj.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[sid]
                or not isinstance(cue_id, str) or len(cue_id) != 24
                or not all(c in "0123456789abcdef" for c in cue_id)
                or cue_id in seen
                or not isinstance(excerpt, str)
                or len(excerpt) > 80
                or obj.get("source_image_human_verified") is not False
                or obj.get("historical_relation_established") is not False
                or obj.get("eligible_for_live_rules") is not False):
                raise ValueError("Invalid source/quote provenance or false verification")
            scanned = obj.get("outcome_terms_UNVERIFIED")
            if not isinstance(scanned, dict) or not scanned:
                raise ValueError("Cue has no lexical outcome terms")
            if not isinstance(obj.get("unreviewed_ocr_text_sha256"), str) or len(obj["unreviewed_ocr_text_sha256"]) != 64:
                raise ValueError("Missing OCR source text digest")
            if not isinstance(obj.get("same_OCR_line_morphology_regions"), list):
                raise ValueError("Missing independently assessed morphology proximity")
            seen.add(cue_id)
            counts.update(scanned.keys())
            # A genuine OCR line may contain only one Han glyph (e.g. 壽).
            # Preserve provenance and audit it, but do not send it to the LLM.
            if len(excerpt) < 2:
                excluded["single_character_OCR_line_not_modelable"] += 1
                continue
            sources.append({
                "id": "m1622-ocr:" + cue_id,
                "legacy_entry_kind": "unverified_ocr_page_line",
                "source_id": sid,
                "pdf_page_zero_based": page,
                "original_pdf_sha256": KNOWN_SCAN_SHA256[sid],
                "page_id": f"{sid}:p{page:03d}",
                "source_excerpt": excerpt,
                "source_excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                "unreviewed_ocr_text_sha256": obj["unreviewed_ocr_text_sha256"],
                "candidate_lexical_domains": sorted(scanned),
                "source_excerpt_newly_human_reviewed": False,
                "this_experiment_may_add_live_rule": False,
            })
    sources.sort(key=lambda s: (s["source_id"], s["pdf_page_zero_based"], s["id"]))
    total = len(sources)
    if max_cues:
        sources = sources[:max_cues]
    return sources, {"available_private_cues": total,
                     "selected_cues": len(sources),
                     "raw_lexical_domain_memberships": dict(counts),
                     "excluded_private_cues_by_reason": dict(excluded),
                     "source_review_level": "UNREVIEWED_MACHINE_OCR"}


def run_private_batch(paths: list[Path], scan_dir: Path, upstream: Path,
                      private_out: Path, public_meta: Path,
                      max_cues: int = 0, ollama_url: str = "http://127.0.0.1:11434",
                      model_name: str = "qwen3:4b-instruct") -> dict:
    private_out, public_meta = private_out.resolve(), public_meta.resolve()
    if private_out == public_meta or private_out.exists() or public_meta.exists():
        raise ValueError("Refuse to overwrite research output or mix private/public")
    selected, selection = read_private_cues(paths, max_cues)
    if not selected:
        raise ValueError("No actual private OCR candidate text, refusing synthetic success")
    # Re-inspect both pinned source PDFs, never take scanned lineage on faith.
    workspace = ReviewWorkspace(scan_dir, private_out.parent / "_absent_ocr",
                                private_out.parent / "_absent_reviewed")
    for item in selected:
        workspace.page_paths(item["source_id"], item["pdf_page_zero_based"])
        if workspace.sources[item["source_id"]]["pdf_sha256"] != item["original_pdf_sha256"]:
            raise ValueError("Private OCR cue source does not match original 1925 PDF")
    upstream_info, prompts = official_role_texts(upstream)
    client = OllamaClient(ollama_url, model_name)
    model_identity = client.installed()
    result = run_relation_agents(selected, client, prompts)
    ledger = {"schema": "faceface-historical-claims-v1", "relations": result["relations"]}
    checked = validate_relations(ledger)
    failures = Counter(x["reason"] for x in result["rejections"])
    private_record = {
        "kind": BATCH_KIND, "model": model_identity,
        "upstream": upstream_info, "selection": selection,
        "full_book_source_text_verified": False,
        "source_records_UNVERIFIED": selected,
        "archival_ledger_SOURCE_UNVERIFIED": ledger,
        "rejections_private": result["rejections"],
        "actual_model_requests_attempted": result["real_requests_attempted"],
        "no_live_rules_created": True,
    }
    atomic_write(private_out, (json.dumps(private_record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    public = {
        "kind": BATCH_KIND, "actual_original_PDF_source_hashes_verified": True,
        "actual_official_pinned_prompts_loaded": True,
        "official_Cangjie_five_roles_run_in_this_batch": False,
        "real_model": model_identity,
        "available_private_cues": selection["available_private_cues"],
        "excluded_private_cues_by_reason": selection["excluded_private_cues_by_reason"],
        "selected_private_OCR_cues": selection["selected_cues"],
        "real_model_requests_attempted": result["real_requests_attempted"],
        "OCR_literal_draft_relations": checked["relation_count"],
        "OCR_literal_domain_memberships": checked["historical_domain_membership_counts"],
        "rejected_model_outputs_by_reason": dict(failures),
        "original_page_human_reviewed": 0,
        "verified_historical_morphology_outcome_relations": 0,
        "new_live_Faceface_rules": 0,
        "all_model_extractions_are_unverified_OCR_candidates": True,
        "full_book_semantic_extraction_complete": False,
        "public_file_contains_OCR_excerpt_or_model_text": False,
    }
    atomic_write(public_meta, (json.dumps(public, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(public, ensure_ascii=False))
    return public


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cues", nargs="+", type=Path, help="M16.21 PRIVATE per-shard OCR cue JSONL files")
    p.add_argument("--scan-dir", type=Path, required=True)
    p.add_argument("--upstream", type=Path, required=True)
    p.add_argument("--private-out", type=Path, required=True)
    p.add_argument("--public-metadata", type=Path, required=True)
    p.add_argument("--max-cues", type=int, default=0,
                   help="0=all selected private cues; positive cap for bounded real pilot")
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    p.add_argument("--model", default="qwen3:4b-instruct")
    args = p.parse_args()
    run_private_batch(args.cues, args.scan_dir, args.upstream,
                      args.private_out, args.public_metadata, args.max_cues,
                      args.ollama_url, args.model)


if __name__ == "__main__":
    main()
