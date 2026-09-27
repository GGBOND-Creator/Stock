# Codex 对话迁移记录

更新时间：2026-09-27

## 2026-09-27 GitHub 接入

本地 `C:\stock` 已初始化 Git，`main` 的 `origin` 指向 `https://github.com/GGBOND-Creator/Stock.git`。首次提交已推送。`.gitignore` 排除的行情 CSV、模型和部分报告仍需单独备份。

## 2026-09-10 迁移前复核

本次复核确认：

- 项目代码、测试、数据、模型、报告和原始归档仍位于完整项目目录中。
- 本地完整测试为 66 项，2026-09-11 复跑全部通过。
- `data/realtime/a_share_spot.csv` 仍是 `2026-07-20T10:45:28` 的旧快照，不能作为当前行情。
- 当时 `.git` 目录没有可用 Git 元数据；2026-09-27 已初始化。迁移仍应复制整个项目目录，不能只复制聊天记录或只依赖克隆。
- 迁移摘要已集中写入 `docs/ACCOUNT_MIGRATION_BRIEF.md`；完整背景和工作规则仍以 `AI_HANDOFF.md` 为准。

## 迁移目标

将股票模型项目的后续 Codex 工作迁移到新的项目路径：

```text
C:\stock
```

Obsidian 仓库路径：

```text
C:\stock\stock
```

Obsidian 项目笔记目录：

```text
C:\stock\stock\股票模型项目
```

## Codex 项目

Codex 已识别到本地项目：

```text
项目名：stock
项目路径：C:\stock
```

已创建新的 Codex 项目任务用于承接后续工作。

## 当前上下文摘要

- 项目定位：低成本、可迁移、可复现的股票走势研究框架。
- 本对话主线：整体框架设定、模型路线、模块边界、规划维护。
- 数据接入细节：放到其他对话中处理。
- 当前主线：人的需求—资源—生产网络 v2；A 股产业网络和资金控制模型保留为下游/历史实验分支。
- 框架主文档：`docs/framework_presentation.md`
- 数据台账：`docs/DATA_STATUS.md`
- 账号迁移摘要：`docs/ACCOUNT_MIGRATION_BRIEF.md`
- Obsidian 同步脚本：`scripts/sync_obsidian.py`
- Obsidian 同步目录：`C:\stock\stock\股票模型项目`

## 后续维护规则

涉及整体框架、模型路线、模块边界、规划变更时：

1. 更新 `docs/framework_presentation.md`
2. 必要时更新项目内对应专题文档
3. 执行 `python scripts/sync_obsidian.py`
4. 确认 Obsidian 中编号笔记已更新

涉及数据源、字段口径、抓取脚本、数据文件状态时：

1. 更新 `docs/DATA_STATUS.md`
2. 执行 `python scripts/sync_obsidian.py`
3. 将具体数据接入细节保留在数据接入相关对话中
