# 本轮 Windows 兼容补丁（本地修改，非上游 0.5.0）

用户明确扩大授权后，基于 `edf9d83f755c4bf00a2dd9fc75ccca2ef8ef5896` 单独开发。原始版本的原生 Windows 阻塞结论保持有效；只有本补丁的精确提交经过审查、并通过本机预检后才用于后续预演。不能把补丁测试与原版本联测混在一起。

## 原始复现与保证边界

真实 Windows NT 10.0.26200 / Node 24.15.0，调用原版 `atomicWrite` 写独立临时普通 JSON，实际抛出 `EPERM`、`syscall=fsync`，位置 `design/authority.mjs:18` 的父目录同步。文件 rename 已完成，目标 JSON 存在且内容完整。因此这是原子写函数在文件替换后的目录同步失败，不是 Python 预检模拟。临时复现残留保留，没有生成或发布真实私钥。

补丁保留同目录独占临时文件、写入、**文件内容 fsync**、关闭和 rename。只有 `process.platform === 'win32'` 跳过父目录 open/fsync；其他平台行为不变。没有 catch EPERM，也不吞掉文件 fsync、创建、写入或 rename 的错误。Windows 下突然断电/内核崩溃时，目录项替换没有额外刷新保证，**不承诺与 POSIX 目录 fsync 等价的断电耐久性**。仍有历史校验、签名和恢复机制，但这些不能补回丢失的目录项；私有状态须备份，损坏时按原 fail-closed 流程恢复。

两处测试 CLI 的 `URL.pathname` 改为 `fileURLToPath`，避免 Windows 的 `/C:/...` 被错误解释。协议、授权、签名和字段版本未修改。

`docs/system-atlas-install.json` 保持原始上游清单；`docs/system-atlas-windows-patch.json` 单独列出修改文件的上游/补丁哈希。预检逐个核对已声明覆盖，其余文件仍按上游清单核对；不是忽略全部 Skill 差异。该清单证明已检出版本的字节匹配，不代替可信代码审查。

## 验证命令

在 Skill 目录：

```sh
npm ci --ignore-scripts
node --test test/atomic-write.test.mjs
npm test
```

新增用例验证实际替换和调用顺序、文件 fsync 的 EPERM/ENOSPC/EACCES 传播、rename EACCES 传播与旧文件保留；POSIX 目录错误用例在 Windows 明确跳过。现有测试另覆盖签名、权限、原子拒绝、冲突、崩溃恢复、真实本地 bare Git、CLI/HTTP 和任务看板。这些本地模拟身份不算多机联测。

运行结果、真实 member 初始化/serve、HTTP/浏览器、GitHub 同步及队长发布新标记回读见后续验证记录；没有运行的项不得标 PASS。本轮截止仍以控制 Issue 为准。

## 本机实际验证与收尾

- 补丁提交：`8992d303412684e2e07b2202ccaecaeacd923280`；独立草稿 PR：https://github.com/huaweibei123/huaweicup2026/pull/11 。这是本人实现；没有将队长并行候选 `ff7025d` 的测试当成本提交测试。
- 新增原子写测试：5 PASS，1 POSIX 专属项 SKIP。实际文件替换成功；文件 fsync 的 EPERM/ENOSPC/EACCES 和 rename EACCES 均传播，原文件保留。
- 第一轮相关回归（原始测试路径）：39 项，36 PASS、2 FAIL、1 SKIP。两项失败是 CLI 路径被解析为 `C:\\C:\\...`；修正 `fileURLToPath` 后这两项在全量回归通过。
- 最终 `npm test`：91 项，79 PASS、12 FAIL、0 SKIP，约 320 秒。12 项在创建测试符号链接时出现 `EPERM, syscall=symlink`（output-path 10 项、preview 1 项、system-design 1 项）；没有绕过系统权限或将失败改成通过。现有 team 的签名、授权/撤权、原子批次、ABA/冲突、请求幂等、Git 并发、断网及损坏恢复用例通过；任务看板相关回归通过。本机没有验证完整的符号链接安全测试，PR 保持草稿。
- 本人实际 `team init-member` 在私有工作区外目录成功，退出 0；使用已由本人确认的本轮邀请。`team serve --interval 10` 启动成功，HTTP 200，HTML 标题 `System Atlas · 系统图谱`，真实 GitHub 同步后验签查询 cursor=10。
- 本人完整 board 查询 `complete=true, page.hasMore=false`，3 个任务：fit 为 done，protocol/windows-compat 为 todo。没有成员 grant 或写请求，没有将队长的 done 当成本人 doing/review 闭环。
- Agent 实际打开本机浏览器并切换 Board，看到全部 7 个任务及本人 3 项。后续协作版本面板检查遇到浏览器会话失效，未完成同 cursor UI/CLI 版本核对；HTTP 不代替视觉验收。未完成队长新标记回读、成员签名写入、F1/F2/F3 真机测试。
- [公开启动证据及身份](https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780541691)。未公开私钥、session URL 或完整私有状态。
- 本轮原截止 2026-09-23T00:56:45+08:00；实际核对命令行后停止本人 serve 的时间为 **00:57:12+08:00**，晚约 27 秒。保留私有身份和证据，不重建身份或清空状态；未安装永久服务。后续联机必须由本人恢复并重新约定时限。

## 本人明确续期后的最终补充

本人续期至2026-09-23T01:20+08:00，01:02:28沿用原身份重启，执行代码仍为8992d303；队长审查并另报macOS目标30/30通过（非本人运行macOS）。网页与Agent在cursor15相同revision读取到LIVE-SYNC-adadf7789e，实际Canvas看到accepted17的输入/批注；doing accepted16、F1 forbidden18整批无改、F2 conflict20及保留双方意图修订accepted21均已回读。cursor22真人拖动fit done→doing，本机网页Task data与Agent API相同revision，完整diff仅该任务状态变更。

F3被队长明确暂停以优先真人拖动，未测。最终protocol review+deliverables请求已上传，但截止本机缓存22 receipt=null，不能算accepted；最后缓存亦未包含撤权。本人serve实际01:20:15停止（晚约15秒），没有继续运行联测服务，私有身份保留。完整脱敏时间线与公开回执摘录在[PR7本人结果目录](https://github.com/huaweibei123/huaweicup2026/pull/7)的session-log.md、member-report.md、protocol-evidence.json；本节更新前文首轮停止时的未完成状态，不改原版与完整Windows回归的失败结论。