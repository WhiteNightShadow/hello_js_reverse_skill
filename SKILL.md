---
name: hello-js-reverse-skill
description: >
  通用 Web API 采集与前端签名问题的方法论。只要任务涉及抓接口或写 Node/Python 协议程序、sign/token/动态 Cookie/自定义头、
  本地生成的值服务端不认、HTTP 200 却是业务错误或空数据、浏览器能过本地不过、SDK 或接口改版失效、
  混淆/JSVMP/WASM/补环境/Hook/插桩、参数跟踪与版本归档，就使用本 Skill，即使用户没有提到“逆向”。
  配套 Camoufox MCP 取证，交付可验证的采集程序，支持分页、断点续采和改版回归。
  仅用于自有或已授权接口；微信小程序 wxapkg 解包使用对应小程序技能。
metadata:
  version: "3.11.1"
  mcp-compatible: "1.8.0（旧工作流兼容 1.6.x / 1.7.x；新参数需对应工具 schema；hook_jsvmp_interpreter 需 1.9.3）"
---

# 通用采集与签名分析

本 Skill 是方法论，回答三件事：问题在哪一层、走哪条链路、做到什么证据才算收口。

它不记录站点规则。域名、接口路径、字段、算法、错误码和 SDK 行为都来自当前目标。`cases/` 里的经验只是待验证的候选假设，换站点、换接口、换版本甚至换一天都可能不成立。`camoufox-reverse-mcp` 提供浏览器取证工具，同样不写站点特例。方法不绑定工具，换用其他浏览器或抓包工具时判断顺序不变。

## 启动与任务范围

**首次任务检查一次，继续操作复用，相关状态变化时只复查受影响项。** 规则见 [任务级检查](references/task-preflight.md)。

1. **按任务选路径**：代码维护和离线验签检查运行时与已有样本；普通采集确认鉴权、业务成功条件和分页；浏览器分析首次调用 `check_environment()`，并读 [浏览器取证契约](references/browser-evidence-contract.md)。不用浏览器的任务不必过浏览器门槛。
2. **复用证据**：先读需求工作区已有代码、任务记录与 `project-manifest.json`。遇到相应逆向特征时才查 [cases](cases/README.md)，命中后验证当前适用性。
3. **状态变化再重查**：浏览器重启或断连查环境与当前页；导航或 Frame 变化只查页面；SDK 或鉴权变化查相关基线和样本。`has_residuals` 可能是当前证据，不自动 reset。
4. **交付约定延续**：默认独立 Node.js/Python 协议程序，沿用用户已确认的字段、分页、鉴权和输出。用户明确要求页面自动化时可交付浏览器程序并声明依赖。

用户已提供的授权与偏好持续有效。沿现有实现完成当前需求，仅在缺少关键登录态、访问条件或无法推断的业务约定时请求必要信息。仓库发布按当前用户授权执行，Skill 自身不扩大授权。

## 先定义成功，再定位失败

成功分四层，下层推不出上层：

| 层级 | 含义 | 不算数的证据 |
|---|---|---|
| S1 能生成 | 本地产物结构合法 | 能跑出一个值 |
| S2 被接受 | 服务端没有拒绝 | HTTP 200 |
| S3 命中目标 | 响应正是请求的那份数据 | 响应非空 |
| S4 可持续 | 多目标、连续、续期、跨天都成立 | 单条成功、离线等价 |

失败分六层：传输、会话、请求形态、动态值、运行环境、服务端策略。403、空数据、错误码都可能来自任何一层，现象不定层，对照实验才定层。详见 [问题路由](references/problem-routing.md)。

## 问题路由

先按现象找到这一行，避开“先别下的结论”，再做第一步。

| 现象 | 先别下的结论 | 第一步 | 链路 |
|---|---|---|---|
| 只要数据，接口看起来没有签名 | 需要逆向 | 确认鉴权、业务成功条件和分页 | [通用采集](references/general-collection.md) |
| 带 sign、token 或自定义头，还没动手 | 这个参数一定要算 | 重放成功请求，再按组删减 | [链路 A](references/problem-routing.md#链路-a这个参数到底要不要算) |
| 别的接口或别的端需要某个头 | 这里也需要 | 按本接口单独验证，多发也可能被拒 | [链路 A](references/problem-routing.md#链路-a这个参数到底要不要算) |
| HTTP 200 里是错误码、空数据或错误页 | 签名或环境错了 | 读业务码，对比同期成功样本 | [链路 B](references/problem-routing.md#链路-b服务端拒绝) |
| 本地值结构合法但被拒 | 算法错了 | 恢复控制组，做来源替换 | [链路 B](references/problem-routing.md#链路-b服务端拒绝) |
| 控制组也失败 | 候选失败了 | 停止归因，先恢复基线 | [控制组失效](references/controlled-experiments.md#控制组失效) |
| 超时、连接失败、没发出去 | 被拒绝了 | 单独分类，确认实际尝试次数 | [结果分类](references/controlled-experiments.md#结果分类) |
| 改了一项没变化 | 这一项无关 | 可能两道闸门并联，做交叉矩阵 | [交叉矩阵](references/controlled-experiments.md#单变量没有翻转时) |
| 同一构造时好时坏 | 修好了或坏了 | 开稳定性批次，报成功数和翻转数 | [稳定性批次](references/controlled-experiments.md#结果时好时坏) |
| 浏览器能过，本地同样的头不过 | TLS 指纹 | 先排除已用值和会话，再做传输对照 | [链路 C](references/problem-routing.md#链路-c浏览器能过本地同样的头不过) |
| 之前能用，现在不行 | 代码坏了 | 比对 SDK 哈希，从最后成功基线回归 | [链路 D](references/problem-routing.md#链路-d之前能用现在不行) |
| SDK 本地报错 | 补上报错这一项就好 | 沿调用链找真实缺口 | [链路 F](references/problem-routing.md#链路-fsdk-在本地跑不起来) |
| SDK 能跑，值不被接受 | 再多补些环境 | 做读值差异，查首次读取缓存 | [链路 E](references/problem-routing.md#链路-e本地值能生成但不被接受) |
| 固定输入下值和浏览器不同 | 算法全错 | 逐环节找首个偏差 | [签名值不一致](references/troubleshooting.md#签名值不一致排查) |
| 值带随机掩码，无法逐字比较 | 无从下手 | 分批采样，分析信封和结构 | [不透明令牌](references/opaque-token-analysis.md) |
| 混淆或 VM 挡住定位 | 一定要读懂 | 先问是否需要读懂，再定 I/O 边界 | [链路 G](references/problem-routing.md#链路-g混淆或-vm-挡住定位) |
| 响应加密、WASM、WebSocket、字体映射 | 通用手段都能解 | 按对应场景取证 | [场景配方](references/analysis-scenarios.md) |
| 动态 Cookie 来源不明 | 是 JS 写的 | 同时看 Set-Cookie 和 JS 写入 | [Cookie 归因](references/analysis-scenarios.md#cookie-归因分析) |
| 首屏挑战、反调试 | 先装 Hook | 首次不加 Hook，先看响应链 | [反调试](references/anti-debug.md) |
| Hook 没日志、插桩后行为变了 | 目标没执行或有检测 | 查 world、Frame、覆盖，比较原始与插桩 | [链路 I](references/problem-routing.md#链路-i观测本身有问题) |
| 单条成功，批量失败 | 算法不稳 | 看失败与次数、时间、账号的相关性 | [链路 H](references/problem-routing.md#链路-h单条成功批量失败) |
| 429、验证页、账号受限 | 换个身份继续 | 停止当批，确定影响范围，恢复后用原目标复验 | [链路 K](references/problem-routing.md#链路-k频控验证或账号受限) |
| 单条耗时不符合预期 | 接口慢 | 拆开调度、初始化、出值、网络 | [链路 J](references/problem-routing.md#链路-j慢) |
| 要持续跟踪参数或版本 | 记一份结论就够 | 分开记录版本身份，结论带范围 | [参数跟踪](references/version-tracking.md) |

## 路线选择

**诊断从重到轻，交付从轻到重。** 诊断时先用最接近真实的路径证明此刻做得成，再一次拿掉一个依赖，第一个让结果变坏的依赖就是问题所在。交付时选能成立的依赖最少的路线。

| 路线 | 做法 | 上移的信号 |
|---|---|---|
| R0 不生成 | 接口不校验这一项，直接不发 | 换接口或换日期复验失败 |
| R1 纯算法 | Node/Python 库复现 | 算法依赖闭包状态或环境 |
| R2 片段执行 | 提取函数放进 vm/execjs | 依赖 DOM、存储或大量全局状态 |
| R3 补环境 | jsdom/vm 运行 SDK，按读值补齐 | 补丁不收敛，或静态值对齐后仍被拒 |
| R4 浏览器级运行时 | 真实引擎运行原始 SDK | 所需状态只存在于真实长驻页面 |
| R5 页面出值、本地发送 | 页面生成未使用的值，本地 HTTP 发送 | 传输确实绑定页面 |
| R6 页面内请求 | 请求由页面自身发出，需用户接受此依赖 | 无 |

不必为了还原算法而还原，目标是取得可用的值。R4、R5 仍依赖外部提供会话，不能写成“无浏览器”。详见 [路线阶梯](references/problem-routing.md#路线阶梯)、[原始 SDK 运行](references/original-sdk-runtime.md)、[签名来源隔离](references/signature-source-isolation.md)。

## 在线实验的纪律

在线请求会消耗账号额度、一次性值和风控状态，所以用尽量少的请求排除假设。完整方法见 [对照实验](references/controlled-experiments.md)。

- **先有控制组**。真实路径此刻成立，候选的结果才有意义。控制组失败时停止归因，不写“候选失败”。
- **发送前过门禁**。版本一致、凭据余量够、值未用过、输入成套，不满足就不发。
- **单变量要回读**。用实际发出的请求核对只改了声称的变量，再写结论，脚本意图不算数。
- **单变量没翻转不等于无关**。可能两道闸门并联，用交叉矩阵确认后才能排除。
- **测量手段先过对照**。工具没看到差异，要先证明它看得见。
- **结果分类不合并**。`not_sent`、`transport_error`、`rejected`、`accepted`、`target_ok` 分开记录，超时不是拒绝，未发送不是失败。
- **遇拒绝停止当批**。继续前要能说清这次和上次差在哪、预期是什么，不用重试或加速碰运气。
- **结论带范围和强度**。写明接口、版本、日期，用观察、支持、排除、证明表达强度。避免“唯一”“必须”“硬墙”。
- **组合成功不等于单项根因**。要归因到某一项需要消融，业务不需要时可以不做，但不能那样写。
- **写错了就纠偏**。原始证据不动，在结论处加日期化说明，并写清哪些结论不受影响。

`scripts/experiment-ledger.py` 提供门禁、台账和回读核对。

## 通用采集

普通 JSON API 不必进入逆向流程，先读 [general-collection.md](references/general-collection.md)。

- `templates/python-request/collect.py` 是可运行的通用入口，`utils/collector.py` 可接入自定义签名与鉴权回调，支持去重、JSONL 和断点恢复。核心只用标准库；有依赖限制时配 urllib 回调即可。
- 空中间页、显式 has_more、临时重复游标、业务重试与页数限制按接口契约启用，默认行为保持兼容。模板不是无需适配的全站方案。
- 每次请求现算动态签名。凭据来自用户配置、合法登录态或协议刷新过程，不把一次抓取的临时 Cookie 写死到公共模板。
- 默认重试只用于 GET/HEAD/OPTIONS。POST 等请求发生不确定失败时，先确认幂等条件再重放。

## 验证、交付与改版

- 验收按任务类型选择：采集和 API 签名任务用代表性新输入、分页、结束和失败路径验证（建议至少 5 次，遵循用户约定并记录实际数量）；WASM 和脚本取证验证来源、完整字节、哈希和真实调用；代码维护运行相关回归。不要为了统一清单制造无关请求或额外项目。
- 单条通过、离线等价、多目标、连续、续期、跨天分别标状态，未运行的不得宣称通过。模板 `npm test` 与 `python test.py` 是离线组件测试，不能替代任务验收。
- 交付程序、配置说明、数据样本、验证结果和已知限制。协议模式最终运行不依赖浏览器；依赖外部会话时写清谁提供、谁续期。无法完成时记录事实、已尝试路径与剩余依赖，不伪造签名或成功响应。
- 收口时写五项：到达层级、当前路线与外部依赖、适用范围、结论强度、失效条件。格式见 [收口格式](references/problem-routing.md#收口格式)。
- 用 `scripts/project-baseline.py` 记录 SDK、签名代码和脱敏 fixture 的哈希与版本身份，改版时先 `check` 定位差异。哈希未变不代表接口行为未变，仍需回归。
- 新发现先记录在需求工作区。一条经验只有在不依赖站点时才进入 `references/`：能在不同体系上成立，或能用公开样本复现。否则按 [cases/_template.md](cases/_template.md) 脱敏留在案例里，标明版本、日期和验证边界。不把登录态、真实密钥或私有请求样本提交到公共仓库。

## 按需参考

| 当前需要 | 参考 |
|---|---|
| 完整链路、路线阶梯、收口格式 | [problem-routing.md](references/problem-routing.md) |
| 实验设计、门禁、归因 | [controlled-experiments.md](references/controlled-experiments.md) |
| 未使用的值、绑定、新鲜度 | [signature-source-isolation.md](references/signature-source-isolation.md) |
| 运行原始 SDK、状态回放、生命周期 | [original-sdk-runtime.md](references/original-sdk-runtime.md) |
| 令牌信封与版式 | [opaque-token-analysis.md](references/opaque-token-analysis.md) |
| 版本身份、结论范围、归档 | [version-tracking.md](references/version-tracking.md) |
| 浏览器抓包、Hook、插桩、原生追踪的证据边界 | [browser-evidence-contract.md](references/browser-evidence-contract.md) |
| 首检复用与状态失效重查 | [task-preflight.md](references/task-preflight.md) |
| 通用采集、恢复、自定义签名与基线 | [general-collection.md](references/general-collection.md) |
| 工具参数和兼容边界 | [mcp-tool-reference.md](references/mcp-tool-reference.md) |
| 深度分析阶段 | [phase-details.md](references/phase-details.md) |
| JSVMP 路径 A / B、源码插桩 | [path-a-four-tools.md](references/path-a-four-tools.md) / [path-b-env-emulation.md](references/path-b-env-emulation.md) / [jsvmp-source-instrumentation.md](references/jsvmp-source-instrumentation.md) |
| 环境补丁与 UA 一致性 | [jsdom-env-patches.md](references/jsdom-env-patches.md) |
| 反混淆改写的语义验证 | [transform-validation.md](references/transform-validation.md) |
| 传输层与协议问题 | [protocol-analysis.md](references/protocol-analysis.md) |
| 具体场景与常见误判 | [analysis-scenarios.md](references/analysis-scenarios.md) / [common-pitfalls.md](references/common-pitfalls.md) / [troubleshooting.md](references/troubleshooting.md) |
| 公开样本的本地实战 | [real-source-cases.md](references/real-source-cases.md) |
| 维护 Skill/MCP 的独立 Agent 评测 | [agent-validation.md](references/agent-validation.md) |

## 更新记录

- v3.11.1（2026-11-10）：JSVMP 探针日志改用 `evaluate_js(..., world="main")` 读取，配合 MCP v1.9.3 把探针装在页面主世界。
- v3.11.0（2026-11-10）：Skill 名称改为 `hello-js-reverse-skill`，符合 Agent Skills 命名规范；安装目录名需与名称一致，模板目录和引用路径不变。
- v3.10.0（2026-11-05）：主干改为问题路由与路线阶梯；新增对照实验、签名来源隔离、原始 SDK 运行、不透明令牌、参数跟踪方法与配套脚本；吸收公开 skill 库的并联闸门、概率门、A/A 对照等方法；工具级细节移入取证契约；清理把单站经验写成全局规则的内容和已失效的工具名。
- 历史版本与详细差异见 Git tags / Releases。模板目录和引用路径保持不变，避免已有引用失效。
