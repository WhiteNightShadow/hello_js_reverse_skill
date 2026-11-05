# 旧经验法则的去向

v3.10.0 起不再维护“经验法则”清单。旧的 30 条来自少数站点的实战，很多把单站结论写成了全局规则。原文移到 [cases/historical-experience-rules.md](../cases/historical-experience-rules.md) 作为历史资料，现行方法见 [问题路由](problem-routing.md)。

保留此文件路径供已有链接访问。下表说明每条旧规则现在怎么处理：

| 旧规则 | 处理 | 现行位置 |
|---|---|---|
| 1 反爬类型识别先行 | 保留“首次不加 Hook 看响应链”，三分法降为选观测手段的线索 | [phase-details](phase-details.md) |
| 2 JSVMP 只有一条路 | 废弃绝对说法 | [路线阶梯](problem-routing.md#路线阶梯) |
| 3 Cookie 归因优先 | 保留，改为手动归因 | [Cookie 归因](analysis-scenarios.md#cookie-归因分析) |
| 4 某类反爬永远不用预注入 | 废弃绝对说法，改为比较原始与观测结果 | [链路 I](problem-routing.md#链路-i观测本身有问题) |
| 5 用特定字段区分 SDK 变体 | 单站结论，留在案例 | [cases](../cases/README.md) |
| 6 从请求发起栈定位 | 保留，注意 `match_confidence` | [取证契约](browser-evidence-contract.md) |
| 7 优先用 Hook 预设 | 保留 | [场景配方](analysis-scenarios.md) |
| 8 源码插桩优先 | 改为 VM 自包含时的选项 | [源码插桩](jsvmp-source-instrumentation.md) |
| 9 重载让 Hook 先生效 | 保留 | [场景配方](analysis-scenarios.md) |
| 10 大文件指定脚本搜索 | 保留 | [路径 A](path-a-four-tools.md) |
| 11 `compare_env` 是补环境起点 | 改为从 SDK 实际读值开始 | [读值差异](original-sdk-runtime.md#读值差异) |
| 12 双通道都要 Hook | 改为先确认入口和通道 | [定位入口](original-sdk-runtime.md#定位入口) |
| 13 AST 在挑战页可用 | 工具细节，以当前契约为准 | [源码插桩](jsvmp-source-instrumentation.md) |
| 14 CSP 可能阻断插桩 | 保留 | [取证契约](browser-evidence-contract.md) |
| 15 响应链默认开启 | 保留 | [工具契约](mcp-tool-reference.md) |
| 16 环境复现快 10 倍 | 废弃，单站耗时不能外推 | [路线阶梯](problem-routing.md#路线阶梯) |
| 17 `toString` 是头号问题 | 改为 jsdom 路线的常见候选 | [补丁模板](jsdom-env-patches.md) |
| 18 环境对比分批采集 | 保留 | [路径 B](path-b-env-emulation.md) |
| 19 补丁在加载前完成 | 保留并扩展为先 seed 后 init | [生命周期](original-sdk-runtime.md#生命周期先-seed后-init) |
| 20 静默拒绝说明环境失败 | 废弃，软拒绝可能来自任何一层 | [链路 B](problem-routing.md#链路-b服务端拒绝) |
| 21 native code 格式因浏览器而异 | 保留 | [路径 B](path-b-env-emulation.md) |
| 22 某初始化参数必传 | 单站结论，通用化为照页面真实调用传配置 | [路径 B](path-b-env-emulation.md) |
| 23 先确认签名入口 | 保留 | [定位入口](original-sdk-runtime.md#定位入口) |
| 24 能轻则轻 | 改为诊断从重到轻、交付从轻到重 | [问题路由](problem-routing.md#三诊断从重到轻交付从轻到重) |
| 25 TLS 是终极壁垒 | 废弃，要用对照确认 | [链路 C](problem-routing.md#链路-c浏览器能过本地同样的头不过) |
| 26 逐环节找首个偏差 | 保留 | [troubleshooting](troubleshooting.md#签名值不一致排查) |
| 27 预热请求不是装饰 | 保留 | [troubleshooting](troubleshooting.md) |
| 28 vm 不等于浏览器 | 保留 | [environment-patch](environment-patch.md) |
| 29 降级梯度逐级走 | 改为按证据移动，不机械逐级 | [路线阶梯](problem-routing.md#路线阶梯) |
| 30 案例价值随次数增长 | 保留，并增加提升为方法的条件 | [cases](../cases/README.md#按需沉淀新案例) |
