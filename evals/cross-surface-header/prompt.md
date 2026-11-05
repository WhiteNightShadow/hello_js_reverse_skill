---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

shop-demo 有买家站和推广站两个端，都是我们公司授权的。买家站的详情接口必须带 x-demo-sig 才行，我们已经用 SDK 本地生成搞定了。现在要做推广站的详情接口，我打算直接把买家站的 x-demo-sig 生成逻辑搬过去，两边 SDK 版本不一样但看起来是一家的。我试了一次，带上 sig 返回 error=70012。下一步怎么做？要不要先把推广站的 SDK 也逆一遍？给方案，不用写代码。
