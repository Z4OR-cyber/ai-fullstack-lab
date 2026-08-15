

抓取网页文章内容，突破 robots.txt 限制，提取干净的文章正文。

## 核心能力

- **两级抓取策略**：先用 fetch_web 尝试直接抓取；若被 robots.txt 拦截，自动切换到 agent-browser 浏览器抓取
- **正文提取**：从网页 HTML 中提取文章标题、作者、发布时间和正文内容，去除广告、导航、评论等噪音
- **多平台支持**：微信公众号、知乎专栏、今日头条、掘金、CSDN 等常见中文内容平台

## 工作流程

### 步骤 1：尝试 fetch_web 直接抓取

先用 fetch_web 工具读取 URL。很多普通网页可以直接抓取，不需要启动浏览器。

```
fetch_web(urls=["<用户提供的URL>"])
```

**判断结果：**
- 成功返回内容 → 直接进入步骤 3（正文提取）
- 返回 `robots.txt` / `disallowed` / `plugin execute failed` 等错误 → 进入步骤 2

### 步骤 2：使用 agent-browser 浏览器抓取

当 fetch_web 被 robots.txt 拦截时（微信公众号 mp.weixin.qq.com 几乎总会被拦截），使用 agent-browser 技能打开真实浏览器抓取。

**重要：agent-browser 命令必须在子 session（sessions_spawn）中执行，不能在主 session 直接调用。**

派发子 session 执行浏览器抓取：

```
sessions_spawn(
  agent="lead",
  name="抓取文章",
  task="使用 agent-browser 打开以下URL并提取完整正文内容：
    URL: <用户提供的URL>

    执行步骤：
    1. agent-browser open "<URL>" && agent-browser tab 0
    2. agent-browser wait --load networkidle
    3. agent-browser get title    # 获取页面标题
    4. agent-browser get text body  # 获取正文内容

    将获取到的标题和完整正文内容原样返回。
    如果页面内容很长，滚动页面多次获取完整内容：
    agent-browser scroll down 2000
    agent-browser get text body"
)
```

### 步骤 3：正文提取与清洗

无论通过哪种方式获取到原始内容，都需要做以下清洗：

1. **提取标题**：从页面标题或正文第一行提取文章标题
2. **提取作者和发布时间**：微信公众号文章通常在正文开头有作者信息和发布时间
3. **去除噪音**：移除广告、"阅读原文"、点赞按钮、"相关阅读"等非正文内容
4. **保留结构**：保留标题层级、段落分隔、代码块、引用块等格式

### 步骤 4：返回结果

将清洗后的文章内容以 Markdown 格式返回，包含：

```markdown
# {文章标题}

> 来源：{URL}
> 作者：{作者（如能识别）}
> 发布时间：{时间（如能识别）}

{正文内容}
```

## 常见平台特殊处理

### 微信公众号 (mp.weixin.qq.com)
- 几乎总是被 robots.txt 拦截，直接走 agent-browser
- 正文在 `#js_content` 元素中
- 标题在 `#activity-name` 元素中
- 作者在 `#js_name` 元素中
- 图片可能使用 data-src 懒加载，需要滚动触发

### 知乎专栏 (zhuanlan.zhihu.com)
- 部分文章被 robots.txt 拦截
- 正文在 `.Post-RichText` 元素中
- 可能需要登录才能查看完整内容，遇到登录墙时提示用户

### 今日头条 (toutiao.com)
- 正文通常可直接 fetch_web
- 如被拦截，agent-browser 抓取

## 注意事项

- agent-browser 必须在子 session 中执行，主 session 直接调用会被拒绝
- 子 session 执行完毕后，结果会自动返回主 session
- 如果 agent-browser 也无法打开（如需要登录），如实告知用户卡点
- 不要把 URL 当作搜索关键词去搜索引擎检索，这不会得到文章内容
- 抓取到的内容仅供用户阅读和分析使用，不用于绕过版权保护


---

## ⚠️ Deprecation Notice

**本技能已被功能更完整的版本替代。**

请使用以下技能之一：
- **Coze技能商店**：`web-article-fetcher`（skill_id: 7674228102490226715）— 4级降级（fetch_web → curl伪装UA → Python解析 → agent-browser），含微信双模式解析和验证码检测
- **群项目内**：如存在 `unified-article-reader`，优先使用该版本

本技能仅保留2层降级（fetch_web → agent-browser），作为轻量备选。新任务请使用上述完整版本。

*Deprecated by 投资理财小豆, 2026-08-15*
