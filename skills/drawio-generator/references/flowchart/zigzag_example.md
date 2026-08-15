# 流程图 - Z字布局示例

**适用场景：** 适用于节点数≥9的长流程，且无任何分支、判断或循环的线性流程

---

## 布局规范

### 整体策略

**核心思路：** 节点按列分组排列，每列从上到下，列与列之间通过转折连接形成Z字形

**布局特征：**
- 多列布局（通常3-4列），每列3-4个节点
- 节点在列内纵向排列，列间通过横向转折连接
- 所有节点宽度一致，便于对齐
- 使用颜色区分不同阶段或列

### 坐标计算公式

**画布参数：**
```
画布宽度 = 列数 × (节点宽度 + 列间距) + 左边距 + 右边距
画布高度 = max(每列节点数) × (节点高度 + 间距) + 顶部边距 + 底部边距
视口宽度 = 1400
视口高度 = 1000
```

**列定位：**
```
列数 = ceiling(节点总数 / 每列节点数)
每列节点数 = 3-4（推荐3）
列X[i] = 左边距 + i × (节点宽度 + 列间距)

左边距 = 100
列间距 = 280（推荐，可调整为200-300）
```

**节点定位：**
```
节点X = 列X[列索引] - 节点宽度 / 2
节点Y = 基础Y + 列内索引 × (节点高度 + 间距)

节点宽度 = 160
节点高度 = 60
纵向间距 = 120
基础Y = 80
```

**列间连接线：**
```
从当前列最后一个节点右侧 (exitX=1, exitY=0.5) 出
到下一列第一个节点左侧 (entryX=0, entryY=0.5) 进
使用路径点引导：先右移，再上/下移，再右移
```

**连接线规则：**
```
列内连接：从上节点底部中心 (exitX=0.5, exitY=1) 到下节点顶部中心 (entryX=0.5, entryY=0)
列间连接：从右侧 (exitX=1, exitY=0.5) 到左侧 (entryX=0, entryY=0.5)，带路径点数组
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1600 | 容纳3-4列 | 1200-2000 |
| 画布高度 | 动态计算 | 根据每列节点数 | 800-1400 |
| 每列节点数 | 3 | 每列最多节点数 | 3-4 |
| 列间距 | 280 | 列中心距离 | 200-300 |
| 纵向间距 | 120 | 节点垂直间距 | 100-140 |
| 节点宽度 | 160 | 所有节点统一宽度 | 140-180 |
| 节点高度 | 60 | 所有节点统一高度 | 50-70 |
| 左边距 | 100 | 第一列左侧空白 | 80-150 |
| 右边距 | 100 | 最后一列右侧空白 | 80-150 |
| 顶部边距 | 80 | 第一行上方空白 | 60-100 |
| 底部边距 | 80 | 最后一行下方空白 | 60-100 |

---

## 关键共识

### 重要提示

⚠️ **本示例仅供结构参考**
- 展示正确的 XML 语法、Z字布局策略和列间连接方式
- **严禁直接复制**示例中的节点内容、数量或固定坐标
- 必须根据用户需求**动态计算**列数、每列节点数和所有坐标
- 参考示例的**分列策略和转折连接**，而非具体数值

### 样式规范

**开始节点样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;
      fillColor=#f5f5f5;strokeColor=#666666;"
```

**普通节点样式（按列分配颜色）：**
```xml
<!-- 第1列（蓝色系） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#dae8fc;strokeColor=#6c8ebf;fontStyle=1"

<!-- 第2列（橙色系） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#ffe6cc;strokeColor=#d79b00;"

<!-- 第3列（绿色系） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1"
```

**结束节点样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;
      fillColor=#f5f5f5;strokeColor=#666666;"
```

**连接线样式：**
```xml
<!-- 列内连接 -->
style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;
      strokeColor=#333333;endArrow=block;"

<!-- 列间连接 -->
style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;
      strokeColor=#333333;endArrow=block;"
```

### 配色建议

**Z字布局的典型配色：**
- **开始/结束节点**：`fillColor=#f5f5f5 strokeColor=#666666` - 灰色中性
- **第1列（需求阶段）**：`fillColor=#dae8fc strokeColor=#6c8ebf` - 蓝色系
- **第2列（开发阶段）**：`fillColor=#ffe6cc strokeColor=#d79b00` - 橙色系
- **第3列（部署阶段）**：`fillColor=#d5e8d4 strokeColor=#82b366` - 绿色系
- **第4列（可选）**：`fillColor=#e1d5e7 strokeColor=#9673a6` - 紫色系

**配色原则：**
- 按列分配不同颜色，区分阶段
- 每列内部使用统一颜色
- 列标题节点可使用粗体 `fontStyle=1`

---

## 案例代码

### 使用方法
复制下方完整代码，在 diagrams.net 选择 **File → Import from → Text**，粘贴即可打开

### 完整 XML（9步Z字示例）

```xml
<mxfile host="app.diagrams.net">
  <diagram name="Z字流程示例">
    <mxGraphModel dx="1400" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1000" pageHeight="600" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        
        <!-- 开始节点 -->
        <mxCell id="start" value="开始" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="1">
          <mxGeometry x="190" y="60" width="120" height="40" as="geometry" />
        </mxCell>
        
        <!-- 第1列节点（蓝色系 - 需求阶段） -->
        <mxCell id="n1" value="1. 需求收集&lt;br&gt;(Backlog)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="170" y="160" width="160" height="60" as="geometry" />
        </mxCell>
        
        <mxCell id="n2" value="2. 原型设计&lt;br&gt;(Prototype)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
          <mxGeometry x="170" y="280" width="160" height="60" as="geometry" />
        </mxCell>
        
        <mxCell id="n3" value="3. 需求评审&lt;br&gt;(Review)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
          <mxGeometry x="170" y="400" width="160" height="60" as="geometry" />
        </mxCell>
        
        <!-- 第2列节点（橙色系 - 开发阶段） -->
        <mxCell id="n4" value="4. 技术方案&lt;br&gt;(Tech Spec)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="450" y="160" width="160" height="60" as="geometry" />
        </mxCell>
        
        <mxCell id="n5" value="5. 代码开发&lt;br&gt;(Coding)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;" vertex="1" parent="1">
          <mxGeometry x="450" y="280" width="160" height="60" as="geometry" />
        </mxCell>
        
        <mxCell id="n6" value="6. 联调测试&lt;br&gt;(Integration)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;" vertex="1" parent="1">
          <mxGeometry x="450" y="400" width="160" height="60" as="geometry" />
        </mxCell>
        
        <!-- 第3列节点（绿色系 - 部署阶段） -->
        <mxCell id="n7" value="7. 预发布&lt;br&gt;(Staging)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="730" y="160" width="160" height="60" as="geometry" />
        </mxCell>
        
        <mxCell id="n8" value="8. 灰度观察&lt;br&gt;(Canary)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;" vertex="1" parent="1">
          <mxGeometry x="730" y="280" width="160" height="60" as="geometry" />
        </mxCell>
        
        <!-- 结束节点 -->
        <mxCell id="end" value="9. 全量上线&lt;br&gt;(Launch)" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="1">
          <mxGeometry x="730" y="400" width="160" height="50" as="geometry" />
        </mxCell>
        
        <!-- 连接线 -->
        <!-- 开始到第一个节点 -->
        <mxCell id="e0" edge="1" parent="1" source="start" target="n1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 第1列内部连接 -->
        <mxCell id="e1" edge="1" parent="1" source="n1" target="n2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <mxCell id="e2" edge="1" parent="1" source="n2" target="n3" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 第2列内部连接 -->
        <mxCell id="e4" edge="1" parent="1" source="n4" target="n5" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <mxCell id="e5" edge="1" parent="1" source="n5" target="n6" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 第3列内部连接 -->
        <mxCell id="e7" edge="1" parent="1" source="n7" target="n8" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <mxCell id="e8" edge="1" parent="1" source="n8" target="end" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        
        <!-- 列间转折连接 -->
        <!-- 第1列到第2列 -->
        <mxCell id="e3" edge="1" parent="1" source="n3" target="n4" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;" exitX="1" exitY="0.5" entryX="0" entryY="0.5">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="390" y="430" />
              <mxPoint x="390" y="190" />
            </Array>
          </mxGeometry>
        </mxCell>
        
        <!-- 第2列到第3列 -->
        <mxCell id="e6" edge="1" parent="1" source="n6" target="n7" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#333333;endArrow=block;" exitX="1" exitY="0.5" entryX="0" entryY="0.5">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="670" y="430" />
              <mxPoint x="670" y="190" />
            </Array>
          </mxGeometry>
        </mxCell>
        
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

## 扩展说明

### 节点数量调整

**当节点总数变化时：**
1. 计算列数：`列数 = ceiling(节点总数 / 每列节点数)`
2. 重新计算画布宽度：`画布宽度 = 列数 × (节点宽度 + 列间距) + 左边距 + 右边距`
3. 按公式分配节点到各列
4. 调整列间转折点位置，确保不与其他节点重叠

**计算公式：**
```
节点所属列索引 = floor(节点全局索引 / 每列节点数)
节点列内索引 = 节点全局索引 % 每列节点数
节点X = 左边距 + 列索引 × (节点宽度 + 列间距)
节点Y = 基础Y + 列内索引 × (节点高度 + 间距)

列间转折点X = 当前列X + 节点宽度/2 + 列间距/2
列间转折点Y = min(起点Y, 终点Y)（向上转折）或 max(起点Y, 终点Y)（向下转折）
```

### 列数调整

**当节点数过多时：**
1. 考虑增加每列节点数（从3增加到4）
2. 或增加列数（从3列增加到4列）
3. 相应调整画布宽度和高度
4. 为每列分配不同配色

### 对齐优化

**生成后不需要运行对齐脚本**
- Z字布局已包含严格的列对齐逻辑
- 关键是确保同一列的节点中心X值相同
- 列间距保持一致即可
