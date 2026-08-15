---
name: bug-bounty-suite
description: Bug Bounty 全流程自动化套件。整合知识库、目标监控、Recon侦察、代码审计四大模块，覆盖从学习理论到提交漏洞报告的完整生命周期。当用户需要参与Bug Bounty悬赏、进行安全测试、执行漏洞扫描、提交漏洞报告、监控赏金项目、学习网络安全、做Recon侦察、代码安全审计时使用此技能。支持HackerOne和Bugcrowd双平台，包含29种外部漏洞类型+15类代码安全问题的统一检测体系。
---

# Bug Bounty 全流程自动化套件

> 整合自：bug-bounty-knowledge-base + bug-bounty-recon-workflow + bounty-monitor-automation + security-audit-agent
> 覆盖：学习 → 监控 → 侦察 → 扫描 → 审计 → 报告 → 迭代

## 全流程架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Bug Bounty 全流程套件                      │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  模块1   │  模块2   │  模块3   │  模块4   │    模块5        │
│  知识库  │  目标    │  Recon   │  漏洞    │    代码         │
│  (理论)  │  监控    │  侦察    │  扫描    │    审计         │
│          │  (发现)  │  (外部)  │  (外部)  │    (内部)       │
├──────────┼──────────┼──────────┼──────────┼─────────────────┤
│  29种    │  H1/BC   │ subfinder│ nuclei   │  Python AST     │
│  漏洞    │  每日    │ httpx    │ ffuf     │  C 正则匹配     │
│  类型    │  监控    │ dnsx     │ katana   │  15类漏洞       │
│  +模板   │  +筛选   │ +分级    │ +报告    │  +修复建议      │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│              模块6：统一报告生成 + 迭代反馈循环                │
└─────────────────────────────────────────────────────────────┘
```

## 模块1：知识库（理论基础）

### 漏洞分类体系（统一内外双维度）

| 类别 | 外部扫描(Recon) | 内部审计(Code) | 共通检测点 |
|------|----------------|----------------|------------|
| 注入 | SQL注入、命令注入 | SQL拼接、os.system | 用户输入→执行路径 |
| XSS | 反射/存储/DOM型 | innerHTML、eval | 输入→输出未转义 |
| SSRF | URL参数探测 | requests.get(用户输入) | 外部URL→内部请求 |
| IDOR | 越权访问测试 | 直接对象引用 | 权限校验缺失 |
| RCE | 模板注入、反序列化 | pickle.loads、eval | 代码执行入口 |
| 认证 | 弱密码、会话固定 | 硬编码密钥、弱加密 | 认证绕过路径 |
| 配置 | 目录列表、Staging暴露 | 调试模式、默认配置 | 安全配置缺失 |
| 路径 | LFI/RFI测试 | open()路径拼接 | 文件包含 |

### 报告模板（统一格式）
```markdown
## 漏洞标题：[漏洞类型] [目标] [简述]

### 严重程度
CVSS 3.1: [评分] | 级别: Critical/High/Medium/Low

### 漏洞描述
[1-2段描述漏洞原理和影响]

### 复现步骤
1. [步骤1]
2. [步骤2]
3. [步骤3]

### 影响范围
- 受影响URL/代码路径
- 潜在数据泄露/权限提升

### 修复建议
[具体可操作的修复方案]

### 时间线
- 发现时间: YYYY-MM-DD
- 报告时间: YYYY-MM-DD
```

## 模块2：目标监控（每日自动）

### 数据源
- HackerOne: `https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/hackerone_data.json`
- Bugcrowd: `https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/bugcrowd_data.json`

### 筛选策略
1. 友好度评分（5/5最优）：响应速度、赏金范围、提交难度
2. Scope匹配：Managed > Public > VDP
3. 赏金范围：$100+优先
4. 响应时间：5个工作日内优先

### 关键配置
- 超时: 120s + 3次重试 + 5s间隔
- 每日9:00 Calendar调度
- 输出: `bounty_briefing_YYYY-MM-DD.md`

### 监控运行状态
- 已连续运行8天（2026-08-05至2026-08-13）
- 监控范围：690个程序
- TOP5推荐：HubSpot/Varonis/Netflix/Visa/Payoneer

## 模块3：Recon 侦察（外部攻击面）

### 7步标准流程
1. 子域名枚举（subfinder）→ 1329子域名
2. DNS记录收集（dnsx）→ 126 DNS记录
3. 存活主机探测（httpx）→ 566存活
4. 主机分类筛选 → 465有内容主机
5. 目录爆破（ffuf）— P0目标优先
6. 漏洞扫描（nuclei）— 精简到≤3目标+限定模板
7. 爬虫扩展（katana）

### P0-P3 分级策略
- P0：目录列表暴露、Staging环境公开、QA环境暴露
- P1：登录页面、API端点、Beta环境
- P2：需客户端证书的API、VPN端点、默认页面
- P3：重定向页面、静态资源

### Acronis Recon 关键发现
1. `storage-repo.acronis.com` [200] — 目录列表暴露（CWE-548）
2. `staging.partners.acronis.com` [200] — Staging环境公开可访问
3. `bg-vpn-qa.acronis.com` [200] — QA环境暴露

### 已产出
- 3份漏洞报告已写入ANYIN9（`C:\Users\34252\Projects\HackerOne提交报告.md`）
- 等待H1 ID验证通过后提交

## 模块4：漏洞扫描

### 工具链配置
| 工具 | 用途 | 路径 |
|------|------|------|
| subfinder | 子域名枚举 | C:\Users\34252\Tools\go-bin\bin |
| httpx | 存活探测 | C:\Users\34252\Tools\go-bin\bin |
| dnsx | DNS记录 | C:\Users\34252\Tools\go-bin\bin |
| nuclei | 漏洞扫描 | C:\Users\34252\Tools\go-bin\bin |
| ffuf | 目录爆破 | C:\Users\34252\Tools\go-bin\bin |
| katana | 爬虫 | C:\Users\34252\Tools\go-bin\bin |

### 扫描优化经验
- nuclei全量扫描在ANYIN9上会超时，需精简到≤3个目标+限定severity
- ffuf使用raft-medium-dirs.txt字典
- 多步骤合一脚本容易超时，拆分为单步骤小脚本
- `go install`编译会超时，改用GitHub Releases预编译二进制

## 模块5：代码安全审计

### 支持语言
- Python（AST解析）
- C（正则匹配）

### 检测的15类安全问题
SQL注入、命令注入、XSS、路径遍历、硬编码密钥、不安全反序列化、弱加密、缓冲区溢出、格式化字符串、不安全文件操作、竞态条件、整数溢出、不安全随机数、信息泄露、不安全配置

### 输出
结构化审计报告，含风险评级（Critical/High/Medium/Low）和修复建议。

## 模块6：报告生成与迭代

### HackerOne 提交流程
1. 完成Veriff身份验证（护照/驾照）
2. 登录HackerOne → 选择目标程序
3. 创建Report → 填写漏洞详情
4. 等待_triage_审核

### 当前阻塞
- **H1强制ID验证**：截止8月14日，需通过Veriff身份验证
- 数据中心IP受限：需通过本地住宅浏览器手动提交
- 3份Acronis漏洞报告已就绪等待提交

## 三平台发布状态
- Coze 技能商店：已发布（skill_id: 7673131572484227112）
- EvoMap：已发布（bundle_964c0e943e4d7b38）
- GitHub：skills/bug-bounty-suite/SKILL.md

## 许可
MIT

## 实战案例

### Varonis Bug Bounty Recon 经验

**侦察数据**：
- 518候选子域名 → 26存活 → 24 HTTP服务
- 114个自动化扫描findings

**误报识别**：
- 所有CRITICAL级别findings均为误报，根因是SPA catch-all（单页应用对所有路径返回相同HTML）
- 使用404控制路径对比法验证后，仅保留6个P4/P5安全头问题

**工具与经验**：
- certspotter替代crt.sh进行证书透明日志查询（更稳定，crt.sh频繁超时）
- 云端数据中心IP被Imperva WAF直接拦截，深度测试需要住宅IP
- atlas-gw.varonis.io发现Alltrue LLM网关默认后端httpbin.org，所有路径返回400 `{"message": "Unprocessable request to https://httpbin.org/"}`，响应头含`x-alltrue-llm-error-type: rule-violation`，判定为配置信息泄露但不可直接利用（SSRF注入全部被Azure WAF拦截403）
