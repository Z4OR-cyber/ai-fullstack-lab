---
name: web-article-fetcher
description: 多级降级网页文章抓取工具，专门解决fetch_web失败场景。当用户分享微信公众号文章链接、fetch_web返回403/robots.txt/内容为空/plugin execute failed、需要抓取JS渲染页面、或提到文章抓取/网页内容提取/微信文章读取/公众号文章获取时使用。采用fetch_web→curl伪装UA双模式检测→agent-browser浏览器自动化→人工复制的四级降级策略，内置微信文章HTML双变体解析和验证码检测。
---

# 网页文章抓取器

多级降级的网页文章抓取方法论，优先用最轻量方案，逐步升级到浏览器自动化。

## 核心流程

```
用户给URL
  ↓
Level 1: fetch_web（工具直读，最轻量）
  ↓ 失败（403/robots.txt/空内容/plugin execute failed）
Level 2: curl + 伪装UA（主session可直接执行，~3秒）
  ↓ 失败（验证码/登录墙/JS渲染内容拿不到）
Level 3: agent-browser（sessions_spawn子session，~15秒）
  ↓ 失败（验证码需人工介入）
Level 4: 请用户手动复制内容
```

**原则**：越轻量越优先，不要一上来就用浏览器。

## Level 2: curl方案（最常用）

### 微信文章抓取命令

```bash
curl -sL -o /tmp/article.html \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.42(0x18002a2c) NetType/WIFI Language/zh_CN" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: zh-CN,zh;q=0.9" \
  -H "Referer: https://mp.weixin.qq.com/" \
  "<URL>"
```

关键点：使用 **iPhone MicroMessenger UA** 可绕过robots.txt限制，这是经过实战验证的方案。

### 验证码检测

```bash
if grep -q "wappoc_appmsgcaptcha" /tmp/article.html 2>/dev/null; then
    echo "CAPTCHA_DETECTED: 需升级到浏览器方案"
fi
```

### 微信文章双模式解析

微信文章HTML有两种结构变体，解析时依次尝试：

| 模式 | 标题变量 | 正文位置 |
|------|---------|---------|
| A | `var msg_title = 'xxx'` | `id="js_content"` div |
| B | `window.msg_title = window.title = 'xxx'` | 可能不在js_content，需OG回退 |

**模式B三级回退**：js_content失败时依次尝试：
1. `<meta property="og:description" content="xxx" />`
2. `<meta name="description" content="xxx" />`
3. `var msg_desc = htmlDecode("xxx");`

### Python解析脚本

```python
import re, html

with open('/tmp/article.html', 'rb') as f:
    raw = f.read()
content = raw.decode('utf-8', errors='replace')

# 标题：模式A→模式B→OG
title_match = re.search(rb"var msg_title = '(.*?)'", raw)
if title_match:
    title = title_match.group(1).decode('utf-8')
else:
    title_match = re.search(rb"window\.msg_title = window\.title = '(.*?)'", raw)
    title = title_match.group(1).decode('utf-8') if title_match else 'N/A'
    if not title_match:
        og = re.search(r'<meta property="og:title" content="(.*?)"', content)
        title = og.group(1) if og else 'N/A'

# 正文：js_content div
body_match = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', content, re.DOTALL)
if body_match:
    body = re.sub(r'<[^>]+>', '\n', body_match.group(1))
    body = html.unescape(body)
    body = re.sub(r'\n{3,}', '\n\n', body).strip()
else:
    # 回退到OG description
    og_desc = re.search(r'<meta property="og:description" content="(.*?)"', content)
    body = og_desc.group(1) if og_desc else '正文提取失败，需浏览器方案'

print(f"标题: {title}\n\n{body}")
```

### 非微信网站

对于一般网站，同样用curl+UA抓取后，用通用HTML清理：
```python
import re, html
# 去掉script/style
text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', content, flags=re.DOTALL)
text = re.sub(r'<[^>]+>', '\n', text)
text = html.unescape(text)
text = re.sub(r'\n{3,}', '\n\n', text).strip()
```

## Level 3: agent-browser方案

当curl方案失败（验证码/JS渲染/登录墙）时：

1. 通过 `sessions_spawn` 创建子session
2. 在子session中加载 `agent-browser` skill
3. 指令描述：打开URL、等待页面加载、提取正文文本
4. **注意**：agent-browser命令不能在主session直接执行，必须在子session中运行

子session task示例：
```
使用agent-browser打开 <URL>，等待页面完全加载后，
提取文章标题和正文全文（去除导航、广告、评论等非正文内容），
以纯文本格式返回。如果遇到验证码，停止并报告。
```

## Level 4: 人工兜底

如果以上方案均失败：
- 告知用户链接需要登录/验证码，无法自动抓取
- 请用户在浏览器中打开链接，复制正文内容粘贴回来
- 拿到内容后正常进行分析处理

## 注意事项

1. **不要用fetch_web失败的URL作为搜索关键词**——这违反工具使用规范
2. curl方案拿到的HTML可能很大（数百KB），用Python提取后只保留正文
3. 微信文章URL有时效性，过期链接可能返回"该内容已被发布者删除"
4. 部分网站有频率限制，不要短时间内反复请求同一URL
5. User-Agent是关键：微信文章必须用MicroMessenger UA，普通网站用Chrome UA即可
