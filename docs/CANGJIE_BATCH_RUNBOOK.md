# M16｜仓颉驱动的《麻衣相法》整书批量知识库流水线

> 执行路线修正：2026-11-17。**本文件是可执行的任务合同，不代表已安装、运行或完成整书蒸馏。** 前面的 M12–M15 单条核验仅为产品闭环样例；它们不等于仓颉整书工作。

## 唯一目标与非目标

**目标：** 对固定的1925年文明书局秦慎安校勘《麻衣相法》五卷，建立完整、可逐页追溯、可审计的原典档案，并由**官方 cangjie-skill v2.5.0 实际参与**整书结构化、并行候选提取、三重验证、语义归一及覆盖审计。一次批量处理覆盖所有已取得并可解析的章节，而不是人工每轮挑一条面相写新源码。

**非目标：** 不让仓颉代替OCR/古文校勘，不把每个古籍断语编译为独立Skill，不以能力卡数量冒充全部原文覆盖，不把传统相貌叙事当作个人现实性格/健康/命运结论。**产品首发核心拍照闭环不等待全书处理完成**，两线并行。

## 执行先决条件与工作边界

1. **确认官方工具本体**：使用 https://github.com/kangarooking/cangjie-skill 的根 `SKILL.md`、`extractors/`、`methodology/`、`scripts/cangjie.py`，锁定实际commit与安装包校验值。先运行 `python scripts/cangjie.py doctor`，记录官方工具实际执行结果。切忌只借鉴README却声称“已使用仓颉”。
2. **固定输入语料而不是凭记忆蒸馏**：先取得五卷覆盖的扫描底本；扫描件编号与印刷卷次独立，建立 `source_file_id + pdf_page_zero_based + printed_volume + section + source_url` 关系。把每页图片/提取文本及校勘记录保存在**非公开、访问受控**的语料工作区。未确认复制许可前，不将整本扫描或全文推送公开GitHub。
3. **先扫整书**：为每页建立记录，包括无正文、图谱、缺页、待释读、异文。自动取文字；识别度不足时保留原图定位和“待校勘”标签，绝不伪造缺失原文。
4. **批量运行仓颉**：先整书 `BOOK_OVERVIEW`，再按章节/长文本分块对五类提取器——框架、原则、案例、反例、术语——执行（有子Agent则并行，否则同一prompt串行）。汇总 `candidates/`，跑来源充分性/可执行性/任务增益三重验证，按 `verified / reference / needs_review / rejected` 分类；保留 `coverage-audit`，使每个有内容的原典页/篇章都有明确去向。对书中纯历史叙述即便不属于方法论能力，依然单独归档，不准因仓颉过滤而丢失。
5. **中间结果是统一结构化候选库**，不是直接新增网站硬编码JSON：每条保留稳定ID、原文页与位置、原文摘录/白话解释、形态概念、必要与例外条件、原书传统说法、可观察性及干扰因素、来源充分性、重复/冲突链、校勘状态。
6. **独立准入**：可观察的候选批量映射到 Faceface `Descriptor.id`，区分 `history_only` / `candidate_unverified` / `verified_not_observable` / `partial_photo_usable`。只有原页通过、几何指标真实可测、边界与遗漏明示者才可批量写入版本化运行规则库；不能把单一现代比例认作完整古籍相型。结果仍为中文/英文文化解读，并由既有浏览器测试回归。

## 需要真正交付的文件与指标

| 交付 | 验收依据 |
| --- | --- |
| **底本目录与全量逐页档案**（私有） | 每份扫描/印刷卷/篇章对齐、页码映射、正文/图谱/缺损标记、校勘状态；总页数和已覆盖页数可直接计算 |
| **仓颉真实运行记录** | 固定上游版本、`doctor` 输出、`PIPELINE_STATE`、`BOOK_OVERVIEW`、五类提取器产物及调用记录；不接受伪造成功日志 |
| **全量候选和分类台账** | 每个候选有原文来源、内容ID、保留/退回原因；`coverage-audit` 明确遗漏及去向 |
| **结构化知识库与批量导入器** | Schema、去重/冲突/缺页核验、dry-run 差异报告；未审核候选不能改变线上报告 |
| **产品回归** | 现有十项描述、隐私/权限与 M11 手动拍照不改变；中英报告与来源跳转、M9对照、Chromium/WebKit通过 |

**成功口径必须分开报告：** （A）原典收录率 = 已归档实际原页 / 已取得有效原页；（B）内容审核率 = 完成原页判读候选 / 总候选；（C）可照片触发率 = 通过来源和照片条件的规则 / 适合照片判断的规则；（D）线上启用数。A 的100%不意味着 C/D 的100%；缺卷/缺页必须独立报告，不可缩小分母。

## 开发纪律

- **立即停止**以“每轮核查一条、增加一张卡片”作为默认主线里程碑；只保留紧急修错或验证整条流水线的小样本测试。小样本试运行通过后，**直接覆盖整书/全部可用章节的批量运行**，不再逐条请求用户“继续”。
- 将过程中的技术阻断集中记录一次，并批量解决；不要用不断增加小PR数量替代实质上的书页覆盖率。
- 不新增声称已使用仓颉、已完成蒸馏或已归档全部五卷的文案，除非实际运行产物可追溯。
- 在用户本地 Windows + Codex 环境工作时，优先项目级 `.agents/skills/` 规范安装并本地处理底本，保护语料；公开 Faceface 仓库只接收可公开的schema、工具、统计及已核对的短篇来源条目。

## M16.1 已实现的底本清点与官方仓颉工具接入

此前仅设计了流程；本版新增 [实际执行工作流](../.github/workflows/cangjie-corpus.yml) 与 [原典分块准备程序](../scripts/cangjie_corpus_stage.py)，运行结果以Actions日志为准。

- 固定底本扫描源：Wikimedia Commons [NLC 44091上册](https://commons.wikimedia.org/wiki/File:NLC416-12jh002690-44091_麻衣相法_第1卷.pdf)，153页；[NLC 44092下册](https://commons.wikimedia.org/wiki/File:NLC416-12jh002690-44092_麻衣相法_第2卷.pdf)，115页。**两份数字文件合计268扫描页，作品正文五卷；文件名的“第1卷/第2卷”不能当作正文卷次。** 具体卷章到PDF页的映射仍待逐页核对。
- 工作流真实下载两份扫描文件，核对PDF格式、页数、SHA256，并对每页生成唯一页ID和 transcription 状态；扫描已取得不等于文本已取得。
- 仅当某页文本文件及人工复核记录中的复核人员、扫描PDF的SHA256、零起页码、文本SHA256全部相符，才纳入可供下游阅读的 reviewed-transcription。
- 通过GitHub Actions从官方仓库检出固定commit a28de55ba881b9928956a55048f743f7a9e3b23e，执行原版 Cangjie doctor 和 build_chunks。为避免假装已读整书，首次测试文本只有既有V5知识库中**10条历史短引文和3条背景短引文**，明确标记 pilot-only。
- GitHub Actions 只保存**页状态、来源hash、任务交接、doctor输出**，不上传整本PDF、未核对OCR或人像材料。官方CLI只负责确定性预处理，Adler整书理解与五类候选提取必须由Agent实际完成，不能把环境检查说成蒸馏成功。

Windows与Codex复现：安装 Python3.10+、PyYAML，以及提供 pdfinfo.exe 的Poppler。将两份PDF分别保存为本地 scans/part1.pdf、scans/part2.pdf，执行：

~~~powershell
python scripts/cangjie_corpus_stage.py --scan-dir C:/faceface-corpus/scans --transcripts-dir C:/faceface-corpus/transcripts --checked-cards src/knowledge/maiyi-source-checked-v5.json --out-dir C:/faceface-corpus/audit
python C:/cangjie-skill/scripts/cangjie.py doctor
python C:/cangjie-skill/scripts/build_chunks.py C:/faceface-corpus/audit/prechecked-excerpts-pilot.md --sidecar C:/faceface-corpus/cangjie-sidecar --source-id faceface-v5-checked-excerpts-PILOT --max-chars 1200
~~~

现阶段**不得声称**268页已转录或校勘、仓颉五提取器已运行、候选库已蒸馏完成。下一完整输入Gate是从原书每页取得可复核的竖排古籍文本并录入 reviewed 页面，再由Agent全书提取。

## 首个实施批次（执行而非长期只出计划）

**一次走通“扫描底本来源映射 → 原页文本/图谱归档 → 官方仓颉5类提取 → 来源/覆盖审计 → 统一JSON候选 → 批量导入dry-run”完整链条**。同一链条跑通后，按剩余章节自动批处理，不能回到单条人工增量。先由实际可用扫描文件确定任务分片范围，不凭空编造底本页数或条目总数。
