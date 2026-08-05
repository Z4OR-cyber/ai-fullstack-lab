"""AST分析器模块

使用Python标准库ast模块解析Python代码的抽象语法树，
通过遍历AST节点检测各类安全漏洞。

AST分析相比正则匹配具有更高的准确性，能够理解代码结构，
减少误报。但对于动态生成的代码（如字符串拼接后eval）无法检测。
"""

import ast
from typing import List, Dict, Any

from app.engine.rules import RULES


class PythonASTAnalyzer(ast.NodeVisitor):
    """Python AST分析器

    继承ast.NodeVisitor，通过访问各类AST节点检测安全漏洞。
    支持检测10种漏洞类型：SQL注入、命令注入、XSS、硬编码密钥、
    路径遍历、不安全反序列化、弱加密、SSRF、信息泄露、不安全随机数。

    用法:
        analyzer = PythonASTAnalyzer(source_code)
        findings = analyzer.analyze()
    """

    # SQL关键字列表，用于识别SQL语句
    SQL_KEYWORDS = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION', 'WHERE')

    # 敏感变量名关键字
    SECRET_PATTERNS = (
        'api_key', 'apikey', 'api_secret', 'password', 'passwd',
        'secret', 'token', 'private_key', 'access_key',
    )

    # 敏感信息关键字（用于信息泄露检测）
    SENSITIVE_LOG_PATTERNS = (
        'password', 'secret', 'token', 'api_key', 'apikey',
        'credential', 'private_key',
    )

    # 危险函数调用集合
    DANGEROUS_COMMAND_CALLS = {
        'os.system', 'os.popen',
        'subprocess.call', 'subprocess.run', 'subprocess.Popen',
        'subprocess.check_output', 'subprocess.check_call',
    }
    DANGEROUS_DESERIALIZE_CALLS = {
        'pickle.loads', 'pickle.load', 'cPickle.loads', 'cPickle.load',
        'eval', 'exec', 'yaml.load', 'marshal.loads', 'marshal.load',
    }
    WEAK_CRYPTO_CALLS = {'hashlib.md5', 'hashlib.sha1'}
    SSRF_CALLS = {
        'requests.get', 'requests.post', 'requests.put', 'requests.delete',
        'requests.head', 'requests.patch', 'requests.request',
        'urllib.request.urlopen', 'httpx.get', 'httpx.post',
    }
    INSECURE_RANDOM_CALLS = {
        'random.random', 'random.randint', 'random.choice',
        'random.randrange', 'random.uniform', 'random.sample',
    }
    XSS_CALLS = {'render_template_string', 'mark_safe'}

    def __init__(self, source: str):
        """初始化分析器

        Args:
            source: Python源代码字符串
        """
        self.source = source
        self.source_lines = source.splitlines()
        self.findings: List[Dict[str, Any]] = []

    def analyze(self) -> List[Dict[str, Any]]:
        """执行AST分析，返回检测结果列表

        Returns:
            检测结果字典列表，每个字典包含rule_id、vuln_type、cwe_id、
            severity、description、line、code_snippet、fix_suggestion
        """
        try:
            tree = ast.parse(self.source)
        except SyntaxError as e:
            self._add_finding("SC000", e.lineno or 1)
            return self.findings

        self.visit(tree)
        return self.findings

    # ============================================================
    # AST节点访问方法
    # ============================================================

    def visit_Call(self, node: ast.Call):
        """访问函数调用节点，检测各类基于函数调用的漏洞"""
        self._check_sql_injection_call(node)
        self._check_command_injection(node)
        self._check_xss(node)
        self._check_path_traversal(node)
        self._check_deserialization(node)
        self._check_weak_crypto(node)
        self._check_ssrf(node)
        self._check_info_leakage(node)
        self._check_insecure_random(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        """访问赋值节点，检测硬编码密钥和SQL语句拼接"""
        self._check_hardcoded_secrets(node)
        self._check_sql_injection_assign(node)
        self.generic_visit(node)

    # ============================================================
    # 漏洞检测方法
    # ============================================================

    def _check_sql_injection_call(self, node: ast.Call):
        """SQL注入检测：execute/executemany调用中使用字符串拼接或f-string"""
        call_name = self._get_full_name(node.func)
        if call_name.endswith('execute') or call_name.endswith('executemany'):
            if node.args and isinstance(node.args[0], (ast.BinOp, ast.JoinedStr)):
                self._add_finding("SC001", node.lineno)

    def _check_sql_injection_assign(self, node: ast.Assign):
        """SQL注入检测：变量赋值为包含SQL关键字的拼接字符串"""
        if isinstance(node.value, (ast.BinOp, ast.JoinedStr)):
            if self._contains_sql_keyword(node.value):
                self._add_finding("SC001", node.lineno)

    def _check_command_injection(self, node: ast.Call):
        """命令注入检测：os.system/subprocess调用使用非常量参数

        subprocess.run(["cmd", "arg"]) 列表形式是安全的，不会触发shell注入。
        仅当参数为字符串拼接(BinOp/JoinedStr)或变量引用(Name)时才报告。
        """
        call_name = self._get_full_name(node.func)
        if call_name in self.DANGEROUS_COMMAND_CALLS:
            if node.args and not isinstance(node.args[0], (ast.Constant, ast.List)):
                self._add_finding("SC002", node.lineno)

    def _check_xss(self, node: ast.Call):
        """XSS检测：render_template_string/mark_safe使用非常量参数"""
        call_name = self._get_full_name(node.func)
        if call_name in self.XSS_CALLS:
            if node.args and not isinstance(node.args[0], ast.Constant):
                self._add_finding("SC003", node.lineno)

    def _check_hardcoded_secrets(self, node: ast.Assign):
        """硬编码密钥检测：敏感变量名赋值为字符串常量"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                if any(p in name_lower for p in self.SECRET_PATTERNS):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        if len(node.value.value) > 3:
                            self._add_finding("SC004", node.lineno)

    def _check_path_traversal(self, node: ast.Call):
        """路径遍历检测：open()使用字符串拼接或f-string作为路径"""
        call_name = self._get_full_name(node.func)
        if call_name == 'open':
            if node.args and isinstance(node.args[0], (ast.BinOp, ast.JoinedStr)):
                self._add_finding("SC005", node.lineno)

    def _check_deserialization(self, node: ast.Call):
        """不安全反序列化检测：pickle.loads/eval/exec/yaml.load等"""
        call_name = self._get_full_name(node.func)
        if call_name in self.DANGEROUS_DESERIALIZE_CALLS:
            self._add_finding("SC006", node.lineno)

    def _check_weak_crypto(self, node: ast.Call):
        """弱加密检测：使用MD5或SHA1哈希算法"""
        call_name = self._get_full_name(node.func)
        if call_name in self.WEAK_CRYPTO_CALLS:
            self._add_finding("SC007", node.lineno)

    def _check_ssrf(self, node: ast.Call):
        """SSRF检测：requests/httpx使用变量/拼接URL发起请求"""
        call_name = self._get_full_name(node.func)
        if call_name in self.SSRF_CALLS:
            if node.args and isinstance(node.args[0], (ast.Name, ast.BinOp, ast.JoinedStr)):
                self._add_finding("SC008", node.lineno)

    def _check_info_leakage(self, node: ast.Call):
        """信息泄露检测：print/logging输出包含敏感变量"""
        call_name = self._get_full_name(node.func)
        is_log_call = (
            call_name == 'print'
            or call_name.endswith('.debug')
            or call_name.endswith('.info')
            or call_name.endswith('.warning')
            or call_name.endswith('.error')
        )
        if is_log_call:
            for arg in node.args:
                if self._arg_contains_sensitive(arg):
                    self._add_finding("SC009", node.lineno)
                    break

    def _check_insecure_random(self, node: ast.Call):
        """不安全随机数检测：random模块用于安全场景"""
        call_name = self._get_full_name(node.func)
        if call_name in self.INSECURE_RANDOM_CALLS:
            self._add_finding("SC010", node.lineno)

    # ============================================================
    # 辅助方法
    # ============================================================

    def _add_finding(self, rule_id: str, line: int):
        """添加一条检测结果"""
        rule = RULES[rule_id]
        snippet = ""
        if 0 < line <= len(self.source_lines):
            snippet = self.source_lines[line - 1].strip()
        self.findings.append({
            "rule_id": rule_id,
            "vuln_type": rule.vuln_type,
            "cwe_id": rule.cwe_id,
            "severity": rule.severity.value,
            "description": rule.description,
            "line": line,
            "code_snippet": snippet,
            "fix_suggestion": rule.fix_suggestion,
        })

    @staticmethod
    def _get_full_name(node) -> str:
        """获取AST节点的完整函数调用名

        示例:
            os.system      -> "os.system"
            hashlib.md5    -> "hashlib.md5"
            eval           -> "eval"
            cursor.execute -> "cursor.execute"

        Args:
            node: ast.Call.func 节点

        Returns:
            完整函数名字符串
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parent = PythonASTAnalyzer._get_full_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return ""

    @classmethod
    def _contains_sql_keyword(cls, node) -> bool:
        """递归检查AST节点是否包含SQL关键字"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return any(kw in node.value.upper() for kw in cls.SQL_KEYWORDS)
        elif isinstance(node, ast.JoinedStr):
            for val in node.values:
                if isinstance(val, ast.Constant) and isinstance(val.value, str):
                    if any(kw in val.value.upper() for kw in cls.SQL_KEYWORDS):
                        return True
        elif isinstance(node, ast.BinOp):
            return (cls._contains_sql_keyword(node.left)
                    or cls._contains_sql_keyword(node.right))
        return False

    @classmethod
    def _arg_contains_sensitive(cls, arg) -> bool:
        """递归检查参数是否引用了敏感变量名"""
        if isinstance(arg, ast.Name):
            name_lower = arg.id.lower()
            return any(p in name_lower for p in cls.SENSITIVE_LOG_PATTERNS)
        elif isinstance(arg, ast.JoinedStr):
            for val in arg.values:
                if isinstance(val, ast.FormattedValue):
                    if cls._arg_contains_sensitive(val.value):
                        return True
        elif isinstance(arg, ast.BinOp):
            return (cls._arg_contains_sensitive(arg.left)
                    or cls._arg_contains_sensitive(arg.right))
        return False
