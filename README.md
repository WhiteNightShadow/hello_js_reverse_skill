# JS 逆向工程 Skill

通用 JavaScript 逆向工程技能，通过 Node.js 实现算法还原和模拟请求。深度集成 `js-reverse` 和 `chrome-devtools` 两个 MCP 工具，覆盖主流 JS 逆向场景。

## 核心能力

- **加密算法还原**: MD5/SHA/AES/DES/RSA/HMAC/Base64 等常见加密算法的 Node.js 纯算法复现
- **JS 混淆还原**: OB混淆、控制流平坦化、eval打包、自定义VM/JSVMP 等混淆类型的分析策略
- **动态 Cookie 逆向**: eval首包、api预热、浏览器指纹等 Cookie 生成机制的破解
- **WASM 逆向**: WebAssembly 加密模块的加载、环境补全和调用
- **协议层对抗**: TLS 指纹检测、HTTP/2 强制、频率限制等协议层防护的应对
- **MCP 工具深度集成**: 源码搜索、断点调试、Hook注入、网络监听全自动化
- **Codex/Claude Code 完整适配**: 内置 Agent 授权指令框架，解决 AI 编码工具在签名分析、接口调试等场景下的安全策略限制，确保 AI 全力协助完成分析任务

## 快速使用

### 方式一：AI 对话框直接安装（推荐）

在你的 AI 编码工具（Cursor / Claude Code / codex 等）的对话框中输入：

```
请帮我配置skill并在后续触发相关操作的时候查阅该skill：https://github.com/WhiteNightShadow/hello_js_reverse_skill
```

AI 会自动完成下载、配置，并在后续 JS 逆向相关任务中自动调用该 Skill。

### 方式二：手动安装

将本仓库克隆到对应 AI 工具的 skills 目录下：

**Cursor：**

```bash
git clone https://github.com/WhiteNightShadow/hello_js_reverse_skill.git ~/.cursor/skills/hello_js_reverse_skill
```

**Claude Code（Codex CLI）：**

```bash
git clone https://github.com/WhiteNightShadow/hello_js_reverse_skill.git ~/.codex/skills/hello_js_reverse_skill
```

**VSCode（Copilot / Cline 等插件）：**

```bash
git clone https://github.com/WhiteNightShadow/hello_js_reverse_skill.git ~/.vscode/skills/hello_js_reverse_skill
```

> 安装完成后，AI Agent 会自动读取 `SKILL.md` 获取 JS 逆向分析能力。当你在对话中涉及 JS 加密分析、网站逆向、参数签名还原等场景时，Skill 会自动激活。

## 项目结构


```
hello_js_reverse_skill/
├── SKILL.md                        # 技能定义（AI Agent 读取的核心文件）
├── README.md                       # 项目文档
│
├── references/                     # 参考文档（知识库）
│   ├── workflow-overview.md        # 工作流总览与解法模式决策树
│   ├── crypto-patterns.md          # 加密算法识别与 Node.js 还原代码
│   ├── obfuscation-guide.md        # JS 混淆类型识别与还原策略
│   ├── hook-techniques.md          # Hook 技术大全（13种 Hook 模板）
│   ├── anti-debug.md               # 反调试对抗手册（7种绕过方案）
│   ├── environment-patch.md        # 环境补全指南（VM沙箱/WASM/jQuery/XHR）
│   ├── protocol-analysis.md        # 协议层分析（TLS/HTTP2/UA/频率限制）
│   └── mcp-cookbook.md              # MCP 工具使用手册（5大场景操作步骤）
│
├── scripts/                        # 工具脚本
│   ├── check-deps.sh               # 环境依赖检查
│   ├── sandbox-runner.js           # VM 沙箱执行器（CLI工具）
│   ├── hook-generator.js           # Hook 代码生成器（10种Hook模板）
│   └── crypto-identifier.js        # 加密算法识别器（密文特征分析）
│
├── templates/                      # 项目模板（按解法模式分类）
│   ├── node-request/               # 模式A：纯 Node.js 算法还原
│   │   ├── main.js
│   │   ├── utils/encrypt.js
│   │   ├── utils/request.js
│   │   └── package.json
│   ├── vm-sandbox/                 # 模式B：VM 沙箱执行
│   │   ├── main.js
│   │   ├── utils/sandbox.js
│   │   ├── utils/request.js
│   │   └── package.json
│   ├── wasm-loader/                # 模式C：WASM 加载还原
│   │   ├── main.js
│   │   ├── utils/wasm-loader.js
│   │   ├── utils/env-patch.js
│   │   └── package.json
│   └── browser-auto/               # 模式D：浏览器自动化
│       ├── main.js
│       └── package.json
│
└── examples/                       # 示例
    └── demo-analysis.md            # 完整分析流程示例
```

## 快速开始

### 1. 环境检查

```bash
bash scripts/check-deps.sh
```

### 2. 作为 Cursor Skill 使用

将本目录放置到 `.cursor/skills/` 下，AI Agent 会自动读取 `SKILL.md` 获取逆向分析能力。

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

### 4. 使用项目模板

根据分析结果选择合适的模板：

| 场景 | 模板 | 何时使用 |
|------|------|---------|
| 标准加密算法 | `templates/node-request/` | 加密可用 crypto 库还原 |
| 动态 Cookie | `templates/vm-sandbox/` | 服务端返回 JS 生成 Cookie |
| WASM 加密 | `templates/wasm-loader/` | 加密在 .wasm 中实现 |
| TLS/环境依赖 | `templates/browser-auto/` | 无法脱离浏览器环境 |

```bash
cp -r templates/node-request/ my_project/
cd my_project && npm install
# 修改 main.js 中的配置和加密逻辑
node main.js
```

## MCP 工具集成

本 Skill 深度集成两个 MCP 服务器：

### js-reverse MCP

| 核心工具 | 用途 |
|---------|------|
| `search_in_sources` | 在所有 JS 源码中搜索加密关键词 |
| `set_breakpoint_on_text` | 按代码文本设置断点 |
| `trace_function` | 追踪函数调用，自动记录参数和返回值 |
| `inject_before_load` | 页面加载前注入 Hook 脚本 |
| `break_on_xhr` | XHR 请求断点 |
| `get_paused_info` | 获取断点处的调用栈和变量 |
| `save_script_source` | 保存脚本到本地分析 |

### chrome-devtools MCP

| 核心工具 | 用途 |
|---------|------|
| `new_page` / `navigate_page` | 页面导航 |
| `click` / `fill` / `type_text` | UI 交互 |
| `evaluate_script` | 在页面执行 JS |
| `take_screenshot` / `take_snapshot` | 截图/DOM快照 |
| `emulate` | 模拟 UA/设备/网络 |
| `get_network_request` | 获取请求详情（支持保存响应体） |

详见 `references/mcp-cookbook.md`。

## 逆向场景覆盖

| 场景 | 技术点 | 参考文档 |
|------|--------|---------|
| 请求参数签名 | MD5/HMAC/自定义哈希 | `crypto-patterns.md` |
| 动态 Cookie | eval首包/api预热/指纹Cookie | `hook-techniques.md` |
| 响应数据加密 | AES/DES/RC4解密 | `crypto-patterns.md` |
| OB混淆 | 字符串还原/CFF/变量重命名 | `obfuscation-guide.md` |
| 自定义VM/JSVMP | I/O追踪/Hook解释器 | `obfuscation-guide.md` |
| WASM加密 | 加载/环境补全/导出函数调用 | `environment-patch.md` |
| TLS指纹 | 浏览器自动化/curl-impersonate | `protocol-analysis.md` |
| HTTP/2 | Node.js http2模块 | `protocol-analysis.md` |
| 字体反爬 | 字体文件解析/CMAP映射 | SKILL.md |
| WebSocket | WS消息分析/协议解析 | `mcp-cookbook.md` |
| 反调试 | debugger绕过/检测对抗 | `anti-debug.md` |
| 环境检测 | webdriver/蜜罐/指纹 | `environment-patch.md` |

## 技术栈

- **Node.js**: 运行时环境
- **crypto** (内置): MD5/SHA/AES/DES/HMAC
- **crypto-js**: CryptoJS 兼容实现
- **node-forge**: RSA/PKI
- **axios**: HTTP 请求
- **vm** (内置): 沙箱执行
- **WebAssembly** (内置): WASM 加载
- **http2** (内置): HTTP/2 请求
- **playwright-core**: 浏览器自动化
