"""数据库持久化模块测试

测试覆盖：
1. 扫描结果存入数据库并正确读取
2. 不存在的扫描ID返回None
3. 漏洞详情正确持久化（字段完整性）
4. 统计摘要正确存储
5. 扫描历史列表分页查询
6. 按文件名筛选
7. 按语言筛选
8. 删除扫描记录
9. 删除不存在的记录
10. 级联删除漏洞记录
11. 数据持久化（新会话查询）
12. API端点：GET /api/history
13. API端点：DELETE /api/report/{scan_id}
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.engine.scanner import Scanner
from app.db.database import get_session, init_db
from app.db import crud
from app.models.scan_result import ScanResult, ScanSummary, Vulnerability
from app.main import app


# ============================================================
# 测试夹具
# ============================================================

@pytest.fixture
def scanner():
    """每个测试使用独立的Scanner实例"""
    return Scanner()


@pytest.fixture
def client():
    """FastAPI测试客户端"""
    return TestClient(app)


def _make_scan_result(scan_id=None, filename="test.py", language="Python"):
    """构造一个测试用的 ScanResult 对象

    Args:
        scan_id: 扫描ID，未指定时自动生成唯一UUID
        filename: 文件名
        language: 语言
    """
    if scan_id is None:
        scan_id = str(uuid.uuid4())
    vuln = Vulnerability(
        rule_id="SC001",
        vuln_type="SQL注入",
        cwe_id="CWE-89",
        severity="Critical",
        description="检测到SQL注入漏洞",
        line=10,
        code_snippet='query = "SELECT * FROM users WHERE id = " + user_id',
        fix_suggestion="使用参数化查询",
    )
    summary = ScanSummary(total=1, critical=1, high=0, medium=0, low=0, info=0)
    return ScanResult(
        scan_id=scan_id,
        filename=filename,
        language=language,
        scan_time="2024-01-01T00:00:00",
        vulnerabilities=[vuln],
        summary=summary,
    )


# ============================================================
# CRUD 基础测试
# ============================================================

class TestCRUDBasic:
    """CRUD 基础操作测试"""

    def test_create_and_retrieve(self):
        """创建扫描结果后应能从数据库读取"""
        result = _make_scan_result()
        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()

            retrieved = crud.get_scan_result(db, result.scan_id)
            assert retrieved is not None
            assert retrieved.scan_id == result.scan_id
            assert retrieved.filename == result.filename
            assert retrieved.language == result.language
        finally:
            db.close()

    def test_get_nonexistent_returns_none(self):
        """查询不存在的扫描ID应返回None"""
        db = get_session()
        try:
            result = crud.get_scan_result(db, "nonexistent-id-99999")
            assert result is None
        finally:
            db.close()

    def test_vulnerability_fields_persisted(self):
        """漏洞详情应完整持久化"""
        result = _make_scan_result()
        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()

            retrieved = crud.get_scan_result(db, result.scan_id)
            assert retrieved is not None
            assert len(retrieved.vulnerabilities) == 1

            vuln = retrieved.vulnerabilities[0]
            original = result.vulnerabilities[0]
            assert vuln.rule_id == original.rule_id
            assert vuln.vuln_type == original.vuln_type
            assert vuln.cwe_id == original.cwe_id
            assert vuln.severity == original.severity
            assert vuln.description == original.description
            assert vuln.line == original.line
            assert vuln.code_snippet == original.code_snippet
            assert vuln.fix_suggestion == original.fix_suggestion
        finally:
            db.close()

    def test_summary_persisted(self):
        """统计摘要应正确存储"""
        result = _make_scan_result()
        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()

            retrieved = crud.get_scan_result(db, result.scan_id)
            assert retrieved is not None
            assert retrieved.summary.total == 1
            assert retrieved.summary.critical == 1
            assert retrieved.summary.high == 0
            assert retrieved.summary.medium == 0
            assert retrieved.summary.low == 0
            assert retrieved.summary.info == 0
        finally:
            db.close()

    def test_multiple_vulnerabilities_persisted(self):
        """多个漏洞应全部持久化"""
        vulns = [
            Vulnerability(
                rule_id="SC001", vuln_type="SQL注入", cwe_id="CWE-89",
                severity="Critical", description="SQL注入", line=1,
                code_snippet="code1", fix_suggestion="fix1",
            ),
            Vulnerability(
                rule_id="SC004", vuln_type="硬编码密钥", cwe_id="CWE-798",
                severity="High", description="硬编码密钥", line=2,
                code_snippet="code2", fix_suggestion="fix2",
            ),
            Vulnerability(
                rule_id="SC010", vuln_type="不安全的随机数", cwe_id="CWE-330",
                severity="Medium", description="不安全随机数", line=3,
                code_snippet="code3", fix_suggestion="fix3",
            ),
        ]
        summary = ScanSummary(total=3, critical=1, high=1, medium=1, low=0, info=0)
        result = ScanResult(
            scan_id=str(uuid.uuid4()), filename="app.py", language="Python",
            scan_time="2024-01-01T00:00:00", vulnerabilities=vulns, summary=summary,
        )

        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()

            retrieved = crud.get_scan_result(db, result.scan_id)
            assert retrieved is not None
            assert len(retrieved.vulnerabilities) == 3
            assert retrieved.summary.total == 3
            assert retrieved.summary.critical == 1
            assert retrieved.summary.high == 1
            assert retrieved.summary.medium == 1
        finally:
            db.close()


# ============================================================
# 历史查询测试
# ============================================================

class TestScanHistory:
    """扫描历史列表查询测试"""

    def test_history_returns_list(self):
        """历史查询应返回列表格式"""
        db = get_session()
        try:
            history = crud.get_scan_history(db, skip=0, limit=10)
            assert "items" in history
            assert "total" in history
            assert "skip" in history
            assert "limit" in history
            assert isinstance(history["items"], list)
            assert history["skip"] == 0
            assert history["limit"] == 10
        finally:
            db.close()

    def test_history_pagination(self):
        """分页查询应正确返回指定范围的记录"""
        db = get_session()
        try:
            # 插入5条记录
            for i in range(5):
                result = _make_scan_result(filename=f"file_{i}.py")
                crud.create_scan_result(db, result)
            db.commit()

            # 第一页（2条）
            page1 = crud.get_scan_history(db, skip=0, limit=2)
            assert page1["total"] >= 5
            assert len(page1["items"]) == 2

            # 第二页（2条）
            page2 = crud.get_scan_history(db, skip=2, limit=2)
            assert len(page2["items"]) == 2

            # 两页的记录不应重复
            ids_page1 = {item["scan_id"] for item in page1["items"]}
            ids_page2 = {item["scan_id"] for item in page2["items"]}
            assert ids_page1.isdisjoint(ids_page2)
        finally:
            db.close()

    def test_history_filter_by_filename(self):
        """按文件名筛选应只返回匹配的记录"""
        db = get_session()
        try:
            result = _make_scan_result(filename="unique_name.py")
            crud.create_scan_result(db, result)
            db.commit()

            history = crud.get_scan_history(db, filename="unique_name")
            assert history["total"] >= 1
            assert all("unique_name" in item["filename"] for item in history["items"])
        finally:
            db.close()

    def test_history_filter_by_language(self):
        """按语言筛选应只返回匹配的记录"""
        db = get_session()
        try:
            result = _make_scan_result(filename="app.js", language="JavaScript")
            crud.create_scan_result(db, result)
            db.commit()

            history = crud.get_scan_history(db, language="JavaScript")
            assert history["total"] >= 1
            assert all(item["language"] == "JavaScript" for item in history["items"])
        finally:
            db.close()

    def test_history_items_have_summary(self):
        """历史记录项应包含统计摘要"""
        db = get_session()
        try:
            result = _make_scan_result()
            crud.create_scan_result(db, result)
            db.commit()

            history = crud.get_scan_history(db, skip=0, limit=100)
            item = next(
                (i for i in history["items"] if i["scan_id"] == result.scan_id),
                None,
            )
            assert item is not None
            assert "summary" in item
            assert item["summary"]["total"] == 1
            assert item["summary"]["critical"] == 1
        finally:
            db.close()


# ============================================================
# 删除操作测试
# ============================================================

class TestDeleteScan:
    """删除扫描记录测试"""

    def test_delete_existing_record(self):
        """删除已存在的记录应返回True"""
        result = _make_scan_result()
        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()

            deleted = crud.delete_scan_result(db, result.scan_id)
            db.commit()
            assert deleted is True

            # 验证已删除
            retrieved = crud.get_scan_result(db, result.scan_id)
            assert retrieved is None
        finally:
            db.close()

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的记录应返回False"""
        db = get_session()
        try:
            deleted = crud.delete_scan_result(db, "nonexistent-delete-id-99999")
            assert deleted is False
        finally:
            db.close()

    def test_cascade_delete_vulnerabilities(self):
        """删除扫描记录时应级联删除关联的漏洞记录"""
        from app.db.models import VulnerabilityRecord, ScanRecord

        result = _make_scan_result()
        db = get_session()
        try:
            crud.create_scan_result(db, result)
            db.commit()

            # 获取扫描记录ID
            scan = db.query(ScanRecord).filter(ScanRecord.scan_id == result.scan_id).first()
            assert scan is not None

            # 验证漏洞记录存在
            vuln_count = db.query(VulnerabilityRecord).filter(
                VulnerabilityRecord.scan_record_id == scan.id
            ).count()
            assert vuln_count == 1

            # 删除扫描记录
            crud.delete_scan_result(db, result.scan_id)
            db.commit()

            # 验证扫描记录已删除
            scan_after = db.query(ScanRecord).filter(ScanRecord.scan_id == result.scan_id).first()
            assert scan_after is None

            # 验证关联的漏洞记录也被级联删除
            vuln_after = db.query(VulnerabilityRecord).filter(
                VulnerabilityRecord.scan_record_id == scan.id
            ).count()
            assert vuln_after == 0
        finally:
            db.close()


# ============================================================
# 数据持久化测试
# ============================================================

class TestPersistence:
    """数据持久化测试"""

    def test_data_survives_new_session(self):
        """数据应在新的数据库会话中仍然可查"""
        result = _make_scan_result()
        db1 = get_session()
        try:
            crud.create_scan_result(db1, result)
            db1.commit()
        finally:
            db1.close()

        # 使用全新的会话查询
        db2 = get_session()
        try:
            retrieved = crud.get_scan_result(db2, result.scan_id)
            assert retrieved is not None
            assert retrieved.scan_id == result.scan_id
            assert retrieved.filename == "test.py"
        finally:
            db2.close()


# ============================================================
# Scanner 集成测试
# ============================================================

class TestScannerWithDB:
    """Scanner 与数据库集成测试"""

    def test_scan_persists_to_db(self, scanner):
        """扫描结果应自动持久化到数据库"""
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test_persist.py", code)

        # 通过新的数据库会话查询验证持久化
        db = get_session()
        try:
            retrieved = crud.get_scan_result(db, result.scan_id)
            assert retrieved is not None
            assert retrieved.filename == "test_persist.py"
            assert retrieved.language == "Python"
            assert len(retrieved.vulnerabilities) >= 1
        finally:
            db.close()

    def test_get_result_reads_from_db(self, scanner):
        """get_result 应从数据库读取"""
        code = 'API_KEY = "sk-1234567890abcdef"'
        result = scanner.scan_code("test_read.py", code)

        # 通过 scanner.get_result 读取（内部使用数据库）
        retrieved = scanner.get_result(result.scan_id)
        assert retrieved is not None
        assert retrieved.scan_id == result.scan_id


# ============================================================
# API 端点测试
# ============================================================

class TestHistoryAPI:
    """GET /api/history 端点测试"""

    def test_history_endpoint_returns_200(self, client):
        """GET /api/history 应返回200"""
        response = client.get("/api/history")
        assert response.status_code == 200

    def test_history_endpoint_structure(self, client):
        """历史响应应包含必需字段"""
        response = client.get("/api/history")
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

    def test_history_after_scan(self, client):
        """扫描后历史列表应包含该记录"""
        # 先执行扫描
        content = 'API_KEY = "sk-test1234567890"'
        scan_response = client.post(
            "/api/scan",
            files={"file": ("history_test.py", content, "text/x-python")},
        )
        scan_id = scan_response.json()["scan_id"]

        # 查询历史
        response = client.get("/api/history")
        data = response.json()
        assert data["total"] >= 1

        # 验证刚扫描的记录在列表中
        scan_ids = [item["scan_id"] for item in data["items"]]
        assert scan_id in scan_ids

    def test_history_with_pagination(self, client):
        """历史列表应支持分页参数"""
        response = client.get("/api/history", params={"skip": 0, "limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 5
        assert len(data["items"]) <= 5

    def test_history_filter_by_filename(self, client):
        """历史列表应支持按文件名筛选"""
        # 扫描一个特殊文件名
        content = 'x = 1'
        client.post(
            "/api/scan",
            files={"file": ("special_filter_file.py", content, "text/x-python")},
        )

        response = client.get("/api/history", params={"filename": "special_filter_file"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all("special_filter_file" in item["filename"] for item in data["items"])

    def test_history_filter_by_language(self, client):
        """历史列表应支持按语言筛选"""
        content = 'var x = Math.random();'
        client.post(
            "/api/scan",
            files={"file": ("lang_test.js", content, "text/javascript")},
        )

        response = client.get("/api/history", params={"language": "JavaScript"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all(item["language"] == "JavaScript" for item in data["items"])


class TestDeleteAPI:
    """DELETE /api/report/{scan_id} 端点测试"""

    def test_delete_existing(self, client):
        """删除已存在的扫描记录应返回200"""
        # 先扫描
        content = 'API_KEY = "sk-test1234567890"'
        scan_response = client.post(
            "/api/scan",
            files={"file": ("delete_test.py", content, "text/x-python")},
        )
        scan_id = scan_response.json()["scan_id"]

        # 删除
        delete_response = client.delete(f"/api/report/{scan_id}")
        assert delete_response.status_code == 200

        # 验证已删除
        report_response = client.get(f"/api/report/{scan_id}")
        assert report_response.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        """删除不存在的记录应返回404"""
        response = client.delete("/api/report/nonexistent-id-99999")
        assert response.status_code == 404

    def test_delete_removes_from_history(self, client):
        """删除后历史列表中不应再包含该记录"""
        content = 'x = 1'
        scan_response = client.post(
            "/api/scan",
            files={"file": ("remove_from_history.py", content, "text/x-python")},
        )
        scan_id = scan_response.json()["scan_id"]

        # 删除
        client.delete(f"/api/report/{scan_id}")

        # 检查历史列表
        response = client.get("/api/history", params={"filename": "remove_from_history"})
        data = response.json()
        scan_ids = [item["scan_id"] for item in data["items"]]
        assert scan_id not in scan_ids
