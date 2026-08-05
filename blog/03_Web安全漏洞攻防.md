# 10种Web安全漏洞：从攻击到防御的完整实战

> **摘要**：Web安全漏洞层出不穷，但底层原理有迹可循。本文基于安全攻防两阶段的练习代码（攻击篇1425行 + 防御篇2399行），系统讲解SQL注入、命令注入、XSS、SSRF、路径遍历、不安全反序列化、JWT篡改、XXE、CSRF、认证绕过等10种漏洞的攻击原理与防御方案。每种漏洞都配有真实的攻击代码和防御代码对照，帮助开发者从攻击者视角理解安全防护的本质。

**关键词**：Web安全、漏洞攻防、SQL注入、XSS、SSRF、CSRF、纵深防御

---

## 一、注入的本质：数据被当作代码

### 1.1 SQL注入

**攻击原理**：当用户输入直接拼接到SQL语句中，攻击者可以注入SQL关键字，使数据被解释器当作代码执行。

```python
# ─── 攻击代码 ───
def unsafe_sql(username, password):
    sql = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    # 攻击者输入: ' OR 1=1 --
    # 实际SQL: SELECT * FROM users WHERE username='' OR 1=1 --' AND password='...'
    # 1=1 永真 → 绕过认证，返回所有用户
    return execute(sql)

# 攻击演示
unsafe_sql("' OR 1=1 --", "anything")  # → 绕过认证，获取全部用户数据
```

**防御方案**：参数化查询——数据与代码隔离

```python
# ─── 防御代码：参数化查询引擎 ───
class ParameterizedQueryEngine:
    def prepare(self, sql_template):
        """预编译SQL模板，提取占位符"""
        self.param_store = {'template': sql_template, 'params': []}

    def bind(self, value):
        """绑定参数——值被当作数据而非SQL代码"""
        self.param_store['params'].append(value)

    def execute(self):
        """参数作为纯数据传递，不会被解释为SQL"""
        template = self.param_store['template']
        for param in self.param_store['params']:
            result = template.replace('?', f"[DATA:{repr(param)}]", 1)
        return result

# 使用方式
engine = ParameterizedQueryEngine()
engine.prepare("SELECT * FROM users WHERE username=? AND password=?")
engine.bind("' OR 1=1 --")  # 被当作纯字符串，不会被执行
engine.execute()
# → SELECT * FROM users WHERE username=[DATA:"' OR 1=1 --"] AND password=...
```

关键区别：参数化查询中，`?`占位符的值由数据库引擎当作纯数据处理，不经过SQL解析器，因此`' OR 1=1 --`只是一个普通字符串。

### 1.2 命令注入

**攻击原理**：当用户输入拼接到shell命令中，攻击者通过`;`、`&&`、`|`等分隔符注入额外命令。

```python
# ─── 攻击代码 ───
def unsafe_cmd(inp):
    cmd = f"ping {inp}"
    os.system(cmd)
    # 攻击者输入: 192.168.1.1; cat /etc/passwd
    # 实际执行: ping 192.168.1.1; cat /etc/passwd
    # → ping结束后读取密码文件

unsafe_cmd("192.168.1.1; cat /etc/passwd")
unsafe_cmd("127.0.0.1 && whoami")
```

**防御方案**：subprocess参数列表 + 输入校验

```python
# ─── 防御代码 ───
import subprocess
import re

def safe_cmd(ip):
    # 1. 输入校验：只允许IP地址格式
    if not re.match(r'^[\d.]+$', ip):
        raise ValueError("非法IP地址")

    # 2. 使用参数列表（非字符串拼接），shell=False
    subprocess.run(['ping', '-c', '3', ip], shell=False)
    # shell=False时，参数列表中的每个元素都被当作独立参数
    # ; && | 等字符不会被shell解释
```

### 1.3 SSTI模板注入

**攻击原理**：用户输入被直接嵌入模板引擎，`{{7*7}}`等表达式被执行。

```python
# ─── 攻击代码 ───
def unsafe_tpl(inp):
    tpl = f"Hello, {inp}!"
    render(tpl)
    # 攻击者输入: {{7*7}}
    # 模板引擎执行: 7*7 = 49

unsafe_tpl("{{7*7}}")         # → Hello, 49!
unsafe_tpl("{{config.SECRET_KEY}}")  # → 泄露密钥
```

**防御**：自动转义 + 沙箱模板引擎，禁止渲染用户输入中的模板表达式。

---

## 二、跨站攻击：信任边界突破

### 2.1 XSS（跨站脚本）

**反射型XSS**：用户输入直接回显到HTML页面。

```python
# ─── 攻击代码 ───
def reflect_xss(inp):
    html = f"<div>搜索结果: {inp}</div>"
    # 攻击者输入: <script>alert('XSS')</script>
    # <script>标签被直接嵌入HTML，浏览器执行JS
    return html
```

**存储型XSS**：恶意payload存入数据库后渲染给其他用户。

```python
# ─── 攻击代码 ───
comment_db = []
payload = "<img src=x onerror=alert(document.cookie)>"
comment_db.append({"user": "attacker", "content": payload})
# 其他用户访问页面时，onerror事件触发，窃取Cookie
```

**防御方案**：HTML输出编码 + CSP

```python
# ─── 防御代码：输出编码器 ───
class OutputEncoder:
    @staticmethod
    def html_encode(s):
        """HTML上下文编码"""
        replacements = {
            '&': '&amp;', '<': '&lt;', '>': '&gt;',
            '"': '&quot;', "'": '&#x27;'
        }
        for char, enc in replacements.items():
            s = s.replace(char, enc)
        return s
    # <script> → &lt;script&gt; 不再被浏览器执行

    @staticmethod
    def js_encode(s):
        """JS上下文编码"""
        result = []
        for ch in s:
            code = ord(ch)
            if code < 0x20 or code in (0x22, 0x27, 0x5c, 0x2f, 0x3c, 0x3e):
                result.append(f'\\u{code:04x}')
            else:
                result.append(ch)
        return ''.join(result)

# CSP策略生成器
class CSPPolicyGenerator:
    def generate(self, nonce=None):
        n = nonce or secrets.token_hex(8)
        directives = {
            'script-src': f"'self' 'nonce-{n}'",
            'object-src': "'none'",
            'frame-ancestors': "'none'",
        }
        return '; '.join(f"{k} {v}" for k, v in directives.items())
```

### 2.2 CSRF（跨站请求伪造）

**攻击原理**：攻击者构造恶意页面，利用受害者已登录的Cookie自动提交请求。

```html
<!-- 攻击者构造的恶意页面 -->
<form action="https://bank.com/transfer" method="POST" id="f">
  <input type="hidden" name="to" value="attacker">
  <input type="hidden" name="amount" value="10000">
</form>
<script>document.getElementById('f').submit();</script>
```

**防御**：CSRF Token + SameSite Cookie

```python
# ─── 防御代码 ───
# 1. CSRF Token：表单包含服务端生成的随机Token
csrf_token = secrets.token_hex(32)
# 每次请求验证Token是否匹配

# 2. SameSite Cookie属性
# Set-Cookie: session=xxx; SameSite=Strict; HttpOnly; Secure
# SameSite=Strict → 跨站请求不携带Cookie
# HttpOnly → JS无法读取Cookie（防XSS窃取）
# Secure → 仅HTTPS传输
```

---

## 三、文件攻击：路径与内容操纵

### 3.1 路径遍历

**攻击原理**：通过`../`突破目录限制，访问任意文件。

```python
# ─── 攻击代码 ───
base_dir = "/var/www/uploads"
def unsafe_read(filename):
    path = os.path.join(base_dir, filename)
    # 攻击者输入: ../../../etc/passwd
    # 拼接路径: /var/www/uploads/../../../etc/passwd → /etc/passwd
    return open(path).read()

# 编码绕过
unsafe_read("..%2f..%2f..%2fetc%2fpasswd")  # URL编码绕过
```

**防御方案**：路径规范化 + 边界检查

```python
# ─── 防御代码 ───
class PathNormalizer:
    @staticmethod
    def normalize(path, base_dir="/var/www/uploads"):
        # 移除null字节
        path = path.replace('\x00', '')
        # 统一路径分隔符
        path = path.replace('\\', '/')
        # 逐段解析 ../
        parts = []
        for part in path.split('/'):
            if part == '..':
                if parts:
                    parts.pop()
            elif part in ('.', ''):
                continue
            else:
                parts.append(part)
        normalized = '/' + '/'.join(parts)
        full = os.path.join(base_dir, normalized.lstrip('/'))
        full = os.path.normpath(full)
        # 确保在基准目录内
        if not full.startswith(base_dir):
            return None, "路径遍历被阻断: 超出基准目录"
        return full, "路径规范化通过"
```

### 3.2 恶意文件上传

**攻击方式**：双扩展名绕过（`shell.php.jpg`）、Content-Type伪造、替代扩展名（`.phtml`）。

**防御方案**：四层联动——扩展名白名单 + Magic Number验证 + 内容检测 + 沙箱隔离

```python
# ─── 防御代码 ───
class FileTypeValidator:
    ALLOWED_EXTENSIONS = {'.jpg', '.png', '.gif', '.pdf', '.txt'}
    MAGIC_NUMBERS = {
        b'\xff\xd8\xff': '.jpg',
        b'\x89PNG': '.png',
        b'GIF8': '.gif',
        b'%PDF': '.pdf',
    }

    @classmethod
    def validate(cls, filename, content=b''):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            return False, f"扩展名 {ext} 不在白名单中"
        # Magic Number校验：防止扩展名伪装
        if content:
            for magic, expected_ext in cls.MAGIC_NUMBERS.items():
                if content[:len(magic)] == magic and expected_ext != ext:
                    return False, f"Magic Number({expected_ext})与扩展名({ext})不匹配"
        return True, "文件类型校验通过"

class FileContentDetector:
    MALICIOUS_PATTERNS = [
        re.compile(rb'<\?php', re.I),
        re.compile(rb'eval\s*\(', re.I),
        re.compile(rb'system\s*\(', re.I),
        re.compile(rb'\$_(GET|POST|REQUEST)', re.I),
    ]

    @classmethod
    def scan(cls, content):
        for pattern in cls.MALICIOUS_PATTERNS:
            if pattern.search(content):
                return False, f"检测到恶意特征"
        return True, "内容检测通过"
```

---

## 四、SSRF：服务端请求伪造

### 4.1 攻击原理

攻击者利用服务器发起HTTP请求的能力，访问内网资源或云元数据接口。

```python
# ─── 攻击代码 ───
def ssrf_fetch(url):
    # 用户输入URL: http://169.254.169.254/latest/meta-data/
    # → 服务器访问AWS元数据接口，获取IAM凭证
    response = requests.get(url)
    return response.text

# 攻击目标
ssrf_fetch("http://169.254.169.254/latest/meta-data/")  # 云元数据
ssrf_fetch("http://127.0.0.1:6379/")                     # 内网Redis
ssrf_fetch("file:///etc/passwd")                          # 本地文件
```

### 4.2 防御方案

```python
# ─── 防御代码 ───
from urllib.parse import urlparse
import ipaddress

def safe_fetch(url):
    parsed = urlparse(url)

    # 1. 协议白名单：只允许http/https
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"禁止协议: {parsed.scheme}")

    # 2. 域名白名单
    ALLOWED_HOSTS = ['api.external.com', 'cdn.example.com']
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"禁止域名: {parsed.hostname}")

    # 3. 禁止内网IP
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"禁止内网地址: {ip}")
    except ValueError:
        pass  # 域名而非IP，已在白名单中检查

    return requests.get(url, timeout=5)
```

---

## 五、不安全反序列化

### 5.1 攻击原理

`pickle.loads()`、`eval()`、`exec()`等函数执行不可信数据时，攻击者可构造恶意序列化数据实现远程代码执行。

```python
# ─── 攻击代码 ───
import pickle

# 攻击者构造的恶意pickle数据
class Exploit:
    def __reduce__(self):
        import os
        return (os.system, ('whoami',))

malicious_data = pickle.dumps(Exploit())
# 受害者执行
pickle.loads(malicious_data)  # → 执行 os.system('whoami')
```

### 5.2 防御方案

```python
# ─── 防御代码 ───
# 1. 使用JSON替代pickle（JSON只支持基本类型，无法执行代码）
import json
data = json.loads(untrusted_json_string)  # 安全

# 2. 如必须使用pickle，通过HMAC签名验证数据完整性
import hmac, hashlib

def safe_pickle_loads(data, key):
    # 数据格式: hmac_signature + b'\n' + pickle_data
    sig, payload = data.split(b'\n', 1)
    expected = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("数据签名验证失败")
    return pickle.loads(payload)  # 签名通过后才反序列化

# 3. 禁止在生产代码中使用eval/exec
# eval("os.system('rm -rf /')")  # 绝对禁止
```

---

## 六、JWT安全

### 6.1 JWT none算法攻击

```python
# ─── 攻击代码 ───
import base64, json, hmac, hashlib

def jwt_encode(header, payload, key=None):
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    alg = header.get("alg", "HS256")
    if alg == "none":
        return f"{h}.{p}."  # 无签名！
    msg = f"{h}.{p}".encode()
    sig = base64.urlsafe_b64encode(
        hmac.new(key.encode(), msg, hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"

# 原始Token（guest用户）
original = jwt_encode({"alg": "HS256", "typ": "JWT"},
                      {"user": "guest", "role": "user"}, "s3cretK3y")

# 篡改Token（改为admin，alg改为none）
forged = jwt_encode({"alg": "none", "typ": "JWT"},
                    {"user": "admin", "role": "superadmin"})
# → 无需密钥即可伪造任意身份！
```

### 6.2 防御

```python
# ─── 防御代码 ───
def jwt_verify(token, key):
    header, payload, sig = jwt_decode(token)
    # 拒绝none算法
    if header.get("alg") == "none":
        return False, "alg=none，拒绝"
    # 验证签名
    expected = jwt_encode(header, payload, key).split(".")[2]
    if hmac.compare_digest(sig, expected):
        return True, "签名通过"
    return False, "签名不匹配"
```

### 6.3 JWT弱密钥破解

```python
# 攻击者用常见密钥字典暴力破解
common_keys = ["secret", "key", "password", "123456", "jwt_secret"]
for k in common_keys:
    valid, _ = jwt_verify(weak_token, k)
    if valid:
        print(f"密钥破解成功: '{k}'")
        break
```

**防御**：使用足够长的随机密钥（至少256位），不要使用常见单词。

---

## 七、XXE：XML外部实体注入

### 7.1 攻击原理

```xml
<!-- 攻击者提交的恶意XML -->
<?xml version="1.0"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>
```

漏洞解析器会将`file:///etc/passwd`的内容替换`&xxe;`，导致敏感文件泄露。还可以利用`http://`协议进行内网探测。

### 7.2 防御

```python
# ─── 防御代码 ───
class XMLSafeParser:
    @classmethod
    def check_unsafe(cls, xml_content):
        """检查XML是否包含危险特性"""
        dangers = []
        if re.search(r'<!DOCTYPE', xml_content, re.I):
            dangers.append("DOCTYPE声明")
        if re.search(r'<!ENTITY', xml_content, re.I):
            dangers.append("实体定义")
        if re.search(r'SYSTEM\s+"', xml_content, re.I):
            dangers.append("外部实体引用")
        return dangers

    @classmethod
    def safe_parse(cls, xml_content):
        dangers = cls.check_unsafe(xml_content)
        if dangers:
            return False, f"拒绝解析: 检测到 {' + '.join(dangers)}"
        return True, "安全解析通过"

# 更好的方案：使用defusedxml替代标准xml.etree
# from defusedxml import ElementTree as ET
# defusedxml自动禁用外部实体解析
```

---

## 八、纵深防御：四层联动体系

单个防御措施可能被绕过，真正的安全需要多层防御互相补充：

```
攻击请求 → [层1: WAF] → [层2: 参数化查询] → [层3: 输出编码] → [层4: CSP] → 安全
                ↓ 拦截         ↓ 阻断SQL        ↓ 阻断XSS        ↓ 阻断内联JS
              已知模式        注入值不执行      数据不渲染为代码   脚本不执行
```

### WAF规则引擎

```python
class WAFRuleEngine:
    RULES = [
        ("SQL注入-UNION",   re.compile(r"union\s+select", re.I), "block"),
        ("SQL注入-OR条件",  re.compile(r"'\s*or\s*'?\d*'?\s*=\s*'?\d*", re.I), "block"),
        ("SQL注入-注释",    re.compile(r"--|/\*|\*/|#"), "block"),
        ("命令注入-管道",   re.compile(r"[|;&`$]"), "block"),
        ("XSS-脚本标签",    re.compile(r"<script[^>]*>", re.I), "block"),
        ("XSS-事件处理器",  re.compile(r"on\w+\s*=", re.I), "block"),
        ("XSS-JS伪协议",    re.compile(r"javascript:", re.I), "block"),
        ("SSTI-模板注入",   re.compile(r"\{\{.*\}\}|\{%.*%\}"), "block"),
        ("路径遍历",        re.compile(r"\.\./|\.\.\\|\.\.%2f", re.I), "block"),
    ]

    @classmethod
    def block_or_pass(cls, payload):
        hits = []
        for name, pattern, action in cls.RULES:
            if pattern.search(payload):
                hits.append({'rule': name, 'action': action})
        if hits:
            return False, hits
        return True, []
```

### 联动防御演示

```python
# 四层联动：WAF + 参数化查询 + 输出编码 + CSP
def full_defense(payload):
    # 层1: WAF拦截
    passed, hits = WAFRuleEngine.block_or_pass(payload)
    if not passed:
        return f"被WAF拦截: {[h['rule'] for h in hits]}"

    # 层2: 参数化查询
    engine = ParameterizedQueryEngine()
    engine.prepare("SELECT * FROM users WHERE name=?")
    engine.bind(payload)
    sql_result = engine.execute()

    # 层3: 输出编码
    encoded = OutputEncoder.html_encode(payload)

    # 层4: CSP策略
    csp, nonce = CSPPolicyGenerator().generate()

    return "全部通过 → 输出已编码, CSP已启用"

# 测试
full_defense("' OR '1'='1' -- ")      # → 被WAF拦截: SQL注入-OR条件
full_defense("<script>alert(1)</script>")  # → 被WAF拦截: XSS-脚本标签
full_defense("normal_input")           # → 全部通过
```

**纵深防御的核心思想**：任一层独立失效，其他层仍可兜底。WAF可能漏过新型攻击，但参数化查询确保SQL注入值不被执行；参数化查询不能防XSS，但输出编码可以；输出编码可能遗漏，但CSP阻止内联脚本执行。

---

## 九、认证安全

### 9.1 弱密码爆破

```python
# ─── 攻击代码 ───
target_hash = hashlib.sha256("admin123".encode()).hexdigest()
password_dict = ["123456", "password", "admin", "admin123", "qwerty"]
for pw in password_dict:
    if hashlib.sha256(pw.encode()).hexdigest() == target_hash:
        print(f"爆破成功: {pw}")
        break
```

**防御**：密码策略 + 速率限制 + MFA

```python
# 密码策略：最少12位，包含大小写/数字/特殊字符
# 速率限制：5次失败锁定15分钟
# 强制MFA：密码 + OTP/生物识别
```

### 9.2 密码重置毒化

```python
# ─── 攻击代码 ───
# 正常请求: Host: example.com → 重置链接: https://example.com/reset?token=abc
# 攻击请求: Host: evil.com    → 重置链接: https://evil.com/reset?token=abc
# 用户点击邮件中的链接 → token泄露给攻击者
```

**防御**：不信任Host头，使用服务端硬编码域名生成重置链接。

---

## 十、总结：安全防护的核心原则

| 原则 | 说明 | 本文示例 |
|------|------|---------|
| 数据与代码隔离 | 永远不要将用户输入当作代码执行 | 参数化查询、subprocess参数列表 |
| 白名单优于黑名单 | 只允许已知安全的输入 | 文件扩展名白名单、URL域名白名单 |
| 纵深防御 | 多层防护互相补充 | WAF + 参数化 + 编码 + CSP |
| 最小权限 | 只授予必要的权限 | 非root运行、沙箱隔离 |
| 不信任任何输入 | 所有外部数据都是不可信的 | 路径规范化、JSON替代pickle |

安全不是一蹴而就的，而是贯穿开发全生命周期的持续过程。理解攻击原理，才能写出真正安全的代码。

> 本文所有代码均来自实际练习项目，攻击篇1425行 + 防御篇2399行，覆盖15道攻击练习题和10道防御练习题。

---

*作者：koze | AI全栈学习笔记*
