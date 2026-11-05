# 协议层分析与对抗

## 概述

有些网站不仅在 JS 层面做加密保护，还在协议层面进行检测（TLS 指纹、HTTP/2 强制等）。
但“本地失败、浏览器成功”不等于传输层问题。一次性值已用过、会话到期、请求形态差异都表现得一模一样，而且更常见、更便宜排除。

## 传输层诊断实验

先按 [问题路由](problem-routing.md#链路-c浏览器能过本地同样的头不过) 排除动态值、会话和请求形态，再做这组对照：

| 组 | 发送通道 | 动态值 | 其余字段 |
|---|---|---|---|
| T0 | 干净页面通道（新 iframe 的原生 fetch） | 未使用的值 | 同一模板 |
| T1 | TLS 模拟客户端 | 新的未使用的值 | 同一模板 |
| T2 | 普通 HTTP 客户端 | 新的未使用的值 | 同一模板 |
| T3 | 上面成功的客户端，换代理或直连 | 新的未使用的值 | 同一模板 |
| T4 | 干净页面通道 | 本地值（反向对照） | 同一模板 |

T1 成功而 T4 失败，问题在值；T1 失败而 T4 成功，问题在传输；都失败时可能两道闸门都没过，判读见 [交叉矩阵](controlled-experiments.md#单变量没有翻转时)。

- 每组都用新的未使用值，否则测到的是复用，不是传输。
- 用生产实际使用的客户端做实验。两个恰好都能过的客户端对这道门没有分辨力。
- 只有分界稳定地落在某个通道上，才能写传输结论，单次失败不算。
- UA 声明版本与 TLS 模拟版本不一致也可能成功，版本不匹配不能单独当原因，要用实验确认。
- 新通道调用超时是传输现象，不是拒绝。辅助函数有重试时尝试次数未知，要记录下来。
- 取值方法见 [签名来源隔离](signature-source-isolation.md)。

### 比较实际发出的传输特征

- 用回显服务读回客户端实际发出的特征，优先自建（如 [pingly](https://github.com/0x676e67/pingly)、[fingerproxy](https://github.com/wi1dcard/fingerproxy)）。带登录态的请求不要发给第三方回显服务。
- 比较项：TLS 版本、套件、扩展及顺序、组、key_share、签名算法、ALPN、ECH；HTTP/2 的 SETTINGS、WINDOW_UPDATE、PRIORITY、伪头顺序；HTTP 头顺序。
- 先做 [A/A 和阳性对照](controlled-experiments.md#测量手段先过对照)。部分浏览器会重排扩展，比较前排序或折叠。
- 指纹串一致不等于字节一致，最后手段是抓包比较。
- 不要自造随机指纹，真实浏览器的指纹是固定组合。

## 1. TLS 指纹检测

### 原理

服务器通过分析 TLS Client Hello 报文中的特征来识别客户端类型：
- Cipher Suites 列表和顺序
- TLS 扩展列表和顺序
- 支持的曲线（Elliptic Curves）
- 签名算法
- ALPN 协议列表

不同客户端（Chrome、Firefox、curl、Node.js）的 TLS 指纹不同。

### 检测表现

下面这些现象都不是 TLS 的专属特征，要靠上面的对照确认：

- 请求返回 `403 Forbidden`
- 返回空响应或错误页面
- 返回 `token failed`、`access denied` 等自定义错误
- 同样的参数在浏览器中正常，在 Node.js 中失败

### 解决方案

#### 方案 A：在浏览器内发送

```javascript
// 使用 camoufox-reverse MCP 在 Camoufox 浏览器环境中执行请求
// [camoufox-reverse] evaluate_js
const response = await fetch('https://target.com/api/data', {
    method: 'GET',
    headers: { 'Cookie': cookieValue },
    credentials: 'include'
});
const data = await response.json();
```

```
MCP 操作：
[camoufox-reverse] launch_browser()
[camoufox-reverse] navigate(url="https://target.com")
[camoufox-reverse] evaluate_js(expression="fetch(url, options).then(r=>r.json()).then(d=>JSON.stringify(d))")
```

#### 方案 B：curl-impersonate（活跃实现见 [lexiforest/curl-impersonate](https://github.com/lexiforest/curl-impersonate) 或 curl_cffi，版本以当前发布为准）

```bash
# 使用 curl-impersonate 模拟 Chrome 的 TLS 指纹
curl_chrome116 https://target.com/api/data \
    -H "Cookie: session=xxx" \
    -H "User-Agent: Mozilla/5.0 ..."
```

Node.js 中通过子进程调用：
```javascript
const { execSync } = require('child_process');

function fetchWithChromeTLS(url, headers = {}) {
    const headerArgs = Object.entries(headers)
        .map(([k, v]) => `-H "${k}: ${v}"`)
        .join(' ');
    const result = execSync(`curl_chrome116 "${url}" ${headerArgs} -s`, {
        encoding: 'utf-8',
        timeout: 30000,
    });
    return JSON.parse(result);
}
```

#### 方案 C：自定义 TLS（高级）

使用支持自定义 TLS 指纹的库（如 `tls-client` 的 Node.js 绑定）。

## 2. HTTP/2 协议

### 检测表现

- HTTP/1.1 请求返回错误
- HTTP/2 请求正常返回数据
- 抓包可以看到服务器仅接受 h2 连接

### Node.js HTTP/2 请求

```javascript
const http2 = require('http2');

function http2Request(url, options = {}) {
    return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const client = http2.connect(`${urlObj.protocol}//${urlObj.host}`);
        
        client.on('error', reject);
        
        const headers = {
            ':method': options.method || 'GET',
            ':path': urlObj.pathname + urlObj.search,
            ':scheme': urlObj.protocol.replace(':', ''),
            ':authority': urlObj.host,
            'user-agent': options.userAgent || 'Mozilla/5.0 ...',
            'accept': 'application/json',
            ...options.headers,
        };
        
        if (options.cookie) {
            headers['cookie'] = options.cookie;
        }
        
        const req = client.request(headers);
        
        let data = '';
        req.on('data', (chunk) => { data += chunk; });
        req.on('end', () => {
            client.close();
            resolve(data);
        });
        req.on('error', reject);
        
        if (options.body) {
            req.write(options.body);
        }
        req.end();
    });
}

// 使用示例
async function main() {
    const data = await http2Request('https://target.com/api/data?page=1', {
        headers: {
            'cookie': 'm=xxx; sessionid=yyy',
            'referer': 'https://target.com/',
        }
    });
    console.log(JSON.parse(data));
}
```

## 3. User-Agent 校验

### 常见场景

- 某些页面要求特定 UA
- 不同 UA 返回不同内容
- 空 UA 或非浏览器 UA 被拒绝

### Node.js 设置

```javascript
const axios = require('axios');

const client = axios.create({
    headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
});
```

### MCP 侧验证

```
[camoufox-reverse] launch_browser(os_type="macos")
[camoufox-reverse] compare_env
→ 验证当前浏览器环境中的 UA、平台和指纹是否与目标站点要求一致
```

## 4. Referer 校验

### 常见场景

- API 接口检查 Referer 头
- 必须来自特定页面的请求
- 缺少 Referer 返回 403

### 解决方案

```javascript
headers: {
    'Referer': 'https://target.com/page',
    'Origin': 'https://target.com',
}
```

## 5. CORS 与跨域

### 预检请求 (Preflight)

```javascript
// 某些请求会先发 OPTIONS 预检
// 确保模拟请求时也处理 CORS 相关头
headers: {
    'Origin': 'https://target.com',
    'Access-Control-Request-Method': 'POST',
    'Access-Control-Request-Headers': 'content-type',
}
```

## 6. 请求频率限制

### 常见策略

- IP 维度限流
- Cookie/Session 维度限流
- 请求间隔检测
- 滑动窗口计数

### 对抗方式

```javascript
// 请求间隔控制
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWithRateLimit(urls, delayMs = 1000) {
    const results = [];
    for (const url of urls) {
        const data = await fetch(url);
        results.push(data);
        await sleep(delayMs + Math.random() * 500); // 随机化延迟
    }
    return results;
}
```

## 7. IP 封禁对抗

### 代理轮换

```javascript
const HttpsProxyAgent = require('https-proxy-agent');

const proxies = [
    'http://proxy1:port',
    'http://proxy2:port',
];

function getRandomProxy() {
    return proxies[Math.floor(Math.random() * proxies.length)];
}

async function fetchWithProxy(url, options = {}) {
    const agent = new HttpsProxyAgent(getRandomProxy());
    return fetch(url, { ...options, agent });
}
```

## 诊断流程

状态码只给出候选方向，不定层：

| 现象 | 候选方向 | 下一步 |
|---|---|---|
| 403 | 会话、请求形态、动态值、传输、IP | 链路 B 或 C |
| 412 | 前置条件、挑战、动态值 | 链路 B，首屏场景看响应链 |
| 429 | 频率限制 | 降频，看 `retry-after` |
| 200 但数据异常 | 业务错误、参数、权限、软拒绝 | 读业务码，链路 B |
| 超时、连接错误 | 网络、代理、证书 | 单独分类，不算拒绝 |

本地失败而浏览器成功时，按 [链路 C](problem-routing.md#链路-c浏览器能过本地同样的头不过) 的顺序走，不要直接切到浏览器方案。需要 HTTP/2 时用对照确认：同一未使用的值，HTTP/1.1 失败而 HTTP/2 成功才算证据。
