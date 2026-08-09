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

## 模块3：Recon 侦察（外部攻击面）

### 7步标准流程
```
Step 1: subfinder → 子域名枚举
Step 2: dnsx → DNS记录收集
Step 3: httpx → 存活主机探测
Step 4: 主机分类筛选（P0-P3分级）
Step 5: ffuf → 目录爆破
Step 6: nuclei → 漏洞扫描
Step 7: katana → 爬虫扩展
```

### P0-P3 目标分级策略
- **P0**: 目录列表暴露、Staging环境公开、QA环境暴露 → 立即报告
- **P1**: 登录页面、API端点、Beta环境 → 深入测试
- **P2**: 需客户端证书的API、VPN端点、默认页面 → 尝试绕过
- **P3**: 重定向页面、静态资源 → 记录备案

### 工具链配置（ANYIN9）
```bash
# Go bin目录
export PATH=$PATH:C:\Users\34252\Tools\go-bin\bin

# 工具版本
subfinder v2.6.6 | httpx v1.3.9 | nuclei v3.3.5
dnsx v1.2.1 | ffuf v2.1.0 | katana v1.1.0

# 字典文件
C:\Users\34252\Tools\wordlists\{common.txt, subdomains-5000.txt, raft-medium-dirs.txt}
```

### 执行约束
- nuclei: 精简到≤3个P0目标，限定severity critical,high,medium
- ffuf: 单目标限200线程，超时10s
- 多步骤脚本拆分为单步骤执行，避免超时

## 模块4：漏洞扫描（外部检测）

### nuclei 模板策略
```bash
# P0目标深度扫描
nuclei -u <target> -severity critical,high,medium -timeout 10 -rate-limit 150

# 特定漏洞类型
nuclei -u <target> -t exposures/ -t misconfiguration/ -t vulnerabilities/
```

### 发现分类
- **配置暴露**: 目录列表(CWE-548)、信息泄露、默认凭据
- **认证缺陷**: 弱密码、会话管理、多因素缺失
- **注入点**: SQL注入、XSS、SSRF、模板注入
- **访问控制**: IDOR、路径遍历、权限提升

## 模块5：代码安全审计（内部检测）

### 支持语言
- **Python**: AST语法树分析 + 正则模式匹配
- **C**: 正则模式匹配
- **通用**: 注释敏感信息、依赖版本检查

### 15类代码漏洞检测
1. SQL注入（字符串拼接SQL）
2. 命令注入（os.system/subprocess shell=True）
3. XSS（innerHTML/eval/document.write）
4. 路径遍历（open()拼接用户输入）
5. 硬编码密钥（API Key/Password明文）
6. 不安全反序列化（pickle.loads/yaml.load）
7. 弱加密（MD5/DES/ECB模式）
8. 缓冲区溢出（C: strcpy/sprintf/gets）
9. 格式化字符串（C: printf用户输入）
10. 不安全随机数（random.random用于安全场景）
11. SSRF（requests.get用户URL）
12. XML外部实体（XXE）
13. 开放重定向
14. 不安全文件上传
15. 调试信息泄露

### 执行方式
```bash
cd skills/security-audit-agent
python main.py <目标路径> --format markdown --output <报告目录>
```

## 模块6：迭代反馈循环

### 反馈机制
```
监控发现新目标 → 调整Recon参数 → 扫描新目标 → 
发现漏洞模式 → 更新知识库 → 优化扫描模板 → 
代码审计补充检测规则 → 回到监控
```

### 迭代优化记录
每次Bug Bounty活动后记录：
- 有效Recon参数（子域名来源、扫描模板）
- 误报率高的检测规则
- 新发现的漏洞模式
- 平台政策变化

## 行为准则
- 严格遵守H1 Rules of Engagement
- 只测scope内目标
- 负责任披露，不利用不勒索
- 不做破坏性测试，不影响业务运行
- 尊重平台和厂商政策

## 平台账号
- HackerOne: 已注册（需Veriff ID验证，截止8月14日）
- Bugcrowd: 已注册
- 3份Acronis漏洞报告已就绪待提交

## 三平台发布状态
- GitHub: skills/bug-bounty-suite/SKILL.md（本文件）
- EvoMap: 待发布
- 虾评: 待发布

## 许可
MIT
