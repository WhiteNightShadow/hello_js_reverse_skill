# JSVMP 源码级插桩专项指南（第四板斧）

目录：[1. 为什么需要源码级插桩](#1-为什么需要源码级插桩) · [2. 两种改写模式：regex vs AST](#2-两种改写模式regex-vs-ast) · [改写状态与运行时健康诊断](#改写状态与运行时健康诊断) · [3. 按需操作骨架](#3-按需操作骨架8-步) · [4. 进阶技巧](#4-进阶技巧) · [5. 常见问题与陷阱](#5-常见问题与陷阱) · [6. 源码级插桩的还原决策](#6-源码级插桩的还原决策) · [7. 参考](#7-参考)

> **Skill v3.13.0 / MCP v1.8.0**（4.5 的阶段对照需要 MCP v1.9.4；日志切片、`rewrite_source` 离线改写和跳过原因需要 v1.10.0）。当前执行接口以 `instrumentation(action=...)` 为准；旧版 MCP 调用前检查实际工具 schema。
>
> 与 `jsvmp-analysis.md` 的第一/二/三板斧互补——前三板斧诊断"VM 看外界 / 外界看 VM"，本文档讲解"VM 看自己"。

---

## 1. 为什么需要源码级插桩

### 1.1 传统 hook 的盲区

**`hook_jsvmp_interpreter`** 等运行时探针只能观察其已包装路径。若 VMP 的关键计算未经过这些 API，就需要其他证据。以下是用于说明盲区的自写 VM 骨架，不是真实上游解释器或某站点的验证产物：

```js
// 典型的自包含 VMP 字节码分发循环
function _vm(bytecode) {
  var stack = [], pc = 0, env = window;
  while (pc < bytecode.length) {
    var op = bytecode[pc++];
    switch (op) {
      case 1: stack.push(env[bytecode[pc++]]); break;    // ← GET 操作：env[key] 直接访问，不经过 apply/Reflect
      case 2: var k = stack.pop(), o = stack.pop(); stack.push(o[k]); break;  // ← 对象属性读取
      case 3: var args = stack.splice(-bytecode[pc++]);
              var fn = stack.pop(); stack.push(fn.apply(null, args)); break;  // ← 这种才被 apply hook 看到
      case 4: stack.push(bytecode[pc++] + stack.pop()); break;                // ← 纯字符串拼接，hook 完全抓不到
      // ... 数十到数百个 case
    }
  }
}
```

- `case 1` 直接访问 `env[key]`，hook `navigator`/`screen` 的 Proxy 能看到（如果 env 是被 Proxy 的全局），但嵌套多层后 Proxy 链会断。
- `case 2` 读任意对象的任意属性——hook 不可能覆盖所有对象。
- `case 4` 的纯字符串拼接不会经过上述 API Hook，可能只能从周边输入输出推断。

**结果**：传统 API Hook 可能只提供零散调用，不足以还原 dispatch 循环中的关键中间值。源码 tap 可以补充受支持位置的证据，仍不等于逐 opcode 追踪。

### 1.2 源码级插桩的原理

**`instrumentation(action="install")`** 在 HTTP 层拦截目标脚本，在支持且被选中的源码位置插入 tap。以下为改写形态示意，不能据此承诺任意脚本的语义等价：

```js
// 改写前
var value = env[key];

// 改写后（regex 模式）
var value = __mcp_tap_get(env, key, 'vmp1');

// 改写前
obj.method(arg);

// 改写后（AST 模式）
__mcp_prepare_method(obj, 'method', 'vmp1')([arg]);
```

运行时将选中位置的事件写入当前 Frame 主世界的 `window.__mcp_vmp_log`。方法调用先读取方法，再求值参数，以保留该顺序与 `this`。主要事件包括：

- **tap_get**: 读取属性——`{type, tag, key, objType, value (preview)}`
- **tap_method**: `obj.method(args)` 调用——`{type, tag, objType, method, argc, arg0, ret}`
- **tap_call**: `fn(args)` 直接调用——`{type, tag, name, argc, arg0, ret}`
- **tap_call_err**: 直接函数调用同步抛错——`{type, tag, name, err}`；不能据此假定所有属性读取、方法抛错或异步拒绝都有错误事件

默认日志只做 primitive preview，长值可能截断；对象为 `[object]`、函数为 `[fn]`，不枚举字段或调用对象的 getter/toJSON。这些占位不是完整 I/O，`objType` 也只是 `typeof`，不能据此识别对象所属的库。需要对象字段时另做明确、受控的采样；精确字符串可用 `evaluate_js(..., world="main", result_format="json_ascii")` 后本地解码，特殊数值等先显式标签化。

源码、堆栈、耗时和新增的 MCP 全局名称仍可被观察。先运行原始产物作为基线，再比较改写后的结果、异常、参数/状态副作用、`this` 和随机源调用次数；不承诺全量覆盖、不可检测或全程序等价。

---

## 2. 两种改写模式：regex vs AST

`instrumentation(action="install", mode=...)` 支持两种模式，均无覆盖率承诺。

### 2.1 `mode="regex"`（无依赖的保守子集）

- **whole-program 白名单**：先检查整个程序是否由受支持的简单读取、字面量/标识符表达式或单个带初始化的变量声明组成，再改写合格的 `identifier[key]`。key 只接受受支持的简单标识符、字符串或整数形式，不是任意表达式。
- **整段原样跳过**：调用、赋值目标、运算符、函数/循环、模板字符串、正则字面量、嵌套方括号等复杂语法不在白名单中；不会在复杂 VMP 中搜出局部片段强改。跳过时不注入 runtime，检查 `last_skip_reason="unsupported_program_syntax"`。
- **只有属性读取 tap**：不生成 `tap_method` / `tap_call`，也不支持 construct（`new` 构造调用）观测。显式 `mode="regex"` 搭配非空 `filter_property_names` 或 `filter_object_names` 会在安装前明确拒绝并建议使用 `mode="ast"`，不会忽略过滤器继续安装。
- **适用范围**：已确认整个输入属于白名单的小型简单脚本。文件大、AST 失败或现代语法出现，都不是改用 regex 的充分理由。

### 2.2 `mode="ast"`（默认，本地解析）

- **解析链路**：MCP 侧先用 esprima-python；其无法解析时，由本地 Node.js 调用随 MCP 打包的 Acorn 处理现代语法。无需页面 CDN，也不执行输入源码。缺少依赖、超过解析资源限制或仍解析失败时查看诊断。
- **改写范围**：在支持的 `MemberExpression` / `CallExpression` 位置插桩；解析成功不等于每个 construct 都支持改写。可选链、`super`、私有成员等有语义边界，可能跳过相关节点；不提供 `new` / `NewExpression` 的 construct 事件，不能把普通调用 tap 当作构造调用记录。
- **选择性改写**：`filter_property_names` 同时约束属性读取与方法调用；`filter_object_names` 匹配静态对象路径，支持 `this.bytecode`，不解析动态对象表达式或推断运行时别名。动态 key 也不能当成已知属性名匹配。
- **有条件回退**：默认 `fallback_on_error=True` 仅在 AST 失败且未设置上述过滤器时尝试 regex；有过滤器时不自动改成无过滤的 regex。尝试回退仍可能原样跳过，不保证产生 tap。可设为 `False` 保留 AST 失败诊断。

历史页面内 Acorn CDN 实现不是当前工具的执行路径；现代解析需要本地 Node.js，不能沿用“零 JS 依赖”的描述。

### 2.3 选择建议

| 情况 | 选 | 原因 |
|------|-----|-----|
| 首次分析某个 VMP | **选择性 AST** | 先按当前源码定位属性，使用 `rewrite_calls=False`（MCP v1.10.0 起是默认值），需要调用证据时再扩大；调用改写会让被调函数读到的 `caller` 变成 null、递归深度下降，指纹可能跟着变 |
| 整个脚本属于 regex 白名单，只需 bracket 读取 | regex | 无解析器依赖，仍需对照验证 |
| 大文件 | **选择性 AST 或保留原文** | 默认 `max_file_size` 在 MCP v1.10.0 起是 2000000 字节（更早是 200000），`on_oversized="selective"` 无过滤器时跳过；被跳过的文件在 `status` 和 `log` 的 `skipped_files` 里列出原因和建议值；不因体积直接换 regex |
| 关心 VMP 调了哪些方法 | **AST** | regex 不生成 tap_method / tap_call |
| 关心 VMP 读了哪些属性 | 通常 AST | 两种模式的语法范围不同，日志只说明实际捕获的读取 |

---

## 改写状态与运行时健康诊断

启用 `instrumentation(action="install", mode="ast")` 后，先通过
`instrumentation(action="status")` 的 `active_patterns[i]` 核对目标 `last_url`、计数和诊断；计数是累计值，`last_*` 描述最近处理状态，不能拿其他脚本的成功代替当前目标：

| `last_mode_used` | 含义 | 动作 |
|---|---|---|
| `"ast"` | 生成 AST 改写文本，或命中该内容的改写缓存 | 查看 `last_parser_backend`，继续做运行时健康检查 |
| `"regex"` | 显式 regex 模式产生了改写文本 | 只代表白名单中的读取被改写 |
| `"regex (fallback)"` | AST 失败后，regex 白名单产生了改写 | 查看 `last_error`，评估有限证据是否满足目标 |
| `"passthrough"` | 原文透传，未产生合格改写 | 查看 `last_skip_reason` 和 `last_error` |

`files_seen` 只是 route 看到了响应；`files_passed_through` 表示透传次数。常见跳过原因包括 `unsupported_program_syntax`、`no_eligible_rewrites`、`oversized_without_selected_properties`、`oversized` 和 `non_success_response`。后者还应核对响应状态；只读 `last_mode_used` 可能看到之前请求的模式。

解析失败先看 `last_error`，核对原始响应确为 JS、esprima/本地 Node/随包 Acorn 是否可用及资源限制。必要时保存已捕获的原始响应核对；不要无证据删除 BOM/前缀或反复重放请求。语法能解析但目标节点不支持时，保留 skip，选择其他可观察位置或运行时方案。

### 改写产物运行时健康检查

`files_rewritten > 0` 和 `last_mode_used="ast"` 只证明 MCP 生成并下发了改写文本，
不能证明浏览器成功解析和执行了它。每次 reload 后继续检查：

```text
instrumentation(action="status")
evaluate_js(expression="(() => ({
  tapInstalled: window.__mcp_tap_installed === true,
  logReady: Array.isArray(window.__mcp_vmp_log)
}))()", world="main")
instrumentation(action="log", tag_filter="vmp1", limit=10)
```

上述示例读取当前页主 Frame。SDK 在 iframe 中时，先用 `get_page_info().frames` 确认目标，在 `evaluate_js` 与 `instrumentation(action="log")` 中指定相同 `frame_url` / `frame_name`；`frame_index` 只适用于当前快照。`log` 自动读所选 Frame 的主世界，不传 `world` 参数。

判定：

- `files_rewritten > 0` 且 `tapInstalled=false`：先核对世界、Frame、目标响应与加载时序，再检查浏览器解析/执行错误；不能仅凭标记缺失断定 AST 损坏。
- `tapInstalled=true` 但日志为空：只证明该 Frame 的 runtime 标记存在，未证明目标 VM 已运行；检查业务完成信号、tag/filter、skip 和容量，不盲目重放业务动作。
- 确认改写改变行为后，停止对应 route，对照原始产物定位影响。仅在输入满足 regex 白名单时才考虑它；完整性校验可能拒绝任何源码变化，轻改写不能保证解决。可选 `hook_jsvmp_interpreter(mode="transparent")` 等运行时观测，但仍需对照验证；`transparent` 不是 instrumentation 的模式。

---

## 3. 按需操作骨架（8 步）

> 以下是按证据选取的操作骨架；站点名称仅为历史线索。首次检查与续做复用遵循 [任务级检查](task-preflight.md)，无需为每个步骤重做环境或案例审查。根据当前源码、Frame 和业务状态调整参数与探针。

### Step 1 — 启动 + 网络捕获

```
Actions:
  # 新浏览器分析任务先 check_environment()；同任务已有环境则复用
  launch_browser(headless=False)   # 需要新建本任务浏览器时执行
  network_capture(action='start', capture_body=True)   # 抓响应头和正文，Cookie 归因需要
```

### Step 2 — 第一次导航定位 VMP 脚本 URL

```
Actions:
  navigate(url="https://target.com/", wait_until="load")
  list_network_requests(resource_type="script")
  → 结合请求发起栈、文件名与源码定位候选；体积大不等于 VMP
  → 记下 url，下面称为 <VMP_URL>
```

### Step 3 — 核对 VM 结构

```
Actions:
  search_code(keyword="switch", script_url="<VMP_URL>", context_chars=500)
  → 结合真实字节码来源、PC 更新、寄存器/堆栈变化和 dispatch 执行证据确认 VM
  → case 数量与 while-switch 只是线索，控制流平坦化也可能有类似结构
  → 记下当前源码位置与所需观测属性（后续选择性插桩）
```

### Step 4 — 装源码级插桩（核心）

```
Actions:
  instrumentation(
    action="install",
    url_pattern="**/<VMP文件>-*.js",   # glob 模式，匹配所有 CDN hash 变种
    mode="ast",                         # 本地解析，不依赖页面联网
    tag="vmp1",                         # 一次插桩多 VMP 时区分
    rewrite_member_access=True,
    rewrite_calls=False,                # 先看所选读取，需要方法事件时再打开
    filter_object_names=["this.bytecode"],  # 示例：替换为当前源码中的静态对象路径
    max_rewrites=5000
  )
  → 返回：{"status": "instrumenting", "pattern": "...", "mode": "ast", "tag": "vmp1"}
```

### Step 5 — 按需增加互补 Hook

只安装当前需要且经过原始/观测对照的探针；源码插桩与运行时 Hook 都可能影响行为，不按域名假定可用。

```
Actions:
  # 仅示意需要 XHR 出口证据时的选择；已有所需证据则跳过
  inject_hook_preset(preset="xhr", persistent=True)
```

### Step 6 — 重载以应用已注册的 route / 持久 Hook

```
Actions:
  instrumentation(action="reload", clear_log=True, wait_until="load")
  → 检查 final_status / redirect_chain、业务完成信号和运行时健康状态
  → HTTP 200 仍需业务验证；403/412 不能单独确定厂商或失败原因

特殊场景：若目标就是首屏挑战页，用：
  navigate(
    url="https://target.com/",
    pre_inject_hooks=["xhr", "fetch", "cookie_hook"],  # 只放本次已选择的探针
    wait_until="networkidle"
  )
```

### Step 7 — 触发业务操作

```
Actions:
  click(selector=".some-btn")
  # 或
  type_text(selector="#search", text="test")
  click(selector=".submit")
  # 或
  evaluate_js(expression="document.querySelector('.nextPage').click()")

  → 用业务信号或新请求记录确认签名/请求实际发生，点击返回不代表异步任务已完成
```

### Step 8 — 读日志，分析 hot_keys / hot_methods / hot_functions

以下摘要仅示意返回格式，不是本轮测试结果，也不是 Step 4 过滤配置必然产生的内容。只选 `this.bytecode` 不会自动得到宿主环境属性分布。

```
Actions (hot_keys — VMP 读取了哪些属性):
  instrumentation(
    action="log",
    tag_filter="vmp1",
    type_filter="tap_get",
    limit=200
  )
  → summary.hot_keys:
    {
      "userAgent": 120,
      "plugins": 98,
      "webdriver": 77,
      "platform": 65,
      "language": 54,
      "cookie": 43,
      ...
    }
  → 实际结果只表示所选位置捕获的读取分布；不能当作参与签名哈希的完整环境指纹集

Actions (hot_methods — VMP 调用了哪些方法):
  instrumentation(
    action="log",
    tag_filter="vmp1",
    type_filter="tap_method",
    limit=200
  )
  → summary.hot_methods:
    {
      "function.defineProperty": 45,
      "object.join": 38,
      "string.charCodeAt": 30,
      "object.MD5": 12,
      ...
    }
  → ObjectType 为 typeof；需结合源码和 I/O 确认是否为标准加密调用

Actions (hot_functions — VMP 调用了哪些函数):
  instrumentation(
    action="log",
    tag_filter="vmp1",
    type_filter="tap_call",
    limit=200
  )
  → summary.hot_functions:
    {
      "_0xabc": 300,
      "_0xdef": 150,
      "encodeURIComponent": 8,
      "parseInt": 6,
      ...
    }
```

Step 4 的读取配置不会产生方法/函数事件。确需这两类证据时，停止对应 route，按当前源码调整过滤器并打开 `rewrite_calls=True`，再有意采样。不要为了获得所有摘要直接扩大到全文件。

SDK 在跨域 iframe 中时，上述 `log` 调用都需加相同的 Frame 选择器，例如 `frame_name="sdk"`（替换为实测名称）。MCP v1.10.0 起同源子 frame 里的事件写进顶层日志，带 `frame_url`、`frame_depth`，页面删掉 iframe 后也还在，不用再选 Frame。查看返回的 `world`、`frame`、`execution_backend` 和 `warning`。`possibly_capped=True` 表示所选 Frame 的原始缓冲区可能达到 20,000 条上限；`truncated=True` 只表示过滤后记录超过本次 `limit`，摘要统计的是过滤后的已保存记录。增大 `limit` 不能补回未采集事件，缺失事件不能作否定证据。MCP v1.10.0 起每条事件都带 `seq`，`dropped` 给出满 20000 条后丢掉的条数；要取一段时用 `after_seq` 往后翻页（返回 `next_after_seq`）或 `seq_window=[起, 止]`，不要拉全量再本地筛。

---

## 4. 进阶技巧

### 4.1 多 VMP 场景（一次分析两个脚本）

```
instrumentation(action="install", url_pattern="**/sdk-a.js", mode="ast", tag="sdk-a",
                rewrite_calls=False, filter_property_names=["userAgent"])
instrumentation(action="install", url_pattern="**/sdk-b.js", mode="ast", tag="sdk-b",
                rewrite_calls=False, filter_property_names=["userAgent"])

# 分别看
instrumentation(action="log", tag_filter="sdk-a", type_filter="tap_get")
instrumentation(action="log", tag_filter="sdk-b", type_filter="tap_get")
```

### 4.2 key_filter 锁定某个具体属性

```
# 按属性名过滤；仍需源码确认对象是 navigator
instrumentation(action="log", tag_filter="vmp1", type_filter="tap_get", key_filter="webdriver")

# 按方法名过滤；MD5 名称本身不能证明来自 CryptoJS
instrumentation(action="log", tag_filter="vmp1", type_filter="tap_method", key_filter="MD5")
```

`key_filter` 是读取日志时对子串的匹配，覆盖 `key` / `method` / `name`，不会减少插桩或采集开销。安装阶段用 AST 的 `filter_property_names` 限制读取与方法调用，用 `filter_object_names` 选择 `this.bytecode` 等静态路径；两类过滤同时设置时目标需同时满足。过滤器不是对 preview 对象的运行时查询。

### 4.3 管理插桩 route

```
# 查看所有激活的 route
instrumentation(action="status")

# 停止单个
instrumentation(action="stop", url_pattern="**/<VMP文件>-*.js")

# 全部停止
instrumentation(action="stop")  # 仅在全部 route 都属于本任务且需清理时
```

`stop` 移除 route，不还原当前文档中已执行的改写代码或卸载其他 Hook。恢复基线时保存证据，再按任务状态决定重载或创建新的自有上下文；其他 Hook 的卸载限制见当前 SKILL.md。

### 4.4 与 runtime_probe 互补

runtime_probe 不改写源码，通过 JS 包装热点 API；它不是 Gecko 原生 trace，也不能保证低开销或不可检测。两者按需配合：

- VMP 内部被选中的 `obj[key]` 读取 → `instrumentation(action="log")`
- VMP 最终落到 `XMLHttpRequest.open` / `canvas.toDataURL` / `navigator.userAgent` 的 getter 调用 → 运行时探针日志 `window.__mcp_runtime_log`

```
inject_hook_preset(preset="runtime_probe", persistent=True)
instrumentation(action="install", url_pattern="**/<VMP文件>-*.js", mode="ast", tag="vmp1",
                rewrite_calls=False, filter_property_names=["userAgent"])
instrumentation(action="reload")
触发操作
# 两路都读
instrumentation(action="log", tag_filter="vmp1", limit=300)
evaluate_js(expression="window.__mcp_runtime_log || []", world="main")  # 本地按 type 过滤
```

### 4.5 平坦化分发的阶段对照

控制流平坦化的 VM 常把每个状态都交给同一个分发调用，例如 `return l.apply(this, [3].concat(Array.prototype.slice.call(arguments)))`，`3` 是状态号。本地补环境算出的值和浏览器不同、读到的属性又对不出差别时，可以把两边的状态序列逐条比对，第一个不同的状态就是分叉点。需要 MCP v1.9.4 起的 `tap_stage_calls`。

```
instrumentation(action="install", url_pattern="**/<VMP文件>-*.js", mode="ast", tag="stage",
                tap_stage_calls=True, rewrite_member_access=False, rewrite_calls=False)
instrumentation(action="reload")
instrumentation(action="status")   # total_edits 是改写的分发调用数
触发一次业务操作，记下这次的输入（种子、时间戳等）
instrumentation(action="log", tag_filter="stage", type_filter="tap_stage", limit=5000)
→ entries 依次带状态号 p、argc、前三个参数和返回值的预览；summary.hot_stages 是各状态的次数
instrumentation(action="log", tag_filter="stage", type_filter="tap_stage", key_filter="3")  # 按状态号筛，子串匹配
```

- `total_edits` 为 0 说明文件里没有这种写法，回到源码确认分发形态。`last_mode_used` 显示 `ast (stage taps only)` 说明文件没解析成功，只做了阶段插桩，原因在 `last_error`。
- 只匹配上面这一种写法，其他写法原样保留。`mode="regex"` 和解析失败的文件没有语法树核对，字符串里同样的文字也会被改写，优先用 `mode="ast"`。
- 事件在状态返回时记录，嵌套的状态排在前面；抛出异常的状态不记录。两边按同样的规则记录，再按顺序比状态号和返回值。
- 时间戳、随机数这类输入两边要固定成同一份，否则序列从头就不同。找到分叉的状态后，再用 `tap_get` 或补丁日志看这个状态读了什么。

本地侧可以在加载 SDK 源码前做同样的替换，按同样的规则记录：

```js
const STAGE = /return\s+([A-Za-z_$][\w$]*)\.apply\(\s*this\s*,\s*\[\s*(\d+)\s*\]\s*\.concat\(\s*Array\.prototype\.slice\.call\(\s*arguments\s*\)\s*\)\s*\)/g;
const preview = v => v === null ? 'null' : typeof v === 'object' ? '[object]'
  : typeof v === 'function' ? '[fn]' : (s => s.length > 120 ? s.slice(0, 120) + '...' : s)(String(v));
const stages = [];
globalThis.__stage = function (p, fn, self, args) {
  const r = Reflect.apply(fn, self, [p].concat(Array.prototype.slice.call(args)));
  stages.push([p, args.length, preview(r)]);  // 与浏览器日志的 [p, argc, ret] 逐条比对
  return r;
};
source = source.replace(STAGE, 'return __stage($2, $1, this, arguments)');
```

MCP v1.10.0 起可以直接让 MCP 生成本地插桩文件，不用手写替换：`instrumentation(action="rewrite_source", source_path="sdk.js", output_path="sdk.tapped.js", tap_stage_calls=True, rewrite_member_access=False)`。生成的文件在 Node、vm 和 jsdom 里都能运行，事件在 `globalThis.__mcp_vmp_log`，格式和浏览器日志相同，断网或被封 IP 时也能反复跑。

序列很长时按段比：`instrumentation(action="log", seq_window=[590, 610])` 取一段；在状态里发生的读取带 `stage`（最内层状态号），`instrumentation(action="log", stage=<p>)` 取某个状态里的事件；`stage_break(action="set", p=<p>)` 再 `reload`，能记下这个状态完整参数、返回值和调用栈的有界快照（页面加载时执行的状态也能记到）。

---

## 5. 常见问题与陷阱

### Q1：`files_rewritten=0`，没改写到

**可能原因**：

1. `url_pattern` 没命中——确认 VMP 实际 URL（`list_network_requests` 里看），glob 模式要用 `**/` 前缀才能匹配任意路径
2. 脚本已在安装前加载——确认加载时序，需要重新采样时用 `instrumentation(action="reload")`，不先清全部缓存
3. route 命中但原文透传——查看 `files_seen`、`files_passed_through`、`last_skip_reason` 与 `last_error`，区分体积门槛、语法/过滤范围和非成功响应；MCP v1.10.0 起 `skipped_files` 逐个列出被放行的文件、大小、原因和建议的 `max_file_size`，`capped_files` 列出改写处数到 `max_rewrites` 上限的文件

### Q2：AST 模式报 `parse_error`

**可能原因**：原始响应不是有效 JS、解析依赖缺失、现代解析资源限制，或两种解析器均不支持该语法。

**对策**：

- 核对 `last_error` / `last_parser_backend` 及本地 esprima、Node.js、随包 Acorn；保存原始响应检查内容和来源
- 仅在整个输入符合 regex 白名单时考虑回退；复杂源码被跳过是明确的能力边界，不强制换模式或直接修补原文

### Q3：改写后页面崩溃

**可能原因**：

1. 世界/Frame 或加载状态不对——先按健康检查核对，再看浏览器解析/执行错误与原始基线
2. VMP 自己对源码做完整性校验——任何源码改动都可能触发，不能承诺 regex 或更少改写解决；停止对应 route，评估无需改源码的观测路径
3. MCP 全局名称冲突或内建函数已被业务修改——检查运行时安装时序；`tag` 只是日志分组，换 tag 不会改 runtime 全局名称
4. 改写开销或语义变化——缩小 AST 过滤范围、关闭不需要的调用改写并做对照；不要持续增加 `max_rewrites` 重试同一失败产物

### Q4：hot_keys 没出现预期的环境指纹

**可能原因**：

1. VMP 尚未触发——查看业务完成信号/请求记录，不把 networkidle 当作签名已完成
2. 改写位置被跳过、过滤或尚未执行——核对目标响应、status 与主世界 runtime 标记
3. Frame、tag/filter 不匹配，或日志达到容量——检查所选 Frame、`possibly_capped` 和 `dropped`；空结果不证明没有读取

### Q5：日志爆炸到上限 20000 条

**对策**：

- 先保存需要的证据；`instrumentation(action="log", ..., clear=True)` 清空所选 Frame 的整个源码日志缓冲区，包括不匹配本次过滤器的记录，不卸载探针
- 收紧 `url_pattern` 和 AST 安装过滤器，关闭不需要的 `rewrite_calls`，按业务窗口有意采样
- `limit=300` 可减少返回量，但不减少采集开销；保留 `possibly_capped` / `truncated`，不能宣称日志完整

---

## 6. 源码级插桩的还原决策

摘要只覆盖所选位置与已保存的事件，下表的数量是历史启发，不是固定判据。`hot_methods` 的 `typeof.method` 不能直接标识 CryptoJS 等库；先结合源码、I/O 和当前业务对照验证，再选择策略：

| 结合源码/I/O 确认的调用特征 | hot_keys 环境属性数 | cookie 来源（Cookie 归因） | 候选策略 |
|-----------------|---------------------|--------------------------------------|------|
| 已证实使用 CryptoJS.MD5 / SubtleCrypto.digest / HMAC | 少（< 10） | 全部 js_document_cookie | 核对输入与拼接后尝试纯算法还原（crypto/hashlib） |
| 已证实使用 CryptoJS，且输入依赖环境 | 中（10-30） | 混合或 js_document_cookie | 提取 JS 签名函数 + vm/execjs 沙箱并验证 |
| 自定义函数与 SDK 执行强绑定，难以隔离 | 多（30+） | 任意 | 评估路径 B：jsdom 环境复现（见 `jsdom-env-patches.md`） |
| 自定义函数且有服务端初始化链路 | 中-多 | 主要 http_set_cookie | 先确认协议初始化；需要环境复现时再选路径 B |

---

## 7. 参考

- [jsvmp-analysis.md](jsvmp-analysis.md)：历史分析线索，按当前工具 schema 核对
- [jsdom-env-patches.md](jsdom-env-patches.md)：环境复现补丁库（路径 B）
- [骨架案例](../cases/universal-vmp-source-instrumentation.md)：模板，需当前适用性验证
- [真实上游本地案例](../references/real-source-cases.md)：VM/CFF/CryptoJS/FingerprintJS 的来源与证据边界
- [准备与验证脚本说明](../scripts/real_cases/README.md)：按需执行，本地通过不等于商业站点验证
- [MCP 上游](https://github.com/WhiteNightShadow/camoufox-reverse-mcp)（本指南对齐 v1.8.0，4.5 节对齐 v1.9.4，日志切片和离线改写对齐 v1.10.0）
