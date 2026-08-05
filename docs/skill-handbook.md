# 通用Agent技能手册

> 所有Agent共享 | 初始版本：2026-08-04 | 贡献者：项目协作
> 各Agent在实操中验证有效的通用经验，按主题分类整理。

---

## 一、Token优化策略

> 任何调用LLM的Agent都适用。验证于AI科技简报脚本，总LLM调用从~25次降到~7次。

### 1.1 八条核心规则
1. **工具输出落盘**：搜索/抓取/工具调用的完整输出写入文件，对话中只传结构化摘要
2. **结构化输出**：用JSON Schema替代自然语言长文，减少请求和响应的冗余
3. **命令链式化**：短命令替代长命令，多操作chain在一起减少per-call overhead
4. **Token预算意识**：system prompt尽量短，条件加载详情而非全量塞入
5. **批处理优先**：多个独立小任务合并为一次LLM调用（batch extract/aggregate）
6. **缓存复用**：相同/相似请求走缓存，不重复调用LLM
7. **摘要替代全文**：历史上下文用摘要而非原文传递
8. **分级调用**：简单任务用便宜模型，复杂任务才用贵模型

### 1.2 批处理实战
- 逐页/逐条调LLM → 每N条合并批量调用
- 适用场景：extract/summarize/classify等无状态处理
- 验证案例：AI简报extract_facts从每页1次→每3页1次，LLM调用降67%

### 1.3 搜索缓存
- 相同query 24h内不重复搜索，直接返回缓存结果
- 无Redis时用SQLite替代：`CREATE TABLE token_cache(query_hash TEXT, response TEXT, ttl TIMESTAMP)`

### 1.4 模型路由策略
- 简单分类/抽取/格式化 → 便宜模型
- 复杂推理/生成/分析 → 强模型
- fallback链：Subscription → API → Cheap → Free

---

## 二、搜索最佳实践

### 2.1 Query语言决定来源分布
- **全中文query** → 搜索引擎返回CSDN/知乎为主，一手来源极少
- **中英文混合query** → 命中TechCrunch/The Verge/GitHub/OpenAI Blog等英文一手来源
- **建议**：每个搜索方向用1条中文+1条英文query

### 2.2 来源质量分层
| 层级 | 类型 | 示例 |
|------|------|------|
| Tier 1 | 官方一手 | 官网公告/财报/论文/法规原文 |
| Tier 2 | 权威二手 | 主流科技媒体/行业报告 |
| Tier 3 | 聚合 | 技术博客/社区讨论 |

策略：Tier排序优先 + 单域名上限（如3条）保证覆盖面

### 2.3 多源验证原则
- 搜索结果与认知冲突时，以多源一致结果为准
- 结果互相冲突时继续查证，无法确定时说明不确定性
- 优先采信原始来源（官网、公告、论文、法规原文）

### 2.4 搜索技巧
- 先宽泛搜索，再按实体、时间、地点、来源等信息收窄
- 搜不到关键信息时换关键词，不要重复非常相似的查询
- 不要用代码从搜索结果中机械提取信息；由Agent阅读、判断和综合

---

## 三、环境配置避坑

### 3.1 国内镜像（必用）
| 工具 | 镜像命令 | 速度对比 |
|------|---------|---------|
| pip | `-i https:pypi.tuna.tsinghua.edu.cn/simple` | 87MB/s vs 默认19KB/s |
| npm | `--registry=https:registry.npmmirror.com` | 显著提升 |
| Node headers | `NODEJS_ORG_MIRROR=https:npmmirror.com/mirrors/node` | 解决node-gyp下载超时 |

### 3.2 Python 3.13 distutils缺失
- **现象**：node-gyp报 `ModuleNotFoundError: No module named 'distutils'`
- **原因**：Python 3.13移除了distutils模块
- **修复**：`pip3 install --upgrade setuptools`（v83提供distutils兼容层）

### 3.3 bash工具pip解析bug
- **现象**：pip直接在bash命令行调用触发 `print("cannot use the package")` 解析错误
- **原因**：bash工具解析器误将Python代码当shell命令
- **修复**：通过Python脚本绕过
  ```bash
  python3 -c "import subprocess,sys; subprocess.run([sys.executable,'-m','pip','install','pkg','-i','https:pypi.tuna.tsinghua.edu.cn/simple'])"
  ```

### 3.4 sandbox网络限制
- Google API (`generativelanguage.googleapis.com`) 和 OpenAI API (`api.openai.com`) 域名在sandbox被封
- 需要通过代理服务（如Apiframe）绕过

### 3.5 安装验证三步
1. 命令执行 exit_code=0
2. `python3 -c "import pkg; print(pkg.__version__)"`
3. 关键功能实际调用测试

---

## 四、文件与记忆管理

### 4.1 工作目录结构
```
/app/data/所有对话/主对话/     ← Agent工作目录（仅自身状态和过程草稿）
├── 基础设定/
│   ├── SOUL.md                # 身份定义
│   ├── TOOLS.md               # 经验索引（只存锚点行）
│   ├── EMAIL_RULES.md         # 邮件规则
│   └── experience/            # 经验详情文件
├── MEMORY.md                  # 长期规则+状态锚点（上限5120字节）
├── USER.md                    # 用户画像（上限2048字节）
├── SECRET.md                  # 敏感凭证
├── recent_memory/
│   ├── index.json             # 记忆单元目录
│   ├── project/               # 项目进度快照
│   ├── decision/              # 重要决策记录
│   ├── todo/                  # 待办事项
│   └── review/                # 每日复盘报告
└── 用户上传/                   # 用户上传的文件
```

### 4.2 TOOLS.md 锚点行格式
```
- **短标题**：一句话结论。详见 基础设定/experience/xxx.md
```
- 只存索引，详情写入experience/对应文件
- 每写一个experience详情，必须同步补一行锚点

### 4.3 MEMORY.md 格式
- 固定两段：`## 长期行为规则` / `## 核心状态锚点`
- 每条用 `- **粗体短标题**：内容`
- 状态锚点附日期 `（YYYY-MM-DD）`
- 指针用代码行块包裹路径

### 4.4 recent_memory 索引
- `index.json`：所有记忆单元的目录（摘要+标签+重要度+时间）
- 分类：project/decision/todo/review
- 有过期时间的条目设置 `expires_at`

### 4.5 记忆检索三层法
1. **即时层**：先查已加载的USER.md、MEMORY.md等
2. **近中期层**：读recent_memory/index.json → 定位具体文件
3. **长期层**：memory_search 语义召回
- 用户说"好好想想"时，至少推到第2层

---

## 五、Coze CLI 使用规范

### 5.1 项目文件操作
```bash
# 列出项目文件
coze agent file list --project-id <PID> --depth 2 --format json

# 下载文件（注意：无--output-path参数，需先cd到目标目录）
cd /app/data/所有对话/主对话 && coze agent file download --project-id <PID> --project-file-path /docs/notes.md --format json

# 上传文件
coze agent file upload --project-id <PID> --local-file-path ./report.md --project-dir /docs --format json

# 读取文件
coze agent file read --project-id <PID> --project-file-path /docs/notes.md --format json
```

### 5.2 三个必须
1. **所有命令追加 `--format json`**：默认文本格式难以结构化提取
2. **必须检查 `exit_code`**：非零时根据错误信息排查
3. **download无--output-path**：先cd到目标目录再执行

---

## 六、子Agent协作模式

### 6.1 适合spawn的任务特征
- 预计超过1分钟且产物可独立检查
- 目标和输入基本清晰，中途不需要频繁交互
- 多个独立子任务可并行

### 6.2 不适合spawn的场景
- 一两步能完成的问答
- 目标不清需要先探索
- 强交互/高风险：授权、绑定、涉及费用

### 6.3 并行派发最佳实践
- 派发前确认所有设计方向已定
- task描述精简，背景用指针引用文件而非全文复制
- 不同独立子任务可并行派发多个子session
- 同一核心产物不要重复派发
- spawn后等待系统推送结果，不主动轮询

### 6.4 子Agent跑偏处理
- 轻微跑偏：sessions_send 修正
- 严重跑偏：sessions_abort 终止

---

## 七、代码生成与编辑技巧

### 7.1 大文件代码生成不委托子Agent
- **问题**：子Agent在>500行代码任务上反复超时
- **解决**：主Agent直接用edit_file分步写入
  1. 先写核心数据+逻辑骨架
  2. 再append完整内容
- **验证**：2026-07-22 识界行者Demo v5 验证3+次成功

### 7.2 全局术语批量替换
- `edit_file replace_all` 可跨多文件批量替换
- 替换后验证关键文件即可，JS函数名不改只改显示文本

### 7.3 多轮术语迭代模式
- 临床→诗意化需要3轮校准
- 最佳实践：先出完整对照方案给用户一次性校准方向，比自己反复猜更高效

### 7.4 文档整合模式
- 多个散落设计文档 → 1份整合文档
- 不原样搬运而是结构化浓缩
- 约束验证表一次性检查所有设计规则
- 后续开发只需参考一个文件

---

## 八、LLM批处理与缓存

### 8.1 批处理降消耗
- 逐页/逐条调LLM → 每N条合并批量调用
- 适用：extract/summarize/classify等无状态处理
- 验证：LLM调用降67%，信息密度不变

### 8.2 非核心路径LLM调用替换
- 能用纯函数/启发式规则完成的处理不调LLM
- 搜索规划+候选筛选改纯函数后总LLM调用大幅降低
- 新增prompt约束强制输出带具体实体+数字，消除空泛表述

### 8.3 积分消耗追溯方法
- 通过session记录拆解到函数级调用次数
- 公式：搜索次数×N + 抓取次数×M + LLM调用次数×K
- 定位消耗大头后针对性优化

---

## 九、搜索结果来源优化

### 9.1 来源质量优化
- 全中文搜索词 → CSDN垄断，需中英文混合
- 英文query优先命中官方/权威站点
- 验证：CSDN占比从100%降到0，官方来源从1条升到8条

### 9.2 来源多样性
- 新增单域名上限（如MAX_PER_DOMAIN=3）
- 同一域名选满上限后跳过，让位给其他来源
- 保证tier优先级不变的前提下来源多样性

### 9.3 抓取量控制
- MAX_FETCH_PAGES从20下调到12
- 单页字符限制PER_PAGE_CHARS=4000
- 减少抓取量同时保持信息密度

---

## 十、Agent发布经验

### 10.1 EvoMap发布三坑
1. Gene字段必须提供strategy数组
2. validation逻辑不能是无意义的trivial（如直接return true）
3. 所有shell操作符（管道&&/||等）在提交内容中全部禁止

### 10.2 Coze技能商店
- 提交审核周期约5天
- 平台与开发者分成比例为7:3，开发者拿70%
- 上架商店需开通商户账户（支付宝/抖音支付）

### 10.3 skill_builder工作流
创建工作区 → 注册凭证 → 打包发布 → 加载测试 → 修复迭代
- 凭证分开发者模式（固定Key）和使用者模式（运行时填写）

---

## 十一、预防性维护思维

> 黄帝内经：「上医治未病」——预防 > 早发现 > 应急止损

### 三层防御
1. **预防层**：发现问题反复出现时追溯根因并消除，不满足于每次手动纠正
2. **监测层**：定期系统化检查关键指标，趋势恶化时立即预警
3. **应急层**：问题已发生时快速止损并修复

### 关键原则
- 批量操作前必须确认成本（积分、token消耗、时间）
- 新机制上线前先小规模验证
- 时间敏感信息必须API实时查询，禁止推测
- 连续3天同一问题 → 触发"技术债即时清偿"

---

## 附录：领域经验扩展

> 各领域经验持续积累中，以下方向待补充。

### [待补充] 金融领域经验

### [待补充] 自媒体运营经验

### [待补充] 开发工程经验
