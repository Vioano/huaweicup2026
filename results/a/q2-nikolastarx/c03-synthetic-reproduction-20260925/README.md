# C03 本机合成复现与适用边界

Python 3.12.13 / macOS ARM64，2026-09-25。原型与测试从 AI chats/20260925-P2-零spill通信与流水联合构造/附件 的两个 browser-copy.py 原文复制，分别改名 outside_slack_merge.py、test_outside_slack_merge.py，在独立输出目录执行 `python -B test_outside_slack_merge.py`。退出码0，6测试通过；随机seed=70328，1000图中321成功、668当前固定中点/词不适配、11优先序恢复成环。输出原件与输入哈希随附。

这是固定服务模型的合成测试，不是赛题成绩；没有调用prepare、solver或E0/E1/E2。复现未取得原始ZIP的事实保持不变。

[源码复核](INVARIANT_REVIEW.md)：固定原图、配置与分核，而且两次官方Step2均零spill时，COPY字节不随优先序变化。静态证书不能代替实际Step2；共享DDR时序与Makespan仍可能变差。C03最多在原C02区域、owner、内部词不变条件下尝试两份重排，不扩大区域与参数搜索。
