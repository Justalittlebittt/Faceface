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

## M16.2｜整书竖排繁体OCR候选产线（不是校勘完成）

**实际程序：** [cangjie_ocr_candidates.py](../scripts/cangjie_ocr_candidates.py)、[cangjie_ocr_audit.py](../scripts/cangjie_ocr_audit.py)、[六片并行OCR Actions](../.github/workflows/cangjie-ocr.yml)。

- 对M16.1的两份原PDF（153页＋115页）使用Poppler逐页渲染及 Tesseract `chi_tra_vert` + `--psm 5` 竖排繁体模型，不把横排OCR错当古籍正文。每页以 **PDF零起页码** 记录扫描SHA256、OCR候选文字SHA256、汉字数、词级平均置信度；0字页记 `empty_ocr_candidate`，不会生成空文本冒充已转录。
- GitHub CI矩阵分6片（第1份0–50／51–101／102–152；第2份0–38／39–77／78–114），**每片下载该扫描源、真正OCR全部指定页**。汇总任务逐页核对268个唯一ID及来源文件SHA256，缺页／重页／OCR自动提升为正式证据均使工作流失败。完成运行结果以实际Actions证据为准。
- **版权与可校勘性边界：** CI完整OCR候选仅在临时runner内生成，GitHub公开Artifacts保留页级元数据和统计，**不保留/公布完整扫描或未经核对的OCR正文**。这意味着生产环境长期使用的候选正文应通过Windows本地执行本脚本存放在本地私有工作区，或后续在许可确认后迁至经批准的受控存储，不得把临时CI运行误作已持久落库。
- **人工或逐图Agent校勘是独立阶段。** OCR文字很可能有旧字形、图谱、阅读列序的错误，`mean_word_confidence`只是OCR引擎内部统计，**不是正确率**。输出一律 `requires_manual_page_review=true`、`eligible_for_cangjie_verified_corpus=false`；现有M16.1校勘哈希验证仍为强制准入。OCR成功的页数**不等于**已校勘页数，也不能直接传仓颉五提取器。

在用户 Windows/Codex 项目本地，需安装Tesseract和包含繁体竖排 `chi_tra_vert` 语言包，以及Poppler的 `pdfinfo`、`pdftoppm`：

~~~powershell
python scripts/cangjie_ocr_candidates.py --scan-dir C:/faceface-corpus/scans --out-dir C:/faceface-corpus/ocr --source nlc-44091
python scripts/cangjie_ocr_candidates.py --scan-dir C:/faceface-corpus/scans --out-dir C:/faceface-corpus/ocr --source nlc-44092
python -m scripts.cangjie_ocr_audit C:/faceface-corpus/ocr/reports/*.json --out C:/faceface-corpus/ocr/full-audit.json
~~~

**Windows PowerShell 通配符注意：** Python接收通配符路径在不同shell下行为不一致，可在Codex任务中枚举 `reports` 目录的JSON文件并传入本脚本，或者使用兼容的shell。OCR候选输出位于 `ocr/transcripts/nlc-44091/000.txt` 等页面路径，`.ocr.json` 包含待审核元数据。与M16.1的 `cangjie_corpus_stage.py --transcripts-dir ...` 对接时，这些未人工校勘候选会标记为 `unreviewed`，只有含一致SHA256的独立 `.review.json` 才成为 `reviewed`。没有图片校勘不可伪造复核人或直接创建review凭证。

**M16.2 Gate：** 全部268页的OCR操作有真实可检索日志和非正文metadata，双源页码不缺漏；正式全文 `reviewed` 的比例须独立报告。下阶段应集中做批量视觉校勘与卷章索引，再运行真正的仓颉Adler和五Agent候选蒸馏，不能恢复每次只选一条古籍规则。

## M16.3｜原文短句锚点：验证OCR质量而不是误把置信度当正确率

**运行证据：** [PR #25](https://github.com/Justalittlebittt/Faceface/pull/25) 和 [真正的OCR模型对照Actions #44034779726](https://github.com/Justalittlebittt/Faceface/actions/runs/44034779726)。

M16.2的268页OCR共267页非空、约51,101个候选汉字，**223页**的词级OCR页面均值不足50/100。为判断这批内容能否批量蒸馏，M16.3直接从原PDF抽出V5知识库已经核对的10个不同扫描页和另外3张第二份扫描样本，在不发布原文和图像的条件下，对四种模型/预处理设置做重复测试：

| 方案 | 第一份10页样本的20段原文短句完全匹配 | 最高连续重合比例均值（仅诊断） | OCR内部词级信度均值 |
| --- | ---: | ---: | ---: |
| 原版chi_tra_vert、170dpi | 1/20 | 0.421 | 37.9 |
| chi_tra_vert、220dpi墨迹裁剪 | 2/20 | 0.438 | 39.2 |
| chi_tra_vert、裁剪+PSM3 | 2/20 | 0.424 | 40.3 |
| HanT_vert、220dpi墨迹裁剪 | 1/20 | 0.355 | 38.6 |

**这些不是真实字错率（CER）或全文识别精度！** 词句有图页断开、原文异体字和文本顺序差异；它们只能说明在当前样本上没有足够证据把Tesseract OCR自动放行给仓颉抽取器。第二份3个页面因缺乏核对原文锚点，仅得到置信度对照（约50.5、53.2、54.2、52.6），无法计算可比来源短句匹配。

下一阶段优先使用能够分析古籍竖排、版面区域和列阅读顺序的**替代OCR/文档视觉引擎**，在相同原始扫描基准上做有人工原文校核的对照；不再无限次调Tesseract阈值，不把低信度OCR直接转成基于外貌的内容。质量合格后再扩大到268页批量文字校勘，之后才运行官方仓颉Adler整书理解、五提取器Agent、三重审核、全部内容去向审计和规则批量dry-run。M16.1/M16.2的原书来源台账、OCR候选CLI和复核SHA256 Gate均保留复用。

## 首个实施批次（执行而非长期只出计划）

**一次走通“扫描底本来源映射 → 原页文本/图谱归档 → 官方仓颉5类提取 → 来源/覆盖审计 → 统一JSON候选 → 批量导入dry-run”完整链条**。同一链条跑通后，按剩余章节自动批处理，不能回到单条人工增量。先由实际可用扫描文件确定任务分片范围，不凭空编造底本页数或条目总数。
