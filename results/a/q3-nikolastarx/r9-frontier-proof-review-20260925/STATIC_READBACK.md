# 独立静态复算当时输出

`STATIC_RECHECK.py` 是本轮先前三条只读 Python heredoc 的整理稿；下列输出逐字抄自当时工具回读，**没有为补原件重新执行**。检查只读原图、plan、evidence 与 metadata，未调用官方 Task/Step/E0 或 R9 constructor。整理稿将三段检查合成一文件，故不是先前命令的字节级副本。

```text
005 raw 4209 4298 11187 eligible 4113 mapping 4113 ownership 4113 noout 0 plan-keys ['node_to_subgraph', 'core_schedules'] meta-matches True owner-coverage True mp-coverage True
086 raw 5372 5462 14290 eligible 5274 mapping 5274 ownership 5274 noout 0 plan-keys ['node_to_subgraph', 'core_schedules'] meta-matches True owner-coverage True mp-coverage True
005 frontier_match True peaks [[15168, 21844], [14976, 21844], [14976, 21844], [40288, 23668], [40288, 23668]] cross_bad [] cross_phase_count {(0, 1): 35, (2, 3): 152, (0, 4): 5, (5, 6): 152, (0, 7): 5, (8, 9): 152}
086 frontier_match True peaks [[16320, 27604], [16128, 27604], [33408, 52852], [43456, 38164], [44416, 38164]] cross_bad [] cross_phase_count {(0, 1): 42, (2, 3): 200, (0, 4): 6, (5, 6): 200, (0, 7): 6, (8, 9): 200}
005 priority_cover True word_cover True backward 0 max_cross 4 reported 4
086 priority_cover True word_cover True backward 0 max_cross 4 reported 4
```

注意：上述脚本重算 H_seq crossing，但使用 R9 evidence 中的归属与全局 priority；它不证明 evidence 自身由原图正确生成。新的 `src/q3/layered_prepared_guard.py` 专门读取未来 captured Task/Step2/Step3 原件并重新建联合图。071 的既有 prepared 只用于校准序列化格式与只读回归，不构成 R9 005/086 官方验证。
