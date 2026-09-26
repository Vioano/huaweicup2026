"""Deterministic, editable Draw.io figure for the fixed P3 forest decision."""
from pathlib import Path
from xml.etree import ElementTree as ET

OUT = Path(__file__).parent
ROOT = ET.Element("mxfile", host="app.diagrams.net", modified="2026-09-26T00:00:00.000Z", agent="P3 figure builder", version="24.7.17", type="device")
page = ET.SubElement(ROOT, "diagram", id="p3-forest", name="P3 树状排序与候选评价")
model = ET.SubElement(page, "mxGraphModel", dx="1500", dy="1020", grid="0", page="1", pageScale="1", pageWidth="1500", pageHeight="1020", math="0", shadow="0")
root = ET.SubElement(model, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")

COLORS = {
    "ink": "#17243B", "muted": "#53657A", "line": "#9BACBF", "blue": "#EDF4FC",
    "teal": "#E9F7F4", "amber": "#FFF4DD", "gray": "#F2F5F8", "white": "#FFFFFF",
}


def box(id, x, y, w, h, text, *, fill="white", stroke="line", size=19,
        bold=False, align="center", rounded=True, color="ink"):
    style = (f"rounded={int(rounded)};arcSize=14;whiteSpace=wrap;html=1;"
             f"fillColor={COLORS.get(fill, fill)};strokeColor={COLORS.get(stroke, stroke)};"
             f"strokeWidth=1.5;fontColor={COLORS.get(color, color)};fontSize={size};"
             f"fontFamily=PingFang SC;fontStyle={int(bold)};align={align};verticalAlign=middle;"
             "spacingLeft=16;spacingRight=16;spacingTop=8;spacingBottom=8;")
    cell = ET.SubElement(root, "mxCell", id=id, value=text, style=style, vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})


def line(id, source, target, *, color="muted", exit_x=None, exit_y=None,
         entry_x=None, entry_y=None, dashed=False):
    style = (f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
             f"html=1;strokeColor={COLORS.get(color, color)};strokeWidth=2;"
             f"endArrow=block;endFill=1;dashed={int(dashed)};")
    if exit_x is not None:
        style += f"exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;"
    if entry_x is not None:
        style += f"entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;"
    cell = ET.SubElement(root, "mxCell", id=id, style=style, edge="1", source=source, target=target, parent="1")
    ET.SubElement(cell, "mxGeometry", relative="1", attrib={"as": "geometry"})


# Upper panel: conditional ordering guarantee, not an official score claim.
box("title", 45, 20, 1410, 46, "问题三｜树状分支排序与完整方案的评价决策", size=29, bold=True, stroke="white", align="left")
box("upper-bg", 40, 82, 1420, 310, "", fill="gray", stroke="gray")
box("upper-label", 66, 92, 700, 42, "一、排序仅作用于满足条件的树状分支", size=22, bold=True, stroke="gray", fill="gray", align="left")
box("scope", 70, 158, 388, 177,
    "多棵互不交错的归约树，且至少有一处汇合；<br>每个操作有一个已知字节数的输出；<br>非根输出只供唯一父操作使用。",
    fill="blue", size=19, align="left")
box("order", 553, 170, 390, 150,
    "对子树计算 hᵢ − rᵢ<br>按该值递减处理同一父操作的子树<br>同值按操作编号排序，随后执行父操作",
    fill="teal", size=20, bold=True)
box("guarantee", 1038, 158, 388, 177,
    "在上述非交错树模型内，<br>使每棵树内部结果的峰值占用最小。<br><font color='#53657A'>这是排序量的保证；不推出官方完成时间或缓存效果。</font>",
    fill="amber", size=20)
line("a1", "scope", "order")
line("a2", "order", "guarantee")

# Lower panel: the exact fixed-code order of gates.
box("lower-label", 56, 415, 1350, 42, "二、完整候选共用最多三次在线 E0 评价", size=22, bold=True, stroke="white", align="left")
box("prior", 55, 495, 186, 111, "基础方案先成当前最优；<br>共享输入或注意力候选先行", fill="blue", size=18)
box("budget", 264, 495, 181, 111, "已用评价次数<br>少于 3？", fill="white", size=19, bold=True)
box("structure", 468, 495, 181, 111, "能构造合法的<br>树状排序方案？", fill="white", size=19, bold=True)
box("duplicate", 672, 495, 181, 111, "与当前最优方案<br>编码不同？", fill="white", size=19, bold=True)
box("bound", 876, 495, 270, 111, "若下界可得：<br>下界 < 当前最优完成时间？", fill="white", size=18, bold=True)
box("e0", 1170, 495, 270, 111, "剩余预算内调用官方 E0<br>评价树状候选", fill="teal", size=19, bold=True)
for n, s, t in [("b1", "prior", "budget"), ("b2", "budget", "structure"),
                ("b3", "structure", "duplicate"), ("b4", "duplicate", "bound"),
                ("b5", "bound", "e0")]:
    line(n, s, t)
box("skip", 264, 658, 882, 91,
    "任一检查不通过 → 跳过树状候选的 E0 评价<br>下界无法证明时继续，不据此剪枝。",
    fill="gray", size=19)
for n, s in [("s1", "budget"), ("s2", "structure"), ("s3", "duplicate"), ("s4", "bound")]:
    line(n, s, "skip", color="line", exit_x=0.5, exit_y=1, entry_x={"budget":.10,"structure":.34,"duplicate":.58,"bound":.87}[s], entry_y=0)
box("compare", 1170, 658, 270, 91, "E0 验证有效后：<br>完成时间严格更短？", fill="amber", size=19, bold=True)
line("b6", "e0", "compare", exit_x=.5, exit_y=1, entry_x=.5, entry_y=0)
box("outcome", 870, 810, 570, 97,
    "是 → 替换当前最优方案<br>否或评价校验失败 → 保留当前最优方案", fill="blue", size=19)
line("b7", "compare", "outcome", exit_x=.5, exit_y=1, entry_x=.77, entry_y=0)
box("note", 55, 811, 760, 95,
    "hᵢ：子树内部结果的峰值字节数；rᵢ：子树完成后保留的输出字节数。<br>树排序不改变既定分核归属；图中“完成时间”均指官方 Makespan。",
    fill="white", stroke="white", size=17, align="left", color="muted")

ET.indent(ROOT, space="  ")
ET.ElementTree(ROOT).write(OUT / "p3-forest-decision.drawio", encoding="utf-8", xml_declaration=True)
