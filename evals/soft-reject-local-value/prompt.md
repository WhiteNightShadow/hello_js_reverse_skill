---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

我在做 shop-demo.example 的商品详情采集（接口是我们自己公司的，已授权）。接口 GET /api/item?id=...，请求头带 x-demo-sig。我用 Node 跑了页面的 SDK，本地能生成 x-demo-sig，格式和校验位都对，发出去 HTTP 200，但 body 是 {"error":70012,"data":null}。浏览器里页面同样的接口是正常的。同事说这肯定是 TLS 指纹，让我把 requests 换成 curl_cffi。这事接下来怎么查？先给我排查方案和你的判断，不用写代码，也先别跑任何请求。
