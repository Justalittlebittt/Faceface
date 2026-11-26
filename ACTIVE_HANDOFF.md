# Faceface 当前交接
更新：2026-11-26；开发基线：M16.18 侧脸技术选型。

## 核心目标
免费、手机优先的国际面相文化网站。真实可观察形态→古籍有出处的传统解读→简洁默认报告／详细来源报告。历史观点不作为个人经历、性格或未来事实的可靠推断。英文优先，中文可切换；默认不上传或保存人脸。

## 当前状态
- 已有 Web 实验站：https://justalittlebittt.github.io/Faceface/
- 手动快门与顺时针绿色轮廓交互已获用户认可，保持不变；当前正式文化卡10张。
- 1925版两份原书共268页已完成OCR预筛，205页有922个词汇线索，并非规则。
- M16.13：13条已有短引文，真实仓颉五角色全部完成，4条草稿仅涉及3个已有框架；新增可上线规则为0，整页真人校勘0/268。
- 证据：PR #35；Actions run 44463236836；research/M16_13_REAL_CLEAN_FIVE_EXTRACTORS_VERIFIED_PILOT.json。

- M16.14–16：眼鼻耳等16条研究候选已存档，但原图截图证据未能在当前执行环境独立确认；不得视作已核实引文。无新增正式卡或仓颉运行。
- M16.17：检查 src/descriptors.ts，现有10个正脸比例字段无耳部关键点；详细报告增加中英文耳部未测量说明。前端改动未运行构建或部署验收。

## 下一项
M16.18选型：保留正脸MediaPipe；侧脸面部优先实测姿态矩阵及可见轮廓，大角度失败再评估3DDFA_V2（模型资产许可待核）。耳部优先独立试验 shameem4/Ear_Landmarker 浏览器ONNX演示（55点；上游自报两阶段检测召回78.6%，不是本站性能；NOTICE披露旧训练数据衍生标注许可争议，商用前须核实）。来源：https://github.com/shameem4/Ear_Landmarker 、https://github.com/cleardusk/3DDFA_V2 、https://github.com/google-ai-edge/mediapipe/issues/4773 。下一批先验证真实侧脸及遮挡情况下检测是否成功、左右镜像及可见性；仅输出可观察形态，不推断性格经历命运。模型尚未接入或测试；保持现有拍照流程不变。

## 按需索引
- docs/STATUS.md：历史证据，默认只读相关段落。
- docs/PRODUCT.md：产品约束；docs/DECISIONS.md：历史决策。
- docs/KNOWLEDGE_BASE.md：知识库；docs/CANGJIE_BATCH_RUNBOOK.md：本机执行（路径以仓库实际文件为准）。
- docs/WEB_ARCHITECTURE.md：前端；docs/PRIVACY_AND_LAUNCH.md：隐私上线。
- README.md：公开说明，不作为每轮必读入口。
