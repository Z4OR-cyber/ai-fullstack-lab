# 时间轴 - 纵向布局示例

适用：节点数量>8个，纵向布局

**重要提示：**
- 本示例仅供结构参考，展示正确的XML语法和布局逻辑
- **严禁直接复制示例内容**：节点数量、文本内容、具体坐标必须根据用户需求动态生成
- 必须参考示例的结构关系（5层卡片、左右交替、间距规则），而非照搬具体数值
- 本示例是9节点演示，实际生成时节点数量和内容完全不同

---

## 完整可用代码（9节点演示）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" version="24.0.0">
  <diagram id="timeline_v" name="人工智能发展时间轴">
    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" pageScale="1" pageWidth="900" pageHeight="2180" background="#FFFFFF" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        
        <!-- 时间线（垂直） -->
        <mxCell id="timeline_line" value="" style="endArrow=none;html=1;dashed=1;strokeColor=#999999;strokeWidth=2;" parent="1" edge="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="400" y="50" as="sourcePoint" />
            <mxPoint x="400" y="2130" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        
        <!-- 节点1: 1956年8月 - AI诞生（左侧） -->
        <mxCell id="n1_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#5E5474;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="90" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c1_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="110" y="15" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c1_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#5E5474;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="118" y="23" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c1_t1" value="1956年8月" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="135" y="28" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c1_t2" value="AI诞生" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="130" y="70" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c1_t3" value="达特茅斯会议召开，人工智能概念正式提出" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="130" y="110" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点2: 1966年 - ELIZA（右侧） -->
        <mxCell id="n2_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#3E4653;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="350" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c2_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="450" y="275" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c2_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#3E4653;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="458" y="283" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c2_t1" value="1966年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="475" y="288" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c2_t2" value="ELIZA" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="470" y="330" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c2_t3" value="第一个聊天机器人ELIZA诞生，能够模拟心理医生对话" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="470" y="370" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点3: 1997年 - 深蓝战胜卡斯帕罗夫（左侧） -->
        <mxCell id="n3_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#455A46;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="610" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c3_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="110" y="535" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c3_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#455A46;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="118" y="543" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c3_t1" value="1997年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="135" y="548" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c3_t2" value="深蓝战胜卡斯帕罗夫" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="130" y="590" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c3_t3" value="IBM深蓝计算机战胜国际象棋世界冠军卡斯帕罗夫" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="130" y="630" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点4: 2012年 - AlexNet（右侧） -->
        <mxCell id="n4_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#756848;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="870" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c4_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="450" y="795" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c4_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#756848;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="458" y="803" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c4_t1" value="2012年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="475" y="808" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c4_t2" value="AlexNet" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="470" y="850" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c4_t3" value="AlexNet在ImageNet竞赛中夺冠，深度学习浪潮兴起" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="470" y="890" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点5: 2016年 - AlphaGo战胜李世石（左侧） -->
        <mxCell id="n5_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#5C3E3E;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="1130" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c5_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="110" y="1055" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c5_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#5C3E3E;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="118" y="1063" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c5_t1" value="2016年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="135" y="1068" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c5_t2" value="AlphaGo战胜李世石" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="130" y="1110" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c5_t3" value="AlphaGo战胜世界围棋冠军李世石，AI在复杂领域超越人类" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="130" y="1150" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点6: 2018年 - GPT-1（右侧） -->
        <mxCell id="n6_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#4A7C8C;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="1390" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c6_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="450" y="1315" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c6_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#4A7C8C;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="458" y="1323" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c6_t1" value="2018年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="475" y="1328" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c6_t2" value="GPT-1" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="470" y="1370" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c6_t3" value="OpenAI发布GPT-1，预训练语言模型时代开启" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="470" y="1410" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点7: 2020年 - GPT-3（左侧） -->
        <mxCell id="n7_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#8B6B47;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="1650" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c7_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="110" y="1575" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c7_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#8B6B47;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="118" y="1583" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c7_t1" value="2020年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="135" y="1588" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c7_t2" value="GPT-3" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="130" y="1630" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c7_t3" value="OpenAI发布GPT-3，参数规模达1750亿，能力大幅提升" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="130" y="1670" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点8: 2022年 - ChatGPT（右侧） -->
        <mxCell id="n8_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#6B5B8C;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="1910" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c8_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="450" y="1835" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c8_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#6B5B8C;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="458" y="1843" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c8_t1" value="2022年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="475" y="1848" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c8_t2" value="ChatGPT" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="470" y="1890" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c8_t3" value="ChatGPT正式发布，生成式AI爆发，全球用户突破1亿" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="470" y="1930" width="200" height="60" as="geometry" />
        </mxCell>

        <!-- 节点9: 2023年 - GPT-4（左侧） -->
        <mxCell id="n9_dot" value="" style="ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#5A7C5A;strokeColor=#333333;strokeWidth=2;" parent="1" vertex="1">
          <mxGeometry x="390" y="2170" width="20" height="20" as="geometry" />
        </mxCell>
        <mxCell id="c9_bg" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=2;arcSize=5;" parent="1" vertex="1">
          <mxGeometry x="110" y="2095" width="240" height="170" as="geometry" />
        </mxCell>
        <mxCell id="c9_header" value="" style="rounded=1;whiteSpace=wrap;html=1;strokeColor=none;fillColor=#5A7C5A;arcSize=10;" parent="1" vertex="1">
          <mxGeometry x="118" y="2103" width="224" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c9_t1" value="2023年" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#FFFFFF;fontStyle=1;fontSize=14;" parent="1" vertex="1">
          <mxGeometry x="135" y="2108" width="190" height="30" as="geometry" />
        </mxCell>
        <mxCell id="c9_t2" value="GPT-4" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontColor=#333333;fontStyle=1;fontSize=20;" parent="1" vertex="1">
          <mxGeometry x="130" y="2150" width="200" height="40" as="geometry" />
        </mxCell>
        <mxCell id="c9_t3" value="OpenAI发布GPT-4，支持多模态输入，能力全面升级" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontColor=#666666;fontSize=12;" parent="1" vertex="1">
          <mxGeometry x="130" y="2190" width="200" height="60" as="geometry" />
        </mxCell>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

## 关键模式

**卡片5层结构：** 背景容器 → 顶部色块 → 时间标识 → 副标题 → 正文描述

**左侧卡片X坐标：** 110（固定）  
**右侧卡片X坐标：** 450（固定）

**节点坐标计算（9节点）：**
- 节点间距：260px（= 2080 / 8）
- 节点1中心Y：200，圆形y=90，卡片y=15
- 节点2中心Y：460，圆形y=350，卡片y=275
- 节点3中心Y：720，圆形y=610，卡片y=535
- 节点4中心Y：980，圆形y=870，卡片y=795
- 节点5中心Y：1240，圆形y=1130，卡片y=1055
- 节点6中心Y：1500，圆形y=1390，卡片y=1315
- 节点7中心Y：1760，圆形y=1650，卡片y=1575
- 节点8中心Y：2020，圆形y=1910，卡片y=1835
- 节点9中心Y：2280，圆形y=2170，卡片y=2095

**卡片Y坐标计算：**
- 卡片高度：170px
- 卡片Y = 节点中心Y - 卡片高度/2 = 节点中心Y - 85

**布局要点：**
- 时间线固定在x=400
- 卡片交替左右排列（奇数左，偶数右）
- 所有文本必须包含 `whiteSpace=wrap;html=1`
- 配色按顺序循环使用