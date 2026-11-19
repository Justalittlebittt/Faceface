#!/usr/bin/env python3
"""M16.17: ACTUAL Ollama/Cangjie historical morphology→outcome relation extraction.

Unlike the old five-role concept pilot, this captures separate literal evidence
spans for shape, classical outcome, condition and exception. Nothing from the
model can be called an original quote unless it occurs within the pinned source
excerpt. All results are RESEARCH/ARCHIVAL only, never individual verdicts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.cangjie_clean_source_agents import (
    OllamaClient, official_role_texts, source_short_catalog
)
from scripts.cangjie_review_core import ReviewWorkspace, atomic_write
from scripts.cangjie_historical_claim_ledger import DOMAINS, validate_relations

RELATION_FORMAT = {
    "type": "object",
    "properties": {"relations": {
        "type": "array", "items": {
            "type": "object",
            "properties": {
                "quote_id": {"type": "integer"},
                "morphology_span": {"type": "string"},
                "claim_span": {"type": "string"},
                "condition_span": {"type": "string"},
                "exception_span": {"type": "string"},
                "relation_type": {"type": "string", "enum": [
                    "explicit_in_source", "contextual", "ambiguous", "not_linked"
                ]},
                "claim_domain": {"type": "string", "enum": sorted(DOMAINS)},
            },
            "required": ["quote_id", "morphology_span", "claim_span",
                         "condition_span", "exception_span",
                         "relation_type", "claim_domain"],
            "additionalProperties": False
        }
    }},
    "required": ["relations"],
    "additionalProperties": False
}


def translate_model_relations(output: dict, sources: list[dict]) -> tuple[list[dict], list[dict]]:
    """No normalization or paraphrasing: every nonempty span is exact source text."""
    if not isinstance(output, dict) or set(output) != {"relations"} or not isinstance(output["relations"], list):
        raise ValueError("Model did not return the relation schema")
    accepted, rejected = [], []
    seen = set()
    for row in output["relations"]:
        if not isinstance(row, dict) or set(row) != set(RELATION_FORMAT["properties"]["relations"]["items"]["required"]):
            rejected.append({"reason": "invalid_fields"})
            continue
        idx = row["quote_id"]
        if type(idx) is not int or not 0 <= idx < len(sources):
            rejected.append({"reason": "unknown_quote_id"})
            continue
        src = sources[idx]
        quote = src["source_excerpt"]
        spans = ["morphology_span", "claim_span", "condition_span", "exception_span"]
        if any(not isinstance(row[k], str) or len(row[k]) > 150 or
               (row[k] and row[k] not in quote) for k in spans):
            rejected.append({"reason": "model_span_not_literal_original"})
            continue
        morph, claim = row["morphology_span"], row["claim_span"]
        if not morph and not claim:
            rejected.append({"reason": "no_evidence_spans"})
            continue
        if row["relation_type"] == "explicit_in_source" and not (morph and claim):
            rejected.append({"reason": "explicit_link_requires_two_spans"})
            continue
        domain = row["claim_domain"]
        if domain not in DOMAINS or ((not claim) != (domain == "none")):
            rejected.append({"reason": "outcome_domain_conflicts_with_claim"})
            continue
        rid = hashlib.sha256((src["id"] + "|" + morph + "|" + claim + "|" +
                              row["relation_type"]).encode("utf-8")).hexdigest()[:24]
        if rid in seen:
            rejected.append({"reason": "duplicate_relation"})
            continue
        seen.add(rid)
        entry = {
            "relation_id": "m1617:" + rid,
            "source_passage_id": src["id"],
            "edition_id": "1925-Wenming-QinShenan",
            "source_id": src["source_id"],
            "source_pdf_sha256": src["original_pdf_sha256"],
            "pdf_page_zero_based": src["pdf_page_zero_based"],
            "quote_original": quote,
            "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            "transcription_review_status": "source_unverified",
            "morphology_original": morph or None,
            "historical_claim_original": claim or None,
            "conditions_original": row["condition_span"],
            "exception_original": row["exception_span"],
            "context_original": "",
            "traditional_relation_type": row["relation_type"],
            "historical_claim_domains": [domain],
            "photo_observability": "unknown",
            "report_eligibility": "archive_only",
            "conflicting_sources": [],
            "modern_explanation": "",
            "eligible_for_Faceface_live_rules": False,
            "claims_real_person_outcome": False,
        }
        accepted.append(entry)
    return accepted, rejected


def run_relation_agents(sources: list[dict], model: OllamaClient, official: dict) -> dict:
    """One real model call per source: independent source excerpts, no OCR guesses."""
    rows = []
    failures = []
    calls = 0
    for i, src in enumerate(sources):
        # The historical claim may be absent. Never fill it from physiognomy lore.
        system = (
            "你正在使用固定版仓颉方法研究《麻衣相法》的传统相貌论述。"
            "将外形、传统断语、条件、例外分开。只返回输入引文中逐字连续出现的片段。"
            "引文没有财富寿命品德等说法就不要补写，也不得对真人作事实性推测。"
            "返回严格JSON。官方仓颉术语/原则提示节选：\n"
            + official["glossary"][:850] + "\n" + official["principle"][:850]
        )
        user = (
            f"quote_id: {i}\n古籍短引文: {src['source_excerpt']}\n"
            "只抽取本条引文有确切原字依据的形态、命运或性情等传统观点，"
            "缺少的字段用空字符串。不要返回别的quote_id。"
            "每条原文最多输出两条关系。"
        )
        calls += 1
        try:
            out = model.infer(system, user, RELATION_FORMAT)
            if len(out.get("relations", [])) > 2:
                raise ValueError("Too many model relations for a short original excerpt")
            accepted, rejected = translate_model_relations(out, sources)
            # The model request is scoped to ONE excerpt, never accept cross-excerpt IDs.
            accepted = [r for r in accepted if r["source_passage_id"] == src["id"]]
            cross = len(out.get("relations", [])) - len(accepted) - len(rejected)
            if cross > 0:
                rejected.append({"reason": "cross_source_quote_id", "count": cross})
            rows.extend(accepted)
            failures.extend({"source_id": src["id"], **r} for r in rejected)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
            failures.append({"source_id": src["id"], "reason": "model_or_schema_error",
                             "error_type": type(exc).__name__})
    return {"relations": rows, "rejections": failures, "real_requests_attempted": calls}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir", type=Path, required=True)
    p.add_argument("--upstream", type=Path, required=True)
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--public-metadata", type=Path, required=True)
    p.add_argument("--catalog", type=Path, default=Path("src/knowledge/maiyi-source-checked-v5.json"))
    p.add_argument("--model", default="qwen3:4b-instruct")
    p.add_argument("--source-ids", nargs="*", default=None, help="Exact legacy source IDs to include in a genuine small-sample pilot")
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = p.parse_args()
    ws = ReviewWorkspace(args.scan_dir, args.private_dir / "no-ocr",
                         args.private_dir / "no-full-page-review")
    sources = source_short_catalog(json.loads(args.catalog.read_text(encoding="utf-8")), ws)
    if args.source_ids is not None:
        chosen = set(args.source_ids)
        if not chosen or len(chosen) != len(args.source_ids) or not chosen.issubset({r["id"] for r in sources}):
            raise ValueError("Source sample must list distinct known legacy source IDs")
        sources = [r for r in sources if r["id"] in chosen]
    upstream, official = official_role_texts(args.upstream)
    client = OllamaClient(args.ollama_url, args.model)
    model_identity = client.installed()
    result = run_relation_agents(sources, client, official)
    ledger = {"schema": "faceface-historical-claims-v1", "relations": result["relations"]}
    audit = validate_relations(ledger)
    private = args.private_dir.resolve()
    public = args.public_metadata.resolve()
    if public.is_relative_to(private):
        raise ValueError("Public metadata must be outside private source workspace")
    ledger_path = private / "m16-17-historical-relations-private.json"
    if ledger_path.exists() or public.exists():
        raise ValueError("Never silently replace previous extraction evidence")
    atomic_write(ledger_path, (json.dumps({
        "model": model_identity, "pinned_upstream": upstream,
        "legacy_source_review_label": "AI_visual_legacy_not_new_human_signature",
        "ledger": ledger, "rejections": result["rejections"]
    }, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    summary = {
        "schema": "m16-17-real-historical-relations-extraction-metadata-v1",
        "source_short_excerpts": len(sources),
        "actual_model_requests_attempted": result["real_requests_attempted"],
        "source_literally_grounded_draft_relations": audit["relation_count"],
        "rejected_model_outputs": len(result["rejections"]),
        "historical_domain_memberships": audit["historical_domain_membership_counts"],
        "full_pages_human_checked": 0, "new_human_signed_roi": 0,
        "official_cangjie_prompts_pinned": True,
        "not_a_complete_five_agent_run": True,
        "new_live_rules": 0,
        "source_quality": "preexisting_AI_visual_excerpt_only",
    }
    atomic_write(public, (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
