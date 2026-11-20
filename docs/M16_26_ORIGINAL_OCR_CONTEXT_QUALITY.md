# M16.26｜从单行OCR走向可复核的原书上下文

## 问题与路线

M16.25已实际证明：7页1925年《麻衣相法》PDF的PP-OCRv5、3次官方仓颉提示引导的Qwen3真实调用、4条未校勘的OCR字面草稿，以及3张原书对应页图均能保存在私有环境，并可通过五阶段哈希恢复。

但上一阶段模型只看到**最多80个汉字的OCR单行**。这导致词汇误命中、跨行语义不明以及竖排古籍阅读顺序错乱都不能从短句推断。模型即使原样复制“富贵”“寿”也不能证明形态—结果存在历史文本上的明确关联。

本轮新增 `scripts/cangjie_private_context_quality.py`，**不再进行额外的模型调用**，只用已保存的真实OCR全文和实际模型来源进行一次可复核的资料质量审计：

- **来源一致性核对**：逐候选校验原版1925 PDF SHA256、私有OCR全文SHA256、完整OCR中的零起行号、按原M16.21算法重算的24位cue ID、模型输入OCR短句与模型关系来源，并阻止伪造行号或已修改的原始OCR重新出报告。
- **上下文而非误认整书关系**：在私有文件保留目标行上下2行的原始OCR结果（可设1–4行），不对列序进行擅自翻转。OCR引擎输出顺序**不等于**准确的古籍竖排阅读顺序，也不保证同一行和邻近行存在关联。
- **确定性错误风险标签**：80字截断、字数过短、同一OCR行不含五官形态、同一行多个断语领域、相邻行五官/断语关键词、整页重复OCR行，以及模型宣称存在明确关联但无人校勘。标签只表示**优先复核需求**，不表示语义证实或者预测概率。
- **生成本地离线页图对照**：`index.html` 显示与M16.25同来源的1925年原书PNG、前文/目标行/后文、模型形态与断语原文以及复核优先级。完整私有原书与模型句子不进公共GitHub，公开只统计数量和风险标记。
- **保持审核隔离**：不会自动标记短句已人工确认；不生成或激活在线Faceface规则；不会对真人财富、寿命、品格做事实性预测。

## Windows使用

必须先使用M16.25在仓库外的本地目录生成**真实完整私有证据**，例如 `C:/faceface-corpus/private/batch-nlc44091-p077-083`。后使用：

```powershell
python -m scripts.cangjie_private_context_quality `
  --selected C:/faceface-corpus/private/batch-nlc44091-p077-083/private/selected/nlc-44091-p077-083.jsonl `
  --model C:/faceface-corpus/private/batch-nlc44091-p077-083/private/semantic/nlc-44091-p077-083.json `
  --ocr-root C:/faceface-corpus/private/batch-nlc44091-p077-083/private/ocr `
  --review-pack C:/faceface-corpus/private/batch-nlc44091-p077-083/private/review-packets/nlc-44091-p077-083 `
  --out-dir C:/faceface-corpus/private/batch-nlc44091-p077-083/private/quality-context/nlc-44091-p077-083
```

结果包含本地HTML、复制的页图及仅保存在本地的`private-OCR-context-quality.json`。质量摘要`quality-summary-metadata-only.json` 不含原始OCR文字，可在审查后公开。

## 真实验证与重要限制

GitHub Actions在PR触发后，先运行来源一致性、OCR修改/伪造行号等单元测试，然后用真实1925扫描件执行7页OCR、3条实际Qwen3模型输入、页图渲染，最后**对这3条真实模型OCR输入重新计算cue ID并提取上下文**。只有运行日志成功后才能声称真实集成通过。

本阶段不会把已发布的49条M16.23临时样本描述为已恢复/已校勘。新工作包是对M16.25可持久保存批次的附加质检工具；GitHub临时Runner仍不是用户本地持久备份。

下一阶段需使用实际原始扫描进行古籍竖排**列顺序核对**、补足短句之外的相邻上下文，再决定是否在专用私有模型任务中重新提取更长的上下文。正式知识库依然要求独立的来源人工校勘。
