# M16.25｜本地私有持久化：原书OCR→仓颉→原图校勘包

## 解决的问题

M16.23实际在GitHub临时运行环境对1925年原版《麻衣相法》268页做了六分片OCR、48次固定仓颉提示引导Qwen3模型调用，得出49条**OCR字面匹配、未校勘**研究草稿。但模型/原OCR文本没持久保留，仅公开计数。M16.24创建私有原图校勘包组件，但没有把模型运行和生成校勘包串成可恢复流水线。

M16.25新增 `scripts/cangjie_durable_private_batch.py`，一次运行自动完成并保存：

1. 原版PDF SHA256/页数核验、真实 PP-OCRv5 逐页OCR，保存每页原OCR文本、元数据及阶段报表；
2. M16.21 源指纹化传统断语线索抽取、保存私有OCR断语段落JSONL；
3. M16.23 按领域/原版页码选择有限数量段落，保存确切模型输入；
4. 使用固定版官方仓颉节选提示 + 本地真实Qwen3 4B，每段独立来源约束，保存**原文和拒绝记录**的私有模型结果，另外生成公开安全计数；
5. M16.24 对所选原书页渲染**真实原版PNG**，生成本地离线HTML对照、逐条待签认校勘表。绝不自动称人工审核。
6. 原始/结果数据位于当前指定的私有本地文件夹；每完成一阶段，保存SHA256文件清单；`--resume` 校验完整数据后跳过已成功步骤，避免重复模型调用和覆盖人工校勘文件。若阶段已完整生成但未登记，验证后重新登记；部分写入或哈希变化则停止并要求人工排查，不会悄悄覆盖。

## Windows（PowerShell）本地运行

安装当前项目Python依赖、Poppler（`pdfinfo`、`pdftoppm`）、PaddleOCR 3.3.2、PaddlePaddle 3.2.0、Ollama并下载`qwen3:4b-instruct`；确保 `cangjie-skill` 指向固定官方提交 `a28de55ba881b9928956a55048f743f7a9e3b23e`。

把两份原版PDF分别保存为 `C:/faceface-corpus/scans/part1.pdf`、`part2.pdf`。下列命令在Faceface代码根目录执行：

```powershell
python -m scripts.cangjie_durable_private_batch `
  --workspace C:/faceface-corpus/private/batch-nlc44091-p077-083 `
  --scan-dir C:/faceface-corpus/scans `
  --upstream C:/tools/cangjie-skill `
  --source nlc-44091 --start 77 --end 83 --max-cues 8
```

若进程因停电/系统更新/模型中断，需要重启：

```powershell
python -m scripts.cangjie_durable_private_batch `
  --workspace C:/faceface-corpus/private/batch-nlc44091-p077-083 `
  --scan-dir C:/faceface-corpus/scans `
  --upstream C:/tools/cangjie-skill `
  --source nlc-44091 --start 77 --end 83 --max-cues 8 --resume
```

上面 `--workspace` 路径为**新目录且必须在Git仓库之外**，文件内容属私有古籍和模型研究记录。切勿提交到公共 GitHub/公开 Actions Artifact，也不要用 `$RUNNER_TEMP` 作为想长期保留资料的目录。

生成后打开 `.../private/review-packets/nlc-44091-p077-083/index.html`，可见原书原图和模型OCR对照；手工对照原图并编辑同目录 `private-review-decisions.json`。每页的OCR文字及元数据、每条模型原文及拒绝原因在该批次的 `private/` 下长期保留。PDF仍是外部 `--scan-dir` 提供的原件，需要一起备份。

### 安全、恢复与证据限制

- OCR原文、模型提取都仍然未校勘。真实模型请求成功≠传统富贵、寿命、品德断语已确认。
- 只有独立人工查对扫描原图，才能核对短句。M16.24的短句签名不等于完整页校勘；完整页核对仍使用既有 `cangjie_page_review.py`。
- 模型使用的是固定版官方仓颉提示**节选**，并非真正完成官方完整五提取器和全书Adler。
- `--resume` 并非为同一目录提供并发锁，**不要并行运行两个写入进程**。阶段里仅写了部分文件而未完成时流程会拒绝覆盖；需先检查并手动修复、或另开新的独立批次。
- 文件哈希保证**恢复时检测到无意修改**，不是签名、防恶意篡改或独立见证，也不保证在磁盘损坏后恢复原字节。应由使用者将整个私有批次目录及原PDF备份到受控的本地离线位置。
- GitHub Actions集成测试确实会运行原版PDF与本地模型，但 `RUNNER_TEMP` 是临时目录，结束即消失；CI只上传不含原始内容的元数据。CI不能替代Windows上的永久私有备份。
- 网站用户人脸图像完全不参与本工具；不改变手机端手动拍照或不保存人脸数据的合同。

## 验收与后续

新增 `.github/workflows/cangjie-durable-private-batch.yml`：回归测试对真实流程做**显式合成模型存根**，验收拒绝篡改、恢复不重跑；另一路下载真实1925 PDF并对第78–84页进行OCR、最多3次真实Qwen3模型调用、真实页图渲染、`--resume`校验。只有实际Actions完成后才能报告运行成功和真实数字。

本阶段目标是让后续每个批次的文本、图像和校勘记录可在本地保存/恢复，而不是再把临时推理次数或统计数字误当作正式历史知识库。
