# Q1 / 情况 A：已实现算法的 Atlas 架构

本交付把已有 Q1 研发结果整理为可展开的架构图，不修改求解器，不运行新性能实验，不接管 fork 的算法或 Pro 请求。主线为：原始图 → 结构化初始构造 → 结构化有限改进 → E1 评分选优 → 官方格式方案 → E0 正式复评。它表示已有阶段的接口关系，不表示已经验收一个统一端到端求解器。

## 五个视图

| ID | 内容 |
| --- | --- |
| `inside-q1-construction` | 主线、共用 E0/E1、成果与独立研究入口 |
| `inside-q1-seed` | 非分叉链打包、拓扑组织分核、合法 cover 合并及 Pro 思想来源 |
| `inside-q1-improve` | 合法移动区间；真实 Task 剖面产生有限拆分/合并 |
| `inside-q1-results` | 官方 Makespan/cycles 与实际求解 wall 两条轴，附开发例数值与计时边界 |
| `inside-q1-research` | trace 排序负结果、E2 尚未接入 Q1、固定版本的 Pro 在途记录 |

单击节点 Map 可原位展开，通过视图选择器或展开后的 Open 进入完整子图；信息按钮查看依据、成果数值及局限。`atlas.html` 是离线只读预览；共享服务发布后以权威 Atlas 为准。原有软件架构预设中的绿色/紫色/灰色分别用于算法模块、持久化方案/成果记录和外部输入/评价来源，并不表示本算法新增了数据库服务。

## 来源与状态

- 算法事实、源文件及阶段报告固定于 `13d6b0298f944d3c0bfdf3172191f1ac25a50379`，复制字节及 SHA-256 见 `evidence-manifest.json`；不依赖未提交代码。8 份源码和 6 份阶段报告与该提交逐字一致。
- 双目标解释依据已读取的公共口径 `b27cf552`（后合入 main）：模拟 cycles 与求解 wall 不混合。在线准备、评分、必要 E0、I/O 和收尾计入求解；结束后的独立正式 E0 另列。5～10 分钟是推荐，不是硬阈值或效率终点。
- E1 固定 `5bfe53a29c1ba05167239f51ea937e602f7f85b4` 已用于 Q1；E2 有专项成果，但本 Q1 固定版本未接入。旧结果支持局部开发例，尚不支持全例、多核数、强基线排名或最优性。
- 1.361 / 2.479 / 1.857 秒是从已有计划出发的局部改进阶段；不是从原图产生当前最好计划的全部成本。
- Pro 思路的采纳、实现、实验与数学证明分别表述。原会话已把算法/Pro 单写交给 fork `nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`；本交付不重新查询其 Pro 状态。

四轴 maturity 有意保守：设计为 proposed（待协调者应用）；有固定源码的模块 implementation=implemented；报告仅绑定 design evidence，不把报告哈希验证升级成全模块 verification；integration 未附统一运行收据，保留 unknown。详情里的已确认开发例与全模块验收是不同范围。共享 E0/E1/E2 的原 maturity 完全保留。

## 权威应用方式

`q1.patch.json` 是交给唯一权威写入者的局部候选，不是 Atlas 原生命令。基于 accepted cursor **83**、revision `508b39b64675b6b3670b81cd62393d6b2ce58995a05eb94f382f60ae177b6b2e` 编制：新增 **17** 个实体、**10** 条关系、**5** 个视图、**14** 条证据；只更新既有 `q1-construction` 的说明字段。

应用时读取最新 manifest 和模型，对 `updateEntities[].expected` 作冲突检查，确认新增 ID 不冲突，再把 additions 合入最新模型并按既有 Atlas 流程验证、签名同步与页面回读。不能把 `candidate.system.json` 整份导入当前权威：它只是 cursor83 的冻结校验副本。任务、原有视图/placement、其他实体和 Q1 原 maturity 均不得被本候选覆盖。源码证据应先随本目录落到权威 repo-root 的相同相对路径。

局部复制的 `canvas-design` 在此旧算法 worktree 里恰好哈希匹配；这**不代表**本交付修复了共享 main 上该既有证据的 stale 状态。权威应用继续保留/计算自己的原证据状态。

## 验证

使用项目固定 System Atlas 0.5.0 执行：

```sh
node .agents/skills/system-atlas/bin/system-atlas.mjs validate docs/a/q1-atlas-20260924/candidate.system.json --repo-root . --json
node .agents/skills/system-atlas/bin/system-atlas.mjs deliver docs/a/q1-atlas-20260924/candidate.system.json docs/a/q1-atlas-20260924/atlas.html --repo-root . --json
```

`delivery.json` 记录冻结 spec 与 HTML 的实际 SHA，18 个视图全部通过 showcase 的 9 项检查，0 error / 0 warning。收据的输出路径规范化为项目相对路径；官方 `visualReview: pending` 未篡改，人工检查另见 `browser-review.json`。本轮还逐字段核对：旧任务和旧视图不变，candidate 等于基底加指定 patch，14 个证据字节与固定 Git 提交一致。

浏览器已查看主图及四个子图，核对原位展开/折叠、选择视图、详情、历史返回与面包屑返回。成果详情显示预期 cycles 与 wall 边界。默认 1600×900 下节点和连线可读；另外记录四个实际 CSS 视口的 containment。未测试触控、移动端、其他浏览器，不把渲染通过当科学结论独立验收。

## 重建说明

`build_candidate.py` 是本次作者脚本，输入为 `output/q1-atlas-authoring/base-bundle.json`（权威 cursor83 的只读 `/api/bundle?cursor=83` 响应）和固定源提交工作区。该临时 bundle 不发布，避免把全量共享状态误作新的权威。正常后续维护应在最新模型上应用局部 patch；重建冻结预览可直接使用已提交 `candidate.system.json` 和绑定证据，无需作者脚本。
