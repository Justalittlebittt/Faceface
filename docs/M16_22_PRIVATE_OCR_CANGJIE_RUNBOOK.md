# M16.22｜私有全书OCR候选直接进入固定仓颉语义提取

## 为什么不再只看整书统计

M16.21 **实际**对1925年原版两份扫描件共268页完成六分片PP-OCRv5；240页出现传统断语主题的OCR字词，139页含与五官形态同一OCR行的词语。该结果只证明原书中应研究的文本范围远大于现有10张形态卡；不是已确认的原文关系。原OCR文本只在临时Runner中，公开的领域统计不能供仓颉读古籍上下文。

M16.22 建立一条**同一受控环境内、不离开私有目录**的生产研究链：

```text
原始1925扫描PDF（SHA256锁定）
  -> PP-OCRv5 候选文本（私有）
  -> M16.21 古籍断语词源定位（私有JSONL；页码、原文SHA、OCR文SHA）
  -> 原版固定仓颉术语/原则角色文件 + 真实 Qwen3:4b-instruct
  -> M16.16 形貌—断语—条件—例外候选（私有、source_unverified、archive_only）
  -> GitHub公开统计（不含OCR原文／模型文本）
```

代码 `scripts/cangjie_private_ocr_semantic_batch.py` 从 M16.21 的私有 `*.jsonl` 直接读取OCR短句，校验扫描PDF存在及原版SHA、页码、OCR摘要、记录状态；支持多个分片、确定性排序和 `--max-cues 0` 全输入遍历，或采用正整数限制真实模型调用量。它复用现存 `OllamaClient`、固定官方仓颉提示文件及M16.17来源字面校验。每条 OCR 输入独立模型调用；候选进入M16.16档案验证，**全部仍为未经原图校勘的研究草稿**。

## 真正执行的验收范围

新增GitHub工作流 `cangjie-private-ocr-semantic-batch.yml` 采用**真实1925扫描零起页77–83共7页**，当场运行PaddleOCR、真实官方仓颉版本检查和本地Qwen3 4B，最多处理8条此时生成的私有断语OCR候选。记录真实模型请求数、通过原文字面校验的草稿数和拒绝原因分类。它不是模拟测试，也不能冒称268页仓颉语义提取已执行；若本区间词汇漏识别而无候选，工作流必须显式失败，不能产生虚假模型结果。

面向私有Windows工作环境，可以先在 `C:/faceface-corpus/scans` 储存两份锁定的原书文件，并用已有 `cangjie_paddleocr_candidates`、`cangjie_outcome_ocr_audit` 按分片生成私有 `jsonl`，再调用：

```powershell
python -m scripts.cangjie_private_ocr_semantic_batch C:/faceface-corpus/private-outcomes/*.jsonl --scan-dir C:/faceface-corpus/scans --upstream C:/cangjie-skill --private-out C:/faceface-corpus/private/semantic-result.json --public-metadata C:/faceface-corpus/reports/semantic-aggregate.json --max-cues 0
```

## 重要边界与下一步

- 原OCR短句可能识别错字、丢字、倒列或缺少上下文，即使匹配原OCR文本，也**不是原始图片逐字核对过的《麻衣相法》原文**；引用必须经过后续独立原版校勘，不能上网站报告。
- 私有OCR词汇候选还包括只出现传统断语、而未出现形貌的页。这些作为历史资料仍有保存价值，不因不能由照片观测就删除。
- 本工具支持多个分片，不要求只选择财富、寿命或品德；但M16.21的OCR关键词仍存在漏检，不能据此宣称“全书传统断语均已提取”。
- 使用固定仓颉原版角色提示**节选**是对官方方法论的真实复用，不等于执行了完整官方Adler+五独立Extractor的整书语义处理。以后仍需面向长篇、多页上下文执行完整角色流程、遗漏审计。
- 公开仓库与Actions Artifact只输出聚合数字。涉及原书全文权利和本地隐私管理，继续把文本存于非公开受控工作空间。
