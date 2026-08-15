# 甘特图示例

适用：项目管理、任务规划

**重要提示：**
- 本示例仅供结构参考，展示正确的XML语法和布局逻辑
- **严禁直接复制示例内容**：任务数量、时间跨度、具体坐标必须根据用户需求动态生成
- 必须参考示例的结构关系（8大组件：标题、时间轴、任务列、网格线、任务条、里程碑、今日线、图例），而非照搬具体数值
- 本示例是7周10任务演示，实际生成时时间跨度和任务完全不同

---

## 完整可用代码（产品发布项目示例）

**使用方法：** 复制下方完整代码，在 diagrams.net 选择 File → Import from → Text，粘贴即可打开

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="2025-01-01T00:00:00.000Z" agent="Draw.io" version="21.0.0" type="device">
  <diagram name="产品发布甘特图" id="gantt-chart-001">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="800" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <!-- ==================== 标题区域 ==================== -->
        <mxCell id="title-001" value="产品发布项目甘特图" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=20;fontStyle=1;fontColor=#1a1a2e;" vertex="1" parent="1">
          <mxGeometry x="400" y="20" width="400" height="40" as="geometry" />
        </mxCell>

        <!-- ==================== 时间轴表头 ==================== -->
        <mxCell id="header-bg" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#e9ecef;" vertex="1" parent="1">
          <mxGeometry x="200" y="80" width="840" height="40" as="geometry" />
        </mxCell>

        <mxCell id="week-1" value="第1周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="200" y="80" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="week-2" value="第2周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="320" y="80" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="week-3" value="第3周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="440" y="80" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="week-4" value="第4周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="560" y="80" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="week-5" value="第5周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="680" y="80" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="week-6" value="第6周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="800" y="80" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="week-7" value="第7周" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontSize=11;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="920" y="80" width="120" height="40" as="geometry" />
        </mxCell>

        <!-- ==================== 任务名称列 ==================== -->
        <mxCell id="task-col-bg" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#f1f3f4;strokeColor=#e9ecef;" vertex="1" parent="1">
          <mxGeometry x="20" y="80" width="180" height="440" as="geometry" />
        </mxCell>

        <mxCell id="task-header" value="任务名称" style="text;html=1;strokeColor=none;fillColor=#e3e7eb;align=center;verticalAlign=middle;fontSize=12;fontStyle=1;fontColor=#343a40;rounded=0;" vertex="1" parent="1">
          <mxGeometry x="20" y="80" width="180" height="40" as="geometry" />
        </mxCell>

        <!-- 阶段1：需求分析 -->
        <mxCell id="phase-1" value="📋 需求分析阶段" style="text;html=1;strokeColor=none;fillColor=#e8f4fd;align=left;verticalAlign=middle;fontSize=11;fontStyle=1;fontColor=#0d6efd;spacingLeft=10;" vertex="1" parent="1">
          <mxGeometry x="20" y="120" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-1-1" value="  用户调研" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="150" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-1-2" value="  需求文档编写" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="180" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-1-3" value="  需求评审" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="210" width="180" height="30" as="geometry" />
        </mxCell>

        <!-- 阶段2：设计开发 -->
        <mxCell id="phase-2" value="💻 设计开发阶段" style="text;html=1;strokeColor=none;fillColor=#fff3cd;align=left;verticalAlign=middle;fontSize=11;fontStyle=1;fontColor=#856404;spacingLeft=10;" vertex="1" parent="1">
          <mxGeometry x="20" y="250" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-2-1" value="  UI/UX设计" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="280" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-2-2" value="  前端开发" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="310" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-2-3" value="  后端开发" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="340" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-2-4" value="  API集成" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="370" width="180" height="30" as="geometry" />
        </mxCell>

        <!-- 阶段3：测试发布 -->
        <mxCell id="phase-3" value="🚀 测试发布阶段" style="text;html=1;strokeColor=none;fillColor=#d4edda;align=left;verticalAlign=middle;fontSize=11;fontStyle=1;fontColor=#155724;spacingLeft=10;" vertex="1" parent="1">
          <mxGeometry x="20" y="410" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-3-1" value="  单元测试" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="440" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-3-2" value="  集成测试" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="470" width="180" height="30" as="geometry" />
        </mxCell>
        <mxCell id="task-3-3" value="  正式发布" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontColor=#495057;spacingLeft=15;" vertex="1" parent="1">
          <mxGeometry x="20" y="500" width="180" height="30" as="geometry" />
        </mxCell>

        <!-- ==================== 网格线（垂直） ==================== -->
        <mxCell id="grid-v1" value="" style="endArrow=none;html=1;strokeColor=#dee2e6;strokeWidth=1;dashed=1;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="320" y="520" as="sourcePoint" />
            <mxPoint x="320" y="120" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="grid-v2" value="" style="endArrow=none;html=1;strokeColor=#dee2e6;strokeWidth=1;dashed=1;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="440" y="520" as="sourcePoint" />
            <mxPoint x="440" y="120" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="grid-v3" value="" style="endArrow=none;html=1;strokeColor=#dee2e6;strokeWidth=1;dashed=1;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="560" y="520" as="sourcePoint" />
            <mxPoint x="560" y="120" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="grid-v4" value="" style="endArrow=none;html=1;strokeColor=#dee2e6;strokeWidth=1;dashed=1;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="680" y="520" as="sourcePoint" />
            <mxPoint x="680" y="120" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="grid-v5" value="" style="endArrow=none;html=1;strokeColor=#dee2e6;strokeWidth=1;dashed=1;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="800" y="520" as="sourcePoint" />
            <mxPoint x="800" y="120" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="grid-v6" value="" style="endArrow=none;html=1;strokeColor=#dee2e6;strokeWidth=1;dashed=1;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="920" y="520" as="sourcePoint" />
            <mxPoint x="920" y="120" as="targetPoint" />
          </mxGeometry>
        </mxCell>

        <!-- ==================== 任务条（甘特条） ==================== -->
        <!-- 需求分析阶段任务条 -->
        <mxCell id="bar-1-1" value="用户调研" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#4285f4;strokeColor=#2b5797;fontColor=#ffffff;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="200" y="152" width="180" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-1-2" value="需求文档" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#4285f4;strokeColor=#2b5797;fontColor=#ffffff;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="320" y="182" width="150" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-1-3" value="评审" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#4285f4;strokeColor=#2b5797;fontColor=#ffffff;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="440" y="212" width="60" height="24" as="geometry" />
        </mxCell>

        <!-- 设计开发阶段任务条 -->
        <mxCell id="bar-2-1" value="UI/UX设计" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fbbc04;strokeColor=#c49102;fontColor=#333333;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="380" y="282" width="180" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-2-2" value="前端开发" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fbbc04;strokeColor=#c49102;fontColor=#333333;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="500" y="312" width="240" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-2-3" value="后端开发" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fbbc04;strokeColor=#c49102;fontColor=#333333;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="500" y="342" width="240" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-2-4" value="API集成" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fbbc04;strokeColor=#c49102;fontColor=#333333;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="680" y="372" width="120" height="24" as="geometry" />
        </mxCell>

        <!-- 测试发布阶段任务条 -->
        <mxCell id="bar-3-1" value="单元测试" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#34a853;strokeColor=#1e7e34;fontColor=#ffffff;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="740" y="442" width="120" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-3-2" value="集成测试" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#34a853;strokeColor=#1e7e34;fontColor=#ffffff;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="800" y="472" width="120" height="24" as="geometry" />
        </mxCell>
        <mxCell id="bar-3-3" value="发布" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#9c27b0;strokeColor=#7b1fa2;fontColor=#ffffff;fontSize=9;arcSize=20;" vertex="1" parent="1">
          <mxGeometry x="920" y="502" width="100" height="24" as="geometry" />
        </mxCell>

        <!-- ==================== 里程碑 ==================== -->
        <mxCell id="milestone-1-icon" value="" style="rhombus;whiteSpace=wrap;html=1;fillColor=#ea4335;strokeColor=none;" vertex="1" parent="1">
          <mxGeometry x="502" y="240" width="14" height="14" as="geometry" />
        </mxCell>
        <mxCell id="milestone-1-label" value="需求冻结" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#ea4335;fontStyle=1;spacingLeft=2;" vertex="1" parent="1">
          <mxGeometry x="518" y="236" width="50" height="20" as="geometry" />
        </mxCell>

        <mxCell id="milestone-2-icon" value="" style="rhombus;whiteSpace=wrap;html=1;fillColor=#ea4335;strokeColor=none;" vertex="1" parent="1">
          <mxGeometry x="802" y="400" width="14" height="14" as="geometry" />
        </mxCell>
        <mxCell id="milestone-2-label" value="开发完成" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#ea4335;fontStyle=1;spacingLeft=2;" vertex="1" parent="1">
          <mxGeometry x="818" y="396" width="50" height="20" as="geometry" />
        </mxCell>

        <mxCell id="milestone-3-icon" value="" style="rhombus;whiteSpace=wrap;html=1;fillColor=#9c27b0;strokeColor=none;" vertex="1" parent="1">
          <mxGeometry x="1022" y="500" width="14" height="14" as="geometry" />
        </mxCell>
        <mxCell id="milestone-3-label" value="正式上线" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#9c27b0;fontStyle=1;spacingLeft=2;" vertex="1" parent="1">
          <mxGeometry x="1005" y="478" width="50" height="20" as="geometry" />
        </mxCell>

        <!-- ==================== 今日线 ==================== -->
        <mxCell id="today-line" value="" style="endArrow=none;html=1;strokeColor=#ea4335;strokeWidth=2;dashed=0;" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="620" y="530" as="sourcePoint" />
            <mxPoint x="620" y="80" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="today-label" value="今日" style="text;html=1;strokeColor=none;fillColor=#ea4335;align=center;verticalAlign=middle;fontSize=10;fontColor=#ffffff;rounded=1;spacingLeft=5;spacingRight=5;" vertex="1" parent="1">
          <mxGeometry x="600" y="55" width="40" height="20" as="geometry" />
        </mxCell>

        <!-- ==================== 图例 ==================== -->
        <mxCell id="legend-bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#dee2e6;" vertex="1" parent="1">
          <mxGeometry x="20" y="550" width="380" height="50" as="geometry" />
        </mxCell>
        <mxCell id="legend-title" value="图例：" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=10;fontStyle=1;fontColor=#343a40;spacingLeft=5;" vertex="1" parent="1">
          <mxGeometry x="30" y="560" width="40" height="30" as="geometry" />
        </mxCell>

        <mxCell id="legend-1-box" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#4285f4;strokeColor=#2b5797;" vertex="1" parent="1">
          <mxGeometry x="75" y="567" width="20" height="16" as="geometry" />
        </mxCell>
        <mxCell id="legend-1-text" value="需求分析" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="100" y="560" width="55" height="30" as="geometry" />
        </mxCell>

        <mxCell id="legend-2-box" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fbbc04;strokeColor=#c49102;" vertex="1" parent="1">
          <mxGeometry x="160" y="567" width="20" height="16" as="geometry" />
        </mxCell>
        <mxCell id="legend-2-text" value="设计开发" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="185" y="560" width="55" height="30" as="geometry" />
        </mxCell>

        <mxCell id="legend-3-box" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#34a853;strokeColor=#1e7e34;" vertex="1" parent="1">
          <mxGeometry x="245" y="567" width="20" height="16" as="geometry" />
        </mxCell>
        <mxCell id="legend-3-text" value="测试发布" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="270" y="560" width="55" height="30" as="geometry" />
        </mxCell>

        <mxCell id="legend-4-box" value="" style="rhombus;whiteSpace=wrap;html=1;fillColor=#ea4335;strokeColor=none;" vertex="1" parent="1">
          <mxGeometry x="330" y="568" width="14" height="14" as="geometry" />
        </mxCell>
        <mxCell id="legend-4-text" value="里程碑" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=9;fontColor=#495057;" vertex="1" parent="1">
          <mxGeometry x="350" y="560" width="45" height="30" as="geometry" />
        </mxCell>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## 关键模式

**8大核心组件：** 标题 → 时间轴表头 → 任务名称列 → 网格线 → 任务条 → 里程碑 → 今日线 → 图例

**任务条X坐标计算（示例）：**
- 用户调研（第1-2.5周）：x = 200 + (1-1)×120 = 200，宽度 = 1.5×120 = 180
- 需求文档（第2-3.25周）：x = 200 + (2-1)×120 = 320，宽度 = 1.25×120 = 150
- UI/UX设计（第3.5-5周）：x = 200 + 1.5×120 = 380，宽度 = 1.5×120 = 180

**任务条Y坐标计算：**
- 任务行基准Y = 120（表头底部）
- 行索引从0开始：阶段1=0行, 子任务1=1行, 子任务2=2行...
- 任务条Y = 120 + 行索引×30 + 3（垂直居中偏移）

**网格线位置：**
- 每条网格线与时间刻度的右边界对齐
- 第1条：x=320（第1周结束）
- 第2条：x=440（第2周结束）
- 以此类推

**布局要点：**
- 任务名称列固定宽度180px
- 时间轴起始X固定200px
- 每周宽度120px（可调整为60/80/150等）
- 任务行高30px，任务条高24px
- 所有文本必须包含 `whiteSpace=wrap;html=1`
- 不同阶段使用配色方案区分
