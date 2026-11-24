# 原始 SDK 运行：入口、运行时、状态回放与生命周期

适用于路线 R3、R4：不读懂内部算法，让原始 SDK 在本地运行并取得值。这条路线的风险是把“能跑出值”当成“能用”，所以全程区分 S1 和 S2。

## 定位入口

1. 枚举页面资源和 `document.scripts`，围绕请求头名、版本字符串、协议标记定位候选脚本。
2. 模块化打包的页面，借打包器运行时取模块导出，再核对函数身份。两个导出可能是同一函数，也可能一层只是包装，外层包装模块不等于实体模块。
3. 记录入参形状：URL 是否完整、Body 是字符串还是空、`this` 和上下文是否参与。
4. 页面真实路径和公开入口可能不同。多个入口都能调用时，固定输入比较中间值或输出，相同就不用换。换入口前先有这个证据，否则只是在改变量。
5. SDK 加载后枚举一次可达全局上的非内建符号，记名字和参数个数，什么都没有也记一次。这一步成本很低。

## 声明原始输入

“固定输入逐字一致”要先说清什么算输入，否则等价结论可能是伪造的。

- 列出实现允许接收的原始输入：请求、环境、时间、随机源、配置、初始状态。
- 派生值只能作调试断言，不能作实现入参。把 VM 算好的中间值喂给实现再比对，通过了也不算还原。
- 可变序列同时记录值和消费顺序。只固定种子不代表随机流一致，调用次数不同也会改变结果。
- 固定一个可变源后输出仍变，说明还有状态没受控，不说明算法不可还原。

## 选运行时

| 运行时 | 优点 | 不足 | 适合 |
|---|---|---|---|
| Node vm + 手补环境 | 轻，无额外依赖 | 全靠手补，原型与原生性差距大 | 依赖少的片段 |
| jsdom | DOM 较完整 | `toString`、原型、布局与真实浏览器不同 | 中等环境依赖 |
| 针对某类 SDK 的定制运行时 | 对该体系省事 | 只适用于对应体系，要核对版本 | 已确认是同一体系 |
| 浏览器级运行时 | 真实 JS 引擎和原生 API，语义最接近 | 仍要输入状态，体积与授权要评估 | 原型、指纹敏感的 SDK |

选型看 SDK 实际读什么，而不是看哪个最强。运行时的 JS 引擎与基线浏览器同源时差异更少，这是推断，以实测为准。

公开例子：[ruyiJS](https://pypi.org/project/ruyijs/)（SpiderMonkey 加原生浏览器 API 的 Python 运行时，AGPL-3.0-only 或商业授权，修改后以网络服务提供时要公开源码）、[iv8](https://github.com/HanZzzzz000/iv8)（V8 内核，闭源预编译，限个人、教育和非商业）。这些只作外部可选依赖，它们宣称的通过情况都未经本 Skill 验证，引入前确认许可证是否符合项目。

## 加载方式

- 用原始 URL 加载，内容由本地资源提供，不用 `eval` 字符串。`eval` 不产生 script 节点和资源条目，栈来源也不同。
- 校验 SDK 文件 SHA-256，版本或哈希不符就不加载。
- 模块和参数留在闭包里，不挂到全局，避免留下可被枚举的辅助变量。

## 状态输入

只补有读值证据的项。下表是常见项和要保留的语义，不是清单式必做项：

| 状态 | 要保留的语义 | 常见缺口 |
|---|---|---|
| Cookie | Domain、hostOnly、Path、Secure、SameSite、HttpOnly、到期时间 | 字符串导入丢属性，用 `document.cookie` 取不到 HttpOnly |
| Storage | 具名读写、枚举、`getItem`/`key`/`length` 一致，两层都要 | `Object.keys` 为空、赋值落成普通属性 |
| 几何与焦点 | outer/inner、窗口位置、visualViewport、`hasFocus` | 用默认值代替快照 |
| DOM 命中 | `elementFromPoint` 等 | 空文档返回 null |
| performance | navigation、resource、mark、measure、paint 条目与 detail | 只有 navigation 一条 |
| 页面身份 | 来源页 URL、title、referrer | 换成目标 URL，而快照来自别的页 |

- 快照、请求模板、Cookie 成套新鲜，来自同一页面同一时刻。
- 缺项就停止，不用空数组或默认值代替，否则会得到一个看似完整、实际已被改变的环境。
- 穿过控制接口的快照用 JSON 字符串传递，再本地解析。深层对象可能被截断成 null。
- 回放层本身可能被观察到（如 Proxy），不要写成“与真实浏览器等价”。

## 生命周期：先 seed，后 init

SDK 常在首次读取后缓存。外部在初始化之后再刷新状态，可能完全不生效。

- 顺序：新建上下文 → 完整 seed → 加载 SDK → 初始化 → 出值。
- **哨兵实验**：首次出值后，从外部改动某个 Cookie 或 Storage 项，再出一次值。输出或中间值不变，说明是实例内缓存；新建实例才变，说明要按实例重新 seed。
- 实例粒度由哨兵结果决定：有一次性状态就每次新建，没有才复用。
- 出值前后各核对一次状态（Cookie 数、Storage 项数、性能条目数），记录 SDK 自身写入。
- 真实长驻页面的私有缓存可能取不到。Cookie 相同不等于缓存相同，这一点写进限制。

## 读值差异

不要 diff 全部环境。要回答的是 SDK 实际读了什么，以及读到的值和基线差在哪：

| 实际读取 | 本地值 | 基线值 | 证据等级 |
|---|---|---|---|
| 某属性或方法 | … | … | 观察差异 / SDK 实读 / 服务端校验 |

- **观察差异**：两边不同，但不确定 SDK 读不读。
- **SDK 实读**：Trace 确认读取并影响了路径。
- **服务端校验**：只有换这一项能让结果翻转时才算，通常到不了这一级，也不必到。

一个 API 在运行时里有三种状态，处理方式不同：

| 状态 | 表现 | 处理 |
|---|---|---|
| 真实实现 | 行为正确 | 不动 |
| 空壳 | `typeof` 和原生表面都对，一用才错，缺失日志抓不到 | 靠运行时报错栈定位，替换成真实行为 |
| 正确缺失 | 真实浏览器也没有 | 保持未定义 |

判读时注意：

- 读到 undefined 不是缺口。SDK 常探测自动化和沙箱标记，真实浏览器也是 undefined，这些保持未定义才对。只记“真实有值而本地没有”的项。
- 差异可能随时钟变化。隔几分钟重采一侧再比，差异跟着时间走就不是环境问题。
- 取值和判定是两回事，SDK 采集到不代表同步判定，上报也可能异步生效。
- 代码里出现字段名不代表当前走了那条路径。
- 观察器本身会改变函数表面，计数相近不能证明无干扰。扩大观察后变慢或超时，不能推断目标有反 Hook 检测。
- 读取次数的绝对值不能跨环境相减来推断“新增了多少检查”，除非两边环境相同只换了 SDK。

## 沙箱原生性、子 Realm 与探针开销边界

当选定 jsdom / Node vm 运行原始 SDK，且常规 `navigator`、窗口几何对齐后产物仍被拒时，重点排查以下跨体系常见的引擎自证与测量干扰（代码模板见 [jsdom 环境补丁](jsdom-env-patches.md)）：

1. **实例自有属性与原型链归属形状**：SDK 常读取 `Object.getOwnPropertyNames(document).length`、`Object.keys(document).length` 或枚举全局构造器（`window[name] !== undefined`）。常见根因是手写补丁误将 `Document.prototype` 属性定义到了 `doc` 实例上，或盲目批量注入空壳构造器（既可能与基线 UA 内核矛盾，又会诱导 SDK 进入原本跳过的深层实例校验分支）。应通过 `evaluate_js(..., world="main")` 采集真实页面的自有/原型描述符快照（注：`compare_env(output_path=...)` 仅覆盖 `navigator`/`screen` 原型 getter、`window.globals` 与 `CSSStyleDeclaration` 原型名，不含 `document` 描述符表），把原型属性挂回对应原型并保持真实缺失项为 `undefined`。
2. **同源 `iframe` 子 Realm 的独立内建对象与原型链**：每个 `iframe.contentWindow` 都有独立的 `Function.prototype`，且 jsdom 中 `childWin.constructor`（`Window`）与子窗口 WebIDL 方法默认挂在 Node 外层 `Function.prototype` 上。仅覆写顶层 `window.Function.prototype.toString` 拦不住 `String(iframe.contentWindow.constructor)` 或经 `contentDocument.defaultView` 访问的子窗口，需在 `HTMLIFrameElement.prototype` 的 `contentWindow` / `contentDocument` 访问入口将 `childWin.EventTarget` 归位到子 Realm 并递归标记原型链。
3. **特殊宿主对象语义（如 `document.all`）**：普通对象和顶层 `Proxy` 无法同时满足 `typeof document.all === 'undefined'` 与活性集合访问；探针还常执行 `delete document.all[i]` 后复读以校验有效索引不可删除。在确认 SDK 实读该对象时，可在受控本地 Node 进程配合 `--allow-natives-syntax` 的 `%GetUndetectable()` 与 `Document.prototype.all` 实现（避免挂在 `document` 实例上增加自有属性），并记录该启动参数依赖。
4. **忙等时钟、高频探针自伤与渲染摘要**：若 SDK 含依赖 `Date.now()` / `performance.now()` 推进的校验循环，将时间冻成常数会导致执行步数激增或落入异常分支，应改用「固定初值 + 单步微小递增」；同理，在 JSVMP 热寄存器或高频分发循环上每拍都调用外部 JS 回调会因时钟推进、对象分配或 `RegExp` 静态属性变化直接令产物变形，应改用内联整数计数器 + 步数窗口门控。Canvas / WebGL 像素输出受系统字体与图形栈影响，不做纯算式拟合，直接从同一基线浏览器采集真值固化。
5. **跨内核 `Error.stack` 文本格式与抗指纹基线等价性**：在 Node `vm` / `jsdom`（V8）中配合 Firefox / Safari UA 运行 SDK 时，V8 默认的 `"Error\n    at ..."` 栈格式会让按 `fn@url:line:col` 编写的内部正则返回 `null` 并抛 `TypeError`，常被 SDK 外层 `try/catch` 静默捕获转写为异常遥测槽位——加载脚本时需通过 `vm.Script(..., { filename: scriptUrl })` 绑定真实脚本 URL，并用非枚举 `Error.prepareStackTrace` 对齐目标引擎栈文本。同时，若基线浏览器开启隐私或抗指纹保护（例如画布读回本身即为全零像素或固定受控摘要），本地轻量存根若已与基线实测输出一致，切勿盲目替换为第三方原生渲染库反而制造新差异。
6. **子资源挂载条件与跨内核 UA 分支静默变形**：若 SDK 依赖动态插入 `<script>` 或子资源完成请求拦截器挂载，默认关闭子资源加载（或 `runScripts: 'outside-only'`）的 `JSDOM` 会出现「导出函数存在但拦截器从未触发」，需配置 `runScripts: 'dangerously'` 并接入只放行本地归档资源的受控 `ResourceLoader`（避免直接使用无过滤的 `resources: 'usable'` 发起真实外网请求破坏网络隔离）。此外，切换 Chromium 与 Firefox UA 分支可能同时改变 SDK 内部的流式密钥派生分支与响应解码函数的返回类型（如一侧返回明文 JSON 字符串、另一侧返回序列化的字节对象而不报错），本地运行时须严格锁定抓包基线的同一 UA 内核族。
7. **空种子退化短令牌断言、覆盖式全局槽的多写捕获与避免泛化 `window` `Proxy` 桩**：部分 JSVMP 签名入口在设备指纹存储项（如 `localStorage` 持久设备串）为空或格式不符时**不会抛异常**，而是静默返回仅带版本前缀加单字符的极短退化值（如 9 字符兜底串），服务端必拒；因此 S1 离线检查必须校验输出长度区间与解码结构，不能只看返回非空字符串。当页面按序加载多个动态模块并复用同一全局属性（如 `window.__slot`）传递或暂存字节码容器时，事后读取只能拿到最后加载模块覆盖后的终值，须在**独立观察会话**于加载前用 `Object.defineProperty` 安装 `setter`（保留原有值与可枚举性，并对 `Uint8Array`/`ArrayBuffer` 在写入瞬间拷贝快照以防解释器原地解密或清零）。此外，按 ECMAScript 规范 `Proxy` 不存在独立的“属性调用”陷阱（`get` 无法区分 `window.fn()` 与 `typeof window.x` / 真值判断 / `instanceof`，且单拦 `get` 会造成 `!(k in window) && typeof window[k] === 'function'` 的自相矛盾，同拦 `has` 又会把一切缺失全局项变成存在，在共享成员解引用辅助函数的 JSVMP 中尤为致命），因此切勿给 `window` 套顶层 `Proxy` 充当万能空函数桩，只按实测证据精确挂载具名宿主回调；若极简 `JSDOM('<html></html>')` 抛出未捕获的 `Node.prototype.removeChild(undefined)` 等 WebIDL 参数类型异常（真实浏览器对 `undefined` 同样抛 `TypeError`），先补齐基础文档节点骨架（`<head>`/`<body>`/占位 `<script>`）排查上游节点查找为何为空，仅在确认目标不做负向 WebIDL 抛错断言与原生 `toString` 校验时才对具体 DOM 方法加保留正常 `Node` 行为的异常兜底。

## 隔离与预检

- 出值阶段隔离网络：拒绝意外的远程请求，确认只有本地资源命中，否则 SDK 上报可能污染服务端状态。
- 发送前检查 SDK 版本、哈希、协议标记、会话余量。
- 出值后做 S1 检查：校验位、长度范围、时间字段与当前时间的偏差。

## 交付时声明

```text
运行时及版本 / SDK 文件与哈希 / 入口
外部输入：谁提供 Cookie、快照、模板，多久失效
未复原的状态：例如长驻页面缓存、完整 DOM、用户后续操作
到达层级：S? 及对应批次
```

一个端验收的环境最小集不能套到另一个端。不同接口、不同 SDK 需要的状态可以完全不同。
