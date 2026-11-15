# JS 逆向分析 Skill

面向 Web API 采集、前端签名分析与改版回归的方法论 Skill。它回答三件事：问题在哪一层、走哪条链路、做到什么证据才算收口。站点规则不进主干，只作为待验证的案例留在 `cases/`。

配套 [Camoufox MCP](https://github.com/WhiteNightShadow/camoufox-reverse-mcp) 捕获网络、定位源码和调试 Hook，交付可验证的采集程序。

## 核心能力

- **问题路由**：按现象定位失败层，给出第一步、对应链路和收口标准
- **对照实验**：控制组、来源替换、单变量回读、结果分类、结论强度
- **签名来源隔离**：取得未使用的值，拆开出值、会话和传输，验证绑定关系与新鲜度
- **原始 SDK 运行**：入口定位、状态回放、生命周期与读值差异，不必还原内部算法
- **不透明令牌分析**：信封、掩码、版式和批次对比
- **参数跟踪**：版本身份分开记录，结论带范围，换版有回归路径
- **双语言算法还原**：Node.js (`crypto` / `crypto-js`) 与 Python (`hashlib` / `pycryptodome`) 双路径实现
- **JS 混淆与 JSVMP**：OB 混淆、控制流平坦化、eval 打包、自定义 VM 的分析策略，实际有效性按目标样本验证
- **Cookie 归因**：分清 HTTP Set-Cookie 与 JS 写入
- **WASM 逆向**：WebAssembly 模块的加载、环境补全和调用
- **协议层诊断**：用对照实验确认 TLS、HTTP/2、频率限制是否真的是原因
- **通用采集**：分页、去重、JSONL、断点恢复

## 快速使用

### 方式一：AI 对话框直接安装（推荐）

在你的 AI 编码工具（Cursor / Claude Code / codex 等）的对话框中输入：

```
帮我安装下这个skill：hello-js-reverse-skill
项目地址：https://github.com/WhiteNightShadow/hello_js_reverse_skill
安装目录名：hello-js-reverse-skill
```

AI 会自动完成下载、配置，并在后续 JS 逆向相关任务中自动调用该 Skill。

### 方式二：手动安装

将本仓库克隆到对应 AI 工具的 skills 目录下：

**Cursor：**

```bash
git clone https://github.com/WhiteNightShadow/hello_js_reverse_skill.git ~/.cursor/skills/hello-js-reverse-skill
```

**Codex：**

```bash
git clone https://github.com/WhiteNightShadow/hello_js_reverse_skill.git ~/.codex/skills/hello-js-reverse-skill
```

**VSCode（Copilot / Cline 等插件）：**

```bash
git clone https://github.com/WhiteNightShadow/hello_js_reverse_skill.git ~/.vscode/skills/hello-js-reverse-skill
```

> 目录名需与 `SKILL.md` 里的 `name` 一致，都是 `hello-js-reverse-skill`；仓库名仍是 `hello_js_reverse_skill`，所以克隆时要写明目录名。v3.10.0 及更早版本装在 `hello_js_reverse_skill` 目录的，更新后把目录改名为 `hello-js-reverse-skill`。
>
> 安装完成后，AI Agent 会自动读取 `SKILL.md`。当你在对话中涉及接口采集、签名分析、动态 Cookie、混淆 JS、WASM 或浏览器环境调试等场景时，Skill 会自动激活。

## 项目结构

```
hello-js-reverse-skill/
├── SKILL.md                        # 技能入口：成功分层、问题路由、路线选择、实验纪律
├── README.md
│
├── references/                     # 按需读取
│   ├── problem-routing.md          # 主干：完整链路、路线阶梯、收口格式
│   ├── controlled-experiments.md   # 对照实验与归因
│   ├── signature-source-isolation.md # 未使用的值、绑定、新鲜度
│   ├── original-sdk-runtime.md     # 原始 SDK 运行、状态回放、生命周期
│   ├── opaque-token-analysis.md    # 令牌信封与版式
│   ├── version-tracking.md         # 参数跟踪与版本归档
│   ├── browser-evidence-contract.md # 抓包、Hook、插桩、原生追踪的证据边界
│   ├── task-preflight.md           # 任务级检查与失效重查
│   ├── general-collection.md       # 通用采集、恢复与基线
│   ├── phase-details.md            # 深度分析操作清单
│   ├── analysis-scenarios.md       # 专项场景配方
│   ├── path-a-four-tools.md        # JSVMP 算法追踪
│   ├── path-b-env-emulation.md     # JSVMP 环境复现
│   ├── jsvmp-analysis.md / jsvmp-source-instrumentation.md
│   ├── jsdom-env-patches.md / environment-patch.md
│   ├── crypto-patterns.md / obfuscation-guide.md / transform-validation.md
│   ├── hook-techniques.md / anti-debug.md / protocol-analysis.md
│   ├── common-pitfalls.md / troubleshooting.md
│   ├── mcp-tool-reference.md / mcp-tools.json
│   └── agent-validation.md / real-source-cases.md
│
├── cases/                          # 站点案例，唯一可以出现站点名的地方
├── evals/                          # 方法层的行为回归场景，全部虚构
├── docs/                           # 版本说明与公开方案调研
│
├── scripts/
│   ├── experiment-ledger.py        # 在线门禁、尝试台账、单变量回读
│   ├── opaque-token-inspect.py     # 令牌批次结构分析
│   ├── project-baseline.py         # SDK/签名代码/fixture 哈希与版本身份
│   ├── check-deps.py / check-mcp-contract.py
│   ├── crypto-identifier.js / hook-generator.js / sandbox-runner.js
│   └── real_cases/                 # 真实开源案例的准备与验证
│
├── templates/
│   ├── python-request/ / node-request/   # R1 纯算法
│   ├── vm-sandbox/                       # R2 片段执行
│   ├── wasm-loader/                      # WASM
│   ├── browser-auto/                     # R6 浏览器自动化
│   ├── env-bundle/                       # 浏览器环境包套到 jsdom
│   └── param-tracking/                   # 参数跟踪与实验单模板
│
└── examples/demo-analysis.md
```

## 快速开始

### 1. 环境检查

```bash
bash scripts/check-deps.sh
```

### 2. 作为 Cursor Skill 使用

将本目录以 `hello-js-reverse-skill` 为名放置到 `.cursor/skills/` 下，AI Agent 会自动读取 `SKILL.md` 获取逆向分析能力。

### 3. 工具脚本

**加密算法识别**:
```bash
node scripts/crypto-identifier.js "e10adc3949ba59abbe56e057f20f883e"
```

**生成 Hook 代码**:
```bash
node scripts/hook-generator.js --type=cookie
node scripts/hook-generator.js --type=xhr --target="/api/data"
node scripts/hook-generator.js --type=all
```

**VM 沙箱执行**:
```bash
node scripts/sandbox-runner.js obfuscated.js --extract-cookie --verbose
```

**令牌批次结构分析**:
```bash
python scripts/opaque-token-inspect.py samples.txt --encoding base64 --xor-align
```

**在线门禁与单变量回读**:
```bash
python scripts/experiment-ledger.py gate --ledger runs/ledger.jsonl --batch b1 --budget 3
python scripts/experiment-ledger.py audit --base a.json --candidate b.json --allow x-sign
```

### 4. 使用项目模板

根据分析结果选择合适的模板：

| 场景 | 语言 | 模板 | 何时使用 |
|------|------|------|---------|
| 标准加密算法 | Node.js | `templates/node-request/` | 加密可用 crypto 库还原 |
| 标准加密算法 | Python | `templates/python-request/` | 加密可用 hashlib/pycryptodome 还原 |
| 动态 Cookie | Node.js | `templates/vm-sandbox/` | 服务端返回 JS 生成 Cookie |
| WASM 加密 | Node.js | `templates/wasm-loader/` | 加密在 .wasm 中实现 |
| TLS/环境依赖 | Node.js | `templates/browser-auto/` | 无法脱离浏览器环境 |
| 环境对齐 | Node.js | `templates/env-bundle/` | 把 `compare_env(output_path=...)` 导出的环境包套到 jsdom（MCP v1.10.0） |

**Node.js 项目：**
```bash
cp -r templates/node-request/ my_project/
cd my_project && npm install
# 修改 main.js 中的配置和加密逻辑
node main.js
```

**Python 项目：**
```bash
cp -r templates/python-request/ my_project/
cd my_project && pip install -r requirements.txt
# 修改 main.py 中的配置和 utils/sign.py 中的签名逻辑
python main.py
```

## MCP 工具集成

本 Skill 围绕 [`camoufox-reverse` MCP](https://github.com/WhiteNightShadow/camoufox-reverse-mcp) 服务器组织能力（Camoufox 反检测浏览器与统一 API）：
- 源码级插桩 `instrumentation(action='install', mode="ast")` — MCP 侧 esprima 实现，挑战页可用
- 低干扰观察 `hook_jsvmp_interpreter(mode="transparent")` — 仅替换 prototype getter，日志在页面主世界
- Cookie 归因 — `network_capture` 与 Cookie Hook 配合，区分 Set-Cookie 与 document.cookie
- 响应链追踪 `navigate` 返回 `redirect_chain`/`final_status`，首次不加 Hook 先看响应链

| 核心工具 | 用途 |
|---------|------|
| `launch_browser` / `navigate` | 启动反检测浏览器并导航到目标页面 |
| `search_code(keyword, script_url=None)` | 在所有/指定 JS 中搜索关键词 |
| `scripts(action='list'\|'get'\|'save')` | 列出/获取/保存脚本 |
| `evaluate_js(..., world='isolated'\|'main')` | 执行 JS；默认隔离上下文保持兼容，可显式进入页面主世界并按 Frame 定位 |
| `hook_function(mode='intercept'\|'trace')` | 自定义 Hook / 函数追踪；可选择主世界与 Frame，跨导航或有界等待动态挂载需设置 `persistent=True` |
| `get_trace_data` | 读取或清理函数 Trace，可按 world 与 Frame 过滤 |
| `inject_hook_preset` | 一键预设 Hook（xhr/fetch/crypto/websocket/debugger_bypass/cookie/runtime_probe）；MCP v1.10.0 起装在页面主世界，日志用 `world='main'` 读 |
| `hook_jsvmp_interpreter` | 一键插桩 JSVMP 解释器（proxy / transparent 两种模式） |
| `instrumentation(action='install'\|'log'\|'stop'\|'reload'\|'rewrite_source')` | 源码级插桩：HTTP 层改写 VMP + 日志 + 重载；`tap_stage_calls` 按状态记录平坦化分发（MCP v1.9.4）；日志按 `seq`/`stage` 切片、`rewrite_source` 离线改写本地源码（MCP v1.10.0） |
| `network_capture(action='start'\|'stop')` | 网络捕获（支持 capture_body） |
| `list_network_requests` / `get_network_request` | 列出/获取捕获的请求 |
| `get_request_initiator` | 获取发起请求的 JS 调用栈（黄金路径） |
| `intercept_request` | 拦截/修改/Mock 网络请求 |
| `cookies(action='get'\|'set'\|'delete')` | Cookie 管理 |
| `compare_env` | 采集 JS 环境基线；其他属性需通过 `properties` 或分批 `evaluate_js` 扩展；MCP v1.10.0 起 `output_path` 导出完整环境包 |
| `trace_property_access(action=...)` | reverse.5 的 77 点 Gecko 原生追踪（旧兼容构建为 75 点）；支持 start→操作→stop、kind/site 过滤和覆盖边界 |
| `verify_signer_offline` | 用真实样本离线验证签名代码 |
| `export_state` / `import_state` | 保存/恢复浏览器状态 |
| `check_environment` / `reset_browser_state` | 环境自检 / 清理残留状态 |

证据边界见 [浏览器取证契约](references/browser-evidence-contract.md)，场景配方见 [analysis-scenarios.md](references/analysis-scenarios.md)。

## 逆向场景覆盖

| 场景 | 技术点 | 参考文档 |
|------|--------|---------|
| 请求参数签名 | MD5/HMAC/自定义哈希 | `crypto-patterns.md` |
| 动态 Cookie | eval首包/api预热/指纹Cookie | `hook-techniques.md` |
| 响应数据加密 | AES/DES/RC4解密 | `crypto-patterns.md` |
| OB混淆 | 字符串还原/CFF/变量重命名 | `obfuscation-guide.md` |
| **JSVMP 虚拟机保护** | **Hook/插桩/日志分析三板斧** | **`jsvmp-analysis.md`** |
| 自定义VM | I/O追踪/Hook解释器 | `obfuscation-guide.md` |
| WASM加密 | 加载/环境补全/导出函数调用 | `environment-patch.md` |
| 疑似 TLS 指纹 | 传输层诊断实验/curl_cffi | `protocol-analysis.md` |
| HTTP/2 | Node.js http2模块/Python httpx | `protocol-analysis.md` |
| 字体反爬 | 字体文件解析/CMAP映射 | `analysis-scenarios.md` |
| WebSocket | WS消息分析/协议解析 | `analysis-scenarios.md` |
| 反调试 | debugger绕过/检测对抗 | `anti-debug.md` |
| 环境检测 | webdriver/蜜罐/指纹 | `environment-patch.md` |
| 首屏挑战 | 响应链观察/低干扰观测 | `analysis-scenarios.md` |
| **请求失败排查** | **Cookie/Header/时间戳/签名对比** | **`troubleshooting.md`** |
| **通用 JSVMP 源码级插桩** | **HTTP 层源码改写 + hot_keys 指纹学习法** | **`jsvmp-source-instrumentation.md`** |
| **Cookie 归因分析** | **HTTP Set-Cookie vs JS document.cookie** | **`analysis-scenarios.md`** |
| **本地值被拒** | **来源替换、读值差异、状态回放** | **`problem-routing.md`** |
| **令牌结构** | **信封、掩码、版式、批次对比** | **`opaque-token-analysis.md`** |
| **版本跟踪** | **身份分开记录、结论范围、换版回归** | **`version-tracking.md`** |

## 技术栈

### Node.js
- **crypto** (内置): MD5/SHA/AES/DES/HMAC
- **crypto-js**: CryptoJS 兼容实现
- **node-forge**: RSA/PKI
- **axios**: HTTP 请求
- **vm** (内置): 沙箱执行
- **WebAssembly** (内置): WASM 加载
- **http2** (内置): HTTP/2 请求
- **playwright-core**: 浏览器自动化

### Python
- **requests** / **httpx**: HTTP 请求（httpx 支持 HTTP/2）
- **pycryptodome**: AES/DES/RSA/3DES 加密
- **hashlib** (内置): MD5/SHA 系列
- **hmac** (内置): HMAC 签名
- **base64** (内置): Base64 编解码
- **execjs**: 执行 JS 代码
- **curl_cffi**: 带浏览器 TLS 指纹模拟的 HTTP 客户端

### 调试工具
- **[camoufox-reverse MCP](https://github.com/WhiteNightShadow/camoufox-reverse-mcp) v1.10.0**: 反检测浏览器逆向分析（统一 API，含主世界/Frame Hook、源码级插桩与可选 Gecko 原生属性追踪）

## 版本记录

| 版本 | 日期 | 要点 |
|------|------|------|
| v3.13.0 | 2026-11-12 | 配合 MCP v1.10.0：插桩默认值、日志切片、离线插桩、preset 主世界；新增环境包套用模板 `templates/env-bundle/` |
| v3.12.0 | 2026-11-10 | 平坦化分发的阶段对照（`tap_stage_calls`），MCP 工具快照更新到 v1.9.4 |
| v3.11.1 | 2026-11-10 | JSVMP 探针日志改到页面主世界读取，配合 camoufox-reverse-mcp v1.9.3 |
| v3.11.0 | 2026-11-10 | Skill 名称改为 `hello-js-reverse-skill`，符合 Agent Skills 命名规范，安装目录名随之调整 |
| v3.10.0 | 2026-11-05 | 问题路由与路线阶梯、对照实验与参数跟踪方法、配套脚本、清理单站全局规则和失效工具名、文档门禁测试 |
| v3.9.0 | 2026-09-08 | 真实开源案例公开复现、现代解析/低副作用观测、精确数据与独立Agent复验 |
| v3.8.0 | 2026-09-08 | 公开方案研究、任务级检查、三轮Agent实操反馈、证据诊断与可选分页恢复增强 |
| v3.7.0 | 2026-09-07 | 通用采集与断点恢复、独立验签、模板修复、三平台 CI 和契约基线 |
| v3.6.1 | 2026-09-07 | 对齐 MCP v1.5.1：补充 Trace 清理、未来 Frame 预注册、执行失败不重放和 Hook 卸载边界 |
| v3.6.0 | 2026-09-04 | 对齐 MCP v1.5.0；新增主世界与 Frame 选择、动态目标持久 Hook、`pending` 状态和 Trace 数据读取规范 |
| v3.5.1 | 2026-09-03 | 对齐 MCP v1.4.1 / Camoufox Reverse reverse.5；LocalStorage 覆盖迁移至 Firefox 152 LSNG，并纳入可达的 partitioned 分支，protocol 1 不变 |
| v3.5.0 | 2026-09-03 | 对齐 MCP v1.4.0 / Camoufox Reverse reverse.4；默认保留 sandbox，新增交互式原生追踪、75 点证据边界、安全 snapshot 与 side-by-side 安装规则 |
| v3.4.1 | 2026-07-29 | 增加 AST 源码插桩执行健康门禁；对齐 camoufox-reverse MCP v1.1.1；保持正常插桩流程不变，仅在异常时进入安全降级 |
| v3.3.1 | 2026-04-21 | 经验法则精简：移除单站点经验，合并 evaluate_js 相关为 1 条，总数从 24 压缩到 22 条 |
| v3.3.0 | 2026-04-19 | 核心层回归扩容：Phase 1-5 详细动作 + 10 个场景速查 + 经验法则回迁核心层；案例层强化（禁动清单 + UA 分支矩阵） |
| v3.2.1 | 2026-04-19 | Phase 0.5.1 强化案例复用策略；经验法则第 11 条重写 |
| v3.2.0 | 2026-04-18 | 移除 MCP session 依赖，Checklist 压缩到三项，cases/ 成为唯一经验库 |
| v3.1.0 | 2026-04-18 | SKILL.md 瘦身，references/ 拆分子文档，工具引用对齐 MCP 合并 API |
| v3.0.0 | 2026-04-18 | 硬约束 Checklist + 红线四条 + 经验法则压缩 |

## 许可证

本仓库以 [Apache License 2.0](LICENSE) 发布。Copyright © 2026 WhiteNightShadow。

`scripts/real_cases/` 里自写的准备与验证脚本、测试输入按该目录的 [LICENSE](scripts/real_cases/LICENSE) 以 CC0-1.0 放弃权利；按配方下载的上游源码和依赖沿用各自原有的许可证。
