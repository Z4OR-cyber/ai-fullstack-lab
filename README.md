# AI Fullstack Lab

> 多 Agent 通过项目协作同步技能的实践仓库

## 这是什么

一个探索「多 Agent 协作生态」的实验室仓库。核心实践：多个 AI Agent 在同一个项目空间中协作，各自贡献专业领域的技能和经验，通过统一的工作流同步到 GitHub、EvoMap 和 Coze 技能商店三个平台。

## 核心理念：项目驱动的技能同步

```
项目协作空间（共享文件 + 群聊）
        │
        ├── Agent A ── 领域技能 ──┐
        ├── Agent B ── 领域技能 ──┤
        ├── Agent C ── 领域技能 ──┤
        └── Agent D ── 领域技能 ──┘
                    │
              统一整理 & 去身份化
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    GitHub       EvoMap      Coze商店
   （开源）    （进化网络）  （分发）
```

### 为什么这样做

1. **技能不绑定身份**：技能是可复用的能力封装，不应绑定到某个特定 Agent。整理时只保留方法论和工具链，去掉所有 Agent 个人信息
2. **项目即协作媒介**：多 Agent 在项目群聊中实时协作，文件空间共享，技能自然流动
3. **三平台互补**：GitHub 便于版本管理和开源协作，EvoMap 提供 GDI 评估和进化反馈，Coze 商店面向终端用户分发

## 仓库结构

```
ai-fullstack-lab/
├── README.md                           # 本文件
├── docs/
│   ├── multi-agent-skill-sync.md       # 多Agent技能同步方法论
│   ├── skill-handbook.md               # 通用技能手册（11章节）
│   └── evomap-framework.md             # 自进化框架设计
├── skills/                             # 技能实现
│   ├── ai-image-studio/                # 多引擎AI图片生成
│   ├── ai-tech-briefing/               # AI科技简报
│   ├── ai-tech-briefing-generator/     # 简报生成器
│   ├── card-game-design-pipeline/      # 卡牌游戏设计流水线
│   ├── card-game-dev-pipeline/         # 卡牌游戏开发流水线
│   ├── content-atomizer/               # 内容知识原子化
│   ├── kimi-k3-coder/                  # Kimi K3编码助手
│   ├── medflow-spaced-repetition/      # 间隔重复学习系统
│   ├── token-optimization-engine/      # Token优化策略
│   ├── video-automation-toolkit/       # 视频自动化剪辑
│   └── wechat-article-reader/          # 微信公众号文章阅读器
├── experiences/                        # 跨Agent通用经验
│   ├── token-optimization.md           # Token优化策略
│   ├── gene-distillation.md            # Gene蒸馏法
│   ├── calendar-automation.md          # 日历自动化
│   └── video-automation.md             # 视频工具链经验
```

## 同步工作流

1. **技能验证**：Agent 在实际任务中验证技能有效性
2. **经验提炼**：将实操经验提炼为通用方法论，去掉 Agent 个人信息
3. **项目上传**：通过项目文件空间共享给所有协作者
4. **GitHub 同步**：整理后推送到本仓库
5. **EvoMap 发布**：以 Gene/Capsule 格式发布，获取 GDI 评估
6. **Coze 商店**：发布到「我的技能」，可上架公开商店

## 贡献规范

- 新技能/经验先在实际任务中验证
- 提炼通用部分，不包含任何 Agent 个人信息
- 技能目录包含 `SKILL.md`（能力描述）和必要的脚本/配置
- 经验文档聚焦方法论，附验证数据（压缩率、调用次数等）

## License

MIT
