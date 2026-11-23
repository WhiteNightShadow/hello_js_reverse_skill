# XYS_ 信封 + 双代 JSVMP（mns0201/mns0301）+ 容器格式全解（离线出值）

> 难度：★★★★☆
> 还原方案：[E: jsdom 环境模拟 + 站点实体原样执行（无需浏览器）]
> 实现语言：Python（客户端/组包）+ Node.js（jsdom 内跑站点实体出值）
> 最后验证日期：2026-11-23
> 平台类型：社交内容平台（Web 端 feed 接口）
> 适用范围：`/api/sns/web/v1/homefeed`，站点 `webBuild 6.62.0`、`vendor-dynamic` 哈希 `204431b8`（另一地域变体 `067e338b`）当天有效
> 到达层级：S3 命中目标（多频道实测 200 / `code:0` / 25、36 条真实 items）；S4 未跑跨天
> 失效条件：`x-s` 换表变化、`mns` 实体换代后旧代被拒、`b1` 指纹串规则变化

本案例的结论只对上述范围成立，不是全局规则。

---

## 技术指纹（候选线索）

### JS 特征
- [ ] `seccore_signv2` 函数名（在 `vendor-dynamic.<hash>.js` 里，明文可搜）
- [ ] `window.mnsv2(c, u, p)` 三参调用点；`mns` 结果前缀 `mns0201_` / `mns0301_`
- [ ] 换表 base64：64 项自定义字母表，函数名形如 `b64Encode`/`xE`
- [ ] 混淆实体入口名随机（如 `_AUuXfEG27Xa3x`、`_0c6b9e549fef9ab9b4798ad1f12ea82b`），每次构建不同

### 参数特征
- [ ] `x-s`：`XYS_` + 自定义字母表 base64，解出明文 JSON `{"x0":"4.4.3","x1":"xhs-pc-web","x2":"Windows","x3":<mns token>,"x4":"object","x5":<md5>}`
- [ ] `x-t`：13 位毫秒时间戳
- [ ] `x-s-common`：同一套字母表编码的设备/会话信封 `{s0,s1,x0..x12}`，**必带**（缺了直接 461）
- [ ] `x5 = md5hex(path + json_body)`（对象要 `JSON.stringify`，字符串直接拼）

### 请求特征
- [ ] 静态资源与安全 SDK 分离：`vendor-dynamic`（签名）、`/api/sec/v1/ds`（loader）、`/api/sec/v1/scripting`（按 `type` 下发模块）
- [ ] `scripting` body：`{"callFrom":"web","callback":"","type":"<t>","appId":"xhs-pc-web"}`，`type=ds/mns/mnsv2/sign/sdt/fingerprint` 各返回一个模块
- [ ] `x-rap-param`（风控参数）**不是**必需项：页面自发请求带，本地去掉仍 200

### 反调试特征
- [ ] JSVMP payload 自带能力探针（首个致命点是 `Node.prototype.removeChild(undefined)`）
- [ ] payload 会调 `window.<随机名>()` 检查宿主接线（本次抓到 `window.fbejkbakrbadskfe()`，0 参）
- [ ] 上报通道 `window.seccallback(token)`，token 是设备指纹串按 14 字符切开的两段

### 混淆类型
- [ ] JSVMP（指令流 + 前缀码常量池 + 状态机解释器），外层再套一层 obfuscator.io 字符串表

### 指纹检测规则（Agent 执行）

```
快速检测命令（30秒内完成）：
  - search_code(keyword="seccore_signv2")        → 命中即本家族（签名主链）
  - search_code(keyword="XYS_")                  → 命中即 XYS_ 信封
  - search_code(keyword="mnsv2")                 → 命中即有三参 JSVMP 出值点
  匹配判定：3 项中 ≥2 项 → 高置信度匹配
```

---

## 问题定位记录

```
现象：HTTP 200 但 {"code":0,"data":{}}（461）、或 {"code":-1,"success":false}（406）
失败层：先分传输/动态值两层——同一份有效 x-s，Node undici / curl.exe / node-tls-client 全部 461，curl_cffi(chrome124) 200
路线：R3（jsdom 跑站点实体）+ R0（能不发就不发的参数一律去掉复验）
外部依赖：会话 cookie（a1/web_session/sec_poison_id/websectiga）由使用者提供；
          x-s-common 取一次会话内的值即可复用（换 a1 仍可用，不是逐字节绑定）
结论强度：证明（三个失败码可分层：缺头 406 / 网关不认 461 / 业务码 200 内-100/-101）
```

---

## 加密方案

- **算法**：
  1. `x5 = md5hex(method 无关；path + body 拼接串)`
  2. `x3 = mnsv2(signStr, x5, md5hex(path))` —— JSVMP 出值
  3. `x-s = "XYS_" + b64_custom(utf8(JSON({x0..x5[,x6,x7]})))`
- **密钥来源**：x5 来自请求本身；x3 来自站点 JSVMP 实体 + 设备指纹 `localStorage.b1`
- **加密流程**：
  1. 取会话（浏览器登录或游客均可，视站点策略）
  2. 本地拼 `signStr = path + body`，算 `x5`
  3. jsdom 里加载站点实体，`mnsv2(signStr, x5, md5(path))` 出 `x3`
  4. 用换表 base64 组装 `x-s`，与 `x-t`、`x-s-common` 一起发
- **签名公式**：`x-s = "XYS_" + b64_custom({x0:"4.4.3",x1:"xhs-pc-web",x2:"Windows",x3:mns(signStr,x5,md5(path)),x4:"object",x5:md5hex(signStr)})`

### 换表 base64 的取值方法

不要猜表：在页面里对编码函数喂 3 字节数组 `[i<<2,0,0]`，取输出的第 1 个字符，`i` 从 0 到 63 扫一遍，就得到完整 64 项表。
本次得到的表（当天有效）：

```
ZmserbBoHQtNP+wOcza/LpngG8yJq42KWYj0DSfdikx3VT16IlUAFM97hECvuRX5
```

---

## 已验证定位路径（按当前目标核对后再用）

```
步骤 1: 打开目标页，网络面板过滤 homefeed，拿一条成功请求，把 x-s 抄下来
步骤 2: search_code(keyword="seccore_signv2") → 找到签名主链（x5/x3/x-s 三件套）
步骤 3: 在该文件里找 window.mnsv2(c,u,p) 调用点，确认 x3 由它产出
步骤 4: search_code(keyword="mnsv2") 命中模块 → 抽它的 eval 体（module 内 String.raw 模板串）
步骤 5: 本地 jsdom 跑该实体验证 window.mnsv2 存在；用已知 (signStr,x5,pathMd5) 复现 x3
步骤 6: 用换表 base64 组装 x-s，先用 curl_cffi 发一次对照（200/406/461 分层）
```

---

## 还原代码模板

### 核心函数（Python）

```python
ALPHABET = "ZmserbBoHQtNP+wOcza/LpngG8yJq42KWYj0DSfdikx3VT16IlUAFM97hECvuRX5"
STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def xE(b: bytes) -> str:                    # 站点 xE：换表 base64
    t = str.maketrans(STD, ALPHABET)
    return base64.b64encode(b).decode().translate(t)

def sign(path: str, body: str, x3: str) -> dict:
    x5 = hashlib.md5((path + body).encode()).hexdigest()
    s = {"x0": "4.4.3", "x1": "xhs-pc-web", "x2": "Windows",
         "x3": x3, "x4": "object", "x5": x5}
    return {"x-s": "XYS_" + xE(json.dumps(s, separators=(",", ":")).encode()), "x5": x5}
```

### 出值侧（Node.js / jsdom，无浏览器）

```javascript
const dom = new JSDOM('<html></html>', { url: 'https://<TARGET>/', runScripts: 'outside-only' });
const w = dom.window;
// 关键 1：DOM 宽容兜底（实体把 removeChild 当能力探针）
for (const m of ['appendChild', 'removeChild', 'insertBefore', 'replaceChild']) {
  const o = w.Node.prototype[m];
  w.Node.prototype[m] = function (...a) { try { return o.apply(this, a); } catch (e) { return a[1] || a[0] || null; } };
}
// 关键 2：UA 与设备指纹必须真实
Object.defineProperty(w.navigator, 'userAgent', { get: () => '<FIREFOX_UA>', configurable: true });
w.localStorage.setItem('b1', '<B1_DEVICE_BLOB>');   // 空值 → 出 9 字符废值
w.eval(SDK_CODE);                                   // 站点实体原文
const x3 = w.eval(`mnsv2(${JSON.stringify(signStr)}, ${JSON.stringify(x5)}, ${JSON.stringify(pm)})`);
```

### 环境补丁（如需要）

```javascript
// b1 来源：x-s-common 解出的 x8 字段，或页面 localStorage.getItem('b1')
// 刷新时机：换设备/换周失效时重新取一次；不要用空串或随手编的串
```

---

## 🚫 禁动清单

### ❌ 禁动对象 1：`x-s-common`
- **理由**：实测同一份有效 `x-s`，去掉 `x-s-common` 立刻从 200 掉到 461（空 data）。曾因为"页面里带截断值也 200"误判成弱校验。
- **正确做法**：整串照抄同会话值；换 a1 后可复用，但不要截断、不要伪造。

### ❌ 禁动对象 2：`localStorage.b1`
- **理由**：空值/假值时 `mnsv2` 仍返回字符串，但是 `mns0201_0`（9 字符）这种废值，服务端必拒；很难从"能出值"上看出问题。
- **正确做法**：用真实指纹串；断言长度与结构（本次实测 668~1788 字符都有有效样本）。

### ❌ 禁动对象 3：给"未定义全局"加泛化 stub
- **理由**：JSVMP 是"先造描述对象、CALL 时才解引用"，把 window 套 Proxy 让未定义名字变可调用，会连带改掉 `typeof`/`in`/`instanceof` 走同一解引用路径的判定，它反而更早失败。
- **正确做法**：只在 window 上真挂它要的那个同名函数（本次是 `fbejkbakrbadskfe`，0 参，返回值无所谓）。

---

## 踩坑记录

| # | 坑 | 现象 | 解决方法 |
|---|---|---|---|
| 1 | 用 Node 原生 `fetch`/`curl` 发 | 一律 461，`{"code":0,"data":{}}` | 换 `curl_cffi impersonate=chrome124`；网关看 TLS/JA 指纹，与 HTTP 版本无关（h1/h2/h3 都通） |
| 2 | 把 `mns0201_` 判成"服务端不认" | 早期一次 406，误以为代次被拒 | 用干净输入重测 → **200**；那次 406 是输入/会话态不匹配，属误判 |
| 3 | 连续打请求 | 第 3 次开始 `300011 账号异常` | 冷却 ~75s 后同一 token 复发仍 200；采集间隔 ≥5s（8–10s 更稳），token 本身可复用 |
| 4 | 裸 jsdom 加载实体 | 抛 `removeChild: parameter 1 is not of type 'Node'` | 给 4 个 DOM 方法加宽容兜底；裸 `vm` 则静默不注册，都不报错 |
| 5 | 想靠"抓一次 `window.__bc`"拿签名程序 | 抓到的是指纹程序 | `__bc` 会被后加载的模块覆盖，只保留最后一次写入 |

---

## 假设与纠偏

| 当时的假设 | 推翻它的证据 | 现在的结论 |
|---|---|---|
| `x-s` 是"加密信封"，需要 AES/流密码还原 | 用站点自己的换表 base64 解码后直接得到明文 JSON | 只是换表 base64，不是密码学 |
| `mns` 前缀（`0201` vs `0301`）是环境评级 | 调用期把 canvas/audio/getComputedStyle 全干掉，前缀不变；给 hook 各种返回值也不变 | 是**程序代次**：两代解出字节数 92（mod16=12，带 padding）vs 144（mod16=0） |
| 站点会拒绝旧代 `mns0201_` | 干净输入重测得 200 / `code:0` / 真实 items | 当天两代都收；换代会再来一次 |
| `x-rap-param` 必需 | 本地去掉仍 200 | 非必需，别浪费算力 |

---

## 变体说明

| 变体 | 差异点 | 影响 |
|------|--------|------|
| 国内站 vs 国际站（域名不同） | `vendor-dynamic` 哈希不同（`204431b8` vs `067e338b`），模块 id 变 | 抽实体的模块 id 要重找；两者出的 `mns` 代次相同 |
| 出口 IP 在境外 | 首屏 302 到国际站域名，`webBuild` 变 7.0.0 | 会话/`x-s-common` 与目标域不匹配会出现 `-100/-101` 业务码，别误判成签名失败 |

---

## 环境检测差异表

| 检测点 | 真实浏览器值 | 模拟环境原始值 | 修复方式 |
|--------|-------------|---------------|---------|
| `Node.prototype.removeChild` | 正常 | 传 `undefined` 直接抛，打断初始化 | 4 个 DOM 方法加 try/catch 兜底 |
| `navigator.userAgent` | 真实 UA 串 | jsdom 默认 `jsdom/xx` | 覆盖成与目标一致的 Firefox 串 |
| `localStorage.b1` | 真实指纹串 | 空 | 从会话里取真实值写入 |

---

## 关键经验总结

### 1. 先分层，再谈"能不能离线"
三个失败码（406 / 461 / 200 内业务码）分别对应"动态值 / 传输 / 会话"。先把同一份有效签名在三种客户端上跑一遍，
就能把"签名不对"和"网关门不对"彻底分开——本次一开始就在这上面浪费了半天。

### 2. "能出值"不等于"值可用"
`mns` 出 `mns0201_0`（9 字符）时没有任何异常，只会被服务端静默拒绝。断言必须包含长度/结构，不能只看非空。

### 3. 抓运行时状态要抓"写入序列"，不是"最终值"
`window.__bc` 这类旁路存证会被后加载模块覆盖；要拿到全部程序，得在页面里给该属性装 setter，把每次写入都截下来。

---

## 可验证事实清单

- [ ] `x-s` 以 `XYS_` 开头，且用给定 64 项字母表可解出明文 JSON
- [ ] `x5` 等于 `md5hex(path + body)`
- [ ] `x3` 由 `window.mnsv2(signStr, x5, md5(path))` 产出，长度为 128/136（旧代）或 200（新代）
- [ ] 缺 `x-s-common` → 461；缺 `x-s` → 406；同一 token 复用仍 200
- [ ] 连续 3 次快速请求触发 `300011`，冷却 ~75s 恢复
