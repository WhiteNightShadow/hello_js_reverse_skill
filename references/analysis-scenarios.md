# 专项场景与工具配方

目录：[常见签名分析场景速查](#常见签名分析场景速查10-个场景) · [调试环境保护策略（反调试对抗速查表）](#调试环境保护策略反调试对抗速查表) · [工具使用最佳实践](#工具使用最佳实践)

先按 [问题路由](problem-routing.md) 定层，再按场景读取。这里是取证操作的配方，不是诊断结论：场景里的特征只是候选解释，当前工具参数以 MCP 契约为准。

## 常见签名分析场景速查（10 个场景）

### 场景 1：请求参数签名（sign/m/token）

```
特征：请求 URL 或 Body 中包含看似随机的签名参数
定位：搜索参数名 → 追踪赋值来源 → 定位签名函数
常见算法：MD5(拼接字符串)、HMAC-SHA256、自定义哈希

MCP 操作：
- search_code(keyword="sign=|m=|token=")
- inject_hook_preset(preset="xhr") → get_request_initiator → 直接定位签名函数
- hook_function(function_path="签名函数名", mode='trace', log_stack=true)
```

### 场景 2：动态 Cookie 生成

```
特征：Cookie 中有频繁变化的字段，页面 JS 动态写入
定位：Hook document.cookie setter → 追踪写入来源
类型：
  a. eval 首包：请求返回混淆 JS → eval 执行 → 写入 Cookie
  b. 预热请求：/api2 等接口返回 JS → 注入 window 变量 → 计算 Cookie
  c. 指纹 Cookie：收集浏览器信息 → base64 编码 → 写入

MCP 操作：
- hook_function(function_path="Document.prototype.cookie",
    hook_code="console.log('Cookie set:', arguments)", position='before')
- inject_hook_preset(preset="crypto") → 捕获加密 I/O
- evaluate_js(expression="document.cookie")
- list_network_requests → 识别预热请求
```

### 场景 3：响应数据加密

```
特征：接口返回的不是明文 JSON，而是加密字符串
定位：Hook JSON.parse 或定位解密函数入口
常见算法：AES-CBC/ECB、DES、RC4、自定义异或

MCP 操作：
- search_code(keyword="decrypt|JSON.parse|atob")
- inject_hook_preset(preset="crypto") → 自动捕获 btoa/atob/JSON.stringify
- hook_function(function_path="解密函数路径", mode='trace', log_args=true, log_return=true)
```

### 场景 4：JS 混淆/OB 混淆

```
特征：大量 _0x 前缀变量、十六进制字符串数组、控制流平坦化
还原：字符串数组还原 → 变量重命名 → 控制流平坦化还原

MCP 操作：
- scripts(action='save', url='<混淆脚本URL>', save_path='./config/obfuscated.js')
- search_code(keyword="关键逻辑关键词") → 定位
- evaluate_js → 在浏览器执行解密函数还原字符串
```

### 场景 5：WASM 加密

```
特征：加密函数调用 WebAssembly 导出函数
还原：Node.js 直接加载 .wasm 文件，调用导出函数
注意：检查 wasm imports，可能需要补环境

MCP 操作：
- search_code(keyword="WebAssembly|.wasm|instantiate")
- list_network_requests → 找 .wasm 文件
- evaluate_js → 测试 wasm 函数的 I/O
```

### 场景 6：疑似 TLS 指纹或协议检测

```
特征：本地请求失败，浏览器成功
先排除：一次性值已用过、会话到期、请求形态差异。这些比传输层常见，也更便宜
确认：把同一个未使用的值分别走干净页面通道、TLS 模拟客户端、普通客户端
      只有这组对照出现稳定分界，才能说是传输层
可选客户端：curl_cffi（Python）、got-scraping（Node.js）

MCP 操作：
- 取得未使用的值，见 signature-source-isolation.md
- 按 protocol-analysis.md 的传输层诊断实验比较
```

### 场景 7：WebSocket 通信

```
特征：数据通过 WebSocket 传输，非 HTTP 接口

MCP 操作：
- inject_hook_preset(preset="websocket") → 一键 Hook WebSocket
- get_console_logs → 获取 WS 消息日志
- evaluate_js → 手动发送/接收 WS 消息

握手失败时列全部凭据来源（Cookie、Header、URL），对照运行时实际读写的位置
```

### 场景 8：字体映射还原

```
特征：页面数字/文字使用自定义字体，复制出来是乱码
还原：下载字体文件 → 解析 CMAP 映射表 → 建立字符映射关系

MCP 操作：
- list_network_requests → 找字体文件（.woff/.woff2/.ttf）
- evaluate_js → 读取页面实际渲染的文字
```

### 场景 9：首屏挑战或验证

```
特征：业务内容出现之前有挑战页、验证或重定向链

MCP 操作：
- navigate → 不加 Hook，先观察 redirect_chain 和最终状态
- launch_browser(humanize=true) → 需要时启用人性化鼠标移动
- intercept_request(url_pattern="**/*", action="log") → 监控所有请求
- inject_hook_preset(preset="debugger_bypass") → 确有反调试时再用
是否出现验证由目标站决定，不做本地预判
```

### 场景 10：JSVMP + 环境复现（运行原始 SDK）

```
特征：JSVMP 不可拆解，改变环境值会改变输出
判断依据：
  - 算法封装在字节码里，入口可调用
  - 改变环境值导致输出变化
  - 本地值已被来源替换实验定位为问题所在

方法：见 original-sdk-runtime.md
1. 定位入口，确认入参形状
2. 记录 SDK 实际读取，与当前浏览器快照比较
3. 先 seed 后 init，按读值证据回放状态
4. 哨兵实验确认首次读取缓存
5. 离线检查，再有界在线验收

具体补哪些项取决于当前 SDK 的读值，别处的补丁清单只作候选。
补丁要与声明的 UA 一致，例如 Firefox UA 不补 Chromium 独有对象。
模板见 jsdom-env-patches.md，路径 B 的步骤见 path-b-env-emulation.md。
```

---

## 调试环境保护策略（反调试对抗速查表）

| 反调试手段 | 检测方式 | 绕过方案 |
|---|---|---|
| `debugger` 定时器 | `setInterval(() => { debugger; }, 100)` | `inject_hook_preset(preset="debugger_bypass")` |
| `Function.toString` 检测 | 检查 Hook 函数的 toString 是否暴露 | `hook_function(..., non_overridable=true)` |
| 时间差检测 | `Date.now()` 前后差值判断是否被调试 | 不暂停执行，用 trace 模式 |
| 控制台检测 | 检测 `console` 对象是否被修改 | 不修改 console，用 MCP 的 `get_console_logs` |
| 原型链检测 | 检查 `XMLHttpRequest.prototype.open.toString()` | `non_overridable=true` 自动伪装 toString |
| 堆栈深度检测 | 通过 Error.stack 行数判断是否有 Hook 层 | 使用 `position="replace"` 减少堆栈层数 |
| `window.outerHeight - window.innerHeight` | 检测 DevTools 是否打开 | 先观察实际浏览器与页面行为，不据此保证不可检测 |

### 反调试处理流程

```
1. 首次 navigate 后如果页面卡住/白屏：
   → inject_hook_preset(preset="debugger_bypass")
   → instrumentation(action='reload')

2. 如果 Hook 被页面 JS 覆盖：
   → hook_function(..., non_overridable=true)
   → 或 inject_hook_preset 前加 persistent=true

3. 如果 console.log 被重写导致看不到输出：
   → 用 get_console_logs（MCP 层面捕获，不依赖页面 console）
```

---

## 工具使用最佳实践

### MCP 工具配合模式

```
黄金路径（最快定位签名函数）：
  network_capture(action='start') → 触发请求 → list_network_requests
  → get_request_initiator(request_id=N) → 直达签名函数

环境复现路径：
  compare_env → evaluate_js(分批采集) → 本地 diff → 补丁 → verify_signer_offline

JSVMP 插桩路径：
  instrumentation(action='install', url_pattern=..., mode='ast')
  → instrumentation(action='reload')
  → instrumentation(action='log', type_filter='tap_get') → hot_keys

Cookie 归因路径：
  network_capture(action='start', capture_body=true)
  → inject_hook_preset(preset="cookie", persistent=true)
  → 触发场景 → 按下文「Cookie 归因分析」汇总三个来源
```

### 效率原则

- 优先用 `get_request_initiator` 而非 `search_code` 定位签名函数
- 优先用 `inject_hook_preset` 而非手写 Hook
- 优先用 `instrumentation(action='install')` 而非逐个 `hook_function`
- 分析产物第一时间写入 `config/` 文件，不要内联长字符串
- `inject_hook_preset` 默认持久化；`hook_function` 需要跨导航时显式传 `persistent=True`
- `hook_function(..., non_overridable=True)` 防止页面 JS 覆盖你的 Hook

### 调试方法论

```
源码级插桩判定与后续策略：

| hot_methods 包含 | hot_keys 环境属性 | 候选策略 |
|-----------------|---------------------|------|
| CryptoJS.MD5 / SubtleCrypto.digest / btoa | 很少 | 纯算法还原 |
| 大量自定义 fn 名 | 很少 | 提取 VMP 子片段 + vm 沙箱 |
| CryptoJS / SubtleCrypto | 很多 | 环境复现（路径 B） |

这张表只是起点，策略以当前读值和实验结果为准。
```

### 使用 inject_hook_preset 一键 Hook

```
inject_hook_preset(preset="xhr")              → Hook 所有 XHR 请求
inject_hook_preset(preset="fetch")            → Hook 所有 fetch 请求
inject_hook_preset(preset="crypto")           → Hook btoa/atob/JSON.stringify
inject_hook_preset(preset="websocket")        → Hook WebSocket 消息
inject_hook_preset(preset="debugger_bypass")  → 绕过反调试
inject_hook_preset(preset="cookie")           → Hook document.cookie 写入
inject_hook_preset(preset="runtime_probe")    → 广谱运行时探针
```

### 使用 hook_function 自定义 Hook

```
hook_function(
  function_path="XMLHttpRequest.prototype.open",
  hook_code="console.log('[XHR]', arguments[0], arguments[1])",
  position="before",
  non_overridable=true    → 防覆盖
)
```

### 使用源码级插桩（通用 VMP 利器）

```
# 1. 确认是 VMP（分支很多的分发循环是线索，不是判定）
search_code(keyword='switch', script_url="<VMP脚本URL>", context_chars=500)

# 2. 装插桩
instrumentation(action='install',
  url_pattern="**/<VMP文件>-*.js",
  mode="ast",
  tag="vmp1",
  rewrite_member_access=true,
  rewrite_calls=true
)

# 3. 重载让插桩生效
instrumentation(action='reload')

# 4. 触发操作后读日志
instrumentation(action='log', tag_filter="vmp1", type_filter="tap_get", limit=200)
  → summary.hot_keys 是 VMP 读取的环境属性 top 30

instrumentation(action='log', tag_filter="vmp1", type_filter="tap_method", limit=200)
  → summary.hot_methods 是 VMP 调用的方法 top 30

# 5. 完工移除
instrumentation(action='stop', url_pattern="**/<VMP文件>-*.js")
```

### 使用 pre_inject_hooks 解决首屏挑战页

```
# 首屏挑战场景：
# 普通 navigate 时 challenge JS 已经跑完了，hook 完全漏掉
# 正确做法：
navigate(
  url="https://target.com/",
  wait_until="networkidle",
  pre_inject_hooks=["xhr", "fetch", "cookie_hook"]
)
# 返回 initial_status / final_status / redirect_chain
```

### Cookie 归因分析

```
# 搞清楚某个 Cookie 是 HTTP Set-Cookie 写的、JS 写的，还是两者配合

# 1. 前置条件：网络抓包 + cookie hook 同时开
network_capture(action='start', capture_body=true)
inject_hook_preset(preset="cookie", persistent=true)

# 2. 触发场景（刷新 / 登录 / 点业务按钮）

# 3. 汇总三个来源
list_network_requests + get_network_request   → 响应头里的 set-cookie 及其 URL
evaluate_js(expression="window.__mcp_cookie_log || []", world="main")  → JS 写入、值和调用栈
cookies(action='get')                         → 当前 Cookie 罐，含 HttpOnly

# 4. 按归因结果进一步分析
  a. 只有 HTTP 响应 → 看是哪个接口下发的
  b. 只有 JS 写入 → 从调用栈定位写入函数
  c. 两者都有 → 两步都做
```

MCP v1.8.0 未注册 `analyze_cookie_sources`，以上是手动归因。实际工具清单以当前 schema 为准。

### hook_jsvmp_interpreter 模式选择

```
# proxy 模式（覆盖广，但会改变被观察对象）
hook_jsvmp_interpreter(mode='proxy', persistent=true)

# transparent 模式（干扰较小，覆盖较低）
hook_jsvmp_interpreter(mode='transparent', persistent=true)

# 区别：
# proxy: 装 Proxy 在 navigator/screen/document 等对象上，能看到所有属性读取
# transparent: 只替换 prototype getter，不装 Proxy，不改 Function.prototype
# 选择依据：比较原始与观测两次的结果，proxy 改变了结果就换 transparent 或选择性源码插桩
```

### verify_signer_offline 离线验证

```
# 用真实样本验证签名代码正确性
verify_signer_offline(
  signer_code="(sample) => { return {sign: generateSign(sample.url)}; }",
  samples=[
    {id: "req1", input: {url: "..."}, expected: {sign: "<真实样本值>"}},
    {id: "req2", input: {url: "..."}, expected: {sign: "<真实样本值>"}},
  ]
)
→ 返回 pass_rate + first_divergence（字符级定位首偏差点）
```

---
