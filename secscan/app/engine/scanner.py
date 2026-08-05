"""扫描调度器模块

协调AST分析和正则匹配，根据文件类型选择合适的分析策略。
Python代码使用AST分析器（高精度），JavaScript代码使用正则匹配（覆盖广）。
扫描结果通过 SQLAlchemy 持久化到 SQLite 数据库。
"""

import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.engine.analyzer import PythonASTAnalyzer
from app.engine.rules import RULES
from app.engine.severity import Severity
from app.models.scan_result import ScanResult, ScanSummary, Vulnerability
from app.db.database import init_db, get_session
from app.db import crud


# ============================================================
# JavaScript正则规则定义
# ============================================================
# 每条规则为 (编译后的正则, 规则ID) 元组
JS_PATTERNS: List[tuple] = [
    # SQL注入 - 字符串拼接SQL语句
    (re.compile(r'''["'`].*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s.*["'`]\s*\+''', re.IGNORECASE), "SC001"),
    # 命令注入 - child_process.exec/execSync/spawn/fork
    (re.compile(r'child_process\.(?:exec|execSync|spawn|fork)\s*\('), "SC002"),
    # XSS - innerHTML赋值
    (re.compile(r'\.innerHTML\s*='), "SC003"),
    # XSS - document.write
    (re.compile(r'document\.write\s*\('), "SC003"),
    # 硬编码密钥
    (re.compile(
        r'(?:const|let|var)\s+\w*(?:api_key|apikey|password|secret|token|private_key)\w*\s*=\s*["\'`][^"\'`]{4,}["\'`]',
        re.IGNORECASE
    ), "SC004"),
    # 路径遍历 - fs.readFile/readFileSync/createReadStream + 字符串拼接
    (re.compile(r'fs\.(?:readFile|readFileSync|createReadStream)\s*\([^)]*\+'), "SC005"),
    # 不安全的反序列化 - eval
    (re.compile(r'\beval\s*\('), "SC006"),
    # 弱加密 - createHash('md5'/'sha1')
    (re.compile(r'''createHash\s*\(\s*["'`](?:md5|sha1)["'`]\s*\)''', re.IGNORECASE), "SC007"),
    # SSRF - fetch/axios使用变量URL
    (re.compile(r'(?:fetch|axios\.(?:get|post|put|delete|request))\s*\(\s*[a-zA-Z_$]'), "SC008"),
    # 信息泄露 - console.log输出敏感信息
    (re.compile(r'console\.log\s*\([^)]*(?:password|secret|token|api_key|apikey)', re.IGNORECASE), "SC009"),
    # 不安全的随机数 - Math.random()
    (re.compile(r'Math\.random\s*\(\s*\)'), "SC010"),
]


class Scanner:
    """扫描调度器

    根据文件类型选择分析策略，将扫描结果持久化到数据库。

    用法:
        scanner = Scanner()
        result = scanner.scan_code("example.py", source_code)
        retrieved = scanner.get_result(result.scan_id)
    """

    def __init__(self):
        """初始化扫描器，确保数据库表已创建"""
        init_db()

    def scan_code(self, filename: str, content: str) -> ScanResult:
        """扫描代码文件

        Args:
            filename: 文件名，用于判断语言类型
            content: 文件内容字符串

        Returns:
            ScanResult 完整扫描结果
        """
        # 根据扩展名判断语言
        language = self._detect_language(filename)

        # 根据语言选择分析策略
        if language == "Python":
            findings = self._scan_python(content)
        elif language == "JavaScript":
            findings = self._scan_javascript(content)
        else:
            findings = []

        # 转换为Vulnerability模型对象
        vulnerabilities = [Vulnerability(**f) for f in findings]

        # RAG增强：为每个漏洞的修复建议添加知识库检索内容
        self._enhance_fix_suggestions(vulnerabilities)

        # 构建统计摘要
        summary = self._build_summary(vulnerabilities)

        # 生成扫描ID和结果
        scan_id = str(uuid.uuid4())
        result = ScanResult(
            scan_id=scan_id,
            filename=filename,
            language=language,
            scan_time=datetime.now().isoformat(),
            vulnerabilities=vulnerabilities,
            summary=summary,
        )

        # 持久化到数据库
        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return result

    def get_result(self, scan_id: str) -> Optional[ScanResult]:
        """根据扫描ID获取扫描结果

        从数据库查询，支持应用重启后获取历史记录。

        Args:
            scan_id: 扫描任务ID

        Returns:
            ScanResult 或 None（如果ID不存在）
        """
        db = get_session()
        try:
            return crud.get_scan_result(db, scan_id)
        finally:
            db.close()

    # ============================================================
    # 内部方法
    # ============================================================

    @staticmethod
    def _detect_language(filename: str) -> str:
        """根据文件扩展名检测代码语言"""
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        language_map = {
            'py': 'Python',
            'js': 'JavaScript',
            'mjs': 'JavaScript',
            'javascript': 'JavaScript',
        }
        return language_map.get(ext, 'Unknown')

    @staticmethod
    def _scan_python(content: str) -> List[Dict[str, Any]]:
        """使用AST分析器扫描Python代码"""
        analyzer = PythonASTAnalyzer(content)
        return analyzer.analyze()

    @staticmethod
    def _scan_javascript(content: str) -> List[Dict[str, Any]]:
        """使用正则匹配扫描JavaScript代码

        逐行扫描，对每行应用所有正则规则。
        同一行同一规则只报告一次，避免重复。
        """
        findings: List[Dict[str, Any]] = []
        seen: set = set()  # (rule_id, line_no) 去重
        lines = content.splitlines()

        for line_no, line in enumerate(lines, 1):
            for pattern, rule_id in JS_PATTERNS:
                key = (rule_id, line_no)
                if key in seen:
                    continue
                if pattern.search(line):
                    seen.add(key)
                    rule = RULES[rule_id]
                    findings.append({
                        "rule_id": rule_id,
                        "vuln_type": rule.vuln_type,
                        "cwe_id": rule.cwe_id,
                        "severity": rule.severity.value,
                        "description": rule.description,
                        "line": line_no,
                        "code_snippet": line.strip(),
                        "fix_suggestion": rule.fix_suggestion,
                    })

        return findings

    @staticmethod
    def _enhance_fix_suggestions(vulnerabilities: List[Vulnerability]) -> None:
        """使用RAG模块增强漏洞修复建议

        为每个检测到的漏洞调用FixAdvisor，从知识库中检索相关修复知识，
        将原始修复建议与检索结果整合，生成更详细的增强建议。

        如果RAG模块未初始化或检索失败，保持原始建议不变。
        """
        if not vulnerabilities:
            return

        try:
            from app.rag.advisor import get_advisor
            advisor = get_advisor()
            advisor.enhance_batch(vulnerabilities)
        except Exception:
            # RAG增强失败不影响扫描结果，使用原始建议
            pass

    @staticmethod
    def _build_summary(vulnerabilities: List[Vulnerability]) -> ScanSummary:
        """构建漏洞统计摘要"""
        counts = {s.value: 0 for s in Severity}
        for vuln in vulnerabilities:
            counts[vuln.severity.value] = counts.get(vuln.severity.value, 0) + 1

        return ScanSummary(
            total=len(vulnerabilities),
            critical=counts.get("Critical", 0),
            high=counts.get("High", 0),
            medium=counts.get("Medium", 0),
            low=counts.get("Low", 0),
            info=counts.get("Info", 0),
        )


# 全局扫描器实例（供API路由使用）
scanner = Scanner()
