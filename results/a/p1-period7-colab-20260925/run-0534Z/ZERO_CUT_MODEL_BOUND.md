# 008 不切链、无 spill 构造类的模型区间

2026-09-25 根推导；既有 Sol 只读核对源码条件。无编译、模拟或官方评价新增调用。

固定输入 SHA c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d。008 有108条私有同型M(a)→V*(b)→M(c)链，a=c=1158，b=2196。限制为链不拆开、无spill、同核串行Task激活以及冻结Step1/2/3生成的FIFO。Step1反向DFS完成一个私有分量的compute spine后才访问另一分量；Step2无spill保持compute序；Step3逐Pipe投影。每链两个M在其Task M FIFO相邻。其間b个V计算周期是同核其他M不可填的间隙，且各链间隙互不重叠。同核不同Task也不能同时激活来填补。

于是每核 T≥Nk(a+b+c)=4512Nk。无论完整链如何分组或分配至至多5核，max Nk≥ceil(108/5)=22，因此T≥99264。DDR、MEM与Task门控等待只可增加所需时间。

该类已有一次真实编译/精确服务回放的可行模型方案：run-0511Z 的normal(21,0)+尾部，16次Task及3次Fraction核验，模型101836周期、extraDDR=0。因此这个限定模型类的最优值位于[99264,101836]。现有模型方案相对下界最多还能降低2572周期，即约2.5256%；不能由此证明已经达到最优。

此结论不能替代官方E0 binary64/EPS数值证书，也不是拆链/跨核片段/共享分量/任意P1的最优证明。官方v4的008周期100603保持自己的E0证据，不偷换成新模型upper。未把“零extraDDR”无条件等价为“不切链”：原始副本、侧输入和边界谓词仍需逐图核实。

来源：docs/a/P1_RETURN_CUT_RESOURCE_BOUND.md前节；冻结schedule_step1.py的DFS；multicore_cut_evaluate_problem_1.py core_active_task与init_pipe_queues；actual model receipt results/a/p1-lazy-seed-colab-20260925/run-0511Z/receipt.json。结论建议：若该模型类内希望获得大于上述区间的突破，应允许有依据的拆链或另证更宽构造，而非无限重排完整链。
