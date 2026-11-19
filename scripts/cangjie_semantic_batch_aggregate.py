#!/usr/bin/env python3
"""M16.23 verify all six original scan shards and real semantic-request statistics.

An audit can cover 268 scanned pages without claiming 268-page semantic
extraction. The model sees a bounded, domain-balanced selection per shard.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.cangjie_outcome_ocr_aggregate import aggregate
from scripts.cangjie_review_core import atomic_write


def summarize(shard_reports: list[dict], model_reports: list[dict],
              selection_reports: list[dict]) -> dict:
    audit = aggregate(shard_reports)
    if len(model_reports) != 6 or len(selection_reports) != 6:
        raise ValueError("Require six real model and six selection shard reports")
    real_requests = 0
    candidates = 0
    rejected = Counter()
    outcomes = Counter()
    selected = 0
    for model, selection in zip(model_reports, selection_reports):
        if (model.get("kind") != "faceface-m16-22-source-unverified-private-OCR-semantic-research"
            or model.get("actual_original_PDF_source_hashes_verified") is not True
            or model.get("actual_official_pinned_prompts_loaded") is not True
            or model.get("official_Cangjie_five_roles_run_in_this_batch") is not False
            or model.get("all_model_extractions_are_unverified_OCR_candidates") is not True
            or model.get("full_book_semantic_extraction_complete") is not False
            or model.get("new_live_Faceface_rules") != 0
            or model.get("verified_historical_morphology_outcome_relations") != 0
            or model.get("original_page_human_reviewed") != 0
            or model.get("public_file_contains_OCR_excerpt_or_model_text") is not False):
            raise ValueError("Model report falsely claims source review or complete distillation")
        n = model.get("real_model_requests_attempted")
        count = model.get("selected_private_OCR_cues")
        sn = selection.get("private_cues_selected_for_model")
        if type(n) is not int or n < 1 or n != count or n != sn:
            raise ValueError("Real LLM requests must equal actual selected private cues")
        selected += sn
        real_requests += n
        c = model.get("OCR_literal_draft_relations")
        if type(c) is not int or c < 0:
            raise ValueError("Invalid literal draft count")
        candidates += c
        for domain, value in model.get("OCR_literal_domain_memberships", {}).items():
            if type(value) is not int or value < 0:
                raise ValueError("Bad classical outcome domain number")
            outcomes[domain] += value
        for reason, value in model.get("rejected_model_outputs_by_reason", {}).items():
            if type(value) is not int or value < 0:
                raise ValueError("Invalid rejected count")
            rejected[reason] += value
        if (selection.get("selector_does_not_run_Cangjie_models") is not True
            or selection.get("selector_does_not_create_live_rules") is not True
            or selection.get("source_original_page_verified_against_image") is not False):
            raise ValueError("Invalid private OCR selection policy")
    if sum(outcomes.values()) != candidates:
        raise ValueError("Domain totals inconsistent with literal candidate count")
    return {
        "schema": "M16.23_ALL_268_SCAN_PAGE_SIX_SHARD_BOUNDED_SEMANTIC_RESEARCH",
        "actual_1925_original_PDF_pages_re_OCR_processed": audit["actual_source_pages_processed"],
        "verified_original_scan_shards": audit["shards_checked"],
        "real_model_shards_with_private_OCR": len(model_reports),
        "private_OCR_cues_selected_across_all_shards": selected,
        "actual_Cangjie_guided_Qwen_model_requests": real_requests,
        "OCR_literal_source_span_draft_relations": candidates,
        "OCR_literal_domain_memberships": dict(outcomes),
        "rejections_by_reason": dict(rejected),
        "pages_with_any_outcome_OCR_lexeme": audit["pages_with_any_outcome_lexical_signal"],
        "original_image_independently_human_reviewed_pages_this_run": 0,
        "verified_original_historical_relations": 0,
        "full_268_page_Cangjie_five_role_semantic_extraction_executed": False,
        "actual_Qwen_calls_run_over_every_OCR_line": False,
        "new_Faceface_live_rules": 0,
        "original_ancient_OCR_text_in_public_aggregate": False,
        "warning": "Whole book actual OCR coverage, bounded real LLM calls only; private unverified OCR literal candidates are not scan-verified historical conclusions.",
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ocr-audits",nargs=6,required=True,type=Path)
    p.add_argument("--model-reports",nargs=6,required=True,type=Path)
    p.add_argument("--selection-reports",nargs=6,required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    result=summarize([json.loads(x.read_text(encoding="utf-8")) for x in a.ocr_audits],
                     [json.loads(x.read_text(encoding="utf-8")) for x in a.model_reports],
                     [json.loads(x.read_text(encoding="utf-8")) for x in a.selection_reports])
    atomic_write(a.output,(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode())
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
