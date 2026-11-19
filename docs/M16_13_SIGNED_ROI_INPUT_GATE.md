# M16.13 | Private signed short-ROI to Cangjie input gate

This milestone creates a **research input gate**, not a completed Cangjie extraction or a new online interpretation.

## Why

M16.12 ran real PP-OCRv5 on four ancient source columns and retrieved 0/3 exact target phrases. Its short-ROI review tool allows a human to check the original scan and attest a limited phrase; it does not prove a whole page is reviewed. Continuing blind OCR parameter sweeps is not the default plan.

## Usage (Windows, repository root)

First generate the original source crops using the M16.12 instructions and inspect them against the pinned 1925 PDF. If and only if a real human has checked a short ROI, use the existing `scripts.cangjie_source_short_review` command to make its private signed review record.

Then run:

```powershell
python -m scripts.cangjie_signed_roi_input --private-root C:/faceface-corpus/private --out C:/faceface-corpus/private/cangjie-short-roi-input.json
python -m unittest tests.test_cangjie_signed_roi_input
```

This command reads only short ROI records and original crop PNGs from the private root; it **does not** read the entire book, run the official five extractors or invoke a model. It verifies pinned source PDF SHA metadata, exact page and target ID, quote SHA and crop file SHA, required human-attestation fields, and observable-morphology classification. Unreviewed, uncertain, figure-only, historical-assertion, altered or missing evidence is separately counted as not admitted.

**Boundary:** A reviewer name and hash trail are reproducible attestations, not independent proof that the reviewer truly inspected the source or transcribed correctly. The underlying source PDF is originally verified by the M16.12 cropping workflow; this exporter checks the signed provenance and unchanged crop hashes, but must not be called a second independent PDF verification. For true source quality, another person should check each selected crop against the original page before any production rule approval.

The JSON output with exact original quotes is **local/private**. Do not commit it to GitHub, upload original scanned pages or send it to an unrelated public API. When approved inputs exist, they can be passed to the **pinned official Cangjie extractor workflow** as a small source-scoped morphology research test, with extraction outputs explicitly marked as unverified candidate analyses until reviewed.

## Acceptance/status

- 268/268 scan pages inventoried; **0/268 complete pages signed as human reviewed**.
- In the last verified M16.12 run, **0/3 exact local OCR target phrases retrieved**.
- No genuine human signed short ROI was available in GitHub when this change was written; exporter must therefore return 0 admitted inputs when private review records are absent.
- This PR does not run the local 4B model, official five Cangjie extractors, change photo descriptors, modify camera flow or create live interpretation rules.
- Next real evidence gate: have a human independently verify a specific source crop and its text, generate a private signed ROI, then feed the verified short-ROI input to the pinned official Cangjie extraction pipeline; preserve both successful and rejected outputs and source IDs.
