#!/usr/bin/env python3
"""
Web Recon Verifier - 验证Web侦察结果，排除误报
核心方法：404控制路径对比法
"""

import hashlib
import json
import sys
import uuid
import argparse

from coze_workload_identity import requests

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass


SECURITY_HEADERS = {
    "x-frame-options": {"severity": "P4", "description": "Missing clickjacking protection"},
    "content-security-policy": {"severity": "P4", "description": "Missing CSP (check frame-ancestors)"},
    "strict-transport-security": {"severity": "P5", "description": "Missing HSTS"},
    "x-content-type-options": {"severity": "P5", "description": "Missing nosniff"},
    "referrer-policy": {"severity": "P5", "description": "Missing referrer policy"},
    "permissions-policy": {"severity": "P5", "description": "Missing permissions policy"},
}

WAF_SIGNATURES = {
    "Imperva": ["x-cdn: Imperva", "incapsula", "Incapsula incident"],
    "Cloudflare": ["server: cloudflare", "cf-ray", "Cloudflare"],
    "Azure WAF": ["x-azure-ref", "azure"],
    "AWS WAF": ["x-amzn-waf", "x-amzn-requestid"],
    "Akamai": ["akamai", "x-akamai-transformed"],
    "Alltrue LLM": ["x-alltrue-llm-error-type", "alltrue"],
}


def fingerprint(resp):
    """生成响应指纹"""
    body_hash = hashlib.sha256(resp.text.encode("utf-8", errors="replace")).hexdigest()
    return {
        "status": resp.status_code,
        "length": len(resp.text),
        "body_hash": body_hash[:16],
        "content_type": resp.headers.get("content-type", ""),
        "server": resp.headers.get("server", ""),
        "headers": dict(resp.headers),
    }


def verify_finding(base_url, path, timeout=10, headers=None):
    """404控制路径对比法验证单个发现"""
    control_path = f"/{uuid.uuid4().hex}_404control"
    url = base_url.rstrip("/")
    
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    if headers:
        default_headers.update(headers)
    
    try:
        ctrl = requests.get(
            f"{url}{control_path}", timeout=timeout,
            verify=False, allow_redirects=False, headers=default_headers
        )
        find = requests.get(
            f"{url}{path}", timeout=timeout,
            verify=False, allow_redirects=False, headers=default_headers
        )
    except requests.RequestException as e:
        return {"path": path, "verdict": "ERROR", "error": str(e)}
    
    ctrl_fp = fingerprint(ctrl)
    find_fp = fingerprint(find)
    
    len_diff = abs(ctrl_fp["length"] - find_fp["length"])
    max_len = max(ctrl_fp["length"], find_fp["length"], 1)
    len_pct = (len_diff / max_len) * 100
    
    result = {
        "path": path,
        "control": ctrl_fp,
        "finding": find_fp,
        "same_body": ctrl_fp["body_hash"] == find_fp["body_hash"],
        "length_diff_pct": round(len_pct, 2),
        "content_type_match": ctrl_fp["content_type"] == find_fp["content_type"],
    }
    
    if result["same_body"]:
        result["verdict"] = "FALSE_POSITIVE"
        result["reason"] = "Identical response body - catch-all handler"
    elif len_pct < 5 and result["content_type_match"]:
        result["verdict"] = "LIKELY_FALSE_POSITIVE"
        result["reason"] = "Nearly identical response"
    elif find_fp["status"] == 200 and ctrl_fp["status"] in (404, 403, 400):
        result["verdict"] = "LIKELY_REAL"
        result["reason"] = "Different status with different content"
    else:
        result["verdict"] = "NEEDS_REVIEW"
        result["reason"] = "Ambiguous, manual inspection needed"
    
    return result


def audit_security_headers(url, timeout=10, headers=None):
    """安全头审计"""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    if headers:
        default_headers.update(headers)
    
    try:
        resp = requests.get(
            url, timeout=timeout, verify=False,
            allow_redirects=False, headers=default_headers
        )
    except requests.RequestException as e:
        return {"url": url, "error": str(e)}
    
    results = {"url": url, "status": resp.status_code, "missing": [], "cookies": []}
    
    for header, info in SECURITY_HEADERS.items():
        if header not in {k.lower(): v for k, v in resp.headers.items()}:
            results["missing"].append({
                "header": header,
                "severity": info["severity"],
                "description": info["description"],
            })
    
    # CSP frame-ancestors special check
    csp = resp.headers.get("content-security-policy", "")
    if "frame-ancestors" not in csp.lower():
        if "x-frame-options" not in {k.lower() for k in resp.headers}:
            results["clickjacking_risk"] = True
    
    # Cookie security
    for cookie in resp.cookies:
        issues = []
        if not cookie.secure:
            issues.append("missing Secure")
        if not cookie.has_nonstandard_attr("HttpOnly"):
            issues.append("missing HttpOnly")
        samesite = cookie.get_nonstandard_attr("SameSite", "")
        if not samesite:
            issues.append("missing SameSite")
        if issues:
            results["cookies"].append({
                "name": cookie.name,
                "issues": issues,
            })
    
    return results


def detect_waf(resp_or_headers):
    """识别WAF"""
    detected = []
    if hasattr(resp_or_headers, "headers"):
        header_str = str(dict(resp_or_headers.headers)).lower()
    else:
        header_str = str(resp_or_headers).lower()
    
    for waf, sigs in WAF_SIGNATURES.items():
        for sig in sigs:
            if sig.lower() in header_str:
                detected.append(waf)
                break
    
    return detected


def main():
    parser = argparse.ArgumentParser(description="Web Recon Verifier")
    parser.add_argument("url", help="Target base URL")
    parser.add_argument("--paths", nargs="+", help="Paths to verify")
    parser.add_argument("--audit", action="store_true", help="Run security header audit")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--output", "-o", help="Output JSON file")
    args = parser.parse_args()
    
    results = {"target": args.url, "findings": [], "header_audit": None}
    
    if args.audit:
        print(f"[*] Auditing security headers: {args.url}")
        audit = audit_security_headers(args.url, args.timeout)
        results["header_audit"] = audit
        if "missing" in audit:
            for m in audit["missing"]:
                print(f"  [{m['severity']}] Missing: {m['header']}")
    
    if args.paths:
        print(f"[*] Verifying {len(args.paths)} findings...")
        for path in args.paths:
            r = verify_finding(args.url, path, args.timeout)
            results["findings"].append(r)
            icon = {
                "FALSE_POSITIVE": "[-]",
                "LIKELY_FALSE_POSITIVE": "[~]",
                "LIKELY_REAL": "[+]",
                "NEEDS_REVIEW": "[?]",
                "ERROR": "[!]",
            }.get(r["verdict"], "[?]")
            print(f"  {icon} {path}: {r['verdict']} - {r.get('reason', '')}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n[*] Results saved to {args.output}")
    
    # Summary
    fp = sum(1 for f in results["findings"] if f["verdict"] in ("FALSE_POSITIVE", "LIKELY_FALSE_POSITIVE"))
    real = sum(1 for f in results["findings"] if f["verdict"] == "LIKELY_REAL")
    review = sum(1 for f in results["findings"] if f["verdict"] == "NEEDS_REVIEW")
    print(f"\n=== Summary: {fp} false positives, {real} likely real, {review} need review ===")


if __name__ == "__main__":
    main()
