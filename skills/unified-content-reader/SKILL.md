---
name: unified-content-reader
description: 统一内容抓取器。整合文章抓取器(article-reader)和微信公众号阅读器(wechat-article-reader)为单一技能，支持微信公众号、知乎、今日头条、通用网页等多平台内容抓取。采用两级策略：先fetch_web直取，被robots.txt拦截后自动切换agent-browser+iPhone设备模拟绕过验证码。当用户需要读取网页文章、抓取公众号内容、提取文章正文、把文章转Markdown、分析文章中的图片和视频时使用此技能。
---

# 统一内容抓取器

> 整合自：article-reader + wechat-article-reader
> 覆盖：微信公众号、知乎、今日头条、通用网页 → 干净Markdown

## 两级抓取策略

### Level 1: fetch_web 直取
```
fetch_web(url) → 成功 → 返回内容
                → 失败(robots.txt/403/空内容) → Level 2
```

### Level 2: agent-browser 浏览器抓取
```
sessions_spawn(agent-browser) → iPhone 14设备模拟 → 绕过滑块验证码 → 提取正文
```

**关键经验**：
- 桌面模式浏览器被微信重定向到滑块验证码页面
- iPhone 14 设备模拟可成功绕过微信验证码
- agent-browser 必须在子session(sessions_spawn)中执行，禁止主session直接调用
- fetch_web 失败时不要把URL作为关键词去搜索，直接切换到Level 2

## 支持平台

| 平台 | 抓取方式 | 特殊处理 |
|------|---------|---------|
| 微信公众号 (mp.weixin.qq.com) | Level 2 (iPhone模拟) | 需绕过验证码 |
| 知乎专栏 | Level 1 或 Level 2 | robots.txt可能拦截 |
| 今日头条 | Level 1 | 通常可直接抓取 |
| 通用网页 | Level 1 | 大多数网页可直接抓取 |
| 原始博客(非CMS) | Level 1 | 如 lilianweng.github.io |

## 输出格式

```markdown
---
title: 文章标题
author: 作者/公众号
publish_time: 发布时间
source_url: 原始URL
fetched_at: 抓取时间
fetch_method: fetch_web | agent-browser
---

# 文章标题

正文内容（已转为干净Markdown）...

![图片描述](images/xxx.jpg)

> 视频：[视频号] 时长: 45s | 描述: xxx
```

## 使用方法

### 自动模式（推荐）
用户分享文章链接后，自动按两级策略抓取：
1. 尝试 fetch_web 读取
2. 失败则派发子session用agent-browser + iPhone模拟抓取

### 手动指定模式
用户明确要求用浏览器抓取时，直接走Level 2。

## 视频号元数据提取
- 微信原生视频：视频ID、缩略图
- 腾讯视频：视频VID、封面
- 视频号视频：时长、描述、点赞数、封面图（通过公开API）

## 技术说明
- 使用浏览器User-Agent请求公开文章页面，不涉及登录
- 图片仅下载PNG/JPG（GIF过滤），每篇最多10张
- 请求间隔默认1秒，避免高频访问
- 依赖：beautifulsoup4, lxml, markdownify（Level 1）；agent-browser（Level 2）

## 三平台发布状态
- Coze 技能商店：已发布（作为article-reader，skill_id: 7673114615181606952）
- EvoMap：已发布（bundle_685da0ce2d3431e1）
- GitHub：skills/unified-content-reader/SKILL.md

## 许可
MIT
