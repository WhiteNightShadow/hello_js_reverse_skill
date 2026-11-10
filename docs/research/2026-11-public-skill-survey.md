# 公开 skill 库与方法论调研（2026-11-05）

本轮迭代前检查了 GitHub 上约 80 个相关仓库，记录借鉴了什么、证据到什么程度、什么没有借鉴。元数据来自当天的 GitHub API。没有运行下载的任何代码，下文的“CI 成功”只代表对方的 CI 记录。

结论：公开世界里有不少逆向类 skill，但方法层普遍偏工具绑定或站点绑定。本仓库的“未使用的值”和“哨兵实验”没有找到公开同类，中文论坛和公众号未覆盖，所以这只说明 GitHub 上没搜到。

## 借鉴的方法

证据状态：**已验证**指有公开可核的运行结果，只验证它声明的那一层；**作者实测**指写了过程但数据不公开；**说法**指只有方法描述。

| 方法 | 落点 | 出处 | 证据状态 |
|---|---|---|---|
| 并联闸门与交叉矩阵 | [对照实验](../../references/controlled-experiments.md#单变量没有翻转时) | [site-accessibility-recon](https://github.com/neoLsH/site-accessibility-recon) `references/cases/01-orthogonal-gates.md`；[js-reverse-skill](https://github.com/erma0/js-reverse-skill) `references/network/ip-risk-control.md` | 作者实测 |
| 概率门与稳定性批次 | [对照实验](../../references/controlled-experiments.md#结果时好时坏) | site-accessibility-recon `references/evidence-matrix.md` | 区间计算有 CI，阈值只是单案例，未采用 |
| A/A 与阳性对照 | [对照实验](../../references/controlled-experiments.md#测量手段先过对照) | [ff-ruyijs](https://github.com/cutetailbud/ff-ruyijs) `docs/tls-profile-report.zh-CN.md` | 已验证（方法层） |
| 声明原始输入，派生值不作入参 | [原始 SDK 运行](../../references/original-sdk-runtime.md#声明原始输入) | [ai-reverse-resources](https://github.com/zhizhuodemao/ai-reverse-resources)（无 license，只取思路） | 说法 |
| 诱饵症状 | [常见误判](../../references/common-pitfalls.md) | [js-reverse-ops](https://github.com/DQmyth/js-reverse-ops) `references/misdiagnosis-patterns.md` | 靶场有 CI，靶子是作者自写 |
| 离线校准 | [在线门禁](../../references/controlled-experiments.md#在线门禁) | js-reverse-ops `references/env-rebuild-recipes.md` | 作者实测 |
| API 三态 | [读值差异](../../references/original-sdk-runtime.md#读值差异) | ai-reverse-resources（只取思路） | 作者实测 |
| 改写分级判定 | [改写验证](../../references/transform-validation.md#分级判定) | [JsDeObsBench](https://arxiv.org/abs/2506.20170)；[wakaru](https://github.com/pionxzh/wakaru) `docs/test262-roundtrip.md`；[restringer](https://github.com/HumanSecurity/restringer) | 论文实测（范围仅 javascript-obfuscator）；wakaru 有 CI |
| 传输特征字段与回显 | [协议层分析](../../references/protocol-analysis.md#比较实际发出的传输特征) | [curl_cffi](https://github.com/lexiforest/curl_cffi) 文档、[pingly](https://github.com/0x676e67/pingly) | 说法 |
| 结论依据与替代关系 | [参数跟踪](../../references/version-tracking.md#结论怎么写) | [reverse-engineering-knowledge-base](https://github.com/Facetomyself/reverse-engineering-knowledge-base)（无 license，只取设计） | 说法 |
| 观测一致性分三态 | [问题路由](../../references/problem-routing.md#链路-i观测本身有问题) | [web-jsvmp](https://github.com/Facetomyself/web-jsvmp) `references/observation-integrity.md` | 说法 |
| 长期运行页面出值 | [签名来源隔离](../../references/signature-source-isolation.md#长期运行页面出值) | [jsrpc-skill](https://github.com/heart147/jsrpc-skill) | 说法 |
| 评测用压力场景、新旧同轮对比 | `evals/` | [superpowers](https://github.com/obra/superpowers) `skills/writing-skills/`；[skill-creator](https://github.com/anthropics/skills) | 流程真实存在，效果无公开数据 |

## 没有借鉴的

| 对象 | 原因 |
|---|---|
| 单一工具绑定的强制流程 | 与“方法不绑定工具”冲突 |
| 练习站结论和具体阈值（样本数、失败预算、重试次数） | 单案例经验，不能进主干 |
| 自评的成功率数据 | 语料私有，无法复核 |
| 吞掉异常的补丁做法 | 与按报错定位冲突 |
| 站点命名的 AST 规则、随包二进制 | 站点专用，二进制无法审计 |
| GPL、AGPL 代码，JA4+ 实现 | 授权不适合内嵌，JA4+ 另有专利声明 |
| 无 license 仓库的文字 | 只取思路，不抄文字 |
| 运行时工具宣称“能过某系统”的列表 | 未经验证 |
| 高 star 本身 | 部分仓库的 star 数明显异常，不作质量依据 |

## 未核实的部分

- ruyiJS、iv8、sdenv 的实际效果没有在本轮测试。
- 中文论坛、公众号、知识星球未覆盖。
- Anthropic 官方最佳实践页未直接读到，读的是第三方仓库里的副本。

后续可做：把触发词集分成训练集和测试集，用真实运行优化 description（`hello_js_reverse_skill` 的名字含下划线，不符合 agentskills 规范，v3.11.0 已改为 `hello-js-reverse-skill`）。
