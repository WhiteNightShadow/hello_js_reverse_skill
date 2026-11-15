# 可重复准备的真实开源案例

本目录只包含本轮自写 CC0 输入、构建/验证脚本、协议适配器及固定 npm 配方。
**不含 KProtect 解释器、上游用例、其他上游源文件、浏览器、采样结果或缓存。**
运行 `prepare.py` 才会下载完整上游源树到新输出目录；输出必须在本 Skill 仓库之外。
无需加载、修改或停止任何现有服务，也无需读取原案例工作目录。

## 准备

需要 Python 3.9+、Node.js 18+ 和支持 lockfile v3 的 npm（建议使用同一 Node/npm
版本复现）。从本 Skill 仓库根目录执行，将路径替换为实际的规范路径：

```sh
python3 -B scripts/real_cases/prepare.py --output /absolute/work/new-assets
python3 -B scripts/real_cases/prepare.py --output /absolute/work/another-new-assets --archive-dir /absolute/work/archive-cache
```

输出目录必须不存在，父目录必须已存在；不接受 `..`、符号链接路径或覆盖空目录。
macOS 的 `/tmp`、`/var` 可能是符号链接，请使用 `realpath` 后的路径。
缓存是**只读**目录：按 `sources.json` 的四个 `archive` 文件名存放 `.tar.gz`。
存在的缓存文件仍须验证 SHA256；错误立即失败，不回退下载；缺失项才下载固定 HTTPS URL。
可把原 `vm-cff/downloads` 两份选定档案和 `crypto-fingerprint/vendor` 两份档案复制到缓存；
不需要 javascript-obfuscator 的 npm tgz、其他候选 VM、已安装依赖或已生成资产。

每次运行都会重新执行两次 `npm ci --ignore-scripts`，使用本目录固定 lock 的版本、
registry URL 和 integrity；包含平台对应的可选 esbuild 二进制依赖。隔离 npm cache、
临时目录、用户/全局 npm 配置，不执行上游 lifecycle scripts。随后显式运行自写构建
及 Node 自测。`--ignore-scripts` 只禁用安装生命周期，显式构建仍会执行已校验上游编译器。
VM/CFF 原 lock 的镜像 URL 已规范为 registry.npmjs.org，所有版本和 SHA512 integrity 保持原值。

下载有体积上限；解包先完整检查路径及类型，拒绝绝对路径、跳目录、链接、设备、稀疏文件、
重复/大小写冲突路径、异常根目录和超额展开内容。失败保留自己的输出及日志，
`PREPARE.json` 标为 `failed`；再次运行须使用另一个新目录。工具不会自动删除或修复旧输出。

## 固定来源和许可

完整 archive SHA256、固定 GitHub URL 见 `sources.json`。

| 来源 | 固定 commit | 许可与用途 |
|---|---|---|
| yang-zhongtian/KProtect | `da4ea8a3095a14dbb7cdf3126cb9cc2e076fdf2a` | 原 GPL 文本；根 package 标 GPL-3.0-or-later，子包标 GPL-3.0。真实 TypeScript compiler/assembler/VM 及一个 substring 上游用例 |
| javascript-obfuscator/javascript-obfuscator 4.1.1 | `828a190cf80a86227ef77be38e99aad9838aed70` | BSD-2-Clause；保留源树，生成器执行 npm 锁定的 4.1.1 官方分发包 |
| brix/crypto-js 4.2.0 | `808f499ec789fcd68416328a40b8735a5c962116` | MIT；浏览器 crypto-js.js 是档案源树中的原文件 |
| fingerprintjs/fingerprintjs 5.2.0 | `e196578ba35362fdf15647e013d66ac28b3c9fb5` | MIT；从原 TypeScript 入口用 esbuild 生成 IIFE，非上游 Rollup 发布二进制 |

KProtect 编译器和 VM 保持原样，只解析官方占位符、枚举并打包；`unicodeDigest`、
`numericLedger` 是自写业务输入，`countSubstrings` 在准备时从上游源树读取。
baseline/VM/CFF/CFF-disabled 均包含该 GPL 用例；VM bundle 还含 GPL 解释器。
**生成资产不自动继承主仓库 Apache-2.0 或本目录 CC0。** 输出保留完整对应源树、archive、构建配方、
原许可证和 bundle 提示；需要交付输出时保留这些来源材料，不把 bundle 单独回填到主仓库。

Acorn 不作为独立案例或 Skill 资源打包，结构验证用已固定的 Babel parser。
javascript-obfuscator 自己要求的 Acorn 8.8.2 仍由其 npm 传递依赖安装，不能从上游 lock 关系中伪删。
本目录没有 Playwright 包、浏览器安装器或浏览器分发。

输出的重要位置：

- `PREPARE.json`：每个来源 URL、commit、预期/实测 SHA、缓存/下载来源、完整源文件清单、Node/npm 版本、完成状态。
- `SHA256SUMS`：源、配方、合成向量、许可证、资产和证据的清单；排除 node_modules/cache/tmp/logs。
- `logs/steps.jsonl`、`logs/*.log`：安装、构建、逐项自测命令、开始/结束时间及退出码。
- `licenses/`、各案例 `licenses/dependencies/`、原始源树：原版权/许可；依赖 integrity 和安装版本另见各 `evidence/dependencies.json`。
- `vm-cff/dist/`：四组脚本、浏览器页面和自测；`evidence/verification.json` 为本次 Node 差分/已知答案结果，`structure.json` 为真实 dispatcher 结构检查。
- `crypto-fingerprint/assets/`、`index.html`：真实库和自写适配器；`samples/` 仅本次生成的公开合成向量，`evidence/` 为本次自测。

VM/CFF 的固定 seed=20260908、threshold=1；没有读取环境变量改变构建结果的入口。
Node 自测涵盖 76 个 VM/CFF 结果/可变参数/重复调用/setter/已知答案检查；
CryptoJS 与独立 Node crypto 交叉验收 8 个信封、篡改拒绝、随机 IV、padding/UTF-8 和方向绑定；
另跑本地 challenge/TTL/nonce/replay 状态机。Node 自测并不等于浏览器或 native trace 已通过。
工具链/平台变化可能改变 bundle 字节；时间、随机 IV 和运行版本证据本来就不要求逐字节相同。

## 真实 MCP 验证

在已安装 `mcp`、`camoufox`/该 MCP 所需依赖和 `pycryptodome` 的 Python 环境中运行：

```sh
python -B scripts/real_cases/validate.py --assets /absolute/work/new-assets --mcp-root /absolute/work/camoufox-reverse-mcp
python -B scripts/real_cases/validate.py --assets /absolute/work/new-assets --mcp-root /absolute/work/camoufox-reverse-mcp --native
```

validator 不负责安装/切换浏览器或安装 MCP。需要可用的本地浏览器和该仓库的真实 MCP AST
依赖（Acorn 由 MCP 自行管理），以及 `evaluate_js(world='main')` 等原 harness 使用的接口。
使用执行 validator 的同一个 Python，通过 MCP SDK stdio 启动 `-B -m camoufox_reverse_mcp`。
不设置 ws_endpoint，不连接现有浏览器；每个场景独立启动/关闭自己拥有的浏览器。
资产和 MCP 仓库只读，MCP cwd、浏览器临时 profile、日志和服务都在自己的临时工作目录中。
本地 HTTP 服务仅监听 `127.0.0.1`，端口由系统分配，只提供白名单资产及演示协议接口。

默认实际跑 6 个场景：VM、CFF 各自原始/AST 插桩对照（每次完整 76 项），加密/指纹原始/AST
插桩对照。插桩须报告真实文件重写和非空运行日志，不能仅凭“已安装 tap”判通过。
加密链路是浏览器 CryptoJS → 独立 Python AES/HMAC → 浏览器验签解密，包含 Unicode/结构体、
响应篡改拒绝和请求重放拒绝；FingerprintJS 必须返回真实版本、组件、visitorId 和两次同页子集一致性。

`--native` 额外使用已安装的 `whitenightshadow/152.0.4-beta.30-reverse.5`，
可用 `REAL_CASE_NATIVE_BROWSER` 指定另一已安装的兼容定制 selector；不会修改持久 active 版本。
必须满足真实 native capability、control acknowledgement、非空原生事件序列及无截断/丢失。
保存空白点击对照和 SDK 页面加载/get 窗口；该窗口包含页面初始化，不能宣称每个事件都来自 SDK，
也不宣称 77 个插桩点全覆盖。未启用 native 时明确记 `not_requested`；
请求 native 但缺少定制版/握手/事件时记 `failed_or_unavailable`，不会退回 JS hook 并虚报通过。

stdout 给出临时 `real-case-validate-*` 目录及 `VALIDATE.json` 路径；该目录保留供审查。
`mcp.jsonl`、逐调用 JSON 和 stderr 是真实 stdio 证据，指纹及信封只在本次独立目录产生。
退出码：0=所请求范围通过，1=常规验证失败，2=常规通过但请求的 native 未通过/不可用。

## 协议与指纹边界

AES-256-CBC + PKCS#7，原始密钥与 16 字节随机 IV；明文为 `JSON.stringify` 的 UTF-8。
HMAC-SHA256 使用独立密钥并覆盖固定顺序数组：
`[v,alg,keyId,direction,requestId,method,path,ts,nonce,challengeId,fingerprint,iv,ciphertext]`。
request/response 各有独立 AES/MAC key；接收响应时按本地保存的请求上下文校验绑定。
`templates/crypto-fingerprint/scripts/verify-node.cjs` 是仅依赖 Node 标准库的协议实现。
合成 fixture 固定时间/IV，实际浏览器往返使用当前时间、随机 ID/nonce/IV 和现场指纹。
所有演示密钥公开；此协议仅测试加密往返和一致性状态机，不是商业风控或真实身份认证。

FingerprintJS 每次初始化显式 `monitoring:false`。适配器保留 SDK 各组件的 value/error/unavailable，
对 platform/languages/timezone/colorDepth/hardwareConcurrency/pdfViewerEnabled 六项生成短挑战子集摘要。
visitorId 是 SDK 自身标识，子集摘要不能当作设备真实性证明；同页重复不代表跨启动稳定。
Canvas、Audio、WebGL 等返回 skipped/unavailable 或有条件分支时，不能换算为 native 未访问。

## 工具安全测试

```sh
python3 -B -m unittest discover -s tests -p test_real_case_prepare.py
```

测试不使用原采样结果，不启动或清理现有服务。真实完整 npm 准备和浏览器验收需按上面的 CLI
单独执行；缺失浏览器/native 能力时应保留实际失败证据，不改成 mock 通过。
