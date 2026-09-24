# P2 9B 五核测量

固定 parallel3 spec 完成 034–066 共33图；tensor_packet 单 worker，各33次新solver与独立未修改官方E0，E1/E2为0，无重试。

- T0 
09/24/2026 17:32:00
；T1 
09/24/2026 17:36:25
；批墙钟 
265.293092899999
 秒，固定字节/Git预检另计 
7.32613120000315
 秒。
- solver逐图墙钟合计 
58.102889
 秒；外部E0合计 
179.093854
 秒。共享CPU/内存及OS缓存未控制，不作为独占机器速度。
- 保存的官方单核基线逐图B/M算术均值 
3.4029509793959
，仅代表本批33图；五核全100未完成。负向结果也在summary.csv和feed中保留。
- 固定算法 
e64723bdf99669c44f76d8e90ab0379a8578522e
，runner 
fa6522a3266fe040379dd064092beb27c0b20a5e
，官方E0 
45f647b395b84e9569f418fd33d62c2b8eb4d190
；逐图graph/config/official哈希及baseline身份在run.json、measurement-audit.json。
- export_board preflight 33 records/33 eligible；analyze成功；audit_saved.py只读独立核对66份gzip原件、固定源码、feed引用、275250个trace操作区间及单worker阶段顺序，退出码0。Windows仅只读元数据扫描，不运行dot_clean。
