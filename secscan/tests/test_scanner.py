"""SecScan扫描器单元测试

测试覆盖：
1. Python漏洞代码扫描 - 验证检出5+种漏洞
2. 干净代码扫描 - 验证0误报
3. JavaScript漏洞代码扫描 - 验证正则匹配
4. 扫描ID生成和结果存储
5. API端点测试（POST /api/scan, GET /api/report）
6. 各漏洞类型的单独检测验证
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.engine.scanner import Scanner
from app.main import app

# 样本文件目录
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")


@pytest.fixture
def scanner():
    """每个测试使用独立的Scanner实例，避免结果互相干扰"""
    return Scanner()


@pytest.fixture
def client():
    """FastAPI测试客户端"""
    return TestClient(app)


def load_sample(filename):
    """读取样本文件内容"""
    with open(os.path.join(SAMPLES_DIR, filename), "r") as f:
        return f.read()


# ============================================================
# Python代码扫描测试
# ============================================================

class TestPythonScan:
    """Python代码扫描测试"""

    def test_vulnerable_python_detects_5_plus_types(self, scanner):
        """漏洞Python代码应检出5种以上不同类型的漏洞"""
        content = load_sample("vulnerable_python.py")
        result = scanner.scan_code("vulnerable_python.py", content)

        vuln_types = {v.vuln_type for v in result.vulnerabilities}
        assert len(vuln_types) >= 5, f"仅检测到{len(vuln_types)}种漏洞类型: {vuln_types}"

    def test_vulnerable_python_detects_all_10_types(self, scanner):
        """漏洞Python代码应检出全部10种漏洞类型"""
        content = load_sample("vulnerable_python.py")
        result = scanner.scan_code("vulnerable_python.py", content)

        vuln_types = {v.vuln_type for v in result.vulnerabilities}
        expected_types = {
            "SQL注入", "命令注入", "XSS跨站脚本", "硬编码密钥",
            "路径遍历", "不安全的反序列化", "弱加密算法",
            "SSRF服务端请求伪造", "敏感信息泄露", "不安全的随机数",
        }
        missing = expected_types - vuln_types
        assert not missing, f"未检测到的漏洞类型: {missing}"

    def test_clean_code_zero_vulnerabilities(self, scanner):
        """安全代码应检出0个漏洞"""
        content = load_sample("clean_code.py")
        result = scanner.scan_code("clean_code.py", content)

        assert len(result.vulnerabilities) == 0, \
            f"安全代码中检出{len(result.vulnerabilities)}个误报: " \
            f"{[v.vuln_type for v in result.vulnerabilities]}"

    def test_sql_injection_detection(self, scanner):
        """测试SQL注入检测"""
        code = 'query = "SELECT * FROM users WHERE id = " + user_id'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC001" for v in result.vulnerabilities)

    def test_command_injection_detection(self, scanner):
        """测试命令注入检测"""
        code = 'import os\nos.system("ping " + host)'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC002" for v in result.vulnerabilities)

    def test_hardcoded_secret_detection(self, scanner):
        """测试硬编码密钥检测"""
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC004" for v in result.vulnerabilities)

    def test_insecure_deserialization_detection(self, scanner):
        """测试不安全反序列化检测"""
        code = 'import pickle\nresult = pickle.loads(data)'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC006" for v in result.vulnerabilities)

    def test_weak_crypto_detection(self, scanner):
        """测试弱加密检测"""
        code = 'import hashlib\nh = hashlib.md5(data)'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC007" for v in result.vulnerabilities)

    def test_insecure_random_detection(self, scanner):
        """测试不安全随机数检测"""
        code = 'import random\ntoken = random.random()'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC010" for v in result.vulnerabilities)

    def test_path_traversal_detection(self, scanner):
        """测试路径遍历检测"""
        code = 'f = open("/data/" + filename, "r")'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC005" for v in result.vulnerabilities)

    def test_ssrf_detection(self, scanner):
        """测试SSRF检测"""
        code = 'import requests\nr = requests.get(user_url)'
        result = scanner.scan_code("test.py", code)
        assert any(v.rule_id == "SC008" for v in result.vulnerabilities)


# ============================================================
# JavaScript代码扫描测试
# ============================================================

class TestJavaScriptScan:
    """JavaScript代码扫描测试"""

    def test_vulnerable_js_detects_3_plus_types(self, scanner):
        """漏洞JS代码应检出3种以上不同类型的漏洞"""
        content = load_sample("vulnerable_js.js")
        result = scanner.scan_code("vulnerable_js.js", content)

        vuln_types = {v.vuln_type for v in result.vulnerabilities}
        assert len(vuln_types) >= 3, f"仅检测到{len(vuln_types)}种漏洞类型: {vuln_types}"

    def test_js_innerhtml_detection(self, scanner):
        """测试JS XSS(innerHTML)检测"""
        code = "element.innerHTML = userInput;"
        result = scanner.scan_code("test.js", code)
        assert any(v.rule_id == "SC003" for v in result.vulnerabilities)

    def test_js_eval_detection(self, scanner):
        """测试JS eval检测"""
        code = "var result = eval(userInput);"
        result = scanner.scan_code("test.js", code)
        assert any(v.rule_id == "SC006" for v in result.vulnerabilities)

    def test_js_math_random_detection(self, scanner):
        """测试JS Math.random()检测"""
        code = "var token = Math.random();"
        result = scanner.scan_code("test.js", code)
        assert any(v.rule_id == "SC010" for v in result.vulnerabilities)


# ============================================================
# 扫描器功能测试
# ============================================================

class TestScannerFunctionality:
    """扫描器基础功能测试"""

    def test_scan_id_generated(self, scanner):
        """扫描结果应包含有效的scan_id"""
        result = scanner.scan_code("test.py", "x = 1")
        assert result.scan_id is not None
        assert len(result.scan_id) > 0

    def test_scan_id_unique(self, scanner):
        """每次扫描应生成唯一的scan_id"""
        r1 = scanner.scan_code("test.py", "x = 1")
        r2 = scanner.scan_code("test.py", "x = 2")
        assert r1.scan_id != r2.scan_id

    def test_report_retrieval(self, scanner):
        """应能通过scan_id获取扫描结果"""
        result = scanner.scan_code("test.py", "x = 1")
        retrieved = scanner.get_result(result.scan_id)
        assert retrieved is not None
        assert retrieved.scan_id == result.scan_id

    def test_report_not_found(self, scanner):
        """不存在的scan_id应返回None"""
        assert scanner.get_result("nonexistent-id") is None

    def test_summary_counts_correct(self, scanner):
        """统计摘要中的漏洞计数应正确"""
        content = load_sample("vulnerable_python.py")
        result = scanner.scan_code("vulnerable_python.py", content)

        total = result.summary.total
        by_severity = (
            result.summary.critical
            + result.summary.high
            + result.summary.medium
            + result.summary.low
            + result.summary.info
        )
        assert total == len(result.vulnerabilities)
        assert by_severity == total

    def test_unknown_language(self, scanner):
        """未知语言文件应返回空漏洞列表"""
        result = scanner.scan_code("test.txt", "some content")
        assert result.language == "Unknown"
        assert len(result.vulnerabilities) == 0

    def test_filename_preserved(self, scanner):
        """扫描结果应保留原始文件名"""
        result = scanner.scan_code("my_app.py", "x = 1")
        assert result.filename == "my_app.py"

    def test_vulnerability_has_code_snippet(self, scanner):
        """漏洞结果应包含代码片段"""
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test.py", code)
        assert len(result.vulnerabilities) > 0
        assert result.vulnerabilities[0].code_snippet != ""

    def test_vulnerability_has_fix_suggestion(self, scanner):
        """漏洞结果应包含修复建议"""
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test.py", code)
        assert len(result.vulnerabilities) > 0
        assert result.vulnerabilities[0].fix_suggestion != ""


# ============================================================
# API端点测试
# ============================================================

class TestAPI:
    """FastAPI接口测试"""

    def test_scan_endpoint_python(self, client):
        """POST /api/scan 应能扫描Python文件"""
        content = load_sample("vulnerable_python.py")
        response = client.post(
            "/api/scan",
            files={"file": ("vulnerable_python.py", content, "text/x-python")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "vulnerable_python.py"
        assert data["language"] == "Python"
        assert len(data["vulnerabilities"]) >= 5
        assert data["summary"]["total"] == len(data["vulnerabilities"])

    def test_scan_endpoint_clean_code(self, client):
        """POST /api/scan 扫描安全代码应返回0漏洞"""
        content = load_sample("clean_code.py")
        response = client.post(
            "/api/scan",
            files={"file": ("clean_code.py", content, "text/x-python")},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["vulnerabilities"]) == 0
        assert data["summary"]["total"] == 0

    def test_scan_endpoint_javascript(self, client):
        """POST /api/scan 应能扫描JavaScript文件"""
        content = load_sample("vulnerable_js.js")
        response = client.post(
            "/api/scan",
            files={"file": ("vulnerable_js.js", content, "text/javascript")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "JavaScript"
        assert len(data["vulnerabilities"]) >= 3

    def test_report_endpoint(self, client):
        """GET /api/report/{scan_id} 应能获取扫描报告"""
        # 先扫描获取scan_id
        content = load_sample("vulnerable_python.py")
        scan_response = client.post(
            "/api/scan",
            files={"file": ("vulnerable_python.py", content, "text/x-python")},
        )
        scan_id = scan_response.json()["scan_id"]

        # 再通过scan_id获取报告
        report_response = client.get(f"/api/report/{scan_id}")
        assert report_response.status_code == 200
        report_data = report_response.json()
        assert report_data["scan_id"] == scan_id
        assert len(report_data["vulnerabilities"]) >= 5

    def test_report_not_found(self, client):
        """GET /api/report/{不存在的ID} 应返回404"""
        response = client.get("/api/report/nonexistent-id-12345")
        assert response.status_code == 404

    def test_scan_unsupported_file_type(self, client):
        """POST /api/scan 上传不支持的文件类型应返回400"""
        response = client.post(
            "/api/scan",
            files={"file": ("test.txt", "some content", "text/plain")},
        )
        assert response.status_code == 400

    def test_root_endpoint(self, client):
        """GET / 应返回API信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "SecScan"

    def test_response_structure_complete(self, client):
        """扫描响应应包含所有必需字段"""
        content = 'API_KEY = "sk-test1234567890"'
        response = client.post(
            "/api/scan",
            files={"file": ("test.py", content, "text/x-python")},
        )
        data = response.json()

        # 顶层字段
        assert "scan_id" in data
        assert "filename" in data
        assert "language" in data
        assert "scan_time" in data
        assert "vulnerabilities" in data
        assert "summary" in data

        # 漏洞字段
        if data["vulnerabilities"]:
            vuln = data["vulnerabilities"][0]
            assert "rule_id" in vuln
            assert "vuln_type" in vuln
            assert "cwe_id" in vuln
            assert "severity" in vuln
            assert "description" in vuln
            assert "line" in vuln
            assert "code_snippet" in vuln
            assert "fix_suggestion" in vuln

        # 摘要字段
        summary = data["summary"]
        assert "total" in summary
        assert "critical" in summary
        assert "high" in summary
        assert "medium" in summary
        assert "low" in summary
        assert "info" in summary
