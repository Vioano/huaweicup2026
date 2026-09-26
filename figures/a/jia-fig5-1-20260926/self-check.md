# 图 5-1 自查记录（甲，v3，2026-09-26）

## 实际执行结果（本机制图环境）

- 导出：draw.io CLI（--disable-gpu --no-sandbox）rc=0，SVG viewBox 711×1032、PNG 1422×2064（scale=2）。
- validate.py：0 error；2 处纯线交叉（s1×s2、e12×s1），无文字/标签压盖。
- 页面预览：XeLaTeX rc=0，main.pdf 1 页（pdfinfo Pages=1）；pdftotext 实测图号「图 5.1」、无 U+FFFF；编译日志 0 处 "Float too large"。
- 尺寸与字号（fontSize×W/711×72/25.4）：最小 10px → 6.58pt@165mm、5.66pt@144mm；主标签 11–13px → 7.24–8.55pt@165mm。（v2 的 5.90pt 系 732/711 旧宽混用误算，按审阅公式更正。）

## 二轮剩余项逐条自查（对应 5844497669）

1. R02 残项：score/plan/hyper 三处 module 改为固定 c665 真实符号（guarded_component._score；adaptive_hypergap_guarded 输出/adaptive_guarded.main 写 plan；gap_hyperrefine.refine）。已完成。
2. R03：route 编号大框按 :43–84 顺序（①resource_word ②tree_paired_leaves ③general+波次 ④条件向量修复），①②成功即返回不流经③；恢复 resource_word；br_shared/cores 移除并入③文字。SVG/PNG/nodes/edges/caption 一致。已完成。
3. R04：note53 覆盖构造意外异常（:34–38/50–54/68–72）、字节证据非法（:57–61）、评分异常（:85–100）→ 一律记录 unknown 退回 Π₀；UnsupportedStructure 区别保留。已完成。
4. R05：e13 间距充足不压 select；e13b 短标签「异常」+note53 释义；TeX 数学模式无缺字；图注实际 4 行如实记录。已完成。
5. R06：命令含真实工作目录与改名步骤、模板锁定 e82c2009 完整 commit；字号算术更正（6.58/5.66pt）。已完成。

## 历史稿

v1=3992a4e96；v2=e3e8d3627；v3=本版。均保留于 git 历史。

未完成项：无。
