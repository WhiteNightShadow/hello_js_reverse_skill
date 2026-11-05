# 错误排查指南

## 请求失败排查流程

### 步骤 0：确认这是一次有效的失败

动手之前先回答三个问题，否则后面的排查都建立在错误事实上：

1. 请求真的发出去了吗？未发送、超时和被拒绝是三件事，见 [结果分类](controlled-experiments.md#结果分类)。
2. 控制组此刻成立吗？页面自身路径也失败时，先恢复基线。
3. 实验是否跨过了凭据到期点？跨过了这次失败就不能归因。

### 排查顺序

当协议脚本请求返回非预期结果时，不要盲目大改，按代价从低到高逐项排查。这是默认顺序，已有证据时可以跳过：

```
步骤 ① Cookie/Session 失效
  │
  ├─ 排查方法：
  │   · 浏览器 F12 → Application → Cookies 获取最新 Cookie
  │   · 对比脚本使用的 Cookie 与浏览器当前 Cookie
  │   · 检查是否有 HttpOnly Cookie 漏掉（Network 面板看完整 Cookie）
  │
  ├─ MCP 辅助：
  │   · cookies(action='get') → 获取 Camoufox 中的 Cookie
  │   · evaluate_js(expression="document.cookie") → 获取 JS 可见 Cookie
  │
  └─ 常见原因：Cookie 过期、登录态失效、缺少 HttpOnly Cookie

步骤 ② 前置请求遗漏
  │
  ├─ 排查方法：
  │   · Network 面板查看主请求之前的所有请求
  │   · 重点关注：/api/init、/token、/config 等路径
  │   · 检查前置请求的响应中是否有 Token、Session ID
  │
  ├─ MCP 辅助：
  │   · network_capture(action='start') → 触发操作 → list_network_requests
  │   · 按时间排序，找到主请求之前的接口
  │
  └─ 常见原因：漏掉预热接口、Token 获取接口、验证码初始化接口

步骤 ③ 时间戳绑定
  │
  ├─ 排查方法：
  │   · 对比浏览器请求的时间戳与脚本生成的时间戳
  │   · 检查精度：秒（10位）vs 毫秒（13位）
  │   · 检查是否有时间窗口限制（如签名有效期 30 秒）
  │
  ├─ 常见坑：
  │   · Python time.time() 返回浮点数，需要 int()
  │   · Node.js Date.now() 返回毫秒
  │   · 服务端可能校验请求时间与服务器时间的差值
  │
  └─ 修复方法：确保签名计算和请求发送使用同一个时间戳值

步骤 ④ Header 缺失或错误
  │
  ├─ 排查方法：
  │   · 逐项对比浏览器 Request Headers 与脚本 Headers
  │   · 重点检查：Content-Type、Referer、Origin、Accept
  │   · 检查自定义 Header（X-开头的、大小写敏感的）
  │
  ├─ 常见坑：
  │   · Header 顺序可能影响（极少数站点）
  │   · sec-ch-ua 等 Client Hints Header
  │   · Accept-Encoding 不支持 br 但发了 br
  │
  └─ 修复方法：完整复制浏览器 Headers，按组删减确认必要项；多发的头也可能导致拒绝

步骤 ⑤ 环境校验
  │
  ├─ 排查方法：
  │   · Hook navigator/screen/canvas 等环境 API
  │   · 检查签名计算是否包含环境指纹
  │   · 对比有无环境值时的请求结果
  │
  ├─ MCP 辅助：
  │   · compare_env → 查看当前环境基线
  │   · search_code(keyword="navigator|screen|canvas") → 搜索环境检测代码
  │
  └─ 关键原则：先验证是否真正参与服务端校验，再决定是否补全

步骤 ⑥ 频率限制
  │
  ├─ 排查方法：
  │   · 降低请求频率重试（间隔 3-5 秒）
  │   · 检查响应中的限流相关字段（rate limit、retry-after）
  │   · 检查是否返回了 429 状态码
  │
  └─ 修复方法：增加请求间隔、使用代理 IP、添加随机延迟
```

---

## 签名值不一致排查

### 逐步对比法

当计算出的签名值与浏览器实际值不匹配时：

```
对比链路（脚本值 vs 浏览器值）：

环节 1：原始输入参数
  ├─ 参数名是否完全一致（大小写、下划线）
  ├─ 参数值是否完全一致
  └─ 是否有隐藏参数（空值但参与签名的参数）

环节 2：参数排序与拼接
  ├─ 参数排序规则（字典序、自定义顺序、原始顺序）
  ├─ 拼接分隔符（& / 空 / 其他）
  ├─ 是否包含 key=value 中的 key 名称
  ├─ 空值参数是否参与拼接
  └─ URL 编码是否在拼接前/后执行

环节 3：时间戳
  ├─ 精度：秒 (10位) vs 毫秒 (13位)
  ├─ 类型：字符串 vs 数字
  └─ 时区：UTC vs 本地时间

环节 4：随机串
  ├─ 长度是否匹配
  ├─ 字符集：hex / alphanumeric / 自定义
  └─ 生成方法：Math.random vs crypto.randomBytes

环节 5：密钥/盐值
  ├─ 密钥值是否正确（注意空格、换行、编码）
  ├─ 密钥是否是硬编码还是动态获取
  └─ 是否有 IV / Salt（AES 加密场景）

环节 6：中间摘要
  ├─ 多次哈希时逐层对比中间值
  └─ 编码格式：hex(小写) vs hex(大写) vs base64

环节 7：最终输出
  ├─ 编码方式：hex / base64 / 自定义
  ├─ 大小写：hex 小写 vs 大写
  └─ 是否有额外处理（截断、拼接前缀等）
```

### 快速定位技巧

```
技巧 1：二分法
  如果有中间值可对比，先对比中间值，
  确定偏差发生在前半段还是后半段

技巧 2：固定输入法
  在浏览器和脚本中使用完全相同的：
  - 时间戳（硬编码一个固定值）
  - 随机串（硬编码一个固定值）
  - 页码（相同页码）
  然后对比签名结果，排除动态因素干扰

技巧 3：打印拼接字符串
  在签名函数的哈希/加密调用之前，
  打印完整的输入字符串，逐字符对比

技巧 4：MCP 辅助对比
  - hook_function(mode='trace', function_path="签名函数")
  - get_trace_data → 获取浏览器端的真实入参和返回值
  - 与脚本端逐项对比
```

---

## 常见错误与解决方案

### HTTP 状态码

| 状态码 | 常见原因 | 排查方向 |
|--------|---------|---------|
| 403 Forbidden | Cookie 失效 / Header 缺失 / 动态值失效 / IP 被封 / TLS 指纹 | 步骤 ①④⑤⑥，再按 [链路 C](problem-routing.md#链路-c浏览器能过本地同样的头不过) |
| 412 Precondition Failed | 签名校验失败 / 缺少前置请求 | 签名对比 + 步骤 ② |
| 429 Too Many Requests | 频率限制 | 步骤 ⑥ |
| 500 Internal Server Error | 参数格式错误 / 数据类型不匹配 | 检查请求 Body 格式 |
| 200 但数据为空 | 参数错误 / 页码越界 / 缺权限 / 软拒绝 | 读业务码，对比同期成功样本，见 [链路 B](problem-routing.md#链路-b服务端拒绝) |

### 加密相关

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| MD5 结果不一致 | 编码问题（UTF-8 vs ASCII） | 确认输入字符串的编码方式 |
| AES 解密失败 | 模式错误（CBC vs ECB）/ Padding 错误 / IV 错误 | 逐一确认模式、Padding、IV |
| Base64 结果多余字符 | URL-safe Base64 vs 标准 Base64 | 检查是否需要 `+/` → `-_` 替换 |
| HMAC 结果不一致 | 密钥编码问题 / 算法类型错误 | 确认密钥是字符串还是 hex bytes |
| RSA 加密失败 | 公钥格式错误 / PKCS1 vs OAEP | 检查公钥格式和填充方案 |

### 环境相关

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| Node.js vm 沙箱报错 | 缺少 DOM API（document/window） | 参考 `environment-patch.md` 补环境 |
| Python execjs 报错 | Node.js 未安装 / JS 代码有语法错误 | 检查 Node.js 环境、验证 JS 代码 |
| WASM 加载失败 | 缺少 imports / 内存不足 | 检查 WASM imports 并补全 |
| Cookie 设置不生效 | domain 不匹配 / path 不匹配 | 确认 Cookie 的 domain 和 path |

---

## Python 特有问题

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| `requests` 请求被拒 | 原因不定，可能是动态值、会话或 TLS | 按 [链路 C](problem-routing.md#链路-c浏览器能过本地同样的头不过) 对照后，确认是传输再换 `curl_cffi` |
| `hashlib.md5()` 报错 | Python 3.9+ FIPS 模式限制 | 使用 `hashlib.md5(usedforsecurity=False)` |
| `execjs` 执行慢 | 每次创建新的 JS 运行时 | 编译后复用 context：`ctx = execjs.compile(js_code)` |
| `pycryptodome` 与 `pycrypto` 冲突 | 同时安装了两个库 | `pip uninstall pycrypto && pip install pycryptodome` |
| 中文编码问题 | 签名包含中文字符 | 使用 `urllib.parse.quote()` 或确认 UTF-8 编码 |
| `httpx` HTTP/2 连接失败 | 缺少 h2 依赖 | `pip install httpx[http2]` |

---

## Node.js 特有问题

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| `crypto` 模块不可用 | 使用了浏览器打包版本 | 确认运行环境是 Node.js 而非浏览器 |
| `vm` 沙箱超时 | JS 代码有死循环 | 设置 `timeout` 选项 |
| `axios` 被 WAF 拦截 | 默认 User-Agent | 自定义完整浏览器 UA |
| HTTP/2 请求失败 | 证书验证失败 | `rejectUnauthorized: false`（调试用） |

---

## 排查工具速查

### MCP 工具

| 排查场景 | MCP 工具 | 用法 |
|---------|---------|------|
| 对比请求差异 | `network_capture(action='start')` + `get_network_request` | 在 Camoufox 中捕获真实请求，与脚本请求对比 |
| 获取真实签名值 | `hook_function(mode='trace')` + `get_trace_data` | 在签名函数设伪断点，捕获真实入参和返回值 |
| 验证环境读取 | `compare_env` + `trace_property_access` | 确认 SDK 实际读取了哪些环境项 |
| 追踪调用链 | `get_request_initiator` | 从请求直接定位到签名函数 |
| 实时对比 | `evaluate_js` | 在浏览器中执行还原后的签名函数，与脚本输出对比 |
| Cookie 归因 | `network_capture` + `inject_hook_preset(preset="cookie")` + `cookies` | 分清 Set-Cookie 与 JS 写入，见 [场景配方](analysis-scenarios.md#cookie-归因分析) |
| 源码级插桩 | `instrumentation(action='install')` + `instrumentation(action='log')` | 对 VMP 做 HTTP 层源码改写，hot_keys 暴露读取集合 |
| 首屏挑战 | `navigate(pre_inject_hooks=[...])` | 挑战页 Hook 预注入 |
| Hook 重载 | `instrumentation(action='reload')` | 重载使持久 Hook 先于页面 JS 执行并清日志 |
| 运行时探针 | `inject_hook_preset(preset="runtime_probe")` | 摸底页面读取和调用，日志在 `window.__mcp_runtime_log` |
| 请求差异 | `compare_network_requests` | 比较已捕获请求，变化字段不等于签名算法 |
| 单变量核对 | `scripts/experiment-ledger.py audit` | 核对两次请求只改了声称的变量 |
