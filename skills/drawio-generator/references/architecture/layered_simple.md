# 架构图 - 简单分层示例

**适用场景：** 展示3-5层清晰的技术栈，每层包含多个独立组件（MVC、三层架构、基础分层）

---

## 布局规范

### 整体策略
**核心思路：** 自上而下分层堆叠，全宽层容器，垂直连接表示依赖

**布局特征：**
- 层容器全宽（1120px），子组件水平均分
- 层间距固定（250px），保持视觉清晰
- 左侧添加层标签，中间可选中心参考线
- 垂直连接线表示跨层依赖关系

### 坐标计算公式

**画布参数：**
```
画布宽度 = 1600 (固定)
画布高度 = 层数 × 250 + 150 (基础边距)
视口宽度 = 1554
视口高度 = 946
```

**层容器定位：**
```
容器X = 240 (固定起始位置)
容器Y = 50 + 层索引 × 250
容器宽 = 1120 (固定全宽)
容器高 = 180 (固定)
```

**层标签定位：**
```
标签X = 40
标签Y = 容器Y + 40 (与容器对齐)
标签宽 = 100
标签高 = 40
```

**子组件定位（层内，使用相对坐标）：**
```
组件数量 = N
步长 = (1120 - 160) / (N - 1)  // 首尾留边距80px
组件X = 160 + 组件索引 × 步长 - 100  // 组件宽200，中心对齐
组件Y = 70 (相对容器)
组件宽 = 200
组件高 = 80
```

**连接线规则：**
```
跨层连接：从上层组件底部 (exitY=1) 到下层组件顶部 (entryY=0)
层内连接：使用 (exitX=0.5, exitY=1) 和 (entryX=0.5, entryY=0)
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1600 | 固定宽度 | 1400-1800 |
| 画布高度 | 层数×250+150 | 动态计算 | - |
| 层容器宽 | 1120 | 固定全宽 | 1000-1300 |
| 层容器高 | 180 | 固定高度 | 140-220 |
| 层间距 | 250 | 容器起始Y的增量 | 200-300 |
| 组件宽度 | 200 | 标准组件宽 | 150-250 |
| 组件高度 | 80 | 标准组件高 | 60-100 |
| 左侧边距 | 240 | 层容器起始X | 200-280 |

---

## 关键共识

### 重要提示
⚠️ **本示例仅供结构参考**
- 展示正确的容器嵌套、相对坐标、连接方式
- **严禁复制**示例的节点内容、数量、固定坐标
- 必须根据实际层数和组件数**动态计算**所有坐标
- 参考**布局策略和公式**，而非具体数值

### 样式规范

**层容器样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor={层级配色};strokeColor={边框色};strokeWidth=2;
      verticalAlign=top;align=center;spacingTop=10;
      fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;"
```

**子组件样式：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#ffffff;strokeColor={继承层容器边框色};
      fontSize=12;fontStyle=0;"
```

**连接线样式：**
```xml
<!-- 强依赖（实线） -->
style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;
      jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;
      entryX=0.5;entryY=0;exitX=0.5;exitY=1;"

<!-- 弱依赖（虚线） -->
style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;
      jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;
      dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;"
```

### 配色建议
**简单分层的典型配色：**
- **表现层**：`fillColor=#dae8fc strokeColor=#6c8ebf` - 蓝色系
- **业务层**：`fillColor=#d5e8d4 strokeColor=#82b366` - 绿色系
- **数据层**：`fillColor=#f8cecc strokeColor=#b85450` - 红色系
- **中心线/标签**：`strokeColor=#CCCCCC fontColor=#333333` - 灰色系

**配色原则：**
- 每层使用统一配色区分
- 子组件填充白色，边框继承层容器颜色
- 连接线统一使用中性灰 `#666666`

---

## 案例代码

### 完整 XML（3层9组件示例）

```xml
<mxGraphModel dx="1554" dy="946" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="900" background="#ffffff" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    
    <!-- 中心参考线（可选） -->
    <mxCell id="guide_center" value="" style="edgeStyle=none;html=1;strokeColor=#CCCCCC;strokeWidth=1;dashed=1;endArrow=none;" parent="1" edge="1">
      <mxGeometry relative="1" as="geometry">
        <mxPoint x="800" y="40" as="sourcePoint" />
        <mxPoint x="800" y="840" as="targetPoint" />
      </mxGeometry>
    </mxCell>
    
    <!-- 层标签 -->
    <mxCell id="lbl_presentation" value="表现层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="40" y="90" width="100" height="40" as="geometry" />
    </mxCell>
    <mxCell id="lbl_business" value="业务层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="40" y="340" width="100" height="40" as="geometry" />
    </mxCell>
    <mxCell id="lbl_data" value="数据层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="40" y="590" width="100" height="40" as="geometry" />
    </mxCell>

    <!-- 第1层：表现层 -->
    <mxCell id="layer_presentation" value="表现层 (Presentation Layer)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;" parent="1" vertex="1">
      <mxGeometry x="240" y="50" width="1120" height="180" as="geometry" />
    </mxCell>
    <mxCell id="web_ui" value="Web UI" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" parent="layer_presentation" vertex="1">
      <mxGeometry x="160" y="70" width="200" height="80" as="geometry" />
    </mxCell>
    <mxCell id="mobile_app" value="Mobile App" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" parent="layer_presentation" vertex="1">
      <mxGeometry x="460" y="70" width="200" height="80" as="geometry" />
    </mxCell>
    <mxCell id="api_endpoint" value="API Endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" parent="layer_presentation" vertex="1">
      <mxGeometry x="760" y="70" width="200" height="80" as="geometry" />
    </mxCell>

    <!-- 第2层：业务层 -->
    <mxCell id="layer_business" value="业务层 (Business Layer)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;" parent="1" vertex="1">
      <mxGeometry x="240" y="300" width="1120" height="180" as="geometry" />
    </mxCell>
    <mxCell id="user_service" value="User Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="layer_business" vertex="1">
      <mxGeometry x="160" y="70" width="200" height="80" as="geometry" />
    </mxCell>
    <mxCell id="order_service" value="Order Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="layer_business" vertex="1">
      <mxGeometry x="460" y="70" width="200" height="80" as="geometry" />
    </mxCell>
    <mxCell id="payment_service" value="Payment Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="layer_business" vertex="1">
      <mxGeometry x="760" y="70" width="200" height="80" as="geometry" />
    </mxCell>

    <!-- 第3层：数据层 -->
    <mxCell id="layer_data" value="数据层 (Data Layer)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;" parent="1" vertex="1">
      <mxGeometry x="240" y="550" width="1120" height="180" as="geometry" />
    </mxCell>
    <mxCell id="db_mysql" value="MySQL" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="200" y="60" width="120" height="100" as="geometry" />
    </mxCell>
    <mxCell id="db_redis" value="Redis Cache" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="500" y="60" width="120" height="100" as="geometry" />
    </mxCell>
    <mxCell id="db_mongo" value="MongoDB" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="800" y="60" width="120" height="100" as="geometry" />
    </mxCell>

    <!-- 连接线 -->
    <mxCell id="link_web_user" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="web_ui" target="user_service" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_mobile_order" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="mobile_app" target="order_service" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_api_payment" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="api_endpoint" target="payment_service" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_user_mysql" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="user_service" target="db_mysql" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_order_redis" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="order_service" target="db_redis" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_payment_mongo" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="payment_service" target="db_mongo" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>

  </root>
</mxGraphModel>
```

---

## 扩展说明

### 层数调整
**当增加或减少层级时：**
1. 重新计算画布高度：`新高度 = 层数 × 250 + 150`
2. 按公式更新每层容器Y：`容器Y = 50 + 层索引 × 250`
3. 更新层标签Y坐标：`标签Y = 容器Y + 40`
4. 更新所有跨层连接线

### 组件数量调整
**当层内组件数量变化时：**
1. 重新计算步长：`步长 = (1120 - 160) / (组件数 - 1)`
2. 按公式更新组件X：`组件X = 160 + 索引 × 步长 - 100`
3. 如组件过多（>6个），考虑增加容器宽度或换行
