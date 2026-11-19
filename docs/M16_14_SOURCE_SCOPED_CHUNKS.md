# M16.14 — short original ROI → source-scoped Cangjie research chunks

This stage formats the *private output* of M16.13 into a page-bound Markdown research file that can be handed to the pinned official Cangjie extractors after source review. It is **NOT** verified complete-page text, whole-book distillation, an actual five-extractor run, or approval for a website rule.

## Run locally (Windows, from repository root)

First create and manually verify a real short-source ROI record using the M16.12 review flow. Prepare the signed input with M16.13:

```powershell
python -m scripts.cangjie_signed_roi_input --private-root C:/faceface-corpus/private --out C:/faceface-corpus/private/short-rois.json

python -m scripts.cangjie_source_scoped_chunks --private-root C:/faceface-corpus/private --input C:/faceface-corpus/private/short-rois.json --output C:/faceface-corpus/private/source-scoped-rois.md --audit C:/faceface-corpus/private/source-scoped-rois.audit.json
```

If there are zero signed reviews, this generates a correctly marked **empty** source batch; no semantics can legitimately be extracted from it. If a quote, source SHA, page index, or status changes, the input is rejected. The original signed ROI records and their image hashes are checked at the previous stage, not cryptographically reauthenticated by this Markdown formatter. Both steps must run in order. All text, source crops and outputs stay in the private root.

The output explicitly keeps each target ID, PDF source ID, zero-based page, PDF SHA, historical quote and SHA. It asks later extraction to distinguish visible morphology from the traditional interpretation, mark absent conditions and keep all derived claims as research candidates. **No actual Cangjie calls occur here.**

## Real-world bottleneck

Current documented genuine human review records remain **0**. A human must physically compare at least one p086/p027 source ROI with its 1925 PDF, correct reading order and actual Chinese characters, and create a signed short-ROI record. Source signatures are reviewer attestations, not independently proven accuracy; source review should be independently spot-checked. Only after that does it make sense to use official pinned Cangjie five-extractor instructions on the small verified passage, and only to produce unapproved candidates. No automated camera/report rules are changed in this milestone.
