# MCP v1.9.4 工具契约

配套 Skill v3.12.0。完整参数快照（MCP v1.9.4）见 [mcp-tools.json](mcp-tools.json)，实际执行时优先读取已安装 MCP 的工具定义。不要将快照的新参数发送给旧版本。

## v1.9.x 新增与兼容行为

| 版本 | 变化 | 兼容说明 |
|---|---|---|
| v1.9.4 | `instrumentation(action="install")` 新增 `tap_stage_calls`，把平坦化 VMP 的分发调用记录成逐状态的 `tap_stage` 事件，日志摘要加 `hot_stages` | 默认关闭；用法和边界见 [阶段对照](jsvmp-source-instrumentation.md#45-平坦化分发的阶段对照)；旧版本不认这个参数 |
| v1.9.3 | `hook_jsvmp_interpreter` 的探针装在页面主世界 | 日志用 `evaluate_js(..., world="main")` 读；更早的版本装在隔离世界，页面脚本的记录一直是空的 |
| v1.9.1 | `launch_browser` 没传的参数改用服务端启动参数（`--headless`、`--os` 等），传了的优先 | 快照里这几个参数不再写默认值 |
| v1.9.0 | 支持用 `uvx` 按标签安装，新增 `--version` | 工具和参数不变 |

## v1.8.0 观测与返回契约

| 工具 | 新能力/修复 | 兼容说明 |
|---|---|---|
| instrumentation | 主世界/Frame 日志、method/静态对象过滤、当前响应缓存、解析与跳过诊断 | AST 现代语法可选本地 Node/随包 Acorn；regex 非空过滤会明确拒绝；对象预览为占位 |
| evaluate_js | result_format=json_ascii 返回未清洗的 ASCII JSON 文本 | 默认 auto 保留；特殊数字/undefined 先标签化；失败不自动重放 |
| hook_function | serialization=preview 减少对象采样副作用；outcome/thrownValue/completion | 默认 json 保留；同步返回 Promise 不等于异步完成，clear 不重置捕获计数 |
| trace_property_access | snapshot_context 明确当前页主 Frame、隔离世界、非事件归属 | collect_values 仍是 stop 后快照，原生覆盖边界不变 |

实操与边界见 [真实源码案例](real-source-cases.md)。

## v1.6 / v1.7 新增与兼容行为

| 工具 | 新能力/修复 | 兼容说明 |
|---|---|---|
| compare_network_requests | 原始 query/Body 与字段差异、明确哈希口径 | 新工具，仅对已有捕获读取 |
| save_response_body | 精确响应实体字节保存、SHA256/partial | 新工具，不补抓、不覆盖文件 |
| take_snapshot | 有界等待与树大小、来源/截断标记 | 旧无参调用保留，默认超时 5 秒 |
| check_environment | 任务级状态指纹、分项就绪、保留已有证据 | 旧字段保留，不自动清理 |
| network_capture | max_body_size、stop 的 wait_timeout_ms；pending/dropped 指标 | 旧 start/stop/clear/status 调用继续可用；ID 清理后不复用 |
| list_network_requests | limit/after_id 增量分页、state/body_state | 默认仍返回列表；domain 匹配修正为主机边界 |
| get_network_request | 采集和读取两层截断元数据 | 保留旧字段；truncated 不再把残缺内容标为完整 |
| export_network_capture | 有版本号的 JSON 文件导出、默认掩码 | 新工具；不重放请求，不覆盖文件 |
| cookies | name/domain 取交集、精确删除选中的 Cookie | 修复旧版扩大删除范围；无条件调用仍清空全部 |
| verify_signer_offline | 输入校验、可选 runtime=node、执行期限 | 默认仍用当前浏览器；签名函数参数为 sample.input 本身 |

`name_filter` 在 Cookie 归因工具中是子串，多个名称分别查询。`get_request_initiator` 仍从 Hook 日志启发式关联调用栈，不能因网络响应精确关联就宣称调用栈也已精确关联。

## 主世界与 Frame

`evaluate_js` 默认 isolated，页面自有对象用 main。`get_page_info().frames` 提供快照，持久 Hook 用 frame_url/frame_name，不能用 frame_index。`pending` 不是捕获成功；用相同 world/Frame 的 get_trace_data 验证。

清理 Trace 不等于卸载 Hook；requires_relaunch 表示锁定属性或初始化脚本需要重建 Context。Attach 模式仅重连无法清掉外部浏览器的初始化脚本。主世界表达式执行失败后不自动换通道重放。

## 已移除的历史能力

Session/Assertion 工具在 MCP v1.0.0 起已移除，使用需求工作区的 manifest/fixture 与 cases 文件。历史 API 列表可通过 Git 旧版本查阅，不作为现行调用依据。旧案例里的工具名按下表替换：

| 旧名称 | 现行写法 |
|---|---|
| `start_network_capture` | `network_capture(action='start')` |
| `get_script_source` | `scripts(action='get', url=...)` |
| `get_cookies` | `cookies(action='get')` |
| `trace_function`、`set_breakpoint_via_hook` | `hook_function(mode='trace')` + `get_trace_data` |
| `add_init_script` | 无通用替代；预设用 `inject_hook_preset`，函数级用 `hook_function(..., persistent=True)` |
| `bypass_debugger_trap` | `inject_hook_preset(preset="debugger_bypass")` |
| `instrument_jsvmp_source`、`get_instrumentation_log`、`stop_instrumentation` | `instrumentation(action='install' / 'log' / 'stop')` |
| `reload_with_hooks` | `instrumentation(action='reload')` |
| `get_runtime_probe_log` | `inject_hook_preset(preset="runtime_probe")` 后读 `window.__mcp_runtime_log` |
| `dump_jsvmp_strings`、`find_dispatch_loops` | `scripts(action='save')` 后本地分析，或 `search_code` |
| `get_fingerprint_info`、`check_detection` | `compare_env`、`evaluate_js` |
| `analyze_cookie_sources` | MCP v1.8.0 源码存在但未注册，按 [手动归因](analysis-scenarios.md#cookie-归因分析) |

两处容易写错的名字：`inject_hook_preset` 的 Cookie 预设叫 `cookie`，`navigate(pre_inject_hooks=[...])` 里叫 `cookie_hook`，写成 `cookie` 会返回 unknown hook name。`navigate` 没有 `via_blank` 参数。

## 更新契约快照

维护者在两个仓库同级时运行：

```bash
python scripts/check-mcp-contract.py --mcp-root ../camoufox-reverse-mcp
python scripts/check-mcp-contract.py --mcp-root ../camoufox-reverse-mcp --write
```

第一次比较快照，工具或参数发生变化时失败；第二次在完成兼容检查后更新快照。该脚本需要 MCP 仓库的 Python 依赖，仅读取工具注册，不启动浏览器。
