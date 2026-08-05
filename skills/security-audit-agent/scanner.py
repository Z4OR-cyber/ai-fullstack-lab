"""
安全扫描引擎
支持 Python（AST分析 + 模式匹配）和 C（模式匹配）代码扫描
"""

import ast
import re
import os
from typing import List, Dict, Any
from rules import PYTHON_RULES, C_RULES, GENERIC_RULES, SEVERITY_WEIGHT


class Vulnerability:
    """漏洞发现"""
    def __init__(self, rule_id, category, name, severity, file_path, line_num,
                 attack_type, description, defense, code_snippet=""):
        self.rule_id = rule_id
        self.category = category
        self.name = name
        self.severity = severity
        self.file_path = file_path
        self.line_num = line_num
        self.attack_type = attack_type
        self.description = description
        self.defense = defense
        self.code_snippet = code_snippet

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "name": self.name,
            "severity": self.severity,
            "file": self.file_path,
            "line": self.line_num,
            "attack": self.attack_type,
            "description": self.description,
            "fix": self.defense,
            "code": self.code_snippet.strip() if self.code_snippet else "",
        }


class PythonASTAnalyzer(ast.NodeVisitor):
    """Python AST分析器 - 检测AST层面的安全问题"""

    def __init__(self, filepath, source_lines):
        self.filepath = filepath
        self.source_lines = source_lines
        self.findings: List[Vulnerability] = []
        self._imported_names = set()

    def _get_line(self, node):
        """安全获取行号"""
        return getattr(node, 'lineno', 0)

    def _get_code_snippet(self, line):
        """获取代码片段"""
        if 0 < line <= len(self.source_lines):
            return self.source_lines[line - 1].strip()
        return ""

    def visit_Import(self, node):
        for alias in node.names:
            self._imported_names.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self._imported_names.add(node.module)
        self.generic_visit(node)

    def visit_Call(self, node):
        line = self._get_line(node)
        snippet = self._get_code_snippet(line)

        # 获取调用函数名
        func_name = self._get_call_name(node)

        # --- SQL注入检测 ---
        if func_name in ("execute", "executemany", "executescript"):
            if node.args:
                first_arg = node.args[0]
                # f-string SQL
                if isinstance(first_arg, ast.JoinedStr):
                    self.findings.append(Vulnerability(
                        "PY001", "注入", "SQL注入", "CRITICAL",
                        self.filepath, line,
                        "字符串拼接SQL查询",
                        "SQL查询使用f-string拼接，攻击者可注入恶意SQL语句。",
                        "使用参数化查询（占位符?/%s），永不拼接用户输入到SQL语句。",
                        snippet
                    ))
                # 字符串格式化
                elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                    self.findings.append(Vulnerability(
                        "PY001", "注入", "SQL注入", "CRITICAL",
                        self.filepath, line,
                        "字符串拼接SQL查询",
                        "SQL查询使用%格式化拼接，存在SQL注入风险。",
                        "使用参数化查询（占位符?/%s），永不拼接用户输入到SQL语句。",
                        snippet
                    ))
                # 字符串拼接
                elif isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Add):
                    self.findings.append(Vulnerability(
                        "PY001", "注入", "SQL注入", "CRITICAL",
                        self.filepath, line,
                        "字符串拼接SQL查询",
                        "SQL查询使用+拼接，存在SQL注入风险。",
                        "使用参数化查询（占位符?/%s），永不拼接用户输入到SQL语句。",
                        snippet
                    ))

        # --- 命令注入检测 ---
        if func_name == "system":
            self.findings.append(Vulnerability(
                "PY002", "注入", "命令注入", "CRITICAL",
                self.filepath, line,
                "os.system执行命令",
                "os.system通过shell执行命令，若含用户输入可注入任意命令。",
                "使用subprocess.run(shell=False, args=[...])并做白名单校验。",
                snippet
            ))

        if func_name == "popen":
            self.findings.append(Vulnerability(
                "PY002", "注入", "命令注入", "CRITICAL",
                self.filepath, line,
                "os.popen执行命令",
                "os.popen通过shell执行命令，存在命令注入风险。",
                "使用subprocess.run(shell=False)并传入参数列表。",
                snippet
            ))

        if func_name in ("eval", "exec"):
            self.findings.append(Vulnerability(
                "PY002", "注入", "命令注入/代码注入", "CRITICAL",
                self.filepath, line,
                f"{func_name}执行动态代码",
                f"{func_name}可执行任意代码，若输入不可信则导致代码注入。",
                "避免使用eval/exec；如必须用，严格限制输入范围并沙箱化。",
                snippet
            ))

        # --- 不安全反序列化 ---
        if func_name in ("loads", "load") and "pickle" in str(self._imported_names):
            self.findings.append(Vulnerability(
                "PY009", "授权安全", "不安全反序列化", "CRITICAL",
                self.filepath, line,
                "pickle反序列化不可信数据",
                "pickle反序列化可导致远程代码执行。",
                "使用json替代pickle；如必须用，仅反序列化可信数据。",
                snippet
            ))

        # --- 弱密码哈希 ---
        if func_name in ("md5", "sha1"):
            self.findings.append(Vulnerability(
                "PY007", "认证安全", "弱密码哈希", "HIGH",
                self.filepath, line,
                f"使用{func_name.upper()}哈希",
                f"{func_name.upper()}已被破解，不适合密码存储。",
                "使用bcrypt/scrypt/argon2，配合随机salt。",
                snippet
            ))

        # --- 弱随机数 ---
        if func_name in ("choice", "randint", "random") and "random" in self._imported_names:
            # 检查上下文是否有安全相关变量
            context = " ".join(self.source_lines[max(0, line-5):line+5])
            security_keywords = ["password", "token", "session", "secret", "csrf", "key"]
            if any(kw in context.lower() for kw in security_keywords):
                self.findings.append(Vulnerability(
                    "PY012", "加密安全", "弱随机数", "MEDIUM",
                    self.filepath, line,
                    "安全场景使用random模块",
                    "random是伪随机可预测，用于生成Token/密码等不安全。",
                    "安全场景使用secrets模块或os.urandom()。",
                    snippet
                ))

        self.generic_visit(node)

    def _get_call_name(self, node):
        """提取调用函数名"""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        elif isinstance(func, ast.Attribute):
            return func.attr
        return ""


class CodeScanner:
    """代码安全扫描器"""

    def __init__(self):
        self.findings: List[Vulnerability] = []
        self.files_scanned = 0
        self.lines_scanned = 0

    def scan_file(self, filepath: str) -> List[Vulnerability]:
        """扫描单个文件"""
        if not os.path.isfile(filepath):
            return []

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return []

        lines = content.splitlines()
        self.files_scanned += 1
        self.lines_scanned += len(lines)

        ext = os.path.splitext(filepath)[1].lower()
        filename = os.path.basename(filepath).lower()

        file_findings = []

        # 根据文件类型选择规则
        if ext == '.py':
            file_findings = self._scan_python(filepath, content, lines)
        elif ext in ('.c', '.h', '.cpp', '.cc', '.hpp'):
            file_findings = self._scan_c(filepath, content, lines)
        elif filename in ('requirements.txt', 'package.json'):
            file_findings = self._scan_generic(filepath, content, lines)
        else:
            # 通用规则扫描所有文本文件
            file_findings = self._scan_generic(filepath, content, lines)

        self.findings.extend(file_findings)
        return file_findings

    def scan_directory(self, dirpath: str, exclude=None) -> List[Vulnerability]:
        """递归扫描目录"""
        if exclude is None:
            exclude = {'.git', '__pycache__', 'node_modules', '.venv', 'venv',
                       '.idea', '.vscode', 'dist', 'build', '.eggs', '*.egg-info'}

        supported_exts = {'.py', '.c', '.h', '.cpp', '.cc', '.hpp', '.txt', '.json'}

        for root, dirs, files in os.walk(dirpath):
            # 排除目录
            dirs[:] = [d for d in dirs if d not in exclude]

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in supported_exts or fname.lower() in ('requirements.txt', 'package.json'):
                    self.scan_file(os.path.join(root, fname))

        return self.findings

    def _scan_python(self, filepath, content, lines) -> List[Vulnerability]:
        """Python代码扫描：AST + 模式匹配"""
        findings = []

        # AST分析
        try:
            tree = ast.parse(content)
            analyzer = PythonASTAnalyzer(filepath, lines)
            analyzer.visit(tree)
            findings.extend(analyzer.findings)
        except SyntaxError:
            pass  # 语法错误时跳过AST，仅做模式匹配

        # 模式匹配（补充AST未覆盖的）
        for rule in PYTHON_RULES:
            if "ast_check" in rule:
                continue  # AST已覆盖
            for i, line in enumerate(lines, 1):
                for pattern in rule["patterns"]:
                    if re.search(pattern, line, re.IGNORECASE):
                        # 上下文过滤
                        if "context_filter" in rule:
                            context = " ".join(lines[max(0, i-5):i+5]).lower()
                            if not any(kw in context for kw in rule["context_filter"]):
                                continue
                        # 避免重复
                        if not any(f.rule_id == rule["id"] and f.line_num == i for f in findings):
                            findings.append(Vulnerability(
                                rule["id"], rule["category"], rule["name"],
                                rule["severity"], filepath, i,
                                rule["attack_type"], rule["description"],
                                rule["defense"], line
                            ))

        return findings

    def _scan_c(self, filepath, content, lines) -> List[Vulnerability]:
        """C代码扫描：模式匹配"""
        findings = []

        for rule in C_RULES:
            for i, line in enumerate(lines, 1):
                for pattern in rule["patterns"]:
                    # 多行模式匹配
                    if re.search(pattern, line, re.IGNORECASE):
                        if not any(f.rule_id == rule["id"] and f.line_num == i for f in findings):
                            findings.append(Vulnerability(
                                rule["id"], rule["category"], rule["name"],
                                rule["severity"], filepath, i,
                                rule["attack_type"], rule["description"],
                                rule["defense"], line
                            ))

        return findings

    def _scan_generic(self, filepath, content, lines) -> List[Vulnerability]:
        """通用规则扫描"""
        findings = []

        for rule in GENERIC_RULES:
            # 文件类型过滤
            if "file_patterns" in rule:
                if os.path.basename(filepath) not in rule["file_patterns"]:
                    continue

            for i, line in enumerate(lines, 1):
                for pattern in rule["patterns"]:
                    if re.search(pattern, line, re.IGNORECASE):
                        if not any(f.rule_id == rule["id"] and f.line_num == i for f in findings):
                            findings.append(Vulnerability(
                                rule["id"], rule["category"], rule["name"],
                                rule["severity"], filepath, i,
                                rule["attack_type"], rule["description"],
                                rule["defense"], line
                            ))

        return findings

    def get_stats(self):
        """获取扫描统计"""
        stats = {
            "files_scanned": self.files_scanned,
            "lines_scanned": self.lines_scanned,
            "total_findings": len(self.findings),
            "critical": sum(1 for f in self.findings if f.severity == "CRITICAL"),
            "high": sum(1 for f in self.findings if f.severity == "HIGH"),
            "medium": sum(1 for f in self.findings if f.severity == "MEDIUM"),
            "low": sum(1 for f in self.findings if f.severity == "LOW"),
            "risk_score": sum(SEVERITY_WEIGHT[f.severity] for f in self.findings),
        }
        return stats
