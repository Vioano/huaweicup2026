# 准备脚本修复的有限验证

保留兄弟目录 `failed-setup/` 中的实际失败脚本不动。此副本修复关闭 TarFile 后读取清单、残留未定义 `uv.returncode` 两个问题，并核对 tar 成员与清单恰好匹配。

Sol 在隔离临时目录执行本脚本 AST 的 try-body 解包前缀（到 `stage=python-uv-sync`），同一个固定源包的 65/65 个文件路径、字节数、SHA-256 均通过。源码与输入哈希、截断执行范围见 `bootstrap-fix-check.json`。这只验证解包修复；uv 安装、Python 选择、探针执行以及修复版在 Colab 的运行均未验证。

此副本未在云端运行。修复不抹去原失败，不授权再次创建 VM，不产生新的方案成绩。
