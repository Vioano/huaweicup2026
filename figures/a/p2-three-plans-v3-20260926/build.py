#!/usr/bin/env python3
"""Deterministic, editable Draw.io source for the fixed three-plan constructor.

Only writes the sibling .drawio. SVG/PNG are exported by Draw.io Desktop.
"""
from pathlib import Path
from xml.etree import ElementTree as ET

OUT = Path(__file__).with_name("p2-three-plans.drawio")

INK = "#17324D"
MUTED = "#4B6377"
BLUE = "#E9F2F8"
TEAL = "#E4F4EF"
AMBER = "#FFF3DC"
RED = "#FCEBE9"
WHITE = "#FFFFFF"

root = ET.Element("mxfile", host="app.diagrams.net", modified="2026-09-26T00:00:00.000Z", agent="deterministic-python", version="30.0.2", type="device")
diagram = ET.SubElement(root, "diagram", id="p2-three-plans", name="问题二 · 三方案完整选择流程")
model = ET.SubElement(diagram, "mxGraphModel", dx="1300", dy="990", grid="1", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth="1300", pageHeight="990", math="0", shadow="0")
cells = ET.SubElement(model, "root")
ET.SubElement(cells, "mxCell", id="0")
ET.SubElement(cells, "mxCell", id="1", parent="0")


def box(id_, text, x, y, w, h, fill=WHITE, stroke="#93A9BA", size=21, bold=False, rounded=1):
    style = (f"rounded={rounded};whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};"
             f"strokeWidth=1.8;fontColor={INK};fontFamily=PingFang SC;fontSize={size};"
             f"fontStyle={1 if bold else 0};align=center;verticalAlign=middle;spacing=10;")
    cell = ET.SubElement(cells, "mxCell", id=id_, value=text, style=style, vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})


def label(id_, text, x, y, w, h, size=18, color=MUTED, bold=False, align="center"):
    style = (f"text;html=0;fillColor=none;strokeColor=none;fontColor={color};"
             f"fontFamily=PingFang SC;fontSize={size};fontStyle={1 if bold else 0};"
             f"align={align};verticalAlign=middle;whiteSpace=wrap;")
    cell = ET.SubElement(cells, "mxCell", id=id_, value=text, style=style, vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), attrib={"as": "geometry"})


def edge(id_, source, target, color="#657F91", dashed=False, points=()):
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;"
             f"html=0;strokeColor={color};strokeWidth=2.4;endArrow=block;endFill=1;"
             f"dashed={1 if dashed else 0};")
    c = ET.SubElement(cells, "mxCell", id=id_, style=style, edge="1", parent="1", source=source, target=target)
    g = ET.SubElement(c, "mxGeometry", relative="1", attrib={"as": "geometry"})
    if points:
        a = ET.SubElement(g, "Array", attrib={"as": "points"})
        for x, y in points:
            ET.SubElement(a, "mxPoint", x=str(x), y=str(y))


def fixed_edge(id_, coords, color="#657F91", dashed=False):
    """A fixed, editable orthogonal route for branches near adjacent cards."""
    style = (f"edgeStyle=none;html=0;strokeColor={color};strokeWidth=2.4;"
             f"endArrow=block;endFill=1;dashed={1 if dashed else 0};")
    c = ET.SubElement(cells, "mxCell", id=id_, style=style, edge="1", parent="1")
    g = ET.SubElement(c, "mxGeometry", relative="1", attrib={"as": "geometry"})
    ET.SubElement(g, "mxPoint", x=str(coords[0][0]), y=str(coords[0][1]), attrib={"as": "sourcePoint"})
    ET.SubElement(g, "mxPoint", x=str(coords[-1][0]), y=str(coords[-1][1]), attrib={"as": "targetPoint"})
    a = ET.SubElement(g, "Array", attrib={"as": "points"})
    for x, y in coords[1:-1]:
        ET.SubElement(a, "mxPoint", x=str(x), y=str(y))


# Quiet editorial frame: three construction columns above one scoring rail.
box("head", "问题二 · 三方案的构造与选择", 42, 24, 1216, 62, WHITE, WHITE, 29, True)
label("input", "输入：原始图、核数与固定配置　｜　输出：一份完整调度方案", 50, 92, 1200, 34, 18)
label("lane0", "① 基础方案", 46, 139, 365, 37, 20, INK, True)
label("lane1", "② 空闲区间方案", 468, 139, 365, 37, 20, INK, True)
label("lane2", "③ 可选局部改进", 890, 139, 365, 37, 20, INK, True)

box("p0", "构造 P0：基础完整方案\n始终保留为回退", 48, 188, 360, 104, BLUE, "#447EAA", 23, True)
box("p1", "尝试构造 P1：\n空闲区间完整方案", 470, 188, 360, 104, TEAL, "#378B75", 23, True)
box("p2ref", "在原始 P1 上尝试\n局部超图调整", 892, 188, 360, 104, AMBER, "#BA842C", 23, True)

box("abort", "立即返回 P0\nP1 不支持或构造失败；\n局部调整／重排发生非预期错误；\n字节证据无效；或评分不可用", 48, 353, 360, 190, RED, "#BC615B", 21)
box("keep", "P1 构造成功：保留原方案\n若与 P0 相同，不重复入列\n仍以原始 P1 尝试局部调整", 470, 353, 360, 127, TEAL, "#378B75", 21)
box("gate", "检查调整前后原始 COPY 字节数\n均为非负整数，且调整后严格更少？", 892, 353, 360, 127, AMBER, "#BA842C", 20, True)

box("skip", "无 P2：局部调整不支持、\n字节数未严格下降，或重排不支持\n继续处理已构造方案", 470, 543, 360, 126, WHITE, "#93A9BA", 20)
box("retime", "仅通过字节门槛后重排\n生成完整 P2；若与已有完整方案\n相同，不重复入列", 892, 543, 360, 126, AMBER, "#BA842C", 20)

box("dedup", "完整方案去重\n按 P0 → P1 → P2 构造顺序排列", 470, 715, 360, 85, BLUE, "#447EAA", 20, True)
box("single", "仅一份不同方案\n直接返回 P0；不请求评分", 48, 845, 360, 92, BLUE, "#447EAA", 19)
box("score", "逐份请求注入评分接口\n仅评分不同的完整方案；总请求 ≤ 3", 470, 845, 360, 92, BLUE, "#447EAA", 19, True)
box("choose", "按（Makespan，额外 COPY 字节数）\n严格字典序选最小；平局留先构造者", 892, 845, 360, 92, TEAL, "#378B75", 20, True)

edge("e01", "p0", "p1")
edge("e12", "p1", "keep")
edge("e23", "keep", "p2ref", points=((850, 325),))
fixed_edge("efail", ((470, 283), (438, 283), (438, 392), (408, 392)), "#B45D57")
edge("eref", "p2ref", "gate")
fixed_edge("egate_no", ((892, 476), (860, 476), (860, 601), (830, 601)), "#A17C3B")
edge("egate_yes", "gate", "retime", "#A17C3B")
edge("eret_skip", "retime", "skip", "#A17C3B", True)
edge("eskip_dedup", "skip", "dedup")
edge("eret_dedup", "retime", "dedup", points=((850, 695),))
edge("ededup_score", "dedup", "score")
edge("esingle", "dedup", "single", points=((435, 819),))
edge("escore_choose", "score", "choose")

label("no1", "失败", 336, 309, 85, 29, 16, "#A1453E", True)
label("ok1", "成功", 765, 309, 75, 29, 16, "#277964", True)
label("no2", "否", 808, 488, 60, 27, 16, "#94702D", True)
label("yes2", "是", 1195, 490, 60, 27, 16, "#94702D", True)
label("skiphint", "可继续", 401, 680, 87, 27, 16)
label("scorehint", "≥ 2 份", 704, 806, 110, 27, 16)
label("singlehint", "= 1 份", 390, 808, 103, 27, 16)
label("foot", "局部原始 COPY 字节门槛不代表官方最终 Makespan 改善；图中评分来自注入接口。", 45, 948, 1210, 32, 18, MUTED)

ET.indent(root, space="  ")
OUT.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
print(OUT)
