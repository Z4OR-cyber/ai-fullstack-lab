---
name: knowledge-pipeline
description: 知识原子化流水线。从文章/网页URL抓取内容→原子化为结构化知识卡片（摘要+概念+实体）→写入项目知识库→自动建立wiki交叉引用→更新索引。当用户发送文章链接要求学习、整理笔记、提炼知识点、构建知识库、做内容摘要时使用此技能。整合wechat-article-reader+content-atomizer，支持微信公众号/普通网页/PDF多来源。
---

# Knowledge Pipeline — 知识原子化流水线

将文章、网页、文档自动转化为结构化知识卡片，沉淀到可搜索、可累积的个人知识库。

## 核心理念

不是 RAG（每次检索后遗忘），而是**编译一次、持续累积**：
- 每次输入内容 → 提取实体和概念 → 写入持久知识页
- 后续输入更新已有页面，不重复创建
- 页间用 `[[wiki-link]]` 自动交叉引用
- 知识随使用而增长

## 标准工作流

```
用户发送URL/文件 → 抓取内容 → 原子化分解 → 写入知识库 → 更新索引 → 通知用户
```

### 第一步：内容抓取

根据URL类型选择抓取方式：

**微信公众号文章**（mp.weixin.qq.com）：
```bash
# 使用wechat-article-reader技能
python3 .skills/skill_wechat-article-reader/scripts/fetch_wechat_article.py "URL" -o 用户上传/
```

如果失败（验证拦截），降级策略：
1. curl + iOS微信UA直抓
2. Python requests + OG元数据提取
3. unified-article-reader的unified_fetch.py（四级策略级联）
4. fetch_web 直接读取

**普通网页**：
```
fetch_web(url) — 获取静态网页文本
```

**PDF/Word/PPT**：
```
parse_file(path) — 提取文本内容
```

**用户直接粘贴文本**：
直接使用文本内容。

### 第二步：原子化分解

阅读全文后，提取三类知识卡片：

#### 摘要页（每个来源1个）
- 来源标题、URL、作者、日期
- 2-3段核心摘要
- 5-10个关键要点
- 2-3个可执行洞见

#### 概念页（每个关键概念1个）
- 概念名称（中英文）
- 定义和解释
- 特征/要素
- 应用场景
- 与其他概念的关系

#### 实体页（每个关键实体1个）
- 类型：人物/工具/公司/产品/技术/框架
- 名称和别名
- 一句话描述
- 关键属性
- 与其他实体的关系

**卡片选择原则**：
- 每页聚焦一个主题，不要把多个概念塞进一页
- 选择最重要、最可复用的概念，不必面面俱到
- 一篇2000字文章通常产出 1摘要 + 5-15概念 + 3-8实体

### 第三步：写入知识库

知识库目录结构：
```
knowledge_base/
├── index.json           # 主索引（必须更新）
├── summaries/           # 来源摘要页
├── concepts/            # 概念页
├── entities/            # 实体页
├── comparisons/         # 对比页（可选）
└── relationships.json   # 实体关系图
```

知识页格式：
```markdown
---
type: concept
title: 概念名
aliases: [别名]
sources: ["来源文章标题"]
tags: [标签1, 标签2]
created: 2026-08-15
updated: 2026-08-15
mentions: 1
---

# 概念名

定义和内容...

## 相关概念
- [[其他概念]] - 关系说明
```

文件命名：
- 只用中英文、数字、下划线
- 概念页优先用英文名（如 `Glassmorphism.md`）
- 中文标题去除特殊字符

### 第四步：更新 index.json

```json
{
  "id": "0098",           // 递增，4位数字
  "type": "concept",      // summary/concept/entity
  "title": "概念名",
  "slug": "概念名",
  "file": "concepts/概念名.md",
  "tags": ["tag1"],
  "created": "2026-08-15",
  "mentions": 1
}
```

更新字段：
- `total_pages`: 总数+N
- `type_counts`: 对应类型+N
- `updated`: 当前日期
- pages数组末尾追加新条目

### 第五步：验证与通知

1. 检查所有文件真实存在（`ls` 验证）
2. 验证 index.json JSON格式正确
3. 统计新增卡片数量
4. 向用户简要汇报：新增多少卡片、知识库总量、关键概念列表

## 批量处理

用户一次发送多篇文章时：
1. 逐篇抓取
2. 可以并行原子化（sessions_spawn）
3. 注意概念去重 — 跨文章的相同概念应更新同一页而非新建
4. 最后统一更新一次 index.json

## 知识库质量标准

- ✅ 每页聚焦一个主题
- ✅ 概念页包含定义、特征、应用场景
- ✅ 摘要页包含可执行洞见（不只是信息罗列）
- ✅ 页间有 [[wiki-link]] 交叉引用
- ✅ 同名概念合并而非重复
- ✅ 所有文件在index.json中有对应条目
- ✅ JSON格式合法

## 检索已有知识

```bash
# 搜索知识库
grep -r "关键词" knowledge_base/concepts/ knowledge_base/entities/

# 列出所有概念
ls knowledge_base/concepts/

# 查看索引
cat knowledge_base/index.json | python3 -m json.tool
```

## 注意事项

- 微信文章图片会自动下载，但知识卡片中不需要引用图片
- 抓取失败时不要把URL当关键词搜索，如实告知卡点
- 文章中的广告/推广内容不纳入知识卡片
- 知识卡片用中文撰写，专业术语保留英文原文
