# 冻结044前缀诊断的Linux执行包

算法/官方源码固定62c69b20ab887c76567dbab5fcce6eef30107b5c，Mac原runner、原manifest、已构造计划字节均不变。Linux外部监督及Colab控制源码固定 `c642da2b016a5796882a24432bc5f01eb9dd6a7c`。包SHA256 `9c16cf654a8c5521c5bab414724a962f07c8d95806d1dbc64b0c7c0206ed86ec`（38479 bytes）。这是同一个尚未启动的实验，不能Mac与Colab各运行一次。

总调度已安排P1后单实例CPU Standard候选窗口；**当前未准入、0云/Task/Step/E0调用**。确认P1 stop且本包唯一准入后，执行：

```sh
.venv/bin/python -B scripts/q3_prefix_colab_control.py \
  results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/package.zip \
  results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/run-local \
  --package-sha256 9c16cf654a8c5521c5bab414724a962f07c8d95806d1dbc64b0c7c0206ed86ec \
  --admission-ref '<实际唯一资源回执>' --cli "$HOME/.local/bin/colab"
```

仅1 prepare（5核Step1/2/3），检查通过再至多1 P3（另5核Step1/2/3），0P2、1worker、0retry；每阶段60s，总120s，进程组RSS采样512MiB。Linux MemAvailable启动≥1536MiB、运行≥1024MiB、pswpout不增长；Linux没有照搬macOS pressure数值。PDEATHSIG覆盖子进程启动窗口，阶段及全程独立watchdog覆盖监督父进程退出；采样与cleanup存在延迟，RSS非内核硬限。

云端只在150s内做稀疏固定SHA检出与环境安装，所有原件再次哈希核对；uv0.11.15、CPython3.12.13、uv sync --locked。Colab宿主镜像由服务管理，不能伪称固定Docker镜像；执行前记录实际内核、Python和二进制哈希。Mac二进制不能冒充Linux二进制。此诊断墙钟含追踪开销，不是solver性能。

控制器只创建命名实例q3-prefix-044-20260925一次；上传、执行后无论成功/异常均尝试下载证据、stop、sessions回读。命令执行预算410s，额外cleanup≤55s；需要人工核对stop和sessions原文才确认释放。CLI超时不等于VM已停止，不自动重试或占用其他实例。创建前必须先核无同名残留实例；失败原件保留。

8个监督mock测试由Sol medium完成，根会话额外验证创建超时仍cleanup、坏包在调用前归档失败。后者第一次mock漏掉platform子进程，修正fixture后通过；没有真实官方调用。Linux实际监督与评价尚未验证。

包只含原044输入副本、原manifest、外部监督器、包清单；无凭据、无需GitHub Actions，不改只读原件。setup/下载/评估/cleanup各自留存；归档原件之后按原实验做正负结果审核，不能当固定算法全500成绩。
