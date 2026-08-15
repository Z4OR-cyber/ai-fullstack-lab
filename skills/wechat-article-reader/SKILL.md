---
name: wechat-article-reader
description: "[已废弃] 请使用 unified-content-reader。微信公众号文章专用抓取。"
deprecated: true
replaced_by: unified-content-reader
---

> ⚠️ **已废弃（2026-08-15）**：本技能已被 `unified-content-reader` 取代。后者整合了 article-reader 和 wechat-article-reader 的全部功能，支持四级降级策略和微信双模式抓取。请使用 `unified-content-reader`。

# 微信文章抓取器（已废弃）

功能已迁移至 `unified-content-reader`，包含：
- 微信公众号文章抓取（含滑块验证码绕过）
- 四级降级策略：curl → Python → 完整脚本 → 浏览器
- iPhone设备模拟
- 多平台支持（微信、知乎、今日头条等）
