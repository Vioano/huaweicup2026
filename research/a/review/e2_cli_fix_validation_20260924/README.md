# Windows 完整 CLI 独立驱动：首个静态检查点

**本交付是不可执行验收的准备检查点，尚有一个明确静态阻断 B1。** 15 行驱动路径、接缝和控制结构已写出，文本/AST/JSON/哈希检查不替代其运行。`contract.json` 保留非空 `execution_blockers`，外层和控制器都会拒绝进入窗口；即使另写 approved=true 也不能越过。不得把本 Draft PR 当可运行验收版。

## 1. 目标、授权与时间

session=`yuanzhifang30-sudo/s-b4329d86154348de9401afcbe48b34ce`，continue。
[准备阶段授权](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5806444428) 实际作者 yuanzhifang30-sudo / 281850557，已全文读。
实际接手 UTC `2026-09-24T02:37:26.6038619+00:00`，约30分钟检查点 `03:07:26Z`；这是静态任务时刻，没有新实验 T0。
分支 `codex/e2-cli-driver-prep-yuanzhifang` 从 `53c151ecaef2636bcf0eb1946c112f19f8cec739` 建立；仅写本目录，保留 PR68、生产补丁和旧门禁/结果。

## 2. 固定输入与来源

- 计划：`53c151e` 的 `research/a/review/e2_cli_fix_static_20260924/`，15例、8潜在E0、43逻辑创建请求、123/126条件OS模型。
- 生产：`a21f7ef7111933d309f3d616b9a3f2e7e861129d`，helper SHA `fb33ab3d120479ff70dbea87a730a08b16b90af44996cf78746d7880351b091b`。
- 只复制旧 `569c65f2673d6fc2a99507f151ca04b814e1dc68` 的单个 `gate_helper.py` 原语文件，SHA `e5af8da2e6cc4288d7066769bb246c68f51da8bc3c2d6da2f4acc45698c88621`；没有复制旧树或改旧文件。
- `sources.json` 列出 driver 文件、driver bundle 及5485项解释器/标准库/既有 NumPy 与相关依赖、项目源码、冻结文件、计划输入的静态字节身份。只记录逻辑相对定位与 SHA，不上传个人目录。runtime home 从已锁 pyvenv.cfg 推导；原配置本身只存 hash。
- 旧3进程仅是已有 venv 入口的 ready 集观测，未记录完整 launcher 映像归属；本阶段没有探测实际启动链。仅允许已锁 venv python.exe / runtime python.exe 映像路径，未知路径/虚拟化别名失败关闭。

## 3. 已实现的可审阅代码

| 文件 | 责任 |
| --- | --- |
| `launch_once.ps1` | 原外层 UTC/QPC、批准/commit/bundle/manifest核对；PowerShell拥有独立root Job；CreateProcess suspended后赋Job并仅resume一次；无继承句柄；root active17=控制器3+案例14、2.25GiB聚合政策；256MiB控制器监测；90/660/670截止与kill-on-close。P/Invoke声明通过Reflection.Emit写出，没有编译器子进程；本阶段没有调用它 |
| `controller.py` | 8真实CLI与7假目标串行调度；创建前持久预留43逻辑请求/8费用上限；新case唯一目录；ACK前禁止目标；明确预计非零与首次意外失败；完整文件比较和有限路径/路线规范化；Job收尾与原始退出码 |
| `bootstrap.py` | exact Job/nonce/bundle/完整PID ACK；每case仅一次真实Popen；文件或并发排空PIPE，有限输出，显式Popen句柄关闭；不导入evaluator |
| `seam.py` | 加载真实helper字节，保留真实verify和真实subprocess；只改目标目录，F-startfail额外改专用进程sys.executable为不存在exe；审计唯一启动尝试；SystemExit/OSError证据后重抛 |
| `fixture.py` | 空/Unicode/引号/反斜线参数、stdin/cwd/env；具名事件控制等待；0/1/2/7/255（2用argparse拒绝）；PIPE各256KiB；取消项唯一孙进程，验证之前不释放事件 |
| `win_support.py` | 新的cap14、2GiB Job/512MiB进程限额回读；PID/父PID/创建FILETIME/映像/非继承观察句柄；累计、采样峰值下界、精确峰值unknown分列；内存和原始DWORD |
| `common.py` | 原子证据/账本写入、source identity、批准门禁、固定输入规则；无目标自动运行 |

实际P2/P3使用固定 `-m` 入口或冻结直调，不通过假目标接缝。两种真实路径都按同一控制环境设置 `PYTHONDONTWRITEBYTECODE=1`、`PYTHONIOENCODING=utf-8:strict`、`PYTHONUTF8=1`；后两项是把比较用的编码输入显式固定，不声称已覆盖任意默认codepage。真实产物在返回时一次读取，缺件失败，不轮询补洞；共享计划和输入仍按原hash读取，不手改旧证据。

失败采集由单个只读daemon线程执行，控制器最多等待100ms，慢API不能推迟发出终止；收集未完记录incomplete、不得通过。线程不拥有Job变更权；退出时内核关闭残余观察句柄。固定原语的失败launch清理与控制器finally共用保守10s总截止，不叠加5+10；新launcher创建最多5s。外层catch也有独立10s截止且不超过原T0+670。所有同步内核调用本身的实际延迟仍未实测。

## 4. 静态结论、阻断与未验证

**B1：真实 adapter→official 的逐逻辑启动链归属尚未闭合。** 当前代码有完整PID/父PID/创建时间/映像尝试、Job总数/active限制与源代码身份，但没有可靠地把未插桩真实CLI的每个venv/包装器层归到各次逻辑创建，因而不能证明或逐链执行“每次最多3层”。总数≤9/12不等于每条链≤3；即便程序路径只含一次subprocess也不能替代OS链证据。必须补出可审阅的归属算法，或由协调明确修订该条件模型与准入规则，然后才能移除硬阻断。没有因为赶检查点把未知标通过。

其他未验证：Reflection.Emit/Win32结构和句柄调用、嵌套Job兼容、PIPE、退出码、取消、实际峰值/内存、5485项预检能否在90秒完成、实际虚拟化路径别名、PID快进快出采样完整性，均未运行。采样漏进程会因累计数与观察句柄数不等而失败；不会自动提升通过。当前说明是实现意图与静态观察，不保证该初稿没有其他缺陷。POSIX仍平台/负责人未定、未实现窗口。

实际只做标准库 `ast.parse`、PowerShell Parser.ParseFile（不执行脚本）、JSON/哈希、Git字节/diff和限定目录扫描。**本阶段目标import/执行、--help、假目标/探针/测试、worker、构建、E0/E1/E2、依赖安装、云调用全为0**。文件读hash用了普通Python进程；没有import任何新驱动模块。运行中的静态hash进程在交付前已结束，不是后台测试。

## 5. 命令、账本与验收边界

以下是将来解除静态阻断、固定新提交并再次明确批准后的入口形式；本检查点不会执行成功，也从未调用：

```powershell
# ApprovalPath 为仓库外的真实批准文件；不能拿 false 模板改名当批准。
& ./research/a/review/e2_cli_fix_validation_20260924/launch_once.ps1 `
  -ApprovalPath <private-approved-json> -EvidenceName <fresh-approved-run-name>
```

真实命令tokens在固定计划matrix，controller只代入已锁ROOT/PY/INPUT/CASE；所有15项唯一输出，input和config来源不变。新预算、cap、内存、1800s全部仍是提案；外层累计90/660/670，发布1200/1500/1800由后续证据流程沿原QPC记录，当前未实现自动发布。发布Git/gh/PowerShell宿主不混入43目标程序请求。静态manifest的大清单是约0.7MB的hash元数据，不是复制依赖二进制。

## 6. 检查点、停止和下一步

本阶段按授权交具体阻断检查点及独立Draft PR，不宣称驱动准备全部完成。交付固定SHA/远端PR/Issue回读后停止；等待协调审查B1及其他静态问题。代码同时保留 approved/execution_enabled=false 默认模板与不可由批准模板覆盖的B1阻断。
旧潜在15、余2、旧T0保持封存；没有申请或使用新运行额度。生产helper/原测试文件未改，Actions不启用，Q2休息，Atlas未写；无子任务/目标进程在途。旧E2失败仍未完整验收。
