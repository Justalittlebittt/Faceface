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

## M16.4｜实际运行PaddleOCR以检验替代方案

**证据：** [PR #26](https://github.com/Justalittlebittt/Faceface/pull/26)；[真实CPU PaddleOCR动作 #44036603159](https://github.com/Justalittlebittt/Faceface/actions/runs/44036603159)；[执行代码](../scripts/cangjie_paddleocr_benchmark.py)。

本轮固定Python3.11/PaddlePaddle3.2.0/PaddleOCR3.3.2，显式配置`PP-OCRv5_mobile_det`（文本检测）与`PP-OCRv5_server_rec`（繁体及古籍文本识别），170dpi原始1925版PDF页，CPU执行并仅在Actions保存非正文统计。官方文档说明PP-OCRv5模型支持繁体、竖排及古籍，但**这些官方的训练/基准指标不是Faceface扫描件的准确率**。

| 来源/设置 | 样本页 | 已核对短句完整检出 | 说明 |
| --- | ---: | ---: | --- |
| 第一份PDF，Tesseract baseline 170dpi | 10 | 1/20 | M16.3对照基线 |
| 第一份PDF，Tesseract较佳方案 220dpi裁剪 | 10 | 2/20 | 仅20段短句的完整子串检出 |
| 第一份PDF，PaddleOCR PP-OCRv5 CPU 170dpi | 10 | **5/20** | 模型原始识别输出1960候选汉字，内部识别评分约0.7761 |
| 第一份PDF，PP-OCRv5强制右到左列重排 | 10 | 4/20 | 几何列排序在这些样本中不如原始顺序，**不启用** |
| 第二份PDF，PP-OCRv5 CPU | 3 | 无已核对短句可作判断 | 输出633候选汉字、模型内部评分约0.8267，**不能算全文准确率** |

唯一可肯定的结论：PP-OCRv5在这批核对过的短语定位上优于当前Tesseract配置，且能以标准免费CPU在GitHub Actions实际完成推理；但仍只有5/20段短句被完整连续检出，模型评分与真实字错率没有对应校准。模型反推的右左阅读顺序也是待检验假设。

**下一质量门：** 使用原页影像核对且有卷章/文字顺序的**整页正确转录**，至少覆盖正文、图谱、诗诀等不同排版类型，再计算真正逐字CER、错序及缺页，确定哪种OCR可用于自动辅助校勘。未经逐页检查的识别文本保持`unreviewed`，不进入已审核的仓颉五类内容提取器。底本共268页的完整扫描覆盖已完成，**正式全文校勘仍0/268**，没有声明新知识规则上线。

## M16.5｜原PDF逐页校勘台与真实整页CER质量门（现已开发并测试，真实校勘仍为0页）

这一步不再把20段历史短句当作“整页识别率”。原典全文的真正难点是保证每个古籍竖排列顺序、正文及配图均经原图核对后再进入仓颉。M16.5提供**可操作、可签发复核记录、可计算真实整页字符编辑距离**的本机工具：

- [本机侧栏原图+OCR编辑校勘台](../scripts/cangjie_page_review.py) + [HTML界面](../scripts/cangjie_review_ui.html)，由**127.0.0.1**提供，不能在远端打开或访问用户本地文件，不使用浏览器外部CDN、在线OCR、埋点、照片接口；POST校勘记录必须通过会话Token和同源检查。
- [审核与原页指纹内核](../scripts/cangjie_review_core.py)固定M16.2实测的两份1925扫描PDF SHA256（第一份`466adfaba96be3ba63cab4784b97dd04d1a7e86950601073e27aa6bdffbcc649`、第二份`ce9020bb7d2e404f16689519c0c33df3525e3131b980b02344ed9ed967303ef7`），如用其他扫描版本会**拒绝误归档**。零起页码、OCR候选文字SHA256及原PDF来源必须一致才能把候选放入编辑区。
- **区别候选与审核：** 在左侧本机扫描原图核对全文后，右侧修改OCR结果，再填写实际复核人、必要的印刷卷章及图谱备注，并勾选“已经核对整页”。审核后的文本写入完全**不同的私有目录** `reviewed/<source-id>/<page>.txt`，同时记录 `.review.json` 的PDF哈希、完整文本哈希、来源页、复核人和时间；不修改OCR候选、原书图像或网站运行知识库。这是人工确认声明，**不能证明这个人真正正确地核对了全部文字**，仍需要独立抽检。
- [整页质量程序](../scripts/cangjie_review_quality.py)在有校勘参考与同一原PDF OCR候选时才计算**逐汉字、严格保留字序的 Levenshtein CER**，另外给出**不计顺序**的汉字多重集召回（仅用于诊断顺序错误）。不对未复核页计算准确率，原有历史短句和OCR置信度不能冒充整页金标准。
- 既有 [Cangjie入库门](../scripts/cangjie_corpus_stage.py) **同时核查**OCR候选与审核后正文；最新要求有明确“完整原页、全文、人工签字”字段，不允许只凭任意名字、PDF哈希和几字短文自动升格；如果撤销全部有效复核，也删除旧的 `reviewed-transcription.md` 防止残留错误知识。
- [M16.5 CI](../.github/workflows/cangjie-page-review.yml)用模拟文字测试签名与CER及CSRF拒绝，并真实下载固定版本两份PDF，**从实际PDF第27个零起页渲染扫描图**，通过本机HTTP服务请求并校验图片及原文状态。真实源页验证覆盖268页；**CI没有也不能代表人类核对了正文（0/268），真正CER分母仍为0**。

### 用户 Windows / Codex 本地运行一次整条工作流

**本地路径不随GitHub公开仓库一起提交。** 在Faceface仓库根目录运行，先将两份固定PDF保存在 `C:/faceface-corpus/scans/part1.pdf` 与 `part2.pdf`；下载来源在M16.1一节。电脑需安装Python3.10+、Poppler（`pdfinfo.exe`、`pdftoppm.exe`），如本地尚无候选OCR文字，另需Tesseract竖排模型 `chi_tra_vert`（或预先用更优模型自行生成**带来源哈希的**OCR文本）。

~~~powershell
# 从原PDF生成可供校勘的候选文字（不自动批准）
python -m scripts.cangjie_ocr_candidates --scan-dir C:/faceface-corpus/scans --out-dir C:/faceface-corpus/ocr --source nlc-44091
python -m scripts.cangjie_ocr_candidates --scan-dir C:/faceface-corpus/scans --out-dir C:/faceface-corpus/ocr --source nlc-44092

# 启动仅本机可访问的图文并排校勘台
python -m scripts.cangjie_page_review --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --port 8765
~~~

在浏览器打开 `http://127.0.0.1:8765`，选择源PDF和零起页，校订原文并签名保存，之后**停止或另外打开命令行终端**再运行：

~~~powershell
python -m scripts.cangjie_review_quality --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --out C:/faceface-corpus/quality.json
python -m scripts.cangjie_corpus_stage --scan-dir C:/faceface-corpus/scans --transcripts-dir C:/faceface-corpus/reviewed --checked-cards src/knowledge/maiyi-source-checked-v5.json --out-dir C:/faceface-corpus/audit
~~~

仅当有真正签署的有效完整原页文字时，`C:/faceface-corpus/audit/reviewed-transcription.md` 才会生成，才可以将这个受控文本交给仓颉的 `build_chunks` 和后续五类Agent。**仍存在单独待实现的难点：纯图谱、确认空白、损坏页面需要可审计的非文本归档状态；不能填虚构正文以凑268/268。** 此阶段暂只签署有可转录文本的页面，图片或空白页继续标注待分类，永远不把“缺文本”自动算完成。

## M16.6｜268页本地视觉Agent自动草稿队列（真实可运行接口；不冒充真实Agent已执行）

**代码和验收：** [批量调度与模型API](../scripts/cangjie_vision_agent_batch.py)、[原图并排校勘台](../scripts/cangjie_page_review.py)、[268页原PDF任务队列CI](../.github/workflows/cangjie-vision-agent.yml)（[PR #28](https://github.com/Justalittlebittt/Faceface/pull/28)）。

目标是避免让人从空白文本框手打268页：使用固定原图、页码及可选OCR候选，由Windows本机运行的**实际视觉模型**逐页输出明确标为`agent_draft`的繁体竖排校订初稿，重复执行可以跳过已完成草稿；已有真人签署的原文永不被自动修改。

- `--mode plan --source all` 逐份核对**两份1925年原PDF及SHA256**，直接产生 **268个唯一`nlc-44091:p000` / `nlc-44092:p114`任务**；优先跳过已有人工完整页复核，识别与源PDF/OCR哈希/模型版本及Prompt版本匹配的可复用AI草稿。此动作不需要模型，不读取外部私人网络，也不产生虚构原文。
- `--mode run` 通过官方 Ollama `POST /api/chat` JSON Schema结构化输出及base64原页图像字段调用用户**自己启动**的本机 `qwen3-vl:4b` 视觉模型；**URL强制限制为localhost或127.0.0.1的HTTP端口**，不接受远程第三方API地址，代码不会发送真人脸图。模型必须事先真实安装并通过 `/api/tags` 检查；如果没有，程序直接报错，不会假装已完成。
- 逐页保留`page_type`（text / title_or_verse / text_and_figures / blank / figure_only / damaged）、**从右到左的候选原文列序**、未辨识字及异体疑点、图谱备注、卷章猜测、模型及来源SHA256、未校勘状态。OCR候选如存在，必须与原PDF页码及其文本哈希匹配，否则不提供给Agent；原始扫描优先于OCR。模型回复必须符合JSON结构，异常不能自动变成审核通过。
- AI草稿仅保存在私有 `agent-drafts/<source-id>/<page>.draft.json` 和 `.draft.txt`。**不会进入`reviewed/`、`reviewed-transcription.md`、浏览器线上规则库或仓颉已审阅正文**；当OCR候选被改写或换原PDF时，旧草稿哈希自动失效，必须重新生成。校勘界面的新按钮可以复制已匹配来源的草稿及不确定字/图谱说明，但人工确认勾选始终清空，仍需比对原图再签署。
- 整书完整质量门仍要求对原图的真实复核、词句错序及古籍图谱核查。**`blank/figure_only`是Agent暂时分类，不是事实或人工非文本页已归档。** 对于没有可信整页转录的页，不能计算已通过的整书CER，也不能凭AI输出直接视为仓颉来源充分。

### 在Windows本地使用（Faceface仓库根目录）

准备两份**固定1925扫描PDF**：`C:/faceface-corpus/scans/part1.pdf`、`part2.pdf`（从M16.1两个Commons原件取得，未复制其它版本）。本地需Python3.10+、Poppler的`pdfinfo.exe/pdftoppm.exe`；安装 Ollama Windows客户端并通过其官网下载免费开源视觉模型（磁盘/RAM占用取决于选择的模型，**不需要租用云服务器**；实际推理性能仍取决于你本机硬件）：

~~~powershell
# 下载视觉模型（一次性，需网络；下载后默认本机推理）
ollama pull qwen3-vl:4b
ollama list
# 如Ollama未作为Windows应用在后台启动，另开终端运行：ollama serve

# 先为全部268页建立真正的来源索引（不需视觉模型、不产生AI文字）
python -m scripts.cangjie_vision_agent_batch --mode plan --source all --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --draft-dir C:/faceface-corpus/agent-drafts

# 从带有已有原文出处的页面做3页真实质量试验（需本机视觉模型，草稿未审核）
python -m scripts.cangjie_vision_agent_batch --mode run --source nlc-44091 --start 27 --end 35 --max-pages 3 --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --draft-dir C:/faceface-corpus/agent-drafts --model qwen3-vl:4b

# 质量合适后同一命令改为处理全书；已经存在且有效的草稿会自动跳过
python -m scripts.cangjie_vision_agent_batch --mode run --source all --keep-going --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --draft-dir C:/faceface-corpus/agent-drafts --model qwen3-vl:4b

# 打开本机人工校勘台，直接载入模型草稿，并逐页与真实扫描原图核对
python -m scripts.cangjie_page_review --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --draft-dir C:/faceface-corpus/agent-drafts --port 8765

# 不修改原典，按“未辨认文字/图谱/空白/破损/来源失效”生成本机复核任务表
python -m scripts.cangjie_vision_draft_audit --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/ocr --reviewed-dir C:/faceface-corpus/reviewed --draft-dir C:/faceface-corpus/agent-drafts --model qwen3-vl:4b --out C:/faceface-corpus/agent-drafts/review-priority.json
~~~

用浏览器打开 `http://127.0.0.1:8765`。原PDF、OCR候选与模型草稿均在你的本机工作区，不被推送到GitHub。低质量Tesseract OCR**不强制作为模型输入**：可先留空`ocr/`目录，只用图像出草稿；如用OCR作为辅助，必须依M16.2写出来源哈希一致的文件。

**复核优先级输出：** [`cangjie_vision_draft_audit.py`](../scripts/cangjie_vision_draft_audit.py) 会按每页未确定字、图谱/非正文分类、OCR来源问题及模型草稿失效进行排序，并只在模型草稿与已核对V5来源页匹配时计算**原文短句诊断召回**；这些指标不证明OCR全文正确，也不会主动签署任何页面。

**本轮真实CI覆盖口径：** GitHub Actions实际下载原版两份PDF、核实源文件并生成268个任务，从两份原PDF渲染图片，另用**本机模拟的Ollama HTTP服务**测试图像base64、JSON Schema、续跑、失效与不晋升。**CI并未下载运行Qwen3-VL或执行268页AI转录，也未取得任何真人完整页校勘（0/268）**。只有本地用户启用实际模型运行后才会产生真实Agent草稿；必须提供运行报告而非口头宣称。

## M16.7｜已在真实1925原版两份PDF完成PP-OCRv5整书识别，并建立未校勘语料到官方仓颉分块的连接

**实际工程：[PR #29](https://github.com/Justalittlebittt/Faceface/pull/29)。**

- **[真实全书 OCR Action #44058499243](https://github.com/Justalittlebittt/Faceface/actions/runs/44058499243)**：使用固定原版的两份扫描文件，六个独立分片执行 **PP-OCRv5 真实CPU推理268/268页**；268页均有非空候选，共 **53,977个未经校勘汉字**。精确SHA256、零起页ID和页数审计通过；没有遗漏或重复页，`human_reviewed_pages=0`、`full_book_agent_extraction_performed=false`。过去Tesseract产字51,101，但不能从53,977比51,101多推断整页识别更准确。
- **为何不选2B视觉模型为主OCR：** [真实四页Qwen转录CI #44054742425](https://github.com/Justalittlebittt/Faceface/actions/runs/44054742425) 只有1/4页得到符合结构的全页草稿，3页因长JSON输出被截断；成功页检出了该页2/2段已核查短句，但不能推断该页准确率。缩减输出的单页试验也失败。改为版面分类后[3/3页输出有效JSON](https://github.com/Justalittlebittt/Faceface/actions/runs/44058070763)，却**3页全部表示`uncertain`**。因此不继续消耗免费CPU让小型VLM写长篇原文；保留其后续辅助高风险图谱工作的可能，正文采用PP-OCRv5候选。
- **[真实OCR脚本](../scripts/cangjie_paddleocr_candidates.py)** 可在用户Windows本机对全部两份原书持续生成 `paddle-ocr/transcripts/nlc-44091/027.txt` 等候选，逐页保存正确的原PDF SHA256、`candidate_text_sha256`、OCR引擎及置信度字段，且全部 `requires_manual_page_review=true`、`eligible_for_cangjie_verified_corpus=false`。**运行于GitHub Actions的识别原文只存在临时Runner；没有持久公开仓库或长期私有工作区**。应在本机工作区运行以下命令，才能实际保留53,977字规模的可续跑研究语料，产生数字可能因模型包及环境改变。
- **[私有仓颉工作语料组装器](../scripts/cangjie_working_corpus.py)** 从两份原PDF、逐页来源匹配的候选及人工已核实原文，生成`working-corpus-OCR-UNVERIFIED.md`和每页状态台账：`ocr_unreviewed/reviewed/missing_or_invalid`。带 `--cangjie-root` 时验证固定Cangjie commit并真正运行其原版 `scripts/build_chunks.py`。**[CI #44059580189](https://github.com/Justalittlebittt/Faceface/actions/runs/44059580189) 已执行原版chunker并产生2个仅供联调的未核验chunk**，尚未让官方Agent实际读完整268页语料，未进行Adler/五类Agent候选提取。
- **进入下一阶段的具体策略：** 允许未校勘的全文用于仓颉 **`source_unverified`候选挖掘**，而非必须先让人手打/审核全部268页；对最终准备让照片触发的每条古籍形态规则单独核原页，核对旧字形、必要及干扰条件，只有通过的人像可见条件才纳入版本化发布库。纯图谱/模糊页必须标记，绝不把机器文字冒充原著确证内容。印刷五卷与这两份扫描PDF的页码映射仍是单独缺口。

### Windows / Codex：将已成功跑通的全书OCR在私有目录持久化并生成仓颉输入

在Faceface项目仓库根目录运行；确保同一1925年版本的`part1.pdf`和`part2.pdf`保存到`C:/faceface-corpus/scans/`，电脑已装Python3.11及Windows Poppler（`pdfinfo.exe`、`pdftoppm.exe`可在PATH找到）。经PaddleOCR官方文档验证的CPU版本安装命令为：

~~~powershell
python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install paddleocr==3.3.2 pyyaml
$env:PADDLE_PDX_MODEL_SOURCE="BOS"
python -c "import paddle; print(paddle.__version__)"
~~~

执行两份固定PDF全文识别（**本机模型及Poppler运行需实际验证，不把Linux CI成功冒充用户Windows已安装通过**）：

~~~powershell
python -m scripts.cangjie_paddleocr_candidates --scan-dir C:/faceface-corpus/scans --out-dir C:/faceface-corpus/paddle-ocr --source nlc-44091
python -m scripts.cangjie_paddleocr_candidates --scan-dir C:/faceface-corpus/scans --out-dir C:/faceface-corpus/paddle-ocr --source nlc-44092
~~~

取得官方仓颉已审核的固定版本并组装私有研究语料：

~~~powershell
git clone https://github.com/kangarooking/cangjie-skill.git C:/faceface-corpus/cangjie-skill
git -C C:/faceface-corpus/cangjie-skill checkout a28de55ba881b9928956a55048f743f7a9e3b23e
python C:/faceface-corpus/cangjie-skill/scripts/cangjie.py doctor
python -m scripts.cangjie_working_corpus --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/paddle-ocr --reviewed-dir C:/faceface-corpus/reviewed --out-dir C:/faceface-corpus/cangjie-working --cangjie-root C:/faceface-corpus/cangjie-skill
~~~

**私有目录的长文本没有在公开GitHub发布，仓颉确定性分块也不等于五类Agent蒸馏。** M16.8应对这份有268页覆盖状态的`source_unverified`工作语料运行官方Adler和五个独立提取器，输出候选及覆盖审计，之后来源抽检并选择可由正脸/侧脸照片触发的条目；只验证拟上线条目，不将全书人审当成知识候选挖掘阻塞。

## M16.10｜真实原PDF目视短句对照与照片可观察条件分离

**已执行的真实源页质量门**：[M16.10专项Action](https://github.com/Justalittlebittt/Faceface/actions/runs/44243091232) · [直接原图短句初读数据](../research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json) · [真实逐句检出统计](../research/M16_10_REAL_ORIGINAL_PHRASE_PROBE_RESULTS.json) · [11页原图主题直读](../research/M16_10_ORIGINAL_PAGE_SPOTCHECK_LEDGER.json)。

- 第一份1925 PDF的数字零起页27、36、86、87与第二份PDF的76、96，已**直接查看原始PDF图像**，从图中初读13个传统形态短句：例如口部轮廓、口角方向、唇厚、鼻梁直线形态、眼部描述、面部额头和眉额、颜面色泽。这是AI图像初读短片段，不是有人签署的全页校勘。本文本也不是新的可上线面相规则。
- 对两份来源SHA256做一致性核对，真实在六张PDF原图上重跑**PP-OCRv5 170dpi**；将13个初读的原书短句逐字汉字规范化、逐页/逐OCR行对照。**同页完整检出6/13，同一OCR行完整检出仍6/13**，另7/13未完整检出。特别是**「口須方大」和「兩頭略仰不垂低」**在原图上可辨，但没有以完整字符串从本轮OCR检出；有用候选漏检或错字不可忽视。**6/13不是整书字符准确率；本任务没有计算OCR的CER，也未抽样检验全部922次词汇命中的实际精准率。**
- 13条短句已明确照片条件：**4条与现有口宽/口角方向/唇部厚度存在局部观测方向，1条仅弱对应眼部开合，8条目前无法由人脸关键点推出**。OCR完整检出的6条里，**只有2条能与当前唇厚照片测量存在局部对应**。不根据「鼻梁端直」偷换成鼻宽、不根据颜色/光泽推人格健康/寿夭、不根据漫画式口型图谱确诊完整古代象形相型。
- **研究输出只存布尔检出、来源页码及SHA**，不公开当前运行时的OCR全文、PDF大图或私有候选短句。对有图示的原始页面，原文的图谱标签与民俗人生判词要单独分类，不可从两个几何比率随意推出全相型。

Windows／Codex可在已部署PaddleOCR+Poppler的本地工作目录复现实测（输出与临时OCR候选仅写到用户私有目录，文件可保留供后续做源页校勘）：

~~~powershell
python -m scripts.cangjie_original_phrase_probe --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/m16-10-real-ocr --source-anchors research/M16_10_ORIGINAL_IMAGE_PHRASE_PILOT.json --out C:/faceface-corpus/m16-10-anchor-quality.json
~~~

**后续M16.11不能再次盲目让小模型做35次空提取。** 先从上面的7条未检出原图短句中优先攻克与照片特征接近的口宽/口角与眼部文字，研究**右向左竖排列序、局部图像裁切、灰度/阈值、OCR对原始小区域**的影响；用同一批原图13条作为前后固定的检出质量门。对真正进入报告的条目再按原图+条件核验，并区分图谱符号、表情和妆容；绝不直接用文字出现在OCR中来声称古籍断言科学正确。

## M16.9｜已实现：六区域原典短词句预筛，不再重复空转仓颉小模型

**程序**：[原文词句预筛](../scripts/cangjie_morphology_mine.py) · [268页来源审计](../scripts/cangjie_morphology_audit.py) · [六片真实OCR+挖掘CI](../.github/workflows/cangjie-morphology-mine.yml) · [PR #31](https://github.com/Justalittlebittt/Faceface/pull/31)。

M16.8真实实验已经表明：35次按仓颉五类角色运行的语言模型提取请求（Qwen2.5 1.5B两种方式合计30次、Qwen3 4B一次5次），全部**0条通过指定OCR页的来源短句验证**；不能把模型调用成功当成“整书提取成功”。因此先复用M16.7真正成功的两份1925版PDF共268页的PP-OCRv5候选文字，在**不调用任何语言模型**情况下，形成6个面部区域的可查原页短句线索。

- **眼、鼻、口、耳、眉、面部结构**六类区域，优先通过“鼻梁、眼尾、口形、耳轮、眉尾、印堂、天庭、地阁、颧骨”等可描述部位的**多字词**查找；单字“眼/鼻/口/耳/眉/面”仅在邻近“长、短、方、圆、厚、薄、上翘、细、宽”等形态描述词时列入候选，尽量避开“人口、门口、项目、目的、前面”等非面部用法。不会凭单字匹配硬凑一条古籍规则。
- 候选条目保存在私有`private/<source>/p000-152.jsonl`等文件：包含**短段OCR文本（仅供校对）**、所属面部区域、匹配来源词、原PDF SHA256、PDF零起页码、原OCR候选SHA256、OCR行号和行内容哈希、候选编号、列序与图示风险；全部标记**`OCR_UNREVIEWED`、`is_a_substantial_book_rule=false`、`original_image_reviewed=false`**。它只是定位古籍描述的**搜索索引**，不证明文字正确，更不证明相术断语科学有效。
- 每个CI分片只上传**`metadata/`**，不上传含原书文字的`private/`、原始PDF或图片。跨六片审计必须覆盖全部268页、绝不允许漏页/重复页，且只有来源哈希、类别和数量成为公开统计。M16.7时临时执行的OCR没有持久保留在私有目录，因此要在本地长期使用时须在**Windows/Codex本地**执行下面的OCR和预筛命令，不能误称GitHub Action产生了永久保存的内容索引。
- **排序思路**：先检查具有多区域词句的原图页，区分正面/侧面能观察到的轮廓描述与图谱、毛发修整、化妆、表情和拍摄角度等不稳定因素；眉部保留较低投入，不作为内容覆盖的核心。真正准备接入网站的单条语义规则再核原图与条件。**不应把“命中多少个OCR短句”说成已经提取了多少条传统面相规则。**

在Windows/Codex保持上一节的实际原PDF与已生成的`C:/faceface-corpus/paddle-ocr/transcripts/`后：

~~~powershell
# 对第一份原PDF的153页生成短句索引（需本机已有有效OCR及来源哈希）
python -m scripts.cangjie_morphology_mine --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/paddle-ocr --out-dir C:/faceface-corpus/morphology-index --source nlc-44091 --start 0 --end 152

# 对第二份原PDF的115页生成短句索引
python -m scripts.cangjie_morphology_mine --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/paddle-ocr --out-dir C:/faceface-corpus/morphology-index --source nlc-44092 --start 0 --end 114

# 通过已核实的原页编号定位原书图像，对候选做人工抽检，不要自动上线
python -m scripts.cangjie_page_review --scan-dir C:/faceface-corpus/scans --ocr-dir C:/faceface-corpus/paddle-ocr --reviewed-dir C:/faceface-corpus/reviewed --port 8765
~~~

下一步在这份**source_unverified原始短片段池**上做多卷/多区域原图抽查：首先排除OCR错字、跨列错序和无意义命中；然后对通过原图核查的有效片段，结合仓颉原版Extractor进行**语义归类、条件和例外蒸馏**。不能把“借助仓颉的方法论”冒称“已经完成仓颉整本五路Agent语义提取”。面向国际用户的Faceface拍摄与历史文化解释界面保持不变。

## 首个实施批次（执行而非长期只出计划）

**一次走通“扫描底本来源映射 → 原页文本/图谱归档 → 官方仓颉5类提取 → 来源/覆盖审计 → 统一JSON候选 → 批量导入dry-run”完整链条**。同一链条跑通后，按剩余章节自动批处理，不能回到单条人工增量。先由实际可用扫描文件确定任务分片范围，不凭空编造底本页数或条目总数。
