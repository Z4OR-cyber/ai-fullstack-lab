---
name: drawio-generator
description: 生成Draw.io图表XML文件,可直接在diagrams.net中打开和编辑。当用户请求创建流程图、思维导图、架构图、组织架构图、甘特图、时间轴或其他可视化图表时使用。支持所有标准Draw.io形状、样式和连接。
---

# Draw.io 图表生成器 v12

生成与Draw.io兼容的XML文件,可在diagrams.net中直接打开进行进一步编辑。

---

## 快速参考（Agent必读）

**每次生成图表的6步工作流程：**

1. **理解需求** - 明确图表类型和内容要求
2. **加载参考** - 读取 `references/{类型}/{类型}_rule.md`（规则文件会指引扩展资源）
3. **生成XML** - 创建完整的 `<mxfile>...</mxfile>`
4. **保存文件** - 使用 `{主题名}_{类型}.drawio` 命名
5. **修正与对齐** - 运行 `script/fix_drawio_xml.py`（必须）+ 对齐脚本（推荐）
6. **提供文件** - 返回最终文件

**关键要点：**
- 第5步不能跳过，必须运行修正脚本
- 文件扩展名必须是 `.drawio`，禁止使用 `.xml`

---

## 文件命名规则

**格式：`{主题名}_{类型}.drawio`**

**关键要求：**
- 文件必须以 `.drawio` 结尾
- **禁止使用 `.drawio.xml` 或 `.xml` 作为扩展名**
- 最终提供给用户的文件必须是 `.drawio` 格式

**命名示例：**
- `电商注册_流程图.drawio`
- `系统架构_架构图.drawio`
- `公司组织_组织架构图.drawio`
- `项目排期_甘特图.drawio`

**禁止** 输出其他格式，只可输出xxx_xxx.drawio,生成其他的格式都会受到严重的惩罚！

---

## 核心工作流程（6步详解）

### 第1步：理解需求

与用户明确以下内容：
- 图表类型（流程图/思维导图/架构图/组织架构图/甘特图/时间轴）
- 具体内容要求
- 如有文件需要解析或需要网络检索，先行完成

### 第2步：加载参考

根据图表类型，读取对应的规则文件：

| 图表类型 | 规则文件路径 |
|---------|------------|
| 流程图 | `references/flowchart/flowchart_rule.md` |
| 思维导图 | `references/mindmap/mindmap_rule.md` |
| 架构图 | `references/architecture/architecture_rule.md` |
| 组织架构图 | `references/architecture_organizational/architecture_organizational_rule.md` |
| 甘特图 | `references/gantt/gantt_rule.md` |
| 时间轴 | `references/timeline/timeline_rule.md` |

**重要提示：**
- 规则文件会在"扩展资源"章节列出其他可选资源（如 examples.md、templates.md）
- 根据需要按需加载扩展资源

### 第3步：生成XML

按照规则文件中的规范，创建完整的 Draw.io XML 内容：
- 遵循 XML 基本结构
- 应用正确的样式规则
- 确保连接点配置正确

### 第4步：保存文件

按照"文件命名规则"保存为 `.drawio` 文件：
- 格式：`{主题名}_{类型}.drawio`
- 确保扩展名正确

### 第5步：修正与对齐（必须执行！）

**5.1 运行修正脚本（所有图表类型必须）**

```bash
python script/fix_drawio_xml.py {文件名}.drawio
```

修正内容：
- style 属性引号错误
- ID 唯一性验证
- source/target 引用验证

**5.2 运行对齐脚本（特定图表类型）**

| 图表类型 | 对齐脚本 | 是否必须 | 特殊说明 |
|---------|---------|---------|---------|
| 流程图（普通/Z字） | `script/align_drawio_nodes.py` | 必须 | - |
| 流程图（泳道） | - | **禁止运行** | 泳道使用容器嵌套和相对坐标，对齐脚本无效且可能破坏布局 |
| 组织架构图 | `script/align_drawio_nodes.py` | 必须 | - |
| 架构图 | `script/align_drawio_architecture.py` | 必须 | - |
| 思维导图 | `script/align_mindmap_vertical.py` | 必须 | - |
| 甘特图 | - | 不需要 | - |
| 时间轴 | - | 不需要 | - |

⚠️ **重要：泳道流程图特别说明**
- 泳道布局使用容器嵌套结构，节点使用相对于泳道容器的坐标
- 对齐脚本只能处理绝对坐标，无法识别相对坐标关系
- **生成泳道图后直接跳过对齐脚本，只运行修正脚本即可**
- 泳道图的对齐由容器自动处理，关键是生成时精确计算坐标


### 第6步：提供文件

将修正并对齐后的 `.drawio` 文件返回给用户。

---

## 正确做法 vs 错误做法

### 正确做法

**完整流程：**
1. 读取对应图表类型的规则文件（如 `references/flowchart/flowchart_rule.md`）
2. 根据规则生成完整的 XML 内容
3. 按命名规则保存为 `.drawio` 文件
4. 运行 `script/fix_drawio_xml.py` 修正错误
5. 根据图表类型运行对应的对齐脚本（`script/align_*.py`）
6. 将最终文件返回给用户

---

**以下做法会导致任务失败：**

**错误1：直接在对话中输出 XML 文本**
- 问题：用户无法直接使用文本形式的 XML
- 正确：必须创建文件

**错误2：保存文件后不运行修正脚本**
- 问题：文件可能有引号错误，无法在 Draw.io 中打开
- 正确：必须运行 `script/fix_drawio_xml.py`

**错误3：跳过第5步（修正与对齐）**
- 问题：文件质量无法保证，可能无法正确渲染
- 正确：必须运行修正脚本，推荐运行对齐脚本

**错误4：对应该对齐的图表类型不运行对齐脚本**
- 问题：图表不规整，连线弯折
- 正确：普通流程图/Z字流程图/组织架构图运行 `align_drawio_nodes.py`，架构图运行 `align_drawio_architecture.py`，思维导图运行`align_mindmap_vertical.py`

**错误4.1：对泳道流程图运行对齐脚本**
- 问题：泳道使用容器相对坐标，对齐脚本会破坏布局
- 正确：泳道流程图**禁止运行对齐脚本**，只运行修正脚本

**错误5：使用错误的文件扩展名**
- 问题：文件无法被 Draw.io 正确识别
- 正确：必须使用 `.drawio` 扩展名，禁止使用 `.drawio.xml` 或 `.xml`

---

## 视觉风格模式

根据用户意图或关键词（如"手绘"、"草图"、"白板"），选择以下风格之一：

### 1. 专业标准风格（默认）

**适用场景：** 正式文档、技术评审、交付物

**样式参数：**
- 节点：`rounded=1;whiteSpace=wrap;html=1;shadow=0;glass=0;sketch=0`
- 连线：`edgeStyle=orthogonalEdgeStyle;rounded=0;sketch=0`
- 字体：默认字体（Helvetica/Verdana）

### 2. 手绘草图风格

**适用场景：** 头脑风暴、早期设计、非正式讨论

**触发关键词：** "手绘"、"草图"、"白板"

**样式参数：**
- 节点/连线：
  - `sketch=1`（开启手绘）
  - `hachureGap=4`（线条间隙）
  - `jiggle=2`（抖动程度）
  - `curveFitting=1`
  - `fontFamily=Architects Daughter`
  - `fontSource=https://fonts.googleapis.com/css?family=Architects+Daughter`
- 连线额外选项：`curved=1`（使线条更自然）

**注意：** 手绘风格时，所有文本节点也必须应用手绘字体。

---

## 图表类型速查

### 支持的6种图表类型

| 类型 | 关键词 | 适用场景 |
|------|-------|---------|
| **流程图** | 流程、工作流、步骤、程序、顺序 | 流程处理、决策树 |
| **思维导图** | 头脑风暴、想法、概念、组织思路 | 层级化想法组织 |
| **架构图** | 系统、组件、服务、技术栈、拓扑 | 系统架构、网络拓扑 |
| **组织架构图** | 组织、团队、汇报关系、部门 | 公司/团队层级结构 |
| **甘特图** | 甘特、项目计划、排期、进度 | 项目排期、时间线管理 |
| **时间轴** | 时间轴、历程、发展、事件、演变 | 发展历程、里程碑展示 |

### 图表类型选择指引

当用户请求图表但未指定类型时，根据关键词自动识别：
- 提到"流程"、"步骤" → 流程图
- 提到"想法"、"头脑风暴" → 思维导图
- 提到"系统"、"架构" → 架构图
- 提到"组织"、"部门" → 组织架构图
- 提到"排期"、"进度" → 甘特图
- 提到"历程"、"发展" → 时间轴

---

## Python脚本说明

### 1. fix_drawio_xml.py（必须运行）

**位置：** `script/fix_drawio_xml.py`

**适用范围：** 所有图表类型

**功能：**
- 修正 style 属性引号错误
- 修正 style 属性分裂
- 修正 key="value" 模式错误
- 验证 ID 唯一性
- 验证 source/target 引用有效性

**使用方法：**
```bash
python script/fix_drawio_xml.py {文件名}.drawio
```

### 2. align_drawio_nodes.py（流程图/组织架构图）

**位置：** `script/align_drawio_nodes.py`

**适用范围：** 流程图、组织架构图

**功能：**
- 纵列对齐（垂直方向）
- 横列对齐（水平方向）
- AABB 碰撞检测与推挤

**使用方法：**
```bash
python script/align_drawio_nodes.py {文件名}.drawio
```

### 3. align_drawio_architecture.py（架构图）

**位置：** `script/align_drawio_architecture.py`

**适用范围：** 架构图

**功能：**
- 父子节点关系处理
- 容器自动扩展
- 层容器间距调整
- 确保无重叠无溢出

**使用方法：**
```bash
python script/align_drawio_architecture.py {文件名}.drawio
```

### 4. align_mindmap_vertical.py（思维导图）

**位置：** `script/align_mindmap_vertical.py`

**适用范围：** 思维导图（逻辑树和放射状）

**功能：**
- 垂直方向防重叠检测
- 从上到下碰撞检测
- 向下推开重叠节点
- 保持最小垂直间距

**使用方法：**
```bash
python script/align_mindmap_vertical.py {文件名}.drawio [最小间距]
```

**参数说明：**
- `最小间距`：可选，默认20px，建议15-40px

---

## 通用 XML 规则

### 1. 基本结构

```xml

  <mxfile host="app.diagrams.net">
  <diagram id="unique_id" name="图表名称">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        
        <!-- 所有节点和边都是root的直接子元素 -->
        <mxCell id="node1" value="文本" 
                style="rounded=1;fillColor=#3366CC;strokeColor=#3366CC;" 
                vertex="1" parent="1">
          <mxGeometry x="100" y="100" width="180" height="60" as="geometry"/>
        </mxCell>
        
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>

```

### 2. Style 属性规则（最容易出错）

**关键原则：永远不要在 style 属性值内部添加引号！**

这是最常见的错误，会导致 Draw.io 完全无法解析 XML。

**错误示例：**
```xml
style="fillColor="#3366CC;strokeColor="#666;"          
style="fillColor="#3366CC;strokeColor=#666;"           
style="rounded=1;fillColor="#3366CC;"                  
```

**正确示例：**
```xml
style="fillColor=#3366CC;strokeColor=#666;"            
style="rounded=1;fillColor=#3366CC;fontColor=#FFFFFF;" 
```

**核心规则：**
- style 的值已经被外层双引号包裹，内部不能再有引号
- 颜色值：`fillColor=#RRGGBB`（无引号）
- 数字值：`rounded=1`（无引号）
- 所有参数必须是 `key=value` 格式（不能只写 `rounded`，必须写 `rounded=1`）

### 3. 连接点规则

出入口坐标是 mxCell 属性，不是 style 参数：

```xml
<!-- 正确 -->
<mxCell id="edge1" 
        style="edgeStyle=orthogonalEdgeStyle;endArrow=block;" 
        edge="1" parent="1" source="node1" target="node2"
        exitX="1" exitY="0.5" entryX="0" entryY="0.5">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

**连接点坐标系统：**
- X 轴：`0`（左）/ `0.5`（中）/ `1`（右）
- Y 轴：`0`（上）/ `0.5`（中）/ `1`（下）

### 4. 换行处理

使用 `&lt;br&gt;` 配合 `html=1;whiteSpace=wrap;` 实现换行：

```xml
<mxCell id="node1" value="第一行&lt;br&gt;第二行&lt;br&gt;第三行" 
        style="rounded=1;fillColor=#3366CC;html=1;whiteSpace=wrap;" 
        vertex="1" parent="1">
```

### 5. 节点关系规则

**基本要求：** 所有 mxCell 元素是 `<root>` 的直接子元素（XML 不嵌套），通过 parent 属性表示层级关系。

**标准结构：**
- `<mxCell id="0"/>` - 根节点
- `<mxCell id="1" parent="0"/>` - 画布节点

**parent 属性使用：**
- **一般图表（流程图/思维导图/甘特图/时间轴）**：所有节点 `parent="1"`（扁平结构）
- **架构图/组织架构图**：允许使用父子嵌套
  - 容器节点：`parent="1"`
  - 子节点：`parent="容器ID"`（坐标相对父容器）

**注意：** 父子关系通过 `parent` 属性表达，不是 XML 标签嵌套。

---

## 工作流强制要求

**完整工作流：**

| 步骤 | 操作 | 要点 |
|-----|------|------|
| 1 | 理解需求 | 明确图表类型和内容 |
| 2 | 加载规则文件 | `references/{类型}/{类型}_rule.md` |
| 3 | 生成XML | 创建完整的 `<mxfile>` 结构 |
| 4 | 保存文件 | `{主题名}_{类型}.drawio` |
| 5.1 | 运行修正脚本 | `script/fix_drawio_xml.py`（必须） |
| 5.2 | 运行对齐脚本 | 根据图表类型选择（必须） |
| 6 | 提供文件 | 返回最终 `.drawio` 文件 |

**关键提醒：**
- 必须运行修正脚本，确保文件可以正确渲染
- 根据图表类型运行对应的对齐脚本
- 最终文件必须是 `.drawio` 格式

---