---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

shop-demo.example 的详情接口（公司自己的，已授权）本地一直被拒，HTTP 200 error=70012。我做了两次实验：1）把本地 requests 换成 curl_cffi，其余不变，还是 70012。2）把本地生成的 x-demo-sig 换成页面刚生成、没发过的新值，其余不变，用 requests 发，还是 70012。页面自身请求此刻是成功的。我的结论是 TLS 和 sig 都不是问题，应该是账号被风控了。这个结论对吗？下一步怎么做？给方案，不用写代码，先别发请求。
