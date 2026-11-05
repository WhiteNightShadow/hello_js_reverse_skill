# 路径 A：算法追踪 — 四板斧完整方法论

目录：[一、四板斧总览](#一四板斧总览) · [二、快速路径（推荐优先试）](#二快速路径推荐优先试) · [三、第一板斧：Hook I/O（确定 I/O 边界）](#三第一板斧hook-io确定-io-边界) · [四、第二板斧：插桩解释器（追踪执行链路）](#四第二板斧插桩解释器追踪执行链路) · [五、第三板斧：日志分析（从海量数据提取签名链路）](#五第三板斧日志分析从海量数据提取签名链路) · [六、第四板斧：源码级插桩（通用 VMP 利器）](#六第四板斧源码级插桩通用-vmp-利器) · [七、路径 A 失败诊断与替代路径](#七路径-a-失败诊断与替代路径) · [八、路径 A 还原策略选择](#八路径-a-还原策略选择) · [九、JSVMP 核心经验（路径 A 专项）](#九jsvmp-核心经验路径-a-专项)

> **触发条件**：遇到 JSVMP 特征且需要算法追踪时按需阅读
>
> **任务检查**：遵循 [task-preflight.md](task-preflight.md)，复用已有证据与首检；案例分类只作线索，验证当前适用性
>
> **版本**：Skill v3.10.0 / MCP v1.8.0（本地现代解析、保守改写、主世界/Frame 日志与证据边界）

---

页面脚本自有全局在隔离上下文中可能不可见。Hook 前先用 `get_page_info().frames`
确认 Frame，再对页面函数显式使用 `hook_function(..., world="main")`；跨导航或
有界等待内的常见赋值式异步挂载函数使用 `persistent=True`。返回 `pending` 只表示
持久脚本已注册、当前文档尚未安装 Hook；必要时调整 `wait_timeout_ms` 或通过
目标挂载信号确认状态，并用相同 world/Frame 的 `get_trace_data` 与业务结果确认命中。
不要因 `pending` 或空日志盲目重放操作；`frame_index` 仅适用于当前快照，持久 Hook 使用
`frame_url` / `frame_name`。源码日志用 `instrumentation(action="log")`，始终读取所选 Frame 的主世界。

## 一、四板斧总览

路径 A 的核心方法论是「从 I/O 两端夹逼 + 中间层插桩 + 选择性源码 tap」。按当前问题选用所需步骤，不要求四斧全部执行。

四板斧的关系：
- **第一 / 二 / 三板斧**：诊断"VM 看外界"（入口）和"外界看 VM"（出口）——适合签名通过 CryptoJS/atob/MD5 等可 hook 原语走的 VMP
- **第四板斧**：诊断"VM 看自己"——适合 VMP 算法全部封装在字节码分发循环 `switch(opcode) { case N: obj[key](args); ... }` 里的场景

### 四板斧概览表

| 板斧 | 名称 | 工具 | 擅长 | 不擅长 | 适用反爬类型 |
|------|------|------|------|--------|-------------|
| 第一斧 | Hook I/O | `inject_hook_preset(xhr/fetch/crypto/cookie)` + `hook_function(..., world='main')` | 请求链路、动态 Cookie、加密原语入口 | VM 内部自实现的 MD5/AES | 需验证 Hook 对行为的影响 |
| 第二斧 | 插桩解释器 | `hook_function(..., mode='trace', world='main')` + 按需解释器探针 | 可定位并可访问函数的调用链 | 闭包内部函数不可直接 Hook；高频日志开销 | 依实际可观测性选择模式 |
| 第三斧 | 日志分析 | `get_trace_data` / 主世界日志 + 反向追踪 | 从已捕获 I/O 推断公式 | 未捕获的数据、preview 占位与容量限制 | 各类已采集证据均可分析 |
| 第四斧 | 源码级插桩 | `instrumentation(action=...)` 的 install / log | 所选 VM 内部属性与调用位置 | 语法/语义 skip、体积限制、完整性检测与观测开销 | 各类均需原始/改写对照 |

### 按观测敏感度的适用性

| 类型 | 可用板斧 | 说明 |
|----------|----------|------|
| **观测敏感**（原始与观测结果不同） | 选择性源码插桩、有限运行时观测或环境复现 | 环境和源码完整性都可能被检查，先对照原始行为 |
| **观测不敏感**（原始与观测结果一致） | 按需使用四斧 | 只对已比较的路径成立，不能推断没有完整性检测 |
| **纯混淆**（obfuscator.io / 自研 VMP） | 静态定位与按需动态验证 | 混淆特征不能排除观察者效应 |

---

## 二、快速路径（推荐优先试）

> 先保留原始产物、成功/失败样本与当前 SDK 基线，再用以下骨架缩小范围。历史站点经验不代表成功率或当前覆盖率。

### 8 步快速流程

```
步骤 1：确认是否 VMP
  search_code(keyword='switch', script_url='<VMP脚本URL>', context_chars=500)
  → 核对真实字节码来源、PC/寄存器/堆栈变化与 dispatch 执行证据；case 数量不能单独区分 VM 和控制流平坦化

步骤 2：按需装运行时探针
  hook_jsvmp_interpreter(mode="transparent", persistent=True)
  → 只在当前问题需要时安装，有限覆盖也需对照原始行为

步骤 3：按需装出口 Hook
  inject_hook_preset("cookie") + inject_hook_preset("xhr", persistent=True)

步骤 4：装源码级插桩（核心）
  instrumentation(action='install', url_pattern="**/<VMP 文件>", mode="ast", tag="vmp1",
                  rewrite_calls=False, filter_object_names=["this.bytecode"])
  （对象路径须替换为当前源码中的静态路径；解析在本地，不依赖页面 CDN）

步骤 5：让所有探针先于 VMP 生效
  instrumentation(action='reload')
  → 检查 status、所选 Frame 主世界 runtime 标记和业务结果

步骤 6：触发目标操作
  evaluate_js / click / type_text → 翻页、搜索、登录等

步骤 7：读所选位置的 hot_keys
  instrumentation(action='log', tag_filter='vmp1', type_filter='tap_get', limit=300)
  → 检查可能 capped / 返回截断；调用摘要需有意开启 rewrite_calls 并调整过滤范围后另行采样

步骤 8：交叉印证
  evaluate_js(expression="window.__mcp_jsvmp_log || []", world="main") + Cookie 归因
  → iframe SDK 使用同一 Frame；对照当前请求和原始结果，不把属性访问当作参与哈希的证明
```

---

## 三、第一板斧：Hook I/O（确定 I/O 边界）

### 目标

确定 JSVMP 的输入（读了什么环境值、接收了什么参数）和输出（生成了什么签名、写了什么 Cookie）。

### 详细步骤

#### 步骤 0：按需选择多路径探针

```
MCP 操作：
  hook_jsvmp_interpreter(mode="transparent", persistent=True)
  → 有限运行时观测；确需 proxy 时先做观察者效应对照，不按站点分类直接启用
```

#### 步骤 1：Hook 出口 — 请求与 Cookie

```
MCP 操作：
  inject_hook_preset("xhr", persistent=True)    → XHR 请求出口
  inject_hook_preset("fetch", persistent=True)   → fetch 请求出口
  inject_hook_preset("cookie", persistent=True)  → 原型链级 cookie hook

  hook_function(function_path='XMLHttpRequest.prototype.open', mode='trace', world='main',
                log_args=True, max_captures=100, serialization='preview')
  → 记录调用入口；确需 non_overridable 时先了解锁定属性的卸载边界

  # Cookie 归因：见 analysis-scenarios.md 的手动汇总
  → 辨识每个 Cookie 是 HTTP Set-Cookie / JS document.cookie / 混合写入
```

#### 步骤 2：Hook 入口 — 加密原语

```
MCP 操作：
  inject_hook_preset("crypto")
  → 自动捕获 btoa/atob/JSON.stringify I/O

  hook_function(
    function_path="String.fromCharCode",
    hook_code="console.log('[MCP] fromCharCode:', JSON.stringify([...arguments]))",
    position="before",
    world="main"
  )
  → 捕获字符编码操作（JSVMP 高频信号）
```

#### 步骤 3：关联出入口数据

```
分析逻辑：
  - 出口捕获到的签名值（如 sign=abc123）
  - 入口捕获到的加密原语调用（如 MD5("timestamp+key")）
  - 关联两者 → 推断签名公式
```

---

## 四、第二板斧：插桩解释器（追踪执行链路）

### 目标

在 JSVMP 解释器层面追踪执行链路，定位字节码分发函数和关键调用。

### 详细步骤

#### 步骤 3：定位字节码分发函数

```
MCP 操作：
  search_code(keyword='switch', script_url='<VMP脚本URL>', context_chars=500)
  → 定位候选 switch，结合实际字节码取值、PC 变化和 dispatch 执行中的状态更新确认解释器
```

#### 步骤 4：分层追踪函数调用

```
MCP 操作（粗粒度 → 中粒度 → 细粒度）：

  # 粗粒度：追踪解释器主函数
  hook_function(
    function_path="<解释器主函数>",
    mode='trace', world='main', serialization='preview',
    log_args=True, log_return=True, log_stack=False,
    max_captures=100
  )

  # 中粒度：追踪子 handler
  hook_function(
    function_path="<子handler函数>",
    mode='trace', world='main', serialization='preview',
    log_args=True, log_return=True, log_stack=True,
    max_captures=50
  )

  # 细粒度：追踪特定加密函数
  hook_function(
    function_path="<加密函数路径>",
    mode='trace', world='main', serialization='preview',
    log_args=True, log_return=True, log_stack=True,
    max_captures=30
  )

  ⚠️ 必须设置 max_captures 限制日志量，高频调用函数（每秒数千次）会爆炸
```

以上函数路径必须在所选主世界可访问；闭包中的解释器不能假定挂在 `window`。
这里显式选择 `serialization="preview"` 避免对象 getter/toJSON；函数 Hook 默认 `json` 为兼容旧用法仍可能有序列化副作用。preview 中对象/函数是占位，需要字段时做受控采样。同步异常核对 `outcome="throw"` / `thrownValue`，Promise 返回的同步完成记录不代表已 settled。

#### 步骤 5：监控签名容器 + 采集环境基准

```
MCP 操作：
  hook_jsvmp_interpreter(mode='proxy', track_props=True)  # 仅在对照证据支持使用时
  → 观察被包装对象的部分读取；可能改变原生性、身份与签名，不能保证全覆盖

  compare_env()
  → 采集浏览器环境基准数据（navigator/screen/canvas/WebGL/Audio/timing）
```

---

## 五、第三板斧：日志分析（从海量数据提取签名链路）

### 目标

从多维度日志中提取签名生成的完整链路。

### 详细步骤

#### 步骤 6：多维度日志采集

```
MCP 操作：
  get_trace_data(world="main")        → 同一 Frame 的函数追踪数据
  evaluate_js(expression="window.__mcp_jsvmp_log || []", world="main") → JSVMP 探针日志
  get_console_logs()                  → 控制台输出
  evaluate_js(expression="window.__mcp_runtime_log || []", world="main") → 运行时探针日志
```

#### 步骤 7：反向追踪法

```
分析方法：
  1. 从已知签名值（如 sign=abc123）出发
  2. 在所有日志中搜索该值首次出现的位置
  3. 从该位置反向追踪：
     - 该值由哪个函数生成？
     - 该函数的输入是什么？
     - 输入又来自哪里？
  4. 逐层追踪直到找到原始明文输入

  这是处理海量日志数据效率最高的方法。
```

#### 步骤 8：验证提取的算法

```
MCP 操作：
  evaluate_js(expression="提取的签名函数(已知输入)", world="main")
  → 对比输出与实际请求中的签名值
  → 一致仅证明该样本匹配；继续验证新输入、状态变化与独立 Node/Python 运行
```

---

## 六、第四板斧：源码级插桩（通用 VMP 利器）

> 闭包内 VM 的补充观测路径，支持范围与验证步骤见 [源码级插桩指南](jsvmp-source-instrumentation.md)。

### 目标

在 HTTP 层对支持且被选中的属性读取和调用位置插入 tap。源码、堆栈、耗时与新增全局均可被观察，不能承诺不改变行为或全量等价。

### 为什么需要第四板斧

若关键逻辑封装在字节码分发循环内，且没有经过可 Hook API，前三斧可能只能提供零散 I/O。是否需要源码插桩，由当前源码和捕获结果判断。

### 详细步骤

#### 步骤 9：安装源码级插桩

```
MCP 操作：
  instrumentation(
    action='install',
    url_pattern="**/<VMP 文件>",
    mode="ast",
    tag="vmp1",
    rewrite_member_access=True,
    rewrite_calls=False,
    filter_object_names=["this.bytecode"]  # 示例，按当前源码定位结果替换
  )

  模式选择：
    - mode="ast"：先用 esprima，失败后本地 Node.js + 随包 Acorn 解析现代语法，无需页面 CDN
    - mode="regex"：保守 whole-program 子集白名单，仅简单读取/单个初始化声明等输入可改写
    - 复杂语法整段原样跳过，不在任意 VMP 中做局部正则替换，也不承诺任何覆盖率
```

可解析不等于可插桩：可选链、`super`、私有成员等可能跳过相关节点；不支持 construct（`new` / `NewExpression`）事件。检查 `last_parser_backend`、`last_skip_reason`、`last_error`，不把 `files_seen` 当作成功改写。

`filter_property_names` 同时约束属性读取与方法调用；`filter_object_names` 支持 `this.bytecode` 等静态路径，不推断动态对象表达式或运行时别名。显式 `mode="regex"` 配非空 `filter_property_names` / `filter_object_names` 会在安装前被拒绝，并建议改用 `mode="ast"`。AST 失败时，默认 `fallback_on_error=True` 也只在未设置这些过滤器时尝试 regex；回退仍可能原样 skip。

默认 `max_file_size=200000` 字节、`on_oversized="selective"`；大文件没有过滤器时原样跳过。先按当前源码收窄范围并关闭不需要的调用改写，避免因文件大而直接切 regex 或强制全量改写。

#### 步骤 10：让插桩先于 VMP 生效

```
MCP 操作：
  instrumentation(action='reload')
  → 新文档加载已注册的 route / 持久 Hook，仍需核对目标 Frame 和实际执行

  保留本任务所需鉴权与基线，不因重新采样自动清 Cookie 或 reset
```

#### 步骤 10.5：验证改写产物实际执行

```
MCP 操作：
  instrumentation(action='status')
  evaluate_js(expression="(() => ({
    tapInstalled: window.__mcp_tap_installed === true,
    logReady: Array.isArray(window.__mcp_vmp_log)
  }))()", world="main")

判定：
  - files_rewritten > 0 且 tapInstalled=false
    → 先核对目标响应、主世界、Frame 与加载时序，再看浏览器解析/执行异常
  - tapInstalled=true 且日志为空
    → 只说明该 Frame 存在 runtime 标记；检查目标 VM 触发、tag/filter、skip 和容量
```

SDK 在 iframe 时，以上 `evaluate_js` 和下面所有 `instrumentation(action="log")` 都指定相同 `frame_url` / `frame_name` / 当前快照的 `frame_index`。`log` 自动读主世界，不接收 `world` 参数。计数是 route 的累计状态，需结合 `last_url` 确认当前目标。

#### 步骤 11：读取插桩日志

```
MCP 操作：

  # 读取属性访问 hot_keys
  instrumentation(action='log', tag_filter='vmp1', type_filter='tap_get', limit=200)
  → summary.hot_keys 告诉你 VMP 读取了哪些属性，按频次倒排
  → 格式示意：{"userAgent":120, "plugins":98, "webdriver":77, "cookie":43, ...}
  → 非本轮测试结果；仅选择 this.bytecode 时不会自动得到上述宿主环境属性
  → 仅为已捕获读取分布，需验证哪些值真正影响签名

  # 读取方法调用 hot_methods
  instrumentation(action='log', tag_filter='vmp1', type_filter='tap_method', limit=200)
  → summary.hot_methods 格式 typeof.methodName，如 object.MD5
  → 默认 objType 不识别具体库，结合源码/I/O 确认算法归属

  # 读取函数调用 hot_functions
  instrumentation(action='log', tag_filter='vmp1', type_filter='tap_call', limit=200)
  → 看有没有 btoa/atob/encodeURIComponent 等熟识函数
```

步骤 9 默认关闭调用改写；方法/函数日志需按需求重新安装对应 AST 配置并采样。
默认源码 preview 对象为 `[object]`、函数为 `[fn]`，primitive 也可能截断；占位不是真实字段或完整 I/O。
日志返回 `world/frame/execution_backend/warning`；检查 `possibly_capped`（原始缓冲区可能达 20,000 条）与 `truncated`（过滤后的返回量超过 limit）。增大 `limit` 不会补回未采集的事件，空日志或缺失尾部事件不能作否定证据。`clear=True` 清空所选 Frame 的整个源码日志缓冲区，先保存需要的证据。

#### 步骤 12：完工清理

```
MCP 操作：
  instrumentation(action='stop', url_pattern="**/<VMP 文件>")
  → 关闭源码级 route
```

停止 route 不会还原当前文档已执行的源码或卸载其他 Hook；恢复基线前先保存证据，按当前 SKILL.md 的生命周期边界处理。

---

## 七、路径 A 失败诊断与替代路径

### 常见失败模式

| 失败表现 | 可能原因 | 应对 |
|----------|----------|------|
| `files_rewritten > 0` 但 `__mcp_tap_installed=false` | 目标响应、世界/Frame、加载时序或解析/执行问题 | 核对目标上下文与浏览器错误，再对照原始产物 |
| runtime 标记存在但源码日志为空 | Frame、tag/filter、未触发、skip 或容量限制 | 查所选主世界、业务信号与日志诊断，不自动重放操作 |
| `hot_keys` 很少 | 所选范围有限、未命中关键位置或观测不完整 | 结合当前源码、skip 和 capped 状态判断，不能按数量断言覆盖不足 |
| 签名值不一致 | 输入/编码、时间随机值、状态、实现差异或观察者效应 | 按输入到输出定位首个偏差，只补证据支持的环境项 |
| `navigate` 反复 412 | 挑战流程、鉴权、网络或观测影响等 | 对照无 Hook 基线与响应链，不直接归因于签名或厂商 |
| AST 失败或 regex 回退后 passthrough | 解析依赖/资源限制、复杂语法不在白名单 | 查 `last_error`、本地 Node/随包 Acorn 与 `last_skip_reason`；保留明确 skip |
| 显式 regex 搭配非空属性/对象过滤器被拒绝 | regex 无法保留选择范围 | 改用 AST；不要删掉必需过滤器以绕过参数校验 |
| 改写触发源码完整性校验 | 任何源码变化都可能被检测 | 停止对应 route，评估不改源码的观测方式；轻改写不保证解决 |

### 按证据选择下一步

1. 先区分原始产物失败、安装/解析/skip、世界/Frame 错位和改写导致的行为变化；修正相关项即可，不重做全量检查。
2. 当前目标受 AST 支持时，调整所需过滤范围与调用选项后做对照。只有整个输入满足 regex 白名单且不需要过滤器时才考虑 regex；不能要求机械执行 `ast → regex`。
3. 源码观测不适用时，可选 `hook_jsvmp_interpreter(mode="transparent")`、可访问函数的 Hook 或已具备能力的原生 trace。`transparent` 不是 instrumentation 模式；JS Proxy 与 Gecko 原生固定点追踪也不是同一种能力，均有证据边界。
4. 需要完整 SDK/VM 执行且环境强绑定时，转 [路径 B](path-b-env-emulation.md) 的最小环境复现；是否使用 proxy 由当前对照结果决定，不按分类假定安全。
5. 在现有任务记录写明实际尝试、证据与剩余依赖，沿用用户确认的交付方式。没有必要先尝试已知不适用的每一层，也不要求为失败另建 case 或项目。

---

## 八、路径 A 还原策略选择

根据已收集的证据选择还原策略；不要求四板斧全部执行。方法名、属性数量与 Cookie 来源都是线索，需要当前源码和业务样本支持：

| 情况 | 策略 | 实现方式 |
|------|------|---------|
| 签名使用标准算法（MD5/HMAC/AES），JSVMP 日志能看到对应 API 调用 | 纯算法还原 | Node.js `crypto` / Python `hashlib` + `pycryptodome` |
| 签名逻辑是标准算法但拼接规则复杂 | 还原拼接逻辑 + 标准算法 | 提取拼接顺序和格式，手动实现 |
| 签名逻辑完全定制化，但 `hot_keys` 清晰暴露输入域 | 提取最小 JS 片段执行 | Node.js `vm` 沙箱 / Python `execjs` |
| VM 接管请求链路，且 Cookie 来源包含 HTTP Set-Cookie | 继续确认服务端初始化与本地签名各自职责 | 先复现协议初始化；SDK 与环境强绑定时考虑路径 B |
| VM 算法全部内联在 dispatch 循环，即便源码插桩 `hot_keys` 也无法还原 | 加载完整 VM + 最小环境 | 转路径 B：优先 jsdom 运行原始脚本 |

### 后续还原路径决策

以下使用结合源码确认后的调用归属；`hot_methods` 本身只记录 `typeof.method`，不能直接给出完整库路径或证明未出现的算法不存在：

```
路径 A-1 — 调用点与 I/O 证实使用 CryptoJS.MD5 / SubtleCrypto.digest 等标准原语
  → 还原输入编码与拼接后，用标准库验证

路径 A-2 — hot_functions 的自定义函数与源码定位到可提取的子片段
  → 提取后在 Node.js vm 验证结果、异常和状态变化

路径 B — 对照证据显示 SDK 与环境强绑定、难以隔离签名函数
  → 按 path-b-env-emulation.md 复现最小环境，并独立处理协议 Cookie 来源
```

---

## 九、JSVMP 核心经验（路径 A 专项）

1. **VM 解释器本身不是目标，签名函数的 I/O 才是目标** — 不要试图反编译字节码
2. **先 Hook 出口确定"要什么"，再 Hook 入口确定"给了什么"** — 出口驱动分析
3. **`hook_function(path, mode='trace', ...)` 对高频调用函数日志量可能爆炸** — 必须设置 `max_captures` 限制
4. **`get_trace_data` 返回的海量数据需要本地过滤** — 用反向追踪法效率最高
5. **regex 是保守 whole-program 白名单** — 模板字符串、正则字面量、调用等复杂语法整段原样跳过；AST 解析成功也不代表所有节点均能改写或产物已执行
6. **所有探针都需评估观察者效应** — Hook/Proxy 可改变原生性与对象身份；源码 tap 可被完整性、堆栈与耗时检测，不能承诺轻改写解决
7. **字符串提取的前提是字符串未被动态解密** — 保存脚本后本地提取的结果全是乱码时，说明字符串已加密
8. **`search_code(keyword='while')` 在超大文件（380KB+）会返回大量无关结果** — 应使用 `search_code(keyword, script_url=url)` 配合更精确关键词
9. **源码改写缓存会核对当前响应内容哈希** — 同 URL 的 SDK 更新不能沿用旧文本；仍需核对当前目标的 status 与运行证据
10. **日志只支持已捕获范围内的结论** — 主世界/Frame、preview 占位、skip 与 possibly_capped 都影响解释；不能把空结果当未执行或把本地样本通过当商业站点成功

---

按当前需要阅读：

- [SKILL.md](../SKILL.md)：当前通用流程与交付约定
- [源码级插桩专项指南](jsvmp-source-instrumentation.md)：参数、健康检查和日志边界
- [骨架案例](../cases/universal-vmp-source-instrumentation.md)：历史线索，需当前适用性验证
- [真实上游本地案例](../references/real-source-cases.md) 与 [准备/验证脚本说明](../scripts/real_cases/README.md)：来源、复现方法与本地验证边界
