// Adapted from the ELK prototype in 精算云画图/引擎测试; see docs/FIGURE_SKILLS_RESEARCH.md.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import ELK from 'elkjs';

const palette = {
  data: ['#E8F1F8', '#0072B2'],
  model: ['#E4F3EE', '#007F64'],
  check: ['#FFF2DD', '#A36600'],
  output: ['#F1EAF5', '#805A8D'],
};
const xml = value => String(value).replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
}[c])).replace(/\n/g, '&#10;');
const finite = n => typeof n === 'number' && Number.isFinite(n) && n > 0;
function fields(object, allowed, context) {
  if (!object || typeof object !== 'object' || Array.isArray(object)) throw Error(`${context}: expected object`);
  for (const key of Object.keys(object)) {
    if (!allowed.includes(key)) throw Error(`${context}: unsupported field ${key}`);
  }
}
function text(value, context) {
  if (typeof value !== 'string' || !value.trim() || /[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/u.test(value)) {
    throw Error(`${context}: expected nonempty XML-safe text`);
  }
}

export function validateGraph(graph) {
  fields(graph, ['title', 'direction', 'nodes', 'edges'], 'graph');
  text(graph.title, 'title');
  if (graph.direction !== undefined && !['RIGHT', 'DOWN', 'LEFT', 'UP'].includes(graph.direction)) throw Error('Invalid direction');
  if (!Array.isArray(graph.nodes) || !graph.nodes.length || !Array.isArray(graph.edges)) throw Error('Provide nodes and edges arrays');
  const ids = new Set(['0', '1']);
  function id(value) {
    if (typeof value !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]*$/.test(value) || ids.has(value)) {
      throw Error(`Invalid or duplicate id: ${value}`);
    }
    ids.add(value);
  }
  for (const node of graph.nodes) {
    fields(node, ['id', 'label', 'role', 'width', 'height'], 'node');
    id(node.id);
    text(node.label, node.id);
    if (node.role !== undefined && !Object.hasOwn(palette, node.role)) throw Error(`Unknown role: ${node.role}`);
    for (const key of ['width', 'height']) {
      if (node[key] !== undefined && !finite(node[key])) throw Error(`${node.id}: invalid ${key}`);
    }
  }
  const nodeIds = new Set(graph.nodes.map(n => n.id));
  for (const edge of graph.edges) {
    fields(edge, ['id', 'source', 'target'], 'edge');
    id(edge.id);
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) throw Error(`Unknown endpoint: ${edge.id}`);
  }
}

// Conservative estimate only; actual font metrics must be checked in the exported preview.
function size(node) {
  const lines = node.label.split('\n');
  const units = s => [...s].reduce((sum, c) => sum + (c.codePointAt(0) > 255 ? 1 : 0.62), 0);
  const width = Math.max(176, Math.ceil(Math.max(...lines.map(units)) * 16 + 40));
  const height = Math.max(64, lines.length * 24 + 28);
  if ((node.width && node.width < width) || (node.height && node.height < height)) {
    throw Error(`${node.id}: box too small for conservative text estimate; increase size or add line breaks`);
  }
  return { width: node.width ?? width, height: node.height ?? height };
}

export async function computeLayout(graph) {
  validateGraph(graph);
  const engine = new ELK();
  const result = await engine.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': graph.direction ?? 'RIGHT',
      'elk.edgeRouting': 'ORTHOGONAL',
      'elk.spacing.nodeNode': '40',
      'elk.layered.spacing.nodeNodeBetweenLayers': '64',
      'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
      'elk.layered.nodePlacement.bk.fixedAlignment': 'BALANCED',
      'elk.randomSeed': '2026',
      'elk.padding': '[top=28,left=28,bottom=28,right=28]',
    },
    children: graph.nodes.map(node => ({ id: node.id, ...size(node) })),
    edges: graph.edges.map(edge => ({ id: edge.id, sources: [edge.source], targets: [edge.target] })),
  });
  const sourceNodes = new Map(graph.nodes.map(n => [n.id, n]));
  const sourceEdges = new Map(graph.edges.map(e => [e.id, e]));
  const nodes = result.children.map(({id, x, y, width, height}) => ({ ...sourceNodes.get(id), id, x, y, width, height }));
  const edges = result.edges.map(edge => {
    if (edge.sections?.length !== 1) throw Error(`${edge.id}: expected one routed section`);
    const section = edge.sections[0];
    return { ...sourceEdges.get(edge.id), points: [section.startPoint, ...(section.bendPoints ?? []), section.endPoint] };
  });
  const layout = { title: graph.title, engine: 'elkjs 0.10.0 layered', width: result.width, height: result.height, nodes, edges };
  const defects = inspectGeometry(layout);
  if (defects.length) throw Error(`Layout validation failed: ${defects.join('; ')}`);
  return layout;
}

export function inspectGeometry(layout) {
  const defects = [];
  const eps = 0.01;
  for (const [i, a] of layout.nodes.entries()) {
    if (![a.x, a.y, a.width, a.height].every(Number.isFinite)) defects.push(`Invalid geometry ${a.id}`);
    if (a.x < 0 || a.y < 0 || a.x + a.width > layout.width + eps || a.y + a.height > layout.height + eps) defects.push(`Outside page ${a.id}`);
    for (const b of layout.nodes.slice(i + 1)) {
      if (a.x < b.x + b.width - eps && a.x + a.width > b.x + eps && a.y < b.y + b.height - eps && a.y + a.height > b.y + eps) defects.push(`Node overlap ${a.id}/${b.id}`);
    }
  }
  const byId = new Map(layout.nodes.map(n => [n.id, n]));
  const onBoundary = (p, r) => p.x >= r.x - eps && p.x <= r.x + r.width + eps && p.y >= r.y - eps && p.y <= r.y + r.height + eps &&
    (Math.abs(p.x - r.x) < eps || Math.abs(p.x - r.x - r.width) < eps || Math.abs(p.y - r.y) < eps || Math.abs(p.y - r.y - r.height) < eps);
  for (const edge of layout.edges) {
    const source = byId.get(edge.source), target = byId.get(edge.target);
    if (!source || !target || edge.points.length < 2) { defects.push(`Missing endpoint ${edge.id}`); continue; }
    if (!onBoundary(edge.points[0], source) || !onBoundary(edge.points.at(-1), target)) defects.push(`Detached route ${edge.id}`);
    for (let i = 1; i < edge.points.length; i++) {
      const a = edge.points[i - 1], b = edge.points[i];
      if (![a.x, a.y, b.x, b.y].every(Number.isFinite)) defects.push(`Invalid route ${edge.id}`);
      if (Math.abs(a.x - b.x) > eps && Math.abs(a.y - b.y) > eps) defects.push(`Non-orthogonal route ${edge.id}`);
      for (const n of layout.nodes) {
        const horizontal = Math.abs(a.y - b.y) < eps && a.y > n.y + eps && a.y < n.y + n.height - eps && Math.max(a.x, b.x) > n.x + eps && Math.min(a.x, b.x) < n.x + n.width - eps;
        const vertical = Math.abs(a.x - b.x) < eps && a.x > n.x + eps && a.x < n.x + n.width - eps && Math.max(a.y, b.y) > n.y + eps && Math.min(a.y, b.y) < n.y + n.height - eps;
        if (horizontal || vertical) defects.push(`Route through node ${edge.id}/${n.id}`);
      }
    }
  }
  return defects;
}

export function toDrawio(layout) {
  const nodes = new Map(layout.nodes.map(n => [n.id, n]));
  const cells = layout.nodes.map(n => {
    const [fill, stroke] = palette[n.role ?? 'model'];
    const style = `rounded=1;whiteSpace=wrap;html=0;fillColor=${fill};strokeColor=${stroke};strokeWidth=1.5;fontFamily=Arial;fontSize=16;fontColor=#202A35;spacing=12;`;
    return `<mxCell id="${xml(n.id)}" value="${xml(n.label)}" style="${style}" vertex="1" parent="1"><mxGeometry x="${n.x}" y="${n.y}" width="${n.width}" height="${n.height}" as="geometry"/></mxCell>`;
  });
  for (const e of layout.edges) {
    const s = nodes.get(e.source), t = nodes.get(e.target), a = e.points[0], b = e.points.at(-1);
    const anchor = (p, n, axis) => (p[axis] - n[axis]) / n[axis === 'x' ? 'width' : 'height'];
    const style = `edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;strokeColor=#46515C;strokeWidth=1.5;exitX=${anchor(a,s,'x')};exitY=${anchor(a,s,'y')};exitPerimeter=0;entryX=${anchor(b,t,'x')};entryY=${anchor(b,t,'y')};entryPerimeter=0;`;
    const points = e.points.slice(1, -1).map(p => `<mxPoint x="${p.x}" y="${p.y}"/>`).join('');
    cells.push(`<mxCell id="${xml(e.id)}" source="${xml(e.source)}" target="${xml(e.target)}" style="${style}" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><Array as="points">${points}</Array></mxGeometry></mxCell>`);
  }
  return `<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="huaweicup2026" version="1"><diagram id="figure" name="${xml(layout.title)}"><mxGraphModel page="1" pageScale="1" pageWidth="${Math.ceil(layout.width)}" pageHeight="${Math.ceil(layout.height)}" background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>${cells.join('\n')}</root></mxGraphModel></diagram></mxfile>\n`;
}

async function main() {
  const [input, output, ...rest] = process.argv.slice(2);
  if (!input || !output || rest.length || path.extname(output) !== '.drawio') {
    throw Error('Usage: node scripts/drawio.mjs INPUT.json OUTPUT.drawio (new output paths only)');
  }
  const raw = await fs.readFile(input);
  const layout = await computeLayout(JSON.parse(raw));
  const prefix = output.slice(0, -7);
  const files = new Map([
    [output, toDrawio(layout)],
    [`${prefix}.layout.json`, JSON.stringify(layout, null, 2) + '\n'],
    [`${prefix}.qa.json`, JSON.stringify({
      inputSha256: createHash('sha256').update(raw).digest('hex'),
      engine: layout.engine, nodeCount: layout.nodes.length, edgeCount: layout.edges.length,
      geometryDefects: [], visualReview: 'pending',
      limits: 'Font rendering, edge crossings, meaning and final-size legibility require visual review.',
    }, null, 2) + '\n'],
  ]);
  // Reserve all outputs before writing, preserving existing work if any path collides.
  const opened = [];
  try {
    await fs.mkdir(path.dirname(output), { recursive: true });
    for (const filename of files.keys()) opened.push([filename, await fs.open(filename, 'wx')]);
    for (const [filename, handle] of opened) await handle.writeFile(files.get(filename));
  } catch (error) {
    for (const [filename, handle] of opened) { await handle.close(); await fs.unlink(filename); }
    throw error;
  }
  for (const [, handle] of opened) await handle.close();
  console.log(JSON.stringify({ output, nodes: layout.nodes.length, edges: layout.edges.length, visualReview: 'pending' }));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
