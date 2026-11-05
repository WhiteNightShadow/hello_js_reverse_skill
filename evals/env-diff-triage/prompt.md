---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

页面 SDK 放进本地运行时能出值，已经确认问题在本地值上：浏览器新值能过，同模板换本地值被拒。我 diff 了环境，差异表有 40 多项：outerWidth、screenX、hasFocus、elementFromPoint、performance 条目数、navigator.plugins、window.chrome、__pw_recorder 等，其中十几项本地是 undefined，真实浏览器也是 undefined。我打算把这 40 多项全部补上，然后在 SDK 初始化完成后再把最新的 Cookie 和 localStorage 刷进去。可以吗？你建议怎么做？
