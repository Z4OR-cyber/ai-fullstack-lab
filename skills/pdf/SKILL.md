---
name: pdf
description: 提供PDF文本表格提取、创建编辑、合并拆分、表单填写等全面处理能力；当需要提取PDF内容、生成新文档、批量处理PDF文件或填写PDF表单时使用
dependency:
  python:
    - pypdf>=4.0.0
    - pdfplumber>=0.11.0
    - reportlab>=4.0.0
    - pdf2image>=1.17.0
    - Pillow>=10.0.0
---
# PDF处理指南


## 目录

- [概述](#概述)
- [快速开始](#快速开始)
- [Python库](#python库)
  - [pypdf - 基本操作](#pypdf---基本操作)
  - [pdfplumber - 文本和表格提取](#pdfplumber---文本和表格提取)
  - [PDF创建设计流程](#pdf创建设计流程)
  - [reportlab - 创建PDF](#reportlab---创建pdf)
- [命令行工具](#命令行工具)
- [常见任务](#常见任务)
- [快速参考](#快速参考)
- [下一步](#下一步)

## 概述

本指南涵盖使用Python库和命令行工具进行的基本PDF处理操作。有关高级功能、JavaScript库和详细示例，请参阅[references/reference.md](references/reference.md)。如果需要填写PDF表单，请阅读[references/forms.md](references/forms.md)并按照其说明操作。

## 快速开始

```python
from pypdf import PdfReader, PdfWriter

# 读取PDF
reader = PdfReader("document.pdf")
print(f"页数: {len(reader.pages)}")

# 提取文本
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python库
#### 错误处理建议

在处理PDF时，建议添加适当的错误处理机制：

```python
try:
    # PDF操作代码
    reader = PdfReader("document.pdf")
except Exception as e:
    print(f"处理PDF时出错: {e}")
```



### pypdf - 基本操作

#### 合并PDF

```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### 拆分PDF

```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### 提取元数据

```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"标题: {meta.title}")
print(f"作者: {meta.author}")
print(f"主题: {meta.subject}")
print(f"创建者: {meta.creator}")
```

#### 旋转页面

```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

page = reader.pages[0]
page.rotate(90)  # 顺时针旋转90度
writer.add_page(page)

with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber - 文本和表格提取

#### 提取文本

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        print(f"第 {i+1} 页: {len(text)} 个字符")
```

#### 提取表格

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for table in tables:
            print(table)
```

#### 检测布局重叠

检测PDF中文字元素是否存在位置重叠，避免生成内容覆盖问题：

```bash
python scripts/check_layout_overlap.py document.pdf
```

该脚本会：
- 提取PDF中所有文字块的位置信息
- 检测文字块之间的重叠情况
- 输出详细的重叠报告，包括重叠文字、页码、位置坐标和重叠度

输出示例：
```
文件: document.pdf
检测到 150 个文字块

SUCCESS: 未检测到文字重叠，布局正常
```

或

```
文件: document.pdf
检测到 150 个文字块

发现 2 处重叠:
--------------------------------------------------
  '标题' 与 '副标题'
     页码: 1 | 重叠度: 25.5%
     位置1: Y=750.0-735.0, X=100.0-200.0
     位置2: Y=745.0-730.0, X=105.0-205.0

建议: 调整元素间距，确保各文字块不重叠
```

### PDF创建设计流程

在开始创建PDF之前，必须完成以下设计步骤，以确保生成的PDF无中文字体乱码、元素覆盖、展示信息不全、美观度不够等问题。

#### 第一步：需求分析

在开始设计前，先明确以下关键信息：

1. **文档类型**：报告、合同、邀请函、证书、票据等
2. **目标受众**：中文用户、英文用户、双语用户
3. **内容结构**：
   - 标题层级（主标题、副标题、章节标题等）
   - 正文内容
   - 表格、图表、图片等辅助元素
   - 页眉页脚（页码、日期、公司Logo等）
4. **页面规格**：
   - 纸张大小（A4、Letter、自定义等）
   - 页边距（上下左右）
   - 横向或纵向
5. **美观要求**：简约、正式、创意、商务等风格

#### 第二步：页面布局设计

基于需求分析结果，设计页面布局：

1. **确定页面尺寸和边距**

```python
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch, cm

# 示例：A4纸张，边距设置
pagesize = A4
margin_top = 2 * cm
margin_bottom = 2 * cm
margin_left = 2 * cm
margin_right = 2 * cm

# 计算可用区域
width, height = pagesize
content_width = width - margin_left - margin_right
content_height = height - margin_top - margin_bottom
```

2. **规划内容区域**

```python
# 示例：页面区域划分
regions = {
    'header': {
        'y_start': height - margin_top,
        'y_end': height - margin_top - 1.5 * cm,
        'description': '页眉区域，放置标题、Logo等'
    },
    'body': {
        'y_start': height - margin_top - 1.5 * cm - 0.5 * cm,
        'y_end': margin_bottom + 1.5 * cm,
        'description': '正文区域，放置主要内容'
    },
    'footer': {
        'y_start': margin_bottom,
        'y_end': margin_bottom + 1.5 * cm,
        'description': '页脚区域，放置页码、日期等'
    }
}
```

3. **设计元素位置**

为每个元素预留坐标位置：

```python
# 示例：元素位置规划
elements = [
    {
        'type': 'title',
        'text': '文档标题',
        'x': margin_left,
        'y': regions['header']['y_end'],
        'font': 'TitleFont',
        'size': 24,
        'color': (0, 0, 0)
    },
    {
        'type': 'paragraph',
        'text': '正文内容',
        'x': margin_left,
        'y': regions['body']['y_start'],
        'font': 'BodyFont',
        'size': 12,
        'color': (0, 0, 0)
    }
]
```

#### 第三步：字体选择

**中文字体选择（解决乱码问题）**

根据系统环境选择合适的中文字体：

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 常用中文字体路径
chinese_fonts = {
    'WenQuanYiMicroHei': '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    'WenQuanYiZenHei': '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            'SimSun': '/usr/share/fonts/truetype/simsun.ttc',
    'SimHei': '/usr/share/fonts/truetype/simhei.ttf'
}

# 注册并选择可用的中文字体
def register_chinese_font():
    """注册可用的中文字体"""
    available_fonts = []
    for font_name, font_path in chinese_fonts.items():
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                available_fonts.append(font_name)
                print(f"已注册字体: {font_name}")
            except Exception as e:
                print(f"注册字体失败 {font_name}: {e}")
    return available_fonts

# 使用示例
available_fonts = register_chinese_font()
if available_fonts:
    chinese_font = available_fonts[0]  # 使用第一个可用的字体
else:
    print("警告: 未找到可用的中文字体，可能存在乱码问题")
    chinese_font = 'Helvetica'  # 降级使用英文字体
```

#### 第四步：样式设计

定义统一的样式体系，确保美观度和一致性：

```python
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.colors import HexColor

# 创建自定义样式
styles = getSampleStyleSheet()

# 标题样式
styles.add(ParagraphStyle(
    name='CustomTitle',
    fontName='WenQuanYiZenHei',
    fontSize=24,
    leading=30,
    spaceAfter=20,
    alignment=TA_CENTER,
    textColor=HexColor('#333333')
))

# 章节标题样式
styles.add(ParagraphStyle(
    name='CustomHeading1',
    fontName='WenQuanYiZenHei',
    fontSize=18,
    leading=24,
    spaceAfter=12,
    spaceBefore=18,
    textColor=HexColor('#333333')
))

# 正文样式
styles.add(ParagraphStyle(
    name='CustomBody',
    fontName='WenQuanYiMicroHei',
    fontSize=12,
    leading=18,
    spaceAfter=10,
    alignment=TA_LEFT,
    textColor=HexColor('#666666')
))

# 强调文本样式
styles.add(ParagraphStyle(
    name='CustomEmphasis',
    fontName='WenQuanYiMicroHei',
    fontSize=12,
    leading=18,
    textColor=HexColor('#E63946'),
    fontName='WenQuanYiZenHei'
))

# 页眉页脚样式
styles.add(ParagraphStyle(
    name='CustomFooter',
    fontName='WenQuanYiMicroHei',
    fontSize=10,
    leading=14,
    alignment=TA_CENTER,
    textColor=HexColor('#999999')
))
```

**配色方案**

```python
# 推荐配色方案
color_schemes = {
    '简约黑白': {
        'primary': '#333333',
        'secondary': '#666666',
        'accent': '#999999',
        'background': '#FFFFFF'
    },
    '商务蓝': {
        'primary': '#1E3A8A',
        'secondary': '#3B82F6',
        'accent': '#93C5FD',
        'background': '#FFFFFF'
    },
    '温暖橙': {
        'primary': '#9A3412',
        'secondary': '#EA580C',
        'accent': '#FDBA74',
        'background': '#FFFFFF'
    }
}
```

#### 第五步：设计验证

完成设计后，必须进行以下验证：

1. **创建测试PDF**

根据设计方案创建测试PDF：

```python
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

def create_test_pdf(output_path, design_data):
    """创建测试PDF以验证设计"""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=design_data['pagesize'],
        leftMargin=design_data['margin_left'],
        rightMargin=design_data['margin_right'],
        topMargin=design_data['margin_top'],
        bottomMargin=design_data['margin_bottom']
    )
    
    story = []
    # 添加测试内容...
    
    doc.build(story)
    return output_path
```

2. **检测元素覆盖**

使用布局重叠检测工具：

```bash
python scripts/check_layout_overlap.py test_design.pdf
```

如果发现重叠，返回第二步调整布局设计。

3. **视觉检查**

```bash
# 将PDF转换为图片进行视觉检查
python scripts/convert_pdf_to_images.py test_design.pdf ./test_output
```

检查：
- ✓ 中文字体显示正常，无乱码
- ✓ 文字清晰可读，字号合适
- ✓ 元素无覆盖、无越界
- ✓ 页面布局美观大方
- ✓ 对齐方式正确
- ✓ 间距合理
- ✓ 配色协调

#### 第六步：从Markdown/Text内容创建PDF

**重要原则**：即使输入是Markdown或纯文本格式，也不能使用pandoc、weasyprint等工具直接转换。不使用任何解析或匹配方式，而是【reportlab - 创建PDF】一样直接逐行硬编码构建PDF内容。需要将给定的Markdown文档内容，直接将文档的每个元素按照其类型硬编码创建对应的Paragraph、Table、Spacer等对象。然后逐一创建对应的ReportLab元素。

**禁止使用的工具**：
- **禁止使用** `pandoc` 直接转换Markdown到PDF
- **禁止使用** `weasyprint` 直接转换HTML/Markdown到PDF
- **禁止使用** 其他一键转换工具

**正确流程**：
1. 读取Markdown/Text内容
2. 参考 [Markdown样式集合](references/Markdown%20样式集合.md) 了解完整的Markdown语法规范
3. 直接编写Platypus代码，手动逐行硬编码构建PDF，构建的PDF要完整还原markdown的样式。

### reportlab - 创建PDF

**重要提示**：在创建PDF之前，请务必先完成上面的"PDF创建设计流程"章节中的所有步骤，以避免出现中文字体乱码、元素覆盖、展示信息不全、美观度不够等问题。

#### 使用Canvas创建简单PDF

```python
from reportlab.pdfgen import canvas

c = canvas.Canvas("simple.pdf")

# 设置字体
c.setFont("Helvetica", 16)

# 添加文本
c.drawString(100, 750, "Hello World")

# 添加线条
c.line(100, 740, 500, 740)

# 保存
c.save()
```

#### 使用Platypus创建复杂文档

```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

# 添加内容
title = Paragraph("报告标题", styles['Title'])
story.append(title)
story.append(Spacer(1, 12))

body = Paragraph("这是报告的正文。 " * 20, styles['Normal'])
story.append(body)
story.append(PageBreak())

# 第2页
story.append(Paragraph("第2页", styles['Heading1']))
story.append(Paragraph("第2页的内容", styles['Normal']))

# 构建PDF
doc.build(story)
```


#### 字体支持

本技能支持以下字体，适用于中文和英文文档创建：

**中文字体（支持简体中文）**

- **WenQuanYi Micro Hei**：文泉驿微米黑，轻量级无衬线中文字体（推荐使用）
- **WenQuanYi Zen Hei**：文泉驿正黑，经典无衬线中文字体（推荐使用）
- **SimSun**：宋体，传统衬线中文字体
- **SimHei**：黑体，无衬线中文字体

> **注意**：Noto系列CJK字体因技术限制可能无法在reportlab中正常使用，推荐使用WenQuanYi系列字体。



本技能支持以下字体，适用于中文和英文文档创建：

**中文字体（支持简体中文）**

- **Noto Sans CJK SC**：Google开源无衬线中文字体，现代简洁，适合UI界面和文档
- **Noto Serif CJK SC**：Google开源衬线中文字体，优雅经典，适合书籍排版
- **WenQuanYi Micro Hei**：文泉驿微米黑，轻量级无衬线中文字体
- **WenQuanYi Zen Hei**：文泉驿正黑，经典无衬线中文字体

**英文字体（跨平台通用）**

- **Noto Sans**：Google开源无衬线字体，支持100+语言
- **Noto Serif**：Google开源衬线字体，优雅经典
- **DejaVu Serif**：开源衬线字体，与Times New Roman兼容
- **Arial**：通用无衬线字体，几乎所有系统都支持
- **Times New Roman**：经典衬线字体，正式文档首选

**使用中文字体示例**

```python
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

c = canvas.Canvas("chinese.pdf")

# 注册中文字体
font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('WenQuanYiMicroHei', font_path))
    c.setFont('WenQuanYiMicroHei', 16)
    c.drawString(100, 750, "你好，世界！")
else:
    # 回退到默认字体
    c.setFont("Helvetica", 16)
    c.drawString(100, 750, "Hello, World!")

c.save()
```

> **提示**：如需查看系统可用字体列表，可使用命令 `fc-list` 查看所有已安装的字体。


### 中文字体使用最佳实践

1. **优先使用WenQuanYi系列字体**：这些字体经过良好测试，兼容性好
2. **字体后备策略**：在代码中实现字体后备机制，确保在主字体不可用时仍能正常显示
3. **避免混合字体**：在同一文档中尽量使用同一字体家族，保持视觉一致性
4. **测试显示效果**：生成PDF后务必检查中文字体显示是否正常，避免乱码问题

## 命令行工具

### pdftotext (poppler-utils)

```bash
# 提取文本
pdftotext input.pdf output.txt

# 保留布局提取文本
pdftotext -layout input.pdf output.txt

# 提取指定页面
pdftotext -f 1 -l 5 input.pdf output.txt  # 第1-5页
```

### qpdf

```bash
# 合并PDF
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf

# 拆分页面
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf
qpdf input.pdf --pages . 6-10 -- pages6-10.pdf

# 旋转页面
qpdf input.pdf output.pdf --rotate=+90:1  # 将第1页旋转90度

# 移除密码
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf
```

## 常见任务

### OCR扫描PDF

```python
# 需要安装: pip install pytesseract pdf2image
import pytesseract
from pdf2image import convert_from_path

# 将PDF转换为图像
images = convert_from_path('scanned.pdf')

# 对每页进行OCR
text = ""
for i, image in enumerate(images):
    text += f"第 {i+1} 页:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"

print(text)
```

### 添加水印

```python
from pypdf import PdfReader, PdfWriter

# 创建水印（或加载现有水印）
watermark = PdfReader("watermark.pdf").pages[0]

# 应用到所有页面
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### 提取图像

```bash
# 使用pdfimages (poppler-utils)
pdfimages -j input.pdf output_prefix

# 这会将所有图像提取为output_prefix-000.jpg, output_prefix-001.jpg等
```

### 密码保护

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

# 添加密码
user_password = "user123"
owner_password = "owner123"
writer.encrypt(user_password, owner_password)

with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## 快速参考


| 任务        | 最佳工具                     | 命令/代码                  |
| ----------- | ---------------------------- | -------------------------- |
| 合并PDF     | pypdf                        | `writer.add_page(page)`    |
| 拆分PDF     | pypdf                        | 每个文件一页               |
| 提取文本    | pdfplumber                   | `page.extract_text()`      |
| 提取表格    | pdfplumber                   | `page.extract_tables()`    |
| 创建PDF     | reportlab                    | Canvas或Platypus           |
| 命令行合并  | qpdf                         | `qpdf --empty --pages ...` |
| OCR扫描PDF  | pytesseract                  | 先转换为图像               |
| 填写PDF表单 | pdf-lib或pypdf（见forms.md） | 参见forms.md               |

## 下一步

- 有关高级pypdfium2用法，请参阅reference.md
- 有关JavaScript库（pdf-lib），请参阅reference.md
- 如果需要填写PDF表单，请遵循forms.md中的说明
- 有关故障排除指南，请参阅reference.md
