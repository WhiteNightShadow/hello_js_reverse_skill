# 逆向经验库（Cases）

本目录汇集历史逆向分析经验与骨架模板，供遇到相关技术特征时按需查阅。案例中的验证结论只适用于其记录的版本、日期和范围；目录存在或关键词命中不代表当前方案已验证。任务首检与续做复用遵循 [任务级检查](../references/task-preflight.md)。

**这是全仓库唯一可以出现站点名、SDK 名和站点参数名的地方。** 案例结论不是全局规则，命中只产生候选假设，走哪条链路由当前目标的证据决定，方法见 [问题路由](../references/problem-routing.md)。下表的关键词由测试自动提取，一旦出现在 `SKILL.md` 或 `references/` 就会失败。

## 高频站点与特征速查表

> 仅在当前任务遇到相应逆向特征时查表，命中后读相关案例的定位线索与踩坑记录，并用当前源码/样本验证适用性。无需遍历全部案例，也不要求每次工具调用前重复查阅。
> URL、JS 变量名或请求参数名任一命中，只用于选择候选案例。

| 关键词（URL 域名 / 签名参数 / SDK 字符串） | 历史分类 | 对应案例 | 历史方案线索 |
|---|---|---|---|
| `tiktok.com` / `X-Bogus` / `X-Gnarly` / `webmssdk` / `cacheOpts` | 行为型 | [`jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md`](./jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md) | jsdom 环境伪装 |
| `douyin.com` / `a_bogus` / `_sdkGlueInit` | 行为型 | [`jsvmp-xhr-interceptor-env-emulation.md`](./jsvmp-xhr-interceptor-env-emulation.md) | jsdom/vm 环境复现与 XHR 拦截线索 |
| `nmpa.gov.cn` / `NfBCSins2OywS` / `NfBCSins2OywT` / `.e17ed02.js` / 412 挑战 | 签名型（RS 6） | [`jsvmp-ruishu6-cookie-412-sdenv.md`](./jsvmp-ruishu6-cookie-412-sdenv.md) | sdenv 纯 Node.js |
| `acmescripts` / `/akam/` | 签名型（Akamai） | (待建) | (待建) |
| `acw_sc__v2` / Aliyun WAF | 签名型 | (待建) | (待建) |
| `FSSBBIl1UgzbN7N` / `_RSG` / 200KB 混淆 JS + 412 | 签名型（RS） | 同 nmpa 案例 | sdenv |
| `obfuscator.io` 特征（`_0x` 大量前缀） | 纯混淆线索 | (无专案，按当前问题选静态分析/四板斧步骤) | AST 反混淆与行为对照 |
| `jsdVipUserMark` / `_yundunxhr` / `dewuCap` / `JS DUN PROTECT` / `.moveImg` + `captcha/blank.png` | 混合型（JSDUN eval-VM + 图集拖拽验证码 + XOR 流密码信封） | [`jsdun-evalvm-triple-sdk-draggrid-captcha-xor-stream.md`](./jsdun-evalvm-triple-sdk-draggrid-captcha-xor-stream.md) | 接管 `eval` 脱壳三件套；请求信封 `md5(明文)+XOR(KS=F(sk,UA))`、响应解密走 `Fun99` 静态表 + zlib；验证码**必须读 DOM**（图位每次随机）；`bgImage` 是答案的马赛克版可直接反查 |
| `haohuo.jinritemai.com` / `ec.snssdk.com` / `promotion/pack/h5` / `10001010A` / `userproductnum` | 行为型（多入口判据分离：登录态门 vs 签名门） | [`multi-entry-h5-detail-login-gate-vs-sign-gate.md`](./multi-entry-h5-detail-login-gate-vs-sign-gate.md) | 零字节响应先换入口比判据；老版 `ec.snssdk.com` 只校验登录态并直译为「未登录」；`ttwid` 可 `union/register` 自建；`get_network_request` 取完整 URL 再判签名有无 |

### 使用方式

1. 先复用需求工作区已知代码、任务记录、样本与 `project-manifest.json`；代码维护、离线验签和普通 API 采集无需为查案例启动浏览器。
2. 遇到相关逆向特征时，用本索引选择候选，只读取需要的案例段落。关键词未命中可继续标准分析，不要求补做全库扫描。
3. 对照当前 SDK/源码、接口输入输出和已有样本，确认案例的定位方法或踩坑点仍适用。只因 SDK、鉴权或相关状态变化而复查受影响项。
4. 工作区已有 `site_<target>/` 或 `<target>_<date>/` 可作为定位入口，但目录名不证明代码可用；核对来源、版本与实际验证记录后复用，不强制扫描所有目录或另建项目。
5. 新发现先记入当前需求工作区；需要沉淀通用经验时按下方模板脱敏整理，不把新增案例作为每个任务的完成门槛。

### 真实上游源码的本地案例（Skill 3.9 / MCP 1.8）

- [真实上游本地案例参考](../references/real-source-cases.md)：KProtect VM、javascript-obfuscator CFF、CryptoJS 和 FingerprintJS 的来源、执行路径与证据边界。
- [准备与验证脚本说明](../scripts/real_cases/README.md)：固定来源的本地准备、Node 自测、真实 MCP 和可选 native 验证方式。按需运行；说明文件存在不代表本机已经执行或通过，也不代表商业站点验证成功。

复用历史源码插桩案例时，以当前 [源码级插桩指南](../references/jsvmp-source-instrumentation.md) 为准：AST 先用 esprima，再由本地 Node.js + 随包 Acorn 解析现代语法；解析成功仍可能跳过不支持的节点，不提供 construct（`new`）事件。regex 是保守 whole-program 子集白名单，复杂语法原样跳过，不承诺覆盖率，也不要求机械降级。**显式 `mode="regex"` 搭配非空 `filter_property_names` / `filter_object_names` 会在安装前被拒绝并建议使用 `mode="ast"`**；AST 失败时带过滤器也不会自动回退为无过滤的 regex。

AST 属性过滤同时约束方法调用，对象过滤支持 `this.bytecode` 等静态路径，不推断动态表达式。日志从所选 Frame 主世界读取；iframe 需指定相应 Frame，检查 `possibly_capped` / `truncated`。默认源码 preview 中对象/函数是类型占位，不是完整 I/O；保留 skip、异常与原始/改写对照，不能把轻改写当作源码完整性校验的保证解法。

## 案例索引

| 案例文件 | 技术特征 | 难度 | 历史方案 / 模板 | 历史分类 |
|---------|---------|------|---------|---------|
| [jsvmp-xhr-interceptor-env-emulation.md](jsvmp-xhr-interceptor-env-emulation.md) | JSVMP 字节码虚拟机 + XHR 拦截器 + 多层 SDK 联动 + jsdom 全量环境伪装 | ★★★★★ | jsdom 沙箱 + 58 项环境补丁 + XHR Hook 截出 a_bogus | 行为型 |
| [jsvmp-ruishu6-cookie-412-sdenv.md](jsvmp-ruishu6-cookie-412-sdenv.md) | JSVMP RS6 + Cookie 生成 + 412 挑战 + sdenv 补环境 | ★★★★★ | sdenv（魔改 jsdom + C++ V8 Addon）让RS JSVMP 真实执行生成 Cookie | 签名型 |
| [universal-vmp-source-instrumentation.md](universal-vmp-source-instrumentation.md) | **[v2.5.0 新]** 通用 VMP（RS 5/6、Akamai sensor_data、webmssdk、obfuscator.io）+ 首屏挑战 + 混合 Cookie 模式 | ★★★★ | **源码级插桩** + hot_keys 指纹学习 + analyze_cookie_sources 归因（**骨架模板**，由使用者按实际站点填充） | 混合（以签名型为主） |
| [jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md](jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md) | **[v2.7.0 新]** JSVMP 双签名（X-Bogus + X-Gnarly）+ XHR/fetch 双通道拦截 + cacheOpts 初始化 + jsdom Firefox 环境伪装 | ★★★★★ | jsdom 喂入-截出策略 + Firefox 格式 native code 伪装 + cacheOpts 路径注册 + got-scraping TLS 指纹模拟 | 行为型 |
| [multi-surface-sdk-source-isolation.md](multi-surface-sdk-source-isolation.md) | **[v3.10 新，已脱敏]** 同平台多端 SDK、软拒绝、来源隔离、原始 SDK 运行、结论纠偏 | ★★★★★ | 按端分别定路线：R0、R4 最小状态、R4 完整回放 | 不分类 |
| [vm-stream-armour-and-boolean-oracle-isolation.md](vm-stream-armour-and-boolean-oracle-isolation.md) | **[v3.14 新，已脱敏]** 等长字节码流式护甲、压缩头产生固定密文前缀、粗粒度布尔判决下的分层变量隔离 | ★★★★ | R1：先离线往返锁死编码层，再校准单位换算并对照当前目标实测基线分布 | 不分类 |
| [bitpacked-dual-vmp-slot-diff-and-realm-nativeness.md](bitpacked-dual-vmp-slot-diff-and-realm-nativeness.md) | **[v3.15 新，已脱敏]** 位打包双分发器 JSVMP、定长码点流逐槽反解消融、jsdom 原型链 / `document.all` / `iframe` 子 Realm 原生性校准 | ★★★★★ | R3：隔离在线改写与同页连调污染，反解槽位流过滤自抖动项后按浏览器快照单点消融 | 不分类 |
| [per-build-polymorphic-vmp-and-composite-gate-ablation.md](per-build-polymorphic-vmp-and-composite-gate-ablation.md) | **[v3.16 新，已脱敏]** 按会话重编译多态 JSVMP、运行期窗口自证提密钥、`Error.stack` 跨引擎对齐与联合门禁金标准二分消融 | ★★★★★ | R3+R1：结构正则跨构建观测 + 运行期窗口频次与同次密文自证提密钥 + Step 0 自证与金标准折半消融 | 不分类 |
| [jsdun-evalvm-triple-sdk-draggrid-captcha-xor-stream.md](jsdun-evalvm-triple-sdk-draggrid-captcha-xor-stream.md) | **JSDUN eval-VM 三件套 + 图集拖拽验证码 + 三层独立密钥**：eval 包自解码、请求信封绑 sk 的流密码、响应静态表 + zlib、验证码位置每次随机、`bgImage` 泄漏答案 | ★★★★★ | 接管 `eval`/`Function` 一键脱壳 → 分层标定三套密钥 → 验证码必须渲染后读 DOM（纯协议死结）→ 真人轨迹模板仿射 + 阈值闸门 + 三通道融合 | 混合型（签名 + 行为） |
| [eval-packer-unwrapping-and-multilayer-codec-separation.md](eval-packer-unwrapping-and-multilayer-codec-separation.md) | **[v3.17 新，已脱敏]** 动态 `eval` 打包壳脱壳、参数/信封/响应三层独立密钥域隔离、Latin-1 二次 UTF-8 膨胀判读与单次会话配额边界 | ★★★★ | R3+R1：离线沙箱接管动态入口脱壳 + `jsdom` 标定绑定会话与 UA 的流式信封 + 静态表与 `zlib` 响应解码 | 不分类 |
| [custom-b64-envelope-dual-gen-vmp-and-container-disassembly.md](custom-b64-envelope-dual-gen-vmp-and-container-disassembly.md) | **[v3.17 新，已脱敏]** 自定义换表 Base64 明文 JSON 信封、双代 JSVMP 前缀判读、字节码容器（魔数/隐写掩码/前缀码常量池）拆解与 `jsdom` 离线出值 | ★★★★ | R3+R0：三层状态码分层归因 + `[i<<2,0,0]` 探针提表 + `setter` 捕获覆盖式全局容器 + 最小宿主容错离线运行原始实体 | 不分类 |
| [multi-entry-h5-detail-login-gate-vs-sign-gate.md](multi-entry-h5-detail-login-gate-vs-sign-gate.md) | **[v3.17.1 新]** 同平台多入口判据分离：新版 BFF 三件套签名 + 环境门给出零字节响应，老版 BFF 仅校验登录态并直译「未登录」；含 `ttwid` 自建流程与 URL 预览截断导致的误判纠偏 | ★★☆☆☆ | R6 取证 → 换入口比判据 → 定层为登录态（未进入签名还原） | 行为型（判据分层） |

[historical-experience-rules.md](historical-experience-rules.md) 是 v3.10 之前的 30 条经验法则原文，含大量单站结论，只作历史追溯，每条的现状见 [旧规则去向](../references/experience-rules-full.md)。

## 特征匹配快速参考

下表仅表示历史关联强弱，不是当前方案的验证结论；长度、变量名和 SDK 结构均可能变化。

| 技术特征关键词 | 候选案例 | 历史关联线索 |
|--------------|---------|--------|
| `webmssdk` / `byted_acrawler` / `_SdkGlueInit` | jsvmp-xhr-interceptor-env-emulation 或 jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox | 高（需进一步区分） |
| `cacheOpts` + `X-Gnarly` | jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox | 高（国际版双签名变体） |
| `a_bogus` + 192字符 + 无 `cacheOpts` | jsvmp-xhr-interceptor-env-emulation | 高（国内版单签名） |
| `sdenv` / `FuckCookie` / 412 挑战 | jsvmp-ruishu6-cookie-412-sdenv | 高（RS） |
| `while-switch` 分发循环 + 200KB+ 文件 | universal-vmp-source-instrumentation | 中（通用骨架） |
| 等长无填充密文（固定前缀但搜不到魔数）+ HTTP 200 布尔判决 | vm-stream-armour-and-boolean-oracle-isolation | 中（分层锁死与往返验证方法） |
| 位打包状态分发（移位掩码嵌套 `switch`）+ 浮动长度 Base64 令牌 + jsdom 原生性自证 | bitpacked-dual-vmp-slot-diff-and-realm-nativeness | 中（定长槽位反解消融与子 Realm / `document.all` 原生性校准） |
| 每次拉取脚本字节哈希与 opcode 编号均变化 + 内嵌会话分组密钥 + 多槽联合门禁 | per-build-polymorphic-vmp-and-composite-gate-ablation | 中（结构正则跨构建定位、运行期窗口自证提密钥与金标准折半消融） |
| 外层 `eval(function(...){...})` 多脚本包 + 请求/响应异或密钥流互不通 + Base64 解码约 `1.5×` 膨胀 | eval-packer-unwrapping-and-multilayer-codec-separation | 中（离线动态脱壳、三层独立编解码隔离与单次会话配额判读） |
| 固定前缀 64 字符集外层信封可解明文 JSON + 内层双代版本前缀并存 + 覆盖式全局容器与空种子 9 字符退化串 | custom-b64-envelope-dual-gen-vmp-and-container-disassembly | 中（`[i<<2,0,0]` 探针提表、多状态码分层归因、容器拆解与 `jsdom` 离线出值） |
| 同一业务数据两条前端入口判据不同 + 一条回零字节、另一条回「未登录」文案 | multi-entry-h5-detail-login-gate-vs-sign-gate | 中（零字节先换入口比判据，登录态门与签名门分离） |

## 变体关系图

```
JSVMP 字节码虚拟机 + 多层 SDK 联动
├── 国内短视频平台变体（单签名 a_bogus + bdms.paths）
│   └── → jsvmp-xhr-interceptor-env-emulation.md
├── 海外短视频平台（国际版）变体（双签名 X-Bogus + X-Gnarly + cacheOpts）
│   └── → jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md
└── 通用 VMP 骨架（RS/Akamai/webmssdk/obfuscator.io）
    └── → universal-vmp-source-instrumentation.md

RS JSVMP + Cookie 签名
└── → jsvmp-ruishu6-cookie-412-sdenv.md
```

## 私有映射

`_private_mapping.json` 可用于本地私有标注域名与案例的对应关系（已加入 `.gitignore`，不会被提交）：

```json
{
  "某短视频平台": {
    "pattern": "jsvmp-xhr-interceptor-env-emulation",
    "domain_hint": "短视频",
    "notes": "Cookie 字段 ttwid/__ac_nonce/__ac_signature"
  },
  "某海外短视频平台": {
    "pattern": "jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox",
    "domain_hint": "海外短视频",
    "notes": "双签名 X-Bogus + X-Gnarly，cacheOpts 初始化"
  }
}
```

## 按需沉淀新案例

先判断它是案例还是方法：一条经验只有在不依赖站点时才进入 `references/`，也就是能在不同体系上成立，或能用公开样本复现。只在一个站点上见过的，哪怕验证过很多次，也留在案例里。提升时把站点名、参数名、阈值和耗时都去掉，写成判断顺序和收口标准。

1. 复制 `_template.md` 为新文件，以技术特征命名
2. 按模板填写，注明来源、版本、日期、实际验证范围与尚未验证项；不把骨架模板标作已验证方案
3. 更新本文件的案例索引表
4. 在“关键经验总结”记录有证据的可验证事实（如当时的参数长度、环境读取与输入输出关系）；下次改版按受影响项核对，不将历史值写成永久规则
5. 可选：在 `_private_mapping.json` 中添加私有域名映射

### 跨端知识提取提示词

当你在其他大模型端完成了一个站点的逆向分析，可以使用以下提示词让它输出可沉淀的结构化信息：

```
请将本次逆向分析的经验总结为结构化的技术案例，按以下格式输出。注意：不要包含具体域名、URL、真实密钥等敏感信息，用抽象描述代替。

---

## 案例名称
（用技术特征命名，如"OB混淆+AES-CBC+动态密钥"、"JSVMP+Cookie生成"）

## 反爬类型判定
（签名型 / 行为型 / 纯混淆，附判定依据）

## 技术指纹
（列出本次观察到的特征，每条写成可搜索模式并注明版本；这些是定位线索）
- JS特征: （如"_0x前缀变量大量出现"、"单文件200KB+"、"存在while-switch解释器循环"）
- 参数特征: （如"sign参数，32位hex，疑似MD5"、"token参数，Base64格式"）
- 请求特征: （如"存在/api/init预热请求"、"Cookie中有动态字段__ac_xxx"）
- 反调试特征: （如"debugger定时器"、"console.log检测"）
- 混淆类型: （如"OB混淆v2"、"JSVMP"、"webpack打包+变量混淆"）

## 加密方案
- 算法: （如AES-CBC、MD5、HMAC-SHA256、RSA等）
- 密钥来源: （硬编码/接口下发/动态计算/从页面DOM提取）
- 加密流程: （明文如何组装 → 如何加密 → 如何拼接到请求中）
- 签名公式: （如 sign = MD5(path + timestamp + nonce + secret).toLowerCase()）

## 定位路径
（还原过程中最高效的定位方法，按执行顺序）
1. 第一步做了什么，搜索了什么关键词
2. 第二步怎么找到的关键函数
3. 第三步怎么确认的算法

## 还原代码
（脱敏后的核心还原函数，标明依赖、输入约定及复用前需验证的条件）

## 验证范围
（记录来源、版本、日期、实际运行的样本/检查与结果；区分本地测试、浏览器/MCP 观测、真实接口和未验证项）

## 踩坑记录
（遇到的坑和解决方法，每条一个）

## 变体说明
（同类站点的已知变体差异）

## 关键经验总结
（本次分析中最有价值的 2-3 条经验）

---
```

将输出内容发给本 Skill 的使用者，即可按 `_template.md` 格式沉淀到本目录。
