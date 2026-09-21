# 科研绘图 Skill 与排版引擎接入

负责人：@NikolaStarx

分支：`codex/scientific-figures`

沟通：本次用户请求；未另发通信 Issue。

1. **任务目标**：找到精算云画图中的排版能力，接入华为杯项目，并按 OpenAI Astra 官方建议审查旧绘图指令；研究其他绘图 Skill。
2. **输入文件**：源项目 `引擎测试/compute-layout.mjs`、`drawio-pic2/generate-drawio.mjs` 及绘图 QA Skill；来源哈希见 `docs/scientific-figures-source.json`。示例仅描述建模工作流。
3. **输出要求**：项目 `scientific-figures` Skill、锁定 ELK 依赖、可编辑 Draw.io 示例与预览、来源记录及研究报告。
4. **限制条件**：不修改源项目未提交文件，不安装其他研究候选，不硬编码个人路径；本次实现单层有向图，复杂泳道和公式另走 Draw.io 原生编辑。
5. **验收标准**：输入节点、标签和端点无丢失；几何无框重叠与穿框；布局可重复；XML 回读正确；已有文件不被覆盖；实际 Draw.io 导出中文图并检查。模型优劣无控制实验时不做量化断言。
6. **截止时间**：本次任务，2026-09-22（Asia/Taipei）。

## 交付记录

实际命令见 `.agents/skills/scientific-figures/references/drawio.md`；`npm test --prefix .agents/skills/scientific-figures` 通过 6 项测试。

结果：`figures/workflow/modeling-workflow.drawio`、PNG、PDF 和布局/几何报告。示例为 6 节点、6 连线，输入哈希记录在 `.qa.json`。

视觉检查：本机 Draw.io 原生导出的 PNG 中文可读、6 条连线方向符合语义、未发现文字裁切或穿框；PDF 已成功导出。几何报告仍保留 `visualReview: pending` 作为自动报告边界，本条是此次单独的视觉检查记录。

未验证：队友本机字体、Windows Desktop 导出与拖拽后的原生重路由；MATLAB、Wolfram、Julia 的绘图运行；第三方候选的端到端表现。当前 Skill 不承担原客户图件的复刻验收。

PR：提交后记录于 GitHub。
