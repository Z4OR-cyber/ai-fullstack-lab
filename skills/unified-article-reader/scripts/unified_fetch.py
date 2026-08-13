#!/usr/bin/env python3
"""
统一文章抓取器 (Unified Article Fetcher)
整合 curl直抓 + Python requests + 完整脚本提取 三级策略级联

策略优先级：
  1. curl 直抓（最快，~3秒）— 模拟 iPhone 微信客户端 UA
  2. Python requests + iOS微信UA（获取OG元数据，~5秒）
  3. 完整脚本提取（最全面，~8秒）— 平台特定CSS选择器 + readability回退

用法：
  python3 unified_fetch.py --url "https://mp.weixin.qq.com/s/xxxxx"
  python3 unified_fetch.py --url "https://zhuanlan.zhihu.com/p/xxx" --cookie "z_c0=xxx"
  python3 unified_fetch.py --url "https://example.com/article" --format json
  python3 unified_fetch.py --url "https://mp.weixin.qq.com/s/xxxxx" --download-images
  python3 unified_fetch.py --url "https://example.com/article" --strategy curl
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# ============================================================
# UA 池
# ============================================================

UA_IOS_WECHAT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.42(0x18002a2c) NetType/WIFI Language/zh_CN"
)

UA_IOS_SAFARI = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)

UA_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

UA_FIREFOX = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0"
)

USER_AGENTS = {
    "wechat": UA_IOS_WECHAT,
    "ios": UA_IOS_SAFARI,
    "chrome": UA_CHROME,
    "firefox": UA_FIREFOX,
}

# ============================================================
# 平台特定提取规则
# ============================================================

PLATFORM_RULES = {
    "mp.weixin.qq.com": {
        "title": "#activity_name",
        "content": "#js_content",
        "author": "#js_name",
    },
    "zhuanlan.zhihu.com": {
        "title": ".Post-Title",
        "content": ".Post-RichText",
        "author": ".AuthorInfo-name",
    },
    "juejin.cn": {
        "title": ".article-title",
        "content": ".article-content",
        "author": ".username",
    },
    "blog.csdn.net": {
        "title": "h1.title-article",
        "content": "#content_views",
        "author": ".user-info dtr a",
    },
}


# ============================================================
# 工具函数
# ============================================================

def detect_platform(url):
    """根据 URL 域名识别平台"""
    domain = urlparse(url).netloc.lower()
    for platform in PLATFORM_RULES:
        if platform in domain:
            return platform
    if "toutiao.com" in domain:
        return "toutiao.com"
    if "medium.com" in domain:
        return "medium.com"
    return "generic"


def is_captcha_page(html_content):
    """检测是否为微信验证码页面"""
    return "wappoc_appmsgcaptcha" in html_content


def clean_html_to_text(raw_html):
    """清理 HTML 标签，转为纯文本"""
    if not raw_html:
        return ""
    # 移除 script 和 style
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw_html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    # 标签转换
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"</h[1-6]>", "\n\n", text)
    text = re.sub(r"<h([1-6])[^>]*>", lambda m: "\n\n" + "#" * int(m.group(1)) + " ", text)
    text = re.sub(r"<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    # HTML 实体解码
    text = html.unescape(text)
    # 清理多余空行
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
    return text.strip()


def extract_images_from_html(raw_html, base_url=""):
    """从 HTML 中提取图片 URL"""
    if not raw_html:
        return []
    # data-src (微信懒加载)
    imgs = re.findall(r'data-src="([^"]+)"', raw_html)
    # src 属性
    imgs += re.findall(r'<img[^>]+src="([^"]+)"', raw_html)
    # 过滤空和占位图
    imgs = [u for u in imgs if u and not u.startswith("data:") and "pixel" not in u.lower()]
    return list(dict.fromkeys(imgs))  # 去重保序


# ============================================================
# 策略 1：curl 直抓
# ============================================================

def fetch_with_curl(url, ua_key="wechat"):
    """使用 curl 模拟浏览器抓取 HTML"""
    ua = USER_AGENTS.get(ua_key, UA_IOS_WECHAT)
    headers = [
        "-H", f"User-Agent: {ua}",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
    ]
    # 微信文章加 Referer
    if "mp.weixin.qq.com" in url:
        headers += ["-H", "Referer: https://mp.weixin.qq.com/"]

    cmd = ["curl", "-sL", "--max-time", "15", "-o", "-"] + headers + [url]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=20)
        raw = result.stdout
        if not raw or len(raw) < 1000:
            return None, "curl返回内容过短"
        html_content = raw.decode("utf-8", errors="replace")
        if is_captcha_page(html_content):
            return None, "触发微信验证码"
        return html_content, "ok"
    except subprocess.TimeoutExpired:
        return None, "curl超时"
    except Exception as e:
        return None, f"curl异常: {e}"


def parse_wechat_article(raw_bytes, url):
    """
    微信公众号文章解析 — 支持双模式HTML结构
    模式A: var msg_title = 'xxx'  +  id="js_content" div
    模式B: window.msg_title = window.title = 'xxx'  +  OG description回退
    """
    raw = raw_bytes if isinstance(raw_bytes, bytes) else raw_bytes.encode("utf-8")
    content = raw.decode("utf-8", errors="replace")

    # === 提取标题 ===
    title = "N/A"
    pattern = "OG"
    m = re.search(rb"var msg_title = '(.*?)'", raw)
    if m:
        title = m.group(1).decode("utf-8", errors="replace")
        pattern = "A"
    else:
        m = re.search(rb"window\.msg_title = window\.title = '(.*?)'", raw)
        if m:
            title = m.group(1).decode("utf-8", errors="replace")
            pattern = "B"
        else:
            og = re.search(r'<meta property="og:title" content="(.*?)"', content)
            if og:
                title = og.group(1)
    title = title.replace("\\u0026", "&").replace("&quot;", '"').replace("&#039;", "'")

    # === 提取公众号名称 ===
    nickname = "N/A"
    m = re.search(rb'var nickname = "(.*?)"', raw)
    if m:
        nickname = m.group(1).decode("utf-8", errors="replace")
    else:
        author = re.search(r'<meta property="og:article:author" content="(.*?)"', content)
        if author:
            nickname = author.group(1)

    # === 提取发布时间 ===
    publish_time = "N/A"
    m = re.search(r'var ct = "(\d+)";', content)
    if m:
        publish_time = datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d %H:%M:%S")
    else:
        pub = re.search(r'<meta property="og:article:published_time" content="(.*?)"', content)
        if pub:
            publish_time = pub.group(1)

    # === 提取正文（三级回退） ===
    body = None
    # 第一级：js_content div
    cm = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', content, re.DOTALL)
    if not cm:
        cm = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*</div>\s*<script', content, re.DOTALL)
    if cm:
        body_html = cm.group(1)
        images = extract_images_from_html(body_html, url)
        body = clean_html_to_text(body_html)

    # 第二级：OG description
    if not body or len(body) < 50:
        og_desc = re.search(r'<meta property="og:description" content="(.*?)"', content)
        if og_desc:
            body = html.unescape(og_desc.group(1)).replace("\\n", "\n").strip()
            if not images:
                images = []

    # 第三级：var msg_desc
    if not body or len(body) < 50:
        desc_match = re.search(r'var msg_desc = htmlDecode\("(.*?)"\);', content)
        if desc_match:
            body = desc_match.group(1)
        elif not body:
            body = "[无法提取正文，可能需要浏览器渲染]"

    # === 提取摘要 ===
    desc = "N/A"
    desc_match = re.search(r'var msg_desc = htmlDecode\("(.*?)"\);', content)
    if desc_match:
        desc = desc_match.group(1)
    else:
        og_desc = re.search(r'<meta property="og:description" content="(.*?)"', content)
        if og_desc:
            desc = og_desc.group(1)

    # === 提取封面图 ===
    cover = None
    og_img = re.search(r'<meta property="og:image" content="(.*?)"', content)
    if og_img:
        cover = og_img.group(1)

    images = images if "images" in dir() else []
    if cover and cover not in images:
        images.insert(0, cover)

    return {
        "title": title,
        "author": nickname,
        "publish_time": publish_time,
        "description": desc,
        "body": body,
        "images": images,
        "cover": cover,
        "pattern": pattern,
    }


# ============================================================
# 策略 2：Python requests + OG 元数据
# ============================================================

def fetch_with_requests(url, ua_key="wechat", cookie=None, proxy=None, retry=3, delay=2):
    """使用 Python requests 抓取 HTML，携带完整 Header"""
    if requests is None:
        return None, "requests库未安装"

    ua = USER_AGENTS.get(ua_key, UA_IOS_WECHAT)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if cookie:
        headers["Cookie"] = cookie
    if "mp.weixin.qq.com" in url:
        headers["Referer"] = "https://mp.weixin.qq.com/"

    proxies = {"http": proxy, "https": proxy} if proxy else None

    for attempt in range(retry):
        try:
            resp = requests.get(url, headers=headers, proxies=proxies, timeout=30)
            resp.raise_for_status()
            html_content = resp.text
            if is_captcha_page(html_content):
                return None, "触发微信验证码"
            return html_content, "ok"
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(delay)
            else:
                return None, f"requests异常: {e}"
    return None, "未知错误"


def parse_with_og_meta(html_content, url):
    """从 HTML 中提取 OG 元数据和正文（通用方案）"""
    # OG 元数据
    def get_og(prop):
        m = re.search(rf'<meta\s+property="og:{prop}"\s+content="(.*?)"', html_content, re.IGNORECASE)
        if not m:
            m = re.search(rf'<meta\s+content="(.*?)"\s+property="og:{prop}"', html_content, re.IGNORECASE)
        return m.group(1) if m else None

    title = get_og("title")
    if not title:
        t = re.search(r"<title>(.*?)</title>", html_content, re.DOTALL)
        title = t.group(1).strip() if t else "N/A"

    author = get_og("article:author") or "N/A"
    publish_time = get_og("article:published_time") or "N/A"
    description = get_og("description") or "N/A"
    cover = get_og("image")

    # 尝试提取正文
    body = None
    platform = detect_platform(url)

    # 使用平台特定选择器
    if BeautifulSoup and platform in PLATFORM_RULES:
        soup = BeautifulSoup(html_content, "html.parser")
        rules = PLATFORM_RULES[platform]
        content_elem = soup.select_one(rules["content"])
        if content_elem:
            body_html = str(content_elem)
            body = clean_html_to_text(body_html)
            images = extract_images_from_html(body_html, url)
        author_elem = soup.select_one(rules.get("author", ""))
        if author_elem:
            author = author_elem.get_text(strip=True)
        title_elem = soup.select_one(rules["title"])
        if title_elem:
            title = title_elem.get_text(strip=True)

    # 回退：从 body 标签提取
    if not body or len(body) < 50:
        if BeautifulSoup:
            soup = BeautifulSoup(html_content, "html.parser")
            body_elem = soup.find("body")
            if body_elem:
                body = clean_html_to_text(str(body_elem))
        else:
            # 无 BeautifulSoup，用正则
            body_match = re.search(r"<body[^>]*>(.*?)</body>", html_content, re.DOTALL)
            if body_match:
                body = clean_html_to_text(body_match.group(1))

    # 最终回退：OG description
    if not body or len(body) < 50:
        if description and description != "N/A":
            body = html.unescape(description)
        else:
            body = "[无法提取正文]"

    images = images if "images" in dir() else []
    if cover and cover not in images:
        images.insert(0, cover)

    return {
        "title": title,
        "author": author,
        "publish_time": publish_time,
        "description": description,
        "body": body,
        "images": images,
        "cover": cover,
        "pattern": "OG",
    }


# ============================================================
# 策略 3：完整脚本提取（平台特定 + readability 回退）
# ============================================================

def fetch_with_full_script(url, ua_key="chrome", cookie=None, proxy=None, retry=3, delay=2):
    """
    完整脚本提取：requests 获取 HTML + 平台特定 CSS 选择器精准提取 + readability 回退
    """
    html_content, msg = fetch_with_requests(url, ua_key, cookie, proxy, retry, delay)
    if html_content is None:
        return None, msg

    platform = detect_platform(url)

    # 微信公众号走专用解析
    if platform == "mp.weixin.qq.com":
        raw_bytes = html_content.encode("utf-8")
        result = parse_wechat_article(raw_bytes, url)
        result["strategy"] = "full_script"
        return result, "ok"

    # 其他平台：平台特定提取
    if BeautifulSoup and platform in PLATFORM_RULES:
        soup = BeautifulSoup(html_content, "html.parser")
        rules = PLATFORM_RULES[platform]

        title_elem = soup.select_one(rules["title"])
        content_elem = soup.select_one(rules["content"])
        author_elem = soup.select_one(rules.get("author", ""))

        if content_elem:
            body_html = str(content_elem)
            body = clean_html_to_text(body_html)
            images = extract_images_from_html(body_html, url)

            return {
                "title": title_elem.get_text(strip=True) if title_elem else "N/A",
                "author": author_elem.get_text(strip=True) if author_elem else "N/A",
                "publish_time": "N/A",
                "description": "N/A",
                "body": body,
                "images": images,
                "cover": None,
                "pattern": "platform_css",
                "strategy": "full_script",
            }, "ok"

    # readability 回退
    try:
        from readability import Document
        doc = Document(html_content)
        body_html = doc.summary()
        body = clean_html_to_text(body_html)
        return {
            "title": doc.title(),
            "author": "N/A",
            "publish_time": "N/A",
            "description": "N/A",
            "body": body,
            "images": extract_images_from_html(body_html, url),
            "cover": None,
            "pattern": "readability",
            "strategy": "full_script",
        }, "ok"
    except ImportError:
        # 最终回退到 OG meta 方案
        result = parse_with_og_meta(html_content, url)
        result["strategy"] = "full_script"
        return result, "ok"


# ============================================================
# 图片下载
# ============================================================

def download_images(images, output_dir, url=""):
    """下载图片列表到指定目录"""
    if not images:
        return []
    if not requests:
        return []
    os.makedirs(output_dir, exist_ok=True)
    downloaded = []
    for i, img_url in enumerate(images):
        if not img_url.startswith("http"):
            continue
        try:
            ext = ".jpg"
            if ".png" in img_url:
                ext = ".png"
            elif ".gif" in img_url:
                ext = ".gif"
            elif ".webp" in img_url:
                ext = ".webp"
            filename = f"image_{i:03d}{ext}"
            filepath = os.path.join(output_dir, filename)
            resp = requests.get(img_url, timeout=15, headers={"User-Agent": UA_CHROME})
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            downloaded.append(filepath)
        except Exception:
            pass
    return downloaded


# ============================================================
# 级联调度器
# ============================================================

def fetch_article(url, strategy="auto", ua_key=None, cookie=None, proxy=None,
                  retry=3, delay=2, download_images_flag=False, image_dir="./images"):
    """
    级联抓取文章
    策略优先级：curl → requests → full_script
    """
    platform = detect_platform(url)
    if ua_key is None:
        ua_key = "wechat" if platform == "mp.weixin.qq.com" else "chrome"

    strategies = []
    if strategy == "auto":
        strategies = ["curl", "requests", "full_script"]
    else:
        strategies = [strategy]

    last_error = ""
    for strat in strategies:
        try:
            if strat == "curl":
                html_content, msg = fetch_with_curl(url, ua_key)
                if html_content is None:
                    last_error = msg
                    continue
                if platform == "mp.weixin.qq.com":
                    raw_bytes = html_content.encode("utf-8")
                    result = parse_wechat_article(raw_bytes, url)
                else:
                    result = parse_with_og_meta(html_content, url)
                result["strategy"] = "curl"

            elif strat == "requests":
                html_content, msg = fetch_with_requests(url, ua_key, cookie, proxy, retry, delay)
                if html_content is None:
                    last_error = msg
                    continue
                if platform == "mp.weixin.qq.com":
                    raw_bytes = html_content.encode("utf-8")
                    result = parse_wechat_article(raw_bytes, url)
                else:
                    result = parse_with_og_meta(html_content, url)
                result["strategy"] = "requests"

            elif strat == "full_script":
                result, msg = fetch_with_full_script(url, ua_key, cookie, proxy, retry, delay)
                if result is None:
                    last_error = msg
                    continue

            else:
                last_error = f"未知策略: {strat}"
                continue

            # 检查正文质量
            body_len = len(result.get("body", ""))
            if body_len > 100:
                result["success"] = True
                result["url"] = url
                result["platform"] = platform
                result["body_length"] = body_len
                result["error"] = None

                # 下载图片
                if download_images_flag and result.get("images"):
                    result["downloaded_images"] = download_images(
                        result["images"], image_dir, url
                    )
                return result
            else:
                last_error = f"策略{strat}正文过短({body_len}字符)"
                continue

        except Exception as e:
            last_error = f"策略{strat}异常: {e}"
            continue

    return {
        "success": False,
        "strategy": None,
        "url": url,
        "platform": platform,
        "title": "N/A",
        "author": "N/A",
        "publish_time": "N/A",
        "description": "N/A",
        "body": "",
        "images": [],
        "cover": None,
        "pattern": None,
        "body_length": 0,
        "error": last_error,
    }


# ============================================================
# 输出格式化
# ============================================================

def to_markdown(result):
    """将结果转为 Markdown 格式"""
    md = f"# {result['title']}\n\n"
    md += f"> 来源：{result['url']}\n"
    md += f"> 作者：{result.get('author', 'N/A')}\n"
    if result.get("publish_time") and result["publish_time"] != "N/A":
        md += f"> 发布时间：{result['publish_time']}\n"
    if result.get("strategy"):
        md += f"> 抓取策略：{result['strategy']}"
        if result.get("pattern"):
            md += f"（模式{result['pattern']}）"
        md += "\n"
    md += "\n---\n\n"
    md += result.get("body", "")
    return md


def to_json(result):
    """将结果转为 JSON 格式"""
    return json.dumps(result, ensure_ascii=False, indent=2)


def to_text(result):
    """将结果转为纯文本格式"""
    lines = []
    lines.append(f"标题: {result['title']}")
    lines.append(f"作者: {result.get('author', 'N/A')}")
    if result.get("publish_time") and result["publish_time"] != "N/A":
        lines.append(f"发布时间: {result['publish_time']}")
    if result.get("strategy"):
        lines.append(f"抓取策略: {result['strategy']}")
    lines.append(f"正文长度: {result.get('body_length', 0)} 字符")
    lines.append("---")
    lines.append(result.get("body", ""))
    return "\n".join(lines)


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="统一文章抓取器 — 多策略级联 (curl → requests → full_script)"
    )
    parser.add_argument("--url", required=True, help="文章 URL")
    parser.add_argument("--strategy", default="auto",
                        choices=["auto", "curl", "requests", "full_script"],
                        help="抓取策略（默认 auto 级联）")
    parser.add_argument("--ua", default=None,
                        choices=["wechat", "ios", "chrome", "firefox"],
                        help="User-Agent 类型（默认按平台自动选择）")
    parser.add_argument("--cookie", default=None, help="Cookie 字符串")
    parser.add_argument("--proxy", default=None, help="代理地址 (http://host:port)")
    parser.add_argument("--retry", type=int, default=3, help="重试次数")
    parser.add_argument("--delay", type=int, default=2, help="重试间隔（秒）")
    parser.add_argument("--format", default="markdown",
                        choices=["markdown", "json", "text"],
                        help="输出格式")
    parser.add_argument("--download-images", action="store_true", help="下载文章图片")
    parser.add_argument("--image-dir", default="./images", help="图片下载目录")
    parser.add_argument("--output", default=None, help="输出文件路径（不指定则打印到终端）")

    args = parser.parse_args()

    result = fetch_article(
        url=args.url,
        strategy=args.strategy,
        ua_key=args.ua,
        cookie=args.cookie,
        proxy=args.proxy,
        retry=args.retry,
        delay=args.delay,
        download_images_flag=args.download_images,
        image_dir=args.image_dir,
    )

    if args.format == "markdown":
        output = to_markdown(result)
    elif args.format == "json":
        output = to_json(result)
    else:
        output = to_text(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已保存到: {args.output}", file=sys.stderr)
    else:
        print(output)

    # 错误信息输出到 stderr
    if not result["success"]:
        print(f"\n[ERROR] 所有策略失败: {result['error']}", file=sys.stderr)
        print("建议: 尝试使用 agent-browser 浏览器方案（策略4）", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
