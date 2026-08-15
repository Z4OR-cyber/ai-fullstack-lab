# {图表类型} - {变体名称}示例

**适用场景：** {一句话描述适用场景，如："展示3-5层技术栈，每层包含多个独立组件"}

---

## 布局规范

### 整体策略

**核心思路：** {描述布局的核心思想，如："自上而下分层堆叠，全宽容器，垂直连接表示依赖"}

**布局特征：**
- {特征1，如："层容器全宽，子组件水平均分"}
- {特征2，如："层间距固定，保持视觉呼吸感"}
- {特征3，如："使用颜色区分不同层级"}
- {特征4（可选）}

### 坐标计算公式

**画布参数：**
```
画布宽度 = {固定值或计算公式，如：1600}
画布高度 = {计算公式，如：元素数 × 单元高度 + 总边距}
视口宽度 = {推荐值，如：1400}
视口高度 = {推荐值，如：1000}
```

**{主要元素类型1}定位：**
```
{元素}X = {公式，如：基础X + 索引 × 步长}
{元素}Y = {公式，如：基础Y + 索引 × (高度 + 间距)}
{元素}宽 = {固定值或公式，如：200}
{元素}高 = {固定值或公式，如：60}
```

**{主要元素类型2}定位（如有）：**
```
{元素}X = {公式}
{元素}Y = {公式}
{元素}宽 = {固定值或公式}
{元素}高 = {固定值或公式}
```

**{次要元素/子元素}定位（如有）：**
```
{元素}X = {公式，如：相对父容器的偏移}
{元素}Y = {公式}
{元素}宽 = {固定值或公式}
{元素}高 = {固定值或公式}

{关键变量}计算 = {公式说明}
```

**连接线规则：**
```
{连接类型1}：{规则描述，如：从元素右侧 (exitX=1) 到下一元素左侧 (entryX=0)}
{连接类型2}：{规则描述}
{连接类型3（可选）}：{规则描述}
```

### 关键参数表

| 参数名称 | 推荐值 | 说明 | 可调整范围 |
|---------|--------|------|-----------|
| 画布宽度 | {值} | {说明} | {范围} |
| 画布高度 | {值/公式} | {说明} | {范围} |
| {参数1} | {值} | {说明} | {范围} |
| {参数2} | {值} | {说明} | {范围} |
| {参数3} | {值} | {说明} | {范围} |
| {参数4} | {值} | {说明} | {范围} |
| {参数5} | {值} | {说明} | {范围} |

---

## 关键共识

### 重要提示

⚠️ **本示例仅供结构参考**
- 展示正确的 XML 语法、样式定义和{核心逻辑}
- **严禁直接复制**示例中的{具体内容，如：节点内容/数量/固定坐标}
- 必须根据用户需求**动态计算**所有{调整对象，如：坐标值/布局参数}
- 参考示例的**{核心要素}和{关键策略}**，而非具体数值

### 样式规范

**{元素类型1}样式：**
```xml
style="rounded={值};whiteSpace=wrap;html=1;
      fillColor={颜色};strokeColor={颜色};strokeWidth={值};
      {其他关键属性};
      fontSize={值};fontStyle={值};"
```

**{元素类型2}样式：**
```xml
style="rounded={值};whiteSpace=wrap;html=1;
      fillColor={颜色};strokeColor={颜色};
      {其他关键属性};
      fontSize={值};fontStyle={值};"
```

**{元素类型3（如连接线）}样式：**
```xml
<!-- {类型1说明，如：强依赖/实线} -->
style="edgeStyle={值};rounded={值};
      orthogonalLoop={值};jettySize=auto;html=1;
      strokeWidth={值};strokeColor={颜色};dashed={值};"

<!-- {类型2说明，如：弱依赖/虚线} -->
style="edgeStyle={值};rounded={值};
      orthogonalLoop={值};jettySize=auto;html=1;
      strokeWidth={值};strokeColor={颜色};dashed={值};"
```

### 配色建议

**{变体名称}的典型配色：**
- **{层级/类型1}**：`fillColor={颜色} strokeColor={颜色}` - {说明}
- **{层级/类型2}**：`fillColor={颜色} strokeColor={颜色}` - {说明}
- **{层级/类型3}**：`fillColor={颜色} strokeColor={颜色}` - {说明}
- **{其他元素}**：`fillColor={颜色} strokeColor={颜色}` - {说明}

**配色原则：**
- {原则1，如：同类型使用统一配色}
- {原则2，如：渐变色表示层级关系}

---

## 案例代码

### 使用方法
复制下方完整代码，在 diagrams.net 选择 **File → Import from → Text**，粘贴即可打开

### 完整 XML（{N个元素}示例）

```xml
<mxfile host="app.diagrams.net">
  <diagram name="{变体名称示例}">
    <mxGraphModel dx="{视口宽}" dy="{视口高}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{画布宽}" pageHeight="{画布高}" background="#ffffff">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>

        <!-- {辅助元素说明，如：中心线/参考线（可选）} -->
        <mxCell id="{id}" value="" style="{辅助线样式}" edge="1" parent="1">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="{X1}" y="{Y1}" as="sourcePoint"/>
            <mxPoint x="{X2}" y="{Y2}" as="targetPoint"/>
          </mxGeometry>
        </mxCell>

        <!-- {元素组1说明} -->
        <!-- {元素1详细说明} -->
        <mxCell id="{id}" value="{文本内容}" style="{完整样式}" vertex="1" parent="1">
          <mxGeometry x="{X}" y="{Y}" width="{宽}" height="{高}" as="geometry"/>
        </mxCell>

        <!-- {元素2详细说明} -->
        <mxCell id="{id}" value="{文本内容}" style="{完整样式}" vertex="1" parent="1">
          <mxGeometry x="{X}" y="{Y}" width="{宽}" height="{高}" as="geometry"/>
        </mxCell>

        <!-- {如有容器嵌套} -->
        <!-- {容器元素} -->
        <mxCell id="{容器id}" value="{容器标题}" style="{容器样式}" vertex="1" parent="1">
          <mxGeometry x="{X}" y="{Y}" width="{宽}" height="{高}" as="geometry"/>
        </mxCell>

        <!-- {容器内子元素1} -->
        <mxCell id="{子元素id}" value="{文本}" style="{子元素样式}" vertex="1" parent="{容器id}">
          <mxGeometry x="{相对X}" y="{相对Y}" width="{宽}" height="{高}" as="geometry"/>
        </mxCell>

        <!-- {容器内子元素2} -->
        <mxCell id="{子元素id}" value="{文本}" style="{子元素样式}" vertex="1" parent="{容器id}">
          <mxGeometry x="{相对X}" y="{相对Y}" width="{宽}" height="{高}" as="geometry"/>
        </mxCell>

        <!-- {元素组2说明（如有更多组）} -->
        {重复上述元素结构，调整坐标和属性}

        <!-- {连接线部分} -->
        <!-- {连接1说明} -->
        <mxCell id="{连接id}" value="{标签文本（可选）}" style="{连接样式}" edge="1" parent="1" source="{源id}" target="{目标id}">
          <mxGeometry relative="1" as="geometry"/>
        </mxCell>

        <!-- {连接2说明} -->
        <mxCell id="{连接id}" value="{标签文本（可选）}" style="{连接样式}" edge="1" parent="1" source="{源id}" target="{目标id}">
          <mxGeometry relative="1" as="geometry">
            {如有特殊路径点，在此添加 Array/mxPoint}
          </mxGeometry>
        </mxCell>

        <!-- {更多连接线...} -->

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

---

## 扩展说明

### {调整场景1，如：元素数量调整}

**当{条件变化}时：**
1. {步骤1，如：重新计算步长/间距}
2. {步骤2，如：按新参数更新坐标}
3. {步骤3，如：调整画布尺寸}
4. {注意事项}

**计算公式：**
```
{公式1} = {计算方式}
{公式2} = {计算方式}
```

### {调整场景2（可选）}

**当{条件变化}时：**
1. {步骤1}
2. {步骤2}
3. {步骤3}

### 对齐优化

**生成后{是否需要}运行对齐脚本：**
```bash
python script/{脚本名称}.py {输出文件路径}
```
- **脚本作用**：{说明，如：自动优化间距、对齐元素、调整画布尺寸}
- **适用场景**：{说明，如：布局复杂或元素较多时}
