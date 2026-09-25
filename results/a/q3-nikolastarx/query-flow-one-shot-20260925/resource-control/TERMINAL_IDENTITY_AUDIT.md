# R2 外监督终态身份审计（只读诊断）

范围：只审 `resource_supervisor.py` SHA-256 `651a8a9ee62253961abc656bfa50e01cdca4e17b5f799ad7d233826dcd438fa7` 的父进程正常退出路径；不修改 R2 原件、算法或监督器，不执行新进程、求解或评价。

## 已证事实

- `run/run.json` 为 `complete`，P3、P2 两个 phase 的 worker exit code 均为 0；P3 worker 于 12:23:52.622Z 完成，P2 于 12:23:53.946Z 完成，run 于 12:23:54.001Z 完成。`resource-control/stdout.txt` 也输出 `{"status": "complete", "candidate_M": 5785}`。
- 外监督 `receipt.json` 记录 T0 为 12:23:51.058Z，父 PID 37660、启动身份 `(1790339031, 58394)`；终态却为 `failed`，`error` 与 `cleanup_error` 均为 `RuntimeError: parent identity or process group unverified`，结束于 12:23:54.191Z，缺 T1/exit_code。最后一条资源样本在 12:23:53.115Z，仍看到父 PID 37660 和 P2 worker PID 37746；没有 12:23:54Z 的样本。`independent-postcheck.json` 于 12:26:30.995Z 对已观测三个 PID 回读 `live_rows=[]`、`signals_sent=0`。后续总调度的两次新 ps 和资源释放由协调方记录，本报告不代签。
- 代码行 195–206 的循环先调用 `sample()`，其中 `current_owned()` 强制在 `ps` 表中找到父 PID、由 libproc 读到相同启动身份且 PGID 等于父 PID；随后才调用带 `WNOWAIT` 的 `waitid()` 检查退出。父正常退出后，即便尚未由 `Popen.wait()` 回收，也可能在 `ps` 或 libproc 的身份接口中不再满足这一条件。异常处理行 216–234 又用同一 `current_owned()` 前提清理，因此可连续得到相同的主错误与清理错误。

## 触发定位与边界

这个顺序缺陷**能够制造**“运行产物已完成、外监督报父身份不明”的症状。结合时间戳，最可能是 12:23:54Z 下一轮在 `sample()` 中遇到已退出父进程；另一可能是 `sample()` 刚通过、随后 `waitid()` 分支的第二次 `current_owned()` 遇到退出竞态。原件没有失败当刻的 `ps` 行、libproc 返回值和分支标记，故不能证明具体是哪次调用、以及三项父身份条件中哪一项失败；也不能把外监督 failed 改写成 pass。已完成的两次评价预算为 2/2，本诊断不建议复跑。

## 最小修复建议（未来窗口，需另行审定）

1. 每轮先以 `waitid(P_PID, child.pid, WEXITED|WNOHANG|WNOWAIT)` 判断父进程是否已结束，之后才对仍运行的父进程做资源采样与 `current_owned()`。父进程已结束的分支应记录退出事件和实际 `child.wait()` 返回码，不再把“已退出父进程可读取当前身份”作为完成判定的必需条件。
2. 在回收父进程前检查已观测组是否仍有成员。只有当前启动身份、祖先关系、组长及全部组成员都重新核实的组才可定向清理；无法核实但仍见成员时标记清理不确定/失败、留存证据，绝不向未知组发信号。若无残余组成员且返回码为 0，可记监督完成。异常与 `finally` 也应先区分“父已正常退出”与“父仍运行需停止”，避免对前者重复调用需要活父身份的 `kill_owned()`。
3. 回执添加终态分支与身份失败细分字段，分清 `ps` 缺父行、libproc 无身份、启动身份变化、PGID 变化；保留失败原件，不覆盖本次 R2 回执。

纯 mock 回归可覆盖三种短场景，均不创建进程、不调用求解或评价：(a) `waitid` 表示已退出、`identity(parent)=None`、无残余组、`wait` 返回 0，应记完整终态且 `killpg` 零调用；(b) `waitid` 表示未退出、父身份有效，沿原采样守卫继续；(c) 已退出但残余组身份不明，应保留失败/不确定回执且 `killpg` 零调用。另用调用顺序断言保证退出检查早于任何要求活父身份的采样。
