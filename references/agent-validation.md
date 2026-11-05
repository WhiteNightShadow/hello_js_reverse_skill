# Skill / MCP 改动的行为验证

维护技能或底层工具时才使用本流程，普通业务采集任务不需要先启动评测。单元测试验证组件，独立 Agent 实操验证指令能否指导真实任务，两者不能互相替代。

1. 检查可信公开源码与测试，记录固定版本、采用的设计和未验证的限制。不要按工具数量或宣传承诺引入功能。
2. 修改后先在本地冻结候选；验证前不提交/发布。将任务说明、场景数据和评分答案分开保存。
3. 给多个新上下文 Agent 自然语言任务、候选 Skill/工具和必要连接方式，不提供预期解法、疑似缺陷或其他 Agent 答案。
4. 浏览器任务真实走 MCP 协议，各自独立进程；普通协议任务按需用本地程序。保留开始/结束、参数、实际错误、耗时、产物与版本。
5. 用独立程序验收新的签名输入/响应、资源字节/执行、数据完整性/恢复等。检查模型是否重复首检、误清理、猜路径或假报成功。
6. 即使产物通过，也读取 Agent 的具体使用反馈。修正真实发现的问题后换输入和新 Agent 复验；不能删掉失败记录或只算成功分支。
7. 行为复验、回归、工具契约和构建通过后再按用户授权提交/发布，报告覆盖范围与剩余限制。

本轮公开研究和方法见配套 MCP 的 [RESEARCH_AND_VALIDATION.md](https://github.com/WhiteNightShadow/camoufox-reverse-mcp/blob/v1.7.0/docs/RESEARCH_AND_VALIDATION.md)。借鉴响应文件与摘要分离、按需工具说明和最小证据闭环；未将 Chrome 调试协议或未经语义验证的 AST 变换直接当作 Camoufox 可用能力。

最近一轮公开方案调研见 [公开 skill 库调研](../docs/research/2026-11-public-skill-survey.md)。

方法层的行为回归放在 `evals/`：每个目录是一个虚构站点的诊断场景，比较新旧版本是否走对链路，详见 [evals/README.md](../evals/README.md)。场景里不写真实站点，改动路由或实验纪律后重跑。

不要把本流程提升成每次点击、每次请求前的通用审查。业务执行的首检/失效规则仍见 [task-preflight.md](task-preflight.md)。

真实上游 VM/CFF/加解密/指纹这一轮的来源、差分与 native 边界见 [REAL_SOURCE_VALIDATION.md](https://github.com/WhiteNightShadow/camoufox-reverse-mcp/blob/v1.8.0/docs/REAL_SOURCE_VALIDATION.md)；本仓库提供 [准备/验证脚本](../scripts/real_cases/README.md)，普通业务任务无需先执行整组实验。
