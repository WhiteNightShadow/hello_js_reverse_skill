# MCP v1.13.0 工具契约

配套 Skill v3.16.0+。完整参数快照（MCP v1.13.0，43 个工具）见 [mcp-tools.json](mcp-tools.json)，实际执行时优先读取已安装 MCP 的工具定义。不要将快照的新参数发送给旧版本。

## v1.9.x～v1.13.x 新增与兼容行为

| 版本 | 变化 | 兼容说明 |
|---|---|---|
| v1.13.0 | 新增第 43 个工具 `extract_script(request_id / body, json_path, output_file, overwrite, allow_partial)`（从已捕获响应或文本按点分/下标 JSON 路径提取 `fetch`+`eval` 动态脚本并安全落盘，默认拦截截断响应体）；`evaluate_js` 新增 `output_file` + `output_encoding="utf8"\|"base64"` + `overwrite`（求值前预校验常规文件路径、严格要求 JS `string` 返回值并清洗孤立代理项，直接落盘大载荷）；`cookies` 新增 `action="header"` + `url` / `output_file` / `overwrite`（按当前页面 URL 或指定 `url`/`domain` 生成 RFC 6265 `Cookie` 头，传 `output_file` 时 `0600` 落盘且返回 `header=None`）；`wait_for` 新增 `mode="auto"\|"request"\|"navigation"` + `after_id`（等待已捕获请求及其响应体收尾）；修复死浏览器句柄误报 `already_running`（`launch_browser` 自愈返回 `recovered_stale_session=True`，`check_environment` 报告 `usable`）与 `rdp_debugger` 首标签页轮询竞态，共 43 个工具 | `output_file` 统一拒绝符号链接、目录与非普通文件，默认 `overwrite=False` 不覆盖已有文件；`extract_script` 遇到超过 `max_body_size` 的截断响应体默认报错（需增大 `max_body_size` 重采或显式传 `allow_partial=True`）；`cookies(action="header", output_file=...)` 不在上下文回显明文凭据；死会话自动恢复会清空上一实例内存中的捕获、路由与持久 Hook（带 `warnings` 提示） |
| v1.12.0 | `instrumentation(action="install" / "rewrite_source")` 新增 `inject=[{find, before/after, group}]` 与 `inject_validate` 源码级正则插桩（支持 `$1..$n` 展开、字符串/注释/正则/嵌套模板字面量跳过、`switch` 的 `case`/`default` 标签后移、ES2025 Acorn 语法校验与逐组回退，`status` 返回 `inject_hits`、`inject_skipped`、`inject_literal_skips` 及无匹配原因区分）；`intercept_request(action="mock")` 的 `mock_response` 新增 `body_file`（UTF-8 常规文件按请求异步重读、10 MiB 上限，与 `body` 互斥）；`rdp_debugger` 的 `set_breakpoint` / `remove_breakpoint` 新增 `url_pattern` + `find`（+ `occurrence`）跨刷新正则断点，且 `sources` / `source` / `breakable_lines` / `breakable_positions` 同步支持 `url_pattern`，共 42 个工具 | `inject` 受 `max_rewrites` 注入总数上限保护，超过 2 MB 解析校验上限时跳过预解析（`mode="ast"` 在 AST 改写失败时回退，`mode="regex"` 依赖语句规整与词法保护）；`body_file` 相对路径按 MCP 服务工作目录解析且页面可读，勿指向敏感文件；`url_pattern` + `find` 断点在 `reload` / `enable` 时自动重算 UTF-16 行列并吸附重挂，用法见 [源码级插桩指南](jsvmp-source-instrumentation.md#46-按构建变化的非标准-vm源码级正则插桩与本地落盘替换) |
| v1.11.0 / v1.11.1 | 新增第 10 组工具 `rdp_debugger(action=...)`（20 个 action：`launch`、`attach`、`enable`、`sources`、`source`、`breakable_lines`、`breakable_positions`、`set_breakpoint`、`remove_breakpoint`、`wait_paused`、`frames`、`scopes`、`evaluate`、`step`、`resume`、`interrupt`、`reload`、`xhr_breakpoint`、`status`、`close`），走 Firefox 原生 RDP 补齐真断点、单步、调用栈、词法作用域、暂停帧求值与发包前断点；继承 `launch_browser` 指纹/代理/激活版本配置，支持 macOS/Linux `unix_socket=True`，共 42 个工具（v1.11.1 修复 Windows 测试跳过与发版校验，工具契约不变） | `launch` 拉起独立于 Playwright 的浏览器进程与临时目录，状态和网络捕获不与 `launch_browser` 互通；`column` 按 1-based 传入并吸附到同行最近 0-based 可停列；按 `source`（`sourceId`）给 `eval`/`new Function` 下的断点在 `reload` 后返回 `reapply_skipped`；完整证据边界见 [浏览器取证契约](browser-evidence-contract.md#原生断点调试仅用于独立观察会话) |
| v1.10.0 | `instrumentation`：`rewrite_calls` 默认改为关，`max_file_size` 默认 2000000；`status`/`log` 列出 `skipped_files`、`capped_files`；每条事件带 `seq`，状态里的事件带 `stage`，`log` 支持 `after_seq`、`seq_window`、`stage` 并返回 `dropped`；新增 `action="rewrite_source"` 离线改写。同源子 frame 的探针和插桩事件写进顶层日志（`frame_url`/`frame_depth`）；`hook_jsvmp_interpreter` 返回 `coverage`。preset 改装页面主世界，`remove_hooks` 能还原。`compare_env` 补齐 canvas/WebGL/audio，`output_path` 导出环境包。新增 `stage_break`、`trace_session`，共 41 个工具 | 需要调用事件时显式传 `rewrite_calls=True`；读 preset 日志用 `world="main"`；preset 在主世界里页面能察觉，签名型页面不要用；旧版本不认新参数 |
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
