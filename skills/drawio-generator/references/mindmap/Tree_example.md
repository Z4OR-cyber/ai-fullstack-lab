# 思维导图 - 逻辑树模式示例

适用：读书笔记、项目拆解、知识体系、大纲整理等有明确层级结构的内容

**重要提示：**
- 本示例仅供结构参考，展示正确的XML语法和布局逻辑
- **严禁直接复制示例内容**：节点数量、文本内容、具体坐标必须根据用户需求动态生成
- 必须参考示例的结构关系（从左到右展开、层级颜色、连接方式），而非照搬具体数值
- 本示例简化为2层结构演示，实际生成时可有更多层级

---

## 完整可用代码（逻辑树布局演示）

**使用方法：** 复制下方完整代码，在 diagrams.net 选择 File → Import from → Text，粘贴即可打开

```xml
<mxGraphModel dx="1412" dy="1222" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="900" background="#FFFFFF" math="0" shadow="0">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />
    <mxCell id="sHhK079kIFacFkWtw_FD-63" value="GenAI垂直应用" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#1976D2;strokeColor=#42A5F5;fontColor=#000000;fontSize=16;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="310" y="870" width="200" height="80" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-64" value="用户画像" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#42A5F5;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="620" y="715" width="150" height="60" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-65" value="技术架构" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#42A5F5;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="620" y="880" width="150" height="60" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-66" value="商业化" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#42A5F5;strokeColor=#42A5F5;fontColor=#000000;fontSize=14;fontStyle=1;" parent="1" vertex="1">
      <mxGeometry x="620" y="1045" width="150" height="60" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-67" value="内容创作者" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="850" y="695" width="140" height="45" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-68" value="企业团队" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="850" y="770" width="140" height="45" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-69" value="LLM基座" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="850" y="858" width="140" height="45" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-70" value="RAG管道" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="850" y="933" width="140" height="45" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-71" value="免费增值" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="850" y="1023" width="140" height="45" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-72" value="企业授权" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#90CAF9;strokeColor=#42A5F5;fontColor=#000000;fontSize=12;" parent="1" vertex="1">
      <mxGeometry x="850" y="1098" width="140" height="45" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-73" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#1976D2;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-63" target="sHhK079kIFacFkWtw_FD-64" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-74" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#1976D2;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-63" target="sHhK079kIFacFkWtw_FD-65" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-75" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#1976D2;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-63" target="sHhK079kIFacFkWtw_FD-66" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-76" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-64" target="sHhK079kIFacFkWtw_FD-67" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-77" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-64" target="sHhK079kIFacFkWtw_FD-68" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-78" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-65" target="sHhK079kIFacFkWtw_FD-69" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-79" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-65" target="sHhK079kIFacFkWtw_FD-70" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-80" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-66" target="sHhK079kIFacFkWtw_FD-71" edge="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="sHhK079kIFacFkWtw_FD-110" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;curved=1;html=1;strokeWidth=2;strokeColor=#42A5F5;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="1" source="sHhK079kIFacFkWtw_FD-66" target="sHhK079kIFacFkWtw_FD-72" edge="1">
      <mxGeometry relative="1" as="geometry">
        <mxPoint x="770" y="1075" as="sourcePoint" />
        <mxPoint x="850" y="1120" as="targetPoint" />
      </mxGeometry>
    </mxCell>
  </root>
</mxGraphModel>
```

## 关键模式

**从左到右展开：** 根节点在左侧，各层依次向右扩展

**水平间距：** 根节点x=310 → 第1层x=620 → 第2层x=850，间距310→230px

**垂直对称分布：** 
- 根节点中心：y=910（870+80/2）
- 第1层3个分支（高60px，间距165px）：
  - totalHeight = 3×60 + 2×165 = 510
  - startY = 910 - 510/2 = 655
  - 实际位置：y=715, 880, 1045（以根节点中心对称）
- 第2层2个分支围绕父节点对称分布

**连接：** 父节点右侧(exitX=1, exitY=0.5) → 子节点左侧(entryX=0, entryY=0.5)，使用曲线(curved=1)，固定出入口，连接线颜色跟随父节点

**配色（蓝色系）：** #1976D2 → #42A5F5 → #90CAF9
**其他推荐色系：**
- 绿色系：#388E3C → #66BB6A → #A5D6A7
- 紫色系：#7B1FA2 → #AB47BC → #CE93D8
- 橙色系：#F57C00 → #FF9800 → #FFCC80

**连接线：** 统一粗细strokeWidth=2，颜色跟随父节点，orthogonalEdgeStyle + curved=1实现固定节点曲线

### 注意：超过第2层的所有层级使用第2层颜色，避免颜色过淡