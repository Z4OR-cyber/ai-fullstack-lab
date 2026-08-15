# 架构图 - 中心辐射网络示例

**适用场景：** 展示以中心节点为核心的辐射结构（网关架构、API Hub、调度中心、星型拓扑）

---

## 布局规范

### 整体策略
**核心思路：** 中心节点居中突出，周围节点按层级环绕

**布局特征：**
- 中心节点：加粗边框（strokeWidth=3）+ 阴影（shadow=1）
- 上层（客户端）：3个节点，Y=80-100
- 左侧（服务）：2个节点，X=100
- 右侧（服务）：2个节点，X=1140
- 下层（数据）：3个节点，Y=750
- 所有连接线汇聚到中心

### 坐标计算公式

**画布参数：**
```
画布宽度 = 1400
画布高度 = 900
视口宽度 = 1554
视口高度 = 946
```

**中心节点定位：**
```
centerX = 550
centerY = 400
centerW = 300
centerH = 120
```

**周围节点分布（按象限）：**
```
上层（客户端）：
  Y = 80-100
  左: X=300, 中: X=620, 右: X=940
  
左侧（服务）：
  X = 100
  上: Y=280, 下: Y=520
  
右侧（服务）：
  X = 1140
  上: Y=280, 下: Y=520
  
下层（数据）：
  Y = 750
  左: X=400, 中: X=640, 右: X=880

节点标准尺寸：
  周围节点宽 = 160
  周围节点高 = 80
  数据库高 = 100
```

**连接线入口参数：**
```
上层到中心：exitX=0.5, exitY=1 → entryY=0
  左节点: entryX=0.25
  中节点: entryX=0.5
  右节点: entryX=0.75

中心到左侧：exitX=0, exitY=0.25/0.75 → entryX=1, entryY=0.5
中心到右侧：exitX=1, exitY=0.25/0.75 → entryX=0, entryY=0.5
中心到下层：exitY=1, exitX=0.25/0.5/0.75 → entryX=0.5, entryY=0
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1400 | 适中宽度 | 1200-1600 |
| 画布高度 | 900 | 适中高度 | 800-1000 |
| 中心节点宽 | 300 | 突出显示 | 250-350 |
| 中心节点高 | 120 | 突出显示 | 100-140 |
| 周围节点宽 | 160 | 标准宽度 | 140-180 |
| 周围节点高 | 80 | 标准高度 | 60-100 |

---

## 关键共识

### 重要提示
⚠️ **本示例仅供结构参考**
- 展示**辐射布局**和**多方向连接**的技巧
- **严禁复制**示例的节点内容、数量、固定坐标
- 节点数量可根据实际调整，但保持辐射结构
- 连接线必须使用不同的出入口参数（exitX/Y, entryX/Y）

### 样式规范

**中心节点（核心）：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=3;
      fontSize=16;fontStyle=1;shadow=1;"
```

**周围节点（按类型）：**
```xml
<!-- 客户端/外部系统 -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;"

<!-- 业务服务 -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;"

<!-- 数据存储 -->
style="shape=cylinder3;whiteSpace=wrap;html=1;
      boundedLbl=1;backgroundOutline=1;size=15;
      fillColor=#f8cecc;strokeColor=#b85450;fontSize=14;"
```

**连接线样式（按类型）：**
```xml
<!-- 客户端到中心（实线） -->
style="edgeStyle=orthogonalEdgeStyle;rounded=1;
      orthogonalLoop=1;jettySize=auto;html=1;
      strokeWidth=2;strokeColor=#6c8ebf;
      entryX=...;entryY=...;exitX=...;exitY=...;"

<!-- 中心到服务（实线，不同颜色） -->
style="...;strokeWidth=2;strokeColor=#82b366;..."

<!-- 中心到数据（虚线） -->
style="...;strokeWidth=2;strokeColor=#b85450;dashed=1;..."

<!-- 服务间调用（虚线，弯曲） -->
style="...;strokeWidth=1;strokeColor=#82b366;dashed=1;curved=1;"
```

### 配色建议
**辐射网络的典型配色：**
- **中心节点**：蓝色 `#dae8fc/#6c8ebf` + 加粗 + 阴影
- **客户端层**：灰色 `#f5f5f5/#666666` （外部系统）
- **服务层**：绿色 `#d5e8d4/#82b366` （核心业务）
- **数据层**：红色 `#f8cecc/#b85450` （持久化）
- **连接线**：按目标节点颜色

---

## 案例代码

### 完整 XML（中心辐射10节点示例）

```xml
<mxGraphModel dx="1554" dy="946" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1400" pageHeight="900" background="#ffffff" math="0" shadow="0">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    
    <!-- 中心节点 -->
    <mxCell id="center_gateway" value="API Gateway&lt;br&gt;(Core)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=3;fontSize=16;fontStyle=1;shadow=1;" parent="1" vertex="1">
      <mxGeometry x="550" y="400" width="300" height="120" as="geometry"/>
    </mxCell>

    <!-- 上层节点 - 客户端 -->
    <mxCell id="client_web" value="Web Client" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="300" y="100" width="160" height="80" as="geometry"/>
    </mxCell>
    <mxCell id="client_mobile" value="Mobile App" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="620" y="80" width="160" height="80" as="geometry"/>
    </mxCell>
    <mxCell id="client_iot" value="IoT Device" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="940" y="100" width="160" height="80" as="geometry"/>
    </mxCell>

    <!-- 左侧节点 - 业务服务 -->
    <mxCell id="svc_user" value="User Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="100" y="280" width="160" height="80" as="geometry"/>
    </mxCell>
    <mxCell id="svc_order" value="Order Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="100" y="520" width="160" height="80" as="geometry"/>
    </mxCell>

    <!-- 右侧节点 - 业务服务 -->
    <mxCell id="svc_payment" value="Payment Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="1140" y="280" width="160" height="80" as="geometry"/>
    </mxCell>
    <mxCell id="svc_notify" value="Notification Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="1140" y="520" width="160" height="80" as="geometry"/>
    </mxCell>

    <!-- 下层节点 - 数据存储 -->
    <mxCell id="db_mysql" value="MySQL" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#f8cecc;strokeColor=#b85450;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="400" y="750" width="120" height="100" as="geometry"/>
    </mxCell>
    <mxCell id="db_redis" value="Redis" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#f8cecc;strokeColor=#b85450;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="640" y="750" width="120" height="100" as="geometry"/>
    </mxCell>
    <mxCell id="db_mq" value="Message Queue" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#f8cecc;strokeColor=#b85450;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="880" y="750" width="120" height="100" as="geometry"/>
    </mxCell>

    <!-- 客户端到网关的连接 -->
    <mxCell id="link_web_gw" value="HTTPS" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#6c8ebf;entryX=0.25;entryY=0;exitX=0.5;exitY=1;" parent="1" source="client_web" target="center_gateway" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_mobile_gw" value="HTTPS" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#6c8ebf;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="client_mobile" target="center_gateway" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_iot_gw" value="MQTT" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#6c8ebf;entryX=0.75;entryY=0;exitX=0.5;exitY=1;" parent="1" source="client_iot" target="center_gateway" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 网关到业务服务的连接 -->
    <mxCell id="link_gw_user" value="RPC" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#82b366;entryX=1;entryY=0.5;exitX=0;exitY=0.25;" parent="1" source="center_gateway" target="svc_user" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_order" value="RPC" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#82b366;entryX=1;entryY=0.5;exitX=0;exitY=0.75;" parent="1" source="center_gateway" target="svc_order" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_payment" value="RPC" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#82b366;entryX=0;entryY=0.5;exitX=1;exitY=0.25;" parent="1" source="center_gateway" target="svc_payment" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_notify" value="RPC" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#82b366;entryX=0;entryY=0.5;exitX=1;exitY=0.75;" parent="1" source="center_gateway" target="svc_notify" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 网关到存储的连接 -->
    <mxCell id="link_gw_mysql" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.25;exitY=1;" parent="1" source="center_gateway" target="db_mysql" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_redis" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="center_gateway" target="db_redis" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_mq" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.75;exitY=1;" parent="1" source="center_gateway" target="db_mq" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 服务间调用（可选） -->
    <mxCell id="link_order_user" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=1;strokeColor=#82b366;dashed=1;curved=1;" parent="1" source="svc_order" target="svc_user" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_payment_notify" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=1;strokeColor=#82b366;dashed=1;curved=1;" parent="1" source="svc_payment" target="svc_notify" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

  </root>
</mxGraphModel>
```

---

## 扩展说明

### 节点数量调整

**增加周围节点时：**
1. **按层级分组**：确定新节点属于哪一层（上/左/右/下）
2. **计算间距**：
   ```
   上层间距 = (画布宽 - 边距×2) / (上层节点数 + 1)
   左侧间距 = (中心Y - 上边距 - 下边距) / (左侧节点数 + 1)
   ```
3. **调整连接入口**：
   ```
   exitX/exitY 按中心节点边缘均分（0.25, 0.5, 0.75等）
   entryX/entryY 指向周围节点中心（通常0.5）
   ```

**示例：增加第4个上层节点**
```xml
<mxCell id="client_desktop" value="Desktop App" 
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;" 
        parent="1" vertex="1">
  <mxGeometry x="1200" y="100" width="160" height="80" as="geometry"/>
</mxCell>

<mxCell id="link_desktop_gw" value="HTTPS" 
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;
               strokeWidth=2;strokeColor=#6c8ebf;entryX=0.875;entryY=0;exitX=0.5;exitY=1;" 
        parent="1" source="client_desktop" target="center_gateway" edge="1">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

