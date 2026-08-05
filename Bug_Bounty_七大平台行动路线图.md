# Bug Bounty 七大平台行动路线图

> 创建日期：2026-08-05
> 目标：按"先练手 → 再实操"路径，逐步在 7 个平台建立实战记录

---

## 阶段一：零门槛练手（立即开始）

### 1. Open Bug Bounty
- **平台**：https://www.openbugbounty.org/report/
- **特点**：无需注册，提交即公开，覆盖 XSS / CSRF / HTML 注入等 Web 漏洞
- **赏金**：无固定报酬，由被报告方自行决定是否奖励
- **行动**：
  - [ ] 在 Acronis 或任意目标上寻找 XSS / CSRF 漏洞
  - [ ] 按 Open Bug Bounty 格式提交（需 PoC + 影响说明）
  - [ ] 目标：完成 3-5 个提交，积累报告写作经验
- **价值**：零门槛、公开记录可展示，是练手的最佳起点

### 2. huntr 2.0（AI 安全挑战赛）
- **平台**：https://blog.huntr.com/huntr-2-0-faq
- **重要变化**：已被 Palo Alto Networks 收购，转型为 AI 安全挑战赛平台
- **OSS 漏洞项目已于 2026-06-30 停止接受新提交**
- **新格式**：闯关式竞赛 + 排行榜 + 现金奖励
- **行动**：
  - [ ] 注册 huntr 2.0 账号，了解当前挑战赛规则
  - [ ] 参加首轮 AI 安全挑战赛（与你的 AI 安全技能完美匹配）
  - [ ] 目标：进入排行榜前 50%
- **价值**：AI 安全是当前最热门赛道，与你已有的安全攻击/防御练习直接对口

---

## 阶段二：Web2/Web3 实操（1-2 周后）

### 3. HackenProof
- **平台**：https://hackenproof.com
- **特点**：Web3 + Web2 混合，审计竞赛 + 常规赏金
- **赏金**：$100 - $100,000+
- **行动**：
  - [ ] 注册并完成 KYC
  - [ ] 从 Web2 项目开始（门槛较低）
  - [ ] 逐步过渡到 Web3 智能合约审计（需 Solidity 基础）
  - [ ] 目标：参加 1-2 个审计竞赛，提交至少 1 个有效漏洞
- **价值**：Web3 赏金高且竞争相对较少，是变现的快速通道

---

## 阶段三：大厂直营高赏金（积累经验后）

### 4. Google VRP
- **平台**：https://bughunters.google.com/about
- **赏金**：$500 - $1,500,000
- **2025 数据**：支付 $1710 万给 747 名研究员
- **Android 最高**：$1,500,000（需攻破 Titan M2 芯片）
- **行动**：
  - [ ] 注册 Google 账号并加入 Bug Hunters 社区
  - [ ] 从 Google Web 产品入手（Google Workspace / Cloud 等）
  - [ ] 研究 Google 的漏洞分类和赏金标准
  - [ ] 目标：提交 1 个有效漏洞（P3 级别起步）

### 5. Microsoft MSRC
- **平台**：https://www.microsoft.com/en-us/msrc/bounty
- **赏金**：$500 - $250,000
- **FY2026 数据**：支付超 $2000 万给 562 名研究员
- **覆盖范围**：包括第三方/OSS 组件
- **行动**：
  - [ ] 注册 Microsoft 账号
  - [ ] 关注 Microsoft 365 / Azure / Edge 的赏金范围
  - [ ] 目标：提交 1 个有效漏洞

### 6. Meta Bug Bounty
- **平台**：https://www.facebook.com/whitehat
- **赏金**：$500 - $300,000+
- **支付**：使用 Bugcrowd 作为支付处理器
- **分层制度**：Hacker Plus 分层（Bronze → Diamond）
- **账号接管漏洞**：最高 $40,000
- **行动**：
  - [ ] 注册 Facebook 账号并加入 Whitehat 项目
  - [ ] 关注意点：Instagram / WhatsApp / Oculus 的 Web 端漏洞
  - [ ] 目标：进入 Hacker Plus Bronze 层

### 7. Apple Security Bounty
- **平台**：https://security.apple.com/bounty/categories
- **赏金**：$500 - $2,000,000（加奖金可达 $5,000,000+）
- **2026 新政策**：6月起限制同时开放的报告数量（防止 AI 生成报告泛滥）
- **提交方式**：通过 Apple Security Research Portal
- **行动**：
  - [ ] 注册 Apple ID 并加入 Security Research Portal
  - [ ] 从 iCloud Web / Apple Services 入手
  - [ ] 注意报告数量限制，确保每次提交质量
  - [ ] 目标：提交 1 个有效漏洞

---

## 推荐推进时间线

| 时间 | 平台 | 目标 |
|------|------|------|
| **本周** | Open Bug Bounty | 完成 3-5 个 XSS/CSRF 提交 |
| **本周** | huntr 2.0 | 注册 + 参加首轮 AI 安全挑战赛 |
| **1-2 周后** | HackenProof | 注册 KYC + 参加 1 个审计竞赛 |
| **3-4 周后** | Google VRP | 注册 + 提交首个漏洞 |
| **4-6 周后** | Microsoft / Meta | 注册 + 提交首个漏洞 |
| **6-8 周后** | Apple | 注册 + 高质量提交 |

---

## 当前已有的实战资源

1. **Acronis Recon 已完成**：3 个 P0 发现待提交
   - storage-repo.acronis.com（目录列表暴露）
   - staging.partners.acronis.com（Staging 环境公开）
   - bg-vpn-qa.acronis.com（QA 环境暴露）
   - nuclei 扫描脚本就绪，等待 ANYIN9 上线执行确认

2. **安全技能储备**：
   - securityelites.com 29 节课程完成（22 种漏洞类型）
   - 阶段九安全攻击 15 题 + 阶段十一安全防御 10 题
   - 安全审计 Agent Skill 已发布
   - Bug Bounty 知识库 + Recon 自动化工作流技能已发布

3. **已注册账号**：
   - HackerOne ✅
   - Bugcrowd ✅

---

## 注意事项

- ⚠️ **PAT 安全**：GitHub PAT 仍有效，请尽快去 https://github.com/settings/tokens 删除
- ⚠️ **Apple 报告数量限制**：2026年6月起限制同时开放的报告数量，每次提交务必确保质量
- ⚠️ **huntr 已转型**：不再接受 OSS 漏洞提交，专注 AI 安全挑战赛
- ⚠️ **Acronis 提交前**：需确认目标在 Open Bug Bounty 的允许范围内，避免违反平台规则
