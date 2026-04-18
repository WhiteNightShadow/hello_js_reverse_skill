# CHANGELOG v2.9.0 — 域级 Session 档案 + 断言驱动交付

**日期**：2026-04-22
**MCP 版本**：camoufox-reverse v0.8.0（78 个工具）

---

## 核心新增

### 1. 域级 Session 档案

每个目标域维护一份持久化 Session 档案（`cases/_session_archives/<domain-hash>/`），跨任务复用反爬类型判定、指纹基准、Cookie 归因结论，避免重复侦察。

- **session.json**：核心元数据（反爬类型、工具链、hot_keys 快照、Cookie 归因摘要）
- **fingerprint.json**：浏览器指纹基准快照
- **cookie-attribution.json**：Cookie 归因结论缓存
- **assertions.json**：断言集（通过/失败/跳过）
- 域名哈希化存储，已加入 `.gitignore`，不纳入版本控制

### 2. 断言系统

Session 档案的核心验证机制。每条断言描述一个可自动检测的技术事实，用于快速判断目标站点是否发生了技术变更。

- 8 种断言类型：`script_exists` / `script_size_range` / `dispatch_loop_count` / `anti_crawl_type` / `cookie_names` / `sdk_fingerprint` / `hot_keys_stable` / `response_structure`
- Phase 0.5 前置 Reverify：断言全部通过则跳过重复侦察，直接进入 Phase 1
- Phase 5 交付时自动更新断言集

### 3. 断言驱动交付（Phase 5 升级）

Phase 5 从"运行验证 + README"升级为断言驱动的结构化交付：

1. 运行 main.js/main.py，确认输出正确数据
2. 与浏览器实际数据交叉验证（≥ 5 次请求）
3. **写入/更新域级 Session 档案**（断言集 + 指纹快照 + Cookie 归因）
4. 生成 README.md
5. 主动询问用户是否沉淀经验到 `cases/`

### 4. 禁止未经梯度降级切换（第一原则第 5 条）

新增原则：遇到工具失败时，必须按降级梯度逐级尝试，禁止直接跳到最终方案。

降级梯度：
```
instrument_jsvmp_source(mode="ast")
  → instrument_jsvmp_source(mode="regex")
    → hook_jsvmp_interpreter(mode="transparent")
      → hook_jsvmp_interpreter(mode="proxy")  [仅行为型]
        → 纯 pre_inject_hooks 观察  [仅行为型/纯混淆]
```

### 5. AI 想放弃时的降级梯度表

错误处理新增降级梯度表，覆盖 6 种常见"想放弃"场景及对应的降级路径。

---

## 工作流变更

| 阶段 | 变更 |
|------|------|
| Phase 0 | 新增步骤 4：启动域级 Session 档案（加载/创建） |
| Phase 0.5 | 新增前置步骤 0.5.-1：本域断言 Reverify |
| Phase 5 | 升级为断言驱动交付（写入 Session 档案 + 断言集） |

## SKILL.md 变更点

| 变更点 | 说明 |
|--------|------|
| frontmatter description | MCP 版本升至 v0.8.0（78 工具），新增 v2.9.0 描述 |
| 第一原则 | 新增第 5 条「禁止未经梯度降级切换」 |
| Phase 0 | 新增步骤 4「启动域级 Session 档案」 |
| Phase 0.5 | 新增 0.5.-1「本域断言 Reverify」前置步骤 |
| Phase 5 | 替换为断言驱动交付 |
| 核心武器 | 工具总数 78，版本 v0.8.0，新增域级 Session 档案与断言小节 |
| 场景 10/11 | MCP 操作清单追加 Session 相关步骤 |
| 错误处理 | 新增「AI 想放弃时的降级梯度表」 |
| 经验法则 | 扩充至 46 条（+41-46） |
| 更新记录 | 追加 v2.9.0 条目 |

## 新增文件

| 文件 | 说明 |
|------|------|
| `references/domain-session-guide.md` | 域级 Session 档案完整指南 |
| `CHANGELOG_v2.9.0.md` | 本文件 |

## 修改文件

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 10 个变更点（见上表） |
| `cases/README.md` | 新案例沉淀工作流插入步骤 1.5（Session 档案归档） |
| `.gitignore` | 追加 `cases/_session_archives/` |
