# 流程图 - 普通布局示例

**适用场景：** 适用于3-8个步骤的标准流程，可包含判断节点、分支和循环

---

## 布局规范

### 整体策略

**核心思路：** 自上而下纵向排列，节点中心对齐，使用侧边分支表示判断结果，虚线表示循环回路

**布局特征：**
- 主流程纵向排列，中心对齐
- 判断节点使用菱形，分支向左右延伸
- 循环使用虚线，错开主流程进入点
- 节点间距充足，避免连线拥挤

### 坐标计算公式

**画布参数：**
```
画布宽度 = 800（可根据侧边分支调整）
画布高度 = 节点数 × (节点高度 + 间距) + 顶部边距 + 底部边距
视口宽度 = 1000
视口高度 = 1000
```

**主流程节点定位：**
```
主轴X = 400（画布中心，可调整）
节点X = 主轴X - 节点宽度 / 2
节点Y = 基础Y + 索引 × (节点高度 + 间距)

节点宽度 = 160（普通节点）或 140（判断节点菱形）
节点高度 = 60（普通节点）或 80（判断节点菱形）
纵向间距 = 100-120px
```

**侧边分支节点定位：**
```
左侧分支X = 主轴X - 主流程节点宽度/2 - 横向间距 - 分支节点宽度
右侧分支X = 主轴X + 主流程节点宽度/2 + 横向间距

横向间距 = 100-150px
分支节点Y = 与判断节点Y对齐或略有偏移
```

**连接线规则：**
```
主流程：从上节点底部中心 (exitX=0.5, exitY=1) 到下节点顶部中心 (entryX=0.5, entryY=0)
分支（否）：从判断节点左侧 (exitX=0, exitY=0.5) 到分支节点右侧 (entryX=1, entryY=0.5)
分支（是）：从判断节点底部向下继续主流程
循环回路：从分支节点顶部 (exitX=0.5, exitY=0) 到主流程节点左侧 (entryX=0, entryY=0.5)，使用虚线
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 800 | 足够容纳主流程和侧边分支 | 600-1000 |
| 画布高度 | 动态计算 | 节点数×180 + 200 | 根据节点数 |
| 主轴X | 400 | 主流程中心线 | 300-500 |
| 基础Y | 80 | 第一个节点顶部位置 | 60-100 |
| 纵向间距 | 100 | 主流程节点间垂直间距 | 80-120 |
| 横向间距 | 120 | 主流程到侧边分支距离 | 100-150 |
| 开始/结束宽度 | 120 | 椭圆节点宽度 | 100-140 |
| 开始/结束高度 | 40 | 椭圆节点高度 | 35-45 |
| 普通节点宽度 | 160 | 矩形节点宽度 | 140-180 |
| 普通节点高度 | 60 | 矩形节点高度 | 50-80 |
| 判断节点宽度 | 140 | 菱形节点宽度 | 140-160 |
| 判断节点高度 | 80 | 菱形节点高度 | 70-90 |

---

## 关键共识

### 重要提示

⚠️ **本示例仅供结构参考**
- 展示正确的 XML 语法、样式定义和连接逻辑
- **严禁直接复制**示例中的节点内容、数量或固定坐标
- 必须根据用户需求**动态计算**所有坐标值和布局参数
- 参考示例的**对齐策略和连接方式**，而非具体数值

### 样式规范

**开始/结束节点样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;
      fillColor=#f5f5f5;strokeColor=#666666;fontStyle=1"
```

**普通处理节点样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#dae8fc;strokeColor=#6c8ebf;"
```

**判断节点样式（必须使用rhombus）：**
```xml
style="rhombus;whiteSpace=wrap;html=1;
      fillColor=#fff2cc;strokeColor=#d6b656;"
```

**侧边分支节点样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#f8cecc;strokeColor=#b85450;"
```

**主流程连接线样式：**
```xml
style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
```

**循环回路连接线样式：**
```xml
style="edgeStyle=orthogonalEdgeStyle;rounded=1;dashed=1;html=1;"
```

### 配色建议

**普通布局的典型配色：**
- **开始/结束节点**：`fillColor=#f5f5f5 strokeColor=#666666` - 灰色中性
- **普通处理节点**：`fillColor=#dae8fc strokeColor=#6c8ebf` - 蓝色系（主流程）
- **判断节点**：`fillColor=#fff2cc strokeColor=#d6b656` - 黄色系（决策点）
- **侧边分支节点**：`fillColor=#f8cecc strokeColor=#b85450` - 红色系（异常/修正）
- **成功完成节点**：`fillColor=#d5e8d4 strokeColor=#82b366` - 绿色系（可选）

**配色原则：**
- 主流程使用统一蓝色系
- 判断节点使用醒目的黄色
- 异常分支使用红色突出显示

---

## 案例代码

### 使用方法
复制下方完整代码，在 diagrams.net 选择 **File → Import from → Text**，粘贴即可打开

### 案例一 XML（带判断和循环的示例）

```xml
<mxGraphModel dx="976" dy="786" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="2" value="开始：需求池" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;fontStyle=1" parent="1" vertex="1">
      <mxGeometry x="280" y="80" width="120" height="40" as="geometry" />
    </mxCell>
    <mxCell id="9" value="结束：上线完成" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;fontStyle=1" parent="1" vertex="1">
      <mxGeometry x="280" y="800" width="120" height="40" as="geometry" />
    </mxCell>
    <mxCell id="3" value="需求评审会议" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" parent="1" vertex="1">
      <mxGeometry x="260" y="180" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="4" value="评审通过?" style="rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;" parent="1" vertex="1">
      <mxGeometry x="260" y="280" width="160" height="80" as="geometry" />
    </mxCell>
    <mxCell id="6" value="编码与开发" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;" parent="1" vertex="1">
      <mxGeometry x="260" y="500" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="7" value="测试通过?" style="rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;" parent="1" vertex="1">
      <mxGeometry x="260" y="600" width="160" height="80" as="geometry" />
    </mxCell>
    <mxCell id="10" value="修订需求文档" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;" parent="1" vertex="1">
      <mxGeometry x="40" y="290" width="140" height="60" as="geometry" />
    </mxCell>
    <mxCell id="11" value="修复 Bug" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;" parent="1" vertex="1">
      <mxGeometry x="480" y="610" width="140" height="60" as="geometry" />
    </mxCell>
    <mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="2" target="3" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="3" target="4" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e3" value="是" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="4" target="6" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e4" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="6" target="7" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e5" value="是" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="7" target="9" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="loop_in_1" value="否" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="4" target="10" edge="1" exitX="0" exitY="0.5" entryX="1" entryY="0.5">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="loop_in_2" value="否" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="7" target="11" edge="1" exitX="1" exitY="0.5" entryX="0" entryY="0.5">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="loop_back_1" style="edgeStyle=orthogonalEdgeStyle;rounded=1;dashed=1;" parent="1" source="10" target="3" edge="1" exitX="0.5" exitY="0" entryX="0" entryY="0.5">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="110" y="210" />
        </Array>
      </mxGeometry>
    </mxCell>
    <mxCell id="loop_back_2" style="edgeStyle=orthogonalEdgeStyle;rounded=1;dashed=1;" parent="1" source="11" target="6" edge="1" exitX="0.5" exitY="0" entryX="1" entryY="0.5">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="550" y="530" />
        </Array>
      </mxGeometry>
    </mxCell>
  </root>
</mxGraphModel>

```

### 案例二 XML（三分支结构）

``` xml
<mxGraphModel dx="1301" dy="1048" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="start" value="开始" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;" parent="1" vertex="1">
      <mxGeometry x="440" y="60" width="120" height="40" as="geometry" />
    </mxCell>
    <mxCell id="query" value="查询订单状态" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;" parent="1" vertex="1">
      <mxGeometry x="420" y="140" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="check_status" value="订单状态？" style="rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;" parent="1" vertex="1">
      <mxGeometry x="430" y="240" width="140" height="80" as="geometry" />
    </mxCell>
    <mxCell id="branch_unpaid" value="提醒用户支付" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;" parent="1" vertex="1">
      <mxGeometry x="140" y="250" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="branch_shipping" value="显示物流信息" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;" parent="1" vertex="1">
      <mxGeometry x="420" y="380" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="branch_completed" value="提示评价订单" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;" parent="1" vertex="1">
      <mxGeometry x="700" y="250" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="merge" value="显示结果" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;" parent="1" vertex="1">
      <mxGeometry x="420" y="500" width="160" height="60" as="geometry" />
    </mxCell>
    <mxCell id="end" value="结束" style="rounded=1;whiteSpace=wrap;html=1;arcSize=50;fillColor=#f5f5f5;strokeColor=#666666;" parent="1" vertex="1">
      <mxGeometry x="440" y="600" width="120" height="40" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="start" target="query" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="query" target="check_status" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-3" value="待支付" style="edgeStyle=orthogonalEdgeStyle;rounded=0;exitX=0;exitY=0.5;entryX=1;entryY=0.5;" parent="1" source="check_status" target="branch_unpaid" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-4" value="配送中" style="edgeStyle=orthogonalEdgeStyle;rounded=0;exitX=0.5;exitY=1;entryX=0.5;entryY=0;" parent="1" source="check_status" target="branch_shipping" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-5" value="已完成" style="edgeStyle=orthogonalEdgeStyle;rounded=0;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" parent="1" source="check_status" target="branch_completed" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-6" style="edgeStyle=orthogonalEdgeStyle;rounded=0;exitX=0.5;exitY=1;entryX=0;entryY=0.5;" parent="1" source="branch_unpaid" target="merge" edge="1">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="220" y="530" />
        </Array>
      </mxGeometry>
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-7" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="branch_shipping" target="merge" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-8" style="edgeStyle=orthogonalEdgeStyle;rounded=0;exitX=0.5;exitY=1;entryX=1;entryY=0.5;" parent="1" source="branch_completed" target="merge" edge="1">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="780" y="530" />
        </Array>
      </mxGeometry>
    </mxCell>
    <mxCell id="Jv53nbsY_RxWU7-Uen46-9" style="edgeStyle=orthogonalEdgeStyle;rounded=0;" parent="1" source="merge" target="end" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
  </root>
</mxGraphModel>

```
---

## 扩展说明

### 节点数量调整

**当节点数量增加时：**
1. 重新计算总高度：`总高度 = 节点数 × (节点高度 + 间距) + 顶部边距 + 底部边距`
2. 按公式更新每个节点的Y坐标：`节点Y = 基础Y + 索引 × (节点高度 + 间距)`
3. 调整画布高度 `pageHeight` 属性
4. 保持主轴X不变，确保中心对齐

**计算公式：**
```
基础Y = 80
节点高度 = 60（普通）或 80（菱形）
间距 = 100
节点Y[i] = 基础Y + i × (节点高度 + 间距)
画布高度 = 节点Y[最后一个] + 节点高度 + 底部边距(60)
```

### 分支数量调整

**当分支增加时：**
1. 评估是否需要扩展画布宽度
2. 调整横向间距以避免重叠
3. 循环回路错开进入点，使用不同的Y值或连接点
4. 必要时使用路径点 `<mxPoint>` 绕过其他节点

### 对齐优化

**生成后不需要运行对齐脚本**
- 普通流程布局相对简单
- 严格按照公式计算坐标即可保证对齐
- 关键是确保同一列节点的中心X值相同
