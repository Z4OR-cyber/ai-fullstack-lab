# 架构图 - 流程导向网络示例

**适用场景：** 展示从左到右的处理流程（数据流转、请求链路、ETL管道、工作流）

---

## 布局规范

### 整体策略
**核心思路：** 从左到右的主流程线，上下分支表示副作用

**布局特征：**
- 主流程：横向排列（用户 → LB → 网关 → 认证 → 业务 → 数据库）
- 分支流程：向上分支（缓存）、向下分支（日志、监控）
- 返回流程：虚线箭头从右到左表示响应
- 编号标签：1-6标记流程步骤
- 节点颜色：按阶段变化（蓝→黄→绿→红）

### 坐标计算公式

**画布参数：**
```
画布宽度 = 1600
画布高度 = 800
视口宽度 = 1636
视口高度 = 996
```

**主流程节点定位（6个节点）：**
```
起始X = 80 (User Actor)
步长 = 280
节点X = 240 + (索引 - 1) × 280  // 索引从1开始（LB、网关、认证等）
节点Y = 360 (固定，水平对齐)
节点宽 = 180
节点高 = 80

具体坐标：
  User:     X=80,   Y=340, W=60,  H=120 (Actor)
  LB:       X=240,  Y=360, W=180, H=80
  Gateway:  X=520,  Y=360, W=180, H=80
  Auth:     X=800,  Y=360, W=180, H=80
  Business: X=1080, Y=360, W=180, H=80
  Database: X=1360, Y=350, W=140, H=100 (Cylinder)
```

**分支节点定位：**
```
分支向上：
  Y = 150 (主流程Y - 210)
  X = 对应主流程节点X + 调整

分支向下：
  Y = 560 (主流程Y + 200)
  X = 对应主流程节点X + 调整

具体坐标：
  Cache:    X=1100, Y=150, W=140, H=80 (从Business向上)
  Logging:  X=540,  Y=560, W=140, H=80 (从Gateway向下)
  Monitor:  X=820,  Y=560, W=140, H=80 (从Auth向下)
```

**连接线规则：**
```
主流程（实线，粗线）：
  strokeWidth = 3
  从左到右: exitX=1, exitY=0.5 → entryX=0, entryY=0.5

分支流程（虚线，细线）：
  strokeWidth = 2
  dashed = 1
  向上: exitY=0 → entryY=1
  向下: exitY=1 → entryY=0

返回流程（虚线，箭头反向）：
  strokeWidth = 2
  dashed = 1
  strokeColor = #999999
  startArrow = block, endArrow = none
  通过waypoints从右下角绕回左侧
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | 1600 | 流程较长 | 1400-2000 |
| 画布高度 | 800 | 留分支空间 | 700-1000 |
| 主流程Y | 360 | 中间位置 | 300-400 |
| 主流程步长 | 280 | 节点间距 | 240-320 |
| 分支上偏移 | -210 | 向上距离 | -180~-240 |
| 分支下偏移 | +200 | 向下距离 | +180~+240 |

---

## 关键共识

### 重要提示
⚠️ **本示例仅供结构参考**
- 展示**横向流程**和**分支处理**的技巧
- **严禁复制**示例的节点内容、数量、固定坐标
- 主流程实线加粗，分支虚线细化
- 返回流程使用startArrow表示反向

### 样式规范

**主流程节点（按阶段配色）：**
```xml
<!-- 入口阶段（蓝色） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#dae8fc;strokeColor=#6c8ebf;
      fontSize=14;fontStyle=1;"

<!-- 认证阶段（黄色） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#fff2cc;strokeColor=#d6b656;
      fontSize=14;fontStyle=1;"

<!-- 业务阶段（绿色） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#d5e8d4;strokeColor=#82b366;
      fontSize=14;fontStyle=1;"

<!-- 数据阶段（红色，圆柱） -->
style="shape=cylinder3;whiteSpace=wrap;html=1;
      boundedLbl=1;backgroundOutline=1;size=15;
      fillColor=#f8cecc;strokeColor=#b85450;
      fontSize=14;fontStyle=1;"
```

**分支节点（按类型配色）：**
```xml
<!-- 缓存（紫色） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#e1d5e7;strokeColor=#9673a6;
      fontSize=14;dashed=1;"

<!-- 日志/监控（灰色） -->
style="rounded=1;whiteSpace=wrap;html=1;
      fillColor=#f5f5f5;strokeColor=#666666;
      fontSize=14;dashed=1;"
```

**User Actor：**
```xml
style="shape=umlActor;
      verticalLabelPosition=bottom;verticalAlign=top;
      html=1;outlineConnect=0;
      fillColor=#dae8fc;strokeColor=#6c8ebf;
      fontSize=14;"
```

**主流程连接线（实线，粗线，带标签）：**
```xml
<mxCell id="flow1" value="1. Request" 
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;
               orthogonalLoop=1;jettySize=auto;html=1;
               strokeWidth=3;strokeColor=#6c8ebf;
               entryX=0;entryY=0.5;exitX=1;exitY=0.5;" 
        parent="1" source="user" target="step1_lb" edge="1">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

**分支连接线（虚线，细线）：**
```xml
<mxCell id="branch_to_cache" value="Cache Read" 
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;
               orthogonalLoop=1;jettySize=auto;html=1;
               strokeWidth=2;strokeColor=#9673a6;dashed=1;
               entryX=0.5;entryY=1;exitX=0.5;exitY=0;" 
        parent="1" source="step4_biz" target="branch_cache" edge="1">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

**返回流程（虚线，反向箭头，waypoints）：**
```xml
<mxCell id="flow_return" value="6. Response" 
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;
               orthogonalLoop=1;jettySize=auto;html=1;
               strokeWidth=2;strokeColor=#999999;dashed=1;
               startArrow=block;endArrow=none;" 
        parent="1" source="step5_db" target="user" edge="1">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="1430" y="728"/>
      <mxPoint x="110" y="728"/>
    </Array>
  </mxGeometry>
</mxCell>
```

### 配色建议
**流程导向的典型配色：**
- **入口节点**：蓝色 `#dae8fc/#6c8ebf` （LB、Gateway）
- **认证节点**：黄色 `#fff2cc/#d6b656` （Auth）
- **业务节点**：绿色 `#d5e8d4/#82b366` （Business）
- **数据节点**：红色 `#f8cecc/#b85450` （Database）
- **分支缓存**：紫色 `#e1d5e7/#9673a6`
- **分支日志**：灰色 `#f5f5f5/#666666`

---

## 案例代码

### 完整 XML（6步主流程 + 3个分支示例）

```xml
<mxGraphModel dx="1636" dy="996" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="800" background="#ffffff" math="0" shadow="0">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    
    <!-- User Actor -->
    <mxCell id="user" value="User" style="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=14;" parent="1" vertex="1">
      <mxGeometry x="80" y="340" width="60" height="120" as="geometry"/>
    </mxCell>

    <!-- 主流程节点 -->
    <mxCell id="step1_lb" value="Load Balancer" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="240" y="360" width="180" height="80" as="geometry"/>
    </mxCell>

    <mxCell id="step2_gw" value="API Gateway" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="520" y="360" width="180" height="80" as="geometry"/>
    </mxCell>

    <mxCell id="step3_auth" value="Auth Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="800" y="360" width="180" height="80" as="geometry"/>
    </mxCell>

    <mxCell id="step4_biz" value="Business Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="1080" y="360" width="180" height="80" as="geometry"/>
    </mxCell>

    <mxCell id="step5_db" value="Database" style="shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#f8cecc;strokeColor=#b85450;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="1360" y="350" width="140" height="100" as="geometry"/>
    </mxCell>

    <!-- 分支节点 -->
    <mxCell id="branch_cache" value="Cache Layer" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;fontSize=14;dashed=1;" parent="1" vertex="1">
      <mxGeometry x="1100" y="150" width="140" height="80" as="geometry"/>
    </mxCell>

    <mxCell id="branch_log" value="Logging Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;dashed=1;" parent="1" vertex="1">
      <mxGeometry x="540" y="560" width="140" height="80" as="geometry"/>
    </mxCell>

    <mxCell id="branch_monitor" value="Monitoring" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;fontSize=14;dashed=1;" parent="1" vertex="1">
      <mxGeometry x="820" y="560" width="140" height="80" as="geometry"/>
    </mxCell>

    <!-- 主流程连接线 -->
    <mxCell id="flow1" value="1. Request" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;strokeColor=#6c8ebf;entryX=0;entryY=0.5;exitX=1;exitY=0.5;" parent="1" source="user" target="step1_lb" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <mxCell id="flow2" value="2. Route" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;strokeColor=#6c8ebf;entryX=0;entryY=0.5;exitX=1;exitY=0.5;" parent="1" source="step1_lb" target="step2_gw" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <mxCell id="flow3" value="3. Authenticate" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;strokeColor=#d6b656;entryX=0;entryY=0.5;exitX=1;exitY=0.5;" parent="1" source="step2_gw" target="step3_auth" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <mxCell id="flow4" value="4. Process" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;strokeColor=#82b366;entryX=0;entryY=0.5;exitX=1;exitY=0.5;" parent="1" source="step3_auth" target="step4_biz" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <mxCell id="flow5" value="5. Query" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=3;strokeColor=#b85450;entryX=0;entryY=0.5;exitX=1;exitY=0.5;" parent="1" source="step4_biz" target="step5_db" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 返回流程 -->
    <mxCell id="flow_return" value="6. Response" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#999999;dashed=1;startArrow=block;endArrow=none;" parent="1" source="step5_db" target="user" edge="1">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="1430" y="728"/>
          <mxPoint x="110" y="728"/>
        </Array>
      </mxGeometry>
    </mxCell>

    <!-- 分支连接线 -->
    <mxCell id="branch_to_cache" value="Cache Read" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#9673a6;dashed=1;entryX=0.5;entryY=1;exitX=0.5;exitY=0;" parent="1" source="step4_biz" target="branch_cache" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <mxCell id="branch_to_log" value="Log" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="step2_gw" target="branch_log" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <mxCell id="branch_to_monitor" value="Metrics" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;entryX=0.5;entryY=0;exitX=0.5;exitY=1;" parent="1" source="step3_auth" target="branch_monitor" edge="1">
      <mxGeometry relative="1" as="geometry"/>
    </mxCell>

    <!-- 标注 -->
    <mxCell id="note_main" value="Main Flow" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=14;fontStyle=1;fontColor=#333333;" parent="1" vertex="1">
      <mxGeometry x="240" y="280" width="100" height="30" as="geometry"/>
    </mxCell>

    <mxCell id="note_branch" value="Side Effects" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=14;fontStyle=1;fontColor=#666666;" parent="1" vertex="1">
      <mxGeometry x="1100" y="100" width="120" height="30" as="geometry"/>
    </mxCell>

  </root>
</mxGraphModel>
```

---

## 扩展说明

### 流程节点调整

**增加或减少主流程节点时：**
1. **重新计算步长**：
   ```
   步长 = (画布宽 - 起始边距 - 结束边距) / (节点数 - 1)
   示例：(1600 - 240 - 100) / 5 = 252
   ```
2. **按公式更新节点X坐标**：
   ```
   节点X = 起始X + 索引 × 步长
   ```
3. **调整画布宽度**：如果节点超过6个，建议增加画布宽度到1800-2000

**示例：增加第7个节点（Message Queue）**
```xml
<mxCell id="step6_mq" value="Message Queue" 
        style="shape=cylinder3;whiteSpace=wrap;html=1;
               boundedLbl=1;backgroundOutline=1;size=15;
               fillColor=#f8cecc;strokeColor=#b85450;
               fontSize=14;fontStyle=1;" 
        parent="1" vertex="1">
  <mxGeometry x="1620" y="350" width="140" height="100" as="geometry"/>
</mxCell>

<mxCell id="flow6" value="6. Publish" 
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;
               orthogonalLoop=1;jettySize=auto;html=1;
               strokeWidth=3;strokeColor=#b85450;
               entryX=0;entryY=0.5;exitX=1;exitY=0.5;" 
        parent="1" source="step5_db" target="step6_mq" edge="1">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

### 分支节点调整

**增加新分支时：**
1. **确定分支源节点**：从哪个主流程节点分出
2. **确定分支方向**：向上（缓存类）或向下（日志类）
3. **计算Y坐标**：
   ```
   向上: 分支Y = 主流程Y - 210
   向下: 分支Y = 主流程Y + 200
   ```
4. **调整X坐标**：通常与源节点X对齐或稍微偏移

### 返回流程调整

**修改返回路径waypoints：**
```xml
<Array as="points">
  <mxPoint x="最右侧X" y="底部Y"/>
  <mxPoint x="最左侧X" y="底部Y"/>
</Array>
```

