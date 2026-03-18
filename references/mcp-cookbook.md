# MCP 工具使用手册

## 概述

本手册详细说明 `js-reverse` 和 `chrome-devtools` 两个 MCP 服务器的协作使用方式，
提供常见逆向场景下的具体操作步骤。

## 工具速查表

### js-reverse MCP（逆向分析核心）

| 类别 | 工具 | 核心用途 |
|------|------|---------|
| **源码搜索** | `search_in_sources` | 在所有 JS 中搜索关键词 |
| **源码获取** | `get_script_source` | 获取指定脚本的代码片段 |
| **源码保存** | `save_script_source` | 将脚本保存到本地文件 |
| **脚本列表** | `list_scripts` | 列出页面加载的所有脚本 |
| **断点设置** | `set_breakpoint_on_text` | 按代码文本设置断点 |
| **XHR 断点** | `break_on_xhr` | 在 XHR 请求时暂停 |
| **函数追踪** | `trace_function` | 追踪函数调用，记录参数 |
| **暂停信息** | `get_paused_info` | 获取断点处的栈和变量 |
| **单步调试** | `step_into/over/out` | 单步执行 |
| **脚本注入** | `inject_before_load` | 页面加载前注入 JS |
| **脚本执行** | `evaluate_script` | 在页面执行 JS |
| **网络请求** | `list_network_requests` | 列出网络请求 |
| **请求详情** | `get_network_request` | 获取请求完整信息 |
| **请求来源** | `get_request_initiator` | 获取请求的 JS 调用栈 |
| **WebSocket** | `list_websocket_connections` | 列出 WS 连接 |
| **WS 分析** | `analyze_websocket_messages` | 分析 WS 消息模式 |
| **控制台** | `list_console_messages` | 读取控制台输出 |

### chrome-devtools MCP（浏览器自动化）

| 类别 | 工具 | 核心用途 |
|------|------|---------|
| **页面管理** | `new_page` / `navigate_page` / `close_page` | 页面操作 |
| **UI 交互** | `click` / `fill` / `type_text` / `press_key` | 元素交互 |
| **DOM 快照** | `take_snapshot` | 获取页面文本结构 |
| **截图** | `take_screenshot` | 页面截图 |
| **脚本执行** | `evaluate_script` | 执行 JS |
| **设备模拟** | `emulate` | 模拟 UA/视口/网络 |
| **网络请求** | `list_network_requests` / `get_network_request` | 请求监控 |
| **等待** | `wait_for` | 等待文本出现 |
| **对话框** | `handle_dialog` | 处理弹窗 |

## 场景化操作手册

### 场景 1：分析数据接口的加密参数

**目标**：找到接口中加密参数的生成逻辑

```
步骤 1：打开目标页面
  [chrome-devtools] new_page(url="https://target.com")

步骤 2：获取页面结构
  [chrome-devtools] take_snapshot() → 确认页面正常加载

步骤 3：触发数据请求（如翻页）
  [chrome-devtools] click(uid="翻页按钮的uid")
  或
  [chrome-devtools] evaluate_script(function="document.querySelector('.next').click()")

步骤 4：查看网络请求
  [js-reverse] list_network_requests(resourceTypes=["XHR","Fetch"])

步骤 5：获取目标请求详情
  [js-reverse] get_network_request(reqid=目标请求ID)
  → 记录 URL、Headers、Params、Response

步骤 6：获取请求调用栈
  [js-reverse] get_request_initiator(requestId=目标请求ID)
  → 找到发起请求的 JS 函数

步骤 7：搜索加密参数
  [js-reverse] search_in_sources(query="参数名=")
  [js-reverse] search_in_sources(query="参数名")

步骤 8：读取相关源码
  [js-reverse] get_script_source(url="包含加密逻辑的脚本URL", startLine=X, endLine=Y)

步骤 9：设置断点验证
  [js-reverse] set_breakpoint_on_text(text="加密函数调用")
  触发请求 →
  [js-reverse] get_paused_info(includeScopes=true)
  → 查看变量值确认加密逻辑
```

### 场景 2：动态 Cookie 逆向

**目标**：找到 Cookie 的生成逻辑

```
步骤 1：注入 Cookie Hook
  [js-reverse] inject_before_load(script="Cookie setter Hook 代码")

步骤 2：刷新页面触发 Cookie 生成
  [js-reverse] navigate_page(type="reload")

步骤 3：读取 Hook 输出
  [js-reverse] list_console_messages(types=["log"])
  → 找到 Cookie 设置记录和调用栈

步骤 4：根据调用栈定位生成函数
  [js-reverse] search_in_sources(query="目标函数名")
  [js-reverse] get_script_source(url="...", startLine=X, endLine=Y)

步骤 5：分析生成逻辑
  [js-reverse] set_breakpoint_on_text(text="cookie生成代码片段")
  刷新页面 →
  [js-reverse] get_paused_info → 查看入参
  [js-reverse] step_into → 进入加密函数
  [js-reverse] get_paused_info → 查看中间值
```

### 场景 3：混淆代码分析

**目标**：还原混淆的 JS 代码

```
步骤 1：列出所有脚本
  [js-reverse] list_scripts()
  → 找到可疑的混淆脚本（通常文件名无意义或体积很大）

步骤 2：保存混淆脚本到本地
  [js-reverse] save_script_source(url="混淆脚本URL", filePath="./project/obfuscated.js")

步骤 3：搜索关键特征
  [js-reverse] search_in_sources(query="_0x", urlFilter="混淆脚本URL")
  → 确认混淆类型（OB混淆）
  
  [js-reverse] search_in_sources(query="switch|while.*true", urlFilter="混淆脚本URL")
  → 检查是否有控制流平坦化

步骤 4：在浏览器中还原字符串
  [js-reverse] evaluate_script(function="返回字符串数组的代码")
  → 获取解密后的字符串映射

步骤 5：定位关键函数
  [js-reverse] search_in_sources(query="encrypt|sign|md5|aes", urlFilter="混淆脚本URL")
  → 找到加密相关代码的大致位置
  [js-reverse] get_script_source → 获取上下文
```

### 场景 4：WASM 逆向

**目标**：分析 WASM 加密函数的输入输出

```
步骤 1：搜索 WASM 加载代码
  [js-reverse] search_in_sources(query="WebAssembly|.wasm|instantiate")

步骤 2：找到 WASM 文件
  [js-reverse] list_network_requests(resourceTypes=["Other"])
  → 找到 .wasm 文件的请求

步骤 3：分析 WASM 调用
  [js-reverse] search_in_sources(query="exports.|instance.exports")
  → 找到导出函数的调用代码

步骤 4：追踪输入输出
  [js-reverse] set_breakpoint_on_text(text="wasm导出函数调用")
  触发请求 →
  [js-reverse] get_paused_info → 查看入参
  [js-reverse] step_over → 执行函数
  [js-reverse] get_paused_info → 查看返回值

步骤 5：在浏览器中测试
  [js-reverse] evaluate_script(function="调用wasm函数并返回结果")
  → 验证 I/O 关系

步骤 6：下载 WASM 文件
  [chrome-devtools] get_network_request(reqid=WASM请求ID, responseFilePath="./project/main.wasm")
```

### 场景 5：WebSocket 通信分析

**目标**：分析 WebSocket 消息格式和加密

```
步骤 1：列出 WS 连接
  [js-reverse] list_websocket_connections()

步骤 2：分析消息模式
  [js-reverse] analyze_websocket_messages(wsid=连接ID, direction="sent")
  [js-reverse] analyze_websocket_messages(wsid=连接ID, direction="received")

步骤 3：获取具体消息
  [js-reverse] get_websocket_messages(wsid=连接ID, show_content=true)

步骤 4：搜索 WS 相关代码
  [js-reverse] search_in_sources(query="WebSocket|ws.send|onmessage")
```

## 高级技巧

### 使用 trace_function 自动记录函数调用

```
[js-reverse] trace_function(
    functionName="encrypt",
    logArgs=true,
    logThis=false,
    pause=false
)
```
→ 每次 `encrypt` 被调用时自动记录参数，不暂停执行

### 使用条件断点

```
[js-reverse] set_breakpoint_on_text(
    text="fetch(",
    condition="arguments[0].indexOf('/api/data') !== -1"
)
```
→ 只在请求特定接口时暂停

### 使用 inject_before_load 进行预分析

```
[js-reverse] inject_before_load(script=`
    // 记录所有全局变量的创建
    const knownGlobals = new Set(Object.keys(window));
    setInterval(() => {
        const newGlobals = Object.keys(window).filter(k => !knownGlobals.has(k));
        if (newGlobals.length > 0) {
            console.log('[Monitor] 新全局变量:', newGlobals);
            newGlobals.forEach(k => knownGlobals.add(k));
        }
    }, 1000);
`)
```

### 使用 evaluate_script 提取运行时数据

```
[js-reverse] evaluate_script(function=`
    // 提取当前页面的所有 Cookie
    JSON.stringify(document.cookie.split('; ').reduce((obj, pair) => {
        const [k, v] = pair.split('=');
        obj[k] = v;
        return obj;
    }, {}))
`)
```

## 两个 MCP 的分工原则

| 需求 | 使用 js-reverse | 使用 chrome-devtools |
|------|----------------|---------------------|
| 搜索 JS 源码 | ✅ `search_in_sources` | ❌ |
| 设置断点 | ✅ `set_breakpoint_on_text` | ❌ |
| 单步调试 | ✅ `step_into/over/out` | ❌ |
| 函数追踪 | ✅ `trace_function` | ❌ |
| 注入 Hook | ✅ `inject_before_load` | ❌ |
| 页面截图 | ✅ 可以 | ✅ 更灵活（指定元素） |
| UI 交互（点击/输入） | ❌ | ✅ `click/fill/type_text` |
| 模拟 UA/设备 | ❌ | ✅ `emulate` |
| DOM 快照 | ❌ | ✅ `take_snapshot` |
| 保存请求响应到文件 | ❌ | ✅ `get_network_request(responseFilePath)` |
| WebSocket 分析 | ✅ 完整支持 | ❌ |
| 请求调用栈 | ✅ `get_request_initiator` | ❌ |
| 执行 JS | ✅ 支持 `mainWorld` 选项 | ✅ 支持 `args` 传 uid |
