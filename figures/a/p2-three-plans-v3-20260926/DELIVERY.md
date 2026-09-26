# FIG-P2-THREE-PLANS · 图件交付

- 固定来源：`c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f`，`src/q2_nikolastarx/adaptive_hypergap_guarded.py`。`P0` 构造与保留见 14–26 行；P1 失败回退、相同方案去重见 27–42 行；局部调整、严格原始 COPY 字节门槛、P2 重排与异常分支见 44–79 行；唯一方案直接返回、依构造顺序评分与字典序选择见 80–108 行；入口的三次请求上限见 111–113 行。被直接调用的 `_score` 见同提交 `src/q2_nikolastarx/guarded_component.py:21–30`，要求 `status=ok` 和非负整数 `(makespan, added_copy_bytes)`。`gap_hyperrefine.py:139–153` 给出调整前后原始 COPY 字节证据与重排前阶段范围。
- 交付文件：`build.py` 为确定性 Draw.io XML 生成器；`p2-three-plans.drawio` 可逐个编辑节点与线条；`p2-three-plans.svg` 为矢量导出；`p2-three-plans.png` 为高分辨率导出；`preview-160mm.png` 为 1890 像素、300 dpi 的约 160 mm 宽预览；`CAPTION.md` 为候选图注。
- 重建：在项目根目录执行 `python3 figures/a/p2-three-plans-v3-20260926/build.py`，再分别使用本机 Draw.io Desktop 的 `drawio -x -f svg -e` 与 `drawio -x -f png -s 2 -b 16` 导出。预览使用 `sips -Z 1890 -s dpiWidth 300 -s dpiHeight 300` 生成。布局和文字以 `build.py` 为当前编辑源；若在 Draw.io 手工修改，须同步生成器或注明编辑源已切换。
- 验证：Draw.io Desktop 成功导出 SVG/PNG；XML 可解析且包含独立节点、连接线；以实际 1890 像素预览回看，中文无缺字，节点文字无裁切，箭头未穿越节点文字；P0、P1、局部字节门槛、可选 P2、完整方案去重、最多三次请求、失败回退与比较顺序均可辨认。此项是图件与固定源码的核对，未运行求解器或评价器，也不构成论文采用或官方成绩验收。
- 范围：最终交付位于本隔离 worktree 的本目录。因开始时工作目录误指主检出区，主检出区同名目录保留为初稿，未再编辑或提交；未修改论文、网站、注册表、其他图件或共享文件。

## SHA-256

下方列出本次输出及可重建源文件的哈希；本交付说明不自列哈希，以免自引用。

- `build.py`: `552ec3ae47a5b27f5f168458872c154b0add479df95816b6c234857561aaeb9c`
- `p2-three-plans.drawio`: `294b31ab231d582b87a4d47c65c82482ca8ea8e611da6f7cd252659fbb0fd8a0`
- `p2-three-plans.svg`: `c52f81551090fe7378a9b3bca20542439bac11f9ba81e47f782b3acf51d95ff3`
- `p2-three-plans.png`: `8010d7ea3d3c15d177e2af9fbf9e7b818545556cc7bc69d1ac95f9185310e27f`
- `preview-160mm.png`: `9883914f17b0d1a1185b5656f427437da7b724dd6014a1b4d42b153b6082a873`
- `CAPTION.md`: `96227c80422ac76bcc3317125eefaffa7e924b7b167a0d6e493a7020a959dc86`
