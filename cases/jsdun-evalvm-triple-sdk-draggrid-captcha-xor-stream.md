# JSDUN eval-VM 三件套 + 图集拖拽验证码 + XOR 流密码信封（电商 PC 站）

> 难度：★★★★★
> 还原方案：E: jsdom 环境模拟（喂入-截出）+ D: 浏览器自动化（仅验证码环节）
> 实现语言：Node.js（主体）+ Python（拖拽执行器）
> 最后验证日期：2026-11-20
> 平台类型：电商平台（潮流网购社区，PC 站）
> 适用范围：`www.dewu.com` PC 首页商品流 `feeds/info`；前端版本 `bcv=1.3.1.20260331`；2026-11-20 抓取
> 到达层级：S3（一次放行取到 40 件真实商品）/ S4 未达（一次放行 = 一次请求）
> 失效条件：`bcv` 升级、`/interceptor` 灰度开关调整、验证码题型从「图集拖拽」变更、`sk` 签发策略变化

本案例的结论只对上述范围成立，不是全局规则。

---

## 技术指纹（候选线索）

### JS 特征
- [x] 三个 `eval(function N(n,Q){...})` 形态的 VM 脚本，**字符串常量里带 `JS DUN PROTECT`**（`pceptor.js` / `preinforce2.js` / `pyuntu.js`）
- [x] 脚本域名 `davstatic.dewu.com`，由业务代码动态注入，不在 HTML 里
- [x] 全局挂载：`_yundunxhr`（伪造 native 外观的 XHR）、`base64js`、`jsdVipUserMark='dw'`、`fun`（object，原型上只有 `Fun110`/`Fun99`，arity 均 5）、`regeneratorRuntime`、`dewuCap`、`yd_md5`
- [x] `_yundunxhr.toString()` 返回 `function XMLHttpRequest() {\n    [native code]\n}`（伪造 native）
- [x] 加载顺序：`pceptor.js` → 业务 chunk → `preinforce2.js` → `pyuntu.js` → 阿里云验证码 SDK

### 参数特征
- [x] `sign` | 32 hex | `md5(键名升序拼接 key+value + 固定盐)`
- [x] 请求体 `{"data":"<32hex><base64>"}` | hex = `md5(明文JSON)`，密文与明文**等长**
- [x] 验证码请求体 `{"d":"<base64>","sign":"<32hex>"}`
- [x] 验证码 verify 明文 12 字段：`sessionID/width/type/pts/xys/data/bcv/webp/c/pc/pn/trace`
- [x] 轨迹 `xys` = `"x,y,相对ms|..."`，首点是**绝对页面坐标 + 绝对时间戳**

### 请求特征
- [x] 加载即打 `POST dav.dewu.com/interceptor`（596B，纯灰度开关，**不含 URL 白名单**）
- [x] 另有 `POST /webSk`（1440B hex，签发 `sk`）、`/cost`、`/wr`
- [x] 业务请求头：`adi`（每请求变）、`hsn`（每请求变）、`ltk`（会话级）、`sk`（= cookie，会话级）、`sks: 1,hdw4`、`shumeiid`、`sessionid`、`skt: hdr1`
- [x] **header 里的 `shumeiid` ≠ cookie 里的 `dwsm`**（两个不同的设备标识，实测）

### 反调试特征
- [x] 全量 JSVMP（控制流平坦化 + 字符串编码），无法直接下断点
- [x] 请求拦截层同时覆盖 `XMLHttpRequest` 与 `fetch`
- [x] 图集验证码按风险分决定题型：低风险→无感验证；高风险→图集拖拽（需人眼）

### 混淆类型
- [x] JSDUN eval-VM（`eval` 包自解码器，运行时把源码还原后执行）

### 指纹检测规则（Agent 执行）

```
快速检测命令（30秒内完成）：
  - search_code(keyword="jsdVipUserMark") → 命中 → 高置信度（这是该 SDK 私有标记）
  - search_code(keyword="JS DUN PROTECT") → 命中 → 确认 JSDUN
  - scripts(action='list') → 存在 davstatic.dewu.com 下 3 个 100KB+ 脚本
  - 全局探测 typeof window.fun === 'object' && typeof window.dewuCap === 'function'
  匹配判定：前 2 项任一命中 → 高置信度
```

---

## 问题定位记录

```
现象：info 返回 485「请校验验证码」；过码后第二次请求 403「请求已拒绝」
失败层：服务端策略（会话放行额度）+ 请求形态（body 必须为 {data} 信封）
      依据：明文 body + 风控头 → 400 校验失败:11001；{data} 原样重放 → 403；页面自己发 → 200
路线：R3（补环境跑原始 SDK）拿下 sign/信封/解密；R6（浏览器自动化）拿下验证码
外部依赖：sk（webSk 签发）、会话放行（过一次码换一次）、adi/ltk/hsn（SDK 每请求生成）
结论强度：sign / 信封 / 解密 = 证明；「一次放行一次请求」= 证明（多场景复现）
仍未固定：adi 的服务端校验规则、放行额度是按次数还是时间窗
```

---

## 加密方案

### 三层独立机制（**这是本案例最关键的结构认知**）

| 层 | 算法 | 密钥来源 | 与什么绑定 |
|---|---|---|---|
| **① 请求签名 `sign`** | `md5(键名升序拼接 key+value + "048a9c4943398714b356a696503d2d36")` | 硬编码盐 | 只与参数有关 |
| **② 请求信封 `{data}`** | `hex32 = md5(明文)`；`cipher = 明文 XOR KS`；等长、偏移 0 | **`KS = F(sk, UA族)`**（同 sk 同 UA 恒定） | 强绑 sk，换 sk 换表 |
| **③ 响应体** | `wire base64 → base64解码 → utf8 每字符&0xff = 密文 → XOR 位置相关 KS → **zlib inflate** → 明文 JSON` | **静态内置**（与 sk/会话/时间无关） | 只与 UA 分支有关 |

**关键坑**：②③ 是两套完全独立的密钥体系。用 ② 的表去解 ③，偏移 0~63 全负（实测）。

### 验证码的 `d`

- 结构与 ② 同形（`hex32?` 无前缀，纯 `base64(XOR(明文, KS))`），但 **`KS` 是另一张表**
- `sign = md5("d" + d + 盐)`（与业务接口同一个盐、同一个 `f(t)`）
- `d` 明文：call 6 字段（`sessionID,bcv,type,c,webp,data`）；verify 12 字段
- **`c` 字段别写反**：call 恒 `rest=0`；verify 是 `rest=156|vrest=0|vreqt=4|sqt=73873|ojst=19`

### 签名公式（可直接复用）

```js
const SALT = '048a9c4943398714b356a696503d2d36';
function sign(params) {
  const concat = Object.keys(params).sort().reduce((acc, k) => {
    let v = params[k];
    if (v === undefined) return acc;
    if (Number.isNaN(v)) v = '';
    if (Array.isArray(v)) {
      if (!v.length) return acc + k;
      return acc + k + v.slice().sort().map(x => x instanceof Object ? JSON.stringify(x) : x).join(',');
    }
    return v instanceof Object ? acc + k + JSON.stringify(v) : acc + k + String(v);
  }, '');
  return md5(concat + SALT);
}
```

---

## 已验证定位路径（按当前目标核对后再用）

```
步骤 1: scripts(action='list') → 找到 davstatic.dewu.com 下 pceptor/preinforce2/pyuntu 三个脚本
步骤 2: 脱壳：不要读字节码。在 vm 沙箱里接管 eval 与 Function，SDK 运行时会自己把源码 eval 出来
        （scripts/unpack.js：sandbox.eval = (src) => { dump(src); return vm.runInContext(src) }）
        → 得到 515KB / 366KB / 703KB 的可读源码
步骤 3: 业务请求封装定位：search_code('feeds/info') → 模块 d0RG → 里面有 f(t) 就是 sign
步骤 4: 拦截器定位：全局探测 _yundunxhr；它同时覆盖 XHR 与 fetch
步骤 5: 出值入口：dewuCap（验证码）在 pyuntu；Fun99（响应解密）/Fun110（令牌）在 preinforce2
步骤 6: 喂入-截出：先 Hook 原生 XHR/fetch → 再 evalSource(pceptor) → 喂 /interceptor 真实响应 → 抓最终 body
```

---

## 还原代码模板

### 核心：顺序敏感的三步

```javascript
// ① 请求信封（与浏览器逐字一致，已验证）
const ks = await calibrate({ sk, shumeiid, ua });          // 内部跑一次原始 SDK 标定
function buildEnvelope(plaintext) {
  const p = Buffer.from(plaintext, 'utf8');
  const cipher = Buffer.alloc(p.length);
  for (let i = 0; i < p.length; i++) cipher[i] = p[i] ^ ks[i];
  const b64 = Buffer.from(cipher.toString('latin1'), 'utf8').toString('base64');  // ← mojibake base64 成因
  return md5(plaintext) + b64;
}

// ② 响应解密（Node 里跑 preinforce2 的 Fun99，不要自己实现）
const plain = await fun.Fun99(rawResponseText, '', sksHeader, '');   // sks='1' 才解密；'' 等价 '1'
// 内部：base64 → utf8&0xff → XOR 静态表 → zlib inflate
```

### 环境补丁的两个硬要求

```javascript
// 1) JSDUN 的拦截器要生效，jsdom 必须开 resources:'usable'
new JSDOM(html, { url, runScripts: 'outside-only', resources: 'usable' });

// 2) Fun110 五参在 Node vm 里必挂（CryptoJS 的 WordArray._doFinalize 被污染成 5.6e8 轮 MD5），
//    同一份源码在 jsdom realm 里 2ms 返回 → 出信封必须用 jsdom，不能用裸 vm
```

---

## 🚫 禁动清单

### ❌ 禁动对象 1：`xys` 首点的绝对坐标当相对值处理
- **理由**：真实 `xys` 是**混合基准**——首点 = 绝对页面坐标 + 绝对时间戳（y=626），后续点 y 用的是另一套基准（0→249）。拿首点做归一化锚点会算出 `fy=1.66`，拖拽直接飞出屏幕（实测：第二点 y 从 251 跳到 459）。
- **正确做法**：归一化只用 `seg[1:]`（跳过首点），首点单独作为起点使用。

### ❌ 禁动对象 2：用 `crop` 通道去否决 `oracle` 通道
- **理由**：题目图是**文字标签**（100×21 灰度，透明底黑字），候选是**照片**（80×80），两者不在同一特征空间。实测「纯视觉 auto」0/2；拿 crop 做一致性惩罚会把正确答案压掉（oracle 0.89 → 融合后 0.53，直接误拒）。
- **正确做法**：oracle 主导（有 `bgImage` 时直接用它的置信度判定），crop/label 只在无 bgImage 时兜底。

### ❌ 禁动对象 3：用 PowerShell `Set-Content` 改含中文的 `.py/.js`
- **理由**：会把 UTF-8 中文写成 GBK 乱码，Python/Node 直接语法错误（本案例踩了 3 次）。
- **正确做法**：只用 write/edit 工具改文件。

---

## 🌐 UA 分支矩阵

### UA 分支 1：Firefox（Camoufox 默认）
**必补**：`navigator.userAgent`、`navigator.plugins`（PDF Viewer 串）、`canvas.getContext('2d')` + `toDataURL`、`screen.width/height`、`document.compatMode`
**禁补**：`window.chrome`、`navigator.userAgentData`（Firefox 没有，补了反而暴露）

### UA 分支 2：Chrome（**不要用**）
换 Chrome UA 会：① 请求侧 keystream 整张换表（0/124 匹配）；② 响应侧 `Fun99` 静默返回 `Uint8Array` 序列化（`{"0":2,"1":64,…}`），不报错但解不出明文。

---

## 踩坑记录

| # | 坑 | 现象 | 解决方法 |
|---|---|---|---|
| 1 | 服务端对明文 body 回 400 | `校验失败:11001`，不报签名错 | 必须用 `{data}` 信封；缺风控头时才会回 485 要验证码 |
| 2 | 信封原样重放被拒 | 403 请求已拒绝 | 信封一次性（防重放）；必须本地重新生成 |
| 3 | `captcha/call` 缺 `sessionID` | 一直 `请求失败` | call 明文顶层第一个字段就是 `sessionID`，来自 info 的 485 响应；复用过期的会被拒 |
| 4 | header 的 `shumeiid` 与 cookie 的 `dwsm` 混用 | 明文里 `shumeiId` 填错 → 请求失败 | 两个是不同标识，明文要用 header 那个 |
| 5 | jsdom 不开 `resources:'usable'` | SDK 加载成功、函数能调，但**拦截器不触发** | 加 `resources:'usable'` 后 `[mock-xhr] feed interceptor` 才出现 |
| 6 | 用 captcha 的 KS 解 info 的 `{data}` | 偏移 0~4 扫描全负（0~0.8% 匹配） | 两套独立密钥体系，必须分别标定 |
| 7 | 用请求侧 KS 解响应 | 全负 | 响应侧是静态内置 + 多一层 zlib |
| 8 | 图集验证码位置写死 | 三次采样相框分别在左上/左下/右下 | 布局每次随机，必须读 DOM 的 `getBoundingClientRect()` |

---

## 假设与纠偏

| 当时的假设 | 推翻它的证据 | 现在的结论 |
|---|---|---|
| 「pure protocol 可以过验证码」 | verify 的 `xys` 首点是按下坐标，服务端靠它判定选了哪张图；而 `captcha/call` 响应**不含任何布局**，图位每次随机 | **纯协议不可行**，必须渲染页面读 DOM |
| 「有一张硬编码常量 keystream」 | 换 sk 后 KS 完全不同（`sk=''` → `48b44cef…`；`sk=96×'A'` → `ef079054…`） | `KS = F(sk, UA族)`，确定性函数，换 sk/UA 必须重新标定 |
| 「验证码能无感自动过」 | 追问用户后确认：每一次成功都是他手动点的 | 至少在本环境没有证据支持"无感"；环境够只决定"不被 403"，不决定"免码" |
| 「`c` 里的计时字段恒为 0，不参与判定」 | 解开 verify 明文：`rest=156|sqt=73873|ojst=19` 全非 0 | call 恒 0，verify 带真实交互耗时 |
| 「响应能解开 = 页面能渲染」 | info 200 但页面商品卡片数 = 0 | 解密与业务渲染是两件事 |
| 「一次放行能连取多页」 | 同 sk 第二次请求即 403（点 tab / 本地请求均复现） | 一次放行 ≈ 一次请求 |

---

## 变体说明

| 变体 | 差异点 | 影响 |
|---|---|---|
| 验证码类型 | 低风险 → 无感验证（197ms 自动过）；高风险 → 图集拖拽（需人眼/自动化） | 决定是否需要拖拽执行器 |
| 接口风控等级 | `category-pick/mapping` 只要 sign；`feeds/info` 要信封 + 过码 | 低风控接口可纯协议，高风控接口必须过码 |

---

## 关键经验总结

### 1. eval-VM 不要去读字节码，接管 `eval` 就能一键脱壳
JSDUN 这类保护把源码编码在 VM 里，运行时用 `eval`/`Function` 还原后执行。在 vm 沙箱里把 `eval` 换成"先落盘再执行"，三个 SDK 立刻变成 366KB/515KB/703KB 的可读源码，工程量从"读混淆"降一个数量级。

### 2. 三层独立密钥体系必须先分层，再动手
sign（参数哈希）/ 请求信封（绑 sk 的流密码）/ 响应解密（静态表 + zlib）。把任意两层的密钥混用，得到的都是"全负"结果，很容易误判成"算法没破"。

### 3. `bgImage` 可能是正确答案的马赛克版
图集验证码的 `call` 响应里，`bgImage` 是「正确候选」的大面积降质版：按 8×8 块均值逐块投票，能直接反查答案（实测 2/2，40~50ms），完全不需要视觉模型。**先找这类"信息泄露"，再考虑上模型。**

### 4. 验证码的坐标依赖 DOM，纯协议必然死
`verify` 的轨迹首点 = 按下位置；`call` 响应只给图内容不给布局；布局每次随机。三者合起来就是死结——**必须在渲染后的 DOM 上读 `getBoundingClientRect()`**。

### 5. 拖拽轨迹要用真人模板做仿射变换，不要凭空造曲线
凭空造的 easeOut + sin 抖动，前 1/4 速度只有真人的 46%、dt 取值数量是真人的 2.4 倍。用一条真人轨迹归一化后按新起终点缩放（并让时长随距离缩放），形状与节奏才同源。

### 6. 阈值闸门比"提高识别率"更救急
识别置信度低时**不提交**、只换题，比"赌一把提交"划算——因为一次失败会计入风控评分，让后续更难。用实跑数据切阈值（成功 0.765/0.872 vs 失败 0.676/0.697 → 阈值 0.72）。

### 7. 高频试错会把环境打成 403，且不可逆
同一个 IP 一小时内上百次请求（假签名、重复 call、失败过码）之后，服务端从"要验证码（485）"降级成"直接拒绝（403）"，连验证码都不给了。**验证码类目标必须控制试错频率，并把"环境状态"当成一等资源管理。**

---

## 可验证事实清单（下次同站分析先逐条 verify）

- [ ] `sign` 盐仍是 `048a9c4943398714b356a696503d2d36`，算法仍是「键名升序拼接 + 盐 → md5」
- [ ] `feeds/info` 请求体仍是 `{"data":"<32hex><base64>"}`，且 `hex32 == md5(明文JSON)`
- [ ] 三个 SDK 仍是 JSDUN eval 包（`JS DUN PROTECT` 魔数），仍挂在 `davstatic.dewu.com`
- [ ] 全局仍有 `_yundunxhr` / `fun.Fun99` / `dewuCap` / `yd_md5`
- [ ] 响应解密仍走 `Fun99(text, '', sks, '')`，且需要 `sks=1`
- [ ] 验证码仍是图集拖拽（`type=5`），DOM 仍是 5 个 `.moveImg` + `blank.png` 相框，位置随机
- [ ] `xys` 仍是混合基准（首点绝对、后续相对）
- [ ] 一次放行仍只够一次请求（同 sk 第二次 403）
