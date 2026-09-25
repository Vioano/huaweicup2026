# P1 R4 — 冻结 MEM 边、编译缓存反例与可认证惰性扩域

## 身份与边界

本轮阅读基点：`huaweibei123/huaweicup2026@d8e41115c86cdb5c16ca34d01b08d2dd291243df`。
读取清单见 ACCESS_REPORT.json。vendor 中官方七个 Python 文件与固定 config.txt 来自当前挂载的R3归档，逐字节哈希与本轮固定提交探针certificate所记身份一致；官方文件未修改。没有读取或修改本轮官方图、没有生成真实图候选、没有E0/E1/E2调用。390425的官方通过是用户提供的本机反馈，不是本轮复评。

## 本包实际完成什么

1. 固定的两个合成图，各含两条同型私人M–V–M链；仅作为不同输入，所有tensor ID整体平移7。每个图的实际plan保持本图原ID。
2. 两次未修改官方 `_build_scene_a_tasks` 静态编译，执行了Step1/2/3，没有调用 `evaluate_scene_a`。
3. 两图旧Family.prekey字段相同，M/V/MTE FIFO相同，但raw PortOp.need不同。配置UB131072B，两Task总managed footprint均262144B；Step3编译峰值98304B，spill0。
4. 纯元数据检查确认新增释放遍历顺序区分上述两键；三个预固定资源盒子的69个整数点验证了exact_box_minimum输出不高于整数点目标。没有运行大型惰性DP，也没有运行任何有理数响应。

具体结果：`results/set_order_probe/report.json`、`results/metadata_tests.json`。

## 1. 为何回放不需要占用状态

限定为当前冻结P1、唯一managed producer、无spill、无跨核Task依赖、每Pipe单槽，且读取Step3 execution_graph全部前驱。每Pipe的完成集是一个前缀，所以每个op在某Pipe上的所有前驱完成，等价于完成前缀长达到该Pipe最大前驱rank。MEM和数据边在此完全相同。Task门控及在途DDR剩余服务量仍需保存，但无需新增allocator内部状态。

还有一个独立容量证明：把容量理解为有限个可拆分虚拟字节token。Step3的free_credits记录每个token最近归属。某旧tensor释放后，其token可被新producer取得；新增MEM边要求旧tensor的全部消费者先完成（无消费者则要求旧producer完成）。故任意满足这些边的重定时都不能使同一个token对应两个重叠tensor生命周期。不同tensor同刻使用的token总量不超过初始容量。此证明不保证回放峰值小于编译峰值；只保证容量上限，并且不声称官方输出字段测量了回放峰值。

先按原配置编译MEM图，再做K倍DDR独占工作量的同步商。不能用K倍工作重新运行Step3当作同一图，因为那会重选额度复用依赖。商系统精确性只在Fraction/整数退休模型内；一般官方binary64/EPS等价仍待外部差分。

## 2. 旧prekey为什么失效，怎样修

冻结Step3不是地址best-fit分配：它按free_credits FIFO取额度。新输出按sorted tensor ID分配；consume_inputs和release_dead_outputs却遍历set，而不是sorted(set)。相对ID序不决定set的遍历序。

反例第一条链的X被入口M和V读取，Y只被V读取；X/Y在同一V完成时释放。在一种ID配置中先释放X，在另一种中先释放Y。二者大小相同，但同步来源集合不同。下一链的COPY_IN消耗FIFO头额度，raw need由(M1,V1,0,0)变为(0,V1,0,0)。本例直接否定raw signature同构；没有将这个冗余依赖差异声称为已测Makespan差异。

修补是 `reuse_prekey.memory_prekey`：在旧完整有序prekey外加入每个计算op的真实 `set(sorted(in_tids))` 和 `set(sorted(out_tids))` 的归一化遍历序，以及冻结编译器/配置/运行时身份。这里sorted只用于复现官方构造出的incidence列表，不能排序set输出。边界COPY只有一个managed端点，所以此无spill限定域不额外引入未知的managed tensor ID。

充分性证明按编译事件归纳：Step1排序对应；Step2生命周期和无spill判断对应；Step3 allocation_order、可用容量、各Pipe队首、退休顺序、输入和死输出释放序、free-credit FIFO、全部source集合对应。产生相同的MEM前驱与raw need。不具有相同新键时必须分别编译，或提供更强的语义等价证明。

注意：Family.verify_ordered_family只验证ID块顺序，不验证新的release-word。在扩大域后，不能因此只用(r,q,s)作为所有n/core位置的键。可预计算每条链P/W/R角色的释放词，逐Task比较拼接词；分层状态(n,r)仍充分，但转移成本可能依赖n。

## 3. 惰性扩域，不把q/r扫成大网格

这是建议集成的控制器，**本包未实现完整生产solver**。`edge_envelope.py`实现其精确算术下界子程序。

状态为同步完整退休边界(n,r)，固定每核链列表，欠返程者为已发起链后缀。新Task含r个旧R、q-s个新W、s个新P。所有这些成员均保持原ID。推进到(n+q,s)，drain到(n,0)。原Family.fits保留为快速充分证书，不再作为唯一可行性否决。无spill可行性由官方静态编译确定。

令a,b,c为入口M、全部中间V、返程M的工作；dP,dR,dW为按原图边界谓词逐COPY取整的片段服务。对任何成功编译的同步推进，完整响应至少为以下三项的最大值：

- M普通工作加q-s条完整链中不可被其他M填补的V间隔：q(a+b+c)-s(b+c)+rc；
- V工作：qb；
- DDR全局服务：K[(q-s)dW+s dP+r dR]。

最后一项不除K。此处只用资源守恒和完整spine的M阻塞，不使用候选MEM边来作全局下界，也不把删除MEM后的贪心共享DDR模拟当下界。

对下一状态，剩余各核新链数为N_k-n-q，待返程s。余下时间下界取每核M工作、每核V工作、总必要DDR的最大值，并可忽略门控来保持下界有效。edge_envelope.Resources.forms返回这两组三个affine形式。

每个状态的未展开(q,s)域用裁剪盒子表示，只受整数范围、s<=q和剩余宽度约束，不提前假设容量可行。区域下界为已认证前缀时间，加下一次实际门控，加“转移下界+后续下界”在整个实数盒子中的精确最小值向上取整。

两个max-affine函数之和的最小值可通过盒子边界、s=q以及各自affine差为零的直线安排求得：检查所有可行交点即可。用Fraction计算，验证器重枚举所有交点；单独提供一个可行点不是下界证书。

### 控制器伪代码

```
U, incumbent = construct_and_verify_existing_method(current_input)
OPEN = {root state with admissible remaining-work lower bound}
while OPEN not empty and extra budgets remain:
    item = remove minimum certified lower-bound item
    if item.bound >= U:
        record pruning certificate; continue
    if item is a reached state:
        insert its drain and terminal leaves as applicable
        insert ONE clipped box covering all its normal (q,s) successors
    elif item is a nonsingleton box:
        split at a resource-envelope intersection / fractional minimizer
        partition disjointly and completely; enqueue all nonempty children
    else:
        build actual members on every core
        get a signature using the strengthened exact key, or compile once per new key
        if a mathematically certified domain violation: exclude ONLY this edge
        if a timeout/budget/unknown: retain its unresolved bound and stop/skip
        if normal signatures differ: exclude from this synchronous-prefix class
        else compute frozen-MEM Fraction response
        relax destination (n+q,s) / (n,0), reopening on better labels
        update U only from a completely constructed, verified full plan
L_front = min(U, all unresolved OPEN bounds)
return best verified plan, [L_front, U], unresolved ledger
```

所有未处理完整路径必须仍被某个前缀状态或区域覆盖。以完整三键代价作优化时，对cycle相等的剪枝还需搬运字节等次级下界；上述标量判停只认证Makespan最优。预算耗尽时绝不把未编译边标成不可行。

运行时边界：预处理O(n+m)加排序；实际开销用新键编译数A、区域分裂数H、已到达状态数S、官方编译代价及Fraction响应代价表述。最终完整方案仍逐Task重编译。没有承诺最坏情况下准线性；无足够下界区分时，完整扩展图会回到O(B^2)状态及O(B^4)位置转移量，因此必须有小的额外预算并诚实输出未封闭gap。

## 4. 既有证明怎么沿用

- 已冻结MEM的prefix响应、K倍DDR商、同步边界(n,r)、合法两键计划和drain/尾部处理可沿用，前提是全MEM纳入need且转移成本的缓存等价已认证。
- 三状态只是选取的一组返程状态；仍可在它自己的已接受转移图上求最优。
- 旧Qmax/Rmax和fits只认证旧域，不能当新域必要条件。
- 旧Bellman/周期证书只覆盖旧边。新边须用精确代价或覆盖整个未展开区间的下界补验，才可扩展证书。
- 旧R2全图335819下界保留私人spine与所有内部切口服务下界等前提；本轮不重新计算它，不把719变成构造参数。

## 运行与文件

```
python -B src/memory_order_counterexample.py
python -B src/test_pure_metadata.py
```

为避免覆写原件，第一个命令要求results/set_order_probe不存在；复跑请复制本包到新目录并先移开旧results。第二个是纯算术/元数据测试。结果不可作官方成绩。

下一步两项预注册建议在 NEXT_EXPERIMENTS.json；没有自动启动、没有GitHub写入。
