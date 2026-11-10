# 深度分析流程

目录：[Phase 0：任务理解与调试环境搭建](#phase-0任务理解与调试环境搭建) · [Phase 0.5：按需查阅相关经验](#phase-05按需查阅相关经验) · [Phase 1：目标侦察（自动执行）](#phase-1目标侦察自动执行) · [Phase 2：源码分析](#phase-2源码分析) · [Phase 3：动态验证](#phase-3动态验证) · [Phase 4：算法还原（Node.js / Python）](#phase-4算法还原nodejs--python) · [Phase 5：验证与交付](#phase-5验证与交付)

仅在 [问题路由](problem-routing.md) 指向深度分析时按当前阶段读取。普通 JSON API 采集先读 [general-collection.md](general-collection.md)，无需逐项执行逆向流程。行为约定与验收以 [SKILL.md](../SKILL.md) 为准。

本文的阶段是操作清单，不是判断依据。走哪条路由当前证据决定；文中的特征、步骤都是候选，换目标后要重新验证。

### Phase 0：任务理解与调试环境搭建

> ⚠️ **开始本段前，确认已完成SKILL.md 中与本任务相关的环境、经验和交付约定检查**。

目标：接收任务，理解业务诉求，搭建 MCP 工具栈。

#### 0.1 任务理解

收到用户的目标 URL 和分析需求后：
1. **明确分析目标**：需要还原哪些加密参数、目标数据是什么
2. **接口分析**：梳理请求的 URL、Method、Headers、Params、Body；识别签名/动态参数；根据参数特征（长度、字符集、结构）给出算法初步判断

#### 0.2 浏览器搭建

```
MCP 操作：
  launch_browser(headless=false)
  → 默认启动反检测浏览器，不启用原生追踪，保留正常 content sandbox

  navigate(url="目标URL")
  → 导航到目标页面

  # 如有 Cookie：
  cookies(action='set', cookies_list=[{name:"k1", value:"v1", domain:".example.com", path:"/"}])
  → 写入 Cookie

  reload()
  → 刷新使 Cookie 生效

  evaluate_js(expression="document.cookie")
  → 验证写入成功
```

#### 0.3 Cookie 写入方法

| 格式 | 处理方式 |
|------|---------|
| Cookie 字符串 `"k1=v1; k2=v2"` | 拆分后构造 `[{name:"k1", value:"v1", domain:".example.com", path:"/"}]` |
| JSON 格式（EditThisCookie 导出） | 直接传入 `cookies(action='set', cookies_list=[...])` |
| Request Headers 中的 Cookie 字段 | 按 `"; "` 拆分后构造数组 |

#### 0.4 项目目录创建

以目标网站/功能命名，结构参考 `templates/` 下的模板：

```
project_name/
├── config/          # 密钥、Headers、JS 代码等配置
├── utils/           # 加密/请求封装
├── main.js          # 主脚本（或 main.py）
├── package.json     # 依赖（或 requirements.txt）
└── README.md
```

### Phase 0.5：按需查阅相关经验

仅在当前任务涉及相应签名、混淆或环境依赖时读取相关案例。若首检已经确认同一版本案例仍适用，直接复用记录；不要求再次全库扫描。资源取证、普通 API 采集和离线代码维护可跳过此阶段。

#### 0.5.1 命中某个 case 的行为

```
readFile("cases/<命中的 case>.md")  # 读取方案方向 + 踩坑记录 + 站点风格

案例的价值是踩坑记录和站点风格,不是可直接运行的代码。
站点会迭代改版,案例代码可能已过期,但踩坑记录不会轻易过期。

命中案例后的执行要求:
1. 精读案例的「踩坑记录」和「关键经验总结」,内化为本次的约束条件
2. Phase 1-5 仍然正常走,用当前环境的实际数据驱动实现
3. Phase 4 编码时,每个实现决策回查案例踩坑记录,确认是否有对应的坑要避开
4. Phase 5 结束后,将本次新发现的踩坑点追加到案例

反模式:
❌ 读了案例 → 只提取方案方向 → 关掉案例 → 自己从零实现 → 踩坑记录里的坑全部重踩
✅ 读了案例 → 踩坑记录内化为约束 → 每步实现时回查 → 遇到问题先查案例再调试

⚠️ 命中案例 = 知道前人踩过哪些坑,不等于有现成可用的代码,也不等于跳过分析流程
```

#### 0.5.2 未命中任何 case 的行为

案例命中与否都不改变流程，继续走 Phase 1-5。需要候选线索时，到 [cases/README.md](../cases/README.md) 的关键词索引查，用 `search_code(keyword="<索引里的关键词>")` 核对当前页面是否出现。

没有命中时先保留需求工作区的分析记录。沉淀规则见 [cases/README.md](../cases/README.md#按需沉淀新案例)。

### Phase 1：目标侦察（自动执行）

使用 MCP 工具完成以下侦察，**不需要用户手动操作**：

#### 1.1 确认调试页面状态

```
Actions:
- Phase 0 中已通过 launch_browser + navigate 启动反检测浏览器并加载目标页面
- take_screenshot → 截取当前页面视觉状态，确认页面正常
- 如需导航到特定子页面：navigate(url="目标子页面")
- 如果涉及登录态，确认 Cookie 已写入且页面内容正确
```

#### 1.2 网络请求捕获

```
Actions:
- network_capture(action='start') → 开始捕获网络流量
- evaluate_js / click / type_text → 触发翻页/交互，产生请求
- list_network_requests → 获取捕获的请求列表（支持过滤）
- get_network_request(request_id=N) → 获取关键接口的详细信息
- get_request_initiator(request_id=N) → 获取可能的 JS 发起栈，核对 match_confidence 与输入证据

重点关注:
- Request URL、Method
- Request Headers（Cookie、自定义签名头）
- Query Params / Request Body（识别加密参数）
- Response 数据结构
- Initiator Stack（直接定位加密函数）
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

🧠 技术分析要点
━━━━━━━━━━━━━━━━━━━━━━━━
本目标涉及的签名分析技术点：
  1. [如：OB混淆还原]
  2. [如：动态Cookie生成]
  3. [如：AES-CBC加密]
```

### Phase 2：源码分析

根据 Phase 1 识别到的加密参数，在调试浏览器页面上深入 JS 源码。

#### 2.1 关键词搜索定位

```
Actions:
- search_code(keyword="加密参数名") → 直接在已加载的 JS 源码中搜索
- search_code(keyword="encrypt|sign|token|md5|sha|aes|des|rsa|hmac|btoa|atob|CryptoJS")
- search_code(keyword="XMLHttpRequest|$.ajax|fetch|beforeSend")
- search_code(keyword="document.cookie")

根据搜索结果：
- scripts(action='get', url='<脚本URL>') → 读取包含加密逻辑的源码片段
- scripts(action='save', url='<脚本URL>', save_path='./config/target.js') → 保存关键脚本到本地分析
```

#### 2.2 代码混淆识别与还原

| 混淆类型 | 特征 | 还原策略 |
|---|---|---|
| OB 混淆 (obfuscator.io) | `_0x` 前缀变量、十六进制字符串数组 | 字符串解密 + 变量重命名 |
| 控制流平坦化 (CFF) | `switch-case` 状态机、`while(true)` 循环 | 追踪状态转移还原执行顺序 |
| eval/Function 打包 | `eval(...)` 或 `new Function(...)` 包裹 | Hook eval/Function 拦截源码 |
| JSVMP | 大文件、自定义解释器 | 默认不从反编译入手，走路径 A 或路径 B |

#### 2.2+ JSVMP 专项分析（核心能力）

当识别到 JSVMP（JS 虚拟机保护）时，默认不从反编译字节码入手：成本高，而且通常不是取得可用值的必要条件。证据表明确实需要时再做。

**识别标志**：
- 异常大的 JS 文件，函数/变量名完全无意义
- 包含自定义解释器循环：`while(true) { switch(opcode) { ... } }`
- 改写或劫持浏览器原生 API（XHR / fetch / Cookie）
- 超大数组（字节码）+ 指针变量 + 栈操作 + 跳转指令

**路径选择决策**：

| 路径 | 目标 | 方法 | 适用场景 |
|---|---|---|---|
| A：算法追踪 | 搞清 JSVMP 内部算法，用纯代码还原 | 四板斧（Hook/插桩/日志/源码级插桩） | JSVMP 算法可提取、环境依赖少 |
| B：环境复现 | 在 jsdom/vm 或浏览器级运行时中运行原始 JSVMP | 读值证据 → 状态回放 → 验证 | JSVMP 与环境深度绑定、算法不可提取 |

```
决策树：
├─ JSVMP 是否劫持了请求链路（XHR/fetch 拦截器）？
│   ├─ YES + 改变环境值会改变输出
│   │   → 优先选路径 B（环境复现）
│   │   → 路径 B 失败时回退路径 A
│   └─ YES 但签名逻辑相对独立
│       → 路径 A（算法追踪），提取签名函数
│
├─ JSVMP 仅生成签名参数（不劫持请求）？
│   ├─ Hook 确认使用标准算法 → 路径 A，纯算法还原
│   └─ 算法完全自定义 + 环境依赖重 → 路径 B
│
└─ 无法判断 → 先做时间盒内的路径 B 试探，不收敛再走路径 A
```

**位置前置判断**：

```
navigate(url) 不加任何 hook，看响应链和后续请求：

├─ 业务页之前有挑战响应链
│   → 值可能在加载阶段就参与校验，观测容易改变行为
│   → 优先低干扰观测，比较原始与观测两次的结果
│
├─ 首屏正常，业务请求带动态参数
│   → 按需组合 Hook、插桩和环境复现
│
└─ 首屏正常，也没有动态参数
    → 走混淆还原或普通采集
```

这只是选观测手段的线索，状态码和响应链都不能判定厂商或工具禁用规则。

**路径 A：算法追踪（四板斧详细步骤）**

```
第一板斧：Hook 出入口（确定 I/O 边界）
  步骤 0：hook_jsvmp_interpreter → 一键插桩（快速路径，推荐先试）
  步骤 1：Hook 出口 — inject_hook_preset("xhr", persistent=True) + Cookie Hook
  步骤 2：Hook 入口 — inject_hook_preset("crypto") + String.fromCharCode
  → 关联出入口数据，推断签名公式

第二板斧：插桩解释器（追踪执行链路）
  步骤 3：search_code(keyword='switch', script_url=url, context_chars=500)
           定位解释器核心分发函数（while-switch 循环）
  步骤 4：分层 hook_function(function_path=fn, mode='trace', max_captures=N)
           粗→中→细，逐步缩小范围
  步骤 5：hook_jsvmp_interpreter(mode='proxy', track_props=True)
           监控签名容器 + compare_env 采集环境基准

第三板斧：日志分析（从海量数据提取签名链路）
  步骤 6：instrumentation(action='log') + evaluate_js("window.__mcp_jsvmp_log || []", world="main") + get_console_logs
           → 多维度过滤
  步骤 7：反向追踪法 — 从已知签名值反向搜索首次出现位置
  步骤 8：evaluate_js 验证提取的算法，对比签名结果

第四板斧：源码级插桩（通用 VMP 利器，v2.5.0 新增）
  步骤 9：instrumentation(action='install',
           url_pattern="**/<VMP文件>", mode="ast", tag="vmp1")
  步骤 10：instrumentation(action='reload') → 重载让插桩先于 VMP 生效
  步骤 10.5：验证插桩实际执行（不可跳过）
           instrumentation(action='status') → 确认 files_rewritten > 0
           evaluate_js(expression="(() => ({
             tapInstalled: window.__mcp_tap_installed === true,
             logReady: Array.isArray(window.__mcp_vmp_log)
           }))()")
           → files_rewritten > 0 但 tapInstalled=false：
             优先判定为改写产物未解析/未执行，不要误判为原始源码 esprima parse 失败
  步骤 11：instrumentation(action='log', tag_filter="vmp1", type_filter="tap_get")
           → hot_keys 是 VMP 读取的环境属性 top 30
  步骤 12：instrumentation(action='log', tag_filter="vmp1", type_filter="tap_method")
           → hot_methods 是 VMP 调用的方法 top 30
```

**路径 A 还原策略**：

| 情况 | 策略 | 实现方式 |
|---|---|---|
| 签名使用标准算法（MD5/HMAC/AES）| 直接用目标语言还原 | Node.js `crypto` / Python `hashlib` + `pycryptodome` |
| 签名逻辑是标准算法但拼接规则复杂 | 还原拼接逻辑 + 标准算法 | 提取拼接顺序和格式，手动实现 |
| 签名逻辑完全定制化 | 提取最小 JS 片段执行 | Node.js `vm` 沙箱 / Python `execjs` |
| VM 劫持了整个请求链路 | 提取 VM 核心 + 最小环境 | 加载完整 VM 文件但只调用签名入口 |

**路径 B：环境复现（六步法详细步骤）**

```
步骤 1：用 Camoufox 采集真实浏览器完整环境指纹
  MCP 操作：
  - launch_browser({headless: false, os_type: "macos", locale: "zh-CN"})
  - navigate({url: "目标页面", wait_until: "domcontentloaded"})
  - compare_env → 采集主流环境基准数据
  - evaluate_js → 分批采集更细粒度的环境值（分 4-5 批次）：
    批次 A：navigator 属性（24 项）
    批次 B：screen + window 属性（25 项）
    批次 C：document + performance + toString + Function.toString（28 项）
    批次 D：DOM 布局 + Canvas + WebGL + Audio（指纹检测类）
  ⚠️ 单次 evaluate_js 代码太长会报错，必须分批采集

步骤 2：在 jsdom 中运行完全相同的采集代码
  const { JSDOM } = require('jsdom');
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    url: '目标URL', pretendToBeVisual: true, runScripts: 'dangerously'
  });
  const win = dom.window;

步骤 3：做读值差异，不做全量 diff
  只比 SDK 实际读取的项，基线值以当前浏览器快照为准。下面是常见候选，不是服务端规则：
  · Function.prototype.toString、Object.prototype.toString 标签、Symbol.toStringTag
  · navigator.plugins、navigator.webdriver
  · document.hasFocus()、DOM 布局尺寸
  · performance 条目、窗口几何
  · 基线浏览器才有的全局对象（按 UA 判断，例如 window.chrome 只属于 Chromium）
  方法见 original-sdk-runtime.md「读值差异」

步骤 4：编写 patchEnvironment()，只补有读值证据的项
  可能用到的修复模块：
  ① markNative 三层防御（WeakSet + 源码正则 + 实例覆写 + 50+ 原型链扫描）
  ② navigator 补丁（plugins 完整结构 / webdriver / 按 UA 分支决定 userAgentData/connection）
  ③ window 补丁（chrome 对象按 UA 分支 / 30+ API 存根，每个经 markNative 处理）
  ④ document + performance 补丁（hasFocus / readyState / timing / navigation）
  ⑤ DOM 布局属性（offsetHeight/Width/getBoundingClientRect 返回非零值）
  ⑥ Symbol.toStringTag 全面修复（document→HTMLDocument / screen→Screen）

步骤 5：从 jsdom 内部（win.eval）验证所有检测点通过
  验证代码必须在 jsdom 的 window 上下文中执行（win.eval）

步骤 6：端到端验证 — 生成签名 → 请求接口 → 返回有效数据
  - 在 jsdom 中加载完整 JSVMP 脚本并触发签名生成
  - 用截获的签名值发起真实接口请求
  - 确认返回有效数据（非空 body / 非错误码）
  - 连续多次请求验证稳定性（至少 5 次）
  - ⚠️ 服务端可能静默拒绝（HTTP 200 + 空 body）。这只是现象，按问题路由的链路 B 定位，不要默认归因到环境
```

**环境复现还原策略**：

| 情况 | 策略 | 实现方式 |
|---|---|---|
| JSVMP 劫持 XHR，在拦截器中追加签名 | "喂入-截出" | jsdom + XHR Hook → 在 jsdom 内发 XHR，拦截器自动追加签名，Hook 截获 |
| JSVMP 导出签名函数到 window | 直接调用导出函数 | jsdom 加载 JSVMP → `win.签名函数(参数)` → 获取签名 |
| JSVMP + 预热初始化（如 SdkGlueInit）| 完整初始化链路 | jsdom 依次加载所有脚本 → 调用初始化函数 → 再触发签名生成 |

详细步骤见 `references/path-a-four-tools.md` 和 `references/path-b-env-emulation.md`。

#### 2.2++ 静态分析关键判断清单

在源码分析阶段，必须确认以下内容：

- [ ] 参数是单独加密还是整条请求链被接管（URL 重写 / 请求劫持）
- [ ] 页码、时间戳、随机数、Cookie、UA、环境变量是否参与运算
- [ ] 是否存在响应解密（接口返回加密字符串而非明文 JSON）
- [ ] 是否存在运行时代码生成（`eval` / `new Function`）
- [ ] 是否有前置请求（预热接口、Token 获取接口）
- [ ] 是否有请求链改写（拦截 XHR/fetch 添加签名头）

#### 2.3 调用链追踪

```
Actions:
- inject_hook_preset(preset="xhr") → 一键注入 XHR Hook
- inject_hook_preset(preset="fetch") → 一键注入 Fetch Hook
- reload() → 刷新页面触发 Hook
- get_request_initiator(request_id=N) → 获取发起请求的 JS 调用栈（黄金路径）
- 从调用栈中逐层定位：请求发送 → 参数构造 → 加密函数 → 密钥/明文来源
```

#### 2.4 提取核心逻辑

```
Actions:
- scripts(action='save', url='<脚本URL>', save_path='./config/target.js') → 保存完整脚本
- 手动提取关键函数到 config/encrypt.js
- 用中文注释标注每个函数的作用、输入输出
```

### Phase 3：动态验证

对静态分析的结论，在调试浏览器页面上进行运行时验证。

#### 3.0 环境指纹采集（路径 B 使用）

> v3.7.0 对齐 MCP v1.6.0 与 Camoufox Reverse reverse.5。默认分析路径不启用
> 原生追踪；仅在路径 B 确实需要时显式选择定制版。

```
默认分析路径：
  launch_browser()  # enable_trace=False，保留官方 active 与正常 sandbox

需要 Gecko 原生追踪时：
  check_environment()
  → 确认 camoufox.multiversion_supported=True
  → 从 camoufox_reverse.available_selectors 取得精确 reverse selector
  → close_browser()（已有浏览器时）
  → launch_browser(
      browser_version="<available_selectors 返回的精确 selector>",
      enable_trace=True
    )
  → 必须确认返回 engine_trace.enabled=True

交互式追踪窗口：
  trace_property_access(action="start")
  → navigate / click / evaluate_js 触发目标行为
  → trace_property_access(
      action="stop",
      mode="summary",
      collect_values=True
    )

其他动作：
  action="query"   → 不停止，读取当前窗口（禁止 collect_values，避免自污染）
  action="capture" → 新建并阻塞指定 duration 的窗口
  action="status"  → 查看当前 run 与 native acknowledgement
  action="clear"   → 只清理当前 launch 的 trace 与 snapshot

不可用时：
  → compare_env() + 分批 evaluate_js 采集
  → 与 jsdom 环境全量 diff
```

**页面主世界与 Frame 规则**：

- Camoufox 默认 `page.evaluate` 使用隔离上下文；页面脚本挂到 `window` 的扩展属性
  可能不可见。默认 `evaluate_js(..., world="isolated")` 保持兼容；确需读取页面
  自有全局或 Hook 页面函数时，显式使用 `world="main"`。
- `world="main"` 优先走 Camoufox 原生 `mw:` 通道；原生通道不可用时，MCP 会明确
  标记 Firefox `wrappedJSObject` 回退，禁止静默退回隔离世界后把 `undefined` 当真实结果。
- 先用 `get_page_info()` 查看 `frames`，再按需传 `frame_url`、`frame_name` 或当前
  快照的 `frame_index`。持久 Hook 不得使用易变化的 `frame_index`。
- 页面函数可能异步挂载。需要跨导航捕获时使用
  `hook_function(..., persistent=True, world="main")`；返回 `pending` 表示脚本已注册、
  当前文档尚未安装 Hook，不能当作已经命中。当前等待有上限；必要时调整
  `wait_timeout_ms`，或通过后续 reload/navigation 让持久脚本重试。
- 函数 Trace 用 `get_trace_data` 读取，并按需传 `world`、`frame_url`、`frame_name`
  或 `frame_index`；不要只看 `get_console_logs`。主世界对象与函数由页面控制，
  参数/返回值仍按不可信数据处理。捕获数量和缓存均有上限，空结果不能单独证明
  目标函数没有执行。
- `get_trace_data(clear=True)` 只清理数据，不代表卸载 Hook。持久 Hook 可针对尚未创建的
  Frame 预注册，`pending_reason="frame_not_found"` 表示等待该 Frame 出现。
- 主世界通道在执行前探测，执行失败不自动换通道重放；调用可能已产生副作用，先核对页面状态。
- `remove_hooks()` 应检查 `status`、`warnings` 和 `requires_relaunch`。锁定属性可能无法原位恢复，
  已注册初始化脚本也无法从现有 BrowserContext 注销；要求彻底移除时关闭并重新启动浏览器。
  Attach 模式仅重连 MCP 不会销毁外部浏览器，应实际重建外部 BrowserContext 或浏览器。

**证据边界（不可省略）**：

- PropertyTracer 是由当前浏览器声明的**固定原生注入点**组成的 Gecko DOM/Web
  API 覆盖集（reverse.5 为 77 点，旧兼容构建为 75 点），不是任意
  SpiderMonkey 属性、JS 对象、VM PC/opcode 或字节码追踪器。
- 命中是强正证据；未命中不是“未访问”的证明。必须检查
  `coverage.negative_result_is_conclusive=false`。
- `possibly_capped=true` 或 `input_truncated=true` 时结果可能不完整。
- `action="status"` 中 `ack_supported=true` 只表示浏览器支持确认协议；只有
  `acknowledged=true` 才表示当前所有 live native 进程已实际确认。
- `query_trace_file` 的 `possibly_capped=null`、`cap_known=false` 表示历史文件
  没有保存原始事件上限，必须按“未知”处理，不能当成未触发 cap。
- 历史文件也没有浏览器 capability marker；`coverage.hook_count=null`、
  `hook_count_known=false` 必须按未知处理，不能套用当前 reverse.5 的 77 点。
- 它不改写页面 JS 对象、descriptor 或 prototype；高频记录仍可能产生 timing
  side channel，不能描述为“完全不可检测”。
- trace 用于确定优先调查对象；不能据此直接认定“只需补这些属性”。
- `collect_values=True` 仅在 summary 结果上执行追踪结束后的安全 JS 快照。
  `snapshot_values/values` 不是事件发生时的值；Cookie、Canvas、WebGL、
  AudioContext 等敏感或有副作用的路径进入 `values_skipped`。

**并存安装规则**：使用 Camoufox Python 0.5+ 和 release 附带的 installer +
SHA-256，将 reverse.5 安装到 `browsers/whitenightshadow/...`；官方 active 必须与
reverse build 的完整 version/build 一致。通过 `browser_version` 只为一次 MCP
launch 选择定制版。不得覆盖/清空缓存、改变持久化 active 或自动迁移 0.4 用户。

#### 3.1 Hook 注入验证

```
Actions:
- inject_hook_preset(preset="xhr")     → XHR Hook
- inject_hook_preset(preset="fetch")   → Fetch Hook
- inject_hook_preset(preset="crypto")  → 加密函数 Hook（btoa/atob/JSON.stringify）
- hook_function(function_path="自定义目标", hook_code="...", position="before|after|replace")
- reload() → 刷新触发 Hook
- get_console_logs → 读取 Hook 输出
```

#### 3.2 断点与追踪确认

```
Actions:
- hook_function(function_path="加密函数路径", mode='trace',
    log_args=true, log_return=true, log_stack=true)
  → 追踪函数调用（不暂停执行）

- 触发目标操作：evaluate_js / click / type_text → 模拟交互
- get_trace_data → 获取函数追踪数据（指定相同 world/Frame）

重点确认：
- 加密算法的具体模式（AES 的 ECB/CBC、填充方式、密钥长度）
- 参数拼接顺序和格式
- 时间戳精度（秒 vs 毫秒）
- 密钥/IV 的来源（硬编码 vs 服务端返回 vs 动态计算）
- 编码方式（hex / base64 / 自定义字符集）
- 是否有前置依赖（预热请求返回的 token / 动态密钥）
```

#### 3.3 多次请求对比

```
Actions:
- evaluate_js / click → 触发多次数据请求（至少 3 次）
- list_network_requests → 收集捕获的网络请求
- 对比加密参数变化规律，确认变化因子：
  · 哪些参数每次都变（时间戳、随机数、签名值）
  · 哪些参数固定不变（密钥、版本号、设备 ID）
  · 变化参数的变化规律（递增 / 随机 / 时间相关）
```

### Phase 4：算法还原（Node.js / Python）

#### 4.1 语言选择策略

| 维度 | 选 Node.js | 选 Python |
|---|---|---|
| 加密逻辑复杂度 | 自定义逻辑可直接用 `vm` 沙箱执行原始 JS | 标准算法可直接用 Python 库还原 |
| 团队技术栈 | 用户/团队偏好 Node.js | 用户/团队偏好 Python |
| JSVMP 场景 | VM 沙箱可直接加载整个 VM | 需 `execjs` 桥接 |
| TLS 指纹需求 | 需额外配置 | `curl_cffi` 一行搞定浏览器指纹模拟 |

#### 4.2 解法模式选择

| 模式 | 适用场景 | Node.js 模板 | Python 模板 |
|---|---|---|---|
| A: 纯算法还原（路线 R1） | 加密逻辑可完整提取，无浏览器环境依赖 | `templates/node-request/` | `templates/python-request/` |
| B: 沙箱执行 JS | 服务端返回混淆 JS 用于生成 Cookie/Token | `templates/vm-sandbox/` | `templates/python-request/`（用 `execjs`） |
| C: WASM 加载还原 | 加密逻辑在 WebAssembly 中实现 | `templates/wasm-loader/` | — |
| D: 浏览器自动化（仅用户明确要求此交付） | 页面交互采集 | `templates/browser-auto/` | — |
| E: 环境复现（路线 R3、R4） | JSVMP 深度绑定环境、算法不可提取 | jsdom + `references/jsdom-env-patches.md`，或 [浏览器级运行时](original-sdk-runtime.md) | 浏览器级运行时 |

#### 4.3 编码原则

1. **先通后全**：先成功请求到第 1 页/第 1 条数据，验证加密正确后再扩展
2. **优先纯算法**：标准算法 Node.js 用 `crypto` / `crypto-js`，Python 用 `hashlib` / `pycryptodome` / `hmac`
3. **中间值对比**：打印关键中间值，与浏览器抓包值逐一比对
4. **配置外置**：密钥、Headers 模板等写入独立配置文件
5. **错误处理**：包含重试机制、频率控制、异常告警
6. **逐步验证**：每次只增加一个参数的实现，确保每步可独立验证
7. **代码可运行**：提供的代码必须是可直接复制运行的，不留占位符
8. **分析产物持久化**：长参数值、Cookie、JS 代码片段、请求样本等，第一时间写入 `config/` 目录
9. **环境复现最小化**：env-patch 只补经 `hook_function(mode='trace')` 证明 JSVMP 真的读了的 API，禁止"先加上保险"
10. **UA 自洽**：环境补丁的每一项都必须与 `navigator.userAgent` 声明的浏览器一致

#### 4.4 配置文件策略

| 产物类型 | 存放位置 |
|---|---|
| Cookie 字符串 | `config/cookies.txt` 或 `config/cookies.json` |
| 长参数样本 | `config/params_sample.json` |
| 提取的 JS 代码 | `config/sign_logic.js` / `config/encrypt.js` |
| Headers 模板 | `config/headers.json` |
| 响应样本 | `config/response_sample.json` |
| 密文样本 | `config/ciphertext_samples.txt` |

**核心原则**：分析过程中产生的任何长文本，立即持久化到 `config/`。后续代码只需「读取文件」而非「内联长字符串」。

#### 4.5 项目结构

**Node.js 项目**：
```
project_name/
├── config/
│   ├── encrypt.js
│   ├── keys.json
│   └── headers.json
├── utils/
│   ├── encrypt.js
│   └── request.js
├── main.js
├── package.json
└── README.md
```

**Python 项目**：
```
project_name/
├── config/
│   ├── sign_logic.js
│   ├── keys.json
│   └── headers.json
├── utils/
│   ├── sign.py
│   └── request.py
├── main.py
├── requirements.txt
└── README.md
```

### Phase 5：验证与交付

#### 5.1 运行验证

```
Actions:
1. 运行当前任务要求的程序或验证产物：采集结果、独立签名函数或资源文件
2. 签名/API 任务用代表性新输入与成功/失败样本交叉验证（建议至少 5 次，具体范围遵循任务约定）；资源取证验证字节、哈希和真实调用，不制造无关接口请求
3. verify_signer_offline(signer_code, samples=[...]) 用真实样本离线验证签名代码
   - signer_code: JS 代码，evaluating to a function: (sample) => {param: computed_value}
   - samples: [{id, input, expected}] 从真实请求中提取
   - 返回 pass_rate + first_divergence 定位首偏差点
```

#### 5.2 生成 README.md

记录以下内容：
- 目标信息与接口分析
- 加密逻辑还原过程
- 涉及的签名分析技术点
- 运行方式与依赖说明

#### 5.3 经验沉淀

将本次新发现和验证限制记录在需求工作区；具有复用价值时按 `cases/_template.md` 沉淀脱敏案例。用户已授权维护 Skill 时直接更新；发布案例遵循当前任务授权。

沉淀内容包括：
- 反爬类型判定过程
- 关键技术点和踩坑记录
- 已验证的定位路径
- 环境补丁清单（如走路径 B）
- 可验证事实清单（5-15 条最小可验证事实）

#### 5.4 交付清单

| 交付项 | 必须 | 说明 |
|--------|------|------|
| 当前任务要求的可用产物 | ✅ | 采集程序、签名模块或资源文件，按任务类型选择 |
| 必要配置与证据 | 按任务 | 数据/签名程序说明配置；资源任务保留来源、哈希和验证记录 |
| README.md | ✅ | 项目说明 + 接口分析记录 |
| 任务对应的验证 | ✅ | API/签名验证新输入；资源核对字节与调用，不统一要求请求次数 |
| cases/ 经验沉淀 | 按需 | 脱敏、标注适用版本和验证范围 |

#### 5.5 关闭浏览器

```
Actions:
- close_browser()  → 释放浏览器资源
  ⚠️ 分析完成后必须关闭浏览器，不要让浏览器一直开着占用资源
```

---
