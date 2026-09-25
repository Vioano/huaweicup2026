# R5 同分区错相：单次云窗口准备

此目录仅为准备材料，**不是资源准入，也未启动云 VM**。Mac 评分 hold 继续。控制器、监督器和传输包随本提交冻结；算法源固定为 `8e63305f86a3692b9552295c61c4f234a006c105`。

只运行一次原图 008、K=5 的机制控制对。图 SHA 为 `c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d`，Task/完整模型参数由 `remote_setup.py` 的 COMMAND 固定，不作参数扫描。根代理实际结构预检确认原图私人链识别、两份官方完整 Task-order 验证通过、映射一致且正好 53 个唯一 Task；该预检没有编译 Task 或评分。

- 1 个命名 CPU Standard 会话 `p1-r5-phase-008-k5-20260925`，1 worker；53 个唯一 Task 静态编译一次、最多 2 次完整 Fraction 响应，各 30 秒、0 retry、0 E0/E1/E2。
- 整个远端研究 runner 180 秒；自首次创建尝试 T0 起总窗口 600 秒。独立本机 watchdog 在创建前启动并落盘 PID/截止时间，到 T0+570 秒对该命名会话 stop。
- 首次异常停止研究，不另选参数/不重试评分。收取可得产物；无论成功失败 finally 都 stop 并以 fresh sessions 空列表核对释放。成功模型结果也不代表 E0 或统一成绩。
- cloud controller 只读取 CLI OAuth 既有状态，不复制凭据。T0 前须由总调度确认资源互斥并重新查询 sessions；不因本目录存在直接启动。

## 拟执行入口与输出

准入之后，将本目录的已核字节复制到唯一且尚不存在的运行目录 `output/p1-r5-phase-colab-20260925/run-r5-008-k5-20260925/`。保留一份固定来源 SHA 与各文件哈希，然后执行：

```sh
python -B output/p1-r5-phase-colab-20260925/run-r5-008-k5-20260925/controller.py --execute --cli "$HOME/.local/bin/colab"
```

这是拟命令，不是已执行记录。运行目录保存 `controller-run.json`、`watchdog-armed.json`、必要时 `watchdog-stop.json` 和真实下载的 `evidence.tar.gz`。远端归档包含完整 trace、两键计划、静态编译 certificate 与 ports、调用账、stdout/stderr；随后根代理另作字节/模型范围检查，并记录实际进程退出和释放回读。

## 静态验证

`preparation.json` 记录 126 个固定源载荷的大小/哈希与依赖 import 预检，`artifact-manifest.json` 记录本机控制文件哈希。临时目录解包后使用锁定 Python 仅执行研究入口 `--help`，通过；合成 controller 成功路径通过，覆盖监督器先启动、上传文件名、停止和空 sessions 回读。`root-structural-preflight.json` 为原图结构验证，未调用 Task 编译、响应器或 evaluator。

这些检查不能证明网络、实际 VM stop 或完整模型结果成功；必须由真实运行收据分别证明。新 phase 若不胜控制或未越过条件性不切类界 99264，停止这个固定构造，不启动 E0 或扩大网格。
