# Bug Bounty 漏洞报告模板

> 本文件用于准备提交到 HackerOne 或直接发送给 Acronis 安全团队的漏洞报告

---

## 报告 #1: storage-repo.acronis.com 目录列表暴露

### 漏洞标题
Information Disclosure via Directory Listing on storage-repo.acronis.com

### 漏洞类型
CWE-548: Exposure of Information Through Directory Listing

### 严重程度
Low — 目录列表暴露了软件更新仓库结构，但未发现敏感配置文件或凭证。暴露内容为 2016-2018 年的软件包目录（mirrorlists/mon/releases/updates），信息价值有限。

### 漏洞描述
The web server at `storage-repo.acronis.com` has directory listing enabled, exposing the file structure of the Acronis software storage repository to any unauthenticated user. The exposed directory `/vstorage/` contains four subdirectories: `mirrorlists/` (Jul 2016), `mon/` (Feb 2017), `releases/` (Apr 2018), and `updates/` (Apr 2018). While the exposed data appears to be outdated software package directories, the misconfiguration itself reveals internal infrastructure structure and could aid attackers in mapping Acronis's update delivery system.

### 受影响资产
- **URL:** https://storage-repo.acronis.com
- **Directory:** /vstorage/
- **HTTP Status:** 200 OK
- **Server:** Nginx
- **Page Title:** "Index of /"

### 暴露内容
| 目录 | 最后修改 | 推测内容 |
|------|----------|----------|
| `/vstorage/mirrorlists/` | 18-Jul-2016 17:00 | 镜像源列表 |
| `/vstorage/mon/` | 08-Feb-2017 15:41 | 监控数据 |
| `/vstorage/releases/` | 24-Apr-2018 16:42 | 软件发布包 |
| `/vstorage/updates/` | 24-Apr-2018 20:31 | 软件更新包 |

### 影响评估
- 攻击者可了解 Acronis 软件更新仓库的内部结构
- 暴露的 `releases/` 和 `updates/` 目录可能包含软件版本信息，有助于针对性攻击
- `mon/` 目录可能包含监控数据或配置
- 数据较旧（最新 2018年4月），但 misconfiguration 至今未修复（已暴露 8+ 年）

### 复现步骤
1. Open a web browser
2. Navigate to https://storage-repo.acronis.com
3. Observe that the server returns a directory listing ("Index of /") showing a `vstorage/` folder
4. Click on `vstorage/` to reveal subdirectories: `mirrorlists/`, `mon/`, `releases/`, `updates/`
5. Each subdirectory is browsable without authentication

### 证据
- 截图1: `storage-repo.acronis.com` 根目录列表（"Index of /"，显示 vstorage/ 文件夹）
- 截图2: `/vstorage/` 目录列表（显示 mirrorlists/、mon/、releases/、updates/ 四个子文件夹）
- HTTP response: 200 OK, Nginx
- Page title: "Index of /"

### 修复建议
1. Disable directory listing in Nginx configuration:
   ```nginx
   autoindex off;
   ```
2. Or add a default index page (index.html/index.php)
3. Restrict access to the storage repository using authentication
4. Review exposed files for sensitive content and remove if necessary

### 时间线
- 2026-08-04: Discovered during Recon (subfinder → httpx)
- 2026-08-05 14:16: Confirmed still active (HTTP 200, "Index of /")
- 2026-08-05 14:21: Confirmed /vstorage/ subdirectory with 4 folders (mirrorlists/mon/releases/updates)
- 2026-08-05 14:32: Screenshot evidence captured via cloud browser
- 2026-08-05 14:38: Report finalized, ready for submission

---

## 报告 #2: staging.partners.acronis.com Staging 环境公开暴露

### 漏洞标题
Staging Environment Publicly Accessible on staging.partners.acronis.com

### 漏洞类型
CWE-489: Active Debug Code / CWE-200: Exposure of Sensitive Information

### 严重程度
Low-Medium

### 漏洞描述
The staging (pre-production) environment at `staging.partners.acronis.com` is publicly accessible without authentication. Staging environments typically have weaker security controls than production and may expose debug information, test accounts, or unfinished features.

### 受影响资产
- **URL:** https://staging.partners.acronis.com
- **HTTP Status:** 200 OK
- **Server:** IIS 10.0, ASP.NET 4.0, Windows Server

### 复现步骤
1. Navigate to https://staging.partners.acronis.com
2. Observe that the staging environment is accessible without authentication

### 修复建议
1. Restrict access to staging environments using IP allowlisting or VPN
2. Require authentication for all non-production environments
3. Use robots.txt or WAF rules to block public access

---

## 报告 #3: bg-vpn-qa.acronis.com QA 环境公开暴露

### 漏洞标题
QA Environment Publicly Accessible on bg-vpn-qa.acronis.com

### 漏洞类型
CWE-489: Active Debug Code / CWE-200: Exposure of Sensitive Information

### 严重程度
Low

### 漏洞描述
The QA environment at `bg-vpn-qa.acronis.com` is publicly accessible. QA environments may contain test data, debug features, or weaker authentication mechanisms.

### 受影响资产
- **URL:** https://bg-vpn-qa.acronis.com
- **HTTP Status:** 200 OK

### 修复建议
1. Restrict access to QA environments using IP allowlisting or VPN
2. Ensure QA environments are not accessible from the public internet

---

## 提交指南与行动方案

### 提交前检查清单
- [x] 获取目录列表截图作为证据（已通过云电脑截图）
- [x] 检查暴露的文件内容（vstorage/ 下 4 个子目录，2016-2018年数据）
- [x] 报告英文草稿已完成
- [ ] 确认目标在 HackerOne Acronis 程序的当前 scope 内（需用户在 HackerOne 页面确认）
- [ ] 决定提交渠道

### 提交渠道（按优先级）
1. **HackerOne Acronis** (https://hackerone.com/acronis) — 如果目标在 scope 内
2. **Acronis 安全团队** (security-advisory.acronis.com) — 直接 responsible disclosure
3. **Open Bug Bounty** (https://www.openbugbounty.org/report/) — 仅限 XSS/CSRF，不适用于此发现

### Bug Bounty 平台最新动态（2026-08-05 搜索）

**HackerOne**（[来源](https://www.stationx.net/bug-bounty-programs-for-beginners/)）
- 3000+ 程序，过去一年支付 $81M
- Hacker101 CTF 免费训练：完成挑战赚积分，26分可获私人程序邀请
- 新用户 30 天内限 4 次提交，每次都要保证质量
- 推荐学习路径：Hacktivity 公开报告 → 逆向工程高分报告写法

**huntr**（[来源](https://www.ieee-security.org/TC/SP2025/downloads/posters/sp25posters-final9.pdf)）
- 已被 Protect AI 收购（非 Palo Alto Networks）
- 专注 AI/ML 开源软件漏洞，已收集 6,427 份报告
- AI/ML 漏洞赏金高于普通 OSS
- 49.5% 的 AI/ML 漏洞披露后仍未修复 → 机会大
- 与你的 AI 安全技能（Prompt注入/数据投毒/模型窃取）完美匹配

**2026 AI 安全趋势**（[来源](https://www.analyticsinsight.net/cybersecurity/top-ai-security-threats-every-cybersecurity-team-must-prepare-for-in-2026)）
- Prompt Injection 是 OWASP LLM Top 10 第一项
- AI Agent 劫持、模型投毒、对抗样本是热门方向
- Meta 为 0-click MXSS 支付 $300K（[来源](https://blog.csdn.net/weixin_42376192/article/details/157170044)）
- Next.js stored XSS 获五位赏金（[来源](https://www.yeswehack.com/news/rickrolling-fifa-ai-google-xss)）
- SVG 上传 XSS → ATO 获 SAR 2,629（[来源](https://buaq.net/go-429284.html)）

### 立即行动清单

| 优先级 | 行动 | 平台 | 操作 |
|--------|------|------|------|
| 🔴 今天 | 提交 storage-repo 报告 | HackerOne/直邮 | 确认 scope 后提交 |
| 🔴 今天 | 开始 Hacker101 CTF | HackerOne | 完成 Newcomers Playlist |
| 🟡 本周 | 注册 huntr | huntr.com | 参加 AI 安全挑战 |
| 🟡 本周 | 学习 Hacktivity 公开报告 | HackerOne | 阅读 10 份高分报告 |
| 🟢 下周 | 找 XSS 目标练手 | Open Bug Bounty | SVG 上传/反射型 XSS |
| 🟢 下周 | 选活跃程序做 Recon | HackerOne | Greenhouse/8x8 等 $100+ 程序 |
