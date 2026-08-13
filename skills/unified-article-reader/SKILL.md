---
name: unified-article-reader
description: 统一文章阅读器，整合多策略级联抓取方案。当用户分享文章链接、需要读取网页内容、抓取微信公众号文章、提取知乎/今日头条/掘金/CSDN等平台正文、读取被robots.txt拦截的页面时使用此技能。支持curl直抓、Python requests反爬、完整脚本提取、浏览器兜底四级策略级联，自动降级，支持图片下载和元数据提取。
---

# 统一文章阅读器 (Unified Article Reader)

整合4种抓取方案的多策略级联文章阅读器，覆盖微信公众号、知乎、今日头条、掘金、CSDN、Medium等主流平台。

## 核心能力

- **四级策略级联**：curl直抓 → Python requests+iOS微信UA → 完整脚本提取 → agent-browser浏览器兜底
- **自动降级**：按优先级依次尝试，前一级失败自动切换下一级，无需人工干预
- **多平台支持**：微信公众号、知乎专栏、今日头条、掘金、CSDN、Medium、通用网页
- **元数据提取**：标题、作者/公众号名、发布时间、摘要、封面图
- **图片下载**：可选下载文章内嵌图片到本地
- **双模式检测**：微信文章HTML两种结构变体自动识别（模式A/B + OG meta三级回退）
- **验证码检测**：自动检测微信验证码重定向，提前切换策略

## 策略级联详解

### 策略 1：curl 直抓（最快，~3秒）

**原理**：用 curl 模拟 iPhone 微信客户端 UA 直接请求 URL，微信服务器返回完整 HTML。

**适用场景**：
- 微信公众号文章（mp.weixin.qq.com）— 成功率约 95%
- 无 JS 渲染需求的静态页面
- 无需登录即可访问的公开页面

**失败条件**：
- 触发微信验证码（URL 含 `wappoc_appmsgcaptcha`）
- 文章被删除或设为仅关注者可见
- 目标站点强制 JS 渲染（SPA 应用）
- 需要登录态的内容（知乎专栏等）

**关键技术**：
- UA：`Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) ... MicroMessenger/8.0.42 ...`（模拟微信客户端）
- Referer：`https://mp.weixin.qq.com/`（模拟从微信内部跳转）
- 双模式HTML解析：模式A（`var msg_title`）→ 模式B（`window.msg_title`）→ OG meta回退

### 策略 2：Python requests + iOS 微信 UA（获取OG元数据，~5秒）

**原理**：用 Python requests 库发送请求，携带更完整的 Header 组合，可提取 OG（Open Graph）元数据。

**适用场景**：
- curl 成功但正文提取不完整（模式B文章）
- 需要提取 OG 元数据（og:title, og:description, og:image 等）
- 需要自定义 Cookie 或 Proxy 的场景
- 知乎、掘金、CSDN 等非微信平台

**失败条件**：
- 目标站点检测到非浏览器请求特征
- 需要 JS 执行后才能渲染的内容
- IP 被封禁（需更换代理）

**关键技术**：
- requests 库发送 GET 请求
- UA 轮换池（Chrome/Firefox/Safari/iOS微信）
- BeautifulSoup 解析 HTML
- OG meta 标签提取

### 策略 3：完整脚本提取（最全面，~8秒）

**原理**：在策略2基础上，使用平台特定 CSS 选择器精准提取正文，配合 readability 算法作为通用回退。

**适用场景**：
- 需要精准提取特定平台正文（而非全页文本）
- 正文被广告、导航、评论等噪音包裹
- 需要保留文章结构（标题层级、段落、代码块、引用块）

**失败条件**：
- 目标页面结构发生变更（CSS选择器失效）
- readability 库未安装（回退到策略2的简单提取）
- 页面完全由 JS 渲染

**关键技术**：
- 平台特定提取规则（PLATFORM_RULES 字典）
- readability-lxml 通用提取回退
- HTML → Markdown 转换

### 策略 4：agent-browser 浏览器兜底（最可靠，~15秒）

**原理**：启动真实浏览器（通过 agent-browser CLI），完全模拟用户访问行为。

**适用场景**：
- 前三级策略全部失败
- 需要 JS 渲染的 SPA 页面
- 需要登录的页面（用户可手动接管）
- 需要滚动加载的长文章

**失败条件**：
- 页面需要验证码且无法自动通过
- 需要用户登录但用户未配合
- 浏览器资源不可用（无云电脑/桌面设备）

**关键技术**：
- agent-browser open/wait/get text/scroll 命令
- browser_wait_user_action 用于登录场景
- 子 session 执行（sessions_spawn）

## 工作流程

### 步骤 1：平台识别

根据 URL 域名自动识别目标平台，选择最优策略组合：

| 平台 | 域名特征 | 首选策略 | 备注 |
|------|---------|---------|------|
| 微信公众号 | `mp.weixin.qq.com` | curl直抓 | robots.txt封锁，fetch_web必定失败 |
| 知乎专栏 | `zhuanlan.zhihu.com` | requests+Cookie | 需登录态 |
| 今日头条 | `toutiao.com` | curl直抓 | 通常可直接抓取 |
| 掌握 | `juejin.cn` | requests | 无需登录 |
| CSDN | `blog.csdn.net` | requests | 无需登录 |
| Medium | `medium.com` | requests+Cookie | 付费文章需Cookie |
| 通用网页 | 其他 | fetch_web优先 | 最轻量 |

### 步骤 2：执行级联抓取

使用统一脚本 `scripts/unified_fetch.py` 执行前三级策略：

```bash
# 自动级联（推荐）
python3 scripts/unified_fetch.py --url "https://mp.weixin.qq.com/s/xxxxx"

# 指定策略（调试用）
python3 scripts/unified_fetch.py --url "https://mp.weixin.qq.com/s/xxxxx" --strategy curl
python3 scripts/unified_fetch.py --url "https://zhuanlan.zhihu.com/p/xxx" --strategy requests

# 下载图片
python3 scripts/unified_fetch.py --url "https://mp.weixin.qq.com/s/xxxxx" --download-images --image-dir ./images

# 指定输出格式
python3 scripts/unified_fetch.py --url "https://example.com/article" --format json
python3 scripts/unified_fetch.py --url "https://example.com/article" --format markdown

# 带 Cookie（知乎等需登录平台）
python3 scripts/unified_fetch.py --url "https://zhuanlan.zhihu.com/p/xxx" --cookie "z_c0=xxx"

# 使用代理
python3 scripts/unified_fetch.py --url "https://example.com/article" --proxy "http://host:port"
```

### 步骤 3：判断结果

脚本输出 JSON 结果，包含 `success`、`strategy`、`pattern`、`title`、`author`、`publish_time`、`body`、`body_length` 等字段。

**判断逻辑**：
- `success: true` 且 `body_length > 100` → 抓取成功，进入步骤 4
- `success: true` 但 `body_length < 100` → 正文提取不完整，尝试下一级策略
- `success: false` → 当前策略失败，尝试下一级策略
- 所有脚本策略失败 → 进入步骤 4（浏览器兜底）

### 步骤 4：浏览器兜底（策略4）

当脚本级策略全部失败时，使用 agent-browser 浏览器抓取：

**重要：agent-browser 命令必须在子 session（sessions_spawn）中执行，不能在主 session 直接调用。**

```
sessions_spawn(
  agent="lead",
  name="浏览器抓取文章",
  task="使用 agent-browser 打开以下URL并提取完整正文内容：
    URL: <用户提供的URL>

    执行步骤：
    1. agent-browser open "<URL>" && agent-browser tab 0
    2. agent-browser wait --load networkidle
    3. agent-browser scroll down 3000   # 触发懒加载
    4. agent-browser wait 2000
    5. agent-browser get title          # 获取页面标题
    6. agent-browser get text body      # 获取正文内容

    将获取到的标题和完整正文内容原样返回，不要总结或删减。
    如果页面需要登录，使用 browser_wait_user_action 等待用户接管。"
)
```

### 步骤 5：正文清洗与输出

无论通过哪种策略获取到原始内容，统一进行以下清洗：

1. **提取标题**：从页面标题或 JS 变量提取
2. **提取作者**：从平台特定元素或 OG meta 提取
3. **提取发布时间**：从时间戳或 meta 标签提取
4. **去除噪音**：移除广告、导航、"阅读原文"、点赞按钮、"相关阅读"等
5. **保留结构**：保留标题层级、段落分隔、代码块、引用块

输出格式：

```markdown
# {文章标题}

> 来源：{URL}
> 作者：{作者/公众号名}
> 发布时间：{发布时间}
> 抓取策略：{使用的策略名称}

{正文内容}
```

## 各平台特殊处理

### 微信公众号 (mp.weixin.qq.com)

- **几乎总是被 robots.txt 拦截**，fetch_web 必定失败，跳过直接用 curl
- 正文在 `#js_content` 元素中（模式A）
- 标题在 `var msg_title` 或 `window.msg_title` 变量中
- 作者（公众号名）在 `var nickname` 变量中
- 图片使用 `data-src` 懒加载，curl 方案无法直接获取
- 双模式检测：模式A（`var msg_title`）→ 模式B（`window.msg_title` + OG description 回退）
- 验证码检测：检查 HTML 是否含 `wappoc_appmsgcaptcha`

### 知乎专栏 (zhuanlan.zhihu.com)

- 部分文章被 robots.txt 拦截
- 正文在 `.Post-RichText` 元素中
- 标题在 `.Post-Title` 元素中
- 需要登录态（`z_c0` Cookie），Cookie 有效期约 7 天
- 遇到登录墙时提示用户提供 Cookie 或使用浏览器接管

### 今日头条 (toutiao.com)

- 正文通常可直接抓取
- 如被拦截，使用 requests + Chrome UA

### 掘金 (juejin.cn)

- 无需登录，可直接抓取
- 正文在 `.article-content` 元素中
- 标题在 `.article-title` 元素中

### CSDN (blog.csdn.net)

- 无需登录，可直接抓取
- 正文在 `#content_views` 元素中
- 标题在 `h1.title-article` 元素中

## 依赖安装

```bash
# 核心依赖（必需）
pip3 install requests beautifulsoup4

# 增强依赖（可选，提升通用提取质量）
pip3 install readability-lxml lxml
```

## 注意事项

1. **不要把 URL 当作搜索关键词**去搜索引擎检索，这不会得到文章内容
2. **agent-browser 必须在子 session 中执行**，主 session 直接调用会被拒绝
3. **验证码场景**：检测到验证码时立即切换策略，不要重试同一策略
4. **Cookie 安全**：用户提供的 Cookie 仅用于当前抓取，不存储不记录
5. **版权尊重**：抓取内容仅供用户阅读和分析使用，不用于绕过版权保护
6. **频率控制**：连续抓取同一域名时适当间隔（默认 2 秒），避免触发封禁
7. **图片下载**：curl 方案只能提取文字，图片需用 requests 方案或浏览器方案获取

## 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| curl 返回验证码页面 | 触发微信反爬 | 切换到 requests 策略或浏览器策略 |
| 正文长度 < 50 字符 | 正文提取失败（模式B） | 检查 OG description 回退，或切换策略 |
| 知乎返回"请先登录" | 缺少登录态 | 用户提供 `z_c0` Cookie，或使用浏览器接管 |
| requests 超时 | 网络问题或IP封禁 | 增加 `--retry 5 --delay 3`，或使用代理 |
| 正文含大量HTML标签 | 清洗不彻底 | 检查 BeautifulSoup 解析逻辑 |
| 图片无法下载 | 图片URL为懒加载data-src | 使用浏览器策略滚动触发懒加载 |
| agent-browser 报错"禁止调用" | 在主 session 执行 | 改用 sessions_spawn 派发到子 session |
