---
name: docx
description: "全面的文档创建、编辑和分析功能，支持修订追踪、批注、格式保留和文本提取。当用户需要处理word文档（.docx 文件）时使用，包括：(1) 创建新文档，(2) 修改或编辑内容，(3) 处理修订追踪，(4) 添加批注，或其他文档任务"
dependency:
  python:
    - defusedxml>=0.7.1
    - lxml>=4.9.0
---

# DOCX 文档创建、编辑和分析

## 概述

用户可能会要求你创建、编辑或分析 .docx 文件的内容。.docx 文件本质上是一个包含 XML 文件和其他资源的 ZIP 压缩包，你可以读取或编辑这些内容。针对不同的任务，你有不同的工具和工作流可供选择。

## 工作流决策树

### 读取/分析内容
使用下方的"文本提取"或"原始 XML 访问"章节

### 创建新文档
使用"创建新 Word 文档"工作流

### 编辑现有文档
- **自己的文档 + 简单修改**
  使用"基础 OOXML 编辑"工作流

- **他人的文档**
  使用**"修订追踪工作流"**（推荐默认选项）

- **法律、学术、商业或政府文档**
  使用**"修订追踪工作流"**（必须）

## 读取和分析内容

### 文本提取
如果你只需要读取文档的文本内容，应该使用 pandoc 将文档转换为 markdown。Pandoc 对保留文档结构有出色的支持，并可以显示修订追踪：

```bash
# 将文档转换为带修订追踪的 markdown
pandoc --track-changes=all path-to-file.docx -o output.md
# 选项：--track-changes=accept/reject/all
```

### 原始 XML 访问
对于以下功能，你需要原始 XML 访问：批注、复杂格式、文档结构、嵌入媒体和元数据。对于这些功能，你需要解压文档并读取其原始 XML 内容。

#### 解压文件
`python ooxml/scripts/unpack.py <office_file> <output_directory>`

#### 关键文件结构
* `word/document.xml` - 主文档内容
* `word/comments.xml` - document.xml 中引用的批注
* `word/media/` - 嵌入的图片和媒体文件
* 修订追踪使用 `<w:ins>`（插入）和 `<w:del>`（删除）标签

## 创建新 Word 文档

从零开始创建新 Word 文档时，使用 **docx-js**，它允许你使用 JavaScript/TypeScript 创建 Word 文档。

### 工作流
1. **必须 - 阅读完整文件**：完整阅读 [`docx-js.md`](docx-js.md)（约 500 行），从头到尾。**阅读此文件时切勿设置任何范围限制。** 在开始创建文档之前，阅读完整文件内容以了解详细语法、关键格式规则和最佳实践。
2. 使用 Document、Paragraph、TextRun 组件创建 JavaScript/TypeScript 文件（可以假设所有依赖已安装，如未安装，请参考下方的依赖项章节）
3. 使用 Packer.toBuffer() 导出为 .docx

## 编辑现有 Word 文档

编辑现有 Word 文档时，使用 **Document 库**（一个用于 OOXML 操作的 Python 库）。该库自动处理基础设施设置，并提供文档操作方法。对于复杂场景，你可以通过该库直接访问底层 DOM。

### 工作流
1. **必须 - 阅读完整文件**：完整阅读 [`ooxml.md`](ooxml.md)（约 600 行），从头到尾。**阅读此文件时切勿设置任何范围限制。** 阅读完整文件内容以了解 Document 库 API 和直接编辑文档文件的 XML 模式。
2. 解压文档：`python ooxml/scripts/unpack.py <office_file> <output_directory>`
3. 使用 Document 库创建并运行 Python 脚本（参见 ooxml.md 中的"Document 库"章节）
4. 打包最终文档：`python ooxml/scripts/pack.py <input_directory> <office_file>`

Document 库提供了用于常见操作的高级方法，以及用于复杂场景的直接 DOM 访问。

## 文档审阅的修订追踪工作流

此工作流允许你在实施 OOXML 之前，先使用 markdown 规划全面的修订追踪。**关键**：要完成完整的修订追踪，你必须系统地实施所有修改。

**批量处理策略**：将相关修改分组为 3-10 个修改的批次。这使调试变得可控，同时保持效率。在进入下一批之前测试每个批次。

**原则：最小化、精确编辑**
实施修订追踪时，只标记实际更改的文本。重复未更改的文本会使编辑更难审阅，显得不专业。将替换拆分为：[未更改文本] + [删除] + [插入] + [未更改文本]。通过提取原始 `<w:r>` 元素并重用它，保留原始 run 的 RSID 用于未更改的文本。

示例 - 在句子中将"30 天"改为"60 天"：
```python
# 错误 - 替换整个句子
'<w:del><w:r><w:delText>期限为 30 天。</w:delText></w:r></w:del><w:ins><w:r><w:t>期限为 60 天。</w:t></w:r></w:ins>'

# 正确 - 只标记更改的部分，为未更改文本保留原始 <w:r>
'<w:r w:rsidR="00AB12CD"><w:t>期限为 </w:t></w:r><w:del><w:r><w:delText>30</w:delText></w:r></w:del><w:ins><w:r><w:t>60</w:t></w:r></w:ins><w:r w:rsidR="00AB12CD"><w:t> 天。</w:t></w:r>'
```

### 修订追踪工作流

1. **获取 markdown 表示**：将文档转换为保留修订追踪的 markdown：
   ```bash
   pandoc --track-changes=all path-to-file.docx -o current.md
   ```

2. **识别并分组修改**：审阅文档并识别所有需要的修改，将它们组织成逻辑批次：

   **定位方法**（用于在 XML 中查找修改）：
   - 章节/标题编号（例如"第 3.2 节"、"第四条"）
   - 段落标识符（如有编号）
   - 使用唯一周围文本的 grep 模式
   - 文档结构（例如"第一段"、"签名区"）
   - **不要使用 markdown 行号** - 它们不对应 XML 结构

   **批次组织**（每批分组 3-10 个相关修改）：
   - 按章节："批次 1：第 2 节修订"、"批次 2：第 5 节更新"
   - 按类型："批次 1：日期修正"、"批次 2：当事方名称变更"
   - 按复杂度：从简单的文本替换开始，然后处理复杂的结构性更改
   - 按顺序："批次 1：第 1-3 页"、"批次 2：第 4-6 页"

3. **阅读文档并解压**：
   - **必须 - 阅读完整文件**：完整阅读 [`ooxml.md`](ooxml.md)（约 600 行），从头到尾。**阅读此文件时切勿设置任何范围限制。** 特别注意"Document 库"和"修订追踪模式"章节。
   - **解压文档**：`python ooxml/scripts/unpack.py <file.docx> <dir>`
   - **记下建议的 RSID**：解压脚本会建议一个用于修订追踪的 RSID。复制此 RSID 供步骤 4b 使用。

4. **分批实施修改**：按逻辑分组修改（按章节、按类型或按邻近度），并在单个脚本中一起实施。这种方法：
   - 使调试更容易（更小的批次 = 更容易隔离错误）
   - 允许渐进式进展
   - 保持效率（3-10 个修改的批次大小效果好）

   **建议的批次分组**：
   - 按文档章节（例如"第 3 节修改"、"定义"、"终止条款"）
   - 按修改类型（例如"日期修改"、"当事方名称更新"、"法律术语替换"）
   - 按邻近度（例如"第 1-3 页的修改"、"文档前半部分的修改"）

   对于每批相关修改：

   **a. 将文本映射到 XML**：在 `word/document.xml` 中 grep 文本，以验证文本如何分布在 `<w:r>` 元素中。

   **b. 创建并运行脚本**：使用 `get_node` 查找节点，实施修改，然后 `doc.save()`。参见 ooxml.md 中的**"Document 库"**章节了解模式。

   **注意**：始终在编写脚本之前立即 grep `word/document.xml`，以获取当前行号并验证文本内容。每次脚本运行后行号都会改变。

5. **打包文档**：所有批次完成后，将解压目录转换回 .docx：
   ```bash
   python ooxml/scripts/pack.py unpacked reviewed-document.docx
   ```

6. **最终验证**：对完整文档进行全面检查：
   - 将最终文档转换为 markdown：
     ```bash
     pandoc --track-changes=all reviewed-document.docx -o verification.md
     ```
   - 验证所有修改是否正确应用：
     ```bash
     grep "原始短语" verification.md  # 应该找不到
     grep "替换短语" verification.md  # 应该找到
     ```
   - 检查是否引入了意外的修改


## 将文档转换为图片

要可视化分析 Word 文档，使用两步流程将其转换为图片：

1. **将 DOCX 转换为 PDF**：
   ```bash
   soffice --headless --convert-to pdf document.docx
   ```

2. **将 PDF 页面转换为 JPEG 图片**：
   ```bash
   pdftoppm -jpeg -r 150 document.pdf page
   ```
   这会创建 `page-1.jpg`、`page-2.jpg` 等文件。

选项：
- `-r 150`：设置分辨率为 150 DPI（根据质量/大小平衡调整）
- `-jpeg`：输出 JPEG 格式（如需 PNG 请使用 `-png`）
- `-f N`：从第 N 页开始转换（例如 `-f 2` 从第 2 页开始）
- `-l N`：转换到第 N 页为止（例如 `-l 5` 到第 5 页停止）
- `page`：输出文件的前缀

指定范围的示例：
```bash
pdftoppm -jpeg -r 150 -f 2 -l 5 document.pdf page  # 仅转换第 2-5 页
```

## 代码风格指南
**重要**：生成 DOCX 操作代码时：
- 编写简洁的代码
- 避免冗长的变量名和冗余操作
- 避免不必要的 print 语句

## 依赖项

需要的依赖项（如不可用请安装）：

- **pandoc**：`sudo apt-get install pandoc`（用于文本提取）
- **docx**：`npm install -g docx`（用于创建新文档）
- **LibreOffice**：`sudo apt-get install libreoffice`（用于 PDF 转换）
- **Poppler**：`sudo apt-get install poppler-utils`（用于 pdftoppm 将 PDF 转换为图片）
- **defusedxml**：`pip install defusedxml`（用于安全的 XML 解析）
