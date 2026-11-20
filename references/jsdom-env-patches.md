# jsdom 环境补丁知识库

目录：[概述](#概述) · [使用方法](#使用方法) · [常见候选一：原生性与自动化标记](#常见候选一原生性与自动化标记) · [常见候选二：对象标签与性能](#常见候选二对象标签与性能) · [常见候选三：API 存在性](#常见候选三api-存在性) · [window 尺寸属性](#window-尺寸属性) · [Node.js 特征清除](#nodejs-特征清除) · [完整 patchEnvironment 调用顺序](#完整-patchenvironment-调用顺序) · [环境采集对比方法](#环境采集对比方法) · [MCP 辅助工作流](#mcp-辅助工作流)

## 概述

> 这里是代码模板，不是必做清单。先用读值证据确认 SDK 实际读取，只补读到且与基线不同的项，判读方法见 [读值差异](original-sdk-runtime.md#读值差异)。分组只表示常见程度，不代表服务端规则。

当 JSVMP 选择路径 B（环境复现）在 jsdom 中运行时，jsdom 与真实浏览器存在大量差异。
本文档提供系统化的环境补丁方案，按检测影响分级，所有代码模板可直接复用。

## 使用方法

```javascript
const { JSDOM } = require('jsdom');

function createPatchedJsdom(url, options = {}) {
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    url: url,
    referrer: options.referrer || '',
    contentType: 'text/html',
    pretendToBeVisual: true,
    runScripts: 'dangerously',
  });
  const win = dom.window;
  const doc = win.document;
  const nav = win.navigator;

  patchEnvironment(win, doc, nav, options);
  return dom;
}
```

---

## 常见候选一：原生性与自动化标记

### 1. Function.prototype.toString 三层防御

**问题**：jsdom 所有 DOM 方法都是 JS 实现，`toString()` 会暴露完整源码（如 `createElement(localName) { const esValue = ...`），
JSVMP 通过此检测判断是否在真实浏览器中。

**难度**：★★★★★ — jsdom 路线里最容易暴露差异的一项

```javascript
const _origFnToString = win.Function.prototype.toString;
const nativeFnSet = new WeakSet();

// 第一层：精确标记 — WeakSet 注册已知 jsdom 内置函数
function markNative(fn) {
  if (typeof fn === 'function') {
    nativeFnSet.add(fn);
    try {
      const name = fn.name || '';
      // 第三层：实例级覆写 — 直接在函数对象上定义 toString
      Object.defineProperty(fn, 'toString', {
        value: function () { return `function ${name}() { [native code] }`; },
        writable: true, configurable: true,
      });
    } catch (e) {}
  }
  return fn;
}

// 第二层：源码模式正则 — 捕获 WeakSet 遗漏的 jsdom 函数
const jsdomPatterns = [
  /^\s*\w+\s*\([^)]*\)\s*\{[\s\S]*?const\s+esValue\s*=/,       // jsdom 接口方法模式
  /^\s*function\s*\([^)]*\)\s*\{[\s\S]*?this\._globalObject/,   // jsdom 全局对象访问模式
  /^\s*\w+\s*\([^)]*\)\s*\{\s*const\s+\w+\s*=\s*this\s*!==/,   // jsdom this 检查模式
  /throw new TypeError\("Illegal constructor"\)/,              // jsdom WebIDL 构造器模式
];

// 覆写全局 Function.prototype.toString
win.Function.prototype.toString = function () {
  // 第一层：WeakSet 精确匹配
  if (nativeFnSet.has(this)) {
    return `function ${this.name || ''}() { [native code] }`;
  }
  let src;
  try { src = _origFnToString.call(this); } catch (e) {
    return 'function () { [native code] }';
  }
  // 第二层：源码模式正则检测
  for (const pat of jsdomPatterns) {
    if (pat.test(src)) return `function ${this.name || ''}() { [native code] }`;
  }
  return src;
};

// 深度扫描原型链，批量标记所有 jsdom 内置方法
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

// 扫描 50+ 原型链
const protoTargets = [
  win.Document?.prototype, win.HTMLDocument?.prototype,
  win.Element?.prototype, win.HTMLElement?.prototype,
  win.Node?.prototype, win.EventTarget?.prototype,
  win.XMLHttpRequest?.prototype, win.HTMLCanvasElement?.prototype,
  win.HTMLInputElement?.prototype, win.HTMLFormElement?.prototype,
  win.HTMLAnchorElement?.prototype, win.HTMLImageElement?.prototype,
  win.HTMLDivElement?.prototype, win.HTMLSpanElement?.prototype,
  win.HTMLBodyElement?.prototype, win.HTMLHeadElement?.prototype,
  win.HTMLScriptElement?.prototype, win.HTMLStyleElement?.prototype,
  win.HTMLLinkElement?.prototype, win.HTMLMetaElement?.prototype,
  win.Window?.prototype, win.Location?.prototype,
  win.DOMParser?.prototype, win.URL?.prototype,
  win.Event?.prototype, win.CustomEvent?.prototype,
  win.MutationObserver?.prototype, win.ResizeObserver?.prototype,
  win.DOMTokenList?.prototype, win.NamedNodeMap?.prototype,
  win.NodeList?.prototype, win.HTMLCollection?.prototype,
  win.CSSStyleDeclaration?.prototype, win.Text?.prototype,
  win.Comment?.prototype, win.DocumentFragment?.prototype,
  win.Range?.prototype, win.Selection?.prototype,
  win.TreeWalker?.prototype, win.NodeIterator?.prototype,
  win.Attr?.prototype, win.CharacterData?.prototype,
  win.Storage?.prototype, win.FormData?.prototype,
  win.Headers?.prototype,
];
for (const proto of protoTargets) {
  if (proto) scanPrototypeChain(proto, 3);
}
scanPrototypeChain(doc, 5);
scanPrototypeChain(nav, 5);
```

### 1.1 同源 iframe 子 Realm 的独立 toString 与原型链修补（按需启用）

**问题**：jsdom 中新建 `iframe` 时存在两层跨 Realm 陷阱：① 子窗口拥有独立的 `childWin.Function.prototype`，仅覆写顶层 `win.Function.prototype.toString` 管不到子 Realm；② `childWin.constructor`（`Window`）、`childWin.EventTarget` 及子窗口 WebIDL DOM 方法实际创建在 Node 外层 Realm（原型链指向外层 `Function.prototype` 而非 `childWin.Function.prototype`）。若不把 `childWin.EventTarget` 归位到 `childWin.Function.prototype` 并对子窗口原型链执行 `markNative`，读取 `String(iframe.contentWindow.constructor)` 或 `String(iframe.contentDocument.createElement)` 仍会直接暴露 jsdom 源码。注意 `formatNative` 输出格式须与基线浏览器内核一致（Chromium 单行 vs Firefox/Camoufox 多行）。

```javascript
// helpers: { markNative, nativeFnSet, jsdomPatterns, scanPrototypeChain, formatNative }
function patchIframeChildRealms(win, helpers, patchedRealms = new WeakSet()) {
  const {
    markNative, nativeFnSet, jsdomPatterns, scanPrototypeChain,
    formatNative = (name) => `function ${name || ''}() { [native code] }`,
  } = helpers;
  const proto = win.HTMLIFrameElement && win.HTMLIFrameElement.prototype;
  if (!proto) return;

  function patchChildWindow(childWin) {
    if (!childWin || patchedRealms.has(childWin)) return;
    patchedRealms.add(childWin);
    try {
      const ChildFn = childWin.Function;
      if (!ChildFn) return;
      // 将子窗口 EventTarget 归位到子 Realm 的 Function.prototype
      if (childWin.EventTarget && Object.getPrototypeOf(childWin.EventTarget) !== ChildFn.prototype) {
        Object.setPrototypeOf(childWin.EventTarget, ChildFn.prototype);
      }
      markNative(childWin.constructor);
      if (childWin.Document) markNative(childWin.Document);
      if (typeof scanPrototypeChain === 'function') {
        if (childWin.document) scanPrototypeChain(childWin.document, 5);
        if (childWin.navigator) scanPrototypeChain(childWin.navigator, 4);
        scanPrototypeChain(childWin, 3);
      }
      if (ChildFn.prototype !== win.Function.prototype) {
        const origToString = ChildFn.prototype.toString;
        const wrapped = function toString() {
          // 先走原生校验：非函数 this 继续抛出子 Realm 的 childWin.TypeError
          const src = origToString.call(this);
          if (nativeFnSet.has(this) || this === childWin.constructor) {
            return formatNative(this.name || '');
          }
          for (const pat of jsdomPatterns) {
            if (pat.test(src)) return formatNative(this.name || '');
          }
          return src;
        };
        Object.setPrototypeOf(wrapped, ChildFn.prototype);
        markNative(wrapped);
        Object.defineProperty(ChildFn.prototype, 'toString', {
          value: wrapped, writable: true, configurable: true,
        });
      }
      // 递归覆盖子窗口内部再创建的嵌套 iframe
      patchIframeChildRealms(childWin, helpers, patchedRealms);
    } catch (e) {}
  }

  // 同时拦截 contentWindow 与 contentDocument（防止经 contentDocument.defaultView 绕过）
  for (const prop of ['contentWindow', 'contentDocument']) {
    const desc = Object.getOwnPropertyDescriptor(proto, prop);
    if (!desc || typeof desc.get !== 'function') continue;
    const getter = markNative(function () {
      const val = desc.get.call(this);
      const targetWin = prop === 'contentWindow' ? val : (val && val.defaultView);
      if (targetWin) patchChildWindow(targetWin);
      return val;
    });
    Object.defineProperty(proto, prop, {
      get: getter, enumerable: desc.enumerable, configurable: true,
    });
  }
}
```

### 1.2 实例自有属性与原型链描述符形状对齐（按需启用）

**问题**：部分 SDK 会同时采集 `Object.getOwnPropertyNames(document).length` 与 `Object.keys(document).length`。原生 jsdom 空文档的 `document` 自有属性通常只有 `['location']`（`readyState`、`visibilityState`、`hidden` 本就在 `Document.prototype` 上）；实战中出现多余自有属性，最常见原因是**补环境脚本自己用 `Object.defineProperty(doc, ...)` 把原型属性挂到了实例上或漏设 `enumerable`**，其次是 `[LegacyUnforgeable]` 属性（如 `location`）在不同内核下的可枚举差异。首选从源头把 WebIDL 原型属性定义在 `Object.getPrototypeOf(doc)` 上；若需根据真实页面通过 `evaluate_js(..., world="main")` 采集的描述符快照事后收敛（注：`compare_env` 不导出 `document` 自有/原型描述符表），迁移时须保留已打补丁的 getter/value 并记录不可配置项：

```javascript
// realShape: { own: { [key]: { enumerable } }, protoOwned: ['readyState', 'fonts', ...], protoEnumerable?: { [key]: boolean } }
function alignOwnAndProtoShape(instance, realShape) {
  const proto = Object.getPrototypeOf(instance);
  const skippedUnconfigurable = [];
  for (const key of (realShape.protoOwned || [])) {
    const desc = Object.getOwnPropertyDescriptor(instance, key);
    if (!desc) continue;
    if (!desc.configurable) {
      skippedUnconfigurable.push(key);
      continue;
    }
    const protoDesc = proto ? Object.getOwnPropertyDescriptor(proto, key) : undefined;
    if (proto && (!protoDesc || protoDesc.configurable)) {
      const targetEnum = realShape.protoEnumerable && key in realShape.protoEnumerable
        ? realShape.protoEnumerable[key]
        : (protoDesc ? protoDesc.enumerable : true);
      Object.defineProperty(proto, key, { ...desc, enumerable: targetEnum });
    }
    delete instance[key];
  }
  for (const [key, meta] of Object.entries(realShape.own || {})) {
    const desc = Object.getOwnPropertyDescriptor(instance, key);
    if (!desc || typeof meta.enumerable !== 'boolean' || desc.enumerable === meta.enumerable) continue;
    if (!desc.configurable) {
      skippedUnconfigurable.push(key);
      continue;
    }
    Object.defineProperty(instance, key, { ...desc, enumerable: meta.enumerable });
  }
  return { skippedUnconfigurable };
}
```

### 1.3 `document.all` 引擎级 undetectable 与不可删活索引（按需启用）

**问题**：真实浏览器中 `Document.prototype.all` 满足 `typeof document.all === 'undefined'` 且 `document.all == null`，但按集合访问 `length`、`document.all[i]`、`[...document.all]` 又能实时反映 DOM 节点，且有效下标执行 `delete document.all[i]` 返回 `false` 并保留原节点（普通对象或顶层 `Proxy` 无法同时满足 `typeof === 'undefined'` 与活性集合语义）。在确认目标实际探测 `document.all` 时，受控本地 Node 进程可配合 `node --allow-natives-syntax` 的 `%GetUndetectable()` + 原型 `Proxy` 实现，并将 `all` 挂在 `Document.prototype` 上以避免污染 `document` 自有属性：

```javascript
// 注意：1) 进程须带 --allow-natives-syntax；2) lockIndices=true 会对当前 0..len-1 锁 configurable:false，若页面后续删除节点缩减 DOM 可传 lockIndices:false
function patchDocumentAll(win, vmModule, markNative, options = {}) {
  let und;
  try {
    und = vmModule.runInThisContext('%GetUndetectable()');
  } catch (err) {
    throw new Error('patchDocumentAll 需要以 node --allow-natives-syntax 启动进程', { cause: err });
  }
  const getNodes = () => Array.prototype.slice.call(win.document.getElementsByTagName('*'));
  let lockedCount = 0;
  function syncNonConfigurableIndices(len) {
    if (options.lockIndices === false) return;
    const cap = Math.min(len, 8192);
    for (let i = lockedCount; i < cap; i++) {
      Object.defineProperty(und, i, {
        get: () => getNodes()[i],
        enumerable: true,
        configurable: false,
      });
    }
    lockedCount = Math.max(lockedCount, cap);
  }
  const collectionProto = new Proxy(Object.create(null), {
    get(_t, prop) {
      const nodes = getNodes();
      if (prop === 'length') {
        syncNonConfigurableIndices(nodes.length);
        return nodes.length;
      }
      if (prop === Symbol.toStringTag) return 'HTMLAllCollection';
      if (prop === Symbol.iterator) return function* () { yield* getNodes(); };
      if (prop === 'item') return markNative(function item(i) { return getNodes()[i >>> 0] || null; });
      if (prop === 'namedItem') {
        return markNative(function namedItem(name) {
          return getNodes().find((el) => el.id === name || el.getAttribute('name') === name) || null;
        });
      }
      if (typeof prop === 'string') {
        const idx = Number(prop);
        if (Number.isInteger(idx) && idx >= 0 && String(idx) === prop) return nodes[idx];
      }
      return undefined;
    },
    has(_t, prop) {
      if (typeof prop === 'string') {
        const idx = Number(prop);
        if (Number.isInteger(idx) && idx >= 0 && String(idx) === prop) return idx < getNodes().length;
      }
      return prop === 'length' || prop === 'item' || prop === 'namedItem'
        || prop === Symbol.iterator || prop === Symbol.toStringTag;
    },
  });
  Object.setPrototypeOf(und, collectionProto);

  const docProto = (win.Document && win.Document.prototype) || Object.getPrototypeOf(win.document);
  Object.defineProperty(docProto, 'all', {
    get: markNative(function all() {
      syncNonConfigurableIndices(getNodes().length);
      return und;
    }),
    enumerable: true,
    configurable: true,
  });
}
```

### 1.4 `Error.stack` 跨引擎格式对齐与非枚举隐藏（按需启用）

**问题**：在 Node.js（V8）的 `vm` 或 `jsdom` 中配合 Firefox / Camoufox（SpiderMonkey）或 Safari（JavaScriptCore）UA 运行原始 SDK 时，若 SDK 调用 `new Error().stack`（或触发内部异常读取 `err.stack`）并用引擎特定正则提取脚本 URL 与行列号，会遇到三层隐蔽差异：① `vm.Script` 未指定 `filename` 时暴露 `evalmachine.<anonymous>`，且同步执行栈底部会带出 `node:vm` / `node:internal/*` 宿主帧；② V8 默认输出首行 `"Error"` 及 `"    at fn (url:line:col)"` 帧，而 SpiderMonkey 输出无首行且带尾随换行的 `"fn@url:line:col\n"`（JavaScriptCore 无尾随换行），导致内部正则返回 `null` 后紧接着取下标抛 `TypeError`，被 SDK 的 `try/catch` 静默吞掉并写入异常遥测槽位；③ 在 `node:vm` 中引擎自抛异常（如 `TypeError`）只会查找子 Realm 内建 `%Error%` 上的 `prepareStackTrace`（不能把外层 `globalThis.Error` 拷入沙箱代替），且 V8 默认 `Error.stackTraceLimit` 为可枚举属性（暴露在 `Object.keys(Error)` 中），直接赋值 `Error.prepareStackTrace = ...` 同样可枚举（若目标进一步枚举 `Object.getOwnPropertyNames(Error)`，需同步在 `Object.getOwnPropertyNames` 包装层过滤 `'prepareStackTrace'`、`'captureStackTrace'` 与 `'stackTraceLimit'`）：

```javascript
// 1) 加载 SDK 字节时传入真实脚本 HTTPS URL：
//    new vm.Script(sdkSource, { filename: 'https://example.com/path/sdk.js' }).runInContext(ctx);
// 2) jsdom 传 dom.window；裸 node:vm 传 ctx 并提供 vmModule 以取得子 Realm 内建 Error：
function patchErrorStackFormat(win, engine = 'firefox', vmModule = null) {
  if (!win || engine === 'chromium') return;
  const TargetError = (vmModule && vmModule.isContext(win))
    ? vmModule.runInContext('Error', win)
    : win.Error;
  if (!TargetError) return;

  const formatNonV8Stack = (_err, structuredStackTrace) => {
    const lines = structuredStackTrace
      .filter((site) => {
        const file = site.getFileName() || site.getEvalOrigin() || '';
        return !file.startsWith('node:') && !file.startsWith('[eval]')
          && !file.startsWith('/') && !/^[A-Za-z]:[\\/]/.test(file);
      })
      .map((site) => {
        const fn = site.getFunctionName() || site.getMethodName() || '';
        const file = site.getFileName() || site.getEvalOrigin() || '';
        const line = site.getLineNumber() || 0;
        const col = site.getColumnNumber() || 0;
        return `${fn}@${file}:${line}:${col}`;
      });
    const body = lines.join('\n');
    return engine === 'firefox' && body ? `${body}\n` : body;
  };

  if (Object.prototype.hasOwnProperty.call(TargetError, 'stackTraceLimit')) {
    Object.defineProperty(TargetError, 'stackTraceLimit', {
      value: TargetError.stackTraceLimit,
      writable: true,
      enumerable: false,
      configurable: true,
    });
  }
  Object.defineProperty(TargetError, 'prepareStackTrace', {
    value: formatNonV8Stack,
    writable: true,
    enumerable: false,
    configurable: true,
  });
}
```

### 2. navigator.webdriver

**问题**：jsdom 中 `navigator.webdriver` 为 `undefined`，真实浏览器为 `false`（Camoufox 在 C++ 层已处理）。

```javascript
Object.defineProperty(nav, 'webdriver', {
  get: () => false, configurable: true, enumerable: true,
});
```

### 3. navigator.plugins 完整结构模拟

**问题**：jsdom `plugins.length = 0`，且无 `item()`/`namedItem()` 方法。JSVMP 不只检查长度，还会遍历结构和检查 `Symbol.toStringTag`。

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

function buildPluginArray(win) {
  const mimeTypes = mimeData.map((m, i) => {
    const mt = Object.create(null);
    Object.defineProperties(mt, {
      type: { get: markNative(function type() { return m.type; }), enumerable: true },
      description: { get: markNative(function description() { return m.description; }), enumerable: true },
      suffixes: { get: markNative(function suffixes() { return m.suffixes; }), enumerable: true },
      enabledPlugin: { get: markNative(function enabledPlugin() { return plugins[0]; }), enumerable: true },
    });
    mt[Symbol.toStringTag] = 'MimeType';
    return mt;
  });

  const plugins = pluginData.map((p, i) => {
    const plugin = Object.create(null);
    Object.defineProperties(plugin, {
      name: { get: markNative(function name() { return p.name; }), enumerable: true },
      filename: { get: markNative(function filename() { return p.filename; }), enumerable: true },
      description: { get: markNative(function description() { return p.description; }), enumerable: true },
      length: { get: markNative(function length() { return mimeTypes.length; }), enumerable: true },
    });
    mimeTypes.forEach((mt, mi) => { plugin[mi] = mt; });
    plugin.item = markNative(function item(idx) { return mimeTypes[idx] || null; });
    plugin.namedItem = markNative(function namedItem(name) {
      return mimeTypes.find(m => m.type === name) || null;
    });
    plugin[Symbol.toStringTag] = 'Plugin';
    plugin[Symbol.iterator] = markNative(function* () { yield* mimeTypes; });
    return plugin;
  });

  const pluginArray = Object.create(null);
  Object.defineProperty(pluginArray, 'length', {
    get: markNative(function length() { return plugins.length; }),
    enumerable: true,
  });
  plugins.forEach((p, i) => { pluginArray[i] = p; });
  pluginArray.item = markNative(function item(idx) { return plugins[idx] || null; });
  pluginArray.namedItem = markNative(function namedItem(name) {
    return plugins.find(p => p.name === name) || null;
  });
  pluginArray.refresh = markNative(function refresh() {});
  pluginArray[Symbol.toStringTag] = 'PluginArray';
  pluginArray[Symbol.iterator] = markNative(function* () { yield* plugins; });

  Object.defineProperty(nav, 'plugins', {
    get: markNative(function plugins() { return pluginArray; }),
    configurable: true, enumerable: true,
  });

  // mimeTypes
  const mimeTypeArray = Object.create(null);
  Object.defineProperty(mimeTypeArray, 'length', {
    get: markNative(function length() { return mimeTypes.length; }),
    enumerable: true,
  });
  mimeTypes.forEach((m, i) => { mimeTypeArray[i] = m; });
  mimeTypeArray.item = markNative(function item(idx) { return mimeTypes[idx] || null; });
  mimeTypeArray.namedItem = markNative(function namedItem(name) {
    return mimeTypes.find(m => m.type === name) || null;
  });
  mimeTypeArray[Symbol.toStringTag] = 'MimeTypeArray';
  mimeTypeArray[Symbol.iterator] = markNative(function* () { yield* mimeTypes; });

  Object.defineProperty(nav, 'mimeTypes', {
    get: markNative(function mimeTypes() { return mimeTypeArray; }),
    configurable: true, enumerable: true,
  });
}
```

### 4. document.hasFocus()

**问题**：jsdom 的 `document.hasFocus()` 始终返回 `false`，真实浏览器活动标签页返回 `true`。

```javascript
doc.hasFocus = markNative(function hasFocus() { return true; });
```

### 5. DOM 布局属性（offsetHeight/Width/getBoundingClientRect）

**问题**：jsdom 无渲染引擎，所有布局属性返回 0。JSVMP 创建不可见元素测量布局值来检测。

```javascript
function patchDOMLayout(win) {
  const HTMLElement = win.HTMLElement;
  if (!HTMLElement) return;

  function parseStyleDimension(el, prop) {
    try {
      const style = el.getAttribute && el.getAttribute('style');
      if (style) {
        const m = style.match(new RegExp(prop + '\\s*:\\s*(\\d+)'));
        if (m) return parseInt(m[1], 10);
      }
    } catch (e) {}
    return 0;
  }

  const layoutProps = ['offsetHeight', 'offsetWidth', 'clientHeight', 'clientWidth',
                       'scrollHeight', 'scrollWidth', 'offsetTop', 'offsetLeft'];
  for (const prop of layoutProps) {
    Object.defineProperty(HTMLElement.prototype, prop, {
      get: markNative(function () {
        const dim = prop.includes('Height') || prop.includes('Top') ? 'height' : 'width';
        const fromStyle = parseStyleDimension(this, dim);
        if (fromStyle > 0) return fromStyle;
        const defaults = { offsetHeight: 150, offsetWidth: 300, clientHeight: 150,
          clientWidth: 300, scrollHeight: 150, scrollWidth: 300, offsetTop: 0, offsetLeft: 0 };
        return defaults[prop] || 0;
      }),
      configurable: true, enumerable: true,
    });
  }

  HTMLElement.prototype.getBoundingClientRect = markNative(function getBoundingClientRect() {
    const w = parseStyleDimension(this, 'width') || 300;
    const h = parseStyleDimension(this, 'height') || 150;
    return { x: 0, y: 0, top: 0, left: 0, right: w, bottom: h, width: w, height: h,
      toJSON: markNative(function toJSON() { return this; }) };
  });

  HTMLElement.prototype.getClientRects = markNative(function getClientRects() {
    return [this.getBoundingClientRect()];
  });
}
```

---

## 常见候选二：对象标签与性能

### 6. Object.prototype.toString 标签（Symbol.toStringTag）

**问题**：jsdom 的 document 原型链是 `Document` 而非 `HTMLDocument`，screen/performance 是普通对象。

```javascript
function patchToStringTags(win, doc, nav) {
  const tagMap = [
    [doc, 'HTMLDocument'],
    [nav, 'Navigator'],
    [win.screen, 'Screen'],
    [win.performance, 'Performance'],
    [win.location, 'Location'],
  ];
  for (const [obj, tag] of tagMap) {
    if (obj) {
      try { obj[Symbol.toStringTag] = tag; } catch (e) {}
    }
  }

  // 修复 document 的原型链构造函数名称
  try {
    const docProto = Object.getPrototypeOf(doc);
    if (docProto && docProto.constructor && docProto.constructor.name !== 'HTMLDocument') {
      Object.defineProperty(docProto.constructor, 'name', { value: 'HTMLDocument' });
    }
  } catch (e) {}
}
```

### 7. window.chrome 对象

**问题**：jsdom 中 `window.chrome` 为 `undefined`，Chrome 浏览器必定存在此对象。

```javascript
function patchChrome(win) {
  win.chrome = {
    app: {
      isInstalled: false,
      InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
      RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
      getDetails: markNative(function getDetails() { return null; }),
      getIsInstalled: markNative(function getIsInstalled() { return false; }),
    },
    runtime: {
      OnInstalledReason: {
        CHROME_UPDATE: 'chrome_update', INSTALL: 'install',
        SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update',
      },
      OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
      PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
      PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
      PlatformOs: { ANDROID: 'android', CROS: 'cros', FUCHSIA: 'fuchsia', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
      RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
      connect: markNative(function connect() { return { onMessage: { addListener: () => {} }, onDisconnect: { addListener: () => {} } }; }),
      sendMessage: markNative(function sendMessage() {}),
      id: undefined,
    },
    csi: markNative(function csi() { return {}; }),
    loadTimes: markNative(function loadTimes() {
      return { commitLoadTime: Date.now() / 1000, connectionInfo: 'h2', finishDocumentLoadTime: 0,
        finishLoadTime: 0, firstPaintAfterLoadTime: 0, firstPaintTime: 0,
        navigationType: 'Other', npnNegotiatedProtocol: 'h2', requestTime: Date.now() / 1000 - 0.5,
        startLoadTime: Date.now() / 1000 - 0.3, wasAlternateProtocolAvailable: false,
        wasFetchedViaSpdy: true, wasNpnNegotiated: true };
    }),
  };
}
```

### 8. navigator.userAgentData

**问题**：jsdom 中不存在 `NavigatorUAData`，Chrome 86+ 浏览器默认提供。

```javascript
function patchUserAgentData(nav, uaBrands) {
  const brands = uaBrands || [
    { brand: 'Chromium', version: '120' },
    { brand: 'Google Chrome', version: '120' },
    { brand: 'Not_A Brand', version: '8' },
  ];
  const uaData = {
    brands: brands,
    mobile: false,
    platform: 'macOS',
    getHighEntropyValues: markNative(function getHighEntropyValues(hints) {
      return Promise.resolve({
        brands, mobile: false, platform: 'macOS',
        architecture: 'arm', bitness: '64', model: '',
        platformVersion: '14.2.0', uaFullVersion: '120.0.0.0',
        fullVersionList: brands.map(b => ({ ...b })),
        wow64: false,
      });
    }),
    toJSON: markNative(function toJSON() { return { brands, mobile: false, platform: 'macOS' }; }),
  };
  uaData[Symbol.toStringTag] = 'NavigatorUAData';
  Object.defineProperty(nav, 'userAgentData', {
    get: markNative(function userAgentData() { return uaData; }),
    configurable: true, enumerable: true,
  });
}
```

### 9. performance.timing / navigation / memory

**问题**：jsdom 中 `performance.timing` 和 `performance.navigation` 为 `undefined`。

```javascript
function patchPerformance(win) {
  const perf = win.performance;
  if (!perf) return;

  const now = Date.now();
  const timing = {
    navigationStart: now - 1200, unloadEventStart: now - 1100, unloadEventEnd: now - 1099,
    redirectStart: 0, redirectEnd: 0, fetchStart: now - 1050,
    domainLookupStart: now - 1000, domainLookupEnd: now - 990,
    connectStart: now - 980, connectEnd: now - 900, secureConnectionStart: now - 950,
    requestStart: now - 890, responseStart: now - 500, responseEnd: now - 400,
    domLoading: now - 380, domInteractive: now - 200, domContentLoadedEventStart: now - 190,
    domContentLoadedEventEnd: now - 185, domComplete: now - 50,
    loadEventStart: now - 40, loadEventEnd: now - 30,
  };
  timing[Symbol.toStringTag] = 'PerformanceTiming';
  Object.defineProperty(perf, 'timing', {
    get: markNative(function timing() { return timing; }),
    configurable: true, enumerable: true,
  });

  const navigation = { type: 0, redirectCount: 0 };
  navigation[Symbol.toStringTag] = 'PerformanceNavigation';
  Object.defineProperty(perf, 'navigation', {
    get: markNative(function navigation() { return navigation; }),
    configurable: true, enumerable: true,
  });

  const memory = { jsHeapSizeLimit: 4294705152, totalJSHeapSize: 35194260, usedJSHeapSize: 24486084 };
  Object.defineProperty(perf, 'memory', {
    get: markNative(function memory() { return memory; }),
    configurable: true, enumerable: true,
  });
}
```

### 10. navigator 基础属性覆盖

```javascript
function patchNavigatorBasics(nav, options) {
  const overrides = {
    platform: options.platform || 'MacIntel',
    language: options.language || 'zh-CN',
    languages: options.languages || ['zh-CN', 'zh'],
    vendor: options.vendor || 'Google Inc.',
    productSub: '20030107',
    appVersion: options.appVersion || '5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    hardwareConcurrency: options.hardwareConcurrency || 8,
    maxTouchPoints: options.maxTouchPoints || 0,
    deviceMemory: options.deviceMemory || 8,
    pdfViewerEnabled: true,
    cookieEnabled: true,
    onLine: true,
    doNotTrack: null,
  };
  for (const [key, value] of Object.entries(overrides)) {
    try {
      Object.defineProperty(nav, key, {
        get: markNative(function () { return value; }),
        configurable: true, enumerable: true,
      });
    } catch (e) {}
  }
}
```

### 11. document 属性补丁

> 注：若目标统计 `Object.getOwnPropertyNames(document)`（见 [1.2 形状对齐](#12-实例自有属性与原型链描述符形状对齐按需启用)），应将下方属性与 `hasFocus`/`fonts` 等定义在 `Object.getPrototypeOf(doc)`（`Document.prototype`）上而非 `doc` 实例上。

```javascript
function patchDocument(doc) {
  Object.defineProperty(doc, 'hidden', {
    get: markNative(function hidden() { return false; }),
    configurable: true, enumerable: true,
  });
  Object.defineProperty(doc, 'visibilityState', {
    get: markNative(function visibilityState() { return 'visible'; }),
    configurable: true, enumerable: true,
  });
  // readyState 在 jsdom 中默认为 'loading'，JSVMP 运行时应为 'complete'
  Object.defineProperty(doc, 'readyState', {
    get: markNative(function readyState() { return 'complete'; }),
    configurable: true, enumerable: true,
  });
  Object.defineProperty(doc, 'fullscreenEnabled', {
    get: markNative(function fullscreenEnabled() { return true; }),
    configurable: true, enumerable: true,
  });
}
```

### 12. screen 对象重建

**问题**：jsdom 的 screen 是普通对象，缺少 `orientation`、`availLeft`/`availTop`，且 `colorDepth` 可能不正确。

```javascript
function patchScreen(win, options) {
  const screenData = {
    width: options.width || 1920, height: options.height || 1080,
    availWidth: options.availWidth || 1920, availHeight: options.availHeight || 1055,
    availLeft: 0, availTop: 25,
    colorDepth: options.colorDepth || 30, pixelDepth: options.pixelDepth || 30,
    orientation: {
      type: 'landscape-primary', angle: 0,
      onchange: null,
      [Symbol.toStringTag]: 'ScreenOrientation',
    },
  };
  screenData[Symbol.toStringTag] = 'Screen';

  for (const [key, value] of Object.entries(screenData)) {
    try {
      Object.defineProperty(win.screen, key, {
        get: markNative(function () { return value; }),
        configurable: true, enumerable: true,
      });
    } catch (e) {}
  }
}
```

---

## 常见候选三：API 存在性

JSVMP 可能通过 `typeof window.XXX` 检测 API 是否存在。以下是 jsdom 缺失但浏览器存在的 API 存根。

**核心原则**：每个存根函数必须经过 `markNative()` 处理，否则 `toString()` 检测会暴露。

### 13. 批量 API 存根

```javascript
function patchWindowAPIs(win) {
  // Notification
  if (!win.Notification) {
    win.Notification = markNative(function Notification() {});
    win.Notification.permission = 'default';
    win.Notification.requestPermission = markNative(function requestPermission() {
      return Promise.resolve('default');
    });
    win.Notification.maxActions = 2;
  }

  // Worker / SharedWorker
  if (!win.Worker) {
    win.Worker = markNative(function Worker() {
      return { postMessage: markNative(function() {}), terminate: markNative(function() {}),
        addEventListener: markNative(function() {}), onmessage: null, onerror: null };
    });
  }
  if (!win.SharedWorker) {
    win.SharedWorker = markNative(function SharedWorker() {
      return { port: { postMessage: markNative(function() {}), start: markNative(function() {}),
        addEventListener: markNative(function() {}), onmessage: null } };
    });
  }

  // RTCPeerConnection
  if (!win.RTCPeerConnection) {
    win.RTCPeerConnection = markNative(function RTCPeerConnection() {
      return { createDataChannel: markNative(function() { return {}; }),
        createOffer: markNative(function() { return Promise.resolve({}); }),
        setLocalDescription: markNative(function() { return Promise.resolve(); }),
        close: markNative(function() {}), onicecandidate: null };
    });
  }

  // AudioContext / OfflineAudioContext
  if (!win.AudioContext) {
    win.AudioContext = markNative(function AudioContext() {
      return { sampleRate: 44100, state: 'suspended', currentTime: 0, destination: {},
        createOscillator: markNative(function() {
          return { type: 'sine', frequency: { value: 440 },
            connect: markNative(function() {}), start: markNative(function() {}),
            stop: markNative(function() {}) };
        }),
        createDynamicsCompressor: markNative(function() {
          return { threshold: { value: -24 }, knee: { value: 30 },
            ratio: { value: 12 }, reduction: 0,
            connect: markNative(function() {}) };
        }),
        createAnalyser: markNative(function() { return { connect: markNative(function() {}) }; }),
        createGain: markNative(function() { return { gain: { value: 1 }, connect: markNative(function() {}) }; }),
        close: markNative(function() { return Promise.resolve(); }),
        resume: markNative(function() { return Promise.resolve(); }) };
    });
  }
  if (!win.OfflineAudioContext) {
    win.OfflineAudioContext = markNative(function OfflineAudioContext(channels, length, sampleRate) {
      const ctx = new win.AudioContext();
      ctx.startRendering = markNative(function startRendering() {
        return Promise.resolve({ duration: length / sampleRate, length: length,
          numberOfChannels: channels, sampleRate: sampleRate,
          getChannelData: markNative(function() { return new Float32Array(length); }) });
      });
      return ctx;
    });
  }

  // fetch + Request/Response/Headers/AbortController
  if (!win.fetch) {
    win.fetch = markNative(function fetch() { return Promise.reject(new Error('Network error')); });
    win.Request = markNative(function Request() {});
    win.Response = markNative(function Response() {});
    if (!win.AbortController) {
      win.AbortController = markNative(function AbortController() {
        return { signal: { aborted: false }, abort: markNative(function() {}) };
      });
    }
  }

  // matchMedia
  if (!win.matchMedia) {
    win.matchMedia = markNative(function matchMedia(query) {
      return { matches: false, media: query, onchange: null,
        addListener: markNative(function() {}), removeListener: markNative(function() {}),
        addEventListener: markNative(function() {}), removeEventListener: markNative(function() {}) };
    });
  }

  // requestIdleCallback / cancelIdleCallback
  if (!win.requestIdleCallback) {
    win.requestIdleCallback = markNative(function requestIdleCallback(cb) {
      return win.setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 50 }), 1);
    });
    win.cancelIdleCallback = markNative(function cancelIdleCallback(id) { win.clearTimeout(id); });
  }

  // requestAnimationFrame（jsdom pretendToBeVisual=true 已提供，但检查一下）
  if (!win.requestAnimationFrame) {
    win.requestAnimationFrame = markNative(function requestAnimationFrame(cb) {
      return win.setTimeout(() => cb(Date.now()), 16);
    });
    win.cancelAnimationFrame = markNative(function cancelAnimationFrame(id) { win.clearTimeout(id); });
  }

  // indexedDB
  if (!win.indexedDB) {
    win.indexedDB = { open: markNative(function open() { return {}; }) };
    win.indexedDB[Symbol.toStringTag] = 'IDBFactory';
  }

  // caches
  if (!win.caches) {
    win.caches = {
      open: markNative(function open() { return Promise.resolve({}); }),
      has: markNative(function has() { return Promise.resolve(false); }),
      delete: markNative(function _delete() { return Promise.resolve(false); }),
      keys: markNative(function keys() { return Promise.resolve([]); }),
      match: markNative(function match() { return Promise.resolve(undefined); }),
    };
    win.caches[Symbol.toStringTag] = 'CacheStorage';
  }

  // speechSynthesis
  if (!win.speechSynthesis) {
    win.speechSynthesis = {
      speaking: false, pending: false, paused: false,
      getVoices: markNative(function getVoices() { return []; }),
      speak: markNative(function speak() {}),
      cancel: markNative(function cancel() {}),
    };
    win.speechSynthesis[Symbol.toStringTag] = 'SpeechSynthesis';
  }

  // customElements
  if (!win.customElements) {
    win.customElements = {
      define: markNative(function define() {}),
      get: markNative(function get() { return undefined; }),
      whenDefined: markNative(function whenDefined() { return Promise.resolve(); }),
    };
    win.customElements[Symbol.toStringTag] = 'CustomElementRegistry';
  }

  // visualViewport
  if (!win.visualViewport) {
    win.visualViewport = {
      width: win.innerWidth || 1920, height: win.innerHeight || 1080,
      offsetLeft: 0, offsetTop: 0, pageLeft: 0, pageTop: 0, scale: 1,
      onresize: null, onscroll: null,
      addEventListener: markNative(function() {}), removeEventListener: markNative(function() {}),
    };
    win.visualViewport[Symbol.toStringTag] = 'VisualViewport';
  }

  // isSecureContext
  if (win.isSecureContext === undefined) {
    Object.defineProperty(win, 'isSecureContext', {
      get: markNative(function isSecureContext() { return true; }),
      configurable: true, enumerable: true,
    });
  }

  // clientInformation
  if (!win.clientInformation) {
    Object.defineProperty(win, 'clientInformation', {
      get: markNative(function clientInformation() { return nav; }),
      configurable: true, enumerable: true,
    });
  }
}
```

### 14. navigator 扩展 API 存根

```javascript
function patchNavigatorAPIs(nav) {
  // connection (NetworkInformation)
  if (!nav.connection) {
    const conn = {
      effectiveType: '4g', downlink: 10, rtt: 50, saveData: false,
      onchange: null, type: 'wifi',
      addEventListener: markNative(function() {}), removeEventListener: markNative(function() {}),
    };
    conn[Symbol.toStringTag] = 'NetworkInformation';
    Object.defineProperty(nav, 'connection', {
      get: markNative(function connection() { return conn; }),
      configurable: true, enumerable: true,
    });
  }

  // getBattery
  if (!nav.getBattery) {
    nav.getBattery = markNative(function getBattery() {
      return Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1,
        onchargingchange: null, onchargingtimechange: null,
        ondischargingtimechange: null, onlevelchange: null,
      });
    });
  }
}
```

### 15. document 扩展 API 存根

```javascript
function patchDocumentAPIs(doc) {
  // fonts (FontFaceSet)
  if (!doc.fonts) {
    const fonts = {
      ready: Promise.resolve(),
      status: 'loaded',
      check: markNative(function check() { return true; }),
      load: markNative(function load() { return Promise.resolve([]); }),
      forEach: markNative(function forEach() {}),
      entries: markNative(function entries() { return [][Symbol.iterator](); }),
      keys: markNative(function keys() { return [][Symbol.iterator](); }),
      values: markNative(function values() { return [][Symbol.iterator](); }),
      [Symbol.iterator]: markNative(function () { return [][Symbol.iterator](); }),
      size: 0,
    };
    fonts[Symbol.toStringTag] = 'FontFaceSet';
    Object.defineProperty(doc, 'fonts', {
      get: markNative(function fonts() { return fonts; }),
      configurable: true, enumerable: true,
    });
  }

  // timeline (DocumentTimeline)
  if (!doc.timeline) {
    const timeline = { currentTime: win.performance?.now?.() || 0 };
    timeline[Symbol.toStringTag] = 'DocumentTimeline';
    Object.defineProperty(doc, 'timeline', {
      get: markNative(function timeline() { return timeline; }),
      configurable: true, enumerable: true,
    });
  }
}
```

---

## window 尺寸属性

```javascript
function patchWindowDimensions(win, options) {
  const dims = {
    innerWidth: options.innerWidth || 1920,
    innerHeight: options.innerHeight || 969,
    outerWidth: options.outerWidth || 1920,
    outerHeight: options.outerHeight || 1055,
    devicePixelRatio: options.devicePixelRatio || 2,
    scrollX: 0, scrollY: 0, pageXOffset: 0, pageYOffset: 0,
  };
  for (const [key, value] of Object.entries(dims)) {
    try {
      Object.defineProperty(win, key, {
        get: markNative(function () { return value; }),
        configurable: true, enumerable: true,
      });
    } catch (e) {}
  }
}
```

---

## Node.js 特征清除

在 jsdom 的 window 上下文中隐藏 Node.js 运行时特征：

```javascript
function hideNodeFeatures(win) {
  const nodeGlobals = ['process', 'module', 'exports', 'require',
    'global', '__filename', '__dirname', 'Buffer'];
  for (const g of nodeGlobals) {
    try { delete win[g]; } catch (e) {
      try { win[g] = undefined; } catch (e2) {}
    }
  }
}
```

---

## 完整 patchEnvironment 调用顺序

**顺序很重要**：markNative 必须在所有补丁之前定义，所有补丁函数必须经过 markNative 处理。

```javascript
function patchEnvironment(win, doc, nav, options = {}) {
  // ① 定义 markNative（三层防御）— 必须最先
  setupMarkNative(win);

  // ② 扫描并标记所有 jsdom 内置原型链方法
  scanAllPrototypes(win, doc, nav);

  // ③ 候选一
  patchNavigatorBasics(nav, options);       // webdriver / platform / language
  buildPluginArray(win);                     // plugins 完整结构
  doc.hasFocus = markNative(function hasFocus() { return true; });
  patchDOMLayout(win);                       // offsetHeight/Width/getBoundingClientRect

  // ④ 候选二
  patchToStringTags(win, doc, nav);          // Symbol.toStringTag
  patchChrome(win);                          // window.chrome
  patchUserAgentData(nav);                   // userAgentData
  patchPerformance(win);                     // timing/navigation/memory
  patchDocument(doc);                        // hasFocus/readyState/visibility
  patchScreen(win, options);                 // colorDepth/orientation
  patchWindowDimensions(win, options);        // innerWidth/outerWidth/devicePixelRatio

  // ⑤ 候选三
  patchWindowAPIs(win);                      // 30+ API 存根
  patchNavigatorAPIs(nav);                   // connection/getBattery
  patchDocumentAPIs(doc);                    // fonts/timeline

  // ⑥ 清除 Node.js 特征
  hideNodeFeatures(win);

  // ⑦ 最后一次全局扫描，标记新增的所有函数
  scanAllPrototypes(win, doc, nav);

  // ⑧ 按读值证据可选启用专项补丁（默认不全开）：
  // - 若目标创建 iframe 检测子窗口构造器/DOM 方法源码：在 ② 之后调 patchIframeChildRealms(win, helpers)
  // - 若目标检测 document/navigator 自有属性数量：补丁直接挂原型，或在 ⑤ 之后调 alignOwnAndProtoShape(...)
  // - 若目标实读 document.all 活性：以 node --allow-natives-syntax 启动并调 patchDocumentAll(...)
  // - 若基线为 Firefox/Safari UA 且目标用正则解析 Error().stack：指定 vm.Script filename 并调 patchErrorStackFormat(win, 'firefox', vm)
  // - 画布/WebGL 返回值先核对基线浏览器实测输出（含抗指纹全零摘要），勿盲目换入第三方原生渲染库
}
```

---

## 环境采集对比方法

### 浏览器端采集（通过 Camoufox MCP）

分 4 批次通过 `evaluate_js` 在真实浏览器中执行采集脚本，
采集代码模板参考 `cases/` 中的「浏览器指纹采集方法」段。

### jsdom 端采集

在 Node.js 中用 `win.eval()` 执行完全相同的采集代码：

```javascript
const dom = createPatchedJsdom('https://target.com');
const win = dom.window;
const jsdomResult = JSON.parse(win.eval(`JSON.stringify({
  nav_userAgent: navigator.userAgent,
  nav_plugins_length: navigator.plugins ? navigator.plugins.length : -1,
  nav_webdriver: navigator.webdriver,
  // ... 与浏览器端完全相同的采集代码
})`));
```

### Diff 生成

```javascript
function diffEnv(browserData, jsdomData) {
  const diffs = [];
  for (const key of Object.keys(browserData)) {
    const bVal = JSON.stringify(browserData[key]);
    const jVal = JSON.stringify(jsdomData[key]);
    if (bVal !== jVal) {
      diffs.push({ key, browser: browserData[key], jsdom: jsdomData[key] });
    }
  }
  return diffs;
}
```

---

## MCP 辅助工作流

```
1. compare_env → 快速采集浏览器基准环境数据（覆盖主流检测项）
   → 适合快速判断差异范围

2. evaluate_js → 分批采集细粒度环境值（4-5 批次）
   → 覆盖 Function.toString / Symbol.toStringTag / DOM 布局等 compare_env 不包含的项
   → 每批代码不要太长，避免执行超时

3. 本地 Node.js 脚本 → 在 jsdom 中运行相同采集代码 + 生成 diff 报告

4. 迭代修复 → 每次修复一批差异 → 重新 diff → 直到差异归零

5. 端到端验证 → jsdom 生成签名 → 真实接口请求 → 确认数据有效
```
