# 电商 H5 商品详情多入口：登录态门与签名门的判据分离

> 难度：★★☆☆☆
> 还原方案：D: 用户明确要求的浏览器/协议取证（未进入签名还原）
> 实现语言：Python (urllib) + Camoufox MCP 取证
> 最后验证日期：2026-11-24
> 平台类型：电商平台（抖音电商 haohuo / ec.snssdk.com）
> 适用范围：`haohuo.jinritemai.com` 新版分享页 `/ecommerce/trade/detail/index.html` 与老版详情页 `/views/product/item2`；商品 ID `3534123999602842315`；**未登录**会话；MCP v1.12.0 / Camoufox 152.0.4-beta.30-reverse.5
> 到达层级：S2（拿到服务端判据，未达 S3 命中目标数据）
> 失效条件：任一条链路的域名、接口路径或错误码变化；登录态引入后需重测全部结论

本案例的结论只对上述范围成立，不是全局规则。

---

## 一句话结论

**同一个商品、同一个平台，两条 H5 入口的判据完全不同**：新版分享页要「动态签名 + 会话环境」，老版详情页只校验「登录态」，而且后者会直接把缺什么写在 `msg` 里。拿到零字节响应时，先换入口比判据，比先逆向签名便宜一个数量级。

---

## 技术指纹

### 请求特征

- 新版分享页：CSR 空壳 HTML（约 11.9 KB，`<title></title>`），数据全部来自
  `POST /aweme/v2/shop/promotion/pack/h5/?is_h5=1&is_native_h5=1&origin_type=detail_share&verifyFp=…&msToken=…&a_bogus=…`
  body 为 urlencoded：`ui_params={...}&use_new_price=1&is_h5=1&bff_type=2&is_in_app=0&origin_type=detail_share&promotion_ids=<商品ID>&isFromVideo=false&enable_timing=true&is_new_h5_bff=1`
- 同页另有两条干扰接口：`/ecom/product/detail/h5/sc/` 只返回 TCC 开关配置（`hspc`/`period`/`top_notice_banner`），`/ai/getGptGeneratedProductDesc` 只返回 AI 生成的卖点文案
- 老版详情页：CSR（静态资源在 `ecom-xiaodian-cdn/product/staticV3`），`<title>商品详情</title>`，数据来自 `snssdk.com` 域：
  - `GET https://ec.snssdk.com/product/fxgajaxstaticitem?&verifyFp=…&b_type_new=0&device_id=0&is_outside=1&id=<商品ID>&preview=0&is_native_h5=1&is_in_app=0&aid=0&page_url=…`
  - `GET https://ec.snssdk.com/product/ajaxitem?b_type_new=0&device_id=0&is_outside=1&id=<商品ID>&abParams=0&is_in_app=0`
  - 旁路：`/product/getstock`、`/order/userproductnum`、`/cart/cartNum`、`ken.snssdk.com/pack/product/detail`、`ken.snssdk.com/pay/getPayForms`

### 参数特征

- `a_bogus`：动态签名，长度约 40–48 字符，字符集含 `%2F`/`%2B` 转义；同机同分钟内多次加载值不同（实测 `YyUdfc23…` / `OfUxXO23…` / `x6lDDO23…`），绑定 query 顺序、`msToken`、`verifyFp` 与 UA
- `msToken`：约 107–128 字符，含 `=` 填充，出现在 query 与 `mssdk.bytedance.com/web/common` 请求里
- `verifyFp`：等于 `s_v_web_id` cookie 值（形如 `verify_xxxx_yyyy`）
- `ttwid`：HttpOnly + Secure，`ttwid/check` 通过后由服务端下发到 `Domain=jinritemai.com`

### 反调试特征

- 未观察到 `debugger` 陷阱；阻挡来自服务端响应形态，不在前端

---

## 问题定位记录

```
现象：入口 A（新版 pack/h5）HTTP 200 且响应体 0 字节；页面渲染"检测到当前环境存在安全风险"
失败层：服务端策略（渠道/环境判定），依据：ttwid check pass + a_bogus 存在的情况下仍 0 字节
路线：R6（页面内请求）用于取证；目标路线未定
结论强度：观察（入口 A 的门未知）+ 证明（入口 B 的门是登录态，服务端文案直接给出）
```

---

## 已验证定位路径

```
步骤 1: launch_browser + network_capture(start, capture_body=True) → navigate 新版分享页
        观察：66 条请求里只有 3 条自家接口；pack/h5 是唯一装数据的
步骤 2: get_network_request(58) 取 pack/h5 完整请求
        —— 必须用 get_network_request，列表里的 url 被预览截断（v1.13.1 前的缺陷）
步骤 3: 用 Python 复现 pack/h5（自带 ttwid，无签名）→ {"code":11001,"msg":"当前网络不稳定"}
        → 说明这条链路确实校验动态签名
步骤 4: 换移动 UA / is_in_app=1 重放 → HTTP 200 + 0 字节
        → 形态变了但仍是拒绝，说明签名不是唯一闸门
步骤 5: 换入口：navigate 老版 /views/product/item2?id=<商品ID>
步骤 6: 读 ec.snssdk.com/product/ajaxitem 响应 → {"code":"10001010A","msg":"用户未登录，请登录后重试"}
        → 一条响应直接给出判据，无需任何签名分析
```

---

## 关键经验总结

### 1. 零字节响应 ≠ 签名缺失

入口 A 上有三种可区分的形态，指向完全不同:

| 形态 | 实测响应 | 判读 |
|---|---|---|
| 桌面 UA + ttwid、无签名 | `{"code":11001,"msg":"当前网络不稳定","st":11001}` | 动态值缺失（真该逆向） |
| 移动 UA、无签名 | HTTP 200，**0 字节** | 环境/渠道判定，签名不是主因 |
| 浏览器内、a_bogus 存在 + ttwid pass | HTTP 200，**0 字节** + 页面提示环境风险 | 同上；补签名也过不去 |

### 2. 换入口是最便宜的一次分层实验

同一份业务数据往往有多个前端实现（新版 BFF / 老版 BFF / App 网关）。它们对同一会话的判据可以完全不同，而老实现的错误码经常**直接把缺什么写在文案里**。先跑一遍换入口，再决定要不要投入签名还原。

### 3. ttwid 可以自行注册，且与业务域无关

```
POST https://ttwid.bytedance.com/ttwid/union/register/
body: {"region":"cn","aid":1522,"needFid":false,"service":"<目标域>",
       "migrate_info":{"ticket":"","source":"node"},"cbUrlProtocol":"https","union":true}
→ 200 {"status_code":0,"redirect_url":"https://<目标域>/ttwid/union/register/callback/?aid=1522&ticket=…"}
   Set-Cookie: ttwid=…; Domain=bytedance.com
→ 跟随 redirect_url（带同一 cookie jar）→ 服务端在目标域下发 ttwid
→ POST https://<目标域>/ttwid/check/ {"aid":1522,"service":"<目标域>","unionHost":"https://ttwid.bytedance.com",
       "needFid":false,"union":true,"fid":"","migrate_priority":0}
→ 200 {"status_code":0,"message":"check pass","sub_status_code":2001}
```

先做这一步，才能把「会话没建起来」和「签名不对」分开。

---

## 可验证事实清单

- [ ] 新版分享页的 pack/h5 是唯一装商品数据的接口（同页 `sc` 只回 TCC 配置）
- [ ] 该接口 query 含 `verifyFp` / `msToken` / `a_bogus` 三件套
- [ ] 桌面 UA 无签名 → `code 11001`；移动 UA 无签名 → 200 + 0 字节
- [ ] `ttwid/check` 返回 `check pass` 时 pack/h5 仍可能 0 字节
- [ ] 老版 `/views/product/item2` 走 `ec.snssdk.com`，未登录返回 `10001010A 用户未登录`

---

## 假设与纠偏

| 当时的假设 | 推翻它的证据 | 现在的结论 |
|---|---|---|
| pack/h5 被拒是因为请求没带 `a_bogus` | 抓到带 `a_bogus` 的真实请求（request 146/183），响应仍是 0 字节 | `a_bogus` 是必要条件之一，但不是这条链路当前的卡点 |
| 「列表里没看到 a_bogus」= 请求没带 | `get_network_request` 返回的完整 URL 尾部就是 `&a_bogus=…`；列表是 200 字符静默截断 | 读 URL 参数必须取完整值（MCP v1.13.1 起预览带 `…` 与 `url_truncated`） |
| 这条链路需要把签名还原出来才能取数 | 换入口后服务端直接回「用户未登录」 | 先定层：这是登录态问题，不是算法问题 |
| 没有 root 手机就拿不到 App 侧数据 | 该商品详情在 App 内也是 web 页面（HTTP + TLS） | 代理 + CA 证书即可取证，root 只影响原生接口的 Pinning |

---

## 踩坑记录

| # | 坑 | 现象 | 解决方法 |
|---|---|---|---|
| 1 | 用请求列表里的 URL 判断参数有无 | URL 在 `msToken` 处结束，看起来没有签名参数 | 用 `get_network_request` 取完整 URL；或读 `url_truncated` |
| 2 | 把 `is_in_app=0` 当作「不支持外部访问」 | 该值在正常外部访问下也是 0 | 判据在登录态，不在这个开关 |
| 3 | 把老版页面的 `device_id=0` 当作参数缺失 | 未登录态下就是 0 | 登录后再取真实值 |
| 4 | 拿 `ken.snssdk.com` 的 502 当接口报废 | 同批 `pay/getPayForms` 也是 502 | 502 是网关侧拒绝，先看同域其他接口再判断 |

---

## 变体说明

| 变体 | 差异点 | 影响 |
|---|---|---|
| 新版 `/ecommerce/trade/detail` | BFF `promotion/pack/h5`，三件套签名 | 需要会话环境 + 签名，未登录几乎拿不到 |
| 老版 `/views/product/item2` | `ec.snssdk.com/product/*`，仅登录态 | 有登录 Cookie 即可直接回 JSON |
| App 内打开 | 同一 web 页面，UA/渠道不同 | 抓包即可，无需 root |
