# 多端同步与 Pro 材料交付

2026-09-23 队长授权新增 `Vioano/huaweicup2026` 私有研究副本。组织仓库 `huaweibei123/huaweicup2026` 继续作为团队协作主库；成员电脑继续使用组织仓库为 origin，Issues、PR 和 Atlas 权威通道不变。

## 同步方向与验收

1. 本机 primary 是 `~/Projects/huaweicup2026`。未提交的工作只存在于相应工作区；不得以整目录复制把缓存、密钥和未验收改动当作远端已发布材料。
2. 成员在本人分支提交到组织仓库，通过 PR 汇合；队长公共资料通过检查后合入 main。算法 PR 未验收时保留独立分支。
3. 队长将组织仓库已经发布的 heads/tags 单向同步到 Vioano 私有仓库，保留相同提交 SHA。Vioano 副本供授权研究连接读取，不另开独立开发或第二套 Issues/PR。
4. 不使用强推、`push --mirror`、远端清理或自动删除；出现分叉先报告，不能用同步覆盖另一端变化。已发布的 Atlas 签名分支可以复制，但 Atlas 实际同步 remote、project、epoch、私有状态和授权不变。
5. 共享资料更新、阶段交付、合并后尽快同步；队长周期跟进时检查是否落后。按每次成功回执记录具体 refs/SHA，不声称各端时时相同。
6. 队友收到固定 commit 后保留改动、fetch、补读并回报实际 HEAD/已读/影响。队长不能从 push、HTTP 200、邮箱发信推断成员电脑已同步。

## 队长本机执行

首次已配置 `vioano=https://github.com/Vioano/huaweicup2026.git`；默认 GitHub 通信账号保持 NikolaStarx。同步脚本仅在子进程环境使用本机已登录的两个账号，不把 token 写入文件、URL、命令参数或 Git 配置，也不切换全局账号。

```sh
python3 scripts/sync_vioano_mirror.py
python3 scripts/sync_vioano_mirror.py --push --receipt output/sync/<unique-run-id>.json
```

默认只拉取组织发布的 Git 对象、检查两端并预演推送。`--push` 使用非强制、原子推送并逐 ref 回读。脚本锁位于 Git common dir，防止本机多个 worktree 同时同步；异常遗留锁须先确认没有同步进程，不能盲删。脚本不修改工作区、不合并分支、不上传未提交文件。

## Pro 文件完整性

共享 project 页面列有文件、连接能看到仓库、甚至另一个 Pro 已读到，都不证明当前 Pro 能读取相同内容。每轮先给简短材料索引、固定提交/原件哈希；对当前会话实际缺少的文件直接附加字节，并要求在自己的工具环境回报读取清单与残余缺口。私有 GitHub 必须经有权的连接读取，匿名网页 404 不能靠链接本身解决。

本轮第一路缺少旧 ZIP 引用的 295 份历史完整结果；第二路未取得冻结源码/ZIP 字节；第三路未取得题面和源码。第四路已取得源码文本，但未取得题面/正式 JSON，现由用户主动停止。执行顺序为：补齐前三路材料并完成第二轮追问 → 汇总新结果与证据边界 → 再续第四路。不要提前启动第四路。

现有本机/仓库中没有找到的历史完整结果保持 missing，不能从摘要补造。新运行保存新的输入、命令、版本、完整结果与运行身份，不能冒充旧产物。代码集合哈希配方见 `docs/a/source-manifest.json`，可由 `scripts/a_materials.py` 复核。附件 ZIP、PDF 和单个源码的哈希不等于代码集合哈希。
