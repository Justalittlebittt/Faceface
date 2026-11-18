# Faceface — Traditional Face Reading, Reimagined for the Web

> **Current M16.10 (2026-11-18):** Faceface's user-approved manual-camera shutter, front/profile alignment guidance with green clockwise confirmation and existing cultural reports remain unchanged. The 1925-original-book research mainline has actually OCR'd all **268 scanned pages** and found **922 lexical morphology clues on 205 pages** (M16.9), which are NOT 922 confirmed rules. In M16.10 the assistant visually read 13 short original-image phrases from **six pages across BOTH actual 1925 PDFs**, labelled what the existing browser geometry can and cannot observe, and reran **real PP-OCRv5** on those six PDF images. The exact original-image fragment appeared in the corresponding OCR page **6/13** times, all six within one OCR line. Among those six exact phrase matches only **two** have limited overlap with the existing photographed lip-fullness metric; none has been independently human-proofread as a complete original page. This is an anchor-retrieval DIAGNOSTIC, not character error rate, original-image human certification or the precision of the 922 prior lexical hits. The 35 real Cangjie semantic small-model role trials in M16.8 still produced zero accepted source-grounded semantic units and were NOT merged. All long OCR text and research candidate snippets stay private; the public repo publishes only short preliminary original excerpts with caveats and metadata-only test evidence. Official whole-book Adler and five semantic extractor distillation remain incomplete.

**项目定位（中文）**：Faceface 是一款面向国际用户的免费、手机优先的传统面相文化解读网站。用户使用浏览器摄像头实时拍摄正脸，按需补拍可见耳部；系统将可观察的面部形态转为结构化、可读的描述，并与《麻衣相法》（历史版本有时称《麻衣神相》）及《易传·说卦》的传统取象知识关联，生成**简洁版报告**与**详细版报告**。报告包含历史相术观点、生活情境与可执行的人生启发。它不是科学人格诊断，也不是命运事实预测。

**Key experience:** live browser camera → model follows your actual face outline (no small fixed oval) → keep your face steady while a green line travels clockwise around it for 3 seconds → **tap the manual shutter** (never automatic capture) → browser-only face description → source-linked reading → user-initiated local save. Optional side-profile SVG is a visual preview only; analysis remains front-facing.

## Product decisions (approved)

- **Platform:** international website (responsive Web/PWA candidate), **not** WeChat Mini Program.
- **Camera:** use the live front-facing camera, never require gallery upload as the main flow. Ears may be captured via guided supplemental views if obscured; allow skip.
- **Privacy-by-design:** intended on-device inference and rule matching. Do not upload or retain face photos, landmarks, or reports by default. User explicitly saves their own report. Public claims must be backed by network/implementation audits; analytics and ads require separate disclosure.
- **User experience:** no personality confirmation questionnaire. Default **concise** report emphasizes traditional interpretations, practical behavior scenarios, and actionable advice. **Detailed** report exposes observations, source passages, conditions, and limits. Both free.
- **Knowledge:** build a complete, version-pinned 《麻衣相法》 source archive; use [cangjie-skill](https://github.com/kangarooking/cangjie-skill) to *assist* extraction/validation, not as a substitute for complete source preservation.
- **Interpretation:** integrate I Ching / Yijing **Eight Trigrams imagery** into relevant face-feature explanations; **no independent divination/hexagram-casting flow**. Do not invent rules such as “larger eyes mean stronger fire.”
- **Scientific boundary:** visible morphology does not establish personality, moral character, life events, or health; traditional claims must be attributed as historical beliefs. Suggestions are reflective rather than diagnostic.
- **Monetization intent:** free product supported by ads *if feasible and compliant*; no ads in camera capture; consent/privacy requirements for third-party advertising remain to be assessed.
- **Development status:** [M16.10 PR #32](https://github.com/Justalittlebittt/Faceface/pull/32) adds [13 source-image anchor pilot entries](research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json), [11 original-page topical visual checks](research/M16_10_ORIGINAL_PAGE_SPOTCHECK_LEDGER.json), and a [real six-page PaddleOCR phrase-recall action](https://github.com/Justalittlebittt/Faceface/actions/runs/44243091232): **6 of 13 preliminary image-read short phrases had exact same-page/same-line OCR matches**. [M16.10 result ledger](research/M16_10_REAL_ORIGINAL_PHRASE_PROBE_RESULTS.json) records matched/not-matched page anchors and clear limitations. Next: target missed high-value source lines with crop/vertical reading-order OCR, check the original scan image phrase-by-phrase, and only then use semantics/geometry where genuinely observable. No new live historical cards or camera changes.

## Start here

| File | What it answers |
| --- | --- |
| [docs/STATUS.md](docs/STATUS.md) | What is done, what is unverified, what is missing |
| [docs/PRODUCT.md](docs/PRODUCT.md) | End-to-end customer experience, concise/detailed report, scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Milestones, prioritization, measurable acceptance gates |
| [docs/WEB_ARCHITECTURE.md](docs/WEB_ARCHITECTURE.md) | Web-first, mobile browser, camera, on-device processing |
| [docs/KNOWLEDGE_BASE.md](docs/KNOWLEDGE_BASE.md) | Full-book collection, Cangjie role, face-description ontology, matching |
| [docs/PRIVACY_AND_LAUNCH.md](docs/PRIVACY_AND_LAUNCH.md) | Privacy promises, auditable evidence, region-aware launch |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Confirmed decisions and explicitly unresolved choices |

## Run the M1 experiment locally

```bash
npm install
npm run dev
npm run build
npm test
```

The UI requests browser camera permission on a secure origin (localhost or HTTPS). The first analysis downloads version-pinned WASM and a public Google-hosted model; the input frame is processed in an in-memory canvas. The app defaults to **English with an immediate Chinese toggle**, and now shows **experimental geometric observations and a small, traceable classical-text reference section in both languages**. Original Chinese excerpts remain available alongside explicitly qualified English explanatory glosses. The ancient observations are partial/insufficient correlations, not authenticated automatic traditional face-type verdicts. See [docs/M1_IMPLEMENTATION.md](docs/M1_IMPLEMENTATION.md) for exact implementation and remaining verification.

## Current top priority

**Live HTTPS test site:** https://justalittlebittt.github.io/Faceface/ — GitHub Actions deployed the site and independently verified HTTP responses for the homepage and privacy page ([deployment and verification](https://github.com/Justalittlebittt/Faceface/actions/runs/43397158717)). **Next:** independently validate real iOS Safari and Android Chrome camera permissions, local processing, report download and privacy requests/storage using willing participants; assess real-world repeatability without uploading face photos. Expand source-checked cultural coverage in **other facial regions**, prioritizing observable conditions and original scan pages over more mouth-only vocabulary. Browser integration still uses a single public portrait and does not establish population accuracy; full-book archival continues separately.

### Repository scope

The repository contains the project's **canonical planning/handoff documents plus experimental M1 Web source code**. Legacy V0.x–V2.8 research packages are referenced by status but have not been automatically imported or declared validated. Future source-data imports require provenance and acceptance.

CI verification: [PR #4](https://github.com/Justalittlebittt/Faceface/pull/4) (first source-linked reports), [PR #5](https://github.com/Justalittlebittt/Faceface/pull/5) (HTTPS test-site pipeline; Pages now enabled), [PR #6](https://github.com/Justalittlebittt/Faceface/pull/6) (WebKit file fallback), [PR #7](https://github.com/Justalittlebittt/Faceface/pull/7) (geometry boundary stability), [PR #8](https://github.com/Justalittlebittt/Faceface/pull/8) (English-first UI, Chinese toggle), [PR #9](https://github.com/Justalittlebittt/Faceface/pull/9) (eight descriptors, conditional historical associations), [PR #10](https://github.com/Justalittlebittt/Faceface/pull/10) (mouth-corner shape and Five Mountains/Four Rivers context), [PR #11](https://github.com/Justalittlebittt/Faceface/pull/11) (lip visibility and multi-condition matches), [PR #12](https://github.com/Justalittlebittt/Faceface/pull/12) (focused cultural summary and complete evidence panel), [PR #13](https://github.com/Justalittlebittt/Faceface/pull/13) (1925 scan-verified face, nose and chin sources), [PR #14](https://github.com/Justalittlebittt/Faceface/pull/14) (14-run public-image reproducibility suite), [PR #15](https://github.com/Justalittlebittt/Faceface/pull/15) (private two-photo check), [PR #16](https://github.com/Justalittlebittt/Faceface/pull/16) (first fixed SVG camera guide), [PR #17](https://github.com/Justalittlebittt/Faceface/pull/17) (user-approved clockwise green face contour), [PR #18](https://github.com/Justalittlebittt/Faceface/pull/18) (borderline source-match safeguard plus scan-verified volume-one Three Sections photo-study; 61/61 tests, [real-model checks](https://github.com/Justalittlebittt/Faceface/actions/runs/44023255670), [HTTPS deployment](https://github.com/Justalittlebittt/Faceface/actions/runs/44023589921)).

**Last updated:** 2026-11-17.
