# M16.27｜1925年《麻衣相法》原书竖排列序候选审计

## 核心目标

Faceface使用的是1925年原版扫描的未经人工校勘OCR。对于竖排、夹注、表格、图画的古籍，一行OCR在计算机里的先后顺序未必符合实际排版，不能把“相邻OCR行”直接当成有因果联系的完整文句。M16.4的实验中，简单的从右到左坐标排序对已知短句的精确命中甚至差于原始PaddleOCR顺序（4 对 5）。因此**M16.27不修改既有M16.21 cue ID、OCR正文、仓颉输入、古籍断语模型输出**。

本轮新增 `scripts/cangjie_ocr_geometry.py`，并扩展 `scripts/cangjie_paddleocr_candidates.py`：

1. **真实识别框持久化**。每个原版页OCR结果在既有 `transcripts/<source>/<page>.txt`、`*.ocr.json` 之外，新增 `*.geometry.json`。记录每条被保存OCR文本行的**零起行号**、对应原始识别序号、PaddleOCR给出的 `[x_min,y_min,x_max,y_max]`、置信度；若没有方框则明确标注，不编造坐标。
2. **来源可核对**。`geometry.json`包含原版PDF SHA256、原版页码、OCR文本SHA256；每页 `*.ocr.json`又包含几何数据文件的哈希。M16.25的私有运行工作目录对新增侧车进行阶段哈希保存；恢复时不能静默篡改坐标或OCR文字。
3. **列序建议而非擅自改写**。从原始PaddleOCR候选区域中按近似x坐标分列、列从右向左、列内按近似y坐标向下生成 **suggested_line_indices**。也永久保留 `ocr_original_line_indices` 原顺序。出现大跨度框、过多孤立列、原顺序和几何建议不符等情况会标出待人审信号。模型**继续使用经过此前真实验证的原始OCR顺序**；不会把建议列序作为可靠原文。
4. **无泄漏的覆盖报告**。生成仅包含逐页识别区域数、是否有完整坐标、几何重排是否与原顺序不同、异常类型计数等的公开报告；含坐标、具体排列的详细资料只保存在私有目录。
5. **保持审核隔离**。所有识别框、候选列序、OCR原文均 `source_unverified`，不能由程序当成整页人工核对，更不能直接产生正式Faceface在线规则。

## Windows运行流程

从M16.27起，新的OCR分片会直接写出几何侧车；需要使用已经安装的PaddleOCR 3.3.2、PaddlePaddle 3.2.0与Poppler，以及与此前完全一致的原版扫描SHA。

```powershell
python -m scripts.cangjie_paddleocr_candidates `
  --scan-dir C:/faceface-corpus/scans `
  --out-dir C:/faceface-corpus/private/ocr-with-boxes `
  --source nlc-44091 --start 77 --end 83 --dpi 170
```

输出的原版OCR文本、哈希元数据和识别框应始终存于**GitHub仓库之外的私有持久目录**。审计同一批次真实列序（原有文件不会重写）：

```powershell
python -m scripts.cangjie_ocr_geometry `
  --ocr-root C:/faceface-corpus/private/ocr-with-boxes `
  --source nlc-44091 --start 77 --end 83 `
  --private-output C:/faceface-corpus/private/geometry-detail-p077-083.json `
  --public-output C:/faceface-corpus/private/geometry-summary-p077-083.json
```

在人工校勘时，对照原书同一页图与两个排列索引，检查正文是竖列、标题、眉批还是图注。此版本**不自动确认列界**。遇到没有坐标、宽框、多孤立列的页优先人工核验。整个项目原有M16.25模型草稿仍保持未校勘。

## 实际验收

`.github/workflows/cangjie-original-geometry-audit.yml` 从两份固定原版PDF下载并核对SHA，真实运行第一份原书PDF零起第77–78页的PP-OCRv5；验收文件是否保存真实框、几何重排与原始顺序对照、页号/OCR哈希、元数据隐私和零历史断语签认。此验收**不重新运行Qwen或完整仓颉五类Extractor**，避免在已有三次模型证据之外增加与列序问题无关的推理开销。

下一阶段应把这些证据呈现为原书页面上的**可视化列区标注**，由人核对列与段落后，才允许重组古籍文本并在私有环境重新执行完整仓颉模型语义提取。仅凭坐标给出一个“从右至左”顺序远不够。
