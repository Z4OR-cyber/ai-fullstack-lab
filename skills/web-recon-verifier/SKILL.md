---
name: web-recon-verifier
description: Web侦察验证与误报识别技能。当使用自动化扫描工具（nuclei/httpx/ffuf等）进行Web安全侦察或Bug Bounty时，用于验证扫描结果、排除SPA catch-all误报、对比404控制路径、审计安全头、识别WAF拦截模式、评估漏洞可利用性。核心方法是404控制路径对比法（请求不存在的路径作为控制组，对比响应hash/长度/content-type来区分真实发现与误报）。当你需要验证CRITICAL/HIGH发现是否真实、排除误报、做安全头审计、判断WAF是否在拦截、评估Bug Bounty发现的实际严重等级时使用此技能。
---

# Web侦察验证器

> 从Varonis Bug Bounty实战中提炼的侦察验证方法论。解决自动化扫描工具产生大量误报的核心痛点。

## 问题背景

自动化扫描工具（nuclei、httpx、ffuf）对现代Web应用会产生大量误报：
- **SPA catch-all**：React/Vue/Angular单页应用对所有路径返回相同HTML（200状态码），扫描器误报为"敏感文件泄露"
- **WAF拦截页**：Imperva/Cloudflare/Azure WAF对恶意请求返回403，但对正常路径也返回403，无法区分
- **重定向循环**：某些应用将所有未知路径301重定向到首页或登录页
- **默认网关响应**：API网关配置了默认后端（如httpbin.org），所有路径返回相同响应

**实战数据**：Varonis Recon中，自动化扫描报告114个findings，其中所有CRITICAL级别均为误报。经过404控制路径对比法验证后，仅保留6个真实的低危安全头问题。

## 核心方法：404控制路径对比法

### 原理

对每个"发现"，发送一个请求到**确定不存在的路径**（控制组），比较控制组与发现的响应：

| 对比维度 | 真实发现 | 误报 |
|---------|---------|------|
| 响应体hash | 不同 | 相同 |
| 响应长度 | 显著不同 | 相同或极接近 |
| Content-Type | 可能不同 | 相同 |
| 状态码 | 不同（200 vs 404/403） | 相同（都是200/301/403） |
| 响应头 | 可能有差异 | 高度一致 |

### 执行步骤

1. **生成随机控制路径**：使用`/{random_uuid}_notexist`或`/this-path-does-not-exist-12345`，确保不会命中真实路由
2. **请求控制路径**：记录响应的status_code、headers、body长度、body hash
3. **请求发现路径**：记录相同维度
4. **对比判定**：
   - body hash完全相同 → **误报**（catch-all）
   - 长度差<5%且Content-Type相同 → **疑似误报**
   - 状态码不同且body内容有实质差异 → **可能真实**
   - 控制路径返回404但发现路径返回200且内容不同 → **真实发现**

### Python实现

```python
import hashlib
import requests
import uuid

def verify_finding(base_url, finding_path, timeout=10):
    """验证单个发现是否为误报"""
    control_path = f"/{uuid.uuid4().hex}_notexist"
    
    # 请求控制组
    ctrl_resp = requests.get(
        f"{base_url}{control_path}", 
        timeout=timeout, 
        allow_redirects=False,
        verify=False
    )
    # 请求发现
    find_resp = requests.get(
        f"{base_url}{finding_path}", 
        timeout=timeout, 
        allow_redirects=False,
        verify=False
    )
    
    ctrl_hash = hashlib.sha256(ctrl_resp.text.encode()).hexdigest()[:16]
    find_hash = hashlib.sha256(find_resp.text.encode()).hexdigest()[:16]
    
    result = {
        "finding_path": finding_path,
        "control_status": ctrl_resp.status_code,
        "finding_status": find_resp.status_code,
        "control_len": len(ctrl_resp.text),
        "finding_len": len(find_resp.text),
        "control_hash": ctrl_hash,
        "finding_hash": find_hash,
        "same_body": ctrl_hash == find_hash,
        "length_diff_pct": abs(len(ctrl_resp.text) - len(find_resp.text)) / max(len(ctrl_resp.text), 1) * 100,
        "content_type_match": ctrl_resp.headers.get("content-type") == find_resp.headers.get("content-type"),
    }
    
    # 判定
    if result["same_body"]:
        result["verdict"] = "FALSE_POSITIVE"
        result["reason"] = "Identical response body - SPA catch-all or default handler"
    elif result["length_diff_pct"] < 5 and result["content_type_match"]:
        result["verdict"] = "LIKELY_FALSE_POSITIVE"
        result["reason"] = "Nearly identical response length and content type"
    elif result["finding_status"] == 200 and result["control_status"] in (404, 403):
        result["verdict"] = "LIKELY_REAL"
        result["reason"] = "Different status codes with different content"
    else:
        result["verdict"] = "NEEDS_MANUAL_REVIEW"
        result["reason"] = "Ambiguous differences, requires manual inspection"
    
    return result
```

## WAF识别与拦截判断

### 常见WAF特征

| WAF | 识别特征 |
|-----|---------|
| Imperva | 响应头含 `x-cdn: Imperva`；拦截页含"Request unsuccessful. Incapsula incident" |
| Cloudflare | 响应头含 `server: cloudflare`、`cf-ray`；403页含"Cloudflare" |
| Azure WAF | 响应头含 `x-azure-ref`；拦截返回403 `{"message":"..."}` |
| AWS WAF | 响应头含 `x-amzn-requestid`、`x-amzn-waf` |
| Akamai | 响应头含 `server: AkamaiGHost`、`x-akamai-transformed` |

### 判断方法

1. **正常请求基线**：请求首页，记录正常响应
2. **恶意payload请求**：发送含`' OR 1=1--`或`<script>alert(1)</script>`的请求
3. **对比**：
   - 正常请求200，恶意请求403且含WAF特征 → WAF在保护
   - 所有请求（包括正常路径）都返回403 → WAF配置过严或IP被封
   - 恶意payload返回200但内容被过滤 → WAF在应用层过滤
4. **响应头线索**：`x-alltrue-llm-error-type: rule-violation` 表示AI网关WAF

### 实战案例

```
# atlas-gw.varonis.io 所有路径返回：
400 {"message": "Unprocessable request to https://httpbin.org/"}
x-alltrue-llm-error-type: rule-violation

# 判定：Alltrue LLM网关，默认后端为httpbin.org
# SSRF注入尝试全部被Azure WAF拦截(403)
# 结论：配置信息泄露，非可直接利用的SSRF漏洞
```

## 安全头审计

### 检查清单

对每个scope内主机，检查以下安全头：

```python
SECURITY_HEADERS = {
    "x-frame-options": {"expected": ["DENY", "SAMEORIGIN"], "severity": "P4"},
    "content-security-policy": {"check": "frame-ancestors", "severity": "P4"},
    "strict-transport-security": {"expected_prefix": "max-age=", "severity": "P5"},
    "x-content-type-options": {"expected": ["nosniff"], "severity": "P5"},
    "x-xss-protection": {"expected": ["1", "1; mode=block"], "severity": "P5"},
    "referrer-policy": {"exists": True, "severity": "P5"},
    "permissions-policy": {"exists": True, "severity": "P5"},
}

COOKIE_CHECKS = ["Secure", "HttpOnly", "SameSite"]
```

### Clickjacking判定

- 缺少 `X-Frame-Options` **且** CSP中无 `frame-ancestors` 指令 → clickjacking风险
- 影响等级取决于页面功能：
  - 登录/表单页面 → P3（可构造点击劫持）
  - 403/404错误页面 → P5（无可利用功能）
  - 管理后台 → P2（高价值目标）

### HSTS判定

- 缺少 `Strict-Transport-Security` → P5信息级
- 已有HSTS但 `max-age=0` → 需关注（等于禁用）

## 子域名枚举可靠性

### 数据源优先级

1. **certspotter API**（推荐）：`https://api.certspotter.com/v1/issuances?domain=DOMAIN&include_subdomains=true&expand=dns_names`
   - 稳定、快速、返回PEM证书中的所有SAN
2. **crt.sh**（备选）：`https://crt.sh/?q=%25.DOMAIN&output=json`
   - 频繁超时，需要重试机制
3. **DNS暴力枚举**：使用subfinder + 字典
   - 最全面但耗时

### 验证流程

```
子域名列表 → DNS解析（过滤无响应）→ HTTP探测（httpx）→ 存活服务 → 安全扫描
                                    ↓
                              内部主机（AKS/K8s）→ 跳过（不在公网scope）
```

## 严重等级评估

### CVSS-inspired评级

| 等级 | 标准 | 赏金预期 |
|-----|------|---------|
| P1/Critical | RCE、SQL注入、认证绕过、敏感数据泄露 | $500-$10000+ |
| P2/High | SSRF（可访问内网）、存储型XSS、IDOR（高价值数据） | $200-$2000 |
| P3/Medium | 反射型XSS、CSRF（敏感操作）、开放重定向 | $50-$500 |
| P4/Low | Clickjacking（低价值页面）、Cookie缺少安全标志 | $0-$100 |
| P5/Info | 缺少安全头、版本信息泄露、OPTIONS方法启用 | 通常无赏金 |

### 诚实原则

- 安全头缺失在错误页面（403/404）上几乎没有可利用性，应如实评为P5
- 不要为了提高赏金而夸大严重等级
- 配置信息（如默认后端URL）在无法利用时评为P5
- 如果WAF拦截了所有利用尝试，即使漏洞模式存在也应降级或不报

## 批量验证脚本

对扫描结果JSON批量验证：

```python
import json

def batch_verify(recon_results, base_url):
    """批量验证所有发现"""
    verified = []
    for finding in recon_results.get("findings", []):
        if finding.get("severity") in ("CRITICAL", "HIGH"):
            result = verify_finding(base_url, finding["path"])
            finding["verification"] = result
            if result["verdict"] not in ("FALSE_POSITIVE", "LIKELY_FALSE_POSITIVE"):
                verified.append(finding)
        else:
            # 低危发现直接保留但标注
            finding["verification"] = {"verdict": "ACCEPTED_LOW_SEVERITY"}
            verified.append(finding)
    return verified
```

## 适用场景

- Bug Bounty Recon结果验证
- nuclei扫描结果去伪
- 安全头合规审计
- WAF配置评估
- 自动化扫描pipeline的验证阶段
- 渗透测试报告的误报过滤

## 边界与限制

- 此技能用于**验证**而非扫描，需要先有扫描结果
- 对需要认证的页面，验证时需携带有效session cookie
- 大量请求可能触发WAF封禁，建议加延迟（1-2秒/请求）
- 云端数据中心IP可能被WAF直接拦截，深度测试需要住宅IP
