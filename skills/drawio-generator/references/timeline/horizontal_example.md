# 时间轴 - 横向布局示例

适用：节点数量≤8个，横向布局

**重要提示：**
- 本示例仅供结构参考，展示正确的XML语法和布局逻辑
- **严禁直接复制示例内容**：节点数量、文本内容、具体坐标必须根据用户需求动态生成
- 必须参考示例的结构关系（5层卡片、交替布局、间距规则），而非照搬具体数值
- 本示例是5节点演示，实际生成时节点数量和内容完全不同

---

## 完整可用代码（5节点演示）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" version="24.0.0">
  <diagram id="timeline_h" name="字节跳动发展历程">
    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" pageScale="1" pageWidth="1600" pageHeight="900" background="#FFFFFF" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        
        <!-- 时间线（水平） -->
        <mxCell id="timeline_line" value="" style="endArrow=none;html=1;dashed=1;strokeColor=#999999;strokeWidth=2;" parent="1" edge="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="50" y="400" as="sourcePoint" />
            <mxPoint x="1550" y="400" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        
        <!-- 节点1: 2012年3月 - 公司成立（上方） -->
        <mxCell id="n1_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#5E5474;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="190" y="390" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c1_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="80" y="180" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c1_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#5E5474;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="88" y="188" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c1_t1" value="2012年3月" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="105" y="193" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c1_t2" value="公司成立" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="100" y="240" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c1_t3" value="字节跳动公司正式成立，以个性化推荐技术为核心，开启内容分发新赛道" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="100" y="280" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点2: 2016年9月 - 用户突破6亿（下方） -->
        <mxCell id="n2_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#3E4653;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="490" y="390" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c2_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="380" y="450" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c2_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#3E4653;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="388" y="458" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c2_t1" value="2016年9月" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="405" y="463" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c2_t2" value="用户突破6亿" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="400" y="500" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c2_t3" value="今日头条用户量突破6亿，成为国内领先的资讯分发平台，奠定个性化推荐技术的行业地位" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="400" y="540" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点3: 2018年8月 - 全球化布局（上方） -->
        <mxCell id="n3_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#455A46;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="790" y="390" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c3_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="680" y="180" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c3_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#455A46;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="688" y="188" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c3_t1" value="2018年8月" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="705" y="193" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c3_t2" value="全球化布局" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="700" y="240" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c3_t3" value="抖音海外版TikTok正式上线，迅速在全球市场获得用户青睐，开启字节跳动全球化征程" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="700" y="280" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点4: 2020年11月 - 估值突破2800亿（下方） -->
        <mxCell id="n4_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#756848;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="1090" y="390" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c4_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="980" y="450" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c4_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#756848;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="988" y="458" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c4_t1" value="2020年11月" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="1005" y="463" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c4_t2" value="估值突破2800亿" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="1000" y="500" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c4_t3" value="完成上市前最后一轮融资，估值超过2800亿美元，成为全球最具价值的未上市科技公司之一" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="1000" y="540" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点5: 2023年11月 - AI时代开启（上方） -->
        <mxCell id="n5_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#5C3E3E;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="1390" y="390" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c5_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="1280" y="180" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c5_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#5C3E3E;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="1288" y="188" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c5_t1" value="2023年11月" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="1305" y="193" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c5_t2" value="AI时代开启" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="1300" y="240" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c5_t3" value="发布豆包大模型，开启多模态AI研发新阶段，将AI技术融入全线产品矩阵" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="1300" y="280" width="200" height="60" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## 关键模式

**卡片5层结构：** 背景容器 → 顶部色块 → 时间标识 → 副标题 → 正文描述

**上方卡片Y坐标：** 180（= 400 - 170 - 50）  
**下方卡片Y坐标：** 450（= 400 + 50）

**节点坐标计算（5节点）：**
- 节点间距：300px（= 1200 / 4）
- 节点1中心：200，圆形x=190，卡片x=80
- 节点2中心：500，圆形x=490，卡片x=380
- 节点3中心：800，圆形x=790，卡片x=680
- 节点4中心：1100，圆形x=1090，卡片x=980
- 节点5中心：1400，圆形x=1390，卡片x=1280

**布局要点：**
- 时间线固定在y=400
- 卡片交替上下排列（奇数上，偶数下）
- 所有文本必须包含 `whiteSpace=wrap;html=1`
- 配色按顺序循环使用