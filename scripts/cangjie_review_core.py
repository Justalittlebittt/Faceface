#!/usr/bin/env python3
"""M16.5 private, source-bound full-page review workspace.

Only 127.0.0.1 may serve this data (see cangjie_page_review.py).
A human must explicitly compare the original page image and edit the complete
page text before approving it. A review record proves provenance and an
attestation, not the truth of the human's work. Short V5 anchors do NOT count as
fully transcribed pages.

Data stays outside the public repository in a local, private workspace.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from scripts.cangjie_corpus_stage import SCANS, pdf_pages, verify_page_review

# These fingerprints were measured on the actual 1925 PDFs in M16.2/16.4.
# Do not auto-accept another edition or silently switch scans.
KNOWN_SCAN_SHA256 = {
    "nlc-44091": "466adfaba96be3ba63cab4784b97dd04d1a7e86950601073e27aa6bdffbcc649",
    "nlc-44092": "ce9020bb7d2e404f16689519c0c33df3525e3131b980b02344ed9ed967303ef7",
}
VALID_TYPES = ("text", "text_and_figures", "title_or_verse")
REJECTED_REVIEWERS = {"auto", "ocr", "agent", "bot", "model", "anonymous"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    """Write beside target and rename. If power is lost, review fails closed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".review-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class ReviewWorkspace:
    def __init__(
        self, scan_dir: Path, ocr_dir: Path, reviewed_dir: Path,
        expected_hashes: dict[str, str] | None = None,
        draft_dir: Path | None = None
    ) -> None:
        self.scan_dir, self.ocr_dir, self.reviewed_dir = (
            Path(scan_dir), Path(ocr_dir), Path(reviewed_dir)
        )
        self.draft_dir = Path(draft_dir) if draft_dir is not None else self.reviewed_dir.parent / "agent-drafts"
        expected_hashes = KNOWN_SCAN_SHA256 if expected_hashes is None else expected_hashes
        self.sources: dict[str, dict] = {}
        for scan in SCANS:
            source, pdf = scan["id"], self.scan_dir / scan["file"]
            if not pdf.is_file() or pdf_pages(pdf) != scan["expected_pages"]:
                raise ValueError(f"Missing or wrong-length original scan: {pdf}")
            sha = file_sha256(pdf)
            if sha != expected_hashes[source]:
                raise ValueError(
                    f"Wrong scan SHA256 for {source}; expected official 1925 source, got {sha}"
                )
            self.sources[source] = {
                "source_id": source, "source_url": scan["url"], "pdf": pdf,
                "pdf_sha256": sha, "page_count": scan["expected_pages"],
            }

    def page_paths(self, source: str, index: int) -> dict[str, Path]:
        if source not in self.sources:
            raise ValueError("Unknown source")
        if type(index) is not int or not 0 <= index < self.sources[source]["page_count"]:
            raise ValueError("Page index must be within this original PDF, starting at zero")
        base = f"{index:03d}"
        return {
            "candidate": self.ocr_dir / "transcripts" / source / f"{base}.txt",
            "candidate_meta": self.ocr_dir / "transcripts" / source / f"{base}.ocr.json",
            "reviewed": self.reviewed_dir / source / f"{base}.txt",
            "review_meta": self.reviewed_dir / source / f"{base}.review.json",
            "agent_draft": self.draft_dir / source / f"{base}.draft.txt",
            "agent_draft_meta": self.draft_dir / source / f"{base}.draft.json",
        }

    def _unchanged_source(self, source: str) -> None:
        if file_sha256(self.sources[source]["pdf"]) != self.sources[source]["pdf_sha256"]:
            raise ValueError("Original PDF was modified while review server was running")

    def page_info(self, source: str, index: int) -> dict:
        p = self.page_paths(source, index)
        original = self.sources[source]
        ocr = p["candidate"].read_text(encoding="utf-8") if p["candidate"].is_file() else ""
        ocr_meta = {}
        if p["candidate_meta"].is_file():
            ocr_meta = json.loads(p["candidate_meta"].read_text(encoding="utf-8"))
        candidate_provenance_ok = bool(
            ocr and ocr_meta
            and ocr_meta.get("source_pdf_sha256") == original["pdf_sha256"]
            and ocr_meta.get("pdf_page_zero_based") == index
            and ocr_meta.get("candidate_text_sha256") == file_sha256(p["candidate"])
            and ocr_meta.get("eligible_for_cangjie_verified_corpus") is False
        )
        agent_meta = {}
        agent_text = ""
        draft_available = p["agent_draft"].is_file() and p["agent_draft_meta"].is_file()
        agent_provenance_ok = False
        if draft_available:
            agent_meta = json.loads(p["agent_draft_meta"].read_text(encoding="utf-8"))
            candidate_hash = ocr_meta.get("candidate_text_sha256") if candidate_provenance_ok else None
            agent_provenance_ok = bool(
                agent_meta.get("pipeline") == "m16.6-vision-agent-draft"
                and agent_meta.get("prompt_version") == "m16.6-source-page-vertical-columns-v1"
                and agent_meta.get("source_id") == source
                and agent_meta.get("pdf_page_zero_based") == index
                and agent_meta.get("source_pdf_sha256") == original["pdf_sha256"]
                and agent_meta.get("ocr_candidate_sha256") == candidate_hash
                and agent_meta.get("draft_text_sha256") == file_sha256(p["agent_draft"])
                and agent_meta.get("eligible_for_cangjie_verified_corpus") is False
                and agent_meta.get("human_reviewed") is False
            )
            if agent_provenance_ok:
                agent_text = p["agent_draft"].read_text(encoding="utf-8")
        existing_text = ""
        review = {}
        if p["reviewed"].is_file():
            # Important: stale text or altered review metadata raise, not hide.
            if verify_page_review(p["reviewed"], original["pdf_sha256"], index):
                existing_text = p["reviewed"].read_text(encoding="utf-8")
                review = json.loads(p["review_meta"].read_text(encoding="utf-8"))
        return {
            "source_id": source, "source_url": original["source_url"],
            "pdf_page_zero_based": index, "pdf_page_number_for_display": index + 1,
            "page_count": original["page_count"], "source_pdf_sha256": original["pdf_sha256"],
            "ocr_candidate": ocr if candidate_provenance_ok else "",
            "ocr_candidate_available": bool(ocr),
            "ocr_candidate_provenance_ok": candidate_provenance_ok,
            "ocr_diagnostic": {
                "engine": ocr_meta.get("engine"), "han_char_count": ocr_meta.get("han_char_count"),
                "mean_word_confidence": ocr_meta.get("mean_word_confidence"),
                "text_sha256": ocr_meta.get("candidate_text_sha256") if candidate_provenance_ok else None
            },
            "agent_draft": agent_text,
            "agent_draft_available": draft_available,
            "agent_draft_provenance_ok": agent_provenance_ok,
            "agent_diagnostic": {
                "model": agent_meta.get("model") if agent_provenance_ok else None,
                "page_type": agent_meta.get("page_type") if agent_provenance_ok else None,
                "uncertain_spans": agent_meta.get("uncertain_spans", []) if agent_provenance_ok else [],
                "figure_notes": agent_meta.get("figure_notes", []) if agent_provenance_ok else [],
                "reading_order_notes": agent_meta.get("reading_order_notes", "") if agent_provenance_ok else "",
                "printed_volume_guess": agent_meta.get("printed_volume_guess", "") if agent_provenance_ok else "",
                "section_guess": agent_meta.get("section_guess", "") if agent_provenance_ok else ""
            },
            "reviewed_text": existing_text,
            "is_reviewed_full_page": bool(existing_text),
            "review": review,
            "note": "A source-linked signoff is a manual attestation, not external proof of accuracy.",
        }

    def save_review(
        self, source: str, index: int, text: str, reviewer: str,
        confirmed_against_image: bool, content_type: str = "text",
        printed_volume: str = "", section: str = "", notes: str = ""
    ) -> dict:
        p = self.page_paths(source, index)
        if confirmed_against_image is not True:
            raise ValueError("Explicit visual comparison against the full original page is required")
        if not isinstance(reviewer, str) or not 2 <= len(reviewer.strip()) <= 80:
            raise ValueError("Reviewer identifier must be 2..80 characters")
        reviewer = reviewer.strip()
        if reviewer.lower() in REJECTED_REVIEWERS:
            raise ValueError("OCR/agent/anonymous cannot claim a human-reviewed page")
        if content_type not in VALID_TYPES:
            raise ValueError("Unknown page type")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 25000:
            raise ValueError("A nonempty, complete-page transcription is required")
        if any(not isinstance(x, str) or len(x) > 2000 for x in (printed_volume, section, notes)):
            raise ValueError("Invalid metadata")
        self._unchanged_source(source)
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"
        content = normalized.encode("utf-8")
        sha = hashlib.sha256(content).hexdigest()
        review = {
            "source_id": source, "source_url": self.sources[source]["source_url"],
            "source_pdf_sha256": self.sources[source]["pdf_sha256"],
            "pdf_page_zero_based": index,
            "page_id": f"{source}:p{index:03d}",
            "reviewed_by": reviewer,
            "confirmed_against_full_original_image": True,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "text_sha256": sha, "content_type": content_type,
            "printed_volume": printed_volume.strip(), "section": section.strip(),
            "notes": notes.strip(),
            "contains_complete_page_transcription_attested_by_reviewer": True,
            "not_an_independent_accuracy_certification": True,
        }
        # Deliberately never overwrite OCR candidate content or source PDF.
        # Hash contract rejects partial, stale, or mismatched reviews.
        atomic_write(p["reviewed"], content)
        atomic_write(
            p["review_meta"],
            (json.dumps(review, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        )
        if not verify_page_review(p["reviewed"], self.sources[source]["pdf_sha256"], index):
            raise RuntimeError("A just-saved review unexpectedly failed validation")
        return review

    def image_path(self, source: str, index: int, dpi: int = 150) -> Path:
        self.page_paths(source, index)
        if dpi not in (120, 150, 200, 250):
            raise ValueError("Unsupported preview resolution")
        self._unchanged_source(source)
        sha = self.sources[source]["pdf_sha256"][:16]
        dest = self.reviewed_dir / "_page-preview-cache" / source / sha / f"{index:03d}-{dpi}.png"
        if dest.is_file() and dest.stat().st_size:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="page-render-") as temp:
            out = Path(temp) / "scan"
            completed = subprocess.run(
                ["pdftoppm", "-f", str(index + 1), "-l", str(index + 1),
                 "-r", str(dpi), "-gray", "-singlefile", "-png",
                 str(self.sources[source]["pdf"]), str(out)],
                capture_output=True, text=True, timeout=60
            )
            tmp_image = out.with_suffix(".png")
            if completed.returncode or not tmp_image.is_file() or not tmp_image.stat().st_size:
                raise RuntimeError("Unable to render source page using pdftoppm")
            atomic_write(dest, tmp_image.read_bytes())
        return dest

    def summary(self) -> dict:
        counts = {"full_page_reviewed": 0, "ocr_candidate_available": 0,
                  "ocr_provenance_ok": 0, "unreviewed_or_missing": 0,
                  "agent_draft_available": 0, "agent_draft_provenance_ok": 0}
        for source, info in self.sources.items():
            for index in range(info["page_count"]):
                p = self.page_paths(source, index)
                if p["candidate"].is_file():
                    counts["ocr_candidate_available"] += 1
                    meta = p["candidate_meta"]
                    if meta.is_file():
                        m = json.loads(meta.read_text(encoding="utf-8"))
                        if (m.get("source_pdf_sha256") == info["pdf_sha256"]
                            and m.get("pdf_page_zero_based") == index
                            and m.get("candidate_text_sha256") == file_sha256(p["candidate"])):
                            counts["ocr_provenance_ok"] += 1
                if p["agent_draft"].is_file() and p["agent_draft_meta"].is_file():
                    counts["agent_draft_available"] += 1
                    if self.page_info(source, index)["agent_draft_provenance_ok"]:
                        counts["agent_draft_provenance_ok"] += 1
                if p["reviewed"].is_file() and verify_page_review(
                    p["reviewed"], info["pdf_sha256"], index
                ):
                    counts["full_page_reviewed"] += 1
                else:
                    counts["unreviewed_or_missing"] += 1
        return {
            **counts, "total_original_scan_pages": sum(x["page_count"] for x in self.sources.values()),
            "all_full_pages_reviewed": counts["unreviewed_or_missing"] == 0,
            "cangjie_agent_whole_book_extraction_performed": False,
        }
