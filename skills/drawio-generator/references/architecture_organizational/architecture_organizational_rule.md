# 组织架构图生成规则

## 生成流程

### 第1步: 需求分析与确定加载的资源

**确定以下信息：**
- 组织层级深度（3-5层典型）
- 每层节点数量
- 显示内容（职位/姓名/人数）
- 组织类型（层级/扁平/矩阵/职能）

**自动判断逻辑：**
- 层级明确的企业 → 标准树形结构
- 扁平化组织 → 减少层级，增加同层节点
- 矩阵组织 → 支持虚线汇报关系
- 跨地区组织 → 可增加地理容器分组

### 第2步: 加载资源并参考

**必须执行：加载组织架构图示例文件**

| 组织类型 | 加载文件 |
|---------|---------|
| 标准层级结构 | `view references/architecture_organizational/standard_example.md` |

**为什么必须加载示例？**
- 示例包含完整的XML结构模板
- 示例展示树形层级的正确组织方式
- 示例提供节点定位和连接计算参考
- 示例展示配色方案和层级样式
- **不加载示例会导致生成错误**

---

## 扩展资源（必读）

**加载标准示例：**
- 标准层级结构 → `standard_example.md`

示例文件包含完整XML模板，不加载会导致生成失败。

---

### 第3步: XML生成

根据确定的层级和内容，按照规范生成完整的 XML：
- 创建根节点（CEO/总裁）
- 生成各层级节点
- 建立父子连接关系
- 应用层级配色方案
- 调整水平分布和垂直间距

### 第4步: 质量自查

**检查清单：**
- [ ] 层级结构清晰（自上而下）
- [ ] 节点定位准确（父下子上对齐）
- [ ] 连接线从父节点下方中心点（exitX=0.5）出发
- [ ] 所有同父节点的连线都从同一个点出发
- [ ] 连接线到子节点上方中心点（entryX=0.5, entryY=0）
- [ ] 连接线使用正交直线（curved=0）
- [ ] 颜色方案：单色系深浅变化，同层同色
- [ ] 字体颜色统一为黑色
- [ ] 连接线颜色跟随父节点
- [ ] 节点尺寸随层级递减
- [ ] 单个父节点下子节点不超过4个（建议）
- [ ] **已运行 align_drawio_nodes.py 对齐脚本**

---

## 关键约束

- **仅作结构参考**：示例旨在展示正确的 XML 语法、样式定义和布局逻辑。
- **严禁生搬硬套**：绝对禁止直接复制示例中的节点内容、数量或固定坐标。
- **动态布局**：必须根据用户的实际需求动态计算坐标和布局。
- **核心关系优先**：重点参考示例中的核心结构关系（树形层级、连接方式），而非具体表现形式。
- **连线统一规范**：所有连接线从父节点下方出，到子节点上方，使用正交直线(curved=0)
- **配色专业性**：使用单色系深浅变化，同层节点同色，统一黑色字体
- **子节点限制**：单个父节点下直接子节点建议不超过4个，超过应增加中间层级

---

## 布局规范

### 标准树形结构

**根节点（CEO/总裁）：**
- 位置：顶部中心
- 样式：最大尺寸，最深色，粗体
- 尺寸：200x80px

**第1层（高管层）：**
- 位置：根节点下方，水平均匀分布
- 样式：大尺寸，深色，粗体
- 尺寸：180x70px

**第2层及以后（部门/团队层）：**
- 位置：对应上层节点下方，水平分布
- 样式：中等尺寸，中等色
- 尺寸：160x70px（或更小）
- 配色：第2层及以后统一使用第2层颜色

**垂直间距：**
- 层间距：160px（层级之间的垂直距离）
- 一致的间距创造整洁的视觉层次

**水平分布：**
- 计算子节点总宽度
- 找到中点并均匀分布
- 根据子节点数量分配exitX值

**连接线（正交直线）：**
- 方向：从父节点下方中心点 → 子节点上方
- 样式：curved=0（正交直线），endArrow=none（无箭头），exitY=1, entryY=0
- 粗细：根据层级递减（2 → 1.5 → 1）
- **关键特征**：所有子节点的连线从父节点底部中心（exitX=0.5）出发

**坐标计算：**
```
垂直位置：
  层Y = 顶部边距 + 层级编号 × (节点高度 + 垂直间距)
  
  示例：
  第0层：60
  第1层：60 + (80 + 80) = 220
  第2层：220 + (70 + 90) = 380
  第3层：380 + (70 + 90) = 540

水平分布（多子节点）：
  子节点X坐标计算：
  - 计算所有子节点的总宽度
  - 在父节点下方居中分布
  - 子节点间保持适当间距（40-60px）
  
  具体公式：
  总宽度 = Σ(子宽度) + (N-1) × 子节点间距
  起始X = 父中心X - 总宽度/2
  子X[i] = 起始X + Σ(前i个子宽度) + i × 间距
  
  **注意**：生成后必须运行 align_drawio_nodes.py 脚本
  对齐脚本会优化水平分布，确保子节点在父节点正下方居中对齐

连接点（单点出发）：
  父节点：exitX=0.5, exitY=1（底部中心点，所有连线统一从这里出发）
  子节点：entryX=0.5, entryY=0（上方中点）
  
  特点：
  - 所有从同一父节点出发的连线，exitX都是0.5
  - 曲线会自动调整路径，形成树状分叉效果
  - 使用orthogonalEdgeStyle确保连线整齐
```

---

## 样式规范

### 节点样式（蓝色系）

**第0层（根节点）：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1976D2;strokeColor=#1565C0;fontColor=#000000;fontSize=16;fontStyle=1;" ...>
```

**第1层（高管层）：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#1976D2;fontColor=#000000;fontSize=14;fontStyle=1;" ...>
```

**第2层及以后（部门/团队层）：**
```xml
<mxCell style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" ...>
```

### 节点内容结构

**标准3行格式：**
1. 职位/角色（中文或主要语言）
2. 职位/角色（英文，可选）
3. 姓名或人数

**示例：**
```xml
value="CTO&lt;br&gt;首席技术官&lt;br&gt;李华"
value="研发部&lt;br&gt;R&amp;D Department&lt;br&gt;总监: 陈伟"
value="前端团队&lt;br&gt;Frontend Team&lt;br&gt;8人"
```

### 连接线样式

**第0层→第1层：**
```xml
<mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=2;strokeColor=#1976D2;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" ...>
```
- 颜色：#1976D2（根节点颜色）
- 粗细：strokeWidth=2
- 箭头：endArrow=none（无箭头）
- **curved=0**：正交直线
- **exitX=0.5**：所有连线从父节点底部中心出发

**第1层→第2层：**
```xml
<mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" ...>
```
- 颜色：#42A5F5（第1层颜色）
- 粗细：strokeWidth=1.5
- 箭头：endArrow=none（无箭头）
- **curved=0**：正交直线
- **exitX=0.5**：所有连线从父节点底部中心出发

**第2层及以后：**
```xml
<mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" ...>
```
- 颜色：#90CAF9（第2层颜色）
- 粗细：strokeWidth=1
- 箭头：endArrow=none（无箭头）
- **curved=0**：正交直线
- **exitX=0.5**：所有连线从父节点底部中心出发

### 配色方案

**核心原则：**
- **单色系渐变**：使用一个色系，通过深浅变化区分层级，最多3种颜色
- **同层同色**：同一层级的所有节点使用相同颜色
- **连接线跟随父节点**：每条连接线使用父节点的颜色
- **统一黑色字体**：所有文本使用 fontColor=#000000
- **3层后复用**：超过第2层的所有层级使用第2层颜色，避免颜色过淡

**层级配色（蓝色系）：**
- 第0层：背景 #1976D2 + 字体黑色 + 尺寸200x80
- 第1层：背景 #42A5F5 + 字体黑色 + 尺寸180x70
- 第2层及以后：背景 #90CAF9 + 字体黑色 + 尺寸160x70（或更小）

**连接线配色：**
- 第0层→第1层：strokeColor=#1976D2, strokeWidth=2, endArrow=none, curved=0
- 第1层→第2层：strokeColor=#42A5F5, strokeWidth=1.5, endArrow=none, curved=0
- 第2层及以后：strokeColor=#90CAF9, strokeWidth=1, endArrow=none, curved=0

**其他推荐色系：**
- 绿色系：#388E3C → #66BB6A → #A5D6A7
- 紫色系：#7B1FA2 → #AB47BC → #CE93D8
- 橙色系：#F57C00 → #FF9800 → #FFCC80

### 文本样式

**第0层（根节点）：**
- `fontSize=16;fontStyle=1;fontColor=#000000`

**第1层（高管层）：**
- `fontSize=14;fontStyle=1;fontColor=#000000`

**第2层及以后（部门/团队层）：**
- `fontSize=12;fontColor=#000000`

**所有文本必须包含：**
- `whiteSpace=wrap`（允许换行）
- `html=1`（启用HTML渲染）

---

## 适配指南

**生成步骤：**

1. 确定层级深度（3-5层）
2. 统计每层节点数量
3. 计算画布尺寸（宽度根据最宽层计算）
4. 生成根节点（顶部中心）
5. 循环生成各层节点（水平均匀分布）
6. 建立父子连接（父下→子上，正交直线）
7. 应用层级配色方案
8. **运行对齐脚本**：执行 `align_drawio_nodes.py` 优化节点位置
9. 添加可选元素（标题、图例、统计）

**关键公式：**
```
画布宽度 = 最宽层节点数 × (节点宽 + 间距) + 左右边距
画布高度 = 顶部边距 + 层数 × (节点高 + 层间距) + 底部边距

节点Y坐标 = 顶部边距 + 层级 × (节点高 + 层间距)

单点出发连接线：
  所有父节点：exitX=0.5, exitY=1（底部中心）
  所有子节点：entryX=0.5, entryY=0（顶部中心）
  
子节点水平居中布局：
  总宽度 = Σ(子宽度) + (N-1) × 间距
  起始X = 父中心X - 总宽度/2
  子X[i] = 起始X + Σ(前i个子宽度) + i × 间距
```

---

## 特殊场景处理

### 大规模节点约束

**子节点数量限制：**
- 单个父节点下直接子节点建议不超过4个
- 超过时应增加中间层级进行分组
- 或使用虚线框容器将相关子节点分组

**层级深度控制：**
- 建议展示深度不超过4层
- 更细的团队信息用人数统计代替

### 特殊组织类型

**扁平组织：**
- 层级更少（2-3层）
- 每个经理的直接下属更多
- 更宽的水平跨度
- 注意子节点数量限制

**矩阵组织：**
- 一些节点有多个父节点
- 使用虚线表示虚线汇报（dashed=1）
- 主要汇报用实线，协作汇报用虚线

**地理/职能组织：**
- 先按地区/职能分组
- 为每个组添加容器框
- 可按组使用不同色系

### 可选元素

**标题：**
```xml
<mxCell value="公司组织架构" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=18;fontStyle=1;fontColor=#000000;" ...>
```

**图例：**
```xml
<mxCell value="图例:&lt;br&gt;● 深色 - 高管层&lt;br&gt;● 中色 - 部门层&lt;br&gt;● 浅色 - 团队层" style="text;html=1;strokeColor=#42A5F5;fillColor=#E3F2FD;align=left;verticalAlign=top;whiteSpace=wrap;rounded=1;fontSize=11;fontColor=#000000;" ...>
```

---

**关键提醒：**
- **组织架构图必须运行对齐脚本**：生成XML后必须运行 `align_drawio_nodes.py` 进行节点对齐优化
- 对齐脚本会优化树形结构的水平分布，确保子节点在父节点正下方居中对齐
- **所有连接线统一从父节点底部中心点（exitX=0.5）出发**
- 连接线必须从父节点下方出，到子节点上方
- 所有连接线使用正交直线（curved=0）和正交路由（orthogonalEdgeStyle）
- 统一使用黑色字体和单色系配色
- 连接线颜色和粗细跟随父节点层级
- 避免单个父节点下子节点过多（建议≤4个）