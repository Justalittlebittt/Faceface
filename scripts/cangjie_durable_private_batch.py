#!/usr/bin/env python3
"""M16.25: durable local-private 1925 scan -> OCR -> Cangjie -> image review.

No user face data; no external upload. This orchestrator REQUIRES a persistent
directory outside the public Faceface repository and refuses to overwrite a
completed source. Explicit --resume verifies existing intermediate evidence.

A successful batch creates unreviewed OCR research candidates and a local image
review packet, NOT historical facts, signed original transcriptions, or live
Faceface rules. The official Cangjie extractors are still prompt-guided only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.cangjie_corpus_stage import SCANS
from scripts.cangjie_review_core import KNOWN_SCAN_SHA256, ReviewWorkspace, atomic_write, file_sha256
from scripts.cangjie_paddleocr_candidates import batch as run_original_ocr
from scripts.cangjie_outcome_ocr_audit import audit_shard
from scripts.cangjie_semantic_batch_plan import plan_private_shard
from scripts.cangjie_private_ocr_semantic_batch import run_private_batch, read_private_cues
from scripts.cangjie_private_review_pack import assemble_review_items, build_pack

STAGES = ("ocr", "lexical", "selected", "inferred", "review_pack")
VERSION = "M16.25_PERSISTENT_PRIVATE_ORIGINAL_CANGJIE_RESEARCH_V1"


def canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def private_paths(root: Path, source: str, first: int, last: int) -> dict[str, Path]:
    stem = f"{source}-p{first:03d}-{last:03d}"
    return {
        "manifest":root/"batch-manifest.json",
        "ocr_report":root/"private"/"ocr"/"reports"/f"{stem}.json",
        "ocr_root":root/"private"/"ocr",
        "lexical":root/"private"/"lexical"/f"{stem}.jsonl",
        "lexical_report":root/"metadata"/f"lexical-{stem}.json",
        "selected":root/"private"/"selected"/f"{stem}.jsonl",
        "selection_report":root/"metadata"/f"selection-{stem}.json",
        "model":root/"private"/"semantic"/f"{stem}.json",
        "model_report":root/"metadata"/f"semantic-{stem}.json",
        "review_pack":root/"private"/"review-packets"/stem,
    }


def verify_scope(root: Path, scan_dir: Path, source: str, first: int, last: int,
                 max_cues: int, dpi: int, resume: bool) -> dict:
    root = root.resolve()
    repo_root = Path(__file__).resolve().parents[1]
    if root == repo_root or root.is_relative_to(repo_root):
        raise ValueError("Private OCR/model data must be OUTSIDE public Git repository")
    if source not in KNOWN_SCAN_SHA256:
        raise ValueError("Unknown original scan")
    source_meta = next(x for x in SCANS if x["id"] == source)
    if (type(first) is not int or type(last) is not int
        or not 0 <= first <= last < source_meta["expected_pages"]
        or type(max_cues) is not int or max_cues < 1
        or dpi not in (120,150,170,200,220)):
        raise ValueError("Invalid original PDF pages, DPI or bounded model budget")
    # The ReviewWorkspace checks both source PDFs, actual lengths and SHA256s.
    scans = ReviewWorkspace(scan_dir, root/"private"/"_no_external_ocr",
                            root/"private"/"_no_external_reviews")
    if resume and not root.is_dir():
        raise ValueError("Cannot resume a missing persistent private workspace")
    if not resume and root.exists():
        raise ValueError("Private batch workspace already exists; use --resume")
    return {
        "kind": VERSION, "source": source, "start": first, "end": last,
        "max_cues": max_cues, "dpi": dpi,
        "original_source_SHA256": dict(KNOWN_SCAN_SHA256),
        "source_scans_validated": True,
        "human_original_page_reviews": 0, "new_live_rules": 0,
    }


def read_manifest(path: Path, config: dict) -> dict:
    existing = json.loads(path.read_text(encoding="utf-8"))
    if existing.get("config") != config:
        raise ValueError("Workspace parameters/source scans do not match saved manifest")
    if existing.get("kind") != VERSION:
        raise ValueError("Unrecognized private workspace manifest")
    records = existing.get("completed")
    if not isinstance(records, dict) or not set(records).issubset(STAGES):
        raise ValueError("Invalid persisted stage manifest")
    if list(records) != list(STAGES[:len(records)]):
        raise ValueError("Completed stages must be contiguous")
    return existing


def stage_files(stage: str, paths: dict[str, Path]) -> list[Path]:
    by_stage = {
        "ocr":[paths["ocr_report"]],
        "lexical":[paths["lexical"],paths["lexical_report"]],
        "selected":[paths["selected"],paths["selection_report"]],
        "inferred":[paths["model"],paths["model_report"]],
        "review_pack":[paths["review_pack"]/"private-OCR-model-evidence.json",
                       paths["review_pack"]/"private-review-decisions.json",
                       paths["review_pack"]/"private-pack-manifest.json",
                       paths["review_pack"]/"index.html"],
    }
    return by_stage[stage]


def stage_file_hashes(stage: str, paths: dict[str, Path]) -> dict[str, str]:
    result={}
    for p in stage_files(stage, paths):
        if not p.is_file():
            raise ValueError(f"Missing private stage evidence: {p.name}")
        result[p.relative_to(paths["manifest"].parent).as_posix()] = file_sha256(p)
    if stage == "ocr":
        report = json.loads(paths["ocr_report"].read_text(encoding="utf-8"))
        for page in report["pages"]:
            sid,index=page["source_id"],page["pdf_page_zero_based"]
            meta=paths["ocr_root"]/"transcripts"/sid/f"{index:03d}.ocr.json"
            result[meta.relative_to(paths["manifest"].parent).as_posix()]=file_sha256(meta)
            candidate=meta.parent/f"{index:03d}.txt"
            if page["state"]=="ocr_candidate":
                result[candidate.relative_to(paths["manifest"].parent).as_posix()]=file_sha256(candidate)
            elif candidate.exists():
                raise ValueError("Unexpected OCR text file on empty source page")
    if stage == "review_pack":
        for p in sorted((paths["review_pack"]/"pages").glob("*.png")):
            result[p.relative_to(paths["manifest"].parent).as_posix()]=file_sha256(p)
        if not any(x.endswith(".png") for x in result):
            raise ValueError("No actual original scan images in workpack")
    return result


def verify_saved_stage(stage: str, paths: dict[str, Path], expected: dict[str, str]) -> None:
    if not isinstance(expected, dict) or not expected:
        raise ValueError("Saved stage has no digest record")
    actual=stage_file_hashes(stage,paths)
    if actual != expected:
        raise ValueError(f"PRIVATE EVIDENCE CHANGED for {stage}; refusing silent re-run")


def recover_complete_uncommitted_stage(stage: str, paths: dict[str, Path],
                                        config: dict) -> dict[str, str] | None:
    """Reattach fully written private data after crash before manifest commit.

    Never guess partial outputs or rerun a finished private model completion.
    Structural integrity is not OCR accuracy or historical validity.
    """
    files = stage_files(stage, paths)
    present = [p.exists() for p in files]
    if not any(present):
        return None
    if not all(present):
        raise ValueError(f"PARTIAL PRIVATE STAGE {stage}; manual recovery required; no overwrites")
    digests = stage_file_hashes(stage, paths)
    if stage == "ocr":
        report = json.loads(paths["ocr_report"].read_text(encoding="utf-8"))
        if (report.get("source_id") != config["source"]
            or report.get("first_pdf_page_zero_based") != config["start"]
            or report.get("last_pdf_page_zero_based") != config["end"]
            or report.get("processed_pages") != config["end"]-config["start"]+1
            or report.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[config["source"]]):
            raise ValueError("OCR stage cannot be recovered with changed original source")
    elif stage == "lexical":
        audit = json.loads(paths["lexical_report"].read_text(encoding="utf-8"))
        if (audit.get("source_id") != config["source"]
            or audit.get("first_pdf_page_zero_based") != config["start"]
            or audit.get("last_pdf_page_zero_based") != config["end"]
            or audit.get("source_pdf_sha256") != KNOWN_SCAN_SHA256[config["source"]]):
            raise ValueError("Cannot recover altered OCR lexical scope")
        read_private_cues([paths["lexical"]])
    elif stage == "selected":
        entries, _ = read_private_cues([paths["selected"]])
        stats = json.loads(paths["selection_report"].read_text(encoding="utf-8"))
        if not entries or len(entries) != stats.get("private_cues_selected_for_model"):
            raise ValueError("Incomplete private selection stage")
    elif stage == "inferred":
        record = json.loads(paths["model"].read_text(encoding="utf-8"))
        entries, _ = assemble_review_items(record)
        public = json.loads(paths["model_report"].read_text(encoding="utf-8"))
        if (public.get("selected_private_OCR_cues") != len(entries)
            or public.get("real_model_requests_attempted") != len(entries)):
            raise ValueError("Private model and metadata disagree")
    elif stage == "review_pack":
        record = json.loads((paths["review_pack"]/"private-pack-manifest.json").read_text(encoding="utf-8"))
        if (record.get("schema") != "M16.24_PRIVATE_ORIGINAL_PAGE_REVIEW_PACK_V1"
            or record.get("real_original_PDF_images_rendered") < 1
            or record.get("human_full_page_reviews_by_this_build") != 0):
            raise ValueError("Incorrect private review packet state")
    return digests


def run_persistent_batch(root: Path, scan_dir: Path, upstream: Path,
                         source: str, first: int, last: int,
                         max_cues: int=8, dpi: int=170,
                         resume: bool=False,
                         model: str="qwen3:4b-instruct") -> dict:
    root=root.resolve()
    config=verify_scope(root,scan_dir,source,first,last,max_cues,dpi,resume)
    config["model"]=model
    paths=private_paths(root,source,first,last)
    if resume:
        manifest=read_manifest(paths["manifest"],config)
    else:
        root.mkdir(parents=True)
        manifest={"kind":VERSION,"config":config,"completed":{}}
        atomic_write(paths["manifest"],canonical_bytes(manifest))
    saved=manifest["completed"]
    for stage in STAGES:
        if stage in saved:
            verify_saved_stage(stage,paths,saved[stage])
            print(json.dumps({"stage":stage,"status":"verified_existing_private_evidence"}),flush=True)
            continue
        recovered = recover_complete_uncommitted_stage(stage,paths,config)
        if recovered is not None:
            saved[stage]=recovered
            atomic_write(paths["manifest"],canonical_bytes(manifest))
            print(json.dumps({"stage":stage,"status":"reattached_complete_private_evidence"}),flush=True)
            continue
        if stage=="ocr":
            run_original_ocr(scan_dir,paths["ocr_root"],source,first,last,dpi)
        elif stage=="lexical":
            audit_shard(scan_dir,paths["ocr_root"],paths["lexical"].parent,
                        paths["lexical_report"].parent,source,first,last)
        elif stage=="selected":
            rows, selection=plan_private_shard([paths["lexical"]],max_cues)
            atomic_write(paths["selected"],
                         ("\n".join(json.dumps(x,ensure_ascii=False) for x in rows)+"\n").encode())
            atomic_write(paths["selection_report"],canonical_bytes(selection))
        elif stage=="inferred":
            run_private_batch([paths["selected"]],scan_dir,upstream,
                              paths["model"],paths["model_report"],0,model_name=model)
        elif stage=="review_pack":
            build_pack(paths["model"],scan_dir,paths["review_pack"])
        else:
            raise AssertionError("Unknown stage")
        digests=stage_file_hashes(stage,paths)
        saved[stage]=digests
        atomic_write(paths["manifest"],canonical_bytes(manifest))
        print(json.dumps({"stage":stage,"status":"persisted_private_evidence",
                          "file_count":len(digests)}),flush=True)
    model_meta=json.loads(paths["model_report"].read_text(encoding="utf-8"))
    pack=json.loads((paths["review_pack"]/"private-pack-manifest.json").read_text(encoding="utf-8"))
    if (model_meta["selected_private_OCR_cues"]!=pack["source_count"]
        or model_meta["OCR_literal_draft_relations"]!=pack["literal_OCR_model_drafts"]
        or model_meta["new_live_Faceface_rules"]!=0
        or pack["verified_historical_relations"]!=0):
        raise ValueError("Private OCR model and review pack source count mismatch")
    report={
        "schema":VERSION,
        "original_scan_source":source,
        "original_pages_ocr_processed":last-first+1,
        "actual_Qwen_requests":model_meta["real_model_requests_attempted"],
        "unverified_model_OCR_literal_drafts":model_meta["OCR_literal_draft_relations"],
        "private_original_page_images_rendered":pack["real_original_PDF_images_rendered"],
        "source_human_verified_pages":0,
        "verified_historical_claims":0,
        "new_live_Faceface_rules":0,
        "private_storage_retained_in_local_workspace":True,
        "private_content_must_not_be_uploaded_to_public_GitHub":True,
        "full_five_Cangjie_extractor_pipeline_executed":False,
    }
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",type=Path,required=True,
                   help="New local/private durable directory outside Git repository")
    p.add_argument("--scan-dir",type=Path,required=True)
    p.add_argument("--upstream",type=Path,required=True,
                   help="Pinned official Cangjie checkout")
    p.add_argument("--source",choices=list(KNOWN_SCAN_SHA256),required=True)
    p.add_argument("--start",type=int,required=True)
    p.add_argument("--end",type=int,required=True)
    p.add_argument("--max-cues",type=int,default=8)
    p.add_argument("--dpi",type=int,default=170)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--model",default="qwen3:4b-instruct")
    a=p.parse_args()
    run_persistent_batch(a.workspace,a.scan_dir,a.upstream,a.source,
                         a.start,a.end,a.max_cues,a.dpi,a.resume,a.model)


if __name__=="__main__":
    main()
