"""RAG知识库模块单元测试

测试覆盖：
1. SecurityKnowledgeBase - 知识库加载与检索
2. TFIDFVectorizer - TF-IDF向量化器
3. VectorRetriever - 向量检索器
4. FixAdvisor - 修复建议生成器
5. Scanner集成 - 扫描结果修复建议增强
"""

import os
import numpy as np
import pytest

from app.rag.knowledge_base import SecurityKnowledgeBase, KnowledgeDoc, KnowledgeChunk
from app.rag.retriever import TFIDFVectorizer, VectorRetriever, tokenize
from app.rag.advisor import FixAdvisor, get_advisor
from app.engine.scanner import Scanner
from app.engine.rules import RULES


# ============================================================
# 知识库管理器测试
# ============================================================

class TestKnowledgeBase:
    """安全知识库管理器测试"""

    def test_load_all_10_documents(self):
        """加载后应包含10种漏洞类型的知识文档"""
        kb = SecurityKnowledgeBase()
        kb.load()

        assert kb.is_loaded is True
        assert kb.doc_count == 10, f"期望10个文档，实际{kb.doc_count}"

    def test_load_all_10_rule_ids(self):
        """加载后应包含SC001到SC010的所有规则ID"""
        kb = SecurityKnowledgeBase()
        kb.load()

        doc_ids = kb.list_doc_ids()
        expected_ids = [f"SC{i:03d}" for i in range(1, 11)]
        assert doc_ids == expected_ids, f"文档ID不匹配: {doc_ids}"

    def test_get_doc_returns_correct_document(self):
        """get_doc应返回对应规则ID的知识文档"""
        kb = SecurityKnowledgeBase()
        kb.load()

        doc = kb.get_doc("SC001")
        assert doc is not None
        assert doc.doc_id == "SC001"
        assert "SQL注入" in doc.title or "SQL" in doc.title
        assert len(doc.content) > 100

    def test_get_doc_nonexistent_returns_none(self):
        """不存在的规则ID应返回None"""
        kb = SecurityKnowledgeBase()
        kb.load()

        assert kb.get_doc("SC999") is None

    def test_get_all_chunks_not_empty(self):
        """所有分块列表不应为空"""
        kb = SecurityKnowledgeBase()
        kb.load()

        chunks = kb.get_all_chunks()
        assert len(chunks) > 0
        assert all(isinstance(c, KnowledgeChunk) for c in chunks)

    def test_chunks_have_valid_structure(self):
        """每个分块应有完整的字段"""
        kb = SecurityKnowledgeBase()
        kb.load()

        chunks = kb.get_all_chunks()
        for chunk in chunks:
            assert chunk.chunk_id != ""
            assert chunk.doc_id.startswith("SC")
            assert chunk.title != ""
            assert chunk.text != ""
            assert chunk.source_file.endswith(".md")

    def test_get_chunks_by_doc(self):
        """按文档获取分块应返回正确的分块列表"""
        kb = SecurityKnowledgeBase()
        kb.load()

        chunks = kb.get_chunks_by_doc("SC001")
        assert len(chunks) > 0
        assert all(c.doc_id == "SC001" for c in chunks)

    def test_get_chunks_nonexistent_doc(self):
        """不存在的文档应返回空列表"""
        kb = SecurityKnowledgeBase()
        kb.load()

        assert kb.get_chunks_by_doc("SC999") == []

    def test_chunk_count_greater_than_doc_count(self):
        """分块总数应大于文档数（每个文档被分为多个章节）"""
        kb = SecurityKnowledgeBase()
        kb.load()

        assert kb.chunk_count > kb.doc_count

    def test_lazy_loading(self):
        """首次调用get_doc时自动加载"""
        kb = SecurityKnowledgeBase()
        assert kb.is_loaded is False

        kb.get_doc("SC001")
        assert kb.is_loaded is True

    def test_each_doc_has_multiple_chunks(self):
        """每个文档应有多个分块（至少3个章节）"""
        kb = SecurityKnowledgeBase()
        kb.load()

        for doc_id in kb.list_doc_ids():
            chunks = kb.get_chunks_by_doc(doc_id)
            assert len(chunks) >= 3, f"文档{doc_id}仅有{len(chunks)}个分块"


# ============================================================
# TF-IDF向量化器测试
# ============================================================

class TestTFIDFVectorizer:
    """TF-IDF向量化器测试"""

    def test_fit_builds_vocabulary(self):
        """fit后应构建词汇表"""
        vectorizer = TFIDFVectorizer()
        vectorizer.fit(["hello world python", "sql injection attack"])

        assert vectorizer.vocab_size > 0
        assert "python" in vectorizer.vocabulary
        assert "sql" in vectorizer.vocabulary

    def test_transform_returns_vector(self):
        """transform应返回正确维度的向量"""
        vectorizer = TFIDFVectorizer()
        vectorizer.fit(["hello world python", "sql injection attack"])

        vec = vectorizer.transform("python sql")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (vectorizer.vocab_size,)

    def test_transform_l2_normalized(self):
        """transform返回的向量应L2归一化"""
        vectorizer = TFIDFVectorizer()
        vectorizer.fit(["hello world python", "sql injection attack"])

        vec = vectorizer.transform("python sql")
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-6 or norm == 0.0

    def test_fit_transform_returns_matrix(self):
        """fit_transform应返回正确形状的矩阵"""
        docs = ["hello world python", "sql injection attack", "xss cross site scripting"]
        vectorizer = TFIDFVectorizer()
        matrix = vectorizer.fit_transform(docs)

        assert matrix.shape == (3, vectorizer.vocab_size)

    def test_transform_unknown_words_returns_zeros(self):
        """对词汇表外的词应返回零向量"""
        vectorizer = TFIDFVectorizer()
        vectorizer.fit(["hello world python"])

        vec = vectorizer.transform("xyzabc")
        assert np.all(vec == 0)

    def test_empty_documents_fit(self):
        """空文档列表应能正常处理"""
        vectorizer = TFIDFVectorizer()
        vectorizer.fit([])

        assert vectorizer.vocab_size == 0
        vec = vectorizer.transform("test")
        assert vec.size == 0

    def test_chinese_tokenization(self):
        """应正确分词中文文本"""
        tokens = tokenize("SQL注入漏洞修复指南")
        assert "sql" in tokens
        assert "注" in tokens
        assert "入" in tokens

    def test_mixed_language_tokenization(self):
        """应正确分词中英混合文本"""
        tokens = tokenize("使用bcrypt代替MD5 password hashing")
        assert "bcrypt" in tokens
        assert "md5" in tokens
        assert "password" in tokens


# ============================================================
# 向量检索器测试
# ============================================================

class TestVectorRetriever:
    """向量检索器测试"""

    def test_build_index(self):
        """构建索引后应标记为已构建"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk("c1", "SC001", "SQL注入概述", "SQL注入是常见漏洞", "test.md"),
            KnowledgeChunk("c2", "SC002", "命令注入概述", "命令注入导致RCE", "test.md"),
        ]
        retriever.build_index(chunks)

        assert retriever.is_built is True
        assert retriever.chunk_count == 2

    def test_search_returns_results(self):
        """搜索应返回相关结果"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk("c1", "SC001", "SQL注入概述", "SQL注入 参数化查询 修复", "test.md"),
            KnowledgeChunk("c2", "SC002", "命令注入概述", "命令注入 subprocess 修复", "test.md"),
            KnowledgeChunk("c3", "SC007", "弱加密概述", "MD5 SHA1 bcrypt 密码哈希", "test.md"),
        ]
        retriever.build_index(chunks)

        results = retriever.search("SQL注入参数化", top_k=2)
        assert len(results) > 0
        assert results[0]["doc_id"] == "SC001"

    def test_search_top_k_limit(self):
        """搜索结果数量应不超过top_k"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk(f"c{i}", f"SC00{i}", f"漏洞{i}", f"漏洞类型{i} 修复方案{i}", "test.md")
            for i in range(1, 6)
        ]
        retriever.build_index(chunks)

        results = retriever.search("漏洞修复", top_k=2)
        assert len(results) <= 2

    def test_search_by_doc(self):
        """按文档检索应只返回指定文档的分块"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk("c1", "SC001", "概述", "SQL注入 参数化查询", "test.md"),
            KnowledgeChunk("c2", "SC001", "修复", "使用参数化查询修复SQL注入", "test.md"),
            KnowledgeChunk("c3", "SC002", "概述", "命令注入 subprocess修复", "test.md"),
        ]
        retriever.build_index(chunks)

        results = retriever.search_by_doc("SQL注入修复", "SC001", top_k=5)
        assert len(results) > 0
        assert all(r["doc_id"] == "SC001" for r in results)

    def test_search_results_have_scores(self):
        """搜索结果应包含相似度分数"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk("c1", "SC001", "SQL注入", "SQL注入参数化查询修复", "test.md"),
        ]
        retriever.build_index(chunks)

        results = retriever.search("SQL注入", top_k=1)
        assert len(results) == 1
        assert "score" in results[0]
        assert results[0]["score"] > 0

    def test_search_empty_query(self):
        """空查询应返回空列表"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk("c1", "SC001", "测试", "测试内容", "test.md"),
        ]
        retriever.build_index(chunks)

        results = retriever.search("", top_k=5)
        assert results == []

    def test_search_before_build_returns_empty(self):
        """未构建索引时搜索应返回空列表"""
        retriever = VectorRetriever()
        results = retriever.search("test", top_k=5)
        assert results == []

    def test_search_results_sorted_by_score(self):
        """搜索结果应按相似度降序排列"""
        retriever = VectorRetriever()
        chunks = [
            KnowledgeChunk("c1", "SC001", "SQL注入修复", "SQL注入参数化查询修复方案", "test.md"),
            KnowledgeChunk("c2", "SC002", "命令注入修复", "命令注入subprocess修复方案", "test.md"),
            KnowledgeChunk("c3", "SC007", "弱加密修复", "MD5 SHA1弱加密替换为bcrypt", "test.md"),
        ]
        retriever.build_index(chunks)

        results = retriever.search("SQL注入参数化修复", top_k=3)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_real_kb(self):
        """使用真实知识库检索应返回相关结果"""
        kb = SecurityKnowledgeBase()
        kb.load()
        chunks = kb.get_all_chunks()

        retriever = VectorRetriever()
        retriever.build_index(chunks)

        # 搜索SQL注入相关内容
        results = retriever.search("SQL注入参数化查询", top_k=3)
        assert len(results) > 0
        assert results[0]["doc_id"] == "SC001"

    def test_search_by_doc_finds_correct_type(self):
        """按文档检索应找到正确漏洞类型的知识"""
        kb = SecurityKnowledgeBase()
        kb.load()
        chunks = kb.get_all_chunks()

        retriever = VectorRetriever()
        retriever.build_index(chunks)

        # 搜索弱加密相关内容，限定在SC007文档中
        results = retriever.search_by_doc("MD5密码哈希bcrypt", "SC007", top_k=3)
        assert len(results) > 0
        assert all(r["doc_id"] == "SC007" for r in results)


# ============================================================
# 修复建议生成器测试
# ============================================================

class TestFixAdvisor:
    """修复建议生成器测试"""

    def test_initialize(self):
        """初始化后应标记为已初始化"""
        advisor = FixAdvisor()
        assert advisor.is_initialized is False

        advisor.initialize()
        assert advisor.is_initialized is True

    def test_enhance_suggestion_returns_string(self):
        """增强建议应返回字符串"""
        advisor = FixAdvisor()
        advisor.initialize()

        result = advisor.enhance_suggestion(
            vuln_type="SQL注入",
            description="检测到通过字符串拼接构造SQL语句",
            code_snippet='query = "SELECT * FROM users WHERE id = " + user_id',
            original_suggestion="使用参数化查询代替字符串拼接",
            rule_id="SC001",
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_enhanced_suggestion_contains_original(self):
        """增强建议应包含原始建议内容"""
        advisor = FixAdvisor()
        advisor.initialize()

        original = "使用参数化查询代替字符串拼接"
        result = advisor.enhance_suggestion(
            vuln_type="SQL注入",
            description="检测到通过字符串拼接构造SQL语句",
            code_snippet='query = "SELECT * FROM users WHERE id = " + user_id',
            original_suggestion=original,
            rule_id="SC001",
        )

        assert original in result

    def test_enhanced_suggestion_contains_kb_content(self):
        """增强建议应包含知识库检索的内容"""
        advisor = FixAdvisor()
        advisor.initialize()

        result = advisor.enhance_suggestion(
            vuln_type="SQL注入",
            description="检测到通过字符串拼接构造SQL语句",
            code_snippet='query = "SELECT * FROM users WHERE id = " + user_id',
            original_suggestion="使用参数化查询",
            rule_id="SC001",
        )

        # 增强建议应包含知识库参考标记
        assert "知识库参考" in result or "参考" in result

    def test_enhanced_suggestion_longer_than_original(self):
        """增强建议应比原始建议更长"""
        advisor = FixAdvisor()
        advisor.initialize()

        original = "使用参数化查询"
        result = advisor.enhance_suggestion(
            vuln_type="SQL注入",
            description="SQL注入漏洞",
            code_snippet='cursor.execute("SELECT * FROM users WHERE id = " + user_id)',
            original_suggestion=original,
            rule_id="SC001",
        )

        assert len(result) > len(original)

    def test_enhance_all_10_vuln_types(self):
        """应能为所有10种漏洞类型生成增强建议"""
        advisor = FixAdvisor()
        advisor.initialize()

        test_cases = [
            ("SC001", "SQL注入", "字符串拼接SQL语句"),
            ("SC002", "命令注入", "os.system拼接用户输入"),
            ("SC003", "XSS跨站脚本", "render_template_string拼接"),
            ("SC004", "硬编码密钥", "API_KEY硬编码在代码中"),
            ("SC005", "路径遍历", "open拼接用户输入路径"),
            ("SC006", "不安全的反序列化", "pickle.loads处理不可信数据"),
            ("SC007", "弱加密算法", "使用MD5哈希密码"),
            ("SC008", "SSRF服务端请求伪造", "requests.get使用用户URL"),
            ("SC009", "敏感信息泄露", "print输出密码"),
            ("SC010", "不安全的随机数", "random生成令牌"),
        ]

        for rule_id, vuln_type, desc in test_cases:
            result = advisor.enhance_suggestion(
                vuln_type=vuln_type,
                description=desc,
                code_snippet="test_code",
                original_suggestion="原始修复建议",
                rule_id=rule_id,
            )
            assert isinstance(result, str)
            assert len(result) > len("原始修复建议")

    def test_enhance_suggestion_without_rule_id(self):
        """不提供rule_id时应使用全局检索"""
        advisor = FixAdvisor()
        advisor.initialize()

        result = advisor.enhance_suggestion(
            vuln_type="SQL注入",
            description="SQL注入漏洞",
            code_snippet='execute("SELECT " + col)',
            original_suggestion="参数化查询",
            rule_id=None,
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_advisor_singleton(self):
        """get_advisor应返回单例"""
        advisor1 = get_advisor()
        advisor2 = get_advisor()
        assert advisor1 is advisor2

    def test_enhance_batch(self):
        """批量增强应修改所有漏洞对象的修复建议"""
        advisor = FixAdvisor()
        advisor.initialize()

        from app.models.scan_result import Vulnerability
        vulns = [
            Vulnerability(
                rule_id="SC001", vuln_type="SQL注入", cwe_id="CWE-89",
                severity="Critical", description="SQL注入漏洞",
                line=1, code_snippet='execute("SELECT" + id)',
                fix_suggestion="原始建议1",
            ),
            Vulnerability(
                rule_id="SC007", vuln_type="弱加密算法", cwe_id="CWE-327",
                severity="High", description="使用MD5",
                line=2, code_snippet="hashlib.md5(data)",
                fix_suggestion="原始建议2",
            ),
        ]

        original_lengths = [len(v.fix_suggestion) for v in vulns]
        advisor.enhance_batch(vulns)

        for i, vuln in enumerate(vulns):
            assert len(vuln.fix_suggestion) > original_lengths[i]


# ============================================================
# Scanner集成测试
# ============================================================

class TestScannerRAGIntegration:
    """扫描器与RAG模块集成测试"""

    def test_scan_result_has_enhanced_suggestion(self):
        """扫描结果中的修复建议应被RAG增强"""
        scanner = Scanner()
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test.py", code)

        assert len(result.vulnerabilities) > 0
        suggestion = result.vulnerabilities[0].fix_suggestion

        # 增强后的建议应包含知识库参考内容
        assert "知识库参考" in suggestion or "参考" in suggestion

    def test_enhanced_suggestion_longer_than_rule_default(self):
        """增强后的建议应比规则中的默认建议更长"""
        scanner = Scanner()
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test.py", code)

        vuln = result.vulnerabilities[0]
        original = RULES[vuln.rule_id].fix_suggestion

        assert len(vuln.fix_suggestion) > len(original)

    def test_all_vulnerabilities_have_enhanced_suggestions(self):
        """扫描出的所有漏洞都应有增强建议"""
        scanner = Scanner()
        # 触发多种漏洞的代码
        code = (
            'import os\n'
            'import pickle\n'
            'import hashlib\n'
            'import random\n'
            'import requests\n'
            'API_KEY = "sk-1234567890abcdef"\n'
            'os.system("ping " + host)\n'
            'pickle.loads(data)\n'
            'h = hashlib.md5(password)\n'
            'token = random.random()\n'
            'r = requests.get(user_url)\n'
            'print(f"password: {password}")\n'
            'f = open("/data/" + filename)\n'
            'query = "SELECT * FROM users WHERE id = " + user_id\n'
            'cursor.execute(query)\n'
        )
        result = scanner.scan_code("test.py", code)

        assert len(result.vulnerabilities) >= 5
        for vuln in result.vulnerabilities:
            assert len(vuln.fix_suggestion) > len(RULES[vuln.rule_id].fix_suggestion)

    def test_clean_code_still_works(self):
        """安全代码扫描不受RAG模块影响"""
        scanner = Scanner()
        result = scanner.scan_code("test.py", "x = 1\ny = 2\nprint(x + y)")

        assert len(result.vulnerabilities) == 0

    def test_sql_injection_enhanced_with_kb_content(self):
        """SQL注入的修复建议应包含知识库中的参数化查询内容"""
        scanner = Scanner()
        code = 'query = "SELECT * FROM users WHERE id = " + user_id\ncursor.execute(query)'
        result = scanner.scan_code("test.py", code)

        vulns = [v for v in result.vulnerabilities if v.rule_id == "SC001"]
        assert len(vulns) > 0

        suggestion = vulns[0].fix_suggestion
        # 增强建议应包含知识库参考标记
        assert "知识库参考" in suggestion or "参考" in suggestion
