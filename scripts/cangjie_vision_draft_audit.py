#!/usr/bin/env python3
"""M16.6: inspect real local AI drafts and prioritize ORIGINAL-PAGE review.

This is a metadata-only triage, never a source-truth certification.
It cannot approve original transcription or claim full-page CER.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from scripts.cangjie_review_core import ReviewWorkspace
from scripts.cangjie_vision_agent_batch import DEFAULT_MODEL, draft_valid, draft_paths, selected_pages
from scripts.cangjie_ocr_benchmark import reference_anchors, anchor_probe


RISK_PAGE_TYPES = {"figure_only", "blank", "damaged", "text_and_figures"}


def audit(workspace: ReviewWorkspace, draft_dir: Path,
          catalog: dict, model: str) -> dict:
    all_pages=selected_pages(workspace)
    by_source={sid:reference_anchors(catalog,sid) for sid in workspace.sources}
    states=Counter()
    types=Counter()
    priority=[]
    anchored_page_count=0
    found_anchors=0
    checked_anchor_count=0
    all_anchor_count=sum(
        len(phrases) for per_page in by_source.values() for phrases in per_page.values()
    )
    for sid,index in all_pages:
        info=workspace.page_info(sid,index)
        page_id=f"{sid}:p{index:03d}"
        if info["is_reviewed_full_page"]:
            states["human_reviewed"]+=1
            continue
        txt,meta_file=draft_paths(draft_dir,sid,index)
        if not txt.exists() or not meta_file.exists():
            states["missing_agent_draft"]+=1
            continue
        if not draft_valid(workspace,draft_dir,sid,index,model):
            states["invalid_or_stale_agent_draft"]+=1
            priority.append({"page_id":page_id,"priority":"blocked",
                             "reason":"source or model/OCR hash mismatch"})
            continue
        states["valid_unreviewed_agent_draft"]+=1
        meta=json.loads(meta_file.read_text(encoding="utf-8"))
        kind=meta["page_type"]
        types[kind]+=1
        reasons=[]
        if kind in RISK_PAGE_TYPES:
            reasons.append("nonstandard_layout_or_nontext_page")
        if meta["uncertain_spans"]:
            reasons.append("uncertain_characters")
        if meta["figure_notes"]:
            reasons.append("figure_annotations")
        if not info["ocr_candidate_provenance_ok"]:
            reasons.append("no_source_matched_ocr_crosscheck")
        if reasons:
            priority.append({"page_id":page_id,"priority":"needs_image_review",
                             "reason":",".join(reasons),
                             "page_type":kind,
                             "uncertain_span_count":len(meta["uncertain_spans"])})
        references=by_source[sid].get(index,[])
        if references:
            anchored_page_count+=1
            probe=anchor_probe(txt.read_text(encoding="utf-8"),references)
            checked_anchor_count+=probe["reference_phrase_count"]
            found_anchors+=probe["exact_phrase_count"]
    result={
        "kind":"M16.6_PRIVATE_AGENT_DRAFT_TRIAGE_NOT_HUMAN_SOURCE_REVIEW",
        "original_pdf_pages":len(all_pages),
        "model":model,
        "states":dict(states),
        "agent_draft_page_types":dict(types),
        "source_checked_reference_anchor_total":all_anchor_count,
        "pages_with_source_anchor_and_valid_agent_draft":anchored_page_count,
        "reference_anchors_on_scored_draft_pages":checked_anchor_count,
        "reference_anchors_found_in_valid_agent_drafts":found_anchors,
        "reference_anchor_metric_is_diagnostic_not_CER":True,
        "priority_review_pages":len(priority),
        "priority":priority,
        "agent_promotions_to_original_reviewed":0,
        "cangjie_five_semantic_agents_executed":False,
        "notice":(
            "Previews, classifications and snippet hits are generated diagnostics only. "
            "Every candidate used for the final knowledge base must satisfy its "
            "own source review contract. Do not call draft coverage source coverage."
        )
    }
    return result


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--ocr-dir",type=Path,required=True)
    p.add_argument("--reviewed-dir",type=Path,required=True)
    p.add_argument("--draft-dir",type=Path,required=True)
    p.add_argument("--model",default=DEFAULT_MODEL)
    p.add_argument("--catalog",type=Path,
                   default=Path("src/knowledge/maiyi-source-checked-v5.json"))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    w=ReviewWorkspace(a.scan_dir,a.ocr_dir,a.reviewed_dir,draft_dir=a.draft_dir)
    catalog=json.loads(a.catalog.read_text(encoding="utf-8"))
    result=audit(w,a.draft_dir,catalog,a.model)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="priority"},ensure_ascii=False))


if __name__=="__main__":
    main()
