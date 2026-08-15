# 架构图 - 混合微服务示例

**适用场景：** 展示既有分层又有服务间调用的复杂系统（微服务架构、多Agent系统、SOA）

---

## 布局规范

### 整体策略
**核心思路：** 宏观分层（网关→服务→数据），微观网络（服务间调用）

**布局特征：**
- **接入层**：全宽容器（1120px），包含3个网关组件
- **服务层**：3个并列微服务容器，每个容器内有3层子组件
- **数据层**：全宽容器（1120px），包含各服务独立数据库 + 共享缓存
- **垂直连接**：网关→服务、服务→数据库（虚线）
- **横向连接**：服务间RPC/Event调用（虚线弯曲）

### 坐标计算公式

**画布参数：**
```
画布宽度 = 1600
画布高度 = 1100
视口宽度 = 1554
视口高度 = 946
```

**层定位（3层）：**
```
接入层：
  Y = 40
  高度 = 140
  
服务层：
  Y = 240
  高度 = 340
  
数据层：
  Y = 690 (或计算: 240 + 340 + 110间距)
  高度 = 180
```

**层标签定位：**
```
标签X = 40
标签宽 = 100
标签高 = 40

接入层标签Y = 80  (层Y + 40)
服务层标签Y = 350 (层Y + 110)
数据层标签Y = 810 (层Y + 120)
```

**服务容器定位（3个并列）：**
```
容器数 = 3
容器宽 = 320
容器间距 = 40
总宽度验证 = 320×3 + 40×2 = 1040 < 1120 ✓

容器X计算：
  容器1 (User):    X = 240
  容器2 (Order):   X = 240 + 320 + 40 = 600
  容器3 (Payment): X = 600 + 320 + 40 = 960 (实际调整为1040)

容器Y = 240 (服务层Y)
容器高 = 340
```

**容器内子组件（垂直3个，使用相对坐标）：**
```
子组件parent = 容器id
子组件X = 40 (相对容器)
子组件宽 = 240
子组件高 = 60

子组件Y（相对容器）：
  API层:        Y = 60
  Business层:   Y = 140
  Repository层: Y = 220
```

**数据层组件定位（在layer_data容器内，相对坐标）：**
```
数据库节点（4个）：
  User DB:    X = 120, Y = 60
  Order DB:   X = 410, Y = 60
  Payment DB: X = 700, Y = 60
  Redis:      X = 920, Y = 60
  
节点尺寸：
  宽 = 100
  高 = 90
```

**连接线规则：**
```
网关到服务（实线）：
  exitX = 0.25/0.5/0.75, exitY = 1
  entryX = 0.5, entryY = 0
  strokeWidth = 2
  strokeColor = #6c8ebf

服务到数据库（虚线）：
  exitX = 0.5, exitY = 1
  entryX = 0.5, entryY = 0
  strokeWidth = 2
  strokeColor = #b85450
  dashed = 1

服务间调用（虚线弯曲）：
  exitX = 0/1, exitY = 0.5
  entryX = 1/0, entryY = 0.5
  strokeWidth = 2
  strokeColor = #82b366
  dashed = 1
  curved = 1
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1600 | 固定 | 1400-1800 |
| 画布高度 | 1100 | 3层+连接 | 1000-1200 |
| 接入层高 | 140 | 顶层 | 120-160 |
| 服务容器宽 | 320 | 并列3个 | 280-360 |
| 服务容器高 | 340 | 容纳3子组件 | 300-380 |
| 数据层高 | 180 | 底层 | 160-200 |
| 容器间距 | 40 | 水平间距 | 30-60 |

---

## 关键共识

### 重要提示
⚠️ **本示例仅供结构参考**
- 展示**分层+网络**的混合模式
- **严禁复制**示例的节点内容、数量、固定坐标
- 每个微服务独立连接各自数据库
- 服务间调用使用虚线 + curved=1

### 样式规范

**接入层容器：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;
      verticalAlign=top;align=center;spacingTop=10;
      fontSize=14;fontStyle=1;"
```

**接入层子组件（在layer_access内）：**
```xml
<mxCell id="gw_auth" value="Auth" 
        style="rounded=1;whiteSpace=wrap;html=1;
               fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" 
        vertex="1" parent="layer_access">
  <mxGeometry x="200" y="60" width="150" height="50" as="geometry"/>
</mxCell>
```

**微服务容器：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;
      verticalAlign=top;align=center;spacingTop=10;
      fontSize=14;fontStyle=1;"
```

**微服务子组件（在svc_container内）：**
```xml
<mxCell id="svc1_api" value="User API" 
        style="rounded=1;whiteSpace=wrap;html=1;
               fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" 
        vertex="1" parent="svc_container_1">
  <mxGeometry x="40" y="60" width="240" height="60" as="geometry"/>
</mxCell>
```

**数据层容器（虚线边框）：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=2;
      verticalAlign=top;align=center;spacingTop=10;
      fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;"
```

**数据库节点（圆柱，在layer_data内）：**
```xml
<mxCell id="db_user" value="User DB" 
        style="shape=cylinder3;whiteSpace=wrap;html=1;
               boundedLbl=1;backgroundOutline=1;size=15;
               fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" 
        vertex="1" parent="layer_data">
  <mxGeometry x="120" y="60" width="100" height="90" as="geometry"/>
</mxCell>
```

**垂直连接线（网关→服务）：**
```xml
style="edgeStyle=orthogonalEdgeStyle;rounded=1;
      orthogonalLoop=1;jettySize=auto;html=1;
      strokeWidth=2;strokeColor=#6c8ebf;
      entryX=0.5;entryY=0;exitX=0.25;exitY=1;"
```

**垂直连接线（服务→数据库，虚线）：**
```xml
style="edgeStyle=orthogonalEdgeStyle;rounded=1;
      orthogonalLoop=1;jettySize=auto;html=1;
      strokeWidth=2;strokeColor=#b85450;dashed=1;
      entryX=0.5;entryY=0;exitX=0.5;exitY=1;"
```

**服务间调用（横向虚线弯曲）：**
```xml
style="edgeStyle=orthogonalEdgeStyle;rounded=1;
      orthogonalLoop=1;jettySize=auto;html=1;
      strokeWidth=2;strokeColor=#82b366;dashed=1;curved=1;
      entryX=1;entryY=0.5;exitX=0;exitY=0.5;"
```

### 配色建议
**混合架构的典型配色：**
- **接入层**：蓝色 `#dae8fc/#6c8ebf`
- **服务层**：绿色 `#d5e8d4/#82b366` （所有微服务统一）
- **数据层**：红色 `#f8cecc/#b85450`
- **子组件**：白色填充 `#ffffff`，边框继承父容器颜色
- **连接线**：按目标层颜色

---

## 案例代码

### 完整 XML（3层3服务示例）

```xml
<mxGraphModel dx="1554" dy="946" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1100" background="#ffffff" math="0" shadow="0">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>

    <!-- 层标签 -->
    <mxCell id="lbl_access" value="接入层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="40" y="80" width="100" height="40" as="geometry"/>
    </mxCell>
    <mxCell id="lbl_service" value="服务层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="40" y="350" width="100" height="40" as="geometry"/>
    </mxCell>
    <mxCell id="lbl_data" value="数据层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="40" y="810" width="100" height="40" as="geometry"/>
    </mxCell>

    <!-- 接入层 -->
    <mxCell id="layer_access" value="API Gateway" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="240" y="40" width="1120" height="140" as="geometry"/>
    </mxCell>
    
    <mxCell id="gw_auth" value="Auth" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" parent="layer_access" vertex="1">
      <mxGeometry x="200" y="60" width="150" height="50" as="geometry"/>
    </mxCell>
    <mxCell id="gw_route" value="Routing" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" parent="layer_access" vertex="1">
      <mxGeometry x="485" y="60" width="150" height="50" as="geometry"/>
    </mxCell>
    <mxCell id="gw_limit" value="Rate Limit" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" parent="layer_access" vertex="1">
      <mxGeometry x="770" y="60" width="150" height="50" as="geometry"/>
    </mxCell>

    <!-- 服务层 - 容器1: User -->
    <mxCell id="svc_container_1" value="User Microservice" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="240" y="240" width="320" height="340" as="geometry"/>
    </mxCell>
    
    <mxCell id="svc1_api" value="User API" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_1" vertex="1">
      <mxGeometry x="40" y="60" width="240" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="svc1_logic" value="Business Logic" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_1" vertex="1">
      <mxGeometry x="40" y="140" width="240" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="svc1_repo" value="Data Repository" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_1" vertex="1">
      <mxGeometry x="40" y="220" width="240" height="60" as="geometry"/>
    </mxCell>

    <!-- 服务层 - 容器2: Order -->
    <mxCell id="svc_container_2" value="Order Microservice" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="640" y="240" width="320" height="340" as="geometry"/>
    </mxCell>
    
    <mxCell id="svc2_api" value="Order API" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_2" vertex="1">
      <mxGeometry x="40" y="60" width="240" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="svc2_logic" value="Business Logic" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_2" vertex="1">
      <mxGeometry x="40" y="140" width="240" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="svc2_repo" value="Data Repository" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_2" vertex="1">
      <mxGeometry x="40" y="220" width="240" height="60" as="geometry"/>
    </mxCell>

    <!-- 服务层 - 容器3: Payment -->
    <mxCell id="svc_container_3" value="Payment Microservice" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="1040" y="240" width="320" height="340" as="geometry"/>
    </mxCell>
    
    <mxCell id="svc3_api" value="Payment API" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_3" vertex="1">
      <mxGeometry x="40" y="60" width="240" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="svc3_logic" value="Business Logic" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_3" vertex="1">
      <mxGeometry x="40" y="140" width="240" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="svc3_repo" value="Data Repository" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#82b366;fontSize=12;" parent="svc_container_3" vertex="1">
      <mxGeometry x="40" y="220" width="240" height="60" as="geometry"/>
    </mxCell>

    <!-- 数据层 -->
    <mxCell id="layer_data" value="Data &amp; Infrastructure Layer" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;" parent="1" vertex="1">
      <mxGeometry x="230" y="690" width="1120" height="180" as="geometry"/>
    </mxCell>
    
    <mxCell id="db_user" value="User DB" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="120" y="60" width="100" height="90" as="geometry"/>
    </mxCell>
    <mxCell id="db_order" value="Order DB" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="410" y="60" width="100" height="90" as="geometry"/>
    </mxCell>
    <mxCell id="db_payment" value="Payment DB" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="700" y="60" width="100" height="90" as="geometry"/>
    </mxCell>
    <mxCell id="cache_redis" value="Redis" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" parent="layer_data" vertex="1">
      <mxGeometry x="920" y="60" width="100" height="90" as="geometry"/>
    </mxCell>

    <!-- 垂直连接：网关 → 服务 -->
    <mxCell id="link_gw_svc1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#6c8ebf;entryX=0.5;entryY=0;exitX=0.25;exitY=1;" parent="1" source="layer_access" target="svc_container_1" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_svc2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#6c8ebf;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="layer_access" target="svc_container_2" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_svc3" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#6c8ebf;entryX=0.5;entryY=0;exitX=0.75;exitY=1;" parent="1" source="layer_access" target="svc_container_3" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 垂直连接：服务 → 数据库 -->
    <mxCell id="link_svc1_db1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="svc_container_1" target="db_user" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_svc2_db2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="svc_container_2" target="db_order" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_svc3_db3" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="svc_container_3" target="db_payment" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 横向连接：服务间调用 -->
    <mxCell id="link_order_user" value="RPC" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#82b366;dashed=1;curved=1;entryX=1;entryY=0.5;exitX=0;exitY=0.5;" parent="1" source="svc2_logic" target="svc1_logic" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_payment_order" value="Event" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#82b366;dashed=1;curved=1;entryX=1;entryY=0.5;exitX=0;exitY=0.5;" parent="1" source="svc3_logic" target="svc2_logic" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 缓存连接（可选） -->
    <mxCell id="link_svc2_cache" value="Cache" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=1;strokeColor=#b85450;dashed=1;entryX=0.5;entryY=0;exitX=0.75;exitY=1;" parent="1" source="svc_container_2" target="cache_redis" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

  </root>
</mxGraphModel>
```

---

## 扩展说明

### 微服务数量调整

**增加或减少微服务时：**
1. **计算容器宽度**：
   ```
   容器宽 = (1120 - (服务数-1) × 间距) / 服务数
   示例：3服务 = (1120 - 2×40) / 3 = 346.7 ≈ 320
   ```
2. **按顺序计算容器X**：
   ```
   容器X = 240 + 索引 × (容器宽 + 间距)
   ```
3. **添加对应数据库**：每个服务对应一个数据库节点

**示例：增加第4个微服务（Notification）**
```xml
<!-- 服务容器 -->
<mxCell id="svc_container_4" value="Notification Microservice" 
        style="rounded=1;whiteSpace=wrap;html=1;
               fillColor=#d5e8d4;strokeColor=#82b366;strokeWidth=2;
               verticalAlign=top;align=center;spacingTop=10;
               fontSize=14;fontStyle=1;" 
        parent="1" vertex="1">
  <mxGeometry x="1400" y="240" width="320" height="340" as="geometry"/>
</mxCell>

<!-- 数据库 -->
<mxCell id="db_notify" value="Notify DB" 
        style="shape=cylinder3;whiteSpace=wrap;html=1;
               boundedLbl=1;backgroundOutline=1;size=15;
               fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" 
        parent="layer_data" vertex="1">
  <mxGeometry x="990" y="60" width="100" height="90" as="geometry"/>
</mxCell>

<!-- 调整画布宽度为1900 -->
```

### 子组件调整

**容器内子组件使用相对坐标**：
- parent属性指向容器id
- 垂直排列：Y = 60, 140, 220
- 如需增加子组件，按80px间距递增

### 服务间调用调整

**连接子组件而非容器**：
```xml
<!-- 从Order的Business Logic到User的Business Logic -->
source="svc2_logic" target="svc1_logic"
```

