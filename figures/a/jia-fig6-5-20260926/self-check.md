# 图 6-5 自查记录（甲，v1，2026-09-26）

## 实际执行结果（本会话为该目录唯一写者，开工回执 5847109716）

- 命令（两步，工作目录=仓库根，退出码 0）：
  1. `.venv/Scripts/python.exe figures/a/jia-fig6-5-20260926/extract_inputs.py --audit-json <prefix-realized-path audit.json> --evidence-tar <evidence.tar.gz>`——显式路径参数，三项固定哈希核对（audit bcdb051a…、tar a923a07f…、成员 official-p3.json.gz 解压前 d4cdf8db…），不符即中止不产表，生成四张交付 CSV。
  2. `.venv/Scripts/python.exe figures/a/jia-fig6-5-20260926/plot.py`——只读交付包内四张 CSV 复现图件；内置断言（40 前缀 op 全 cold COPY_IN、逐前缀 max(end)==official_finish、关键路径 366 节点 start/end 与 per_core_timeline 一致、分项贡献+cross_lag==38,024、excess==8,244==38,024−29,780、prefix2 op_id 序列==关键路径开头）。

## 逐项对应派发单（5847092768）

1. **固定 044/k5 计划绑定记录**：输入为 28e8c7dd 的 prefix-realized-path audit.json（plan_sha256 13914b24…、official_result_sha256 d4cdf8db…、op_count 1,678、edge_count 3,992 与其 source_archive_sha256 一致）+ evidence.tar.gz（成员官方结果实测同哈希）。定位值 29,780/36,592/38,024 全部从固定来源读取并断言，未手填。
2. **四条冷读前缀 + 后继事件 + 已核路径**：prefix_ops.csv 40 行（每前缀单核、全 miss；端点=official_finish）；critical_path_ops.csv 366 行含 minimum_duration/incoming_lag（跨核等待以入边等待呈现，路径行内为空隙）；后继事件以关键路径行 + 仅前缀 2 的证据连接线呈现（其 7 次冷读与关键路径开头同 op_id 序列，plot.py 断言），其余连接不画。
3. **甘特只连有证据的路径关系**：前缀内操作按 start 排序绘制（fifo 相邻），前缀间/前缀-关键路径连接仅画有同 op_id 审计证据的前缀 2 一条。
4. **三类证据点图**：evidence_points.csv 15 行（5 对象 × 3 类）；乐观独占值（○）、条件共享模型界（□）、官方实测（◆）三种标记；对数横轴；同一对象三点以淡虚线相连表示口径推进；图例与图注明确"模型值/研究界/官方实测"，未画成实测柱。
5. **口径**：三类数为同一对象三种口径的声明写入 x 轴标签与图注；36,592 的适用限制（固定前缀/归核/Task、非剪枝证书）、29,780 不用于预测新方案、单格不进全量成绩，均已写入图注；无"带宽利用率""实测 DDR 等待"表述。
6. **数值身份说明**：随包 path_contributions.csv（关键路径分项：COPY_IN 16,862/COPY_OUT 47/CONV 16,512/RELU 2,233/ADD 1,370/跨核等待 1,000/超最小时长部分 8,244）。
7. **图面检查（165 mm 插入宽度）**：preview-insert-width.png（624px）目检——两面板行标签/图例/数值标注完整不截切、图例位于留白不压数据、面板 B overall 行三标注分离；PNG 300 dpi 局部放大复核。

## 缺口

- 无（两项固定来源哈希核对一致；0 新 solver/Task/E0/E1/E2，未重跑任何官方评价）。

## 版本

- v1：初版交付（本目录全部文件，哈希见 audit.json）。
