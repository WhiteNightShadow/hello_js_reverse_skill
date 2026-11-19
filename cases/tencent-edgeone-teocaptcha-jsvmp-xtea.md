# 腾讯 EdgeOne / 天御 TEOCaptcha `collect`：JSVMP + XTEA + 四槽综合校验

> 难度：◄★★★★（JSVMP + 每次会话重新生成密钥 + 服务端只校验综合分）
> 还原方案：**E: 本地 VM 复现 + 明文槽定点修正**（跑厂商 SDK 出 collect → 提 key 解密 → 改 4 个环境槽 → 重加密）
> 实现语言：Node.js（vm 沙箱承载 `tdc.js`，无需浏览器）
> 最后验证日期：2026-11-19（4 次 `errorCode=0`，浏览器已关闭状态下复验通过）

---

## 技术指纹（供 Phase 0.5 自动匹配）

### JS 特征
- [x] 挑战页由 `TEOCaptchaWidget.js` + `tcaptcha-widget-eo-frame.<hash>.js` 拉起，内嵌 iframe 指向
      `https://captcha.eo.gtimg.com/static/template/widget_ele_eo.<hash>.html`
- [x] 核心脚本 `https://captcha.eo.qq.com/tdc.js?app_data=…&t=<n>&appid=…&js_data=d04…**&a=b`，
      **每次加载字节都不同**（11 次抓包 = 10 份不同 sha256，连"同长度 + 同 TDC_NAME"也命中不了）
- [x] 单行压缩 190KB~270KB；`window.TDC_NAME="<20 位随机串>"` + `window[TDC_NAME]="<352 字符>"`（= `eks`）
- [x] 字节码解释器：常量池形如 `[void 0,null,0x9e3779b9,0x13c6ef3720,0.75,…,0x811c9dc5]`，
      入口 `cv_xxxx(0x6d84,[],window,[…常量池…],void 0)()`
- [x] **opcode 编号 build 绑定**：属性写分片在 264504 那份是 `case 0x22`、244257 是 `case 0x4b`、
      241194 是 `case 0x51`、202210 是 `case 0x4e`。按 `case 0xNN` 硬编码必然失效
- [x] 字符串表被提到 IIFE 顶部的共享对象里（`{'mDAJd':'ABCDEF…+/='}`），函数体只留键名 ——
      这会让"函数体内找 base64 字母表"的静态识别失效

### 参数特征
- [x] `GET /cap_union_prehandle?aid=…&sid=<10 位>&deviceID=<10 位>&uuid=<20 位>&ec_pub=<b64>&enc_ok=c1&…`
      响应含 `sess`（538~570 字符）、`pow_cfg{prefix,md5}`、`comm_captcha_cfg.tdc_path`
- [x] `POST /cap_union_new_verify`，body 为
      `collect`（base64，4.3KB~5.5KB）、`tlg`（= collect 长度）、`eks`（352）、`sess`、`ans`、
      `deviceID`、`pow_answer`（`<prefix><nonce>`）、`pow_calc_time`
- [x] `ans` 恒为 `[{"elem_id":0,"type":"DynAnswerType_TIME","data":""}]`
- [x] PoW：`md5(prefix + nonce) === pow_cfg.md5`，`pow_calc_time` 不校验严格
- [x] 通过后下发 `EO-Bot-Captcha-Token`（max-age 2592000，domain `.51cto.com`），
      随后页面侧 JS 再设 `__tst_status` / `EO_Bot_Ssid`，reload 才出正文

### 请求特征
- [x] 未过校验时目标页返回"挑战页"（`<title>Security Verification</title>`，正文只有一句
      "Verifying the safety of the connection. Please check the box below."）
- [x] `verify` 返回 `errorCode:"0"` + `ticket` 才算过；失败常见 `"12"`（内容不匹配）、
      `"51"`（格式非法/结构异常）
- [x] verify **不携带任何 Cookie**（实测），Referer/Origin 都是 `https://captcha.eo.gtimg.com/`

### 反调试特征
- [x] **`Error().stack` 会被读进载荷**：SDK 用正则从栈里取"函数名@URL:行:列"。
      Node 默认栈格式（`    at fn (file:1:2)`）不匹配 → `match()` 返回 null → `null[0]` 抛 TypeError →
      **这个 TypeError 被当指纹写进 collect**（见踩坑 #6）
- [x] `Object.keys(window).length` 会进载荷（`sd.ep.k`），真机 iframe 是 **282**
- [x] canvas 深指纹、WebGL 参数、音频 DSP、字体宽度、`navigator.plugins`、媒体编解码能力列表都会采集
- [x] `readPixels` 全 0 会让 graphics 探针降级（`sd.fpBio.gp.s = -3`），需要填非零像素

### 混淆类型
- [x] JSVMP（字节码 + 扁平化 dispatcher + 运行期字符串池拼装）

### 指纹检测规则（Agent 执行）

```
快速检测（30 秒内）：
  - list_network_requests(urlFilter="tdc.js")        → 命中 190KB+ 单行脚本 + TDC_NAME 全局
  - search_in_sources("0x13c6ef3720")               → 命中常量池（32 × TEA delta）
  - search_in_sources("cv_") + "0x6d84"             → 命中 VM 入口调用形态
  - list_network_requests(urlFilter="cap_union_prehandle") → 存在即本案例挑战流
  - 响应 errorCode 12 且 tlg == collect.length      → 内容层校验，本案例
匹配判定：tdc.js + TEA delta 常量 + prehandle/verify 组合 → 本案例高置信度
```

---

## 加密方案

- **算法**：`collect = base64( XTEA / 32 轮 / ECB / 8 字节块 / (v0,v1) 小端 / sum 在两半之间 +=delta )`
  - 明文长度不足 8 字节倍数时用 `\0` 补齐（实测补 3 字节）
  - **不需要二次 base64、不需要 XOR、无压缩**
- **密钥**：4 个 32bit 字，**每次会话都不同**（由 `js_data` 派生，build 绑定）
  - 原始 4 字是从字节码里按 `(charCode + K) << 8i` 打包出的"半成品"，裸字直接解密必然失败
  - 轮函数按 key 下标分支成多份内联副本，每份给该下标加一个常量 `S[i]`
    ⇒ **实际有效密钥 `EK[i] = key[i] + S[i]`**
  - `S` 的形状随 build 变：实测有 `[s,0,t,0]`（位 0/2）与 `[s,t,0,0]`（位 0/1）两种，
    **写死位置必漏**
- **明文结构**：
  ```json
  {"cd":[ 72~73 个槽 ], "sd":{ od, mathFingerprint, fpBio{v,cw,ce{s,h,p},gp{s,sp,px},af{s,sum,h}}, ep, tdc_perf{fi,pi,gd} }}
  ```
  原始明文里 `cd` 不是紧凑 JSON（**含约 103 个空格**），但服务端只解析内容，重建为紧凑格式照样能过
- **反解思路**：拿到任意一条真实 `collect` + 该 build 的 `EK` 就能解出全文明文；
  `EK` 用「跑 VM 自证」的方式枚举（见还原代码模板）

---

## 已验证定位路径（Phase 0.5 命中后直接执行）

```
① prehandle → 拿 sess / pow_cfg / tdc_path / sid
② 下载 tdc.js（每次都新）
③ 本地 vm.runInContext 跑它 → TDC.getData(true) → collect（VM 自己加密，不需要我们提 key）
④ tdc_key3 提该 build 的 EK（--selfcheck 自证，平均 3.5s）
⑤ 解密 collect → 定点修正下面 4 个槽 → 重新加密
⑥ 提交 verify（collect/tlg/eks/sess/ans/deviceID/pow_answer/pow_calc_time）
⑦ 用 ticket 请求目标页，判 200 且不含 "Security Verification"
```

### 服务端真正校验的 4 个槽（**综合评分，必须同时正确**）

| 槽语义 | 真机值 | 本地 VM 值 | 修正 |
|---|---|---|---|
| `"<flag>;<sid>"` | `1;<prehandle 的 sid>` | `0;1106021005`（硬编码旧值） | flag→1，sid→本次 prehandle 的 sid |
| 自动化特征分 | `0` | `22` | → 0 |
| iframe 判定 | `"iframe"` | `"top"` | → `"iframe"` |
| 某计数 | `0` | `3` | → 0 |

**为什么必须 4 个一起改**（实测，每行都是一次真实提交）：

```
只恢复前 9 个差异槽        → 0     （后 9 个用本地值完全没问题）
只恢复中间那 4 个          → 0     ← 这 4 个是关键
只恢复 4 个里的前 2 个     → 12
只恢复 4 个里的后 2 个     → 12
只改 canvas 深指纹槽        → 0     （不校验）
只改 sd.tdc_perf / sd.ep.m → 0     （不校验）
```

⇒ 服务端算的是**综合分**，只修一部分仍超阈值。这是本案例最反直觉的地方。

---

## 还原代码模板

### 核心：本地 VM 出 collect + 四槽定点修正

```js
// ① 用 Firefox 风格栈跑 SDK（否则 cd 里会写进一个 TypeError，见踩坑 #6）
const { buildEnv, createContext } = await import('./scripts/env.mjs');
const w = buildEnv();
w.globalThis = w;
w.TCaptchaSid = sidParam;                       // 本次 prehandle 的 sid
const { ctx } = createContext(w, tdcUrl);       // 内含 Error.prepareStackTrace
vm.runInContext(tdcSrc, ctx, { filename: tdcUrl, timeout: 40000 });
await new Promise(r => setTimeout(r, 1200));    // 让异步采集落地
const collect0 = decodeURIComponent(w.TDC.getData(true));

// ② 提 key（失败就换一份 build 重跑，约 1/6 概率）
const EK = runKey3(tdcFile);                    // tools/tdc_key3.mjs --selfcheck

// ③ 解密 → 修正 4 个槽 → 重新加密
const j = JSON.parse(xteaDec(Buffer.from(collect0, 'base64'), EK).toString('utf8').replace(/\0+$/, ''));
for (let i = 0; i < j.cd.length; i++) {
  const v = j.cd[i];
  if (typeof v === 'string' && /^[01];\d+$/.test(v)) j.cd[i] = '1;' + sidParam;
  else if (v === 'top') j.cd[i] = 'iframe';
  else if (v === 22 || v === 3) j.cd[i] = 0;
}
const rebuilt = Buffer.from(JSON.stringify(j), 'utf8');
const padded  = Buffer.concat([rebuilt, Buffer.alloc((8 - rebuilt.length % 8) % 8)]);
const collect = xteaEncEnc(padded, EK).toString('base64');

// ④ 提交
const body = new URLSearchParams({
  collect, tlg: String(collect.length), eks, sess,
  ans: '[{"elem_id":0,"type":"DynAnswerType_TIME","data":""}]',
  deviceID, pow_answer: prefix + nonce, pow_calc_time: String(ms),
});
```

### 核心：`tdc_key3` 的 key 提取思路（可复用于同类 JSVMP）

```
1) 内存 patch dispatcher（插桩点取 "switch(CODE[++IP])" 形态），把寄存器数组暴露给宿主
2) key 候选 = 寄存器里"连续 4 元 32bit 整数"（长度≥4 的数组都要扫窗口，不能只认长度恰好 4）
3) 盐候选 = 寄存器里那条**字节码 int 流**中 1e5..1e7 的整数，按**运行期读取次数**排序
   （比静态反汇编的排序信号强得多：真盐能顶到 top1~2，静态口径会排到 50+）
4) oracle = 「同一份 tdc.js 在本地 VM 跑出的 collect 必须解成 JSON」——这是自证，不是猜
5) 分级枚举：L0 无盐 → L1 ≤1 非零盐 → L2 ≤2 非零（~50 万组）→ L3 → L4 轮数×偏移 → L5 词池交叉
```

### 核心：`Error.stack` 对齐（`scripts/env.mjs` 的 `createContext`）

```js
export function createContext(w, tdcUrl) {
  const ctx = vm.createContext(w);
  vm.runInContext(`
    Error.prepareStackTrace = (err, frames) => frames.map(f =>
      (f.getFunctionName() || 'anonymous') + '@' + (f.getFileName() || ${JSON.stringify(tdcUrl)}) +
      ':' + f.getLineNumber() + ':' + f.getColumnNumber()
    ).join('\\n');`, ctx);
  return { ctx };
}
```

---

## 踩坑记录

| # | 坑 | 现象 | 解决方法 |
|---|---|---|---|
| 1 | 以为 key 可复用 | 用上一份 build 的 key 解新 collect 全是乱码 | 每次会话的 `tdc.js` 字节全新（11 次抓包 10 份不同 sha256），key 必须现提 |
| 2 | 按 `case 0xNN` 硬编码 opcode | 换一份 build 断点/插桩全失效 | opcode 编号 build 绑定（同一站点见过 0x22/0x4b/0x4e/0x51），必须现场扫形状 |
| 3 | 盐位置写死 `[s,0,t,0]` | 某些 build 永远枚举不到 | `S` 有 `[s,0,t,0]` 与 `[s,t,0,0]` 两种形状，要全排列 |
| 4 | 静态反汇编挑盐 | 真盐排到第 54（69 个候选里 62 个计数都是 1） | 改用「寄存器 int 流的运行期读取次数」排序，真盐顶到 top1~2 |
| 5 | 只认长度恰好 4 的 key 数组 | 某类 build 只采到 4 个候选，枚举 51 万组不中 | 扫所有 ≥4 长度数组的连续 4 元窗口（加窗口上限防 VM 超时） |
| 6 | **`Error.stack` 格式没对齐** | `cd` 里写进 `TypeError: Cannot read properties of null (reading '0')` —— 整整一晚都在追这个"指纹异常" | SDK 用正则按 Firefox 的 `fn@url:line:col` 解析栈；Node 的 `    at fn (file:1:2)` 让 `match()` 返回 null。用 `Error.prepareStackTrace` 渲染成 Firefox 格式 |
| 7 | 以为 canvas 深指纹 `_state:-2` 是关键 | 花了一整晚补 Blob/FileReader/OffscreenCanvas/createImageBitmap，纹丝不动 | 金标准实验证明**这一槽根本不校验**（只改它 → errorCode 仍 0）。真机上它从字面量 `<flag>` 分支构造，属性写断点抓不到 |
| 8 | 以为"缺 API"导致降级 | 补了 8 类 canvas 家族 API + Worker/SharedWorker/MessageChannel，全部无效 | TDC 压根没调用 Worker；`-2` 是能力探测阶段的降级分支，不是异常 |
| 9 | 真渲染替换沙箱 canvas | 用 `@napi-rs/canvas` 替换后，原本已与真机一致的 `sd.fpBio.ce` 反而被改坏 | 真机在 RFP 下 canvas 读回是全 0，我们的 stub 恰好等价；**不要引入真渲染** |
| 10 | 二分实验"怎么改都 12" | 反向实验里"全部恢复成真机明文"仍然 12 | 脚本 bug：rev 分支恢复的值被后面一行无条件用本地值覆盖了。**先验证「全恢复 == 金标准」再用二分** |
| 11 | 二分只看单个槽 | 改任何一个槽都不影响，误判"环境值都不重要" | 服务端是**综合评分**：4 个槽必须同时正确，单独改仍超阈值 |
| 12 | 时间戳槽当差异追 | 每次跑都不同，以为漏补 | 会话绑定值（时间/cookie）必须保留真机值，或在重建时用当前值 |
| 13 | Python Camoufox 拦截即坏 | 加了 `page.on('response')` 或 `page.route()` 后 widget iframe 直接不加载 | Playwright 同步 API 在事件回调里调 `r.text()` 会阻塞事件循环 → 死锁。要么不用拦截，要么用 Node 侧抓包 |

---

## 这一轮我判断错的四次

| # | 当时的判断 | 实际 | 推翻它的判据 |
|---|---|---|---|
| 1 | "key 提取就是静态挖 4 个整数" | 静态 recipe 在多数 build 上跑偏，必须运行期采样 + VM 自证 | 同一份 tdc.js 的解密自证只对 2/6 份成立，改运行期采样后 5/6 |
| 2 | "collect 内容差异是主要矛盾，逐槽补到 73/73 就能过" | 真机只校验 4 个槽的综合分，其余 16 项逐个验证全都不校验 | 金标准改槽：canvas/URL/自动化分单独改 → 全部 `errorCode=0` |
| 3 | "纯本地补环境到极限就通了" | 补到 56/73 仍 12；真正的解法是"跑 VM + 定点修正 4 槽" | 4 槽修好后 4 次连续 `errorCode=0` |
| 4 | "异常值异常一定是某 API 缺失" | `cd[36]` 的 TypeError 是**栈格式**问题，不是缺 API | 换成 Firefox 栈格式后该槽与真机逐字节一致 |

---

## 关键判据

- **判"是不是本案例"**：`tdc.js` + 常量池里 `0x9e3779b9`/`0x13c6ef3720` + `cap_union_prehandle`/`cap_union_new_verify`
- **判"collect 是否合法"**：`errorCode=0` + 拿到 `ticket`；`12` 多半是内容层（本案例的 4 槽），`51` 是结构/长度异常
- **判"key 提取对不对"**：用**同一份 tdc.js 在本地 VM 跑出的 collect** 自解，解出含 `cd` 的 JSON 才算对
- **判"某槽要不要补"**：拿真机明文当金标准，只改那一个槽提交 —— `0` 说明不校验，`12` 说明校验
- **判"通了没有"**：`errorCode=0` 之后再用 ticket 请求目标页，必须 `200` 且不含 `Security Verification`

---

## 变体说明

| 变体 | 差异点 | 影响 |
|---|---|---|
| `tdc.js` 每次换字节 | 190KB~270KB 不等，`TDC_NAME` 与 `js_data` 全变 | key/盐/opcode 位置全部变化，必须现场提取 |
| 明文 `cd` 槽数 | 见过 72 槽与 73 槽两种 | 槽位索引不可跨 build 复用，**按语义定位**（`/^[01];\d+$/`、`'top'`、`22`、`3`） |
| key 提取覆盖率 | 约 1/6 的 build 形状提不出（枚举 330 万组不中） | 用退出码重试换一份 build；实测重试 1 次内必过 |
| 风控/限速 | 短时间大量 `prehandle` 后，widget 可能不再渲染 | 停当批、冷却后重试（链路 K） |
| 站点不同 | 同一套 SDK 服务多个站点（本例 `appid=25199668`） | `sid`/`appid`/`entry_url` 随站点变，其余结构一致 |
