---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

下面是负对照脚本和报告，报告结论是“唯一变量是 x-demo-sig，已证明服务端校验 sig 新鲜度”。这个结论上周已经写进文档，同事都在引用。帮我核一下，有问题的话文档该怎么改。

```python
def build(sig, rid):
    return {"x-demo-sig": sig, "x-demo-rid": rid, "x-demo-nonce": secrets.token_hex(8), **fixed_headers}

# A：浏览器新 sig
resp_a = send(build(browser_sig, browser_rid))
# B：本地新 sig
resp_b = send(build(local_sig, local_rid))
# D：负对照，A 已用过的 sig + B 的 rid
resp_d = send(build(browser_sig, local_rid))
```

结果：A 成功，B 成功，D 返回 error=70012。
