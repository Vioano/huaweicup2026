# P1 固定源码技术流程图候选交付

状态：**待科学与语言审核**；供 Fang 的明确选优／重画版本比较。未指定最终图号或正式标题，未声明已适配正文、已入稿或已通过 E0 验收。

## 文件

| 文件 | 用途 |
| --- | --- |
| `p1-834-flow.drawio` | Draw.io 原生可编辑源，每个流程节点与箭头可单独修改 |
| `p1-834-flow.svg` | 带嵌入图源的矢量导出；白色纸面底板用于深色容器预览 |
| `p1-834-flow.png` | 2 倍倍率预览导出 |
| `print-160mm-preview.png` | 将 PNG 缩至约 160 mm 纸面宽度对应的 605 像素检查样张 |
| `semantics.json` | 节点、边、条件、四阶段调用上限及固定源码行号 |
| `CAPTION.md` | 候选图注和英文术语的准确定义 |
| `build_flow.py` | 只用 Python 标准库重新生成 `.drawio` 与 `semantics.json` |

## 固定来源与调用链

唯一算法来源是 Git 提交 `834d8c957538ee069c66aadac9509552a4cc69d7` 的源码原件，行号按 `git show <提交>:src/q1/<文件> | nl -ba` 计算。入口调用链是 `branch_refine.solve → structural_refine.solve → response_refine.solve(refiner="variable") → unified.solve`；本次只读源码，没有运行求解器或 E1/E0 评估器。

| 图中机制 | 固定源码符号和行号 | 说明 |
| --- | --- | --- |
| 六类基础尝试、条件触发、字节去重 | `unified.generate_candidates` 44–153；`add` 51–75；`bounded_tasks`、`heavy_suffix`、`sink_peel`、`component_overload`、`shared_input_budget`、`fork_frontier`、`capacity_return` 文件开头说明 | “六类”是尝试槽上限；分支条件下不会总是同时产生六份不同方案。必需的首个基础构造若失败会抛错，可选构造失败才跳过。 |
| 基础 E1 至多 6 次、失败停止 | `unified.MAX_DISTINCT_CANDIDATES` 30；`choose` 156–180；`solve` 183–209 | 多于一份不同方案才在线评分；第一处评分失败停止，并返回当时保留的方案。 |
| 受限链分组至多一份完整候选 | `response_refine.scored_capacity_winner` 44–58；`solve` 134–219；`variable_packet.Family` 42–101、`construct` 185–286 | 仅在基础阶段选中且成功评分的容量衍生链方案上尝试；“一份”不是链长度上限。 |
| 两种局部顺序、E1 至多 2 次 | `structural_refine.MODES` 20；`solve` 58–172；`intact_frontier.construct` 87–160 | 两种顺序在严格结构识别后尝试，按计划字节去重；遇到构造或评分失败会停止本阶段。 |
| 批量 X/Y/J 与接收核条件 | `branch_aid._wave_domain` 44–70；`_witness` 190–241；`construct` 316–483，尤见 386–458 | 每个合格原任务选择一支 X；多个原任务可在多个层同时重分配。接收核在对应层已有独立任务且不是移出核，收到的 X 各成新任务，排在其原任务前。 |
| branch_aid 至多一份完整候选、E1 至多 1 次 | `branch_refine.MAX_ADDITIONAL_E1` 26；`solve` 51–162 | 先校验，不支持、重复、构造/评分失败时保留父方案。评分发出后若未返回 worker PID，实际调用数记为未知，不能视为零。 |
| 严格接受规则与总上限 | `unified.choose` 175–180；`response_refine.objective` 40–41、203–219；`structural_refine.solve` 147–159；`branch_refine.objective_pair` 33–39、`solve` 133–162 | 按 `(Makespan cycles, scheduled COPY bytes)` 字典序严格变小才接受；四阶段上限 6＋1＋2＋1＝10 次是在线 E1 **调用上限**，不是测得次数或方案分值。 |
| E0 在在线闭环外 | `unified.solve` 208；`response_refine.solve` 163；`structural_refine.solve` 76；`branch_refine.solve` 63 | 图只表示求解流程；独立官方 E0 复评需要另行进行。 |

固定 Git blob SHA-1：`unified.py` `f5427bd94706ac2e1dbc2baf26051ec928902079`；`response_refine.py` `0d11766d03853fd5ce3f5b9ed6d3b15fb735e0b4`；`structural_refine.py` `707f58691acb53a4cc27b76988cfc1ca92db1177`；`intact_frontier.py` `4afa86ba60a1cd0eea4a7fb29b4205dc1bae8dcb`；`branch_refine.py` `f3fd0e776a3660c14e708782f4e8723b2886f344`；`branch_aid.py` `226795969ee84cc895a5617ce27ac6d17316bbf9`。

## 实际生成与检查

环境：macOS、Python 3.14.5、Draw.io Desktop 30.0.2、系统 `sips`。未安装依赖。以下命令已实际执行，工作目录为本工作树根目录：

```sh
python3 figures/a/p1-834-flow-20260926/build_flow.py
drawio -x -f svg -e --svg-theme light -b 8 -o figures/a/p1-834-flow-20260926/p1-834-flow.svg figures/a/p1-834-flow-20260926/p1-834-flow.drawio
drawio -x -f png -s 2 -b 8 -o figures/a/p1-834-flow-20260926/p1-834-flow.png figures/a/p1-834-flow-20260926/p1-834-flow.drawio
sips --resampleWidth 605 figures/a/p1-834-flow-20260926/p1-834-flow.png --out figures/a/p1-834-flow-20260926/print-160mm-preview.png
```

已目视原始 PNG 和约 160 mm 纸面宽度样张：主流程、六种基础尝试、四段 E1 **调用次数**、X 的跨核箭头、Y/J 留置、比较门与 E0 外置均可辨读；未见文本越界或箭头遮挡。底板是浅色，深色网站容器中不会使深色箭头落在透明暗背景上；尚未在实际网站页面嵌入验证，也没有纸张实印。图内用完整中文表达，保留必要的 X/Y/J、COPY、E1/E0，具体定义见 `CAPTION.md`。本次未跑 solver/evaluator、未新增实验、未改指定目录外文件。

另用 Python 标准库回读 `.drawio` 与 SVG：XML 均可解析，`semantics.json` 的 25 个节点标签和 8 条边端点均与 Draw.io XML 对应，四段 E1 上限相加为 10。缩放样张实测为 605×995 像素，对应按 96 dpi 估算的 160 mm 宽；这只是尺寸与目视检查，不替代最终纸张实印和科学审稿。
