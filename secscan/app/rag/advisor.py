"""修复建议生成器模块

集成知识库和向量检索器，为检测到的安全漏洞生成增强的修复建议。
将漏洞的原始修复建议与知识库检索到的相关内容整合，提供更详细的修复指导。

工作流程：
1. 初始化时加载知识库并构建向量索引
2. 接收漏洞信息（类型、描述、代码片段、原始建议）
3. 构造查询文本，检索知识库中的相关内容
4. 将原始建议与检索结果整合，生成增强的修复建议
"""

from typing import Optional, List, Dict

from app.rag.knowledge_base import SecurityKnowledgeBase, KnowledgeChunk
from app.rag.retriever import VectorRetriever


class FixAdvisor:
    """修复建议生成器

    集成知识库和向量检索器，为安全漏洞提供基于RAG的增强修复建议。

    用法:
        advisor = FixAdvisor()
        advisor.initialize()
        enhanced = advisor.enhance_suggestion(
            vuln_type="SQL注入",
            description="...",
            code_snippet="...",
            original_suggestion="...",
            rule_id="SC001",
        )
    """

    def __init__(self):
        """初始化修复建议生成器"""
        self.kb = SecurityKnowledgeBase()
        self.retriever = VectorRetriever()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    def initialize(self) -> None:
        """初始化：加载知识库并构建向量索引

        加载所有知识文档，将分块转换为TF-IDF向量索引。
        此方法只需调用一次，后续检索复用已构建的索引。
        """
        if self._initialized:
            return

        # 加载知识库
        self.kb.load()

        # 构建向量索引
        chunks = self.kb.get_all_chunks()
        if chunks:
            self.retriever.build_index(chunks)

        self._initialized = True

    def enhance_suggestion(
        self,
        vuln_type: str,
        description: str,
        code_snippet: str,
        original_suggestion: str,
        rule_id: Optional[str] = None,
    ) -> str:
        """增强修复建议

        根据漏洞信息检索知识库，将检索到的相关内容与原始建议整合，
        生成更详细的修复建议。

        策略：
        1. 优先按rule_id直接获取该漏洞类型的知识文档
        2. 使用向量检索获取最相关的知识分块
        3. 将原始建议与检索结果整合，生成增强建议

        Args:
            vuln_type: 漏洞类型名称，如 "SQL注入"
            description: 漏洞描述
            code_snippet: 漏洞代码片段
            original_suggestion: 原始修复建议
            rule_id: 规则ID，如 "SC001"

        Returns:
            增强后的修复建议字符串
        """
        if not self._initialized:
            self.initialize()

        # 构造查询文本：漏洞类型 + 描述 + 代码片段
        query = f"{vuln_type} {description} {code_snippet}"

        # 策略1：按rule_id直接检索该漏洞类型的知识分块
        doc_chunks: List[Dict] = []
        if rule_id:
            doc_chunks = self.retriever.search_by_doc(query, rule_id, top_k=3)

        # 策略2：如果按文档检索结果不足，使用全局检索补充
        if len(doc_chunks) < 2:
            global_results = self.retriever.search(query, top_k=3)
            # 去重：避免重复添加同一分块
            existing_ids = {c["chunk_id"] for c in doc_chunks}
            for result in global_results:
                if result["chunk_id"] not in existing_ids:
                    doc_chunks.append(result)
                    existing_ids.add(result["chunk_id"])
                if len(doc_chunks) >= 4:
                    break

        # 如果没有检索到任何知识，返回原始建议
        if not doc_chunks:
            return original_suggestion

        # 整合原始建议和检索结果
        return self._compose_suggestion(
            original_suggestion, doc_chunks, vuln_type
        )

    def _compose_suggestion(
        self,
        original: str,
        retrieved_chunks: List[Dict],
        vuln_type: str,
    ) -> str:
        """将原始建议与检索到的知识整合为增强建议

        格式：
        [原始修复建议]
        ---
        [知识库参考]
        来源1: [标题] 内容摘要...
        来源2: [标题] 内容摘要...

        Args:
            original: 原始修复建议
            retrieved_chunks: 检索到的知识分块列表
            vuln_type: 漏洞类型名称

        Returns:
            整合后的增强修复建议
        """
        parts: List[str] = [original.strip()]

        parts.append("")
        parts.append("---")
        parts.append("📚 知识库参考（RAG增强）：")
        parts.append("")

        for i, chunk in enumerate(retrieved_chunks[:3], 1):
            title = chunk.get("title", "")
            text = chunk.get("text", "")
            doc_id = chunk.get("doc_id", "")
            score = chunk.get("score", 0.0)

            # 截取知识内容的前500字符作为摘要
            summary = text[:500]
            if len(text) > 500:
                summary += "..."

            parts.append(f"参考{i}: [{title}]")
            parts.append(f"  相关度: {score:.1%}")
            parts.append(f"  {summary}")
            parts.append("")

        return "\n".join(parts)

    def enhance_batch(self, vulnerabilities: List) -> None:
        """批量增强漏洞列表的修复建议

        直接修改传入的漏洞对象的 fix_suggestion 字段。

        Args:
            vulnerabilities: Vulnerability对象列表
        """
        if not self._initialized:
            self.initialize()

        for vuln in vulnerabilities:
            enhanced = self.enhance_suggestion(
                vuln_type=vuln.vuln_type,
                description=vuln.description,
                code_snippet=vuln.code_snippet,
                original_suggestion=vuln.fix_suggestion,
                rule_id=vuln.rule_id,
            )
            if enhanced:
                vuln.fix_suggestion = enhanced


# ============================================================
# 模块级单例管理
# ============================================================

_advisor: Optional[FixAdvisor] = None


def get_advisor() -> FixAdvisor:
    """获取全局FixAdvisor单例实例

    首次调用时创建并初始化实例，后续调用返回同一实例。
    确保知识库只加载一次，避免重复构建索引。

    Returns:
        FixAdvisor 单例实例
    """
    global _advisor
    if _advisor is None:
        _advisor = FixAdvisor()
        _advisor.initialize()
    return _advisor
