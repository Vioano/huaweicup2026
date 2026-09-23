# 一手文献与读取范围

检索/核对日期：2026-09-23。以下为本轮实际读取的原文，不是根据搜索摘要补写定理。论文 PDF/HTML 经联网工具读取；由于容器网络 DNS 失败，没有把网页 PDF 下载到本证据包。书和论文的原件不随包再分发。未确认最终出版出处的论文保留 arXiv 身份。

## L1 有向无环超图划分
Merten Popp, Sebastian Schlag, Christian Schulz, Daniel Seemaier. **Multilevel Acyclic Hypergraph Partitioning**. ALENEX 2021, pp. 1–15. DOI: [10.1137/1.9781611976472.1](https://doi.org/10.1137/1.9781611976472.1). [开放原文 arXiv:2002.02962](https://arxiv.org/pdf/2002.02962).

已读：问题模型、连通性代价、§3.1，以及基于层级的无环粗化条件 Theorem 3.1/3.2（PDF 第6页截图核对）。可移植的是构造时维护无环性，不是其全部代价函数。论文所用有向超边方向约定与本题单生产者/多消费者约定可相反；整体反向保留无环/割性质，但不保留执行时序。平衡划分和割代价不是固定官方 FIFO、共享 DDR 下的 Makespan。

## L2 有序分区的数学表示
M. Yusuf Özkaya, Ümit V. Çatalyürek. **A Simple and Elegant Mathematical Formulation for the Acyclic DAG Partitioning Problem**. 2022. [arXiv:2207.13638](https://arxiv.org/abs/2207.13638); [PDF](https://arxiv.org/pdf/2207.13638).

已读：§4 分配变量、负载、割变量、商图变量及其三角约束（PDF 第7页截图核对）。帮助把“分区无环”转成有序标签/前缀约束。注意这是抽象图结构重标号，不证明本题含固定 ID 并列规则的编译结果在子图数字编号变更后不变。

## L3 超边代价到最小割
Nate Veldt, Austin R. Benson, Jon Kleinberg. **Hypergraph Cuts with General Splitting Functions**. *SIAM Review* 64(3), 650–685, 2022. DOI: [10.1137/20M1321048](https://doi.org/10.1137/20M1321048). [开放原文 arXiv:2001.02817](https://arxiv.org/pdf/2001.02817).

已读：§4，尤其 §4.1 两辅助点的 all-or-nothing 超边割装置（PDF 第12页截图），及文中针对特定基数型 splitting functions 的可表示性条件。本文只调用最简单的非负 all-or-nothing 装置；不声称任意子模高阶能量都能用同一装置表示。与逆向无限容量偏序边的组合、嵌套性证明及本题映射见研究备忘。

## L4 参数化最大流
Giorgio Gallo, Michael D. Grigoriadis, Robert E. Tarjan. **A Fast Parametric Maximum Flow Algorithm and Applications**. *SIAM Journal on Computing* 18(1), 30–55, 1989. DOI: [10.1137/0218003](https://doi.org/10.1137/0218003).

[Princeton 技术报告入口](https://www.cs.princeton.edu/research/techreps/633)；[实际读到的作者上传全文](https://www.researchgate.net/publication/220616489_A_Fast_Parametric_Maximum_Flow_Algorithm_and_Applications)。Princeton PDF 下载未成功，不能声称从该入口读到 PDF。

已读：§2.3 单调源/汇容量条件；§3.4 Theorem 3.1 的断点算法；§3.5 嵌套割集合。源容量非减、汇容量非增，其余固定；参数方向反过来也可用变量换号对齐。我们的有界核验实现是重复 Dinic，不是这篇论文的参数化最大流实现，因此不能拿其复杂度冒充原型实测。

## L5 max-plus 离散事件代数
François Baccelli, Guy Cohen, Geert Jan Olsder, Jean-Pierre Quadrat. **Synchronization and Linearity: An Algebra for Discrete Event Systems**. Wiley, 1992. ISBN 0-471-93609-X.

[作者开放版入口](https://www.rocq.inria.fr/metalau/cohen/SED/book-online.html)；[Delft 存档](https://repository.tudelft.nl/record/uuid:1add64d4-0dfc-4b5d-9db0-2d4be33dfeb3)；[实际阅读 PDF](https://repository.tudelft.nl/file/File_681d1849-7274-4560-a103-aeb57d4d87ee).

已读：Chapter 3，Theorem 3.17/3.20 的闭包与最早事件解、矩阵的路径解释；也核对了 Theorem 3.23 最大环均值所需条件。本题有限 DAG 的固定时延部分适合闭包/消元；动态带宽和 FIFO Cache 不整体 max-plus 线性。最大环均值不能不加条件套成有限一次执行的 Makespan。

## L6 支配内存剖面与线性化
Ce Jin, Manish Purohit, Zoya Svitkina, Erik Vee, Joshua R. Wang. **New Tools for Peak Memory Scheduling**. 2023. [arXiv:2312.13526](https://arxiv.org/abs/2312.13526); [实际阅读 HTML](https://arxiv.org/html/2312.13526v1).

已读：§1.1–1.3 的模型与主要结论；§5 的 isolation、Lemma 5.3 exchange、Lemma 5.4 linearization；Appendix C 的指针推进交换证明。其“用支配调度将孤立子图替换为路径”保持的是 peak-memory 模型，而不是本题多 Pipe Makespan。权重 one-shot pebbling 在某些简单图族仍强 NP-hard；有界出度的串并联特例才有相应参数算法。可借支配剖面/封闭接口思想，不直接继承其保证。

## L7 小树宽调度的边界
Eric Angel, Sébastien Morais, Damien Regnault. **A Bi-Criteria FPTAS for Scheduling with Memory Constraints on Graphs with Bounded Tree-Width**. *Euro-Par 2022: Parallel Processing*, LNCS 13440, pp. 136–151. DOI: [10.1007/978-3-031-12597-3_9](https://doi.org/10.1007/978-3-031-12597-3_9). [开放预印本 arXiv:2202.08704](https://arxiv.org/pdf/2202.08704)（预印本题名使用 Graph 单数）。

已读：§1 的无向邻域静态存储模型、§3 nice tree decomposition 上的状态、§4 的 trimming 和 Theorem 1。其内存为所分配节点闭邻域的总权重，并允许双指标近似中的容量放宽。本题容量是硬约束、存在生命周期和共享动态资源；不能据此宣称本题有 FPTAS。借用的是记忆边界状态和限制状态空间的方法。

## L8 谱超图方法的实际目标
Dengyong Zhou, Jiayuan Huang, Bernhard Schölkopf. **Learning with Hypergraphs: Clustering, Classification, and Embedding**. NIPS 2006, *Advances in Neural Information Processing Systems* 19, pp. 1601–1608. [作者单位开放 PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2017/01/HYPER.pdf).

已读：§2–6 的关联矩阵、归一化超图 Laplacian、谱松弛及 Theorem 1。其超边割项包含两侧节点数乘积/超边大小，不是本题按目标核心去重后的通信次数。只适合相似性种子，不保证方向、合法性或性能。计算关联算子时不必形成稠密 H H^T。

## L9 2025 年计算图—实际加速器局部性研究
Oguz Selvitopi, Emin Ozturk, Jie Chen, Ponnuswamy Sadayappan, Robert G. Edwards, Aydın Buluç. **Fast Algorithms for Scheduling Many-body Correlation Functions on Accelerators**. 2025. [arXiv:2511.02257](https://arxiv.org/abs/2511.02257); [实际阅读 HTML](https://arxiv.org/html/2511.02257v1).

已读：§II-C 模型、§III-A Algorithms 1–3 sibling 构造、§III-B Algorithms 4–8 的 tree gain 与增量更新。方法利用二叉收缩及共享张量的释放机会，而不是通用黑箱搜索。该文明确不把处理一个树时的临时存储计入 tree gain，且存储管理系统不同；本题必须补瞬时申请容量检查。只将其作为实测 SPILL 较重时的低成本顺序/分组种子，不能改写官方 Step1、插任意预取或重算。

# 最新官方主机硬件 / SDK 资料

## H1 CUDA
- [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/index.html)，入口显示最近更新 2026-09-10。
- [CUDA C++ Best Practices Guide 13.4](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html)，读取 profiling、host/device 传输、coalescing、数值精度部分。
- [CUDA Graphs](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html)，读取实例化和重复 launch 的摊销说明。CUDA Graph 是主机命令图，不是替代赛题执行语义的许可。
- [Floating-point documentation](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/mathematical-functions.html)，核对 FMA、舍入及平台差异。

## H2 Apple Silicon
- [Metal Feature Set Tables](https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf)，2026-05-21 版本；实际查看第2、4、6页截图：M5 对应 Apple10，表列 Metal 3/4；整数64位功能与64位原子功能有不同条件。
- [WWDC26: Optimize custom machine learning operations with Metal tensors](https://developer.apple.com/videos/play/wwdc2026/330/)，实际读 transcript。M5 Neural Accelerators/MPP tensor operations 重点是矩阵乘和卷积，不等价于 max-plus 半环或整数最大流。
- [Metal what's new](https://developer.apple.com/metal/whats-new/)。

没有从这些资料推出本队 Mac 的 GPU 核数、内存带宽、系统/Xcode版本或 FP64 能力；都须设备查询/编译测试。没有运行 CUDA/Metal 基准。完整 MSL 规范 PDF 因获取失败未读，不引用其中未核实的 FP64 条款。
