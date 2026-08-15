# 组织架构图 - 标准层级结构示例

适用：企业组织结构、部门层级、团队汇报关系等树形层级结构

**重要提示：**
- 本示例仅供结构参考，展示正确的XML语法和布局逻辑
- **严禁直接复制示例内容**：节点数量、文本内容、具体坐标必须根据用户需求动态生成
- 必须参考示例的结构关系（树形层级、连接方式），而非照搬具体数值
- **关键特征**：所有连接线统一从父节点底部中心点（exitX=0.5）出发，使用正交直线(curved=0)
- 本示例是科技公司架构，实际生成时主题和内容完全不同

---

## 完整可用代码（4层架构演示）

**使用方法：** 复制下方完整代码，在 diagrams.net 选择 File → Import from → Text，粘贴即可打开

```xml
<mxGraphModel dx="1177" dy="1018" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1400" pageHeight="900" background="#FFFFFF" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="ceo" value="CEO&lt;br&gt;首席执行官&lt;br&gt;张明" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1976D2;strokeColor=#1565C0;fontColor=#000000;fontSize=16;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="600" y="60" width="200" height="80" as="geometry" />
    </mxCell>
    <mxCell id="cto" value="CTO&lt;br&gt;首席技术官&lt;br&gt;李华" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#1976D2;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="240" y="220" width="180" height="70" as="geometry" />
    </mxCell>
    <mxCell id="cpo" value="CPO&lt;br&gt;首席产品官&lt;br&gt;王芳" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#1976D2;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="540" y="220" width="180" height="70" as="geometry" />
    </mxCell>
    <mxCell id="cfo" value="CFO&lt;br&gt;首席财务官&lt;br&gt;赵强" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#1976D2;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="800" y="220" width="180" height="70" as="geometry" />
    </mxCell>
    <mxCell id="coo" value="COO&lt;br&gt;首席运营官&lt;br&gt;刘丽" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#1976D2;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="1080" y="220" width="180" height="70" as="geometry" />
    </mxCell>
    <mxCell id="rd_dept" value="研发部&lt;br&gt;R&amp;D Department&lt;br&gt;总监: 陈伟" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="170" y="380" width="160" height="70" as="geometry" />
    </mxCell>
    <mxCell id="qa_dept" value="质量保障部&lt;br&gt;QA Department&lt;br&gt;总监: 孙敏" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="380" y="380" width="160" height="70" as="geometry" />
    </mxCell>
    <mxCell id="product_dept" value="产品部&lt;br&gt;Product Department&lt;br&gt;总监: 周婷" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="550" y="380" width="160" height="70" as="geometry" />
    </mxCell>
    <mxCell id="finance_dept" value="财务部&lt;br&gt;Finance Department&lt;br&gt;总监: 吴杰" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="810" y="380" width="160" height="70" as="geometry" />
    </mxCell>
    <mxCell id="marketing_dept" value="市场部&lt;br&gt;Marketing&lt;br&gt;总监: 郑磊" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="1010" y="380" width="160" height="70" as="geometry" />
    </mxCell>
    <mxCell id="hr_dept" value="人力资源部&lt;br&gt;HR Department&lt;br&gt;总监: 钱颖" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="1220" y="380" width="160" height="70" as="geometry" />
    </mxCell>
    <mxCell id="frontend_team" value="前端团队&lt;br&gt;Frontend&lt;br&gt;8人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="130" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="backend_team" value="后端团队&lt;br&gt;Backend&lt;br&gt;12人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="270" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="test_team" value="测试团队&lt;br&gt;Test Team&lt;br&gt;6人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="400" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="design_team" value="设计团队&lt;br&gt;Design Team&lt;br&gt;5人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="570" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="digital_team" value="数字营销&lt;br&gt;Digital&lt;br&gt;7人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="970" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="brand_team" value="品牌团队&lt;br&gt;Brand&lt;br&gt;4人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="1110" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="recruit_team" value="招聘团队&lt;br&gt;Recruitment&lt;br&gt;3人" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="1240" y="540" width="120" height="60" as="geometry" />
    </mxCell>
    <mxCell id="link_ceo_cto" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=2;strokeColor=#1976D2;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="ceo" target="cto" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_ceo_cpo" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=2;strokeColor=#1976D2;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="ceo" target="cpo" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_ceo_cfo" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=2;strokeColor=#1976D2;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="ceo" target="cfo" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_ceo_coo" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=2;strokeColor=#1976D2;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="ceo" target="coo" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_cto_rd" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="cto" target="rd_dept" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_cto_qa" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="cto" target="qa_dept" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_cpo_product" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="cpo" target="product_dept" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_cfo_finance" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="cfo" target="finance_dept" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_coo_marketing" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="coo" target="marketing_dept" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_coo_hr" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1.5;strokeColor=#42A5F5;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="coo" target="hr_dept" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_rd_fe" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="rd_dept" target="frontend_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_rd_be" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="rd_dept" target="backend_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_qa_test" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="qa_dept" target="test_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_product_design" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="product_dept" target="design_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_mkt_digital" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="marketing_dept" target="digital_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_mkt_brand" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="marketing_dept" target="brand_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="link_hr_recruit" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;curved=0;strokeWidth=1;strokeColor=#90CAF9;endArrow=none;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" parent="1" source="hr_dept" target="recruit_team" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="title" value="科技公司组织架构" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=18;fontStyle=1;fontColor=#000000;" parent="1" vertex="1">
      <mxGeometry x="500" y="10" width="400" height="30" as="geometry" />
    </mxCell>
  </root>
</mxGraphModel>

```

## 关键模式

**自上而下树形结构：** CEO在顶部，各层级依次向下展开

**层级结构：**
- 第0层（CEO）：Y=60，尺寸200x80
- 第1层（高管）：Y=220，尺寸180x70，4个节点
- 第2层（部门）：Y=380，尺寸160x70，6个节点
- 第3层（团队）：Y=540，尺寸120x60，8个节点（使用第2层颜色）

**垂直间距：** 160px（层级之间的垂直距离）

**连接线单点出发特性：**
- **所有父节点统一使用 exitX=0.5**（底部中心点）
- 所有从同一父节点出发的连线都从同一个点出发
- 正交直线会自动形成树状分叉效果
- 使用 orthogonalEdgeStyle 确保连线整齐

**水平定位：**
- 子节点在父节点下方水平居中分布
- 子节点间保持适当间距（40-60px）
- 总宽度计算：Σ(子宽度) + (N-1)×间距
- 起始X = 父中心X - 总宽度/2

**连接线：**
- 从父节点下方中心点(exitX=0.5, exitY=1) → 子节点上方中心点(entryX=0.5, entryY=0)
- 使用正交直线(curved=0)和正交路由(orthogonalEdgeStyle)
- 颜色跟随父节点层级
- 粗细随层级递减：2 → 1.5 → 1

**配色（蓝色系）：**
- 第0层：#1976D2 + 黑字 + strokeWidth=2
- 第1层：#42A5F5 + 黑字 + strokeWidth=1.5
- 第2层及以后：#90CAF9 + 黑字 + strokeWidth=1

**连接线：** 粗细和颜色跟随父节点层级，所有连线统一从父节点底部中心出发，无箭头(endArrow=none)

**节点内容格式：** 职位&lt;br&gt;英文名&lt;br&gt;姓名/人数