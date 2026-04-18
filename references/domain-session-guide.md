# 域级 Session 档案指南

> v2.9.0 新增。每个目标域维护一份持久化 Session 档案，跨任务复用反爬类型判定、指纹基准、Cookie 归因结论，避免重复侦察。

## 1. 档案结构

每个域的 Session 档案存放在 `cases/_session_archives/<domain-hash>/` 下，包含以下文件：

```
cases/_session_archives/
└── <domain-hash>/
    ├── session.json          # 核心档案（结构化元数据）
    ├── fingerprint.json      # 浏览器指纹基准快照
    ├── cookie-attribution.json  # Cookie 归因结论缓存
    ├── assertions.json       # 断言集（通过/失败/跳过）
    └── notes.md              # 人工备注（可选）
```

### session.json 字段说明

```json
{
  "domain_hash": "sha256(domain)[0:12]",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "skill_version": "2.9.0",
  "anti_crawl_type": "signature | behavioral | obfuscation | unknown",
  "anti_crawl_evidence": {
    "initial_status": 412,
    "final_status": 200,
    "redirect_chain_pattern": "412→412→200",
    "vmp_script_url": "**/sdenv-*.js",
    "vmp_case_count": 87,
    "sdk_fingerprint": ["sdenv", "FuckCookie"]
  },
  "tool_chain": {
    "primary": "instrument_jsvmp_source",
    "mode": "ast",
    "fallback": "hook_jsvmp_interpreter(mode=transparent)"
  },
  "hot_keys_snapshot": {
    "top_10": ["userAgent", "plugins", "webdriver", "cookie", "platform", "language", "screen.width", "screen.height", "hardwareConcurrency", "deviceMemory"],
    "total_count": 42,
    "captured_at": "ISO8601"
  },
  "cookie_attribution_summary": {
    "signature_cookies": ["acw_tc"],
    "js_cookies": ["x-bogus-js"],
    "mixed_cookies": ["NfBCSins"]
  },
  "assertions_passed": 12,
  "assertions_failed": 0,
  "assertions_total": 12
}
```

## 2. 生命周期

### 2.1 创建时机

Session 档案在以下时机自动创建：

1. **Phase 0 启动时**：`launch_browser` + `navigate` 成功后，检查 `cases/_session_archives/` 下是否已有该域的档案
   - 已有 → 加载并验证（跑断言集，见第 4 节）
   - 没有 → 创建空档案，后续步骤逐步填充

2. **反爬类型识别完成后**：将 `anti_crawl_type` 和 `anti_crawl_evidence` 写入档案

3. **Phase 0.5 指纹采集后**：将 `hot_keys_snapshot` 和 `cookie_attribution_summary` 写入档案

### 2.2 更新时机

- 每次成功完成 Phase 5 交付后，更新 `updated_at` 和断言结果
- Cookie 归因结论变化时（如新增 cookie 字段），更新 `cookie-attribution.json`
- 用户手动触发 `session refresh` 时，重新采集指纹基准

### 2.3 过期策略

- 档案默认 **7 天有效**（`updated_at` 距今超过 7 天视为过期）
- 过期档案不删除，但加载时会标记 `stale: true`，提示用户是否重新验证
- 断言集失败 ≥ 3 条时，自动标记为 `needs_refresh`

## 3. 与工作流的集成

### Phase 0 集成

```
Phase 0 步骤 4（新增）：启动域级 Session 档案
  ① 计算目标域的 hash：sha256(domain)[0:12]
  ② 检查 cases/_session_archives/<hash>/session.json 是否存在
  ③ 存在且未过期 → 加载档案，输出摘要：
     "已加载域级 Session 档案：反爬类型=签名型，上次分析于 2 天前，12/12 断言通过"
  ④ 存在但过期 → 加载档案 + 标记 stale，提示用户：
     "域级 Session 档案已过期（7 天前），建议重新验证断言集"
  ⑤ 不存在 → 创建空档案，后续步骤自动填充
```

### Phase 0.5 集成

```
Phase 0.5.-1（新增前置步骤）：本域断言 Reverify
  如果 Session 档案存在且包含断言集：
  ① 逐条执行断言（见第 4 节）
  ② 全部通过 → 跳过 Phase 0.5 的指纹采集，直接进入 Phase 1
     输出："断言集 12/12 通过，目标站点技术栈未变，跳过重复侦察"
  ③ 有失败 → 标记失败断言，进入 Phase 0.5 正常流程重新采集
     输出："断言 #3（VMP case_count）失败：期望 87，实际 102。目标可能已更新，重新侦察"
```

### Phase 5 集成

```
Phase 5 交付时自动更新 Session 档案：
  ① 将本次分析的断言集写入 assertions.json
  ② 更新 session.json 的 updated_at 和 assertions_passed/failed/total
  ③ 如果是新域，提示用户："已创建域级 Session 档案，下次分析同域时将自动复用"
```

## 4. 断言系统

断言是 Session 档案的核心验证机制。每条断言描述一个可自动检测的技术事实，用于快速判断目标站点是否发生了技术变更。

### 4.1 断言类型

| 类型 | 示例 | 检测方法 |
|------|------|---------|
| `script_exists` | VMP 脚本 URL 模式仍然存在 | `list_scripts` → 匹配 URL pattern |
| `script_size_range` | VMP 脚本大小在 ±20% 范围内 | `list_scripts` → 检查文件大小 |
| `dispatch_loop_count` | VMP 分发循环 case 数在 ±10 范围内 | `find_dispatch_loops` → 比较 case_count |
| `anti_crawl_type` | 反爬类型未变（仍为签名型） | `navigate` → 检查 redirect_chain 模式 |
| `cookie_names` | 关键 cookie 名称仍然存在 | `get_cookies` → 检查 name 列表 |
| `sdk_fingerprint` | SDK 特征关键词仍可搜索到 | `search_code` → 匹配关键词 |
| `hot_keys_stable` | hot_keys top 10 与快照重合度 ≥ 70% | `get_instrumentation_log` → 比较 hot_keys |
| `response_structure` | API 响应结构未变 | `get_network_request` → 检查 JSON 字段 |

### 4.2 断言格式

```json
{
  "assertions": [
    {
      "id": 1,
      "type": "script_exists",
      "description": "VMP 脚本 URL 匹配 **/sdenv-*.js",
      "params": { "url_pattern": "**/sdenv-*.js" },
      "last_result": "passed",
      "last_checked": "ISO8601"
    },
    {
      "id": 2,
      "type": "dispatch_loop_count",
      "description": "VMP 分发循环 case 数在 77-97 范围内",
      "params": { "expected": 87, "tolerance": 10 },
      "last_result": "passed",
      "last_checked": "ISO8601"
    }
  ]
}
```

### 4.3 断言执行流程

```
对每条断言：
  ① 根据 type 选择检测方法（MCP 工具调用）
  ② 执行检测，获取实际值
  ③ 与 params 中的期望值比较
  ④ 记录结果：passed / failed / skipped（工具不可用时）
  ⑤ 更新 assertions.json 的 last_result 和 last_checked
```

## 5. 隐私与安全

- **域名哈希化**：目录名使用 `sha256(domain)[0:12]`，不直接暴露域名
- **已加入 .gitignore**：`cases/_session_archives/` 不纳入版本控制
- **敏感数据脱敏**：session.json 中不存储具体 Cookie 值、密钥、Token 等
- **fingerprint.json 仅存结构**：存储属性名和类型，不存储具体指纹值（如 canvas hash）

## 6. 手动操作

### 查看当前域的 Session 档案

```bash
# 计算域名 hash
echo -n "target-domain.com" | sha256sum | cut -c1-12

# 查看档案
cat cases/_session_archives/<hash>/session.json | jq .
```

### 强制刷新档案

在对话中告诉 Agent："刷新当前域的 Session 档案"，Agent 将：
1. 清空 assertions.json
2. 重新执行 Phase 0 + Phase 0.5 的完整流程
3. 重建断言集

### 删除档案

```bash
rm -rf cases/_session_archives/<hash>/
```

## 7. 与经验库（cases/）的关系

| 维度 | Session 档案 | 经验库案例 |
|------|-------------|-----------|
| 粒度 | 单个域 | 一类技术方案 |
| 内容 | 运行时状态（指纹、cookie、断言） | 方法论（定位路径、还原模板） |
| 生命周期 | 7 天有效，自动过期 | 永久，手动更新 |
| 隐私 | 哈希化，不入 git | 脱敏后入 git |
| 用途 | 跳过重复侦察 | 跳过重复分析 |

两者互补：Session 档案回答"这个域现在是什么状态"，经验库回答"这类技术方案怎么破"。
