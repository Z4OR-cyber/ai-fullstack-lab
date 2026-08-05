---
name: wechat-article-reader
description: 抓取微信公众号文章并转为干净Markdown，支持图片下载和视频号元数据提取。当用户需要读取公众号文章内容、下载公众号文章、提取公众号文章正文、把微信文章转Markdown、分析公众号文章中的图片和视频、阅读mp.weixin.qq.com链接内容时使用此技能。
---

# 微信公众号文章阅读器

将微信公众号文章 URL 转为结构化 Markdown，自动下载内嵌图片，提取视频号元数据。

## 工作流程

1. 用户提供微信公众号文章 URL（格式：`https://mp.weixin.qq.com/s/xxx`）
2. 运行 `scripts/fetch_wechat_article.py` 抓取文章
3. 脚本返回包含 YAML 元数据的干净 Markdown 正文
4. 图片自动下载到本地目录，URL 重写为相对路径

## 使用方法

### 单篇文章

```bash
python scripts/fetch_wechat_article.py "https://mp.weixin.qq.com/s/xxxxx"
```

### 指定输出目录

```bash
python scripts/fetch_wechat_article.py "https://mp.weixin.qq.com/s/xxxxx" -o ./articles/
```

### 仅提取不下载图片

```bash
python scripts/fetch_wechat_article.py "https://mp.weixin.qq.com/s/xxxxx" --no-images
```

## 输出格式

```markdown
---
title: 文章标题
author: 公众号名称
publish_time: 2024-01-15 10:30:00
source_url: https://mp.weixin.qq.com/s/xxx
fetched_at: 2024-01-20 14:00:00
---

# 文章标题

正文内容（已转为 Markdown）...

![图片描述](images/01_xxxx.jpg)

> 📹 视频：[微信视频号] 时长: 45s | 描述: xxx
```

## 支持的视频类型

| 类型 | 提取内容 |
|------|---------|
| 微信原生视频 | 视频ID、缩略图 |
| 腾讯视频 | 视频VID、封面 |
| 视频号视频 | 时长、描述、点赞数、封面图（公开API） |

## 技术说明

- 使用浏览器 User-Agent 请求公开文章页面，不涉及登录或绕过反爬
- 图片仅下载 PNG/JPG（GIF 过滤），每篇最多 10 张
- 视频号元数据通过微信公开 `batch_get_video_snap` API 获取，无需登录
- 请求间隔默认 1 秒，避免高频访问

## 输入

- `url`（必填）：微信公众号文章 URL
- `-o/--output`（可选）：输出目录，默认为当前目录
- `--no-images`（可选）：不下载图片，仅保留图片 URL

## 依赖

- beautifulsoup4
- lxml
- markdownify
