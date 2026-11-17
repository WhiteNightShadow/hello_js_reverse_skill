# 招聘平台 `__zp_stoken__`：security-js JSVMP + jsdom 原生性补环境

> 难度：★★★★★
> 还原方案：E: jsdom 环境模拟（原生性探针补齐 + 载荷反解逐字段对照）
> 实现语言：Python（协议/编排）+ Node.js（jsdom 内执行 SDK）
> 最后验证日期：2026-11-17

---

## 技术指纹（供 Phase 0.5 自动匹配）

### JS 特征
- [x] 切片脚本路径形如 `/web/passport/zp/security-js/<sdkName>.js`，由 `security.html` 在挑战时动态加载，文件名每次发版都变
- [x] 单行混淆，30 万字节量级；以 `!function(){try{function b(p){if(p)l[0]=l[16]=…` 这类形态开头
- [x] 扁平化分发器用**位打包状态号**：`var Wbl=31&p,jbl=31&p>>5,Ubl=31&p>>10;`，三层 `switch` 嵌套；源码里搜不到 `case <状态号>`
- [x] 状态分发 thunk 形态：`l.apply(this,[<stateId>].concat(Array.prototype.slice.call(arguments)))`（本例约 170 处）
- [x] 文件内存在**两个**扁平化分发循环（主 VM 用 5/5/5 拆位，IIFE 层另有一个用 2bit×4 拆位），末尾那个 `catch` 属于后者
- [x] 内嵌一份 `js-md5` 并挂到 `window.md5`（赋值形态 `S.md5=m`），用于 canvas 指纹

### 参数特征
- [x] Cookie 名 `__zp_stoken__`，值 = 固定短前缀 + Base64，长度落在 **440~475** 区间，随环境浮动
- [x] 长度由载荷里 ASCII / 非 ASCII 码点数量决定：`len = 前缀长 + 4*ceil((码点总数 + 非ASCII数)/3)`
- [x] 提交接口 `POST /wapi/zppassport/set/zpToken`，**空 body**，Referer 需带 `?_security_check=1_<毫秒时间戳>`

### 请求特征
- [x] 业务接口（如 `POST /wapi/zpgeek/search/joblist.json`）在未放行时返回 `code 37` + `zpData{name, seed, ts}`
- [x] 铸出 token 后必须先 `set/zpToken` 拿到 `code 0`，再重放业务接口才返回数据
- [x] `code 38` = 环境自证不通过（给了 seed 但业务接口仍拒绝）；`code 35` = 出口 IP 风控（**连 seed 都不返回**）

### 反调试特征
- [x] 存在依赖时间推进的忙等循环：把 `Date.now` / `performance.now` 冻死会让执行步数从十几万爆到百万级且不稳定
- [x] 自证方式是**原生性/活性探针**而非 debugger 陷阱：`typeof document.all`、`Object.getOwnPropertyNames(document).length`、`Object.keys(document).length`、`String(iframe.contentWindow.constructor)` 都会进载荷
- [x] 会逐个探测一批全局构造器是否存在（`window[name] !== undefined`）来决定分支，虚假补齐会被识破

### 混淆类型
- [x] JSVMP（扁平化 + 位打包状态 + 运行期字符串池拼接）

### 指纹检测规则（Agent 执行）

```
快速检测命令（30秒内完成）：
  - list_scripts(filter="security-js") → 命中 200KB+ 单行脚本 → 高置信度
  - search_in_sources("31&p") → 命中 `var Wbl=31&p,jbl=31&p>>5,Ubl=31&p>>10` → 直接定位本案例
  - search_in_sources("apply(this,[") → 大量 `l.apply(this,[数字].concat(...))` → 确认位打包分发
  - list_network_requests(urlFilter="joblist") → 响应 code 37 且带 seed → 挑战态
  - list_network_requests(urlFilter="set/zpToken") → 存在该请求 → 确认挑战流程
  匹配判定：security-js 脚本 + `31&p` 拆位 + code 37/38 → 本案例高置信度
```

---

## 加密方案

- **算法**：收集环境 → 组装一段**定长码点载荷** → UTF-8 编码 → Base64 → 拼固定前缀
- **载荷形状（本例实测，可用于自查）**：
  - 载荷是 241 个码点，前 3 个是常量头，其后 238 个是**记录流**，槽号 = 下标 − 3
  - 记录流不是明文：每个槽都经过一层**位置相关变换**（按 `下标 mod k` 查一张小常量表，再做加减与按位异或），
    常量表与偏移随版本变，**必须现场反解**，不要照抄别处的数值
  - 记录流里有一段是 `md5(canvas.toDataURL())` 的十六进制字符，逐字符映射进相邻槽
- **反解思路**：`编码` 与 `解码` 都是逐码点独立运算 ⇒ 拿到任意一条真实 token 就能还原出记录流，
  再拿本地铸的 token 还原一次，**逐槽比较**。这比对比最终字符串可靠得多。
- **单/双字节分支**：载荷落进 UTF-8 编码循环时，每个码点按 `码点 < 0x80` 走单字节、否则走双字节，
  分支本身由一个布尔状态寄存器决定（形如 `p = flag ? A : B`）——**这也是判断载荷差异的最灵敏指标**：
  两侧 ASCII 计数不同，token 长度就一定不同。
- **服务端判据**：整份载荷参与校验，改任何字段（哪怕只差 1 个数值）都会退回 `code 38`，
  不是简单的"签名 + 时间戳"。

---

## 已验证定位路径（Phase 0.5 命中后直接执行）

```
步骤 1: 拿厂商字节并核身份（最容易翻车的一步）
  list_scripts(filter="security-js") 拿到 URL → 页面内 fetch → 记录 len 与 sha256 并归档。
  ⚠ 取之前必须 instrumentation(action="status") 确认没有活动改写路由：
    开着改写时取回的是被改写过的脚本（体积、载荷都会变），会被误判成"服务端下发了第二个版本"。

步骤 2: 走一遍挑战流程，拿真实 token 作基准
  navigate(业务页) → list_network_requests(urlFilter="joblist") 看到 code 37 + seed
  在页面里 eval 同一份 SDK，调用 SDK 的构造函数铸一次 token
  ⚠ 一次页面加载只铸一次：连铸会往 window 上加键，改变 Object.keys(window) 条数 ⇒ 载荷漂移

步骤 3: 本地铸一次同 seed/ts 的 token
  jsdom + 同一份 SDK 字节；时间 / Math.random / WebCrypto 用同一份确定性注入，且在 SDK eval 之前注入

步骤 4: 反解成记录流，逐槽比较
  两侧都按加密方案里的变换还原出 238 槽 → 逐槽 diff → 得到"本地 vs 浏览器"的差异清单

步骤 5: 先分类，再归因
  同一侧多次「重载页面 → 只铸一次」采样，把槽分成「稳定」与「本侧自己会变」两类；
  只对「稳定且两侧不同」的槽做单点消融（一次只改一个环境量，要求只动目标槽）

步骤 6: 按槽语义逐个修（本例的顺序就是收敛最快的顺序）
  文档形状（自有属性数/可枚举数） → iframe 子 realm 的构造器源码文本 → 其余
  时间戳派生槽、window 键集派生槽 不要追

步骤 7: 服务端验收
  协议客户端 --mint local --pages 1
  期望：code 37 → set/zpToken code 0 → 业务接口返回数据
```

---

## 还原代码模板

### 核心类：TokenMinter（在 jsdom 里执行厂商 SDK 铸 token）

```javascript
/**
 * 在 jsdom 里执行厂商 security-js 铸 token
 * 依赖：npm install jsdom；运行时必须带 --allow-natives-syntax
 * 原理：
 *   1) 造一份「原生性正确」的环境（文档形状 / document.all 活性 / iframe 子 realm 源码文本）
 *   2) eval 厂商原始字节（不要用任何改写版）
 *   3) 调用 SDK 暴露的构造函数铸 token
 * 注意：几何、canvas 真值等常量必须在本机实测后填入，不要沿用别处快照。
 */
const fs = require('fs');
const vm = require('vm');
const { JSDOM } = require('jsdom');

class TokenMinter {
  constructor({ sdkPath, env, pageUrl }) {
    this.sdk = fs.readFileSync(sdkPath, 'utf8');
    this.env = env;              // { screen:{w,h,aw,ah}, win:{iw,ih,ow,oh,sy}, canvas:'data:image/png;base64,...' }
    this.pageUrl = pageUrl;
  }

  build() {
    const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
      url: this.pageUrl, pretendToBeVisual: true, runScripts: 'dangerously',
    });
    const win = dom.window;
    this.patchGeometry(win);
    this.patchDocumentShape(win);
    this.patchDocumentAll(win);
    this.patchIframeRealm(win);
    this.patchCanvas(win);
    win.eval(this.sdk);
    this.win = win;
    return this;
  }

  // 1) 几何：用本机实测值（旧快照会让若干布尔位翻转）
  patchGeometry(win) {
    const s = this.env.screen, w = this.env.win;
    const def = (o, k, v) => Object.defineProperty(o, k, { get: () => v, configurable: true });
    def(win.screen, 'width', s.w); def(win.screen, 'height', s.h);
    def(win.screen, 'availWidth', s.aw); def(win.screen, 'availHeight', s.ah);
    def(win, 'innerWidth', w.iw); def(win, 'innerHeight', w.ih);
    def(win, 'outerWidth', w.ow); def(win, 'outerHeight', w.oh);
    def(win, 'screenY', w.sy);
  }

  // 2) 文档形状：自有属性数与可枚举数都要匹配真实引擎
  patchDocumentShape(win) {
    const d = win.document, P = Object.getPrototypeOf(d);
    for (const n of ['fonts', 'readyState', 'domain', 'visibilityState', 'hidden']) {
      const desc = Object.getOwnPropertyDescriptor(d, n);
      if (desc && desc.configurable) { Object.defineProperty(P, n, desc); delete d[n]; }
    }
    for (const n of Object.getOwnPropertyNames(d)) {
      const desc = Object.getOwnPropertyDescriptor(d, n);
      if (desc && desc.configurable && !desc.enumerable) {
        desc.enumerable = true; Object.defineProperty(d, n, desc);
      }
    }
  }

  // 3) document.all：undetectable + 活索引（长度活、下标也活、且索引不可删）
  patchDocumentAll(win) {
    const und = vm.runInThisContext('%GetUndetectable()');   // 需 --allow-natives-syntax
    if (und === null) throw new Error('缺少 --allow-natives-syntax');
    const elems = () => Array.prototype.slice.call(win.document.getElementsByTagName('*'));
    let defined = 0;
    const ensure = (n) => {
      for (let i = defined; i < Math.min(n, 8192); i++) {
        // 不可删：探针会 delete 掉越界索引后再读，真实引擎上删不掉
        Object.defineProperty(und, i, { get: () => elems()[i], enumerable: true, configurable: false });
      }
      defined = n;
    };
    Object.defineProperty(und, 'length', {
      get: () => { const L = elems().length; ensure(L + 8); return L; }, configurable: true,
    });
    Object.defineProperty(win.document, 'all', { get: () => und, configurable: true });
  }

  // 4) iframe 子 realm：构造器源码文本要是原生形态（JS 实现会明显变长）
  patchIframeRealm(win) {
    const NATIVE = 'function Window() { [native code] }';
    const desc = Object.getOwnPropertyDescriptor(win.HTMLIFrameElement.prototype, 'contentWindow');
    if (!desc || !desc.get) return;
    const seen = [];
    const once = (w) => {
      if (seen.includes(w)) return;
      seen.push(w);
      try {
        const F = w.Function, WC = w.constructor;
        if (!F || F.prototype === win.Function.prototype || typeof WC !== 'function') return;
        const fts = F.prototype.toString;
        const nt = function toString() { return this === WC ? NATIVE : fts.call(this); };
        Object.defineProperty(F.prototype, 'toString', { value: nt, configurable: true, writable: true });
      } catch (e) {}
    };
    Object.defineProperty(win.HTMLIFrameElement.prototype, 'contentWindow', {
      configurable: true,
      get: function () { const w = desc.get.call(this); try { if (w) once(w); } catch (e) {} return w; },
    });
  }

  // 5) canvas：渲染结果无法仿真，直接用本机采到的真值（其摘要会进载荷）
  patchCanvas(win) {
    const real = this.env.canvas;
    if (!real) return;
    win.HTMLCanvasElement.prototype.toDataURL = function () { return real; };
  }

  // 铸一次（调试时一次加载只铸一次）
  mint(seed, rawTs) {
    if (!this.win) this.build();
    const tz = new Date().getTimezoneOffset();
    return String(new this.win.ABC().z(seed, rawTs + (480 + tz) * 60000));
  }
}

module.exports = { TokenMinter };
```

---

## 踩坑记录

| # | 坑 | 现象 | 解决方法 |
|---|---|---|---|
| 1 | 在线改写路由残留 | 页面取回的 SDK 比厂商版大出一截，误判成"服务端下发第二个版本"，并据此做了一整轮错误校准 | 字段级对照前先 `instrumentation(action="status")`，非空先 `stop`；取回脚本立刻核 `len` + `sha256` |
| 2 | 同页面连续铸造 | 同一页面连铸 3 次，执行步数各不相同，误判"浏览器不可复现" | 每次铸造都会往 `window` 加键；改成"重载页面 → 只铸一次"后，多次采样绝大多数槽完全一致 |
| 3 | 两侧随机源没对齐 | 同一 seed 本地三次铸出三种不同长度，逐字节比较结论全废 | 时间 / `Math.random` / WebCrypto 用同一份确定性注入，且必须在 SDK eval 之前注入 |
| 4 | 调试 prelude 污染键数 | 注入 `__trace`/`__dumpLog` 等全局后 `Object.keys(window)` 变了，而 SDK 正是读这个数进载荷 | 测载荷的工具不要注入额外全局；必须注入时单独成组并在结论里标注 |
| 5 | 把时间派生槽当缺口追 | 两个槽两次采样差几十，怎么补都对不上 | 它们是一个时间戳的秒/毫秒部分；同侧多次采样取交集，只追"稳定且两侧不同"的槽 |
| 6 | `document.all` 只做对了一半 | 只做 undetectable + 长度活，`all[length]` 仍取不到新追加的节点，探针必失败 | 索引也必须活（惰性 getter 回读），且 `configurable:false`（探针会 delete 后再读） |
| 7 | iframe 补丁打在主 realm | 在 `window` 上覆盖 `Function.prototype.toString`，目标槽一位不动、命中日志 0 条 | 每个 iframe 有独立 intrinsics，必须包 `contentWindow` getter 在**子 realm** 打补丁 |
| 8 | 探针自身的两种自伤 | 不带 `--allow-natives-syntax` 时执行步数变化；对热寄存器"每次变化都回调"时 token 直接变形 | 运行时必带该参数；探针用内联计数器 + 区间限流，只对目标对象回调 |
| 9 | `finally` 挂错分发循环 | 调用帧全错，几百次激活只有 1 次记录到退出，追到的实参落在错误帧 | 文件里有两个扁平化分发循环，`finally` 要挂在主 VM 的那个 `catch` 上 |
| 10 | 出口 IP 风控 | 突然连 seed 都拿不到，返回 `code 35` | 与 token 无关；等冷却或换出口，且必须走 IPv4 |

---

## 这一轮我判断错的四次

| # | 我当时的判断 | 实际 | 推翻它的判据 |
|---|---|---|---|
| 1 | "服务端下发了两个版本的 SDK" | 是我自己开的在线改写路由在改写脚本 | `instrumentation status` 显示 `files_rewritten>0`；停掉路由后页面取回的字节与归档厂商版一致 |
| 2 | "浏览器侧不可复现，所以没法继续二分" | 采样方式错了：同页面连铸改变了全局键数 | 改成"重载 + 单铸"后，多次采样绝大多数槽完全相同 |
| 3 | 拿"单次浏览器 token"做逐字符 diff | 那个基准本身在不稳定槽上抖动，差异无法归因 | 同侧多次采样显示这些槽自己就在变 |
| 4 | 换页面（如 `robots.txt`）来"稳定基准" | 换页面等于换被测环境，DOM/文档状态全变 | 同一 token 在不同页面下 ASCII 计数、载荷头部都不同 |

**共同点**：四次都是"测量方式"出问题，而不是逆向结论错。**先证明测量可信，再谈结论。**

---

## 关键判据

补环境类任务，可以直接拿这几条验收：

1. **字节身份**：脚本 `len` + `sha256` 与归档一致；取回路径上没有改写/拦截。
2. **结构等价**：两侧载荷码点数、ASCII 计数、头部 3 个常量码完全一致。
3. **分类收敛**：把槽分成「稳定」与「本侧自己会变」；稳定槽全部一致才算对齐，标准是**同侧多次采样取交集**。
4. **单点可归因**：每个修复都必须能证明"只动目标槽、其余不动"；广播级联（几十上百槽同变）只能算线索。
5. **服务端验收**：最终判据只有服务端返回码，不是本地差异数。

---

## 变体说明

| 变体 | 差异点 | 影响 |
|------|--------|------|
| SDK 换版 | 文件名与体积变化，历史上见过多个不同版本号 | 必须重核 `sha256` 并重跑"反解对照 → 残差清单"；状态号可能整体位移 |
| 新功能块入载荷 | 某些版本把 WebGL 能力块也放进载荷（本例版本没有） | 槽位整体位移，需按新偏移重建槽表 |
| 出口地区 / 网络类型 | 同一份 token，不同出口判定不同 | IPv6 出口直接 `code 35`；需强制 IPv4 或指定代理 |
| 登录态 | 带登录 Cookie 时判定更宽松 | 未登录态对载荷内容要求更高，补环境门槛更高 |
| canvas 渲染栈 | 浏览器版本 / 系统字体 / DPI 不同，`toDataURL` 真值不同 | 必须本机重采，用 `len` + `md5` + 尾字符做真值指纹 |
