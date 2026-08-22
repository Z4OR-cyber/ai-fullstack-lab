---
name: article-reader
description: "[已废弃] 请使用 unified-article-reader（四级策略级联文章抓取，覆盖微信公众号/知乎/今日头条/掘金/CSDN等平台）。"
deprecated: true
replaced_by: unified-article-reader
deprecated_date: 2026-08-22
---

> **DEPRECATED (2026-08-22)**: Use `unified-article-reader` instead.
>
> 本技能仅保留2层降级（fetch_web → agent-browser），功能已被 `unified-article-reader` 完全覆盖：
> - 四级策略级联（curl直抓 → Python requests+iOS微信UA → 完整脚本提取 → agent-browser兜底）
> - 微信文章双模式HTML解析 + OG meta三级回退
> - 验证码自动检测与策略切换
> - 多平台支持（微信公众号/知乎/今日头条/掘金/CSDN/Medium）
>
> Coze技能商店版本：`web-article-fetcher`（skill_id: 7674228102490226715）

# Article Reader（已废弃）

功能已迁移至 `unified-article-reader`。请勿再使用本技能。
