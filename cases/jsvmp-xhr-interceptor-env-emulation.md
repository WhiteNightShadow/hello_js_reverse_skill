# JSVMP 字节码虚拟机 + XHR 拦截器 + 多层 SDK 联动 + jsdom 全量环境伪装

> 难度：★★★★★
> 还原方案：E: jsdom 环境模拟（喂入-截出策略）
> 实现语言：Node.js
> 最后验证日期：2026-04-01
> 平台类型：短视频平台

---

## 技术指纹（供 Phase 0.5 自动匹配）

### JS 特征
- [x] `window['_$webrt_1668687510']` — JSVMP 解释器入口函数，接受十六进制字节码字符串
- [x] 单文件 380KB+，包含 `'HNOJ@?RC'` 魔数校验
- [x] `_0x` 前缀变量大量出现（构造函数、工厂函数、闭包变量）
- [x] UMD 模式导出到 `window.byted_acrawler`（浏览器）或 `module.exports`（Node.js）
- [x] 存在 while-switch 风格的 JSVMP 解释器循环（`_0x1218ef` / `_0x5f1fc4` 函数）
- [x] 内部状态对象含 `bogusIndex`、`msNewTokenList`、`moveList`、`clickList`、`activeState`
- [x] 三层 SDK 脚本联动：`sdk-glue.js`（100KB）→ `bdms.js`（147KB）→ `webmssdk.es5.js`（387KB）

### 参数特征
- [x] `a_bogus`：约 180~192 字符，Base64 变体编码（含 `+`、`/`、`=`）
- [x] `X-Bogus`（旧版）：16 字符，字母数字（由 `frontierSign()` 生成，非 JSVMP 拦截器）
- [x] `msToken`：约 140 字符，Base64 编码，来自目标域名的 Cookie
- [x] `verifyFp` / `fp`：格式 `verify_xxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx`
- [x] `UIFID`：约 256 字符 hex 编码，浏览器指纹标识

### 请求特征
- [x] 页面 inline script 调用 `window._SdkGlueInit(config, resources)` 完成初始化
- [x] 初始化配置含 `bdms.paths` 数组（正则路径列表，如 `'^/aweme/v1/'`）
- [x] JSVMP 通过修改 `XMLHttpRequest.prototype.open` 实现请求拦截
- [x] 拦截器仅对匹配 `enablePathList` 的 URL 追加 `a_bogus`
- [x] 默认仅拦截 `/web/report`，需通过 `_SdkGlueInit` 注入业务路径
- [x] Cookie 中包含动态字段：`ttwid`、`__ac_nonce`、`__ac_signature`、`s_v_web_id`、`odin_tt`

### 反调试特征
- [x] JSVMP 字节码执行，无法直接设置断点
- [x] debugger 定时器陷阱（可通过 `bypass_debugger_trap` 绕过）
- [x] 环境检测（58 项）：`Function.prototype.toString` 原生性检查、`navigator.webdriver`、`navigator.plugins.length`、`document.hasFocus()`、DOM `offsetHeight/Width` 零值检测、`Object.prototype.toString` 标签、`window.chrome` 存在性、`Performance.timing` 对象、Canvas/WebGL 指纹、AudioContext 指纹等
- [x] 非真实浏览器环境生成的签名会被服务端**静默拒绝**（返回 HTTP 200 + 空 body，不报错）

### 混淆类型
- [x] JSVMP（JavaScript Virtual Machine Protection），字节码存储为十六进制字符串，由解释器 `_$webrt_1668687510` 运行时执行

### 指纹检测规则（Agent 执行）

```
快速检测命令（30秒内完成）：
  - search_code(keyword="webmssdk") → 命中 → 直接定位本案例
  - search_code(keyword="byted_acrawler") → 命中 → 直接定位本案例
  - search_code(keyword="_SdkGlueInit") → 命中 → 直接定位本案例
  - search_code(keyword="a_bogus") → 命中 + 参数长度 180-192 → 高置信度
  - list_scripts → 存在 380KB+ 文件 → 辅助确认
  匹配判定：以上前 3 项命中任意 1 项 → 高置信度匹配
```

---

## 加密方案

- **算法**：JSVMP 自定义字节码虚拟机，内部算法不可直接读取。签名结果为 `a_bogus`（~192 字符 Base64 变体）或 `X-Bogus`（16 字符）
- **密钥来源**：动态计算 — 由浏览器环境指纹（Canvas/WebGL/navigator/screen 等数十项数据）+ 请求 URL query string + User-Agent + 时间戳共同生成
- **加密流程**：
  1. `sdk-glue` 通过 `_SdkGlueInit(config, resources)` 初始化，注入拦截路径列表
  2. `webmssdk` JSVMP 构造函数执行字节码，修改 `XMLHttpRequest.prototype.open`
  3. 当 XHR 请求 URL 匹配 `enablePathList` 中的正则时，拦截器触发
  4. JSVMP 读取完整 URL query string、`document.cookie`、`navigator.*` 属性、`screen.*` 属性等数十项环境指纹
  5. JSVMP 内部通过字节码计算生成 `a_bogus` 值（含环境指纹哈希）
  6. 拦截器将 `&a_bogus=xxx` 追加到 URL 末尾，再调用原始 `open`
- **签名公式**：无法提取（JSVMP 字节码保护，算法封装在虚拟机内部）。采用「喂入-截出」策略：在 jsdom 中执行原始 JSVMP 字节码，通过 XHR Hook 截获最终签名值

---

## 方案方向

jsdom 环境伪装，喂入-截出策略截获 a_bogus。环境值必须与 UA 自洽。

## 各 Phase 加速指引

- **Phase 1**: `search_code(keyword="_SdkGlueInit")` 定位配置；`scripts(action='save')` 保存三件套（webmssdk.es5.js / bdms.js / sdk-glue.js）到 `config/`
- **Phase 2**: 加载顺序 webmssdk → bdms → sdk-glue → `_SdkGlueInit`；签名在 XHR send 阶段追加
- **Phase 3**: 用 Camoufox `compare_env` + `evaluate_js` 分批采集真实环境，与 jsdom 逐项 diff，**确认需要补的环境项范围后再写补丁**
- **Phase 4**: jsdom 配置需 `resources:'usable'`；XHR Hook 必须在 SDK 加载前安装；`scanPrototypeChain` 的 `Object.prototype` 边界不能突破
- **Phase 5**: 连续 ≥5 次请求验证，200 + 空 body = 环境指纹不对不是算法错

## 踩坑记录

- **不要对 Object.prototype / Array.prototype 做 markNative**，会破坏 JSVMP 自身运行
- **SDK 脚本必须保存到本地**（`scripts(action='save')`），不要每次从 CDN 下载
- 签名 192 字符但服务端返回空 body = 环境指纹不对，不是算法错
- **环境补丁逐项添加逐项验证**，不要批量添加后排查
- Firefox 和 Chrome 环境都可以工作，关键是所有值与 UA 自洽
- XHR Hook 顺序：我方 Hook → SDK 加载（保存 Hook 后的引用）→ JSVMP 调用时经过我方 Hook

## 原始定位路径（参考，不要跳过 Phase 直接照做）

> 以下是首次分析时的实际步骤记录，供理解方案演进过程。实战时仍需走 Phase 1-5。

### Phase 1：网络捕获定位接口

```
步骤 1: start_network_capture + list_network_requests → 捕获带 a_bogus 的完整请求 URL
步骤 2: search_code(keyword="bdms") → 找到三个关键脚本的 CDN 地址：
        - webmssdk.es5.js (v1.0.0.20, 387KB) — JSVMP 签名引擎
        - bdms.js (v1.0.1.19, 147KB) — ByteDance Monitoring System
        - sdk-glue.js (v1.0.0.64, 100KB) — SDK 胶水层
```

### Phase 2：初始化链路还原

```
步骤 3: search_code(keyword="enablePathList") → 定位到 sdk-glue 中的路径配置机制
步骤 4: 页面 inline script 中找到 _SdkGlueInit 调用及完整的 paths 配置
步骤 5: search_code(keyword="frontierSign") → 找到 webmssdk 的导出结构：init() / frontierSign() / setConfig()
步骤 6: search_code(keyword="bogusIndex") → 确认 a_bogus 由 JSVMP 的 XHR 拦截器生成（不同于 frontierSign 生成的 X-Bogus）
```

### Phase 3：jsdom 沙箱验证

```
步骤 7: 在 jsdom (runScripts: 'dangerously') 中依次加载三个脚本并调用 _SdkGlueInit，
        成功触发 JSVMP 的 XHR 拦截器生成 192 字符的 a_bogus
步骤 8: 浏览器生成的 a_bogus 用 Node.js axios 请求成功 → 确认非 TLS 问题
步骤 9: jsdom 生成的 a_bogus 被服务端拒绝（返回空 body）→ 确认是环境指纹差异
```

### Phase 4：环境指纹对比（核心突破点）

```
步骤 10: 用 camoufox-reverse MCP 启动反检测浏览器，navigate 到目标页面
步骤 11: 通过 evaluate_js 分批采集浏览器完整环境指纹
         （navigator 24项 / screen 10项 / window 40项 / document 16项 /
          performance 12项 / toString 7项 / Function.toString 6项 /
          DOM布局 6项 / Canvas+WebGL+Audio 各项）
步骤 12: 在 jsdom 中运行完全相同的采集代码
步骤 13: 逐项对比发现 58 项差异，按影响分级修复
```

### Phase 5：环境补丁与验证

```
步骤 14: 编写 patchEnvironment() 函数修复全部 58 项差异
步骤 15: 从 jsdom 内部验证所有检测点通过（win.eval() 内执行 Function.prototype.toString 等）
步骤 16: 连续 5 次请求同一视频 ID，全部返回完整数据（35KB+），确认稳定性
```

---

## 还原代码模板

### 核心函数：markNative — 将 jsdom 函数伪装为浏览器原生函数

```javascript
const _origFnToString = win.Function.prototype.toString;
const nativeFnSet = new WeakSet();

function markNative(fn) {
  if (typeof fn === 'function') {
    nativeFnSet.add(fn);
    try {
      const name = fn.name || '';
      Object.defineProperty(fn, 'toString', {
        value: function () { return `function ${name}() { [native code] }`; },
        writable: true, configurable: true,
      });
    } catch (e) {}
  }
  return fn;
}

// jsdom 内部函数的通用源码特征（不在 WeakSet 中的漏网之鱼）
const jsdomPatterns = [
  /^\s*\w+\s*\([^)]*\)\s*\{[\s\S]*?const\s+esValue\s*=/,
  /^\s*function\s*\([^)]*\)\s*\{[\s\S]*?this\._globalObject/,
  /^\s*\w+\s*\([^)]*\)\s*\{\s*const\s+\w+\s*=\s*this\s*!==/,
];

win.Function.prototype.toString = function () {
  if (nativeFnSet.has(this)) {
    return `function ${this.name || ''}() { [native code] }`;
  }
  let src;
  try { src = _origFnToString.call(this); } catch (e) {
    return 'function () { [native code] }';
  }
  for (const pat of jsdomPatterns) {
    if (pat.test(src)) return `function ${this.name || ''}() { [native code] }`;
  }
  return src;
};
```

### 核心函数：深度扫描原型链标记所有 jsdom 内置方法

```javascript
function scanPrototypeChain(obj, maxDepth) {
  let proto = obj;
  for (let d = 0; d < (maxDepth || 10) && proto; d++) {
    for (const name of Object.getOwnPropertyNames(proto)) {
      try {
        const desc = Object.getOwnPropertyDescriptor(proto, name);
        if (desc && typeof desc.value === 'function') markNative(desc.value);
        if (desc && typeof desc.get === 'function') markNative(desc.get);
        if (desc && typeof desc.set === 'function') markNative(desc.set);
      } catch (e) {}
    }
    proto = Object.getPrototypeOf(proto);
    if (proto === Object.prototype || proto === null) break;
  }
}

// 扫描 50+ 原型链，覆盖 jsdom 所有内置类
const protoTargets = [
  win.Document?.prototype, win.HTMLDocument?.prototype,
  win.Element?.prototype, win.HTMLElement?.prototype,
  win.Node?.prototype, win.EventTarget?.prototype,
  win.XMLHttpRequest?.prototype, win.HTMLCanvasElement?.prototype,
  // ... 扫描 50+ 个 DOM 类的原型链
];
for (const proto of protoTargets) {
  if (proto) scanPrototypeChain(proto, 3);
}
scanPrototypeChain(doc, 5);   // document 实例自身
scanPrototypeChain(nav, 5);   // navigator 实例自身
```

### 核心函数：navigator.plugins 完整模拟

```javascript
const pluginData = [
  { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
  { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
  { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
  { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
  { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
];
const mimeData = [
  { type: 'application/pdf', description: 'Portable Document Format', suffixes: 'pdf' },
  { type: 'text/pdf', description: 'Portable Document Format', suffixes: 'pdf' },
];

// 构建完整的 PluginArray → Plugin → MimeType 对象树
// 包含 item()/namedItem()/refresh() 方法 + Symbol.toStringTag
```

### 核心函数：a_bogus 生成（喂入-截出策略）

```javascript
function generateABogus(fullUrl, cookieStr) {
  const dom = initSdk();  // jsdom + 环境补丁 + SDK 加载（单例）
  const win = dom.window;

  // 写入 Cookie 供 JSVMP 读取
  if (cookieStr) {
    cookieStr.split(';').forEach(c => {
      try { win.document.cookie = c.trim(); } catch (e) {}
    });
  }

  return new Promise((resolve) => {
    win.__capturedUrls = [];
    // 在 jsdom 内发起 XHR，触发 JSVMP 拦截器自动追加 a_bogus
    win.eval(`(function(){
      var x = new XMLHttpRequest();
      x.open('GET','${fullUrl.replace(/'/g, "\\'")}',true);
      x.send();
    })()`);

    setTimeout(() => {
      let aBogus = null;
      for (const url of win.__capturedUrls) {
        const m = url.match(/[&?]a_bogus=([^&]+)/);
        if (m) { aBogus = decodeURIComponent(m[1]); break; }
      }
      resolve(aBogus);
    }, 500);
  });
}
```

---

## 踩坑记录

| # | 坑 | 现象 | 解决方法 |
|---|---|------|---------|
| 1 | Function.prototype.toString 暴露 jsdom | JSVMP 检测到非原生函数，生成无效签名 | 三层防御：WeakSet 精确标记 + jsdom 源码模式正则 + 实例级 Object.defineProperty |
| 2 | navigator.plugins 结构不完整 | 不是简单的 `length=5`，JSVMP 遍历 `item()`/`namedItem()` 并检查 `Symbol.toStringTag` | 构建完整 PluginArray→Plugin→MimeType 对象树 |
| 3 | DOM 布局属性全为 0 | jsdom 无渲染引擎，`offsetHeight`/`Width`/`getBoundingClientRect` 返回 0 | HTMLElement.prototype getter 覆写，解析 style 或返回默认非零值 |
| 4 | Object.prototype.toString 标签错误 | jsdom 的 document 原型链是 `Document` 而非 `HTMLDocument`，screen 是普通对象 | `Symbol.toStringTag` 修复 + 原型链 `constructor.name` 修改 |
| 5 | XHR Hook 顺序导致截获失败 | webmssdk 保存的是 Hook 之前的原始 `open`，我方 Hook 截获不到最终 URL | 必须在 webmssdk 加载前完成 XHR Hook 安装 |
| 6 | 服务端静默拒绝 | 环境不完整时返回 HTTP 200 + 空 body，不返回错误码 | 通过对比 Camoufox 真实环境逐项排查 58 项差异 |

---

## 变体说明

| 变体 | 差异点 | 影响 |
|------|--------|------|
| X-Bogus（旧版） | 由 `frontierSign()` 生成的 16 字符签名，非 JSVMP 拦截器 | 较简单，可通过 Hook `frontierSign` 入参直接还原 |
| 不同业务线 | `enablePathList` 配置不同，不同业务接口使用不同路径正则 | 需从 `_SdkGlueInit` 调用中提取完整 paths 配置 |
| SDK 版本迭代 | `webmssdk` 版本号更新，字节码变化 | 环境检测项可能增加，需重新对比 `compare_env` |

---

## 浏览器指纹采集方法

使用 camoufox-reverse MCP 在真实浏览器中采集指纹的完整流程：

```
步骤 1: launch_browser({headless: false, os_type: "macos", locale: "zh-CN"})
步骤 2: navigate({url: "目标页面", wait_until: "domcontentloaded"})
步骤 3: 分批采集环境指纹（通过 evaluate_js 在页面上下文中执行）
```

### 批次 A: navigator 属性

```javascript
JSON.stringify({
  nav_userAgent: navigator.userAgent,
  nav_platform: navigator.platform,
  nav_language: navigator.language,
  nav_languages: navigator.languages,
  nav_cookieEnabled: navigator.cookieEnabled,
  nav_doNotTrack: navigator.doNotTrack,
  nav_onLine: navigator.onLine,
  nav_hardwareConcurrency: navigator.hardwareConcurrency,
  nav_maxTouchPoints: navigator.maxTouchPoints,
  nav_webdriver: navigator.webdriver,
  nav_vendor: navigator.vendor,
  nav_productSub: navigator.productSub,
  nav_appVersion: navigator.appVersion,
  nav_deviceMemory: navigator.deviceMemory,
  nav_plugins_length: navigator.plugins ? navigator.plugins.length : -1,
  nav_mimeTypes_length: navigator.mimeTypes ? navigator.mimeTypes.length : -1,
  nav_pdfViewerEnabled: navigator.pdfViewerEnabled,
  nav_connection_type: typeof navigator.connection,
  nav_getBattery_type: typeof navigator.getBattery,
  nav_userAgentData_type: typeof navigator.userAgentData
})
```

### 批次 B: screen + window 属性

```javascript
JSON.stringify({
  scr_width: screen.width, scr_height: screen.height,
  scr_availWidth: screen.availWidth, scr_availHeight: screen.availHeight,
  scr_colorDepth: screen.colorDepth, scr_pixelDepth: screen.pixelDepth,
  scr_availLeft: screen.availLeft, scr_availTop: screen.availTop,
  scr_orientation_type: screen.orientation ? screen.orientation.type : undefined,
  win_innerWidth: window.innerWidth, win_innerHeight: window.innerHeight,
  win_outerWidth: window.outerWidth, win_outerHeight: window.outerHeight,
  win_devicePixelRatio: window.devicePixelRatio,
  win_chrome: typeof window.chrome,
  win_Notification: typeof window.Notification,
  win_SharedWorker: typeof window.SharedWorker,
  win_WebSocket: typeof window.WebSocket,
  win_RTCPeerConnection: typeof window.RTCPeerConnection,
  win_AudioContext: typeof window.AudioContext,
  win_OfflineAudioContext: typeof window.OfflineAudioContext,
  win_fetch: typeof window.fetch,
  win_Worker: typeof window.Worker,
  win_isSecureContext: window.isSecureContext,
  win_matchMedia: typeof window.matchMedia,
  win_indexedDB: typeof window.indexedDB,
  win_visualViewport: typeof window.visualViewport,
  win_clientInformation: typeof window.clientInformation
})
```

### 批次 C: document + performance + toString + Function.toString

```javascript
JSON.stringify({
  doc_hidden: document.hidden,
  doc_visibilityState: document.visibilityState,
  doc_hasFocus: document.hasFocus(),
  doc_characterSet: document.characterSet,
  doc_compatMode: document.compatMode,
  doc_readyState: document.readyState,
  doc_fullscreenEnabled: document.fullscreenEnabled,
  doc_fonts_type: typeof document.fonts,
  doc_timeline_type: typeof document.timeline,
  perf_timing_type: typeof performance.timing,
  perf_navigation_type: typeof performance.navigation,
  perf_memory_type: typeof performance.memory,
  toString_nav: Object.prototype.toString.call(navigator),
  toString_doc: Object.prototype.toString.call(document),
  toString_win: Object.prototype.toString.call(window),
  toString_scr: Object.prototype.toString.call(screen),
  toString_perf: Object.prototype.toString.call(performance),
  fn_eval: eval.toString().substring(0, 60),
  fn_setTimeout: setTimeout.toString().substring(0, 60),
  fn_createElement: document.createElement.toString().substring(0, 80),
  FnProto_toString: Function.prototype.toString.call(Function.prototype.toString).substring(0, 80),
  nav_proto: Object.getPrototypeOf(navigator).constructor.name,
  doc_proto: Object.getPrototypeOf(document).constructor.name,
  nav_toStringTag: navigator[Symbol.toStringTag],
  doc_toStringTag: document[Symbol.toStringTag]
})
```

### 批次 D: DOM 布局 + Canvas + WebGL + Audio

```javascript
JSON.stringify({
  dom_test: (function(){
    var d = document.createElement('div');
    d.style.cssText = 'width:100px;height:100px;position:absolute;left:-9999px';
    document.body.appendChild(d);
    var r = {offsetHeight: d.offsetHeight, offsetWidth: d.offsetWidth,
             clientHeight: d.clientHeight, clientWidth: d.clientWidth};
    var rect = d.getBoundingClientRect();
    r.rect_width = rect.width; r.rect_height = rect.height;
    document.body.removeChild(d);
    return r;
  })(),
  canvas_test: (function(){
    var c = document.createElement('canvas'); c.width = 200; c.height = 50;
    var ctx = c.getContext('2d');
    ctx.textBaseline = 'top'; ctx.font = '14px Arial';
    ctx.fillStyle = '#f60'; ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = '#069'; ctx.fillText('abcdef', 2, 15);
    return {dataURL_len: c.toDataURL().length};
  })(),
  webgl_test: (function(){
    try {
      var c = document.createElement('canvas');
      var gl = c.getContext('webgl');
      var ext = gl.getExtension('WEBGL_debug_renderer_info');
      return {
        vendor: gl.getParameter(gl.VENDOR),
        renderer: gl.getParameter(gl.RENDERER),
        unmasked_vendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : 'N/A',
        unmasked_renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'N/A'
      };
    } catch(e) { return {error: e.message}; }
  })(),
  audio_test: (function(){
    try { var ctx = new OfflineAudioContext(1,44100,44100);
      return {sampleRate: ctx.sampleRate, available: true};
    } catch(e) { return {error: e.message}; }
  })()
})
```

---

## 环境检测差异全表（58 项）

### 致命级（缺失即被拒）

| 检测点 | 真实浏览器值 | jsdom 原始值 | 修复方式 |
|--------|-------------|-------------|---------|
| `Function.prototype.toString` | `function X() { [native code] }` | 暴露实际实现代码（如 `createElement(localName) { const esValue = ...`） | WeakSet 精确标记 + jsdom 源码模式正则 + 实例级 `Object.defineProperty(fn, 'toString')` |
| `navigator.webdriver` | `false` | `undefined` | `Object.defineProperty` 强制设为 `false` |
| `navigator.plugins.length` | `5` | `0` | 模拟 Chrome 5 个 PDF 插件（含完整 PluginArray/Plugin/MimeType 结构） |
| `document.hasFocus()` | `true` | `false` | 方法覆写，始终返回 `true` |
| DOM `offsetHeight/Width` | 非零值（如 100） | `0` | `HTMLElement.prototype` getter 覆写，解析 style 或返回默认值 |

### 高危级（可能参与指纹哈希）

| 检测点 | 真实浏览器值 | jsdom 原始值 | 修复方式 |
|--------|-------------|-------------|---------|
| `Object.prototype.toString(document)` | `[object HTMLDocument]` | `[object Document]` | `Symbol.toStringTag` 修复 + 原型链 `constructor.name` 修改 |
| `Object.prototype.toString(screen)` | `[object Screen]` | `[object Object]` | 重建 screen 对象并设置 `Symbol.toStringTag` |
| `window.chrome` | `{app:{...}, runtime:{...}, csi, loadTimes}` | `undefined` | 完整 Chrome 对象模拟（含 `runtime.OnInstalledReason` 等枚举） |
| `navigator.userAgentData` | `NavigatorUAData` 对象 | `undefined` | 模拟 Chrome brands/mobile/platform + `getHighEntropyValues()` |
| `navigator.platform` | `MacIntel` | `""` | `Object.defineProperty` 覆盖 |
| `navigator.language` | `zh-CN` | `en-US` | `Object.defineProperty` 覆盖 |
| `navigator.languages` | `["zh-CN", "zh"]` | `["en-US", "en"]` | `Object.defineProperty` 覆盖 |
| `performance.timing` | 完整 `PerformanceTiming` 对象（20+ 字段） | `undefined` | 构造合理的 timing 对象（时间戳递增） |
| `performance.navigation` | `PerformanceNavigation` 对象 | `undefined` | 构造 `{type:0, redirectCount:0}` 对象 |
| `document.readyState` | `complete` | `loading` | getter 覆写返回 `'complete'` |
| `screen.colorDepth/pixelDepth` | `30` | `24` | 重建 screen 对象 |
| `screen.orientation` | `{type: 'landscape-primary', angle: 0}` | `undefined` | 重建 screen 对象含 orientation |

### 中危级（API 存在性检测）

| 检测点 | jsdom 原始值 | 修复方式 |
|--------|-------------|---------|
| `window.Notification` | `undefined` | 构造函数存根 + `permission`/`requestPermission` |
| `window.Worker` / `SharedWorker` | `undefined` | 构造函数存根 |
| `window.RTCPeerConnection` | `undefined` | 构造函数存根 |
| `window.AudioContext` / `OfflineAudioContext` | `undefined` | 完整 Web Audio API 存根（含 `createOscillator`/`createDynamicsCompressor`/`startRendering`） |
| `window.fetch` | `undefined` | 函数存根 + `Request`/`Response`/`Headers`/`AbortController` |
| `window.matchMedia` | `undefined` | 返回 `{matches:false, media:query}` 存根 |
| `window.requestIdleCallback` | `undefined` | `setTimeout` 包装 |
| `window.indexedDB` | `undefined` | `IDBFactory` 存根 |
| `window.caches` | `undefined` | `CacheStorage` 存根 |
| `window.speechSynthesis` | `undefined` | `SpeechSynthesis` 存根 |
| `window.customElements` | `undefined` | `CustomElementRegistry` 存根 |
| `window.visualViewport` | `undefined` | `VisualViewport` 存根 |
| `window.isSecureContext` | `undefined` | 设为 `true` |
| `window.clientInformation` | `undefined` | 指向 `navigator` |
| `navigator.connection` | `undefined` | `NetworkInformation` 存根 |
| `navigator.getBattery` | `undefined` | 返回 `BatteryManager` Promise |
| `navigator.deviceMemory` | `undefined` | 设为 `8` |
| `navigator.maxTouchPoints` | `undefined` | 设为 `0` |
| `navigator.pdfViewerEnabled` | `undefined` | 设为 `true` |
| `navigator.mimeTypes.length` | `0` | 模拟 2 个 MIME 类型 |
| `document.fonts` | `undefined` | `FontFaceSet` 存根 |
| `document.timeline` | `undefined` | `DocumentTimeline` 存根 |
| `document.fullscreenEnabled` | `undefined` | 设为 `true` |

---

## 关键经验总结

### 1. 为什么不反编译 JSVMP 字节码

JSVMP 用自定义指令集执行，反编译成本极高且版本迭代频繁。「喂入-截出」策略（在模拟环境中运行原始字节码，只截获 I/O）是性价比最高的方案。

### 2. jsdom 环境伪装的核心难度排序

| 排名 | 难度 | 检测项 | 为什么难 |
|------|------|--------|---------|
| 1 | ★★★★★ | `Function.prototype.toString` | jsdom 所有 DOM 方法都是 JS 实现，`toString()` 会暴露完整源码。需要三层防御：WeakSet 精确匹配 + jsdom 源码正则模式 + 实例级 toString 覆写 |
| 2 | ★★★★ | `navigator.plugins` 结构 | 不是简单的 `length=5`，JSVMP 可能遍历 `item()`/`namedItem()` 并检查 `Symbol.toStringTag` |
| 3 | ★★★ | DOM 布局属性 | jsdom 无渲染引擎，所有 `offsetHeight`/`Width`/`getBoundingClientRect` 返回 0 |
| 4 | ★★★ | `Object.prototype.toString` 标签 | jsdom 的 document 原型链是 `Document` 而非 `HTMLDocument`，screen 是普通对象 |
| 5 | ★★ | 30+ 缺失 API | 需要逐个补全，且每个都要 `markNative` 处理 toString |

### 3. XHR Hook 顺序至关重要

```
我方 Hook → webmssdk 加载（保存我方 Hook 后的 open 引用）→ JSVMP 执行时调用保存的 open
                                                              ↓
                                               我方 Hook 拦截到带 a_bogus 的 URL
```

如果 webmssdk 先加载再 Hook，JSVMP 保存的是原始 `open`，我方 Hook 无法截获最终 URL。

### 4. 对比方法论

用 Camoufox 反检测浏览器（C++ 引擎级指纹伪装）作为「干净基准」，在目标页面上下文中执行环境采集代码，与 jsdom 输出逐项 diff。分批采集（navigator / screen+window / document+performance+toString / DOM+Canvas+WebGL+Audio）避免单次执行过长。
