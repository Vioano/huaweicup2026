# 内存依赖包宽探针

`src/q1/memory_packet_probe.py` 是独立研究入口，仅接受 `Family.verify_ordered_family` 的严格有序、私有同构链。它用 `compiled_memory_response` 对每个实际位置、每个核心的 Task 编译；只有完全相同的 `nodes` tuple 可复用编译。同步组要求各核实际签名相同，不对不等的 Task 加隐式屏障。

同一张已编译候选表供两个 `(n,r)` 无环 DP 使用：旧保守容量子域与实验上限 `q<=2,r<=2`。drain、末尾 merge/separate 都计入成本。选中的两键计划会在原图上完整官方 Task 编译，并核对逐 Task 签名、DDR 字节与完整有理数模型回放。最多 2500 次 Task 编译，函数使用 60 秒硬截止；超限不输出成功计划。CLI 写文件采用拒绝覆盖。

上限是预声明机制实验范围，不是结构最优或全 P1 最优证明。官方 E0 仍需独立运行；当前纯 DP 单测不证明真实投影支持，也不证明有理数与官方浮点时间零差分。
