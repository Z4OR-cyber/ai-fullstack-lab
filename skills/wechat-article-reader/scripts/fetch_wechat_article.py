#!/usr/bin/env python3
"""
微信公众号文章阅读器
基于 weixin-articles-mcp 和 wechat-article-downloader 的核心逻辑改写。
使用浏览器 UA 请求公开文章页面，不涉及登录或绕过反爬。
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md

# 必须使用 coze_workload_identity 的 requests
from coze_workload_identity import requests

# 浏览器 User-Agent
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.43(0x18002b2f) NetType/WIFI Language/zh_CN"
)

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

MAX_IMAGES = 10
REQUEST_TIMEOUT = 30
RATE_LIMIT_SEC = 1.0


def fetch_article_html(url: str) -> str:
    """请求微信文章页面，返回 HTML 文本"""
    headers = {
        "User-Agent": UA_MOBILE,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        # 微信页面通常是 utf-8
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        raise RuntimeError(f"请求微信文章失败: {e}")


def extract_metadata(soup: BeautifulSoup, html: str) -> dict:
    """从 HTML 中提取文章元数据"""
    meta = {}

    # 标题: <h1 id="activity-name"> 或 og:title
    title_tag = soup.find("h1", id="activity-name")
    if title_tag:
        meta["title"] = title_tag.get_text(strip=True)
    else:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            meta["title"] = og_title.get("content", "").strip()
        else:
            title_tag = soup.find("title")
            if title_tag:
                meta["title"] = title_tag.get_text(strip=True)

    # 作者/公众号名: <a id="js_name"> 或 og:nickname
    author_tag = soup.find("a", id="js_name")
    if author_tag:
        meta["author"] = author_tag.get_text(strip=True)
    else:
        og_nick = soup.find("meta", property="og:nickname")
        if og_nick:
            meta["author"] = og_nick.get("content", "").strip()

    # 发布时间: var ct = "1234567890" 或 <em id="publish_time">
    ct_match = re.search(r'var\s+ct\s*=\s*["\'](\d+)["\']', html)
    if ct_match:
        ts = int(ct_match.group(1))
        tz_sh = timezone(timedelta(hours=8))
        meta["publish_time"] = datetime.fromtimestamp(ts, tz_sh).strftime("%Y-%m-%d %H:%M:%S")
    else:
        pub_tag = soup.find("em", id="publish_time")
        if pub_tag:
            meta["publish_time"] = pub_tag.get_text(strip=True)

    # 描述
    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        meta["description"] = og_desc.get("content", "").strip()

    return meta


def extract_content(soup: BeautifulSoup) -> BeautifulSoup:
    """提取文章正文区域"""
    content = soup.find("div", id="js_content")
    if not content:
        # 尝试其他选择器
        content = soup.find("div", class_="rich_media_content")
    if not content:
        content = soup.find("div", id="page-content")
    return content


def extract_images(content: BeautifulSoup, base_url: str) -> list:
    """提取文章中的图片 URL"""
    images = []
    seen = set()

    for img in content.find_all("img"):
        # 微信图片常用 data-src 懒加载
        src = img.get("data-src") or img.get("src") or ""
        if not src or not src.startswith("http"):
            continue

        # 过滤 GIF 和非图片资源
        if ".gif" in src.lower():
            continue

        # 去重
        if src in seen:
            continue
        seen.add(src)

        images.append(src)
        if len(images) >= MAX_IMAGES:
            break

    return images


def extract_videos(content: BeautifulSoup, html: str) -> list:
    """提取视频信息"""
    videos = []

    # 1. 微信原生视频: <iframe data-mpvid="wxv_*">
    for iframe in content.find_all("iframe"):
        mpvid = iframe.get("data-mpvid", "")
        if mpvid and mpvid.startswith("wxv_"):
            videos.append({
                "type": "wechat_native",
                "id": mpvid,
                "src": iframe.get("data-src", ""),
            })

        # 2. 腾讯视频
        src = iframe.get("data-src") or iframe.get("src") or ""
        if "v.qq.com" in src:
            vid_match = re.search(r'/([a-zA-Z0-9]+)\.html', src)
            videos.append({
                "type": "tencent_video",
                "vid": vid_match.group(1) if vid_match else "",
                "src": src,
            })

    # 3. 视频号: <mp-common-videosnap>
    for snap in content.find_all("mp-common-videosnap"):
        video_info = {
            "type": "wechat_channels",
            "data_id": snap.get("data-id", ""),
        }

        # 从 data 属性提取元数据
        desc = snap.get("data-desc", "")
        if desc:
            video_info["description"] = desc

        duration = snap.get("data-duration", "")
        if duration:
            try:
                secs = int(duration)
                video_info["duration"] = f"{secs // 60}:{secs % 60:02d}"
            except ValueError:
                video_info["duration"] = duration

        like_count = snap.get("data-like-count", snap.get("data-likecount", ""))
        if like_count:
            video_info["likes"] = like_count

        cover = snap.get("data-cover", snap.get("data-poster", ""))
        if cover:
            video_info["cover_url"] = cover

        videos.append(video_info)

    # 4. 从内联 JS 提取视频号元数据 (batch_get_video_snap 响应)
    snap_match = re.search(
        r'batch_get_video_snap.*?desc.*?["\']([^"\']+)', html, re.DOTALL
    )
    if snap_match:
        # 避免重复添加
        if not any(v["type"] == "wechat_channels" for v in videos):
            videos.append({
                "type": "wechat_channels",
                "description": snap_match.group(1),
            })

    return videos


def download_image(url: str, output_dir: Path, index: int) -> str:
    """下载单张图片，返回本地文件名"""
    # 从 URL 推断扩展名
    parsed = urlparse(url)
    ext = ".jpg"
    path_lower = parsed.path.lower()
    if ".png" in path_lower:
        ext = ".png"
    elif ".webp" in path_lower:
        ext = ".webp"
    elif ".jpeg" in path_lower:
        ext = ".jpeg"

    filename = f"{index:02d}_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
    filepath = output_dir / filename

    try:
        headers = {"User-Agent": UA_DESKTOP, "Referer": "https://mp.weixin.qq.com/"}
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(resp.content)

        return filename
    except Exception as e:
        print(f"  [警告] 图片下载失败 ({url[:60]}...): {e}", file=sys.stderr)
        return ""


def content_to_markdown(content: BeautifulSoup, images: list, image_names: list, videos: list) -> str:
    """将文章内容转为 Markdown"""
    # 处理图片：替换为带编号的占位符
    img_idx = 0
    for img in content.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        if src in images and img_idx < len(image_names):
            if image_names[img_idx]:
                img["src"] = f"images/{image_names[img_idx]}"
                img["alt"] = f"图{img_idx + 1}"
                del img["data-src"]
            img_idx += 1
        else:
            # 非目标图片，保留 URL
            if src:
                img["src"] = src

    # 处理视频：替换为引用块
    for iframe in content.find_all("iframe"):
        mpvid = iframe.get("data-mpvid", "")
        src = iframe.get("data-src") or iframe.get("src") or ""

        if mpvid and mpvid.startswith("wxv_"):
            iframe.replace_with(
                BeautifulSoup(
                    f'<blockquote><p>📹 微信原生视频 ({mpvid})</p></blockquote>', "html.parser"
                )
            )
        elif "v.qq.com" in src:
            iframe.replace_with(
                BeautifulSoup(
                    f'<blockquote><p>📹 腾讯视频 (<a href="{src}">链接</a>)</p></blockquote>',
                    "html.parser",
                )
            )

    for snap in content.find_all("mp-common-videosnap"):
        desc = snap.get("data-desc", "")
        duration = snap.get("data-duration", "")
        dur_str = ""
        if duration:
            try:
                secs = int(duration)
                dur_str = f"时长: {secs // 60}:{secs % 60:02d} | "
            except ValueError:
                pass
        snap.replace_with(
            BeautifulSoup(
                f'<blockquote><p>📹 视频号视频 | {dur_str}描述: {desc}</p></blockquote>',
                "html.parser",
            )
        )

    # 转为 Markdown
    markdown = md(str(content), heading_style="ATX")

    # 清理多余空行
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)

    # 添加视频摘要
    if videos:
        markdown += "\n\n---\n\n## 📹 视频摘要\n\n"
        for i, v in enumerate(videos, 1):
            vtype = {
                "wechat_native": "微信原生视频",
                "tencent_video": "腾讯视频",
                "wechat_channels": "视频号视频",
            }.get(v["type"], v["type"])
            details = []
            for k, val in v.items():
                if k not in ("type",):
                    details.append(f"{k}: {val}")
            markdown += f"{i}. **{vtype}** — {' | '.join(details)}\n"

    return markdown.strip()


def fetch_wechat_article(url: str, output_dir: str = ".", download_images: bool = True) -> str:
    """主函数：抓取微信文章并返回 Markdown"""

    if "mp.weixin.qq.com" not in url:
        raise ValueError(f"URL 不是微信公众号文章: {url}")

    print(f"📥 正在抓取文章: {url}")

    # 创建输出目录
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 请求文章
    html = fetch_article_html(url)
    print(f"✅ 页面获取成功 ({len(html)} bytes)")

    # 解析
    soup = BeautifulSoup(html, "lxml")
    meta = extract_metadata(soup, html)
    content = extract_content(soup)

    if not content:
        raise RuntimeError("无法提取文章正文，可能页面结构已变更或文章已被删除")

    # 提取图片
    image_urls = extract_images(content, url)
    print(f"🖼️  发现 {len(image_urls)} 张图片")

    # 下载图片
    image_names = []
    if download_images and image_urls:
        img_dir = out_path / "images"
        img_dir.mkdir(exist_ok=True)
        for i, img_url in enumerate(image_urls):
            print(f"  下载图片 {i + 1}/{len(image_urls)}...", end=" ")
            name = download_image(img_url, img_dir, i)
            image_names.append(name)
            if name:
                print(f"✅ {name}")
            else:
                print("❌")
            time.sleep(RATE_LIMIT_SEC)
    else:
        image_names = [""] * len(image_urls)

    # 提取视频
    videos = extract_videos(content, html)
    if videos:
        print(f"📹 发现 {len(videos)} 个视频")

    # 转为 Markdown
    markdown_body = content_to_markdown(content, image_urls, image_names, videos)

    # 构建 YAML frontmatter
    meta_yaml = ["---"]
    meta_yaml.append(f"title: \"{meta.get('title', '未知标题')}\"")
    if meta.get("author"):
        meta_yaml.append(f"author: \"{meta['author']}\"")
    if meta.get("publish_time"):
        meta_yaml.append(f"publish_time: \"{meta['publish_time']}\"")
    if meta.get("description"):
        meta_yaml.append(f"description: \"{meta['description']}\"")
    meta_yaml.append(f"source_url: \"{url}\"")
    meta_yaml.append(f"fetched_at: \"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\"")
    meta_yaml.append("---")

    result = "\n".join(meta_yaml) + "\n\n" + markdown_body

    # 保存到文件
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', meta.get("title", "article"))[:50]
    output_file = out_path / f"{safe_title}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"\n📄 文章已保存: {output_file}")
    print(f"📊 统计: {len(image_urls)} 张图片, {len(videos)} 个视频, {len(result)} 字符")

    return result


def main():
    parser = argparse.ArgumentParser(description="微信公众号文章阅读器")
    parser.add_argument("url", help="微信公众号文章 URL")
    parser.add_argument("-o", "--output", default=".", help="输出目录")
    parser.add_argument("--no-images", action="store_true", help="不下载图片")

    args = parser.parse_args()

    try:
        result = fetch_wechat_article(
            url=args.url,
            output_dir=args.output,
            download_images=not args.no_images,
        )
        print("\n" + "=" * 60)
        print("文章内容预览（前 500 字符）:")
        print("=" * 60)
        print(result[:500])
        if len(result) > 500:
            print("\n... (完整内容已保存到文件)")

    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
