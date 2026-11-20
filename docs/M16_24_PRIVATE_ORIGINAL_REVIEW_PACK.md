# M16.24｜1925年《麻衣相法》原图／OCR／仓颉断语私有校勘工作包

## 产品意义与边界

M16.23 实际运行六分片原版268页PP-OCRv5，48次真实 Qwen3:4b-instruct 模型请求，留下49条**未核对原图的OCR字面匹配草稿**及37条被拒绝的模型输出；原图人工完整校勘仍为0。原版扫描件、OCR候选、模型原文均在GitHub Actions临时运行环境，未上传到公开仓库。其公开聚合统计**不能还原这49条私有草稿内容**。

M16.24 引入 `scripts/cangjie_private_review_pack.py`：在仍持有**实际**M16.22/M16.23私有结果文件与原版PDF的环境运行，把真实原始页图、相应未校勘OCR、模型草稿和拒绝原因放到本地离线HTML。并建立**逐条人工短句核对模板**；所有操作仍与 Faceface 用户的人脸采集、运行规则完全隔离。

## 本地 Windows 生成方法

先将本地真实OCR→Qwen实验中的 `--private-out` 结果文件保存在本地私有目录（**不能从公开GitHub统计JSON恢复OCR短句**），确保 `scans/part1.pdf` 与 `scans/part2.pdf` 是官方SHA锁定的原版扫描件；安装并配置Poppler工具 `pdfinfo` 和 `pdftoppm`。在Faceface项目根目录：

```powershell
python -m scripts.cangjie_private_review_pack `
  --private-record C:/faceface-corpus/private/shard-p051-101-semantic.json `
  --scan-dir C:/faceface-corpus/scans `
  --out-dir C:/faceface-corpus/private/review-p051-101 `
  --dpi 150
```

打开生成的 `index.html`（本地文件，无网络访问、无JS追踪），可同时查看原书整页扫描、未校勘OCR短句、模型抽取到的形态/传统历史断语/领域以及所有拒绝原因。图片在 `pages/`，私有候选详细信息在 `private-OCR-model-evidence.json`。

本地 `private-review-decisions.json` 逐条以 `pending` 开始。人工必须直接对照原版图像才能将状态改为 `short_span_confirmed`、`OCR_mismatch`、`ambiguous_original` 或 `out_of_scope`，填写真实核对者标识、`confirmed_against_original_page_image: true` 和适用的校正原文。**绝不能仅根据OCR文字或模型推测确认。**

可单独核验人工短句记录，并在另一私有位置生成只含计数的审核摘要（不可覆盖原有审核档案）：

```powershell
python -m scripts.cangjie_private_review_pack `
  --audit-decisions C:/faceface-corpus/private/review-p051-101 `
  --audit-output C:/faceface-corpus/private/review-p051-101-audit.json
```

本工具**不会**将校正的短句直接升级为`human_reviewed_full_page`，也不会触发Faceface线上规则。若要完成真正的整页人工签认，继续使用现有 `scripts.cangjie_page_review` 的全文校对功能，不能用短句核对偷换完整页认证。

## 本轮真实验证范围

- GitHub Actions运行原版两份PDF的真实下载、SHA256校验和**真实一页 PDF→PNG 图像渲染**。
- 校验界面HTML能显示扫描图、OCR及模型关系，拒绝伪造源文件哈希、缺失候选、恶意HTML和“由agent替代人类校勘”。
- CI用于页面渲染的OCR短句/模型返回**明确是合成契约测试用例**，不是M16.23实际49条候选，也**没有再调用一次Qwen**。无人工审核声称。
- GitHub仅上传不含古籍短句的聚合元数据；私有工作包、PNG、OCR文字、模型内容以及人工核对记录全部保留在各自的本地私有环境，既不提交GitHub也不上传到公开Artifacts。
- 因为之前M16.23 GitHub临时Runner结束后未保存私有全文，此PR**不能声称找回那49条原有OCR模型草稿**。对于要长期留存的结果，务必在本地持久私有工作区运行M16.22/M16.23，再生成同目录工作包。

## 下一阶段

用M16.24工作包驱动真实原图校勘、记录OCR漏字／串列、重跑模糊段落，开展来源可审计的古籍档案清理。保留财富、寿命、品德等传统观念原典内容，但线上应用只能作为传统文化历史观点，不能据此断定真人寿命、财富或品行。现有拍照交互和隐私合同均不改变。
