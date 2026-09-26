# 图 5-3 发布后回读

图与脚本发布于固定提交 `7d1bf1e4718596f428696ed4f4b12015003f59ca`，Draft PR [#231](https://github.com/huaweibei123/huaweicup2026/pull/231)。2026-09-27 使用 GitHub 内容接口，按该完整提交读取 `audit.json` 所列 10 件文件及绘图脚本，共 11 件；逐件解码远端内容并核对 SHA-256，全部一致。

- PNG：`fc834110435d4681a2fd8b783bfa34562a30d005a447dcf4a1efcd3ed551babb`
- PDF：`84de74614ec7e63366a5df4bc3637b73178c3ea9f8294fcc7052cbd6d5ac5034`
- Fang 交接 ZIP：`de2563406e59a599d0792d11139a2ad99732967bc65c2e3600287a9bf5539e27`

本收据形成于图件固定提交之后，不列入该提交的 `manifest.json`，不改变已核图像、数据和脚本字节。原 `self-check.md` 中“发布后还须回读”是生成图件时的待办；本次已完成。远端文件一致不等于论文整页排版、科学解释或用户最终验收通过。
