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
