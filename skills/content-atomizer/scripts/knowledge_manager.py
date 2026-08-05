#!/usr/bin/env python3
"""
内容知识原子化器 - 知识库管理脚本
支持 URL 内容获取、知识页存储、全文搜索、知识图谱查看。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from coze_workload_identity import requests

# 知识库根目录（默认在当前工作目录下）
KB_DIR = Path(os.environ.get("KNOWLEDGE_BASE_DIR", "knowledge_base"))
SUMMARIES_DIR = KB_DIR / "summaries"
ENTITIES_DIR = KB_DIR / "entities"
CONCEPTS_DIR = KB_DIR / "concepts"
INDEX_FILE = KB_DIR / "index.json"
RELATIONSHIPS_FILE = KB_DIR / "relationships.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def init_kb():
    """初始化知识库目录结构"""
    for d in [KB_DIR, SUMMARIES_DIR, ENTITIES_DIR, CONCEPTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        write_json(INDEX_FILE, {"pages": [], "next_id": 1})
    if not RELATIONSHIPS_FILE.exists():
        write_json(RELATIONSHIPS_FILE, {"nodes": [], "edges": []})


def read_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(title: str) -> str:
    """将标题转为文件名安全的 slug"""
    slug = re.sub(r'[<>:"/\\|?*\s]+', '_', title.strip())
    slug = re.sub(r'[^\w\u4e00-\u9fff\-_]', '', slug)
    return slug[:60] if slug else "untitled"


def parse_frontmatter(content: str) -> tuple:
    """解析 YAML frontmatter，返回 (metadata_dict, body_text)"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm_text = parts[1].strip()
    body = parts[2].strip()

    meta = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # 解析列表
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            meta[key] = val

    return meta, body


def build_frontmatter(meta: dict) -> str:
    """构建 YAML frontmatter"""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            val_str = "[" + ", ".join(f'"{item}"' for item in v) + "]"
        else:
            val_str = f'"{v}"'
        lines.append(f"{k}: {val_str}")
    lines.append("---")
    return "\n".join(lines)


def fetch_url_content(url: str) -> str:
    """获取 URL 内容并提取正文文本"""
    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"

    soup = BeautifulSoup(resp.text, "lxml")

    # 移除不需要的元素
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # 尝试找到主要内容区域
    content = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
        or soup.find("body")
        or soup
    )

    # 提取标题
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.find("title"):
        title = soup.find("title").get_text(strip=True)

    # 转为文本
    text = content.get_text(separator="\n", strip=True) if content else ""

    # 清理多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    result = f"# {title}\n\n来源: {url}\n获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{text}"
    return result


def store_page(page_type: str, title: str, content: str, tags: str = "",
               aliases: str = "", source: str = "") -> str:
    """存储一个知识页，如果同名已存在则合并"""
    init_kb()

    slug = slugify(title)
    type_dir = {
        "summary": SUMMARIES_DIR,
        "entity": ENTITIES_DIR,
        "concept": CONCEPTS_DIR,
    }.get(page_type, ENTITIES_DIR)

    filepath = type_dir / f"{slug}.md"

    # 检查是否已存在
    if filepath.exists():
        existing = filepath.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(existing)

        # 合并：更新 mentions 计数，添加新来源，追加内容
        mentions = int(meta.get("mentions", 1)) + 1
        meta["mentions"] = mentions
        meta["updated"] = datetime.now().strftime("%Y-%m-%d")

        if source:
            sources = meta.get("sources", [])
            if isinstance(sources, str):
                sources = [sources]
            if source not in sources:
                sources.append(source)
            meta["sources"] = sources

        if tags:
            existing_tags = meta.get("tags", [])
            if isinstance(existing_tags, str):
                existing_tags = [existing_tags]
            new_tags = [t.strip() for t in tags.split(",") if t.strip()]
            meta["tags"] = list(set(existing_tags + new_tags))

        merged = build_frontmatter(meta) + "\n\n" + body
        if content.strip():
            merged += f"\n\n---\n\n## 更新 ({datetime.now().strftime('%Y-%m-%d')})\n\n{content}"

        filepath.write_text(merged, encoding="utf-8")
        print(f"✅ 已更新: {filepath.name} (mentions: {mentions})")
        return str(filepath)
    else:
        # 新建
        index = read_json(INDEX_FILE)
        page_id = index.get("next_id", 1)
        index["next_id"] = page_id + 1

        meta = {
            "type": page_type,
            "title": title,
            "id": f"{page_id:04d}",
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
            "aliases": [a.strip() for a in aliases.split(",") if a.strip()] if aliases else [],
            "sources": [source] if source else [],
            "created": datetime.now().strftime("%Y-%m-%d"),
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "mentions": 1,
        }

        page_content = build_frontmatter(meta) + "\n\n" + content
        filepath.write_text(page_content, encoding="utf-8")

        # 更新索引
        index_entry = {
            "id": f"{page_id:04d}",
            "type": page_type,
            "title": title,
            "slug": slug,
            "file": str(filepath.relative_to(KB_DIR)),
            "tags": meta["tags"],
            "created": meta["created"],
            "mentions": 1,
        }
        index.setdefault("pages", []).append(index_entry)
        write_json(INDEX_FILE, index)

        # 更新关系图
        update_relationships(title, page_type, content)

        print(f"✅ 已创建: {filepath.name} (id: {page_id:04d})")
        return str(filepath)


def update_relationships(title: str, page_type: str, content: str):
    """从内容中提取 wiki 链接，更新关系图"""
    rel = read_json(RELATIONSHIPS_FILE)

    # 添加节点（如果不存在）
    node_exists = any(n.get("title") == title for n in rel.get("nodes", []))
    if not node_exists:
        rel.setdefault("nodes", []).append({
            "title": title,
            "type": page_type,
        })

    # 提取 [[wiki-links]]
    wiki_links = re.findall(r'\[\[([^\]]+)\]\]', content)
    for link in wiki_links:
        link = link.strip()
        # 确保目标节点存在
        if not any(n.get("title") == link for n in rel.get("nodes", [])):
            rel.setdefault("nodes", []).append({"title": link, "type": "unknown"})

        # 添加边（如果不存在）
        edge = {"source": title, "target": link}
        if edge not in rel.get("edges", []):
            rel.setdefault("edges", []).append(edge)

    write_json(RELATIONSHIPS_FILE, rel)


def search_pages(query: str, limit: int = 10) -> list:
    """全文搜索知识库"""
    init_kb()
    results = []
    query_lower = query.lower()

    for page_file in KB_DIR.rglob("*.md"):
        content = page_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)

        # 计算匹配分数
        score = 0
        title = meta.get("title", page_file.stem)

        # 标题匹配权重高
        if query_lower in title.lower():
            score += 10

        # 标签匹配
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            if query_lower in tag.lower():
                score += 5

        # 正文匹配
        body_lower = body.lower()
        count = body_lower.count(query_lower)
        score += count

        # 别名匹配
        aliases = meta.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        for alias in aliases:
            if query_lower in alias.lower():
                score += 8

        if score > 0:
            results.append({
                "title": title,
                "type": meta.get("type", "unknown"),
                "score": score,
                "mentions": meta.get("mentions", 1),
                "file": str(page_file.relative_to(KB_DIR)),
                "tags": tags if isinstance(tags, list) else [tags],
                "snippet": body[:200] + "..." if len(body) > 200 else body,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def list_pages() -> list:
    """列出所有知识页"""
    init_kb()
    index = read_json(INDEX_FILE)
    return index.get("pages", [])


def show_graph() -> dict:
    """返回知识图谱数据"""
    init_kb()
    return read_json(RELATIONSHIPS_FILE)


def recommend(project_desc: str) -> list:
    """基于知识库内容给出推荐"""
    init_kb()
    # 简单实现：搜索与项目描述相关的页面
    keywords = re.findall(r'[\w\u4e00-\u9fff]+', project_desc)
    all_results = []
    for kw in keywords:
        if len(kw) < 2:
            continue
        results = search_pages(kw, limit=5)
        for r in results:
            if r not in all_results:
                all_results.append(r)

    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:15]


def main():
    parser = argparse.ArgumentParser(description="内容知识原子化器 - 知识库管理")
    sub = parser.add_subparsers(dest="command")

    # fetch
    p_fetch = sub.add_parser("fetch", help="获取URL内容")
    p_fetch.add_argument("url", help="要获取的URL")

    # store
    p_store = sub.add_parser("store", help="存储知识页")
    p_store.add_argument("--type", required=True, choices=["summary", "entity", "concept"])
    p_store.add_argument("--title", required=True)
    p_store.add_argument("--content", default="", help="知识页内容")
    p_store.add_argument("--content-file", help="从文件读取内容")
    p_store.add_argument("--tags", default="")
    p_store.add_argument("--aliases", default="")
    p_store.add_argument("--source", default="")

    # search
    p_search = sub.add_parser("search", help="搜索知识库")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)

    # list
    sub.add_parser("list", help="列出所有知识页")

    # graph
    sub.add_parser("graph", help="查看知识图谱")

    # recommend
    p_rec = sub.add_parser("recommend", help="基于知识库推荐")
    p_rec.add_argument("description")

    args = parser.parse_args()

    if args.command == "fetch":
        print(f"📥 获取URL内容: {args.url}")
        content = fetch_url_content(args.url)
        print(content[:1000])
        if len(content) > 1000:
            print(f"\n... (完整内容 {len(content)} 字符)")

    elif args.command == "store":
        content = args.content
        if args.content_file:
            content = Path(args.content_file).read_text(encoding="utf-8")
        if not content:
            print("❌ 请提供 --content 或 --content-file", file=sys.stderr)
            sys.exit(1)
        store_page(args.type, args.title, content, args.tags, args.aliases, args.source)

    elif args.command == "search":
        results = search_pages(args.query, args.limit)
        if not results:
            print("🔍 未找到匹配的知识页")
        else:
            print(f"🔍 找到 {len(results)} 个结果:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. [{r['type']}] {r['title']} (score: {r['score']}, mentions: {r['mentions']})")
                print(f"   标签: {', '.join(r['tags'])}")
                print(f"   摘要: {r['snippet'][:100]}...")
                print()

    elif args.command == "list":
        pages = list_pages()
        if not pages:
            print("📚 知识库为空")
        else:
            print(f"📚 知识库共 {len(pages)} 个页面:\n")
            by_type = {}
            for p in pages:
                by_type.setdefault(p["type"], []).append(p)
            for ptype, pgroup in by_type.items():
                print(f"## {ptype} ({len(pgroup)})")
                for p in pgroup:
                    print(f"  - [{p['id']}] {p['title']} (mentions: {p.get('mentions', 1)})")
                print()

    elif args.command == "graph":
        graph = show_graph()
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        print(f"🕸️  知识图谱: {len(nodes)} 个节点, {len(edges)} 条关系\n")
        if edges:
            print("关系:")
            for e in edges[:50]:
                print(f"  {e['source']} → {e['target']}")
            if len(edges) > 50:
                print(f"  ... (共 {len(edges)} 条)")

    elif args.command == "recommend":
        results = recommend(args.description)
        if not results:
            print("💡 知识库中暂无相关内容，建议先添加更多来源")
        else:
            print(f"💡 基于知识库的推荐 (共 {len(results)} 项):\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. [{r['type']}] {r['title']} (score: {r['score']})")
                print(f"   {r['snippet'][:100]}...")
                print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
