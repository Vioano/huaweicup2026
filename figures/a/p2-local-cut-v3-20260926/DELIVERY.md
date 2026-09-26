# FIG-P2-LOCAL-CUT · 图件交付

- 固定算法：`c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`。`src/q2_nikolastarx/binary_hypercut.py:144-195` 给出固定核心集合、辅助边、常数偏移与原目标的相等校验；`:198-258` 给出计算流水线工作量上限的固定与重求；`src/q2_nikolastarx/gap_hyperrefine.py:87-145` 给出至多 16 条链的区域、原始 COPY 字节数严格下降才接受及该步骤的范围限制。
- 文件：`build_local_cut.py` 确定性生成可编辑 `p2-local-cut.drawio` 与逐元素 `semantics.json`；`p2-local-cut.svg` 为矢量导出，`p2-local-cut.png` 为图像导出，`preview-160mm-300dpi.png` 为约 160 mm 宽、300 dpi 的纸面预览；`CAPTION.md` 为候选图注。
- 重建：运行 `python3 build_local_cut.py`，用 Draw.io Desktop 对 `.drawio` 分别执行 `drawio -x -f svg` 和 `drawio -x -f png -s 2`；预览由 `sips -Z 1890 -s dpiWidth 300 -s dpiHeight 300` 生成。若手工改动 Draw.io 图，须同步生成器或注明新的编辑源。
- 核查：按固定源码逐条核了 `F=∅` 和 `F={a,c}` 的偏移及容量；Draw.io 导出成功、XML 可解析；实际查看原图和约 160 mm 预览，修正了最初计算流水线节点的文字溢出。未运行求解器、官方评价器，也未生成新的实验数据。图注、正文适配、Fang 选版及最终科学验收仍待论文组织任务核查。
