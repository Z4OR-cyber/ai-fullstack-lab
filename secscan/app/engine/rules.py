"""漏洞规则定义模块

定义 SecScan 支持的所有安全漏洞检测规则。
每条规则包含：规则ID、漏洞类型、CWE编号、严重程度、描述和修复建议。

CWE (Common Weakness Enumeration) 是MITRE维护的通用弱点枚举标准，
每个CWE编号对应一种公认的安全弱点类型。
"""

from dataclasses import dataclass
from typing import Dict

from app.engine.severity import Severity


@dataclass(frozen=True)
class Rule:
    """漏洞检测规则

    Attributes:
        rule_id: 规则唯一标识符，格式 SCxxx
        vuln_type: 漏洞类型中文名称
        cwe_id: CWE编号，如 CWE-89
        severity: 严重程度
        description: 漏洞描述
        fix_suggestion: 修复建议
    """
    rule_id: str
    vuln_type: str
    cwe_id: str
    severity: Severity
    description: str
    fix_suggestion: str


# ============================================================
# 规则注册表 - 所有漏洞检测规则统一定义在此
# ============================================================
RULES: Dict[str, Rule] = {

    "SC000": Rule(
        rule_id="SC000",
        vuln_type="语法错误",
        cwe_id="N/A",
        severity=Severity.INFO,
        description="代码存在语法错误，无法完成完整的安全扫描",
        fix_suggestion="请修复语法错误后重新进行安全扫描",
    ),

    "SC001": Rule(
        rule_id="SC001",
        vuln_type="SQL注入",
        cwe_id="CWE-89",
        severity=Severity.CRITICAL,
        description="检测到通过字符串拼接构造SQL语句，攻击者可注入恶意SQL代码，"
                    "导致数据泄露、数据篡改或数据库被接管",
        fix_suggestion="使用参数化查询代替字符串拼接。例如：\n"
                       "  cursor.execute('SELECT * FROM users WHERE name = ?', (username,))\n"
                       "或使用ORM框架的查询构建器",
    ),

    "SC002": Rule(
        rule_id="SC002",
        vuln_type="命令注入",
        cwe_id="CWE-78",
        severity=Severity.CRITICAL,
        description="检测到使用os.system/subprocess执行包含用户输入的命令，"
                    "攻击者可注入任意系统命令，导致远程代码执行(RCE)",
        fix_suggestion="使用subprocess.run()并传入参数列表(非字符串拼接)，避免使用shell=True。\n"
                       "例如：subprocess.run(['ping', '-c', '3', host], shell=False)\n"
                       "或使用shlex.quote()对输入进行转义",
    ),

    "SC003": Rule(
        rule_id="SC003",
        vuln_type="XSS跨站脚本",
        cwe_id="CWE-79",
        severity=Severity.HIGH,
        description="检测到将用户输入直接渲染到HTML页面中(render_template_string/mark_safe/"
                    "innerHTML/document.write)，攻击者可注入恶意JavaScript脚本",
        fix_suggestion="对用户输入进行HTML转义后再输出。Flask默认开启自动转义；"
                       "避免使用render_template_string拼接用户输入；"
                       "JavaScript中使用textContent代替innerHTML",
    ),

    "SC004": Rule(
        rule_id="SC004",
        vuln_type="硬编码密钥",
        cwe_id="CWE-798",
        severity=Severity.HIGH,
        description="检测到代码中硬编码了API密钥、密码或令牌等敏感凭证，"
                    "一旦代码泄露将直接暴露系统凭据",
        fix_suggestion="将敏感凭证移至环境变量或配置文件中，通过os.environ或配置管理工具读取。\n"
                       "例如：api_key = os.environ.get('API_KEY')\n"
                       "并确保配置文件不被纳入版本控制(.gitignore)",
    ),

    "SC005": Rule(
        rule_id="SC005",
        vuln_type="路径遍历",
        cwe_id="CWE-22",
        severity=Severity.HIGH,
        description="检测到使用用户输入拼接文件路径，攻击者可通过../等特殊字符"
                    "访问任意文件，导致敏感文件泄露",
        fix_suggestion="使用os.path.basename()提取文件名，或使用os.path.realpath()配合"
                       "白名单目录检查。例如：\n"
                       "  safe_path = os.path.join(BASE_DIR, os.path.basename(filename))\n"
                       "  if not safe_path.startswith(BASE_DIR):\n"
                       "      raise ValueError('非法路径')",
    ),

    "SC006": Rule(
        rule_id="SC006",
        vuln_type="不安全的反序列化",
        cwe_id="CWE-502",
        severity=Severity.CRITICAL,
        description="检测到使用pickle.loads/eval/exec等不安全的反序列化操作，"
                    "攻击者可构造恶意序列化数据实现远程代码执行",
        fix_suggestion="避免使用pickle/eval处理不可信数据。改用JSON等安全格式进行序列化。\n"
                       "如必须使用pickle，通过HMAC签名验证数据完整性。\n"
                       "禁止在生产代码中使用eval()和exec()",
    ),

    "SC007": Rule(
        rule_id="SC007",
        vuln_type="弱加密算法",
        cwe_id="CWE-327",
        severity=Severity.HIGH,
        description="检测到使用MD5或SHA1等已被攻破的弱哈希算法，"
                    "这些算法存在已知碰撞攻击，不适用于密码存储或完整性校验",
        fix_suggestion="密码存储使用bcrypt/scrypt/argon2等专用算法。\n"
                       "数据完整性校验使用SHA-256或更高版本。\n"
                       "例如：hashlib.sha256(data.encode()).hexdigest()",
    ),

    "SC008": Rule(
        rule_id="SC008",
        vuln_type="SSRF服务端请求伪造",
        cwe_id="CWE-918",
        severity=Severity.HIGH,
        description="检测到使用用户可控的URL发起HTTP请求，攻击者可利用此漏洞"
                    "访问内网服务、云元数据接口或执行端口扫描",
        fix_suggestion="对用户提供的URL进行严格校验：\n"
                       "1. 使用白名单限制允许访问的域名\n"
                       "2. 禁止访问内网IP地址(10.x, 172.16-31.x, 192.168.x, 127.x)\n"
                       "3. 禁止使用file://、gopher://等非HTTP协议",
    ),

    "SC009": Rule(
        rule_id="SC009",
        vuln_type="敏感信息泄露",
        cwe_id="CWE-532",
        severity=Severity.MEDIUM,
        description="检测到通过print或日志输出敏感信息(密码、令牌、密钥等)，"
                    "这些信息可能被记录到日志文件中导致泄露",
        fix_suggestion="移除调试用的print语句，或确保日志中不输出敏感字段。\n"
                       "在日志框架中配置敏感字段过滤/脱敏规则。\n"
                       "生产环境关闭DEBUG级别日志",
    ),

    "SC010": Rule(
        rule_id="SC010",
        vuln_type="不安全的随机数",
        cwe_id="CWE-330",
        severity=Severity.MEDIUM,
        description="检测到使用random模块生成安全相关的随机数，"
                    "random模块使用伪随机数生成器(PRNG)，不具备密码学安全性，"
                    "生成的值可被预测",
        fix_suggestion="安全场景(令牌生成、密码重置、密钥生成等)使用secrets模块。\n"
                       "例如：secrets.token_hex(32)  # 生成64字符的安全随机令牌\n"
                       "secrets.token_urlsafe(32)   # 生成URL安全的安全随机串",
    ),
}


def get_rule(rule_id: str) -> Rule:
    """根据规则ID获取规则定义"""
    return RULES.get(rule_id, RULES["SC000"])
