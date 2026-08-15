# 架构图 - 嵌套容器分层示例

**适用场景：** 展示4-5层架构，每层包含嵌套容器和子组件（DDD架构、洋葱架构、模块化分层）

---

## 布局规范

### 整体策略
**核心思路：** 自上而下分层，层内包含多个独立容器，每个容器内有子组件

**布局特征：**
- 顶层（网关）全宽，下层分为多个并列容器
- 容器内子组件使用相对坐标
- 垂直连接表示跨层依赖，容器级别连接
- 基建层全宽，包含所有共享资源

### 坐标计算公式

**画布参数：**
```
画布宽度 = 1600 (固定)
画布高度 = 1000 (适应4层结构)
视口宽度 = 1554
视口高度 = 946
```

**层定位（4层结构）：**
```
网关层Y = 40,  高度 = 140
应用层Y = 230, 高度 = 200
领域层Y = 490, 高度 = 180
基建层Y = 730, 高度 = 160

层间距约 = 50-60px
```

**应用层/领域层容器定位（并列2个）：**
```
容器宽 = 530 (每个)
左容器X = 240
右容器X = 830 (左容器X + 容器宽 + 间距60)
```

**容器内子组件（相对坐标）：**
```
子组件X = 40 + 索引 × 步长
子组件Y = 60 (第一行) 或 130 (第二行)
子组件宽 = 150
子组件高 = 50-60
```

**全宽层（网关/基建）：**
```
容器X = 240
容器宽 = 1120
子组件水平均分，公式同 layered_simple
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1600 | 固定宽度 | 1400-1800 |
| 画布高度 | 1000 | 4层结构 | 900-1200 |
| 网关层高 | 140 | 顶层 | 120-180 |
| 应用容器高 | 200 | 嵌套容器 | 180-240 |
| 领域容器高 | 180 | 嵌套容器 | 160-200 |
| 基建层高 | 160 | 底层 | 140-180 |
| 容器间距 | 60 | 水平间距 | 40-80 |

---

## 关键共识

### 重要提示
⚠️ **本示例仅供结构参考**
- 展示正确的**多级嵌套**和**容器并列**布局
- **严禁复制**示例的节点内容、数量、固定坐标
- 必须根据实际容器数和子组件数**动态计算**
- 参考**嵌套策略和parent属性用法**

### 样式规范

**顶层容器（网关/基建）：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor={配色};strokeColor={边框};strokeWidth=2;
      verticalAlign=top;align=center;spacingTop=10;
      fontSize=14;fontStyle=1;"
```

**嵌套容器（应用/领域）：**
```xml
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor={配色};strokeColor={边框};strokeWidth=2;
      verticalAlign=top;align=center;spacingTop=10;
      fontSize=14;fontStyle=1;"
```

**子组件（在容器内，使用parent）：**
```xml
<mxCell id="xxx" value="组件" style="..." vertex="1" parent="容器id">
  <mxGeometry x="相对X" y="相对Y" width="150" height="60" as="geometry"/>
</mxCell>
```

### 配色建议
- **网关层**：`fillColor=#dae8fc strokeColor=#6c8ebf` - 蓝色
- **应用层**：`fillColor=#fff2cc strokeColor=#d6b656` - 黄色
- **领域层**：`fillColor=#e1d5e7 strokeColor=#9673a6` - 紫色
- **基建层**：`fillColor=#f8cecc strokeColor=#b85450` - 红色

---

## 案例代码

### 完整 XML（4层嵌套结构示例）

```xml
<mxGraphModel dx="1554" dy="946" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="1000" background="#ffffff" math="0" shadow="0">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>

    <!-- 层标签 -->
    <mxCell id="lbl_gateway" value="网关层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" vertex="1" parent="1">
      <mxGeometry x="40" y="80" width="100" height="40" as="geometry"/>
    </mxCell>
    <mxCell id="lbl_app" value="应用层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" vertex="1" parent="1">
      <mxGeometry x="40" y="290" width="100" height="40" as="geometry"/>
    </mxCell>
    <mxCell id="lbl_domain" value="领域层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" vertex="1" parent="1">
      <mxGeometry x="40" y="570" width="100" height="40" as="geometry"/>
    </mxCell>
    <mxCell id="lbl_infra" value="基建层" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=16;fontStyle=1;fontColor=#333333;" vertex="1" parent="1">
      <mxGeometry x="40" y="800" width="100" height="40" as="geometry"/>
    </mxCell>

    <!-- 网关层 -->
    <mxCell id="layer_gateway" value="API Gateway" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="240" y="40" width="1120" height="140" as="geometry"/>
    </mxCell>
    <mxCell id="gateway_auth" value="Authentication" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" vertex="1" parent="layer_gateway">
      <mxGeometry x="100" y="60" width="200" height="50" as="geometry"/>
    </mxCell>
    <mxCell id="gateway_route" value="Routing" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" vertex="1" parent="layer_gateway">
      <mxGeometry x="460" y="60" width="200" height="50" as="geometry"/>
    </mxCell>
    <mxCell id="gateway_limit" value="Rate Limiting" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#6c8ebf;fontSize=12;" vertex="1" parent="layer_gateway">
      <mxGeometry x="820" y="60" width="200" height="50" as="geometry"/>
    </mxCell>

    <!-- 应用层 - 左容器 -->
    <mxCell id="app_container_1" value="Order Application" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="240" y="230" width="530" height="200" as="geometry"/>
    </mxCell>
    <mxCell id="app1_ctrl" value="Order Controller" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="app_container_1">
      <mxGeometry x="40" y="60" width="150" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="app1_svc" value="Order Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="app_container_1">
      <mxGeometry x="220" y="60" width="150" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="app1_repo" value="Order Repository" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="app_container_1">
      <mxGeometry x="340" y="130" width="150" height="50" as="geometry"/>
    </mxCell>

    <!-- 应用层 - 右容器 -->
    <mxCell id="app_container_2" value="User Application" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="830" y="230" width="530" height="200" as="geometry"/>
    </mxCell>
    <mxCell id="app2_ctrl" value="User Controller" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="app_container_2">
      <mxGeometry x="40" y="60" width="150" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="app2_svc" value="User Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="app_container_2">
      <mxGeometry x="220" y="60" width="150" height="60" as="geometry"/>
    </mxCell>
    <mxCell id="app2_repo" value="User Repository" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#d6b656;fontSize=12;" vertex="1" parent="app_container_2">
      <mxGeometry x="340" y="130" width="150" height="50" as="geometry"/>
    </mxCell>

    <!-- 领域层 - 左容器 -->
    <mxCell id="domain_container_1" value="Order Domain" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="240" y="490" width="530" height="180" as="geometry"/>
    </mxCell>
    <mxCell id="domain1_model" value="Order Model" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;fontSize=12;" vertex="1" parent="domain_container_1">
      <mxGeometry x="60" y="60" width="180" height="80" as="geometry"/>
    </mxCell>
    <mxCell id="domain1_logic" value="Business Logic" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;fontSize=12;" vertex="1" parent="domain_container_1">
      <mxGeometry x="290" y="60" width="180" height="80" as="geometry"/>
    </mxCell>

    <!-- 领域层 - 右容器 -->
    <mxCell id="domain_container_2" value="User Domain" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="830" y="490" width="530" height="180" as="geometry"/>
    </mxCell>
    <mxCell id="domain2_model" value="User Model" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;fontSize=12;" vertex="1" parent="domain_container_2">
      <mxGeometry x="60" y="60" width="180" height="80" as="geometry"/>
    </mxCell>
    <mxCell id="domain2_logic" value="Auth Logic" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9673a6;fontSize=12;" vertex="1" parent="domain_container_2">
      <mxGeometry x="290" y="60" width="180" height="80" as="geometry"/>
    </mxCell>

    <!-- 基建层 -->
    <mxCell id="layer_infra" value="Infrastructure Layer" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;strokeWidth=2;verticalAlign=top;align=center;spacingTop=10;fontSize=14;fontStyle=1;dashed=1;dashPattern=8 4;" vertex="1" parent="1">
      <mxGeometry x="240" y="730" width="1120" height="160" as="geometry"/>
    </mxCell>
    <mxCell id="infra_db" value="Database" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" vertex="1" parent="layer_infra">
      <mxGeometry x="200" y="50" width="100" height="90" as="geometry"/>
    </mxCell>
    <mxCell id="infra_cache" value="Cache" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" vertex="1" parent="layer_infra">
      <mxGeometry x="510" y="50" width="100" height="90" as="geometry"/>
    </mxCell>
    <mxCell id="infra_mq" value="Message Queue" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#ffffff;strokeColor=#b85450;fontSize=12;" vertex="1" parent="layer_infra">
      <mxGeometry x="820" y="50" width="100" height="90" as="geometry"/>
    </mxCell>

    <!-- 连接线 -->
    <mxCell id="link_gw_app1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;" edge="1" parent="1" source="layer_gateway" target="app_container_1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_gw_app2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;" edge="1" parent="1" source="layer_gateway" target="app_container_2">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_app1_domain1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;" edge="1" parent="1" source="app_container_1" target="domain_container_1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_app2_domain2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;" edge="1" parent="1" source="app_container_2" target="domain_container_2">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_domain1_db" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;" edge="1" parent="1" source="domain_container_1" target="infra_db">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>
    <mxCell id="link_domain2_cache" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;" edge="1" parent="1" source="domain_container_2" target="infra_cache">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

  </root>
</mxGraphModel>
```

---

## 扩展说明

### 容器数量调整
**当并列容器数量变化时：**
1. 计算容器宽度：`容器宽 = (1120 - (容器数-1)×间距60) / 容器数`
2. 按顺序计算容器X：`容器X = 240 + 索引 × (容器宽 + 60)`

### 子组件调整
**容器内子组件使用相对坐标，parent指向容器id**
1. 横向分布：`子组件X = 边距 + 索引 × 步长`
2. 纵向分行：`子组件Y = 60 (第1行) / 130 (第2行)`

