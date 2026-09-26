# 图 5-4 自查记录（甲，v3，2026-09-26）

## 实际执行结果（v3 返工，针对反馈 5847081278 的 F54-R04/R05；R01/R02/R03/R06/R07 已于上轮关闭）

- 命令（两步，工作目录=仓库根，退出码 0）：
  1. `.venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/extract_inputs.py --r05-zip <S15 result.zip> --s16-report <S16 report.json>`（与 v2 相同，未改动）
  2. `.venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/plot.py`
- CSV 未改动（与 v2 逐字节一致：R01/R02/R03 的修正全部保留）；本轮仅修 plot.py 图形逻辑与 caption/self-check/audit 文档。

## v3 修正（逐项对应 F54-R04/R05）

1. **R04-1 broken_barh 宽度修正**：确认 v2 把 (start, end) 直接当作 broken_barh 的 (left, width) 传入、实际画出宽度=end 的错误；task_by_row 与 op_by_row 两处收集全部改为 (start, end-start)。plot.py 新增几何断言：逐段 left+width==end；同 variant 全部条形终点 ≤ 各自 makespan（SUBGRAPH 26,910 段与操作 40,475 段分别检查）。修复前 recovered event 67384（PIPE_MTE3，[254507,254508]）画到 509,015、event 57557（SUBGRAPH）画到 509,001，均越界一倍；修复后全部 ≤ makespan。
2. **R04-2 子泳道**：面板 1 改为每方案每核一个泳道块，块内 PIPE_MTE2/MTE3/V/M 四条独立子行（固定垂直偏移、互不重叠、自上而下逐行标注 MTE2/MTE3/V/M），核名以两级标签（seed 核1…rec 核2）置于行标签左侧；task（SUBGRAPH）仅作浅灰整核背景；不同管道不再相互覆盖、不伪装成同一管道。整图高度 8.0→8.9 in。
3. **R04-3 端点线**：纵范围改为由 ENVELOPE 常量（所属方案两个泳道块的并集，seed [8.25,16.15]、rec [-0.45,7.45]）导出，仅贯穿本方案两块、不进图例区、不越入他方案；seed/recovered 端点仍为 248,166 / 254,508 cycles。
4. **R05 面板 3 图例**：移出轴外，置于轴下预留空白（bbox_to_anchor 上缘 -0.16、两行），底边距 0.065→0.135；不删点、不截断坐标。审查指出的 072/k5=(-209,485, 121,376,804 B)、014/k2=(-120,195, 99,704,740 B)、014/k3=(-86,650, 95,454,232 B) 三点全部保留且在主图与 165mm 预览可辨、不与图例重叠（放大裁片逐点目检）。面板 2 图例同时复核：ylim 提至 12，图例三行与 ① ② 两柱全部数值分离。
5. **几何/视觉检查（不止 CSV 断言）**：PNG（1950×2670, 300 dpi）局部放大逐面板目检——面板 1 四块八行标签完整、三行图例位于顶部留白不压条形、端点线不贯穿他方案；面板 2 图例与柱值分离；面板 3 轴下两行图例与全部散点及轴标题互不重叠；preview-insert-width.png（624px=165mm）同步更新。

## 缺口

- 无（0 新实验；CSV 与五项已关闭项未改动）。

## 版本

- v1：初版交付（97dd14fb1）。
- v2：F54-R01..R07 首轮返工（4fb9d92f3）。
- v3：F54-R04 broken_barh 宽度/子泳道/端点包络 + F54-R05 面板 3 图例轴下（本轮）。
