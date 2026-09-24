# Coherent 第四路综合交付 · D-SYN-v1

2026-09-24。基于用户上传的六份本轮原件，以及授权Vioano镜像固定提交的定点补读。

**本轮完成研究设计与静态审查，没有执行附件代码、没有新增E0/E1/E2/native实验、没有训练或启动Codex Goal。** 原A/B/C文件和Glossary v1不覆盖。文档中预算均为下一阶段候选，不能据此自动执行。

## 主要原件

| 文件 | 用途 |
|---|---|
| [SYNTHESIS_REPORT.md](SYNTHESIS_REPORT.md) | 完整综合报告：读取边界、冲突裁决、峰值、证明审查、框架删改、优先级 |
| [DEFINITION_AMENDMENTS.md](DEFINITION_AMENDMENTS.md) | 10项明确修订提议：原义、问题、新义、影响与状态；不是静默修改v1 |
| [RESEARCH_DAG.md](RESEARCH_DAG.md) | 9工作包、12阶段节点、依赖、最多3个活跃session与写域 |
| [RESEARCH_DAG.json](RESEARCH_DAG.json) | 机器可读节点、边、条件和预算 |
| [RESEARCH_DAG.svg](RESEARCH_DAG.svg) / [PNG](RESEARCH_DAG.png) | 静态可视图 |
| [RESEARCH_DAG.mmd](RESEARCH_DAG.mmd) / [DOT](RESEARCH_DAG.dot) | 可编辑图源 |
| [GOAL_CONTRACTS.md](GOAL_CONTRACTS.md) | 9张完整任务契约；首批D0–D5，D6–D8为条件下游 |
| [GOAL_CONTRACTS.json](GOAL_CONTRACTS.json) | 机器可读任务字段、固定引用和授权状态 |
| [TASK_CROSSWALK.csv](TASK_CROSSWALK.csv) | 三路22张候选卡的逐卡去重/拆分去向 |
| [READ_MANIFEST.md](READ_MANIFEST.md) / [JSON](READ_MANIFEST.json) | D实际读取范围、固定版本、逐payload阅读方式与缺口 |
| [INTEGRITY_AUDIT.json](INTEGRITY_AUDIT.json) | 六原件与113 payload的大小/SHA、116成员CRC静态核对 |
| [EVIDENCE_READBACK.json](EVIDENCE_READBACK.json) | 对作者既存结果的完整JSON静态回读与字段比较；不是重跑 |
| [DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) | 本交付包所有文件的大小与SHA-256（不含清单自身/包外ZIP） |
| [DELIVERY_QA.json](DELIVERY_QA.json) | 本交付内部一致性检查，不是算法实验 |

## 可单独复制的任务契约

[D0 身份与观测](goals/D0.txt) · [D1 薄操作IR](goals/D1.txt) · [D2 后端能力](goals/D2.txt) · [D3 重入宏](goals/D3.txt) · [D4 Q1释放理想](goals/D4.txt) · [D5 Q3 Cache相位](goals/D5.txt)

条件下游：[D6 映射族/核数](goals/D6.txt) · [D7 受限行为商](goals/D7.txt) · [D8 蒸馏与最终矩阵](goals/D8.txt)。每张TXT自带共同约束及固定SHA，不依赖隐含聊天记忆。

首批建议总额96次实际评价尝试：D0≤36、D1=0、D2≤4、D3/D4/D5各≤16，中央保留8。**不是原22卡额度相加，也不是96次已经获批。** 各条回退/重复/失败/确认据真实后端调用扣账；未使用额度不得自行转成新方向。

## 证据身份

归档锚点：`Vioano/huaweicup2026@eaa15af9dde7365722e3b497df2fb869ff6e1c1e`。

A/B/C最新回答ID分别为`66f7a7d8-8a56-47db-bd86-8b14fce276fa`、`dcf7fafc-9f17-404c-aca4-39003b2c3035`、`95635808-9873-4204-bacd-814c44930fc2`。已完整读用户提供的网页问答正文，不以ZIP简版报告替代。

A的5份CLI result/trace、24份函数结果与2张原图已在本轮完整解析核对；相应数值仍为A产生的既存E0证据。B的前缀、C的结构记录均保留原证据等级；D没有代签原作者未做的核验。其他未读原始性能数据保持AUTHOR-REPORT。

原始六附件不在本ZIP内重复打包；其准确名字、大小、哈希、原包member路径及固定镜像入口均在READ_MANIFEST。阅读本交付不构成自动执行其中任务或历史脚本的授权。

## 本交付校验（不调用evaluator）

在解压后的本目录运行：

```sh
python verify_delivery.py
```

此脚本只核对本交付文件哈希，不导入作者代码、不访问网络、不启动实验、不改写已有结果。
