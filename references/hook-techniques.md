# JS Hook 技术大全

## 概述

Hook 是 JS 逆向中最核心的技术之一。通过劫持/拦截 JS 原生函数或对象属性，可以捕获加密函数的
输入输出、Cookie 的生成过程、网络请求的参数构造等关键信息。

## 注入方式

### 通过 MCP 注入（推荐）

```
[js-reverse] inject_before_load(script=HookScript)
→ 在页面脚本加载前注入，确保 Hook 在目标代码之前生效

[js-reverse] evaluate_script(function=HookScript)
→ 在当前页面上下文执行，适合页面已加载后的动态注入
```

### 通过浏览器控制台注入

在 chrome-devtools MCP 中使用：
```
[chrome-devtools] evaluate_script(function=HookScript)
```

## Hook 模板库

### 1. Cookie Setter Hook

**用途**：监控所有 Cookie 写入操作，定位动态 Cookie 生成逻辑

```javascript
(function() {
    let cookieTemp = '';
    Object.defineProperty(document, 'cookie', {
        set: function(val) {
            console.log('[Hook] Cookie Set:', val);
            if (val.indexOf('目标cookie名') !== -1) {
                console.log('[Hook] ★ 目标Cookie捕获:', val);
                console.trace('[Hook] Cookie 调用栈');
            }
            cookieTemp = val;
            return val;
        },
        get: function() {
            return cookieTemp;
        }
    });
})();
```

### 2. XHR Hook

**用途**：拦截所有 XMLHttpRequest 请求，捕获完整请求参数

```javascript
(function() {
    const _open = XMLHttpRequest.prototype.open;
    const _send = XMLHttpRequest.prototype.send;
    const _setHeader = XMLHttpRequest.prototype.setRequestHeader;
    
    XMLHttpRequest.prototype.open = function(method, url) {
        this._hookMethod = method;
        this._hookUrl = url;
        this._hookHeaders = {};
        console.log('[Hook] XHR Open:', method, url);
        return _open.apply(this, arguments);
    };
    
    XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
        this._hookHeaders[name] = value;
        return _setHeader.apply(this, arguments);
    };
    
    XMLHttpRequest.prototype.send = function(body) {
        console.log('[Hook] XHR Send:', {
            method: this._hookMethod,
            url: this._hookUrl,
            headers: this._hookHeaders,
            body: body
        });
        if (this._hookUrl.indexOf('目标接口') !== -1) {
            console.log('[Hook] ★ 目标请求捕获');
            console.trace('[Hook] 请求调用栈');
        }
        return _send.apply(this, arguments);
    };
})();
```

### 3. Fetch Hook

**用途**：拦截 fetch API 请求

```javascript
(function() {
    const _fetch = window.fetch;
    window.fetch = function(url, options) {
        console.log('[Hook] Fetch:', url, options);
        if (typeof url === 'string' && url.indexOf('目标接口') !== -1) {
            console.log('[Hook] ★ 目标Fetch捕获');
            console.trace('[Hook] Fetch 调用栈');
        }
        return _fetch.apply(this, arguments);
    };
})();
```

### 4. $.ajax Hook（jQuery 场景）

**用途**：拦截 jQuery AJAX 请求，捕获加密参数

```javascript
(function() {
    if (typeof $ === 'undefined' || typeof $.ajax === 'undefined') return;
    
    const _ajax = $.ajax;
    $.ajax = function(options) {
        if (typeof options === 'object') {
            console.log('[Hook] $.ajax:', {
                url: options.url,
                method: options.type || options.method,
                data: options.data,
                headers: options.headers
            });
            
            if (options.url && options.url.indexOf('目标接口') !== -1) {
                console.log('[Hook] ★ 目标Ajax捕获');
                if (options.data && options.data.m) {
                    console.log('[Hook] 加密参数 m:', options.data.m);
                }
            }
        }
        return _ajax.apply(this, arguments);
    };
    
    // 同时 Hook ajaxSetup
    if ($.ajaxSetup) {
        const _setup = $.ajaxSetup;
        $.ajaxSetup = function(options) {
            console.log('[Hook] $.ajaxSetup:', options);
            return _setup.apply(this, arguments);
        };
    }
})();
```

### 5. eval / Function Hook

**用途**：捕获动态生成和执行的代码

```javascript
(function() {
    // eval Hook
    const _eval = window.eval;
    window.eval = function(code) {
        console.log('[Hook] eval 调用, 代码长度:', (typeof code === 'string') ? code.length : 'N/A');
        if (typeof code === 'string' && code.length < 5000) {
            console.log('[Hook] eval 代码:', code.substring(0, 500));
        }
        return _eval.apply(this, arguments);
    };
    
    // Function 构造器 Hook
    const _Function = Function;
    const handler = {
        construct(target, args) {
            const body = args[args.length - 1];
            console.log('[Hook] new Function, body 长度:', body ? body.length : 0);
            if (body && body.indexOf('目标关键词') !== -1) {
                console.log('[Hook] ★ 目标 Function 捕获:', body.substring(0, 500));
            }
            return new target(...args);
        },
        apply(target, thisArg, args) {
            const body = args[args.length - 1];
            console.log('[Hook] Function(), body 长度:', body ? body.length : 0);
            return target.apply(thisArg, args);
        }
    };
    window.Function = new Proxy(_Function, handler);
})();
```

### 6. JSON.parse Hook

**用途**：捕获 JSON 解析操作，常用于响应数据解密场景

```javascript
(function() {
    const _parse = JSON.parse;
    JSON.parse = function(text) {
        const result = _parse.apply(this, arguments);
        console.log('[Hook] JSON.parse:', typeof text === 'string' ? text.substring(0, 200) : text);
        return result;
    };
})();
```

### 7. JSON.stringify Hook

**用途**：捕获 JSON 序列化操作，常在签名前执行

```javascript
(function() {
    const _stringify = JSON.stringify;
    JSON.stringify = function(obj) {
        const result = _stringify.apply(this, arguments);
        console.log('[Hook] JSON.stringify:', result ? result.substring(0, 200) : result);
        return result;
    };
})();
```

### 8. atob / btoa Hook

**用途**：捕获 Base64 编解码操作

```javascript
(function() {
    const _atob = window.atob;
    const _btoa = window.btoa;
    
    window.atob = function(str) {
        const result = _atob(str);
        console.log('[Hook] atob:', str.substring(0, 100), '→', result.substring(0, 100));
        return result;
    };
    
    window.btoa = function(str) {
        const result = _btoa(str);
        console.log('[Hook] btoa:', str.substring(0, 100), '→', result.substring(0, 100));
        return result;
    };
})();
```

### 9. setTimeout / setInterval Hook

**用途**：监控定时器调用，识别反调试和周期性操作

```javascript
(function() {
    const _setTimeout = window.setTimeout;
    const _setInterval = window.setInterval;
    
    window.setTimeout = function(fn, delay) {
        const fnStr = typeof fn === 'function' ? fn.toString().substring(0, 200) : String(fn).substring(0, 200);
        // 过滤 debugger 反调试
        if (fnStr.indexOf('debugger') !== -1) {
            console.log('[Hook] setTimeout 拦截 debugger，已跳过');
            return -1;
        }
        return _setTimeout.apply(this, arguments);
    };
    
    window.setInterval = function(fn, delay) {
        const fnStr = typeof fn === 'function' ? fn.toString().substring(0, 200) : String(fn).substring(0, 200);
        if (fnStr.indexOf('debugger') !== -1) {
            console.log('[Hook] setInterval 拦截 debugger，已跳过');
            return -1;
        }
        return _setInterval.apply(this, arguments);
    };
})();
```

### 10. WebSocket Hook

**用途**：拦截 WebSocket 消息

```javascript
(function() {
    const _WebSocket = window.WebSocket;
    window.WebSocket = function(url, protocols) {
        console.log('[Hook] WebSocket 连接:', url);
        const ws = new _WebSocket(url, protocols);
        
        const _send = ws.send.bind(ws);
        ws.send = function(data) {
            console.log('[Hook] WS 发送:', data);
            return _send(data);
        };
        
        ws.addEventListener('message', function(event) {
            console.log('[Hook] WS 接收:', event.data);
        });
        
        return ws;
    };
    window.WebSocket.prototype = _WebSocket.prototype;
})();
```

### 11. window 属性访问 Hook（蜜罐检测）

**用途**：监控对 window 属性的访问，识别蜜罐检测

```javascript
(function() {
    const handler = {
        get(target, prop, receiver) {
            if (['__selenium', '__webdriver_script_fn', '__driver_evaluate',
                 '$cdc_asdjflasutopfhvcZLmcfl_', 'callPhantom', '_phantom'].includes(prop)) {
                console.log('[Hook] ★ 蜜罐属性访问:', prop);
                return undefined;
            }
            return Reflect.get(target, prop, receiver);
        }
    };
    // 注意：直接代理 window 风险较大，仅在需要时使用
})();
```

### 12. Canvas 指纹 Hook

**用途**：拦截 Canvas 指纹采集

```javascript
(function() {
    const _toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {
        console.log('[Hook] Canvas toDataURL 调用');
        console.trace('[Hook] Canvas 调用栈');
        return _toDataURL.apply(this, arguments);
    };
    
    const _toBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function() {
        console.log('[Hook] Canvas toBlob 调用');
        return _toBlob.apply(this, arguments);
    };
})();
```

### 13. Navigator 属性 Hook

**用途**：伪装浏览器指纹

```javascript
(function() {
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false
    });
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en']
    });
})();
```

## 组合 Hook 模板

### 通用逆向分析 Hook（一键注入）

```javascript
(function() {
    console.log('[Hook] ========== 通用逆向Hook已注入 ==========');
    
    // 1. Cookie 监控
    let _cookie = document.cookie;
    Object.defineProperty(document, 'cookie', {
        set(v) { console.log('[Cookie] Set:', v); _cookie += '; ' + v; },
        get() { return _cookie; }
    });
    
    // 2. XHR 监控
    const _xhrOpen = XMLHttpRequest.prototype.open;
    const _xhrSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m, u) { this._m = m; this._u = u; return _xhrOpen.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function(b) { console.log('[XHR]', this._m, this._u, b); return _xhrSend.apply(this, arguments); };
    
    // 3. Fetch 监控
    const _fetch = window.fetch;
    window.fetch = function() { console.log('[Fetch]', ...arguments); return _fetch.apply(this, arguments); };
    
    // 4. debugger 拦截
    const _si = window.setInterval;
    window.setInterval = function(fn, d) {
        if (typeof fn === 'function' && fn.toString().indexOf('debugger') > -1) return -1;
        return _si.apply(this, arguments);
    };
    
    console.log('[Hook] ========== Hook注入完成 ==========');
})();
```

## MCP 注入最佳实践

1. **使用 `inject_before_load`**：确保 Hook 在目标代码之前生效
2. **使用 `console.log` 输出**：通过 `list_console_messages` 收集结果
3. **使用 `console.trace`**：在关键点输出调用栈
4. **避免覆写原型链的 toString**：防止被反检测代码发现
5. **使用 Proxy 代替直接覆写**：更隐蔽，不改变 `typeof` 结果
