# 浏览器取证契约

使用浏览器抓包、Hook、插桩或原生追踪之前读取。这里是工具层的证据边界，回答“这个返回值能说明什么”；遇到问题该走哪条链路见 [问题路由](problem-routing.md)。工具参数以已安装 MCP 的 schema 为准，完整快照见 [mcp-tools.json](mcp-tools.json)。

## 浏览器采样与诊断


```text
check_environment()
launch_browser()                         # 默认不启用原生 trace
network_capture(action="start", capture_body=True)
navigate(url="<目标地址>")
# 触发代表性操作；等待业务完成信号或确认本次目标请求已进入捕获
network_capture(action="stop", wait_timeout_ms=3000)
list_network_requests(limit=100, after_id=0)
get_network_request(request_id=<捕获ID>, include_body=True)
export_network_capture(save_path="<需求工作区>/artifacts/capture.json")
```

MCP v1.6.0 的采集契约：

- 响应通过原始 Request 对象关联，避免同 URL 并发串数据；完整 Cookie/Set-Cookie 头异步采集，检查 `headers_complete`。`get_request_initiator` 的 Hook 栈仍是 URL 匹配线索，查看 `match_confidence` 并交叉验证，不视为并发请求的精确归因。
- 点击返回不代表异步签名/防抖请求已经发出。先依据页面业务信号或新增请求记录确认操作进展；不要靠重放点击补样本。`stop(wait_timeout_ms)` 不等待未来才发出的请求。
- `stop` 停止新捕获，已捕获的请求仍可完成；`wait_timeout_ms` 有界等待后必须看 `pending_requests/pending_responses`。`clear/reset/close` 会取消当前实例的后台采集任务。
- `body_state=skipped_capacity/failed/pending` 或 `dropped_requests>0` 表示证据不完整；默认保存正文上限 200,000 字符。Playwright 会先读取完整响应，保存上限不是下载内存上限。
- 读取时区分 `response_body_capture_truncated` 和 `response_body_return_truncated`；`max_body_size=-1` 只取已保存内容，不补回已丢失的正文。
- `after_id` 用于增量读取；ID 在当前浏览器实例关闭前单调递增，清理缓冲区不会复用旧 ID。
- 导出默认掩码 Headers、URL 查询值并省略正文；路径仍保留，不等于完全匿名。确需原始样本时显式传 `include_sensitive=True`，需要正文再传 `include_body=True`，产物留在私有需求工作区。导出不覆盖已有文件。
- Cookie 的 `name` 与 `domain` 删除条件取交集，域名按完整边界匹配；Cookie 过滤条件是单个子串，不是正则。

MCP v1.7.0 能力（调用前通过当前工具 schema 确认）：

- `compare_network_requests(request_ids=[...])` 比较 2–10 个已捕获请求，返回变化字段、常量字段、值摘要和完整值哈希。摘要 sha256/length 针对规范化 JSON；对照 HTTP 正文哈希时使用 `body.raw` 项的 `raw_utf8.sha256/bytes`。保留重复 query 值及顺序、`query.raw` 和 `body.raw`；JSON 投影只供解释。不要把变化字段直接认定为签名算法。
- `save_response_body(request_id=..., save_path=...)` 将已捕获的 JS/WASM/JSON/二进制保存到新文件，返回 SHA-256 与字节数。它不会重新请求；默认拒绝残缺正文。先检查 body_state，需要时增加采集上限并有意重采。
- 网络列表旧 `size` 是字符数，`body_bytes` 才是保存的正文实体字节数；详情 `response_body_total_bytes` 也是解压后的实体字节，不直接与压缩 Content-Length 比较。
- 大段源码/二进制优先保存后本地分析；模型只读摘要、相关片段和验证结果。WASM 需校验文件哈希、imports/exports 和真实调用，不能仅凭文件名/截图判定成功。

MCP v1.13.0 证据直落盘与死会话自愈边界：

- `extract_script(request_id=..., json_path=..., output_file=...)` 用于提取经异步接口返回再 `eval` 的动态脚本（无 `<script src>` 资源）；默认 `allow_partial=False` 会拒绝被 `max_body_size` 截断的响应体，遇到报错应调大 `network_capture(max_body_size=...)` 重采而非带残缺半截脚本继续分析。
- `evaluate_js(..., output_file=..., output_encoding="utf8"|"base64")` 适合将运行期解出的大字符串或字节数组（在页面侧转 Base64）直接原子落盘，仅返回短预览与 `sha256`；传入 `cookies(action="header", output_file=...)` 时文件以 `0600` 权限落盘且返回 `header=None`，避免长凭据暴露到对话记录。
- `wait_for(url_pattern=..., mode="request", after_id=...)` 会等待匹配请求及其响应体收尾（非 `pending`）后再返回，可安全衔接 `save_response_body` 或 `extract_script`。
- 当全部标签页关闭或浏览器连接意外断开后，重新调用 `launch_browser()` 会自动清理失效句柄并拉起新实例（返回 `recovered_stale_session=True` 及 `warnings`）；注意旧会话内存中的网络捕获、活动插桩路由与持久 Hook 均已随死会话清空，需按需重新开启采集或路由。

使用旧 MCP 时先查看已安装工具定义，不传新参数；保留原有 `network_capture/list_network_requests/get_network_request` 调用方式即可。

## 观测对行为的影响

首次观察反爬挑战时尽量不加 Hook，先看响应链。签名对环境敏感时优先源码插桩或较少侵入的模式，用受控对比确认观测是否改变行为；案例里的站点分类只是定位线索。

源码日志由 `instrumentation(action="log")` 从主世界读取，iframe SDK需指定相同Frame；现代语法需要本地Node/随包Acorn，保守降级可能原样跳过。源码 `files_rewritten>0` 只说明完成改写，继续检查 runtime 标记、实际日志与当前响应，不能当作脚本已经执行。反混淆/常量折叠先生成独立候选并按 [改写验证](transform-validation.md) 比较行为，不能把可读视图当等价代码。

### 在线改写路由跨导航残留：对照前先核状态与字节哈希

`instrumentation(action="install")` 注册的是会话级持续拦截路由，装上后不随 `navigate`、页签刷新或对话轮次自动消失，直到显式执行 `instrumentation(action="stop")`、`reset_browser_state(clear_active_routes=True)` 或关闭浏览器。注意 `check_environment()` 返回的 `browser.has_residuals` 不检查活动插桩路由，不能单靠它判定无改写残留。

常见误判后果：
- 在改写路由仍激活时页面内 `fetch` 或调用 `scripts(action="get" | "save")`（底层同样经页面上下文 `fetch` 拉取），保存下来的是插桩改写产物，字节数与 `sha256` 均与厂商原版不同，容易被误判成“服务端下发了新版本 SDK”；
- 改写注入的辅助代码可能改变执行路径或全局状态，使同一环境与种子下的载荷出现大量字段偏移，不能用作载荷级比对基线。

操作边界：
1. 任何版本核对或字段/槽位级基线对照开始前，显式调用 `instrumentation(action="status")`，若 `active_patterns` 非空先 `stop` 并刷新干净页面；
2. 归档脚本后立即记录原始字节的 `bytes` 与 `sha256`，后续校准认准该哈希，不同名同哈希或同名异哈希均以字节哈希为准；
3. 将**行为观察会话**（允许开插桩、Hook、断点或调试全局变量）与**载荷基线会话**（无改写路由、未安装 `persistent=True` 主世界初始化 Hook、不向主世界注入 `__trace` 等额外全局键以避免改变 `Object.keys(window)`；若此前已装过持久主世界 Hook 则新建或重启浏览器会话）明确分开，并在结论中注明样本采集自哪类会话。

## 主世界、Frame 与 Hook 生命周期


- 默认 `evaluate_js(..., world="isolated")` 保持兼容；读取页面自有全局或 Hook 页面函数时明确传 `world="main"`。
- 主世界优先 Camoufox `mw:`，不可用时明确标记 `wrappedJSObject` 回退。通道在执行前探测，用户表达式失败后不换通道重放；先核对是否已有副作用。
- 用 `get_page_info().frames` 取得当前 Frame；优先 `frame_url/frame_name`。`frame_index` 仅对当前快照有效，持久 Hook 禁止使用它。
- 异步挂载的目标可用 `hook_function(..., persistent=True, world="main")`；`pending` 只表示注册成功，当前未安装，`pending_reason="frame_not_found"` 表示等待未来 Frame。等待有上限，需要时调整 `wait_timeout_ms`。
- 用相同 world/Frame 的 `get_trace_data` 判断捕获，不要只看 console。日志有界，空结果不能单独证明目标没有运行。
- `get_trace_data(clear=True)` 只清数据，不卸载 Hook；`remove_hooks()` 要检查 `status/warnings/requires_relaunch`。
- 锁定属性与已注册初始化脚本可能无法原位卸载，彻底恢复需要新建 BrowserContext 或重启自有浏览器。Attach 模式仅断开再连接不会销毁外部 Context。
- 完成后关闭本任务拥有的浏览器；Attach 模式保留外部浏览器，不擅自终止他人的工作。

## 原生追踪：仅在需要时启用


先用 `check_environment()` 查 `available_selectors`，需要时选择定制浏览器并传 `enable_trace=True`，确认返回 `engine_trace.enabled=True`。不修改持久化 active，不覆盖缓存，不自动迁移旧安装。

```text
trace_property_access(action="start")
# navigate / click / evaluate_js 触发目标行为
trace_property_access(action="stop", mode="summary", collect_values=True)
```

- reverse.5 声明 77 个固定 Gecko 原生点；不是任意 JS 属性、VM PC/opcode 或字节码追踪。命中是正证据，未命中不是否定证据。
- 检查 `possibly_capped/input_truncated`、`coverage.negative_result_is_conclusive`、进程 `acknowledged`。`ack_supported` 不表示当前进程已经确认。
- 历史文件未知的 hook count/cap 必须保留未知，不能套用当前浏览器的能力。
- `collect_values=True` 只是追踪结束后的安全快照，不是事件发生时的值；敏感或可能有副作用的路径在 `values_skipped`。query 不采值，避免污染追踪。
- 高频记录可能改变时序，不能宣称完全不可检测。启用 engine trace 会临时关闭内容 sandbox；普通启动不受影响。
- 不具备原生追踪时仍可 `compare_env()` + 分批 `evaluate_js`，只补证据支持的环境项，保持 UA 与 API 一致。

## 原生断点调试：仅用于独立观察会话

当静态定位或源码插桩已锁定关键行、热状态或发包出口，需要暂停线程读取闭包词法变量或请求发送瞬间的入参时，可使用协议级断点调试器（如 MCP v1.11.0 的 `rdp_debugger`）：

| 观测手段 | 是否改写页面源码 | 是否暂停 JS 线程 | 擅长取什么证据 | 核心边界 |
|---|---|---|---|---|
| 源码插桩（`instrumentation`） | 是（HTTP 层改写） | 否 | 连续状态序列、`hot_keys`、多拍属性读取 | 大文件上限、语法跳过、源码长度/完整性校验 |
| 原生属性追踪（`trace_property_access`） | 否（Gecko C++ 层） | 否 | 77 个固定引擎入口是否被读取 | 不能任意停行，不记录闭包局部变量 |
| 原生断点调试（如 `rdp_debugger`） | 否（Firefox RDP） | 是 | 暂停帧调用栈、闭包词法作用域、`xhr_breakpoint` 发包前明文入参 | 独立浏览器进程、暂停拉大真实时钟差 |

使用 `rdp_debugger` 时遵守五条证据边界：

- **独立进程与状态隔离**：`rdp_debugger(action="launch")` 通过 `-start-debugger-server` 启动独立于 Playwright `launch_browser` 的浏览器进程和临时目录；两边的网络捕获、已注入 Hook、内存态 Cookie/Storage 不会自动互通。
- **时序与调试面副作用**：断点暂停期间真实时钟（`Date.now()` / `performance.now()`）继续推进，恢复执行后极易触发时间差反调试（`链路 I`），且调试口开启了 `devtools.chrome.enabled`。不要把一次被断点停过的请求遭服务端拒绝当成“算法错”；抓清局部状态后，回到无断点的干净会话或离线环境做收口验证。
- **动态脚本断点生命周期**：固定 URL 脚本按 `source_url` 下的断点可在 `reload` 时自动重挂；当脚本 URL 携带每次变化的随机查询参数且代码列偏移按构建漂移时，用 MCP v1.12.0 起的 `set_breakpoint(url_pattern="...", find="...", occurrence=1)`，在 `reload` / `enable` 时自动匹配新脚本并重算 UTF-16 行列吸附重挂（通过返回值 `reapplied` / `reapply_failed` 核对状态，清理用 `remove_breakpoint(url_pattern=..., find=...)`）；对无 URL 的 `eval` / `new Function` 脚本按 `source`（`sourceId`）下的断点仍绑定在旧 `thread` 上，刷新后返回 `reapply_skipped`。
- **列号基准与自动吸附**：工具入参 `column` 为 1-based（对齐 `Error.stack` 与 DevTools 面板），底层 RDP 为 0-based 并自动吸附到同行最近可停列；单行压缩脚本下断后务必核对返回值里的 `location`、`snapped_from_column_1based` 与 `breakable_positions`。
- **配置继承降级与本地安全**：继承 `CAMOU_CONFIG` 指纹、无认证代理、`headless`、`os`、`locale`、`browser_version`；带认证代理、`headless="virtual"` 及原版 Firefox 下的降级项见返回值 `warnings`。RDP 端口无认证且具备主进程权限，macOS / Linux 优先传 `unix_socket=True`（`0700` 临时目录）；`attach` 模式关闭时不会删除外部浏览器的 socket；源码内含孤立 UTF-16 代理项时 `source` 会替换为 `U+FFFD` 并返回 `lone_surrogates_replaced`。

## 离线验签

```text
verify_signer_offline(
  signer_code="({text}) => ({sign: require('node:crypto').createHash('md5').update(text).digest('hex')})",
  samples=[{input: {text: "abc"}, expected: {sign: "900150983cd24fb0d6963f7d28e17f72"}}],
  runtime="node"
)
```

- 默认 `runtime="browser"` 保留浏览器样本比对；显式 `node` 才能证明该签名代码不依赖浏览器，并需要 Node.js。可用 `crypto/node:crypto`，完整 jsdom 项目请在自己的项目运行，不塞进单函数验证器。
- `expected` 与 `compare_params` 必须指向有效断言；异步签名、缺失结果、超时和抛错均须显式检查。Node vm 不是执行不可信代码的安全边界。
- 离线样本需固定时间/随机输入，或让签名函数显式接收这些值；不要自动改写浏览器全局时间和随机源。
