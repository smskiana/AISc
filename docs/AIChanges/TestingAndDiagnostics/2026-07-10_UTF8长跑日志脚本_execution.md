> 设计方案: [2026-07-10_UTF8长跑日志脚本_plan.md](2026-07-10_UTF8长跑日志脚本_plan.md)

# UTF-8 长跑日志脚本 — 执行记录

## 完成时间
2026-07-10

## 本次完成内容

这次按“最简单的办法”处理乱码问题，没有继续和宿主控制台代码页硬碰硬，而是直接把长跑压测固化成一个 Python 脚本，让它自己写 UTF-8 文件。

落地结果：

1. 新增正式长跑脚本
2. 长跑原始日志改为 Python 直接写 UTF-8
3. 摘要 JSON 继续由 Python 直接写 UTF-8
4. 不再依赖 `Tee-Object` 抓控制台输出

## 实际改动文件

| 文件 | 改动 |
|------|------|
| `backend/scripts/run_7day_benchmark.py` | 新增长跑脚本：隔离测试库、推进游戏分钟、记录午夜统计、直接写 UTF-8 `.log` 和 `_summary.json` |
| `docs/AIChanges/TestingAndDiagnostics/2026-07-10_UTF8长跑日志脚本_plan.md` | 本轮方案文档 |
| `docs/AIChanges/TestingAndDiagnostics/2026-07-10_UTF8长跑日志脚本_execution.md` | 本执行记录 |

## 脚本行为

脚本入口：

```powershell
python backend/scripts/run_7day_benchmark.py --tag <输出前缀> --minutes <分钟数>
```

默认设计：

1. `--minutes` 默认是 `7 * 1440`
2. `--tag` 决定输出文件名
3. 自动生成：
   - `docs/AIChanges/artifacts/<tag>/<tag>.log`
   - `docs/AIChanges/artifacts/<tag>/<tag>_summary.json`
   - `docs/AIChanges/artifacts/<tag>/data` 与 `SaveData`

## 关键实现说明

### 1. 不再走控制台转存

以前的问题是：

1. 控制台会话是 `cp936`
2. `pwsh` 虽然能跑，但 `Tee-Object` 抓到的仍是终端链路输出
3. 所以 `.log` 里会混进乱码

现在改成：

1. 脚本启动后直接配置 `logging.FileHandler(..., encoding='utf-8')`
2. 摘要 JSON 直接 `encoding='utf-8'` 写文件
3. 即使控制台本身还可能有终端层乱码，落盘文件仍然是干净的

### 2. 隔离测试产物

脚本会自动重定向：

1. `DATA_DIR`
2. `SAVE_DIR`

到 `docs/AIChanges/artifacts/<tag>/` 下，避免污染主库和主 LanceDB。

## 验证方式

### 1. 编译检查

执行：

```powershell
python -m py_compile backend/scripts/run_7day_benchmark.py
```

结果：通过。

### 2. 短时 smoke

执行：

```powershell
python backend/scripts/run_7day_benchmark.py --tag 2026-07-10_utf8_benchmark_smoke --minutes 180
```

生成产物：

1. [2026-07-10_utf8_benchmark_smoke.log](F:/GameProject/unity/AISc/docs/AIChanges/artifacts/2026-07-10_utf8_benchmark_smoke/2026-07-10_utf8_benchmark_smoke.log)
2. [2026-07-10_utf8_benchmark_smoke_summary.json](F:/GameProject/unity/AISc/docs/AIChanges/artifacts/2026-07-10_utf8_benchmark_smoke/2026-07-10_utf8_benchmark_smoke_summary.json)
3. `docs/AIChanges/artifacts/2026-07-10_utf8_benchmark_smoke/`

### 3. 验证结果

1. `.log` 文件中文可正常读取，无 GBK 乱码
2. `_summary.json` 文件中文可正常读取
3. 脚本按预期完成 180 分钟短跑
4. 隔离测试目录正常生成

## 额外说明

1. 终端里仍可能出现少量不是 Python logging 发出的底层库输出，例如 Lance/Rust 的警告
2. 但这些内容现在不会再决定压测日志文件的编码质量
3. 后续做完整 7 天复测时，优先直接用这个脚本即可
