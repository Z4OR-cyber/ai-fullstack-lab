"""RAG知识库增强模块

为SecScan安全审计平台提供基于RAG的修复建议增强能力。
包含三个核心组件：
- KnowledgeBase: 安全知识库管理器，加载Markdown知识文档
- VectorRetriever: 向量检索器，基于TF-IDF + 余弦相似度
- FixAdvisor: 修复建议生成器，整合检索结果生成增强建议

所有实现均基于纯numpy和Python标准库，无需外部API Key。
"""
