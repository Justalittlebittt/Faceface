# Faceface — Traditional Face Reading, Reimagined for the Web

> **Project phase: M1 browser inference and an M2 limited source-linked cultural report have passed GitHub CI and a real Chromium MediaPipe integration test.** This is **not yet a verified iOS/Android product or a full classical face-reading engine**.

**项目定位（中文）**：Faceface 是一款面向国际用户的免费、手机优先的传统面相文化解读网站。用户使用浏览器摄像头实时拍摄正脸，按需补拍可见耳部；系统将可观察的面部形态转为结构化、可读的描述，并与《麻衣相法》（历史版本有时称《麻衣神相》）及《易传·说卦》的传统取象知识关联，生成**简洁版报告**与**详细版报告**。报告包含历史相术观点、生活情境与可执行的人生启发。它不是科学人格诊断，也不是命运事实预测。

**Key experience:** live browser camera → face description → classical-source matching → concise practical reading → detailed references → user-initiated local save.

## Product decisions (approved)

- **Platform:** international website (responsive Web/PWA candidate), **not** WeChat Mini Program.
- **Camera:** use the live front-facing camera, never require gallery upload as the main flow. Ears may be captured via guided supplemental views if obscured; allow skip.
- **Privacy-by-design:** intended on-device inference and rule matching. Do not upload or retain face photos, landmarks, or reports by default. User explicitly saves their own report. Public claims must be backed by network/implementation audits; analytics and ads require separate disclosure.
- **User experience:** no personality confirmation questionnaire. Default **concise** report emphasizes traditional interpretations, practical behavior scenarios, and actionable advice. **Detailed** report exposes observations, source passages, conditions, and limits. Both free.
- **Knowledge:** build a complete, version-pinned 《麻衣相法》 source archive; use [cangjie-skill](https://github.com/kangarooking/cangjie-skill) to *assist* extraction/validation, not as a substitute for complete source preservation.
- **Interpretation:** integrate I Ching / Yijing **Eight Trigrams imagery** into relevant face-feature explanations; **no independent divination/hexagram-casting flow**. Do not invent rules such as “larger eyes mean stronger fire.”
- **Scientific boundary:** visible morphology does not establish personality, moral character, life events, or health; traditional claims must be attributed as historical beliefs. Suggestions are reflective rather than diagnostic.
- **Monetization intent:** free product supported by ads *if feasible and compliant*; no ads in camera capture; consent/privacy requirements for third-party advertising remain to be assessed.
- **Development status:** Real MediaPipe inference in Chromium now leads to five observed regions, two partial historical references plus an insufficient nose-bridge reference, a concise/detailed source-linked report, and a locally downloadable text report. CI reports 15/15 geometry + source/report tests passing. This M2 seed is explicitly NOT a validated traditional face-type judgment; real Android/iOS camera tests, diverse-sample calibration, full classical rules, and privacy audits remain open. Historical ZIP prototypes remain outside this repository.

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

The UI requests browser camera permission on a secure origin (localhost or HTTPS). The first analysis downloads version-pinned WASM and a public Google-hosted model; the input frame is processed in an in-memory canvas. The app now shows **experimental geometric observations and a small, traceable classical-text reference section**. The ancient observations are partial/insufficient correlations, not authenticated automatic traditional face-type verdicts. See [docs/M1_IMPLEMENTATION.md](docs/M1_IMPLEMENTATION.md) for exact implementation and remaining verification.

## Current top priority

**Next:** enable GitHub Pages once via **Settings → Pages → Build and deployment → GitHub Actions** so the existing deploy workflow can publish a real HTTPS mobile test site; then validate iOS Safari and Android Chrome camera permissions and privacy requests/storage. Browser-model integration passes on Chromium camera simulation and WebKit file input only; thresholds remain experimental. Then add source-verifiable multi-condition ancient rules for useful content. A single public portrait passing Chromium does not validate shape thresholds across people. Full-book archival continues in parallel.

### Repository scope

The repository contains the project's **canonical planning/handoff documents plus experimental M1 Web source code**. Legacy V0.x–V2.8 research packages are referenced by status but have not been automatically imported or declared validated. Future source-data imports require provenance and acceptance.

CI verification: [PR #4](https://github.com/Justalittlebittt/Faceface/pull/4) (first source-linked reports), [PR #5](https://github.com/Justalittlebittt/Faceface/pull/5) (HTTPS test-site pipeline; Pages enablement still required), [PR #6](https://github.com/Justalittlebittt/Faceface/pull/6) (WebKit local-photo fallback), [PR #7](https://github.com/Justalittlebittt/Faceface/pull/7) (16/16 tests, cross-engine border labels and correct image orientation).

**Last updated:** 2026-11-13.
