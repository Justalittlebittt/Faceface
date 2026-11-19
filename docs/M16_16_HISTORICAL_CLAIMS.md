# M16.16｜形态—传统断语关联档案的可执行合同

## 背景与目标

Faceface 必须忠实保留《麻衣相法》里的传统形貌—财富、寿命、品德、婚姻、事业、家庭等关联，即使当下照片无法观测，或这些内容不适合在对真人的自动报告中输出。**历史文化内容不得因前端暂不能展示而在仓颉加工阶段消失。**

本阶段提供 `scripts/cangjie_historical_claim_ledger.py` 用于验证**私有人工整理/仓颉研究候选台账**。它不是 OCR、不是仓颉模型提取器、不是原典校勘器，且不改动网站报告。

## 数据结构与准入条件

输入 JSON schema: `faceface-historical-claims-v1`，含 `relations: []`。每个关联必须提供：

- `relation_id` 与 `source_passage_id`，以及固定底本 `edition_id`；
- `source_id` / `source_pdf_sha256` / `pdf_page_zero_based`；
- `quote_original`、`quote_sha256`；
- `transcription_review_status`（`source_unverified`、`human_attested_short_roi`、`human_reviewed_full_page`），属于**声明字段**，不证明真正核读；
- `morphology_original`、`historical_claim_original`（至少一个非空）及 `traditional_relation_type`：`explicit_in_source`、`contextual`、`ambiguous`、`not_linked`；明确原文直接关联必须两侧均有内容；
- `conditions_original`、`exception_original`、`context_original` 可为空；不能为追求完整而编造原书条件；
- `historical_claim_domains`：`wealth` / `longevity` / `moral_character` / `temperament` / `marriage` / `family` / `offspring` / `career` / `social_status` / `fortune` / `health` / `other` / `none`；
- `photo_observability`：`measurable`、`partial`、`unavailable`、`unknown`；
- `report_eligibility`：`archive_only`、`research_candidate`、`source_reference_only`；
- `conflicting_sources: []`、可选 `modern_explanation`，及必须为 false 的 `eligible_for_Faceface_live_rules` 和 `claims_real_person_outcome`。

未校勘来源只可 `archive_only`；缺失断语的原文片段须将领域设为 `none`。每条原文有SHA核查、每个来源有底本页码及PDF SHA，输出统计区分财富、寿命、品德等领域，不把这些历史观点当作科学认可的现实人格或命运预测。

## 本地执行

```powershell
python -m scripts.cangjie_historical_claim_ledger --input C:/faceface-corpus/private/historical-relations.json --audit-output C:/faceface-corpus/private/historical-relations.audit.json
python -m unittest tests.test_cangjie_historical_claim_ledger
```

输入文件必须由源文审核或明确标为未审核的提取流程产生。**当前并无新增人工签认的真实关系资料**；CI仅以虚构测试语句检测准入逻辑，绝不将其当作原典论断或仓颉提取成果。此工具也不能认证签名是否真实、完整页是否真的被校过；后续需要衔接M16.12–M16.14的独立校勘凭据。

## 验收口径

保存未可观测的古籍断语；来源状态、历史断语领域、照片可用性、报告发布资格必须分开；未核对文本不能自动升格；统计仅反映已入档条目，**不能用它声称全书历史断语覆盖率已经达标**。零新真人预测、零新增运行规则、零新增正式已核对原文。
