---
name: content-atomizer
description: 将文章、网页、PDF等内容原子化为结构化知识页，自动提取实体、概念和关系，构建可搜索的个人知识库。当用户需要提炼文章精华、提取知识点、构建知识图谱、做内容摘要、把文章转为知识卡片、整理学习笔记、管理知识库、搜索已保存的知识时使用此技能。
---

# 内容知识原子化器

将任意内容（URL、文本、文件）分解为原子化的结构化知识页，每页聚焦一个实体或概念，页间通过 wiki 链接交叉引用。随着内容不断添加，知识库自动累积和更新。

灵感来自 The Curator（原子化分解）和 knowledge-engine（知识图谱搜索）。

## 核心理念

不是 RAG（每次检索后遗忘），而是**编译一次、持续累积**：
- 每次输入内容时，提取实体和概念，写入持久化知识页
- 后续输入会更新已有页面，而非创建重复
- 页间交叉引用自动建立
- 知识随使用而增长

## 工作流程

### 1. 接收内容

用户提供以下任一形式：
- URL（网页链接）
- 文本内容（直接粘贴或文件路径）
- 已有文件（.md, .txt, .pdf 等）

### 2. 获取内容文本

如果是 URL，运行脚本获取：
```bash
python scripts/knowledge_manager.py fetch "https://example.com/article"
```

如果是文件，直接读取文件内容。

### 3. 原子化分解（LLM 推理）

阅读内容后，提取以下结构化知识：

**摘要页**（每个来源1个）：
- 来源标题、URL、日期
- 2-3段核心摘要
- 5-10个关键要点
- 2-3个可执行洞见

**实体页**（每个关键实体1个）：
- 类型：人物/工具/公司/产品/技术/框架/论文
- 名称和别名
- 一句话描述
- 来源引用
- 与其他实体的关系

**概念页**（每个关键概念1个）：
- 概念名称
- 定义和解释
- 应用场景
- 与其他概念的关系

### 4. 存储到知识库

运行脚本存储知识页：
```bash
python scripts/knowledge_manager.py store --type summary --title "文章标题" --content "..."
python scripts/knowledge_manager.py store --type entity --title "OpenAI" --content "..." --tags "ai-company,llm"
python scripts/knowledge_manager.py store --type concept --title "RAG" --content "..." --tags "retrieval,augmentation"
```

如果同名页面已存在，脚本会合并内容而非覆盖。

### 5. 搜索知识库

```bash
# 全文搜索
python scripts/knowledge_manager.py search "知识图谱嵌入"

# 列出所有页面
python scripts/knowledge_manager.py list

# 查看知识图谱关系
python scripts/knowledge_manager.py graph

# 获取项目推荐（基于已有知识）
python scripts/knowledge_manager.py recommend "构建RAG流水线"
```

## 知识库结构

```
knowledge_base/
├── index.json           # 主索引
├── summaries/           # 来源摘要页
├── entities/            # 实体页（人物/工具/公司/技术）
├── concepts/            # 概念页（方法论/框架/理论）
└── relationships.json   # 实体关系图
```

每个知识页格式：
```markdown
---
type: entity
title: OpenAI
aliases: [OpenAI Inc.]
sources: [001_article.md]
tags: [ai-company, llm]
created: 2024-01-15
updated: 2024-01-15
mentions: 3
---

# OpenAI

OpenAI 是一家 AI 研究公司...

## 相关实体
- [[GPT]] - 开发的大语言模型
- [[Sam Altman]] - CEO
```

## 输出规范

原子化时遵循以下原则：
1. **每页聚焦一个主题** — 不要把多个概念塞进一个页面
2. **交叉引用** — 页面间用 `[[wiki-link]]` 格式链接
3. **合并而非重复** — 同名实体更新已有页面，增加新来源引用
4. **可执行性** — 摘要页必须包含可执行洞见，不只是信息罗列
5. **渐进式** — 每次输入只处理当前内容，不回溯重做已有页面

## 依赖

- beautifulsoup4（URL内容获取）
- lxml（HTML解析）
