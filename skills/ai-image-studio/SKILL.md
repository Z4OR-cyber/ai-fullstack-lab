---
name: ai-image-studio
description: 多引擎AI图片生成技能，集成GPT Image 2、FLUX 2、Google Nano Banana、Qwen Image 2 Pro、Midjourney(代理)五大引擎。当用户需要生成图片、AI作图、出图、画图、生成封面、生成素材、UI素材、海报设计、概念图、产品图、头像、壁纸、插画、图标等任何图片生成需求时使用此技能。支持指定引擎、尺寸、风格、批量生成、图生图、图片编辑。
---

# AI作图工坊 — 多引擎图片生成

调用 5 大 AI 图片生成引擎，根据用户需求自动选择最优引擎或按用户指定引擎出图。

## 引擎能力矩阵

| 引擎 | 最强场景 | 速度 | 中文支持 |
|------|---------|------|---------|
| GPT Image 2 | 对话式迭代、Prompt理解力、概念设计 | 中 | 中 |
| FLUX 2 Pro | 写实摄影、文字渲染、海报设计 | 快 | 中 |
| Nano Banana | 4K大图、真实人脸、自然光影 | 快 | 弱 |
| Qwen Image 2 | 中文场景、传统文化、多语种 | 快 | 最强 |
| Midjourney | 审美天花板、艺术风格、概念设计 | 慢 | 弱 |

## 引擎选择逻辑

根据用户需求自动推荐引擎：
- 用户说"中文/国风/传统/水墨/书法" → Qwen Image 2
- 用户说"海报/文字/标题/排版" → FLUX 2 Pro
- 用户说"4K/高清/大图/壁纸" → Nano Banana
- 用户说"帮我改/调整/迭代" → GPT Image 2（对话式）
- 用户说"最美/艺术/概念/氛围" → Midjourney
- 用户未指定 → 默认 FLUX 2 Pro（性价比最高）

用户明确指定引擎时，直接按指定执行，不做替换。

## 工作流程

### 1. 解析需求
从用户输入中提取：
- **prompt**: 图片描述（中文需翻译为英文，Qwen引擎除外）
- **engine**: 目标引擎（未指定则按上述逻辑推荐）
- **size**: 尺寸（默认 1024x1024）
- **count**: 数量（默认 1）
- **style**: 风格修饰词

### 2. 调用生成
执行 `python main.py` 并传入参数：
```bash
python main.py --prompt "描述" --engine flux --size 1024x1024 --count 1
```

### 3. 返回结果
脚本输出图片的本地路径，将图片展示给用户。

## 参数说明

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| --prompt | 是 | 图片描述 | "赛博朋克城市夜景" |
| --engine | 否 | 引擎名: gpt/flux/google/qwen/mj | 默认 flux |
| --size | 否 | 输出尺寸 | 1024x1024, 1024x1792, 1792x1024 |
| --count | 否 | 生成数量 | 1-4 |
| --output | 否 | 输出目录 | 默认 ./output |
| --negative | 否 | 负面提示词 | "模糊,低质量" |

## 凭据说明

### 实际架构（v6+）
由于sandbox网络限制（Google/OpenAI API域名被封锁），4个引擎统一通过Apiframe v2代理调用，FLUX保留BFL直连：

| 引擎 | 调用路径 | 凭证 |
|------|---------|------|
| GPT Image 2 | Apiframe v2 (`gpt-image-2` 模型) | `mj_proxy` |
| FLUX 2 Pro | BFL 直连 (api.bfl.ai) | `bfl_key` |
| Nano Banana | Apiframe v2 (`nano-banana` 模型) | `mj_proxy` |
| Qwen Image 2 | Apiframe v2 (`qwen-image-2-pro` 模型) | `mj_proxy` |
| Midjourney | Apiframe v2 (`midjourney` 模型) | `mj_proxy` |

### 凭证列表
- `mj_proxy`: Apiframe v2 API Key（覆盖 GPT/Nano Banana/Qwen/MJ 四个引擎）
  - domain: api.apiframe.ai
  - 认证方式: Header `X-API-Key`（无Bearer前缀）
  - API格式: POST /v2/images/generate + GET /v2/jobs/:id 轮询
- `bfl_key`: BFL API Key（FLUX 2 Pro 直连）
  - domain: api.bfl.ai
  - 认证方式: Header `x-key`
  - API格式: POST /v1/flux-2-pro-preview + 轮询 polling_url
- `google_image`: Google AI API Key（因网络封锁目前闲置）
  - domain: generativelanguage.googleapis.com

### 凭证值机制
凭证环境变量值为 `COZE_CRED_DUMMY_xxx` 占位符，由 outbound auth proxy 自动替换为真实值。代码中**不能**过滤 dummy 值，直接使用 `os.getenv()` 返回值。

未配置的引擎会跳过，不影响其他引擎使用。

## 边界情况

- Prompt 过长时自动截断至引擎限制内
- API 返回错误时输出具体错误信息，不静默失败
- 无凭据的引擎给出明确提示，引导用户配置
