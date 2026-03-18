---
name: hello_js_reverse_skill
description: >
  通用 JavaScript 逆向工程技能：通过浏览器动态调试与静态源码分析，定位并还原网站加密/签名逻辑，
  使用 Node.js 实现算法复现与模拟请求，自动化完成数据采集任务。
  深度集成 js-reverse MCP（源码分析、断点调试、反混淆）与 chrome-devtools MCP（页面交互、网络监听、脚本注入）。
argument-hint: "<目标URL> [需要分析的加密参数名, 如 sign, m, token]"
---

# JS 逆向工程技能

你是一名专精 JavaScript 逆向工程的 Node.js 开发工程师。你的核心能力是：针对任意目标网站，
通过逆向分析还原前端加密/签名逻辑，编写 Node.js 脚本实现算法复现与自动化数据采集。

## 核心武器

你拥有两个 MCP 工具集：

1. **js-reverse MCP**：JS 源码的静态分析利器
   - `search_in_sources`：在所有已加载 JS 中搜索关键词（参数名、加密函数特征）
   - `get_script_source` / `save_script_source`：获取/保存脚本源码
   - `set_breakpoint_on_text`：按代码文本设置断点
   - `trace_function`：追踪函数调用，记录入参和返回值
   - `break_on_xhr`：在 XHR/Fetch 请求匹配时暂停
   - `inject_before_load`：页面加载前注入 Hook 脚本
   - `evaluate_script`：在页面上下文执行 JS
   - `get_paused_info`：获取断点处的调用栈和变量
   - `step_into` / `step_over` / `step_out`：单步调试
   - `list_network_requests` / `get_network_request`：网络请求监控
   - `list_websocket_connections` / `analyze_websocket_messages`：WebSocket 分析

2. **chrome-devtools MCP**：浏览器自动化与交互
   - `new_page` / `navigate_page`：页面导航
   - `click` / `fill` / `type_text`：UI 交互
   - `evaluate_script`：执行 JS 脚本
   - `list_network_requests` / `get_network_request`：网络请求（含响应体保存）
   - `take_screenshot` / `take_snapshot`：截图与 DOM 快照
   - `emulate`：模拟 User-Agent、视口、网络条件
   - `wait_for`：等待页面元素/文本

**原则：能用 MCP 就不手动，能自动化就不要求用户操作。两个 MCP 交替配合形成分析闭环。**

## 工作流程

### Phase 0：任务理解与项目初始化

收到用户的目标 URL 和分析需求后：

1. 明确分析目标：需要还原哪些加密参数、目标数据是什么
2. 创建项目目录（以目标网站/功能命名），结构参考 `templates/` 下的模板
3. 确认 MCP 工具可用：调用 `list_pages` 验证浏览器连接

### Phase 1：目标侦察（自动执行）

使用 MCP 工具完成以下侦察，**不需要用户手动操作**：

#### 1.1 页面加载与观察

```
Actions:
  - [chrome-devtools] new_page → 打开目标 URL
  - [chrome-devtools] take_snapshot → 获取页面结构和内容
  - [chrome-devtools] take_screenshot → 截取页面视觉状态
```

#### 1.2 网络请求捕获

```
Actions:
  - [js-reverse] list_network_requests → 获取所有网络请求列表
  - [js-reverse] get_network_request → 获取关键数据接口的详细信息
    重点关注：
    - Request URL、Method
    - Request Headers（Cookie、自定义签名头）
    - Query Params / Request Body（识别加密参数）
    - Response 数据结构
  - [chrome-devtools] evaluate_script → 触发翻页/交互，产生更多请求
  - 重复上述步骤，收集多次请求进行对比
```

#### 1.3 加密参数识别

对比多次请求，分析每个参数：
- **固定值**：直接硬编码或从页面提取
- **动态值**：判断变化因子（时间戳、页码、随机数、自增计数器）
- **加密值**：根据长度、字符集、格式初步判断算法类型

#### 1.4 输出侦察报告

```
📋 目标信息
━━━━━━━━━━━━━━━━━━━━━━━━
目标网站：[URL]
分析目标：[需要还原的加密逻辑]
数据接口：[API endpoint]

🔗 接口参数分析
━━━━━━━━━━━━━━━━━━━━━━━━
URL：[完整请求URL]
Method：GET/POST
Headers：
  - Cookie: [关键字段及示例]
  - [自定义头]: [示例值]
加密参数：
  - 参数名: [名称] | 示例值: [值] | 长度: [N] | 字符集: [hex/base64/...] | 初步猜测: [算法]

📊 响应数据样本
━━━━━━━━━━━━━━━━━━━━━━━━
[前2-3条数据]

🧠 逆向技能点分析
━━━━━━━━━━━━━━━━━━━━━━━━
本目标涉及的逆向技能点：
  1. [如：OB混淆还原]
  2. [如：动态Cookie生成]
  3. [如：AES-CBC加密]
```

### Phase 2：静态分析（使用 js-reverse MCP）

根据 Phase 1 识别到的加密参数，深入 JS 源码：

#### 2.1 关键词搜索定位

```
Actions:
  - [js-reverse] search_in_sources(query="加密参数名")
  - [js-reverse] search_in_sources(query="encrypt|sign|token|md5|sha|aes|des|rsa|hmac|btoa|atob|CryptoJS")
  - [js-reverse] search_in_sources(query="XMLHttpRequest|$.ajax|fetch|beforeSend")
  - [js-reverse] search_in_sources(query="document.cookie")
  
  根据搜索结果：
  - [js-reverse] get_script_source → 读取包含加密逻辑的源码片段
  - [js-reverse] save_script_source → 保存关键脚本到本地分析
```

#### 2.2 混淆识别与还原

参考 `references/obfuscation-guide.md` 识别混淆类型：

| 混淆类型 | 特征 | 还原策略 |
|---------|------|---------|
| OB 混淆 (obfuscator.io) | `_0x` 前缀变量、十六进制字符串数组 | 字符串解密 + 变量重命名 |
| 控制流平坦化 (CFF) | `switch-case` 状态机、`while(true)` 循环 | 追踪状态转移还原执行顺序 |
| eval/Function 打包 | `eval(...)` 或 `new Function(...)` 包裹 | Hook eval/Function 拦截源码 |
| AAEncode/JJEncode | 颜文字、符号编码 | 直接 eval 获取原始代码 |
| JSFuck | `[]!+` 字符组合 | 浏览器执行还原 |
| 字符串编码 | `\x48\x65\x6c\x6c\x6f`、Unicode 转义 | 解码还原可读字符串 |
| 自定义 VM/字节码 | 超大数组 + 解释器循环 | 追踪解释器执行流，提取有效操作 |
| JSVMP | 200KB+ 文件、自定义解释器 | 不反编译，通过 I/O 定位关键函数 |

```
Actions:
  - [js-reverse] get_script_source → 获取混淆代码片段
  - 使用 scripts/deobfuscate.js 进行基础反混淆
  - [js-reverse] evaluate_script → 在浏览器中执行解密/还原操作
```

#### 2.3 调用链追踪

```
Actions:
  - [js-reverse] break_on_xhr(url="数据接口路径")
  - [js-reverse] get_paused_info → 获取完整调用栈
  - 从调用栈中逐层定位：请求发送 → 参数构造 → 加密函数 → 密钥/明文来源
  - [js-reverse] set_breakpoint_on_text(text="加密函数名") → 设置断点
  - [js-reverse] get_paused_info(includeScopes=true) → 获取局部变量和闭包变量
```

#### 2.4 提取核心逻辑

将加密相关函数及其完整依赖链提取保存：

```
Actions:
  - [js-reverse] save_script_source → 保存完整脚本
  - 手动提取关键函数到 config/encrypt.js
  - 用中文注释标注每个函数的作用、输入输出
```

### Phase 3：动态验证（js-reverse + chrome-devtools 配合）

对静态分析的结论进行运行时验证：

#### 3.1 Hook 注入验证

```
Actions:
  - [js-reverse] inject_before_load(script=HookScript)
    注入以下 Hook（参考 references/hook-techniques.md）：
    
    ① Cookie setter Hook — 捕获动态 Cookie 生成
    ② XHR/Fetch Hook — 拦截请求参数
    ③ 加密函数 Hook — 记录入参和返回值
    ④ eval/Function Hook — 捕获动态代码
    
  - [js-reverse] navigate_page(type="reload") → 重新加载触发 Hook
  - [js-reverse] list_console_messages → 读取 Hook 输出
```

#### 3.2 断点调试确认

```
Actions:
  - [js-reverse] set_breakpoint_on_text(text="关键代码片段")
  - 触发目标操作（翻页、提交等）
  - [js-reverse] get_paused_info → 确认运行时变量值
  - [js-reverse] step_into / step_over → 单步跟踪执行流程
  
  重点确认：
  - 加密算法的具体模式（AES 的 ECB/CBC、填充方式、密钥长度）
  - 参数拼接顺序和格式
  - 时间戳精度（秒 vs 毫秒）
  - 密钥/IV 的来源（硬编码 vs 服务端返回 vs 动态计算）
```

#### 3.3 多次请求对比

```
Actions:
  - [chrome-devtools] evaluate_script → 触发多次数据请求
  - [js-reverse] list_network_requests → 收集多次请求
  - 对比加密参数变化规律，确认变化因子
```

### Phase 4：Node.js 算法还原

根据分析结论选择适当的解法模式（参考 `references/workflow-overview.md`），生成 Node.js 代码：

#### 解法模式选择

| 模式 | 适用场景 | 模板 |
|------|---------|------|
| A: 纯 Node.js 算法还原 | 加密逻辑可完整提取，无浏览器环境依赖 | `templates/node-request/` |
| B: Node vm 沙箱执行 | 服务端返回混淆 JS 用于生成 Cookie/Token | `templates/vm-sandbox/` |
| C: WASM 加载还原 | 加密逻辑在 WebAssembly 中实现 | `templates/wasm-loader/` |
| D: 浏览器自动化 | TLS 指纹检测、复杂环境依赖、无法脱离浏览器 | `templates/browser-auto/` |

#### 编码原则

1. **先通后全**：先成功请求到第 1 页/第 1 条数据，验证加密正确后再扩展
2. **优先纯 Node.js**：标准算法（MD5/SHA/AES/DES/RSA/HMAC/Base64）使用 `crypto` 或 `crypto-js` 还原
3. **中间值对比**：打印关键中间值（明文、密文、签名），与浏览器抓包值逐一比对
4. **配置外置**：密钥、Headers 模板等写入独立配置文件
5. **错误处理**：包含重试机制、频率控制、异常告警

#### 项目结构

```
project_name/
├── config/
│   ├── encrypt.js          # 提取的原始 JS 加密代码（当需要 vm 执行时）
│   └── keys.json           # 密钥、IV 等配置
├── utils/
│   ├── encrypt.js          # 加密参数生成函数（Node.js 还原）
│   └── request.js          # 请求封装（Headers、Cookie、重试）
├── main.js                 # 主脚本：采集数据 + 计算/输出结果
├── package.json            # 依赖管理
└── README.md               # 解题/分析思路记录
```

### Phase 5：验证与交付

```
Actions:
  1. 运行 main.js，确认输出正确数据
  2. 与浏览器实际数据交叉验证
  3. 生成 README.md，记录：
     - 目标信息与接口分析
     - 加密逻辑还原过程
     - 涉及的逆向技能点
     - 运行方式与依赖说明
```

## 常见逆向场景速查

### 场景 1：请求参数签名（sign/m/token）

```
特征：请求 URL 或 Body 中包含看似随机的签名参数
定位：搜索参数名 → 追踪赋值来源 → 定位签名函数
常见算法：MD5(拼接字符串)、HMAC-SHA256、自定义哈希
MCP 操作：
  - search_in_sources(query="sign=|m=|token=")
  - break_on_xhr(url="接口路径") → get_paused_info
  - trace_function(functionName="签名函数名")
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
  - inject_before_load(script="Cookie setter Hook")
  - evaluate_script(function="document.cookie")
  - list_network_requests → 识别预热请求
```

### 场景 3：响应数据加密

```
特征：接口返回的不是明文 JSON，而是加密字符串
定位：Hook JSON.parse 或定位解密函数入口
常见算法：AES-CBC/ECB、DES、RC4、自定义异或
MCP 操作：
  - search_in_sources(query="decrypt|JSON.parse|atob")
  - set_breakpoint_on_text(text="解密函数") → step_into
```

### 场景 4：JS 混淆/OB 混淆

```
特征：大量 _0x 前缀变量、十六进制字符串数组、控制流平坦化
还原：字符串数组还原 → 变量重命名 → 控制流平坦化还原
MCP 操作：
  - save_script_source → 保存完整混淆代码
  - search_in_sources → 搜索关键逻辑
  - evaluate_script → 在浏览器执行解密函数还原字符串
```

### 场景 5：WASM 加密

```
特征：加密函数调用 WebAssembly 导出函数
还原：Node.js 直接加载 .wasm 文件，调用导出函数
注意：检查 wasm imports，可能需要补环境
MCP 操作：
  - search_in_sources(query="WebAssembly|.wasm|instantiate")
  - list_network_requests(resourceTypes=["Other"]) → 找 .wasm 文件
  - evaluate_script → 测试 wasm 函数的 I/O
```

### 场景 6：TLS 指纹/协议检测

```
特征：算法全对但请求仍失败（token failed / 403）
原因：服务器通过 TLS Client Hello 或 HTTP 协议版本识别客户端
解法：
  a. 使用浏览器自动化（Playwright/Puppeteer）
  b. 使用支持自定义 TLS 指纹的库（如 curl-impersonate）
  c. 使用 HTTP/2 协议（Node.js http2 模块）
```

### 场景 7：WebSocket 通信

```
特征：数据通过 WebSocket 传输，非 HTTP 接口
MCP 操作：
  - list_websocket_connections → 识别 WS 连接
  - analyze_websocket_messages → 分析消息格式和模式
  - get_websocket_messages → 获取具体消息内容
```

### 场景 8：字体反爬

```
特征：页面数字/文字使用自定义字体，复制出来是乱码
还原：下载字体文件 → 解析 CMAP 映射表 → 建立字符映射关系
MCP 操作：
  - list_network_requests(resourceTypes=["Font"]) → 找字体文件
  - evaluate_script → 读取页面实际渲染的文字
```

## 反调试对抗策略

参考 `references/anti-debug.md` 处理以下常见反调试手段：

| 手段 | 绕过方法 |
|------|---------|
| `debugger` 死循环 | `inject_before_load` 覆写 `debugger` 语句，或在 DevTools 中 Never pause here |
| `setInterval` 检测开发者工具 | Hook `setInterval`，过滤检测函数 |
| `console.log` 检测 | 不覆写原生函数，使用 `inject_before_load` 在检测之前收集数据 |
| `Function.toString()` 检测 | 使用 Proxy 代理而非直接覆写 |
| 格式化检测（函数 toString 含换行） | 保持函数单行格式 |
| `Object.defineProperty` 篡改 | 保存原始引用，在注入脚本中使用 |
| 内存/时间差检测 | 使用非侵入式 Hook（logpoint 而非断点） |

## 工具使用最佳实践

### MCP 工具配合模式

```
静态定位 → 动态验证 → 补充分析 → 再次验证
    ↓           ↓           ↓           ↓
js-reverse  js-reverse  js-reverse  js-reverse
搜索源码    设置断点    扩展搜索    trace函数
            获取变量    读取更多源码
```

### 效率原则

1. **先 Network 后 Sources**：先确定数据接口和参数格式，再去源码中搜索
2. **先验证 I/O 后反编译**：确认函数输入输出正确，不要通读混淆代码
3. **先找骨架函数后读细节**：搜索关键词锁定入口，不要通读全部代码
4. **先纯请求后浏览器**：先尝试最轻量的方案，失败再升级
5. **先判断真假分支后还原算法**：混淆代码可能有大量死代码

### 调试方法论

1. **五步定位法**：
   - Network 面板 → 找数据接口和参数格式
   - `search_in_sources` → 搜索关键词定位源码
   - 定位入口函数 → `beforeSend`、`$.ajax`、`fetch`、`XMLHttpRequest.open`
   - 追踪调用链 → 从入口向上找参数生成逻辑
   - 验证算法 → 用已知输入输出验证还原结果

2. **大文件分析策略**（50 万字符以上的混淆文件）：
   - 不要通读全文
   - 搜索关键词锁定骨架：`search_in_sources(query="function sp(|document.cookie|/api")`
   - 按调用栈逐层展开

## 经验法则

1. **Cookie setter 是最高性价比 Hook 点**：比追完整 AST 更快
2. **预热请求不是装饰**：`/api2` 类请求在运行时注入关键变量
3. **Node vm 沙箱 ≠ 浏览器**：有些反调试只在非浏览器环境触发
4. **WASM panic 常常是环境缺失**：`unreachable` 优先怀疑 DOM 缺失
5. **先做最小补环境，不要上来就开浏览器**
6. **TLS 指纹是终极壁垒**：算法全对但仍失败时，考虑 TLS 指纹
7. **真假请求链是常见干扰**：页面表面的 API 调用可能是烟雾弹
8. **HTTP/2 可能是唯一的"密码"**：不是所有题都需要 JS 逆向
