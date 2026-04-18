# 逆向经验库（Cases）

本目录存放已验证的逆向分析经验案例，供 Phase 0.5 指纹匹配阶段自动检索。

## 使用方式

- Agent 在 Phase 0.5 采集目标站点的技术指纹后，遍历本目录下的 `.md` 文件，匹配「指纹检测规则」段
- 命中后按案例中的「已验证定位路径」和「还原代码模板」快速执行
- 每个案例以**技术特征**命名，不以具体域名命名

## 案例索引

| 案例文件 | 技术特征 | 难度 | 核心方案 | 反爬类型 |
|---------|---------|------|---------|---------|
| [jsvmp-xhr-interceptor-env-emulation.md](jsvmp-xhr-interceptor-env-emulation.md) | JSVMP 字节码虚拟机 + XHR 拦截器 + 多层 SDK 联动 + jsdom 全量环境伪装 | ★★★★★ | jsdom 沙箱 + 58 项环境补丁 + XHR Hook 截出 a_bogus | 行为型 |
| [jsvmp-ruishu6-cookie-412-sdenv.md](jsvmp-ruishu6-cookie-412-sdenv.md) | JSVMP RS6 + Cookie 生成 + 412 挑战 + sdenv 补环境 | ★★★★★ | sdenv（魔改 jsdom + C++ V8 Addon）让RS JSVMP 真实执行生成 Cookie | 签名型 |
| [universal-vmp-source-instrumentation.md](universal-vmp-source-instrumentation.md) | **[v2.5.0 新]** 通用 VMP（RS 5/6、Akamai sensor_data、webmssdk、obfuscator.io）+ 首屏挑战 + 混合 Cookie 模式 | ★★★★ | **源码级插桩** + hot_keys 指纹学习 + analyze_cookie_sources 归因（**骨架模板**，由使用者按实际站点填充） | 混合（以签名型为主） |
| [jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md](jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox.md) | **[v2.7.0 新]** JSVMP 双签名（X-Bogus + X-Gnarly）+ XHR/fetch 双通道拦截 + cacheOpts 初始化 + jsdom Firefox 环境伪装 | ★★★★★ | jsdom 喂入-截出策略 + Firefox 格式 native code 伪装 + cacheOpts 路径注册 + got-scraping TLS 指纹模拟 | 行为型 |

## 指纹匹配快速参考

| 技术特征关键词 | 匹配案例 | 置信度 |
|--------------|---------|--------|
| `webmssdk` / `byted_acrawler` / `_SdkGlueInit` | jsvmp-xhr-interceptor-env-emulation 或 jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox | 高（需进一步区分） |
| `cacheOpts` + `X-Gnarly` | jsvmp-dual-sign-xhr-intercept-cacheOpts-jsdom-firefox | 高（国际版双签名变体） |
| `a_bogus` + 192字符 + 无 `cacheOpts` | jsvmp-xhr-interceptor-env-emulation | 高（国内版单签名） |
| `sdenv` / `FuckCookie` / 412 挑战 | jsvmp-ruishu6-cookie-412-sdenv | 高（RS） |
| `while-switch` 分发循环 + 200KB+ 文件 | universal-vmp-source-instrumentation | 中（通用骨架） |

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

## 新增案例

1. 复制 `_template.md` 为新文件，以技术特征命名
1.5. **归档 Session 档案**（v2.9.0 新增）：如果本次分析过程中创建了域级 Session 档案（`cases/_session_archives/<domain-hash>/`），确认断言集已写入且通过验证。Session 档案会自动被 `.gitignore` 排除，但其中的技术结论（反爬类型、hot_keys 快照）应同步体现在案例文件的「技术指纹」和「加密方案」段中。
2. 按模板格式填写各段（v2.7.0 起模板新增「反爬类型判定」和「关键经验总结」段）
3. 更新本文件的案例索引表
4. 可选：在 `_private_mapping.json` 中添加私有域名映射

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
（列出可用于自动检测的稳定特征，每条写成可搜索的模式）
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
（脱敏后的核心还原函数，可直接复用）

## 踩坑记录
（遇到的坑和解决方法，每条一个）

## 变体说明
（同类站点的已知变体差异）

## 关键经验总结
（本次分析中最有价值的 2-3 条经验）

---
```

将输出内容发给本 Skill 的使用者，即可按 `_template.md` 格式沉淀到本目录。
