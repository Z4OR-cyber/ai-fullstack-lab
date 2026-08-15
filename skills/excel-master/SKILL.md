---
name: excel_master
description: 当用户任务涉及 Excel 文件（.xlsx、.xls、.xlsm）、CSV、表格清洗、批量填充、格式保留修改、表格分析或基于表格的批量 NLP / 搜索时，优先使用本技能。它提供一套清晰的 Excel 工作流，覆盖数据探索、需求拆解、策略选型、质量校验与产物交付。
dependency:
  python:
    - openpyxl==3.1.2
    - pandas==2.0.0
    - httpx==0.24.1
---

# Excel Expert

在遵守全局指令、仓库规范和执行环境限制的前提下，优先按本技能的 Excel 工作流执行。

请始终遵守以下原则：

1. 严禁伪造、模拟或臆测数据。
2. 用户未指定报告格式时，默认使用 Markdown，不使用 `.txt`。
3. 默认在用户当前 workspace 中工作；临时文件可写入 `/tmp`；不要假设 home 目录或任意系统目录可写。
4. 本技能附带的文档位于 `references/`，可复用代码位于 `scripts/`；引用资源时优先基于 `SKILL_DIR` 拼接绝对路径。
5. 如果只是简单查看某个 sheet、回答列名、统计几行几列，可轻量处理；只有在分析、批处理、格式保留修改、批量搜索或批量 NLP 场景下，才执行完整 SOP。

## When To Trigger

遇到以下需求时，优先使用本技能，即使用户没有显式说“Excel”：

- 处理 `.xlsx`、`.xls`、`.xlsm`、`.csv`
- 修改表格、补列、批量填值、做分析、导出结果文件
- 保留模板样式、改公式、按行匹配并回填
- 对表格中的文本列逐行做分类、抽取、翻译、摘要、标签生成
- 需要把分析结果写回表格并附带 Markdown 报告

# 核心工作流

## 1. 数据探索（EDA）

在开始处理前，先完整理解输入文件的结构和边界：

- 使用当前运行时提供的本地文件读取能力或终端命令能力查看文件。
- 如果输入是 Excel / 表格文件，必须先确认所有 sheet 名称，避免遗漏。
- 不要只看前 5 行；若表头混乱、存在空行、合并单元格或多层表头，要扩大预览范围。
- 对 DataFrame 预览时，优先展示全部列，避免因列折叠漏看字段。

示例：

```python
import pandas as pd

pd.set_option("display.max_columns", None)
print(df.head(10))
```

需要掌握的信息至少包括：

- 多 sheet 之间的关系
- 表头和字段定义
- 数据量级
- 空值、异常值、重复值、错位风险

## 2. 需求拆解

先把用户目标拆成清晰的编号列表，再开始执行。

- 后续动作要逐项对齐需求列表，避免遗漏。
- 如果用户要求“分析一下”“多维度看看”“做个报告”，默认补充图表、结论和关键发现。
- 如需图表，可直接使用 Python 生成图表并导出图片，再在 Markdown 报告中引用。

## 3. 能力研判

根据任务类型，按需读取本技能的专用能力文档：

- NLP 任务：`SKILL_DIR/references/batch_nlp.md`
- 联网搜索 / 外部事实补全：`SKILL_DIR/references/batch_search_analysis.md`
- 复杂 Excel 操作 / 模板填充 / 公式与格式保留：`SKILL_DIR/references/excel_api.md`

如果任务命中上述场景，不要跳过对应文档。

以下情况一旦命中，直接视为 NLP 任务：

- 对某一列或多列文本逐行做分类、标签、情感判断、摘要、翻译、抽取、改写
- 根据自然语言描述为每行生成结构化字段
- 需要从评论、公告、简历、合同、工单、对话中提取语义信息

命中后，先读取 `SKILL_DIR/references/batch_nlp.md`，再决定实现方式；不要先写正则、`if/else` 或 `pandas.apply(lambda ...)` 硬做。

## 4. 策略选择

根据数据特征选工具：

- `pandas`：标准表头、分析统计、批量筛选、聚合、大数据量处理
- `openpyxl`：复杂表头、合并单元格、样式保留、模板微调、公式修改

处理复杂格式时，应尽量在原文件基础上修改并另存，不要轻易重建整份工作簿。

## 5. 结果审查

交付前必须做 QA：

- 抽样检查头部、中部、尾部的多行数据
- 对比源文件与结果文件的行列数量
- 检查空值、错位、公式失效、sheet 丢失、编码问题
- 若产出了报告，确认结论与结果文件一致

## 6. 结果交付

最终答复中应包含：

- 产物内容的简要说明
- 做过哪些验证
- 生成文件的绝对路径

默认交付方式：

- 数据结果：`.xlsx` 或用户指定格式
- 复杂报告：`.md`
- 图表：优先生成可复核、可落盘的图片文件

## Report Structure

当用户要求“分析”“总结”“做报告”且未指定结构时，默认使用以下模板：

```markdown
# 分析结果
## 处理范围
## 关键发现
## 明细说明
## 产物说明
## 验证情况
```

# NLP 任务特别准则

涉及情感分析、摘要、抽取、翻译、改写、分类、标签生成等语义任务时，遵循“模型理解优先，而非字符串拼接”原则。

禁止事项：

- 不要用 `if/else` 关键词匹配冒充语义理解
- 不要用正则表达式替代真正的语义抽取
- 不要用词频统计替代 LLM 判断

强制事项：

- 如果是“对表格中的文本逐行做语义处理”，先阅读 `SKILL_DIR/references/batch_nlp.md`
- 优先使用文档中定义的批量能力
- 如果批量接口不可用，则使用可验证的替代方案，并在结果中说明处理方式

# Python 数据处理规范

## 常用库

优先使用已具备或常见的数据处理库：

- `pandas`
- `openpyxl`
- `matplotlib`
- `xlrd`
- `PyPDF2`
- `python-docx`
- `python-pptx`
- `odfpy`

## 运行方式

- 探索阶段可使用短命令快速验证
- 正式处理时，优先把处理脚本写到 workspace 中执行
- 如果修改了仓库文件，按仓库规范执行必要的格式化和验证

推荐执行模式：

```bash
SKILL_DIR="<skill_base_dir>" PYTHONPATH="$SKILL_DIR/scripts" python <workspace_script.py>
```

含义：

- 临时脚本和结果文件留在 workspace
- skill 自带模块从 `SKILL_DIR/scripts` 导入
- 不依赖当前工作目录碰巧等于技能目录

## 修改与提取

- 修改 / 填表：优先 `openpyxl`，避免破坏原始格式
- 内容提取：优先直接读取，不要无意义地堆复杂正则

## 异常处理

- 认真阅读 Traceback
- 遇到 `KeyError` / `ValueError` 时，先检查列名隐藏空格、重复列名和特殊字符
- 用户输入若存在轻微笔误，可结合文件内容做合理纠偏；若影响结果正确性，再向用户确认

# 路径与资源

本 skill 的资源路径相对于 skill 根目录解析：

- `SKILL_DIR/references/batch_nlp.md`
- `SKILL_DIR/references/batch_search_analysis.md`
- `SKILL_DIR/references/excel_api.md`

如果需要调用本技能附带的 Python 模块，优先保留脚本在 workspace，并通过 `PYTHONPATH="$SKILL_DIR/scripts"` 暴露模块路径。

# 批量能力说明

本技能目录中包含对内部 workflow API 的 Python 封装，可用于批量 NLP 和批量搜索分析。这些能力依赖：

- 可用的 `identity_ticket`
- 可用的网络访问

如果上述条件不满足：

- NLP 任务使用其他可验证的语义处理方案
- 实时搜索任务使用可用的联网检索能力

## 产物路径建议

- 优先写入用户当前 workspace
- 临时中间文件写入 `/tmp`
- 最终答复必须给出绝对路径

## 技能基础目录

技能加载后，会得到一个技能基础目录。所有 bundled 资源都应视为位于 `SKILL_DIR` 下，例如：

- `SKILL.md`
- `references/batch_nlp.md`
- `references/batch_search_analysis.md`
- `references/excel_api.md`
- `scripts/llm_api.py`
- `scripts/web_search_api.py`
- `scripts/excel_api.py`

推荐约定：

- `SKILL_DIR`：技能基础目录
- `SKILL_DIR/references`：按需读取的文档
- `SKILL_DIR/scripts`：可复用的 Python 模块
- `workspace`：存放模型生成的临时脚本、结果文件、报告文件

推荐执行方式：

```bash
SKILL_DIR="<skill_base_dir>" PYTHONPATH="$SKILL_DIR/scripts" python <workspace_script.py>
```
