# contest_figures — 甲方绘图脚本组织

本目录集中管理 A 题甲方（farmeruncle123）名下 10 组图的**全部绘图脚本**。
后续会有一轮「数据替换」优化：数据更新后重跑本目录脚本即可全量重绘，不改脚本逻辑。

## 原则

1. **数据路径集中**：所有输入路径写在本目录 `data_paths.py`（或脚本顶部常量区），换数据只改一处。
2. **一图一函数**：每个图号对应一个 `fig{N}-*.py`（或 make_all.py 内一个函数），输出到 `figures/a/jia-fig{N}-*/`。
3. **变体命名**：`fig{N}-{name}.{variant}.ext`，例如
   - `fig3-speedup-curves.line.pdf`（经典折线）
   - `fig3-speedup-curves.heat.pdf`（热力图风）
   规范版（用于验收基线）不带 variant 后缀；美化变体带 variant，供论文挑选。
4. **口径不变**：换数据不改语义——Makespan=cycles、耗时=s、搬运量=B/MiB；平均加速比=逐例比值算术平均；缺数据登记缺口，不造数。
5. **可复现**：脚本内记录输入哈希与生成命令，配合各图目录 audit.json。

## 文件清单

| 文件 | 职责 |
|---|---|
| `make_all.py` | 赛题四图（仿赛题插图）生成器，输出 `figures/a/contest-figures-20260925/` |
| `styles.py` | 全局样式：字体（Microsoft YaHei）、配色群组、变体主题（classic / modern / heat） |
| `README.md` | 本说明 |

## 视觉变体策略（2026-09-26 用户要求：每图多做类型供挑选）

| 图 | 类型 | 计划变体 |
|---|---|---|
| 4-1 / 4-2 / 5-1 / 6-1（drawio 结构图） | 双层流程 / 三联 / 分支 | classic（规范版）、modern（卡片渐变+阴影）、compact（窄版可读性优先） |
| 4-3（配对甘特） | 时间线 | classic 甘特、heat 时间热力条、泳道面积 |
| 5-2（生命周期+占用） | 区间+阶梯 | classic、heat 填充阶梯、双面板合并版 |
| 5-4（正反例拼版） | 组合 | 时间线/散点各 2 种配色主题 |
| 6-2（阶段切分条带） | 条带+容量 | classic、heat 条带 |
| 6-5（冷读前缀甘特） | 甘特+点图 | classic、modern |
| 6-6（对齐时间线） | 时间线+放大窗 | classic、modern |

## 数据替换工作流（下一轮优化）

1. 更新 `data_paths.py` / 脚本常量中的输入路径或文件；
2. 重跑对应 `fig{N}-*.py`（或 make_all.py）；
3. 重算 audit.json 中哈希（模板见各图目录）；
4. 图注中的数据版本号同步更新。

## 工具

- matplotlib（项目 .venv，Agg 后端）
- draw.io CLI：`"F:/draw.io/draw.io.exe" --disable-gpu --no-sandbox -x -f svg|png ...`
- 结构校验：`F:/WorkBuddyData/skills/drawio-skill/scripts/validate.py`
