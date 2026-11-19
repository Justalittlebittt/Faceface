# M16.17 — 仓颉古籍形貌—传统断语关系提取

本轮将“只出概念”的 M16.13 试验，扩展为能从真实短篇古籍引文分别提取**相貌特征、传统断语、条件、例外**的模型入口。

## 真实模型入口与现有来源

`scripts/cangjie_real_historical_relations.py` 复用 `cangjie_clean_source_agents.py` 已证实可用的 localhost Ollama 客户端、1925年两份原版PDF的 SHA 和 13 条 V5 既有短句，以及固定 `a28de55b...` 仓颉官方源码的 `glossary` 和 `principle` 两种角色提示片段。该入口请求真实本地 `qwen3:4b-instruct` 模型逐段输出结构化关系。

若某条原文**只有形态，没有财富/寿命/品德等断语**，相关断语留空，领域为 `none`；绝不要求模型凭传统常识填补缺失结果。模型必须给出在原输入古文中**逐字连续出现**的形态、断语、条件、例外字符串；超出原文的短语一律拒绝。结果保存至 M16.16 标准的历史断语关联档案，记录领域（含财富、寿命、品德等），未被照片测出的内容仍保留。

## Windows 本机执行（需 Poppler、两份固定原始PDF、Ollama Qwen3 4B、官方固定仓颉源码）

```powershell
python -m scripts.cangjie_real_historical_relations --scan-dir C:/faceface-corpus/scans --upstream C:/cangjie-skill --private-dir C:/faceface-corpus/private/m16-17 --public-metadata research-local/m16-17-aggregate-only.json --model qwen3:4b-instruct
```

`--upstream` 必须是真正 checkout 到项目固定 SHA 的官方仓颉源仓库；无需且不得将私人扫描或古籍完整OCR候选放入公开仓库。模型解释与古文原文只在私有目录；指定的外部 metadata JSON **只含统计、领域计数，不含原文**。该程序不修改线上网站规则，也不保存任何用户人脸信息。

## 验收边界

- 现有13条V5引文属于先前的AI原图视觉核对短句，而非新的独立人工签认原文。即使模型从中抽出逐字可见的“富贵”字样，**也只能作为待审核历史候选**。
- 本 PR 新增真正的 Ollama 调用代码及纯模拟响应的测试，不把模拟调用说成已发生的模型运行；CI测试通过只代表源文门禁逻辑正常。
- 两段仓颉官方角色提示采用固定版本原文件**节选**，不是再执行完整五Extractor语义工作流，也不声称完成全书268页蒸馏。
- 原文之外的现代解释、健康/道德/财富的个体事实判断一律不从模型输出进入个人报告。
- 后续需要对真实古文来源进行独立校勘、取得模型运行证据、对照断语与形态适用条件并做最终展示审核，不允许直接批量激活报告。
