"""Build editable Draw.io geometry drafts from measured v9 PNG coordinates.

The labels are transcribed from v9 and are NOT approved for v10 publication.
Replace them from the paper supervisor's fixed wording list before final export.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


OUT = Path(__file__).resolve().parent
INK = "#091142"
BLUE = "#006DFF"
PURPLE = "#7B2CFF"
TEAL = "#00AC9C"
ORANGE = "#FF8D00"


class Diagram:
    def __init__(self, name: str, width: int, height: int):
        self.name, self.width, self.height = name, width, height
        self.root = ET.Element("mxfile", host="app.diagrams.net", type="device")
        page = ET.SubElement(self.root, "diagram", name=name, id=name)
        model = ET.SubElement(
            page,
            "mxGraphModel",
            dx="0", dy="0", grid="0", gridSize="10", guides="1",
            tooltips="1", connect="1", arrows="1", fold="1", page="1",
            pageScale="1", pageWidth=str(width), pageHeight=str(height),
            math="0", shadow="0", background="#FFFFFF",
        )
        self.cells = ET.SubElement(model, "root")
        ET.SubElement(self.cells, "mxCell", id="0")
        ET.SubElement(self.cells, "mxCell", id="1", parent="0")
        self.used: set[str] = set()
        self.rect("canvas", 0, 0, width, height, fill="#FFFFFF", stroke="none", width_stroke=0)

    def cell(self, key: str, style: str, value: str, x: float, y: float, w: float, h: float):
        if key in self.used:
            raise ValueError(f"duplicate shape key: {key}")
        self.used.add(key)
        c = ET.SubElement(self.cells, "mxCell", id=key, value=value, style=style, vertex="1", parent="1")
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})
        return c

    def rect(self, key, x, y, w, h, *, fill="#FFFFFF", stroke="#34445D", width_stroke=2,
             rounded=1, gradient=None, dashed=0, opacity=100, arc=4):
        style = (
            f"rounded={rounded};arcSize={arc};whiteSpace=wrap;html=1;"
            f"fillColor={fill};strokeColor={stroke};strokeWidth={width_stroke};"
            f"dashed={dashed};opacity={opacity};"
        )
        if gradient:
            style += f"gradientColor={gradient};gradientDirection=south;"
        return self.cell(key, style, "", x, y, w, h)

    def ellipse(self, key, x, y, w, h, *, fill="#FFD990", stroke="#A33E00", width_stroke=3):
        style = f"ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth={width_stroke};"
        return self.cell(key, style, "", x, y, w, h)

    def text(self, key, value, x, y, w, h, *, size=30, color=INK, bold=False,
             align="center", font="Songti SC", fill="none", stroke="none", italic=False):
        style = (
            f"text;html=1;whiteSpace=wrap;align={align};verticalAlign=middle;"
            f"fontFamily={font};fontSize={size};fontColor={color};"
            f"fontStyle={(1 if bold else 0)+(2 if italic else 0)};"
            f"fillColor={fill};strokeColor={stroke};spacing=0;overflow=fill;"
        )
        return self.cell(key, style, value, x, y, w, h)

    def diamond(self, key, x, y, w, h, *, fill="#F0F6FF", stroke=BLUE):
        return self.cell(key, f"rhombus;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;", "", x, y, w, h)

    def edge(self, key, x1, y1, x2, y2, *, color="#273850", width_stroke=3,
             dashed=0, arrow=True, curved=False, points=()):
        if key in self.used:
            raise ValueError(f"duplicate edge key: {key}")
        self.used.add(key)
        style = (
            "edgeStyle=none;html=1;rounded=0;"
            f"strokeColor={color};strokeWidth={width_stroke};dashed={dashed};"
            f"endArrow={'classic' if arrow else 'none'};endFill=1;"
            f"curved={1 if curved else 0};"
        )
        c = ET.SubElement(self.cells, "mxCell", id=key, value="", style=style, edge="1", parent="1")
        g = ET.SubElement(c, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(g, "mxPoint", x=str(x1), y=str(y1), **{"as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", x=str(x2), y=str(y2), **{"as": "targetPoint"})
        if points:
            a = ET.SubElement(g, "Array", **{"as": "points"})
            for x, y in points:
                ET.SubElement(a, "mxPoint", x=str(x), y=str(y))

    def write(self):
        path = OUT / f"{self.name}.drawio"
        ET.indent(self.root, space="  ")
        path.write_bytes(ET.tostring(self.root, encoding="utf-8", xml_declaration=True))
        return path


def node(d: Diagram, key: str, label: str, x: float, y: float, w: float, h: float, *, size=32):
    d.rect(key + "-box", x, y, w, h, fill="#DBCBFF", gradient="#F7F3FF", stroke=INK, width_stroke=2, arc=12)
    d.text(key + "-label", label, x + 4, y + 2, w - 8, h - 4, size=size, bold=True)


def hypercut():
    d = Diagram("hypercut-geometry-draft", 1942, 809)
    panels = [
        ("left", 34, 100, 642, [("Core 0", 34, 322), ("Core 1", 356, 320)]),
        ("middle", 744, 100, 588, [("Core 0", 744, 350), ("Core 1", 1094, 238)]),
        ("right", 1400, 100, 508, [("Core 0", 1400, 508)]),
    ]
    for key, x, y, w, cores in panels:
        d.rect(key + "-panel", x, y, w, 506, fill="#E8F5FF", gradient="#FFFFFF", stroke=BLUE, width_stroke=2)
        for j, (label, cx, cw) in enumerate(cores):
            tint = "#CCEAFE" if j == 0 else "#C9FAEF"
            d.rect(f"{key}-core-{j}", cx + 10, y + 10, cw - 18, 484, fill=tint, gradient="#FFFFFF", stroke="none", width_stroke=0, rounded=1)
            d.rect(f"{key}-head-{j}", cx + 10, y + 10, cw - 18, 85, fill=tint, gradient="#DDF7FC", stroke="none", width_stroke=0, rounded=1)
            d.text(f"{key}-core-title-{j}", label, cx + 10, y + 13, cw - 18, 75, size=46, bold=True)
    # First configuration: both consumers are on core 1.
    for key, label, x in [("a-u", "u", 108), ("a-v1", "v₁", 364), ("a-v2", "v₂", 529)]:
        node(d, key, label, x, 225, 126, 85, size=49)
    d.ellipse("a-tensor", 331, 447, 57, 57)
    for key, sx, ex in [("a-from-u", 171, 348), ("a-from-v1", 427, 360), ("a-from-v2", 592, 371)]:
        d.edge(key, sx, 310, ex, 451, color=ORANGE, width_stroke=4, arrow=False, curved=True,
               points=[((sx + ex) / 2, 405)])
    # Second configuration: one consumer moves to core 0.
    for key, label, x in [("b-u", "u", 779), ("b-v1", "v₁", 947), ("b-v2", "v₂", 1153)]:
        node(d, key, label, x, 225, 126, 85, size=49)
    d.ellipse("b-tensor", 1007, 447, 57, 57)
    for key, sx, ex in [("b-from-u", 842, 1024), ("b-from-v1", 1010, 1036), ("b-from-v2", 1216, 1048)]:
        d.edge(key, sx, 310, ex, 451, color=ORANGE, width_stroke=4, arrow=False, curved=True,
               points=[((sx + ex) / 2, 405)])
    # Third configuration: all three operators are on core 0.
    for key, label, x in [("c-u", "u", 1430), ("c-v1", "v₁", 1590), ("c-v2", "v₂", 1760)]:
        node(d, key, label, x, 225, 125, 85, size=49)
    d.ellipse("c-tensor", 1622, 447, 57, 57)
    for key, sx, ex in [("c-from-u", 1492, 1638), ("c-from-v1", 1652, 1650), ("c-from-v2", 1822, 1664)]:
        d.edge(key, sx, 310, ex, 451, color=ORANGE, width_stroke=4, arrow=False, curved=True,
               points=[((sx + ex) / 2, 405)])
    for key, cx in [("a", 358), ("b", 1034), ("c", 1649)]:
        d.rect(key + "-tensor-label-box", cx - 98, 504, 196, 76, fill="#FFF7E7", gradient="#FFFFFF", stroke=ORANGE, width_stroke=2)
        d.text(key + "-tensor-label", "t · 8 B", cx - 95, 507, 190, 70, size=45, bold=True)
    for key, x, lam, traffic, lambda_w, traffic_w, gap in [
        ("a", 93, "λₜ = 2", "16 B", 268, 235, 21),
        ("b", 754, "λₜ = 2", "16 B", 268, 235, 21),
        ("c", 1438, "λₜ = 1", "0 B", 225, 204, 18),
    ]:
        d.rect(key + "-lambda-box", x, 629, lambda_w, 83, fill="#FFF5E7", gradient="#FFFFFF", stroke=ORANGE, width_stroke=2)
        d.rect(key + "-traffic-box", x + lambda_w + gap, 629, traffic_w, 83, fill="#FFF5E7", gradient="#FFFFFF", stroke=ORANGE, width_stroke=2)
        d.text(key + "-lambda", lam, x + 8, 637, lambda_w - 16, 67, size=46, bold=True)
        d.text(key + "-traffic", traffic, x + lambda_w + gap + 6, 637, traffic_w - 12, 67, size=46, bold=True)
    for key, x in [("a-to-b", 686), ("b-to-c", 1342)]:
        d.edge(key, x, 354, x + 46, 354, color="#52647B", width_stroke=14, arrow=True)
    for key, x, y, w, _ in panels:
        d.rect(key + "-outline", x, y, w, 506, fill="none", stroke=BLUE, width_stroke=2)
    return d


def progression():
    d = Diagram("progression-geometry-draft", 1536, 1024)
    top = [("p1", 26, 102, 510, BLUE, "#E0EEFF", "问题一"),
           ("p2", 546, 102, 446, PURPLE, "#EFE2FF", "问题二"),
           ("p3", 1004, 102, 505, TEAL, "#E1F7F3", "问题三")]
    for key, x, y, w, color, tint, title in top:
        d.rect(key + "-panel", x, y, w, 447, fill="#FFFFFF", gradient=tint, stroke=color, width_stroke=2)
        d.rect(key + "-head", x + 2, y + 2, w - 4, 68, fill=tint, stroke="none", width_stroke=0)
        d.rect(key + "-foot", x + 2, 478, w - 4, 68, fill=tint, stroke="none", width_stroke=0)
        d.text(key + "-title", title, x + 12, 108, w - 24, 60, size=48, bold=True)
    d.rect("p1-sg0", 49, 188, 215, 142, fill="#FFFFFF", stroke="#82B8FF", width_stroke=2, dashed=1)
    d.rect("p1-sg5", 327, 188, 190, 142, fill="#FFFFFF", stroke="#82B8FF", width_stroke=2, dashed=1)
    d.text("p1-sg0-name", "sg0 · Core 0", 52, 196, 208, 39, size=27, bold=True)
    d.text("p1-sg5-name", "sg5 · Core 0", 329, 196, 185, 39, size=27, bold=True)
    node(d, "p1-720", "720", 70, 245, 141, 58, size=34)
    node(d, "p1-724", "724", 369, 245, 132, 58, size=34)
    for key, label, x, w in [("out", "COPY_OUT", 54, 146), ("ddr", "DDR", 229, 116), ("in", "COPY_IN", 371, 132)]:
        d.rect("p1-" + key + "-box", x, 367, w, 54, fill="#E9DFFF" if key != "ddr" else "#EDF5FF", gradient="#FFFFFF", stroke=PURPLE if key != "ddr" else INK)
        d.text("p1-" + key, label, x + 3, 372, w - 6, 44, size=27, bold=True, font="Times New Roman")
    for key, x1, y1, x2, y2 in [("p1-e1", 140, 303, 140, 367), ("p1-e2", 200, 394, 229, 394),
                                 ("p1-e3", 345, 394, 371, 394), ("p1-e4", 435, 367, 435, 303)]:
        d.edge(key, x1, y1, x2, y2, color=INK, width_stroke=3)
    d.text("p1-tensor", "t721 · 2 B", 197, 423, 145, 42, size=28, italic=True)
    d.text("p1-summary", "每个子图对应一个Task", 55, 482, 450, 57, size=33, bold=True)
    for key, x, w, color in [("p2", 564, 411, "#D9A8FF"), ("p3", 1024, 467, "#77BAFF")]:
        d.rect(key + "-task", x, 188, w, 184, fill="#FFFFFF", stroke=color, width_stroke=2, dashed=1)
        d.text(key + "-task-name", "Task · Core 0", x + 8, 195, w - 16, 44, size=28, bold=True)
    for key, x in [("p2-720", 577), ("p2-724", 847), ("p3-720", 1039), ("p3-724", 1353)]:
        node(d, key, "720" if key.endswith("720") else "724", x, 268, 119, 65, size=34)
    d.edge("p2-data", 696, 301, 847, 301, color=INK, width_stroke=3)
    d.edge("p3-data", 1158, 301, 1353, 301, color=INK, width_stroke=3)
    d.text("p2-tensor", "t721 · 2 B", 708, 259, 130, 42, size=27, italic=True)
    d.text("p3-tensor", "t721 · 2 B", 1193, 259, 134, 42, size=27, italic=True)
    d.text("p2-summary", "数据保留在这个Core中", 570, 483, 399, 54, size=31, bold=True)
    d.text("p3-summary", "增加共享只读Cache", 1030, 483, 454, 54, size=31, bold=True)
    d.rect("read-panel", 26, 579, 1483, 306, fill="#FFFFFF", gradient="#E9FBF7", stroke=TEAL, width_stroke=2)
    d.rect("read-head", 28, 581, 1479, 67, fill="#E3F8F3", stroke="none", width_stroke=0)
    d.text("read-title", "问题三的读取位置", 65, 586, 480, 55, size=43, bold=True, align="left")
    d.rect("read-in-box", 376, 723, 182, 63, fill="#EBDFFF", gradient="#FFFFFF", stroke=PURPLE)
    d.text("read-in", "COPY_IN", 387, 731, 160, 47, size=31, bold=True, font="Times New Roman")
    d.diamond("read-hit-diamond", 598, 691, 137, 132, fill="#F6F9FF", stroke=BLUE)
    d.text("read-hit", "命中？", 612, 730, 108, 46, size=28, bold=True)
    d.rect("read-cache-box", 823, 662, 230, 81, fill="#D8F6EC", gradient="#FFFFFF", stroke=TEAL)
    d.text("read-cache", "Cache\n250 B/cycle", 835, 668, 206, 68, size=29, bold=True)
    d.rect("read-ddr-box", 823, 780, 230, 80, fill="#E9F0FE", gradient="#FFFFFF", stroke=INK)
    d.text("read-ddr", "DDR\n60 B/cycle", 835, 785, 206, 69, size=29, bold=True)
    d.rect("read-store-box", 1163, 786, 306, 64, fill="#FFFFFF", stroke=PURPLE, dashed=1)
    d.text("read-store", "传输完成后放入Cache", 1170, 791, 292, 54, size=28, bold=True)
    d.edge("read-e1", 558, 755, 598, 755, color=INK)
    d.edge("read-e2", 735, 732, 823, 703, color=INK, points=[(778, 703)])
    d.edge("read-e3", 735, 782, 823, 820, color=INK, points=[(777, 820)])
    d.edge("read-e4", 1053, 820, 1163, 820, color=PURPLE, dashed=1)
    d.text("read-yes", "是", 737, 677, 43, 36, size=27, bold=True)
    d.text("read-no", "否", 737, 809, 43, 36, size=27, bold=True)
    for key, x, y, w, color, _, _ in top:
        d.rect(key + "-outline", x, y, w, 447, fill="none", stroke=color, width_stroke=2)
    d.rect("read-outline", 26, 579, 1483, 306, fill="none", stroke=TEAL, width_stroke=2)
    return d


def p1_cuts():
    # v9's actual visible area: the full PNG is trimmed 235 px from the bottom.
    d = Diagram("p1-cuts-geometry-draft", 1536, 789)
    d.rect("before-panel", 36, 45, 678, 730, fill="#FFFFFF", gradient="#EAF6FF", stroke="#AABED2", width_stroke=2)
    d.rect("after-y-panel", 811, 45, 319, 357, fill="#E7F5FF", gradient="#FFFFFF", stroke="#0082FF", width_stroke=2)
    d.rect("after-x-panel", 1140, 45, 359, 357, fill="#E3FAF4", gradient="#FFFFFF", stroke=TEAL, width_stroke=2)
    d.rect("after-j-panel", 812, 416, 687, 359, fill="#FFF0DA", gradient="#FFFFFF", stroke=ORANGE, width_stroke=2)
    for key, label, x, y, w in [
        ("before-head", "sg0 · Core 0", 65, 48, 250),
        ("after-y-head", "Y · sg0 · Core 0", 842, 48, 260),
        ("after-x-head", "X · sg6 · Core 1", 1171, 48, 290),
        ("after-j-head", "J · sg5 · Core 0", 842, 420, 235),
    ]:
        d.text(key, label, x, y, w, 46, size=31, bold=True, align="left")
    before = {710: (82, 154, 108, 72), 712: (240, 154, 108, 72),
              714: (398, 154, 108, 72), 716: (556, 154, 108, 72),
              720: (152, 305, 121, 73), 722: (469, 305, 122, 73),
              724: (304, 492, 132, 72), 726: (304, 633, 132, 72)}
    after = {710: (846, 154, 108, 72), 712: (1000, 154, 108, 72),
             714: (1188, 154, 108, 72), 716: (1348, 154, 108, 72),
             720: (908, 305, 128, 73), 722: (1256, 305, 127, 73),
             724: (1084, 492, 132, 72), 726: (1084, 633, 132, 72)}
    for prefix, coords in [("before", before), ("after", after)]:
        for op, (x, y, w, h) in coords.items():
            node(d, f"{prefix}-{op}", str(op), x, y, w, h, size=35)
        for op in [710, 712, 714, 716]:
            x, y, w, _ = coords[op]
            d.ellipse(f"{prefix}-port-{op}", x + w / 2 - 6, 103, 12, 12, fill="#33445E", stroke="#33445E", width_stroke=0)
            d.edge(f"{prefix}-port-edge-{op}", x + w / 2, 115, x + w / 2, y,
                   color="#34435B", width_stroke=3, dashed=1)
        for source, target in [(710, 720), (712, 720), (714, 722), (716, 722),
                               (720, 724), (722, 724), (724, 726)]:
            sx, sy, sw, sh = coords[source]
            tx, ty, tw, _ = coords[target]
            d.edge(f"{prefix}-dep-{source}-{target}", sx + sw / 2, sy + sh,
                   tx + tw / 2, ty, color="#273850", width_stroke=3,
                   curved=source in (720, 722),
                   points=[((sx + sw / 2 + tx + tw / 2) / 2, (sy + sh + ty) / 2)] if source in (720, 722) else ())
        x, y, w, h = coords[726]
        d.edge(f"{prefix}-port-bottom", x + w / 2, y + h, x + w / 2, 751,
               color="#34435B", width_stroke=3, dashed=1)
        d.ellipse(f"{prefix}-out-dot", x + w / 2 - 6, 750, 12, 12,
                  fill="#33445E", stroke="#33445E", width_stroke=0)
    # On the right, dependencies crossing the new subgraph boundaries are orange.
    for source in ("after-dep-720-724", "after-dep-722-724"):
        for cell in d.cells.findall("mxCell"):
            if cell.get("id") == source:
                cell.set("style", cell.get("style", "").replace("strokeColor=#273850", f"strokeColor={ORANGE}").replace("dashed=0", "dashed=1"))
    # The incoming t719 is connected to a cropped-out operator on both sides.
    for prefix, dot_x, target_x in [("before", 657, 436), ("after", 1448, 1216)]:
        d.ellipse(f"{prefix}-t719-dot", dot_x - 6, 663, 12, 12, fill="#33445E", stroke="#33445E", width_stroke=0)
        d.edge(f"{prefix}-t719-edge", dot_x, 669, target_x, 669,
               color="#34435B", width_stroke=3, dashed=1)
        d.text(f"{prefix}-t719-label", "t719 · 2 B", dot_x - 140, 623, 146, 38,
               size=29, italic=True)
    d.text("after-t721", "t721 · 2 B", 1080, 444, 150, 39, size=28, italic=True)
    d.text("after-t723", "t723 · 2 B", 1280, 444, 153, 39, size=28, italic=True)
    d.edge("before-to-after", 738, 410, 790, 410, color="#4E6177", width_stroke=14)
    return d


def framework():
    d = Diagram("framework-geometry-draft", 1448, 1086)
    d.rect("input-box", 392, 11, 664, 72, fill="#E5F0FF", gradient="#FFFFFF", stroke=INK, width_stroke=3)
    d.text("input-label", "读入计算图与固定配置", 407, 17, 634, 60, size=37, bold=True)
    columns = [
        ("p1", 25, 143, 439, BLUE, "#E0EFFF", "问题一"),
        ("p2", 481, 143, 472, PURPLE, "#F1E8FF", "问题二"),
        ("p3", 971, 143, 452, TEAL, "#E4F7F5", "问题三"),
    ]
    for key, x, y, w, color, tint, title in columns:
        d.rect(key + "-panel", x, y, w, 417, fill="#FFFFFF", gradient=tint, stroke=color, width_stroke=3)
        d.rect(key + "-head", x + 2, y + 2, w - 4, 65, fill=tint, stroke="none", width_stroke=0)
        d.text(key + "-title", title, x + 9, 150, w - 18, 56, size=41, bold=True)
        d.rect(key + "-inner", x + 18, 216, w - 36, 329, fill="#FFFFFF", stroke=color, width_stroke=2, dashed=1)
    for key, x1, y1, x2, y2, color in [
        ("to-p1", 637, 83, 245, 143, BLUE),
        ("to-p2", 724, 83, 724, 143, PURPLE),
        ("to-p3", 806, 83, 1197, 143, TEAL),
    ]:
        d.edge(key, x1, y1, x2, y2, color=color, width_stroke=3,
               points=[(x2, 108)] if x1 != x2 else ())
    d.text("p1-instruction", "拆分独立分支", 122, 220, 246, 48, size=31, bold=True)
    d.rect("p1-core0", 111, 333, 113, 166, fill="#F7F2FF", stroke="#C37EFF", dashed=1)
    d.rect("p1-core1", 263, 333, 113, 166, fill="#E9FFFF", stroke="#20C9C5", dashed=1)
    for key, x, y, fill in [("p1-top", 223, 279, "#F3F8FF"),
                            ("p1-left1", 147, 352, "#E1C7FF"), ("p1-left2", 147, 430, "#E1C7FF"),
                            ("p1-right1", 300, 352, "#BEEBFF"), ("p1-right2", 300, 430, "#BEEBFF"),
                            ("p1-bottom", 223, 496, "#F3F8FF")]:
        d.ellipse(key, x, y, 41, 41, fill=fill, stroke=INK, width_stroke=2)
    for key, x1, y1, x2, y2 in [
        ("p1-a", 243, 320, 168, 352), ("p1-b", 243, 320, 321, 352),
        ("p1-c", 168, 393, 168, 430), ("p1-d", 321, 393, 321, 430),
        ("p1-e", 168, 471, 243, 496), ("p1-f", 321, 471, 243, 496),
    ]:
        d.edge(key, x1, y1, x2, y2, color=INK, width_stroke=3)
    d.text("p1-core0-label", "Core 0", 122, 501, 110, 38, size=26)
    d.text("p1-core1-label", "Core 1", 277, 501, 110, 38, size=26)
    d.text("p2-instruction", "安排计算位置和顺序", 569, 220, 303, 48, size=31, bold=True)
    d.rect("p2-data-box", 650, 297, 150, 53, fill="#E8F2FF", stroke=INK)
    d.text("p2-data", "数据", 657, 303, 136, 41, size=29, bold=True)
    d.rect("p2-core0", 513, 409, 202, 81, fill="#F7F2FF", stroke="#C37EFF", dashed=1)
    d.rect("p2-core1", 731, 409, 193, 81, fill="#E9FFFF", stroke="#20C9C5", dashed=1)
    for i, x in enumerate([528, 594, 660, 745, 810, 875]):
        d.ellipse(f"p2-node-{i}", x, 430, 37, 37,
                  fill="#DEC7FF" if i < 3 else "#BEEBFF", stroke=INK, width_stroke=2)
    for a, b in [(0, 1), (1, 2), (3, 4), (4, 5)]:
        x1 = [528, 594, 660, 745, 810, 875][a] + 37
        x2 = [528, 594, 660, 745, 810, 875][b]
        d.edge(f"p2-chain-{a}-{b}", x1, 449, x2, 449, color=INK, width_stroke=3)
    for key, x1, x2 in [("p2-read0", 686, 613), ("p2-read1", 764, 828)]:
        d.edge(key, x1, 350, x2, 409, color=INK)
        d.text(key + "-label", "读", x2 - 15, 365, 46, 35, size=25)
    d.text("p2-core0-label", "Core 0", 566, 494, 100, 33, size=26)
    d.text("p2-core1-label", "Core 1", 790, 494, 100, 33, size=26)
    d.text("p3-instruction", "调整树状计算的顺序", 1053, 220, 284, 48, size=31, bold=True)
    tree = [("root", 1178, 302, "#F3F8FF"),
            ("left-mid", 1100, 396, "#DEC7FF"), ("right-mid", 1255, 396, "#BEEBFF"),
            ("left-a", 1069, 481, "#DEC7FF"), ("left-b", 1138, 481, "#DEC7FF"),
            ("right-a", 1217, 481, "#BEEBFF"), ("right-b", 1287, 481, "#BEEBFF")]
    for key, x, y, fill in tree:
        d.ellipse("p3-" + key, x, y, 40, 40, fill=fill, stroke=INK, width_stroke=2)
    for key, x1, y1, x2, y2 in [
        ("p3-e1", 1120, 396, 1198, 342), ("p3-e2", 1275, 396, 1198, 342),
        ("p3-e3", 1089, 481, 1120, 436), ("p3-e4", 1158, 481, 1120, 436),
        ("p3-e5", 1237, 481, 1275, 436), ("p3-e6", 1307, 481, 1275, 436),
    ]:
        d.edge(key, x1, y1, x2, y2, color=INK, width_stroke=3)
    # Shared comparison sequence. Text is still the unapproved v9 wording.
    steps = [
        ("generate", 356, 619, 736, 72, "生成完整的切分与调度方案", ORANGE, "#FFF1D7"),
        ("check", 415, 713, 617, 63, "检查操作覆盖与执行顺序", INK, "#E7F1FF"),
        ("bound", 415, 794, 617, 63, "依据下界排除不可能更快的方案　适用时", INK, "#E7F1FF"),
        ("evaluate", 415, 877, 617, 66, "完整评价并比较完成时间", INK, "#E7F1FF"),
        ("output", 415, 961, 617, 82, "输出最佳合法方案", BLUE, "#D9ECFF"),
    ]
    for key, x, y, w, h, label, stroke, fill in steps:
        d.rect(key + "-box", x, y, w, h, fill=fill, gradient="#FFFFFF", stroke=stroke, width_stroke=3)
        d.text(key + "-label", label, x + 12, y + 7, w - 24, h - 14, size=32, bold=True)
    for key, x1, x2, color in [("p1-merge", 245, 640, BLUE),
                               ("p2-merge", 724, 724, PURPLE),
                               ("p3-merge", 1197, 806, TEAL)]:
        d.edge(key, x1, 560, x2, 619, color=color, width_stroke=3,
               points=[(x1, 573)] if x1 != x2 else ())
    for key, y1, y2 in [("step1", 691, 713), ("step2", 776, 794),
                        ("step3", 857, 877), ("step4", 943, 961)]:
        d.edge("shared-" + key, 724, y1, 724, y2, color="#667287", width_stroke=3)
    for key, x, y, w, color, _, _ in columns:
        d.rect(key + "-outline", x, y, w, 417, fill="none", stroke=color, width_stroke=3)
    return d


def fang_fork():
    # The confirmed A PNG has a horizontal composition unlike its earlier Draw.io source.
    d = Diagram("fang-fork-geometry-draft", 1536, 1024)
    d.rect("background", 0, 0, 1536, 1024, fill="#627083", gradient="#E8F9FF",
           stroke="none", width_stroke=0, rounded=0)
    d.rect("top-haze-left", 0, 0, 760, 622, fill="#3E4859", gradient="#EDF4F8",
           stroke="none", width_stroke=0, rounded=0, opacity=65)
    d.rect("top-haze-right", 766, 0, 770, 622, fill="#555C68", gradient="#ECF6F2",
           stroke="none", width_stroke=0, rounded=0, opacity=58)

    def graph_node(key, label, x, y, w=134, h=47, *, group="plain"):
        palette = {
            "plain": ("#EFF3F6", "#536984"),
            "branch": ("#DFF9E8", "#009C5B"),
            "tail": ("#FFF0D9", "#F36D00"),
        }
        fill, stroke = palette[group]
        d.rect(key + "-box", x, y, w, h, fill=fill, gradient="#FFFFFF", stroke=stroke, width_stroke=2, arc=9)
        d.text(key + "-label", label, x + 4, y + 1, w - 8, h - 2,
               size=29, bold=True, font="Times New Roman")

    left = {
        "s": (317, 33), "a": (317, 118), "b1": (85, 203), "b2": (327, 203),
        "b3": (563, 203), "c1": (85, 282), "d2": (327, 282),
        "c3": (563, 282), "d1": (85, 361), "d3": (563, 361),
        "r": (317, 454), "t": (317, 540),
    }
    right = {
        "s": (1088, 29), "a": (1088, 115), "b1": (853, 205),
        "b2": (1075, 205), "b3": (1335, 205), "c1": (853, 283),
        "d2": (1075, 283), "c3": (1335, 283), "d1": (853, 363),
        "d3": (1335, 363), "r": (1085, 453), "t": (1085, 540),
    }
    for prefix, positions in [("before", left), ("after", right)]:
        for label, (x, y) in positions.items():
            group = "branch" if prefix == "after" and label.startswith(("b", "c", "d")) else "tail" if prefix == "after" and label in ("r", "t") else "plain"
            graph_node(f"{prefix}-{label}", label, x, y, 122 if label.startswith(("b", "c", "d")) else 134,
                       group=group)
        for a, b in [("s", "a"), ("a", "b1"), ("a", "b2"), ("a", "b3"),
                     ("b1", "c1"), ("c1", "d1"), ("b2", "d2"),
                     ("b3", "c3"), ("c3", "d3"), ("d1", "r"),
                     ("d2", "r"), ("d3", "r"), ("r", "t")]:
            ax, ay = positions[a]; bx, by = positions[b]
            aw = 122 if a.startswith(("b", "c", "d")) else 134
            bw = 122 if b.startswith(("b", "c", "d")) else 134
            d.edge(f"{prefix}-{a}-{b}", ax + aw / 2, ay + 47, bx + bw / 2, by,
                   color="#425A78", width_stroke=3,
                   curved=(a == "a" and b != "b2") or (b == "r" and a != "d2"),
                   points=[((ax + aw / 2 + bx + bw / 2) / 2, (ay + 47 + by) / 2)]
                   if ((a == "a" and b != "b2") or (b == "r" and a != "d2")) else ())

    # Task and stage groupings in the confirmed A raster, independent of the prior Draw.io layout.
    for key, x, w in [("branch1", 835, 159), ("branch2", 1076, 158), ("branch3", 1320, 157)]:
        d.rect(key + "-group", x, 190, w, 238, fill="#DDF9EC", stroke="#00A45E",
               width_stroke=2, dashed=1, opacity=68, arc=9)
    d.rect("tail-group", 1059, 439, 189, 161, fill="#FFF0D9", stroke="#F37300",
           width_stroke=2, dashed=1, opacity=65, arc=9)
    d.text("stage0", "阶段 0", 835, 55, 95, 39, size=30, bold=True)
    d.text("stage1", "阶段 1", 726, 340, 100, 39, size=30, bold=True)

    rows = [("core0", 633, "Core 0"), ("core1", 733, "Core 1"), ("core2", 833, "Core 2")]
    for key, y, label in rows:
        d.rect(key + "-row", 34, y, 1469, 94, fill="#EAF6FF", gradient="#FFFFFF",
               stroke="#55C5FF", width_stroke=2, arc=5)
        d.text(key + "-label", label, 48, y + 19, 134, 57, size=30, bold=True,
               font="Times New Roman", align="left")
    d.text("core-count", "K = 3", 1416, 615, 80, 37, size=31, bold=True,
           font="Times New Roman", fill="#FFFFFF")
    tasks = [
        ("task0", "Task 0\ns → a", 191, 646, 279, 70, "#E7EBF0", "#7C8FA4"),
        ("task1", "Task 1\nb1 → c1 → d1", 644, 646, 264, 70, "#DDF8E7", "#00A05D"),
        ("task2", "Task 2\nb2 → d2", 644, 747, 267, 70, "#DDF8E7", "#00A05D"),
        ("task3", "Task 3\nb3 → c3 → d3", 644, 847, 267, 70, "#DDF8E7", "#00A05D"),
        ("task4", "Task 4\nr → t", 1145, 747, 269, 70, "#FFF0D8", "#F06B00"),
    ]
    for key, label, x, y, w, h, fill, stroke in tasks:
        d.rect(key + "-box", x, y, w, h, fill=fill, gradient="#FFFFFF",
               stroke=stroke, width_stroke=2, arc=8)
        d.text(key + "-label", label, x + 4, y + 3, w - 8, h - 6,
               size=26, bold=True, font="Times New Roman")
    d.edge("core0-order", 470, 681, 644, 681, color="#158CCB", width_stroke=3)
    d.edge("core1-order", 911, 782, 1145, 782, color="#158CCB", width_stroke=3)
    for key, x1, y1, x2, y2, points in [
        ("task0-to-task2", 470, 686, 644, 781, [(550, 710)]),
        ("task0-to-task3", 470, 697, 644, 882, [(568, 742)]),
        ("task1-to-task4", 908, 681, 1255, 747, [(1115, 711)]),
        ("task3-to-task4", 911, 882, 1255, 817, [(1130, 863)]),
    ]:
        d.edge(key, x1, y1, x2, y2, color="#F36B00", width_stroke=2,
               dashed=1, curved=True, points=points)
    d.rect("legend-box", 347, 941, 842, 60, fill="#FFFFFF", stroke="#ADBDCD", width_stroke=2, arc=5)
    d.edge("legend-order", 380, 971, 474, 971, color="#163C66", width_stroke=3)
    d.text("legend-order-label", "同一 Core 内的 Task 顺序", 486, 950, 261, 43, size=23, bold=True)
    d.text("legend-divider", "│", 745, 950, 24, 43, size=28)
    d.edge("legend-dependency", 776, 971, 867, 971, color="#F36B00", width_stroke=2, dashed=1)
    d.text("legend-dependency-label", "跨 Core 的数据依赖（经 DDR）", 874, 950, 291, 43, size=22, bold=True)
    return d


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("figures", nargs="*", choices=["hypercut", "progression", "p1_cuts", "framework", "fang_fork"])
    args = parser.parse_args()
    chosen = args.figures or ["hypercut", "progression", "p1_cuts", "framework", "fang_fork"]
    for name in chosen:
        print(globals()[name]().write())


if __name__ == "__main__":
    main()
