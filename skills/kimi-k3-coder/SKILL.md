---
name: kimi-k3-coder
description: 通过Kimi K3 API完成编码任务。当需要K3帮忙写代码、实现功能、完成开发任务、生成HTML/CSS/JS、编写游戏逻辑、前端开发、代码审查、生成方案代码时使用。支持传入任务描述和上下文代码，返回K3的代码方案。
---

# Kimi K3 编码助手

通过调用 Kimi K3（月之暗面旗舰模型，2.8T MoE，1M上下文）完成编码任务。K3在前端代码Arena排名第一，适合HTML/CSS/JS单文件游戏开发。

## 工作流程

1. 读取用户提供的任务描述和可选的上下文代码
2. 构造 system prompt：指定K3为前端开发专家，要求只输出代码，不要多余解释
3. 调用 Kimi K3 API（OpenAI兼容格式）
4. 返回K3生成的代码内容

## 使用方式

```bash
python main.py --task "任务描述" [--context "上下文代码或文件路径"] [--max-tokens 8192]
```

### 参数说明

- `--task`（必填）：编码任务描述，如"实现一个牌堆查看面板，点击抽牌堆显示剩余卡牌列表"
- `--context`（可选）：上下文代码，可以传文件路径或直接传代码文本。K3有1M上下文，可以传入完整文件
- `--max-tokens`（可选）：最大输出token数，默认8192。K3是强制思考模式，实际输出约为max_tokens的70%
- `--system`（可选）：自定义system prompt，默认为前端开发专家

### 输出

- 成功：将K3生成的代码内容输出到stdout，同时保存到 `kimi_k3_output.txt`
- 失败：输出错误信息到stderr

## 注意事项

- K3是强制思考模式（always thinking），会消耗较多token在推理上，max_tokens建议设大一些
- K3引擎可能过载（engine_overloaded_error），脚本会自动重试3次，每次间隔递增
- 缓存命中率通常>90%，重复上下文的请求成本很低
