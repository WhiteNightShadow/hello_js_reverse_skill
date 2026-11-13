# 阿里云滑块（AliyunCaptcha / FeiLin）+ JSVMP 加密层 + 行为风控轨迹

> 难度：★★★★☆
> 还原方案：A（纯算法还原，最终运行不需要浏览器）
> 实现语言：Node.js
> 最后验证日期：2026-11-13
> 平台类型：通用（阿里云滑块验证码，站点侧只做转发）
> 适用范围：`FeiLin 1.5.4` / `feilin076.<hash>.js` + `dynamicJS/3.29.0/pe.0xx.<hash>.js`，2026-11-13 抓取
> 到达层级：**S3 命中（连续 5/5，gap 160~202）**；S4 可持续未验证（跨天/续期未测）
> 失效条件：bundle hash 变更（SEED 与 64 项表需重解）；站点风控策略调整；渲染缩放关系变化

本案例的结论只对上述范围成立，不是全局规则。

---

## 一句话结论

**这不只是密码学问题，是两个独立难点叠在一起**：

1. `data` 字段的加密层（JSVMP 字节码虚拟机里的一段自修改查表变换）——可以直接解出来，离线逐字节复现；
2. 滑块轨迹的**形态**——真人不是平滑曲线，而是「慢逼近 → 谷底犹豫 → 末端甩鞭 → 收尾」。

**只解决第 1 条会一直失败**（12 次全 false，即使几何 0.24px、flag 全 1、设备遥测 200）。
补上第 2 条后 **5/5 连续通过**。而且通过的那两次 `data` 长度只有 1304/1528，之前那些"精心构造"的 4688/16300 全 false。

---

## 技术指纹（候选线索）

### JS 特征
- [x] `o.alicdn.com/captcha-frontend/aliyunCaptcha/AliyunCaptcha.js`：入口，含 `initAliyunCaptcha`
- [x] `g.alicdn.com/captcha-frontend/FeiLin/<ver>/feilin0NN.<sha256>.js`：父 SDK，字符串池 = 自定义 base64 + 逐字节 XOR（XOR 键 44 个，如 68/139）
- [x] `g.alicdn.com/captcha-frontend/dynamicJS/<ver>/pe.0NN.<hash>.js`：**每次会话的 hash 不同**（由 InitCaptcha 响应的 `StaticPath` 指定）
- [x] `pe.0xx.js` 内含**字节码栈机 VM**：解释器 + 两段字节码（一段生成 nonce，一段做加密层）

### 参数特征
- [ ] `captchaVerifyParam`：JSON 信封 `{sceneId, certifyId, deviceToken, data}` → POST 站点 `?method=slideAuth`
- [ ] `data`：base64，解码后前 3 字节固定 `25 13 27`（`JRMn`）
- [ ] `deviceToken`：`base64("WEB#deviceId#cipherB64#len#" + MD5(前四段+"#daye,raolewoba!"))`
- [ ] `CertifyId` / `Image` / `PuzzleImage` / `StaticPath`：来自 InitCaptcha 响应

### 请求特征
- [ ] 首次进入页面自动 `POST https://<prefix>.captcha-open.aliyuncs.com/`（Action=InitCaptcha，阿里云 RPC + HMAC-SHA1 签名）
- [ ] 拖完才发站点侧 `slideAuth`，**判决只有两个布尔**，无错误码 → 无法用响应小步逼近
- [ ] 设备遥测 `cloudauth-device-dualstack.cn-shanghai.aliyuncs.com` 必须 200（`{"ResultObject":true,"Code":"200"}`）

### 反调试 / 环境特征
- [ ] `FeiLin` 启动时做 WebGL 指纹采集，会打印 `WebGL context was lost`（**正常，不是失败原因**）
- [ ] 目标页面常把 `#captcha-element` 设成 `position:absolute` 空 div、`#button` 设 `visibility:hidden`
- [ ] `navigator.webdriver` 为 true 时轨迹再像也判机器（换设备来源时注意）

### 混淆类型
- [ ] 字符串池（自定义 base64 + XOR）+ 控制流平坦化（CFF switch）+ **字节码 VM**

### 指纹检测规则（Agent 执行）

```
快速检测（30 秒内）：
  - scripts(action='list') → 出现 feilin0NN + dynamicJS/pe.0NN 两个 CDN 脚本
  - search_code("captchaVerifyParam") → 命中页面内联脚本
  - 看 data 解码后前 3 字节是否 25 13 27
匹配判定：以上 3 项全中 → 本案例的加密层结论可直接复用（需重跑 SEED 求解）
```

---

## 问题定位记录

```
现象：slideAuth 返回 HTTP 200 + {"captchaVerifyResult":false,"bizResult":false}
失败层：先判"动态值"（真的错了：4/3 长度关系误读），最终定位在【服务端策略】+【轨迹形态】
路线：R1 纯算法（data 完全离线）→ 但 S3 失败
      改成 R4/R5（浏览器内出值 + SendInput 注入）→ 仍失败
      回到 R1，但把轨迹换成真人形态 → 5/5 通过
结论强度：data 加密层【已证明】；轨迹形态是 S3 的必要条件【已证明】；
         是否还需别的条件【未定 — 5/5 都在同一小时内】
```

**关键的自我纠错**：一度在浏览器里调 `SendInput` 的坐标/焦点（`knob=(398,946)` 按下抓不住滑块），
连开 6 次浏览器都没结论。这类"注入工具"问题和目标本身无关——**纯协议根本不需要浏览器**。

---

## 还原方案（可直接照抄）

### 第 1 层：`data` 的加密

```js
// 1) payload = nonce_hex(32 字符) ‖ JSON（键顺序固定）
//    JSON: {TrackList, TrackStartTime, VerifyTime, xPos, slidePos, arg}
//    TrackList: {mc, tc, mu, te, mp, tmv, mm, ks, fi, startTime, si}

// 2) T = base64( zlib.deflate(payload, {level:6}) )     // T 恒以 "eJ" 开头

// 3) armour：无需密钥，只依赖构建常量
const TABLE = [32,50,10,51,6,44,37,16,46,11,62,19,43,25,23,30,
               60,33,53,34,7,26,12,48,5,2,20,4,61,13,47,49,
               18,29,27,22,1,17,39,56,41,38,55,31,15,58,52,40,
               8,57,45,35,59,36,42,54,63,3,24,28,14,9,0,21];
const SEED = '3e627e1b4c63f913';
// 阶段1：用 SEED 打乱 64 项表
for (let i = 0, t = 0; i < 64; i++) {
  t = ((((i + t) + R[i] + R[t]) >> 1) + SEED.charCodeAt(i % 16)) & 63;
  if (i !== t) swap3xor(R, i, t);
}
// 阶段2：逐字符变换（状态 e/a 自推进，表在过程中被自修改）
for (let i = 0, e = 0, a = 0; i < T.length; i++) {
  a = ((e ^ a) + (R[e] ^ R[a])) & 63;
  if (e !== a) swap3xor(R, e, a);
  let m = T.charCodeAt(i) + e + R[e];
  m = m - (a + R[a]);
  m = m ^ (R[e] + R[a]);
  m = m ^ R[(R[e] + R[a]) & 63];
  out[i] = m & 0xff;
  e = (e + 1) & 63;
}

// 4) data = base64(out)        // 长度 == |T|，前 3 字节天然是 25 13 27
```

**三个反直觉的点**：

1. **魔数 `25 13 27` 不是常量，是产物**——SEED 固定 + `T` 恒以 `eJ` 起步，前 3 字节自动算出来。
   这就是为什么静态搜 `251327` / `[37,19,39]` 永远搜不到。
2. **`|enc| = |T| − 3` 是误读**——`armour` 输出与 `T` **等长**，那 3 字节本来就是输出的前缀。
3. **没有密钥**——`DeviceConfig` 里那个每会话变化的 16 hex 值不参与这一步，别被它带偏。

`armour` 可逆：同样流程反着做一遍即可（`unarmour`），可用两组真实样本做往返校验。

### 第 2 层：轨迹形态（决定 S3 成败）

**这是本案例最值钱的部分。** 真人的轨迹不是平滑曲线：

```
慢逼近（占 45~60% 的帧，只走 15~30% 的距离，dt 4.5~6.5ms）
→ 谷底犹豫（3~6 帧，微位移 + dt 40~110ms，在"看缺口"）
→ 末端甩鞭（16~28 帧吃掉 86~94% 的距离，dt 按峰值反解让峰值落在 7000~12000 px/s）
→ 收尾（5~10 帧，dt 6~16ms）
```

配套扰动（缺一个都容易被分类器抓到）：

| 特征 | 真人数值 | 说明 |
|---|---|---|
| 峰值速度位置 | **74.5%（p50）** | 末端甩鞭，不是前载爆发 |
| 峰值速度 | **9722 px/s（p50）** | 平滑曲线的 ~400 px/s 差 24 倍 |
| `dx` 量化 | 0.42~0.58px 网格 | 真实鼠标的半像素取样，制造符号切换 |
| 零位移帧 | **4%** | 完全静止（真人会顿一下） |
| 中段回拉 | 1~3 次，0.8~2.2px | "对位置"的手感 |
| 末端回拉 | **55% 概率，3~12px** | 拖过头再拉回，6~13 帧负 `dx` |
| y 路径 std | **38px（p50）** | **手臂线性漂移**，不是小振幅振荡 |
| 事件数 | **127（p50）**，p10~p90 86~215 | 不是越多越像 |
| 总时长 | **1.62s（p50）** | — |

**y 的正确做法**：`y = drift * u + A * sin(πu)^1.7 * sin(2π·cycles·u)`
——线性漂移（25~90px，75% 向上）+ 温和振荡（8~18px），双端包络收敛。

### 第 3 层：几何（本站实测为线性）

```
slidePos = 手指位移 / 2.5          （受控标定：指令 600px → slidePos 240，6 样本 2.50±0.005）
xPos     = 拼图块最终位置 / 2.5
图片 296×200 → 渲染 750×500（容器 transform: scale(2.5)）
```

⚠️ 有公开项目测出**二次关系**（`piece.left = 0.0769·m + 0.003552·m²`，反解 `D=(-A+√(A²+4B·target))/(2B)`）。
**换站点必须重新标定，不要照抄系数**——同一家厂商不同集成方式会给出不同的缩放/映射。

---

## 踩坑清单（每条都有判据）

| 坑 | 教训 |
|---|---|
| 以为"点数越多越像人"，生成 543 点 / 4.4 秒 | **92~114 帧 / 0.88~1.24 秒**才通过；多反而是特征 |
| 用贝塞尔对称缓动（教科书式平滑） | **完美不可分**：30 条真人 vs 合成训分类器 AUC=1.000，平滑就是机器指纹 |
| 闭环"按块的实际位置回压手指" | 造出 `107 -35 -102 42 -58` 的**来回震荡**（屏幕上看就是指针乱抖），真人全程单调 |
| 看端点只回两个布尔就以为"没法定位" | 正因如此，只能用**控制组对照**：唯一变量是输入形态，结果 true/false 翻转 |
| `tempfile.mkdtemp = lambda: PROFILE` 复用同一 profile | device SDK 状态累积 → XHR `status 0`，看起来像风控拒绝，其实是**自己写脏了会话** |
| 把 `mm` 里最后一步 `137px` 当异常 tail | 那正是**末端甩鞭**，是真人最显著的特征 |
| 一度认定"必须真人/硬件设备" | 错。纯软件注入 5/5 通过，之前失败纯粹是形态错 |
| 在浏览器里调 SendInput 坐标/焦点 | 跑偏。**纯协议不需要浏览器**，先确认数据层能离线复现 |

---

## 验证

```
纯 Node 单命令：node e2e_run_chain.js --gen human --submit
  InitCaptcha → 检测 gap → 离线 data → slideAuth

post 13  gap=182  dataLen=1528  → {"captchaVerifyResult":true,"bizResult":true}
post 14  gap=169  dataLen=1304  → true
post 15  gap=160  dataLen=1404  → true
post 16  gap=166  dataLen=1752  → true
post 17  gap=202  dataLen=1384  → true
                                             5/5，gap 160~202，无浏览器
```

对照（同样纯 Node、同样几何精度、flag 全 1、device 200，只换轨迹形态）：

| 轨迹形态 | 结果 |
|---|---|
| 平滑贝塞尔 543 点 / 4.4s | 0/12 |
| 真人形态 92~114 帧 / 0.9~1.2s | **5/5** |

---

## 未解决

- **S4**：5 次都在同一小时内，跨天 / 连续续期未验证。
- `arg` 字段（10 字节 base64，事件级随机）语义未解——两次成功都用随机值，说明不影响判决。
- `si` 字段来源未解（沿用了真实样本的值）。
- 二次位移模型在本站未标定（线性标定已实测可用）。
