# 本轮证据与读取边界

## 四种来源

1. **实际读取**：授权镜像分支HEAD、固定文档/代码/CSV/summary；细目在READ_MANIFEST.json。原官方七模块全文从已上传原附件本机副本读到，代码集合hash与当前main manifest核对。
2. **AUTHOR-REPORT**：其他session报告的质量/计时/回归数、原生倍数、Q1新池与Q2/Q3历史池。本轮读取报告并不等于重新运行或独立验收其全部原始结果。
3. **FORMAL**：完整result恢复逻辑plan、Q1固定划分编译分解、D17操作闭合充分条件、末尾空核嵌入（带具体域和参考runtime假设）。
4. **本轮新E0/EMP**：以下独立保存的29次官方调用，以及零新评价的结果恢复检查。

## 新调用账目

- `evidence/new/peak/protocol.json`：运行前声明五次CLI、各30秒上限；源码hash、平台/Python版本。
- `evidence/new/peak/ledger.json`：每次dispatch、命令、输入/方案身份、状态、耗时与result哈希。
- `evidence/new/peak/summary.json`：五次成功；官方字节前后相同。case008 B=487605；Q2=Q3=63768；同计划Q1=588824；case044 B=154407。
- `evidence/new/peak/{single008,single044,q2_peak008,q3_peak008,q1_same_plan008}/`：完整原JSON、Trace、log、stdout、stderr。
- `evidence/new/quotient/protocol.json`：四操作API合成域、24顺序、相邻槽位交换及观察定义。
- `evidence/new/quotient/{00..23}.json.gz`：每份原计划和完整函数结果；不是只留Makespan。
- `evidence/new/quotient/rows.json`、`summary.json`：实际全24态、全动作转移、h0/h1/h2/h3类数与最短一步区分对。调用24次函数，不是24次CLI。全部成功，无调用预算外搜索。
- `evidence/new/recovery.json`：重读3份正式多核结果和24份合成结果，恢复逻辑plan共27/27，零新增E0。
- `evidence/new/derived_bound.json`：从case008计算工作得到四核资源下界62532及差距上界；零新增E0。

计数：**5 CLI + 24函数 = 29次新E0**；无E1/E2，未启动共享worker服务或全100图研究。函数输出曾经转为JSON保存；不据此宣称跨语言类型等价。具体比较层在各实验protocol中声明。

## 身份核对

- `evidence/official_hash.json`：冻结代码逐文件SHA256及集合hash `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。
- `evidence/plan_reconstruction.json`：008 plan长12057 bytes；SHA256 `1935d89ad16a59a52ad62b2e00b4b43f30e783ade40fe481fc6063d905da64ce`；Gitblob `9a1fd3849389fb0155d82d02a91d87c1bf967410`，均匹配授权镜像返回元数据/manifest。
- `code/reconstruct_plan.py`是根据已读官方算法分支重建的脚本，不冒称它与仓库`construct.py`源码字节相同；输出计划字节相同。
- `source/context/formal__SPEC.md`来自旧DELTA的86b副本，**不是**本轮远端65d6c0e SPEC。保留为历史上下文，不能按文件名推定版本。本轮不采用其中旧spill通则。

## 已知读取/验证缺口

- main不含所尝试的PRO4审计更新路径；已在Q1固定分支找到并读到。
- 并发设计起初尝试docs/a根路径返回404，随后在docs/a/e2读到；不据此判私库不可读。
- 容器尝试取授权连接返回的下载地址失败。未向匿名web发送私库请求；随后按已读源码重建并校验发布计划身份。证据包不保存临时下载token。
- Q1/Q2/Q3其他历史完整结果/压缩包并未全部重新获取或重跑；295份早期缺件没有找回。
- 没有重新验收FORM全集、E1全错误域、原生跨平台或共享服务。
- 没有完整proof证明全体Q2/Q3一般计划域存在大商/紧凑D17状态；负例只砍相应主张，不替代各受限域的研究。

## 公共一手资料读取范围

- Baccelli/Cohen/Olsder/Quadrat，Synchronization and Linearity，1992：作者开放版；本轮读§3.2.3、Theorem3.17/3.20及证明的路径解释。仅用于固定时延事件结构；不向共享DDR/浮点机制外推。
- Paige/Tarjan，Three Partition Refinement Algorithms：1986 Princeton TR038原稿前两页引言/关系最粗细化问题的截图，及1987期刊元数据；本轮代码是直接逐轮细化，不冒称实现了该论文优化算法。
- Alur/Dill，A Theory of Timed Automata，1994：摘要及元数据；全文获取失败，不引用未读的具体定理。
