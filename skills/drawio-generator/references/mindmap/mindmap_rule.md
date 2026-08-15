# 思维导图生成规则

## 生成流程

### 第1步: 需求分析与确定加载的资源

**确定以下信息：**
- 节点数量和层级深度
- 内容主题和类型
- 布局模式选择

**模式选择规则：**
- **逻辑树模式（默认）**：从左到右展开，适合有明确层级结构的内容
- **发散模式**：从中心向四周散开，适合自由联想和头脑风暴
- **用户优先**：如果用户明确指定模式，以用户指定为准

**应用场景：**
- **逻辑树模式** → 读书笔记、项目拆解、知识体系、大纲整理
- **发散模式** → 头脑风暴、灵感迸发、个人日记、自由创作
注意：以上场景仅供参考，具体还需按照实际情况灵活选择，以呈现效果为优先

### 第2步: 加载资源并参考

**🔴 关键操作（必须执行，否则生成失败）：**

根据模式，**立即使用view工具加载**对应的示例文件：

| 模式 | 必须执行的命令 |
|-----|---------------|
| 逻辑树模式 | `view references/mindmap/tree_example.md` |
| 发散模式 | `view references/mindmap/radial_example.md` |

**执行顺序（严格遵守）：**
1. 先view加载示例文件
2. 仔细阅读完整XML结构
3. 理解核心布局逻辑（树形/放射状）
4. 然后开始生成XML

**⚠️ 严禁跳过加载步骤直接生成XML**

**为什么必须加载？**
- 示例包含完整的XML结构模板
- 示例展示节点层级和连接的正确组织方式
- 示例提供实际坐标计算参考
- 示例展示配色方案和样式规范

---

## 扩展资源（必读）

**根据模式加载对应示例：**
- 逻辑树模式 → `tree_example.md`
- 发散模式 → `radial_example.md`

示例文件包含完整XML模板，不加载会导致生成失败。

---

### 第3步: XML生成

根据确定的模式和内容，按照规范生成完整的 XML：
- 创建根节点
- 生成各层级节点
- 建立连接关系
- 应用配色方案
- 调整布局间距

### 第4步: 质量自查

**检查清单：**
- [ ] 模式选择正确（逻辑树/发散）
- [ ] 节点层级关系清晰
- [ ] 连接关系正确（exitX/exitY, entryX/entryY）
- [ ] 颜色方案：单色系深浅变化，同层同色
- [ ] 连接线统一使用单一颜色，无渐变
- [ ] 节点间距合理，无重叠
- [ ] 所有文本使用 `whiteSpace=wrap;html=1`
- [ ] 连接线样式符合层级（粗细、曲线）
- [ ] 所有连接线均已创建，不能存在孤立节点

---

## 关键约束

- **仅作结构参考**：示例旨在展示正确的 XML 语法、样式定义和布局逻辑。
- **严禁生搬硬套**：绝对禁止直接复制示例中的节点内容、数量或固定坐标。
- **动态布局**：必须根据用户的实际需求（节点数量、层级关系）动态计算坐标和布局。
- **核心关系优先**：重点参考示例中的核心结构关系（分层逻辑、连接方式），而非具体表现形式。
- **配色专业性**：使用单色系深浅变化，同层节点同色，所有连接线统一颜色，严禁"彩虹色"配色。
- **连接线完整**：所有的连接线都已经创建，不存在孤立的节点
---

## 布局规范

### 逻辑树模式（从左到右展开）

**根节点：**
- 位置：画布左侧中心
- 样式：深色背景、大字体、粗体
- 尺寸：200x80px

**主分支（第1层）：**
- 位置：根节点右侧
- 方向：从左到右展开
- 水平间距：距离根节点300px
- 垂直分布：以根节点为中心，向上下对称展开
- 样式：同层同色，使用色系中的第1层颜色

**子分支（第2层及以后）：**
- 位置：继续向右展开
- 水平间距：距离父节点260px
- 垂直分布：以父节点为中心，向上下对称展开
- 样式：使用第2层颜色

**坐标计算：**
```
方向：从左到右展开
  所有分支都在根节点右侧

水平间距：
  根→第1层：+300px（向右）
  第1层→第2层：+260px（向右）
  第2层及以后：+240px（向右）

垂直分布（以父节点为中心对称）：
  totalHeight = N × nodeHeight + (N-1) × spacing
  startY = parentY + parentHeight/2 - totalHeight/2
  childY[i] = startY + i × (nodeHeight + spacing)
  
示例（父节点中心y=910，3个子节点高60px，间距105px）：
  totalHeight = 3×60 + 2×105 = 390
  startY = 910 - 390/2 = 715
  子节点Y：715, 820, 925
  
连接点：
  父节点出发点：exitX=1, exitY=0.5（右侧中点出发）
  子节点结束点：entryX=0, entryY=0.5（左侧中点进入）
  使用曲线：curved=1
  使用正交路由：edgeStyle=orthogonalEdgeStyle（固定出入口，曲线连接）
```

### 发散模式（从中心向四周）

**根节点：**
- 位置：画布中心
- 样式：深色背景、大字体、粗体
- 尺寸：240x100px

**主分支（第1层）：**
- 位置：围绕根节点，放射状分布
- 角度：360° / 主分支数量
- 距离：根节点中心向外200-250px
- 样式：同层同色，使用色系中的第1层颜色

**子分支（第2层+）：**
- 位置：继续沿父节点方向向外扩展
- 距离：每层向外150-200px
- 样式：父节点的浅色版本

**坐标计算：**
```
角度分配：
  angleStep = 360° / 主分支数量
  branchAngle[i] = i * angleStep
  
极坐标转直角坐标：
  x = centerX + radius * cos(angle)
  y = centerY + radius * sin(angle)
  
层级距离：
  第1层：radius = 220px
  第2层：radius = 380px
  第3层：radius = 540px
  
连接点：
  根节点：根据角度动态设置 exitX, exitY
  子节点：指向根节点中心 entryX, entryY
```

---

## 样式规范

### 节点样式

**根节点：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1976D2;strokeColor=#1565C0;fontColor=#000000;fontSize=16;fontStyle=1;shadow=1;" ...>
```
- 背景：中蓝色（#1976D2）
- 字体：黑色（#000000）

**第1层节点：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#1976D2;fontColor=#000000;fontSize=14;fontStyle=1;" ...>
```
- 背景：浅蓝色（#42A5F5）
- 字体：黑色（#000000）

**第2层节点：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" ...>
```
- 背景：更浅蓝色（#90CAF9）
- 字体：黑色（#000000）

**第3层节点：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#E3F2FD;strokeColor=#90CAF9;fontColor=#000000;fontSize=11;align=left;spacing=5;" ...>
```
- 背景：极浅蓝色（#E3F2FD）
- 字体：黑色（#000000）

**字体颜色规则：**
- 所有层级统一使用黑色字体（fontColor=#000000）

### 连接线样式

**统一配色原则：连接线颜色跟随父节点颜色**

**统一粗细：所有连接线使用 strokeWidth=2**

**根→第1层：**
```xml
<mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#0D47A1;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" ...>
```
- 颜色使用根节点的颜色
- exitX=1, exitY=0.5（父节点右侧中点）
- entryX=0, entryY=0.5（子节点左侧中点）

**第1层→第2层：**
```xml
<mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#1565C0;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" ...>
```
- 颜色使用第1层节点的颜色

**第2层→第3层：**
```xml
<mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" ...>
```
- 颜色使用第2层节点的颜色

**逻辑树模式连接点：**
- 父节点出发点：exitX=1, exitY=0.5（右侧中点）
- 子节点结束点：entryX=0, entryY=0.5（左侧中点）
- 使用曲线：curved=1
- 使用正交路由：edgeStyle=orthogonalEdgeStyle（固定出入口的曲线连接）

**发散模式连接点：**
- 根据节点角度动态计算 exitX/exitY 和 entryX/entryY
- 使用直线：edgeStyle=none

### 配色方案

**核心原则：**
- **单色系渐变**：使用一个色系，通过深浅变化区分层级，最多3种颜色
- **同层同色**：同一层级的所有节点使用相同颜色
- **连接线统一**：所有连接线使用同一颜色，不使用渐变
- **3层后复用**：超过第3层的所有层级使用第3层颜色，避免颜色过淡

**层级配色（以蓝色系为例）：**
- 第0层（根）：背景 #1976D2（中蓝）+ 字体 #000000（黑色）
- 第1层：背景 #42A5F5（浅蓝）+ 字体 #000000（黑色）
- 第2层及以后：背景 #90CAF9（更浅蓝）+ 字体 #000000（黑色）

**连接线配色：**
- 跟随父节点颜色
- 根→第1层：strokeColor=#1976D2（根节点颜色）
- 第1层→第2层：strokeColor=#42A5F5（第1层颜色）
- 第2层及以后：strokeColor=#90CAF9（第2层颜色）
- 统一粗细：strokeWidth=2

**其他推荐色系：**
- 绿色系：#388E3C → #66BB6A → #A5D6A7
- 紫色系：#7B1FA2 → #AB47BC → #CE93D8
- 橙色系：#F57C00 → #FF9800 → #FFCC80

**严格禁止：**
- ❌ 彩虹色配色（红橙黄绿青蓝紫混用）
- ❌ 同层使用不同颜色
- ❌ 连接线使用渐变或多色
- ❌ 超过三层禁止颜色继续变淡

### 文本样式

**根节点：**
- `fontSize=16;fontStyle=1;fontColor=#000000`

**第1层：**
- `fontSize=14;fontStyle=1;fontColor=#000000`

**第2层及以后：**
- `fontSize=12;fontColor=#000000`

**字体颜色原则：**
- 所有层级统一使用黑色字体（#000000）
- 同一层级的所有节点使用相同的字体颜色

**所有文本必须包含：**
- `whiteSpace=wrap`（允许换行）
- `html=1`（启用HTML渲染）

---

## 适配指南

**生成步骤：**

1. 确定模式（逻辑树/发散）
2. 统计节点数量和层级
3. 计算画布尺寸
4. 生成根节点
5. 循环生成各层级节点（计算坐标）
6. 建立连接关系
7. 应用配色方案

**关键公式：**

**逻辑树模式（从左到右展开，垂直对称）：**
```
水平坐标：
  节点X = 父X + 水平间距(300/260/240)

垂直坐标（对称分布）：
  totalHeight = N × nodeHeight + (N-1) × spacing
  startY = 父中心Y - totalHeight/2
  节点Y[i] = startY + i × (nodeHeight + spacing)

连接点：
  exitX=1(父右侧), entryX=0(子左侧)
  exitY=0.5, entryY=0.5（均为中点）
```

**发散模式：**
```
角度 = i × (360° / 主分支数)
半径 = 220 + 层级索引 × 160
节点X = 中心X + 半径 × cos(角度)
节点Y = 中心Y + 半径 × sin(角度)
```

---

**关键提醒：**
- **对称布局约束**：子节点必须以父节点中心为轴对称分布，奇数个子节点时中间节点与父节点同高
- 必须根据模式使用对应的坐标计算方法
- 连接线的 exitX/exitY/entryX/entryY 必须根据节点位置动态计算
- 发散模式需要考虑节点旋转角度，确保文本可读