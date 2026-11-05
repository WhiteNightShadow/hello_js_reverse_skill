# 参数跟踪模板

长期维护一个采集目标时使用，方法见 [参数跟踪与版本归档](../../references/version-tracking.md)。把这些文件复制到需求工作区：

```text
<目标>/
├── README.md              ← surface-readme.md
├── change-log.md          ← change-log.md
├── <SDK 版本>/README.md   ← version-page.md
└── runs/<批次>/sheet.md   ← experiment-sheet.md
```

原始 SDK、Cookie、令牌、响应留在本机私有目录，文档只写位置和哈希。
