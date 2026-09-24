# Fang Q2 历史结果同步到方案成绩台

本包将固定 `0b58c123cccf02fc993b741d79dcd8511e4dd38f` 的 Stage B 九个已完成方法单元导出为 `board-submission-v1`。仅读取 Git 原件、核对身份和生成数据包，新增 solver/E0/E1/E2 调用均为 0。

## 六字段交付

1. **目标**：把本方已发布的 Q2 Stage B 结果交网站专责接收，区分数据送达、原件匹配、页面可见和算法验收。
2. **输入**：上述固定提交中的 `results/a/q2-yuanzhifang/stage-b-20260924-042906/` 的 summary、九份 ZIP、evidence_manifest；冻结 source-manifest 及各实际 as-run 提交。协议读至 `674ce01248c59a02ce6953809ae376193adbb192`；本轮精简未改变 schema。
3. **输出**：`board-feed-stage-b-20260924.json`、45个从原件复制/无损压缩的文件、`export-manifest.json`、可复跑只读导出脚本及预检记录。三个方法族、两版实际代码分 run；九条最终记录覆盖 P2 case002/008/044、4核，共三个格位。
4. **限制**：只新增本目录。中央网站、来源准入、注册表、Atlas 和生产算法仍归原 owner。本次不重跑、不复用封存预算，不宣称完整100图或独立科学终验。
5. **验收**：原九ZIP及1506成员的大小/SHA全部检查；输出原字节/压缩字节映射；九组计划/完整result/运行收据、冻结输入/官方源码及实际代码身份一致；新协议预检的实际输出见 `validation.json`。最终入库和页面可见须由队长网站维护会话回执。
6. **时点**：2026-09-24 本次同步；原实验开始UTC和各unit monotonic时间在原始收据，本次导出时间不作为运行时间。当前session登记：[Issue26](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814905150)。

## 数值和范围

| case / 4核 | D | M1 | M2 |
|---|---:|---:|---:|
| 002 | 132209 | 72415 | 132209 |
| 008 | 123060 | 123060 | 123060 |
| 044 | 125648 | 74530 | 69113 |

单位为官方模拟 cycles。D、M1、M2均为独立方法单元，不把最低值拼成一个通用算法实验。M1为包结构分核候选，M2固定D的核心归属改变优先级/粒度；M2没有继承M1赢家。全体122次历史E0均保留在上游ZIP与本包calls/run中，含退化候选；本次feed只展开九次方法单元的最终确认，不把122个内部调用冒充122次完整求解。

case002/008实际代码为 `9b544ad28b9515f9ab53070d457774b1d8f65a58`，case044为 `e503e61daed67c97cb09629a6f315b14cae2cca1`。之后的控制修复及导出提交都不是原运行版本。原StageB控制中断、修复前后区别及全部失败/退化细节见[固定完整报告](https://github.com/huaweibei123/huaweicup2026/blob/0b58c123cccf02fc993b741d79dcd8511e4dd38f/results/a/q2-yuanzhifang/stage-b-20260924-042906/REPORT.md)。本包不删除或覆盖其历史。

标准 `solver_wall_seconds` / `evaluation_wall_seconds` 保留 null：原记录是包含在线E0与最终确认的 controller unit，不能不加条件当作通用独立求解器的完整外层测速；也没有独立外部最终评价时间。`parameters`完整保留实际 unit wall、controller receipt wall、全部在线E0 wall、内部最终确认 wall及原阶段跨度。内部确认已包含在unit时间中，不能相加。原unit wall 2.562–39.891秒，九unit加账本181.094秒，含协调暂停的阶段跨度561.063秒；测后报告/打包不是求解速度。

未记录的逐unit UTC、CPU、RAM、线程和冷热启动保留 null 及原因；250ms采样的 Windows working-set峰值不冒充严格peak RSS。runner.argv取原controller所记录的子进程命令，runner.source为启动该controller的StageB代码；它是历史记录而非本次可直接启动实验的授权。

三个官方单核分母可由维护者按冻结身份复用其现有原件。本包未重新计算或冒充已配对，baseline比值留空。额外搬运和spill来自各完整result的原始字段；P2没有Cache命中率。

## 只读重建与预检

在包含源提交的本仓库工作区运行：

```sh
python -X utf8 results/a/q2-yuanzhifang/board-sync-20260924/export.py
python -X utf8 src/benchmark_board/protocol.py results/a/q2-yuanzhifang/board-sync-20260924/board-feed-stage-b-20260924.json --submission
```

脚本只调用 `git show`，无生产模块import，不启动求解器/评价器。已有输出若字节不同会拒绝覆盖；修订应生成新快照和revision。`.json.gz`是完整官方result的无损压缩，解压后逐字节等于源ZIP成员；manifest同时记录源ZIP、成员、原字节与压缩字节SHA。完整Trace/日志/逐候选原件仍在固定上游ZIP，不重复上传。

GitHub Actions按项目规则保持停用。实际验证平台为Windows，本包不代签其他电脑复现或网站接收。

Windows预检须启用Python UTF-8模式。首次未启用时校验器读取UTF-8 schema触发GBK解码错误；加 `-X utf8` 后9/9通过，无需修改公共校验器或原件。

原计划JSON采用CRLF；本目录Git属性关闭JSON行尾转换并将CRLF识别为正常行尾，保证提交内字节与原计划SHA不变。初次普通diff检查将CR报为行尾空白，未为消除提示改写原件。Windows无 `dot_clean`，只读扫描本目录未发现 `._*`、`.DS_Store` 或 `__MACOSX`。
