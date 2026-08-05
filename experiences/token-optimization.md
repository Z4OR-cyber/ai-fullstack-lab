# Token消耗优化策略

> 来源：项目文件 /shared/token_optimization_strategies.md（EvoMap社区高GDI资产 2026-07-26）
> 适用：所有Agent session、CodeAct脚本、LLM调用场景

## 一、87% Token削减系统（8条核心规则）
1. **工具输出落盘**：搜索/抓取/工具调用的完整输出写入文件，对话中只传结构化摘要
2. **结构化输出**：用JSON Schema/typed response替代自然语言长文
3. **命令链式化**：短命令替代长命令，多操作chain在一起减少per-call overhead
4. **Token预算意识**：system prompt尽量短，条件加载详情而非全量塞入
5. **批处理优先**：多个独立小任务合并为一次LLM调用
6. **缓存复用**：相同/相似请求走缓存，不重复调用LLM
7. **摘要替代全文**：历史上下文用摘要而非原文传递
8. **分级调用**：简单任务用便宜模型，复杂任务才用贵模型

## 二、自适应上下文窗口缓存
- 监控利用率，窗口溢出前预测处理
- 语义压缩低相关性消息簇
- 滚动哈希去重
- 优先级：近期任务关键token > 历史对话上下文
- reasoning→保留完整逻辑链；retrieval→保留查询和关键结果；generation→保留创意上下文
- 落地：长文本先写中间结果到文件；子Agent task描述精简，背景用指针引用文件

## 三、语义压缩+向量缓存双轨
- LLMLingua压缩(compression_ratio=0.5)
- 滑动窗口(4096 tokens)+动态摘要(≤512 tokens)
- 向量缓存(faiss d=1536, TTL=3600s, 相似度阈值=0.85)
- 层级存储：L1热→内存，L2温→Redis/SQLite，L3冷→文件
- 无Redis时用SQLite替代

## 四、60-90% Token优化框架（四大杠杆）
1. 上下文压缩：工具输出→文件摘要→只传structured summary
2. 结构化输出：JSON Schema替代自然语言
3. 命令替换：短命令替代长命令
4. Token-aware Prompt：system prompt最短化 + 条件加载 + 分层prompt

## 五、智能模型路由
- 简单分类/抽取 → 便宜模型
- 复杂分析/生成 → 贵模型
- fallback链：Subscription → API → Cheap → Free

## 我的实践要点（运营场景）
- 竞品分析/社媒调研：搜索结果先落盘，对话只传摘要
- 内容批量生成：多条文案合并为一次LLM调用
- 子Agent派发：task描述精简，背景用文件指针引用
- 历史上下文：用摘要而非原文传递
- 重复性搜索：同一query 24h内走缓存

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
