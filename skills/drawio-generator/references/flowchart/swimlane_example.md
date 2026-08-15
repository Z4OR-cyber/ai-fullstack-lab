# 流程图 - 泳道布局示例

**适用场景：** 适用于有明确并行任务、角色分工或跨部门协作的流程

---

## 布局规范

### 整体策略

**核心思路：** 使用横向或纵向泳道（容器）划分不同角色/部门的职责范围，流程在泳道间流转

**布局特征：**
- 每个泳道代表一个角色、部门或系统
- 泳道使用带标题的容器表示
- 节点放置在对应的泳道内
- 跨泳道连接表示交接或协作

### 坐标计算公式

**画布参数（横向泳道）：**
```
画布宽度 = max(节点宽度, 流程长度) + 左右边距
画布高度 = 泳道数 × (泳道高度 + 间距) + 顶部边距
视口宽度 = 1400
视口高度 = 1000
```

**泳道定位（横向）：**
```
泳道宽度 = 画布宽度 - 左边距 - 右边距（通常全宽）
泳道高度 = 150-200（根据内容调整）
泳道间距 = 20-30

泳道X = 左边距（通常对齐）
泳道Y[i] = 顶部边距 + i × (泳道高度 + 间距)
```

**节点定位（泳道内相对坐标）：**
```
节点相对X = 流程步骤索引 × (节点宽度 + 水平间距) + 初始偏移
节点相对Y = (泳道高度 - 节点高度) / 2（垂直居中）

节点宽度 = 140-160
节点高度 = 50-60
水平间距 = 100-120
初始偏移 = 40-60
```

**连接线规则：**
```
泳道内连接：从左节点右侧 (exitX=1) 到右节点左侧 (entryX=0)
跨泳道连接：从当前节点底部/顶部到目标节点顶部/底部
         根据泳道位置选择合适的出入点
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1400 | 足够容纳完整流程 | 1200-1800 |
| 画布高度 | 动态计算 | 泳道数×(泳道高+间距) | 根据泳道数 |
| 泳道数 | 3-5 | 角色/部门数量 | 2-6 |
| 泳道宽度 | 1200 | 通常全宽 | 1000-1600 |
| 泳道高度 | 180 | 单个泳道高度 | 150-220 |
| 泳道间距 | 20 | 泳道之间空隙 | 10-30 |
| 节点宽度 | 150 | 泳道内节点宽度 | 120-170 |
| 节点高度 | 55 | 泳道内节点高度 | 45-65 |
| 水平间距 | 110 | 泳道内节点间距 | 90-130 |
| 左边距 | 100 | 泳道左侧空白 | 80-120 |
| 右边距 | 100 | 泳道右侧空白 | 80-120 |
| 顶部边距 | 80 | 第一个泳道上方空白 | 60-100 |

---

## 关键共识

### 重要提示

⚠️ **本示例仅供结构参考**
- 展示正确的泳道容器结构和跨泳道连接方式
- **严禁直接复制**示例中的角色名称、节点内容或固定坐标
- 必须根据用户需求**动态计算**泳道数、节点分配和所有坐标
- 参考示例的**容器嵌套和相对定位**，而非具体数值

### 样式规范

**泳道容器样式：**
```xml
style="swimlane;startSize=30;horizontal=1;containerType=tree;
      fillColor=#e1f5fe;strokeColor=#0288d1;strokeWidth=2;
      whiteSpace=wrap;html=1;fontStyle=1;fontSize=14;"
```

**泳道内节点样式：**
```xml
<!-- 普通处理节点 -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#dae8fc;strokeColor=#6c8ebf;"

<!-- 判断节点 -->
style="rhombus;whiteSpace=wrap;html=1;
      fillColor=#fff2cc;strokeColor=#d6b656;"

<!-- 开始/结束节点 -->
style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;
      fillColor=#f5f5f5;strokeColor=#666666;"
```

**连接线样式：**
```xml
<!-- 泳道内连接 -->
style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;
      strokeColor=#333333;"

<!-- 跨泳道连接 -->
style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;
      strokeColor=#666666;dashed=1;"
```

### 配色建议

**泳道布局的典型配色：**
- **泳道1（用户/客户）**：`fillColor=#e1f5fe strokeColor=#0288d1` - 蓝色系
- **泳道2（业务部门）**：`fillColor=#fff3e0 strokeColor=#f57c00` - 橙色系
- **泳道3（技术部门）**：`fillColor=#f3e5f5 strokeColor=#7b1fa2` - 紫色系
- **泳道4（运维/支持）**：`fillColor=#e8f5e9 strokeColor=#388e3c` - 绿色系

**配色原则：**
- 不同泳道使用不同背景色，清晰区分职责
- 泳道内节点可使用统一或相似色系
- 跨泳道连接使用虚线，便于识别

---

## 案例代码

### 使用方法
复制下方完整代码，在 diagrams.net 选择 **File → Import from → Text**，粘贴即可打开

### 完整 XML（横向泳道示例）

```xml
<mxfile host="app.diagrams.net">
  <diagram name="泳道流程示例">
    <mxGraphModel dx="1400" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="900" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        
        <!-- 泳道1：客户 -->
        <mxCell id="lane1" value="客户" style="swimlane;startSize=30;horizontal=1;containerType=tree;fillColor=#e1f5fe;strokeColor=#0288d1;strokeWidth=2;whiteSpace=wrap;html=1;fontStyle=1;fontSize=14;" vertex="1" parent="1">
          <mxGeometry x="100" y="80" width="1200" height="180" as="geometry" />
        </mxCell>
        
        <!-- 泳道1内节点 -->
        <mxCell id="n1_1" value="提交需求" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="lane1">
          <mxGeometry x="50" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <mxCell id="n1_2" value="确认方案" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="lane1">
          <mxGeometry x="520" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <mxCell id="n1_3" value="验收完成" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="lane1">
          <mxGeometry x="1000" y="65" width="150" height="45" as="geometry" />
        </mxCell>
        
        <!-- 泳道2：产品团队 -->
        <mxCell id="lane2" value="产品团队" style="swimlane;startSize=30;horizontal=1;containerType=tree;fillColor=#fff3e0;strokeColor=#f57c00;strokeWidth=2;whiteSpace=wrap;html=1;fontStyle=1;fontSize=14;" vertex="1" parent="1">
          <mxGeometry x="100" y="280" width="1200" height="180" as="geometry" />
        </mxCell>
        
        <!-- 泳道2内节点 -->
        <mxCell id="n2_1" value="需求分析" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;" vertex="1" parent="lane2">
          <mxGeometry x="270" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <mxCell id="n2_2" value="方案设计" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;" vertex="1" parent="lane2">
          <mxGeometry x="520" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <!-- 泳道3：技术团队 -->
        <mxCell id="lane3" value="技术团队" style="swimlane;startSize=30;horizontal=1;containerType=tree;fillColor=#f3e5f5;strokeColor=#7b1fa2;strokeWidth=2;whiteSpace=wrap;html=1;fontStyle=1;fontSize=14;" vertex="1" parent="1">
          <mxGeometry x="100" y="480" width="1200" height="180" as="geometry" />
        </mxCell>
        
        <!-- 泳道3内节点 -->
        <mxCell id="n3_1" value="技术评审" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;" vertex="1" parent="lane3">
          <mxGeometry x="270" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <mxCell id="n3_2" value="开发实现" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;" vertex="1" parent="lane3">
          <mxGeometry x="520" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <mxCell id="n3_3" value="测试部署" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;" vertex="1" parent="lane3">
          <mxGeometry x="770" y="60" width="150" height="55" as="geometry" />
        </mxCell>
        
        <!-- 连接线 -->
        <!-- 泳道1内连接 -->
        <mxCell id="e1_1" edge="1" parent="1" source="n1_2" target="n1_3" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 泳道2内连接 -->
        <mxCell id="e2_1" edge="1" parent="1" source="n2_1" target="n2_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 泳道3内连接 -->
        <mxCell id="e3_1" edge="1" parent="1" source="n3_1" target="n3_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <mxCell id="e3_2" edge="1" parent="1" source="n3_2" target="n3_3" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 跨泳道连接（虚线） -->
        <!-- 客户到产品 -->
        <mxCell id="ec1" edge="1" parent="1" source="n1_1" target="n2_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#666666;dashed=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 产品到客户 -->
        <mxCell id="ec2" edge="1" parent="1" source="n2_2" target="n1_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#666666;dashed=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 产品到技术 -->
        <mxCell id="ec3" edge="1" parent="1" source="n2_1" target="n3_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#666666;dashed=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <mxCell id="ec4" edge="1" parent="1" source="n2_2" target="n3_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#666666;dashed=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 技术到客户 -->
        <mxCell id="ec5" edge="1" parent="1" source="n3_3" target="n1_3" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#666666;dashed=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

## 扩展说明

### 泳道数量调整

**当角色/部门增加时：**
1. 计算新的画布高度：`画布高度 = 泳道数 × (泳道高度 + 间距) + 顶部边距 + 底部边距`
2. 按公式更新每个泳道的Y坐标：`泳道Y[i] = 顶部边距 + i × (泳道高度 + 间距)`
3. 调整画布高度 `pageHeight` 属性
4. 为新泳道分配不同配色

**计算公式：**
```
泳道高度 = 180（可调整）
泳道间距 = 20
泳道Y[i] = 顶部边距 + i × (泳道高度 + 泳道间距)
画布高度 = 泳道Y[最后一个] + 泳道高度 + 底部边距
```

### 节点分配调整

**当流程步骤增加时：**
1. 确定每个步骤所属的泳道（角色/部门）
2. 计算节点在泳道内的相对X坐标：`相对X = 步骤索引 × (节点宽度 + 间距) + 初始偏移`
3. 节点Y坐标保持垂直居中：`相对Y = (泳道高度 - 节点高度) / 2`
4. 必要时扩展泳道宽度和画布宽度

### 纵向泳道

**如需使用纵向泳道：**
1. 设置泳道 `horizontal=0`（纵向）
2. 调整泳道宽度和高度：宽度固定，高度扩展
3. 节点在泳道内垂直排列
4. 跨泳道连接从左右侧出入

### 对齐优化

**泳道布局的关键原则：**
- ⚠️ **禁止运行对齐脚本** (`align_drawio_nodes.py`)
- 原因：泳道使用容器嵌套，节点使用相对坐标
- 对齐脚本只能处理绝对坐标，无法识别父子关系
- 运行对齐脚本可能破坏容器内的相对定位

**正确的做法：**
1. 生成时按公式精确计算所有坐标
2. 确保泳道容器的位置和尺寸正确
3. 节点在泳道内使用相对定位，保持一致性
4. 只运行修正脚本 (`fix_drawio_xml.py`) 修正语法错误
5. **跳过对齐脚本**，容器会自动处理内部对齐
