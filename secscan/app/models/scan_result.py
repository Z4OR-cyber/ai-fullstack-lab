"""Pydantic数据模型

定义API请求和响应的数据结构，确保类型安全和自动文档生成。
"""

from typing import List
from pydantic import BaseModel, Field

from app.engine.severity import Severity


class Vulnerability(BaseModel):
    """单个漏洞检测结果"""
    rule_id: str = Field(..., description="规则ID，如 SC001")
    vuln_type: str = Field(..., description="漏洞类型，如 SQL注入")
    cwe_id: str = Field(..., description="CWE编号，如 CWE-89")
    severity: Severity = Field(..., description="严重程度")
    description: str = Field(..., description="漏洞描述")
    line: int = Field(..., ge=1, description="漏洞所在行号")
    code_snippet: str = Field(..., description="漏洞代码片段")
    fix_suggestion: str = Field(..., description="修复建议")


class ScanSummary(BaseModel):
    """扫描结果统计摘要"""
    total: int = Field(0, ge=0, description="漏洞总数")
    critical: int = Field(0, ge=0, description="严重漏洞数")
    high: int = Field(0, ge=0, description="高危漏洞数")
    medium: int = Field(0, ge=0, description="中危漏洞数")
    low: int = Field(0, ge=0, description="低危漏洞数")
    info: int = Field(0, ge=0, description="信息级漏洞数")


class ScanResult(BaseModel):
    """完整扫描结果"""
    scan_id: str = Field(..., description="扫描任务唯一ID")
    filename: str = Field(..., description="扫描的文件名")
    language: str = Field(..., description="代码语言")
    scan_time: str = Field(..., description="扫描时间(ISO格式)")
    vulnerabilities: List[Vulnerability] = Field(
        default_factory=list, description="检测到的漏洞列表"
    )
    summary: ScanSummary = Field(..., description="统计摘要")


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
