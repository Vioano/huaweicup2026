import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { computeLayout, inspectGeometry, toDrawio, validateGraph } from '../scripts/drawio.mjs';

const fixture = JSON.parse(await fs.readFile(new URL('../examples/modeling-workflow.json', import.meta.url)));
test('branched workflow preserves labels, endpoints and reproducible nonoverlapping geometry', async () => {
  const layout = await computeLayout(fixture);
  assert.deepEqual(inspectGeometry(layout), []);
  assert.deepEqual(layout.nodes.map(n => [n.id, n.label]), fixture.nodes.map(n => [n.id, n.label]));
  assert.deepEqual(layout.edges.map(e => [e.id, e.source, e.target]), fixture.edges.map(e => [e.id, e.source, e.target]));
  assert.deepEqual(await computeLayout(fixture), layout);
});
test('XML roundtrip preserves special characters and actual source/target connections', async () => {
  const graph = structuredClone(fixture);
  graph.nodes[0].label = 'α < β & "测量"\n单位：m';
  const document = toDrawio(await computeLayout(graph));
  const parsed = spawnSync('python3', ['-c', 'import sys,json,xml.etree.ElementTree as ET;r=ET.fromstring(sys.stdin.read());print(json.dumps([c.attrib for c in r.iter("mxCell")]))'], {input: document, encoding:'utf8'});
  assert.equal(parsed.status, 0, parsed.stderr);
  const cells = JSON.parse(parsed.stdout);
  assert.equal(cells.find(c => c.id === 'data').value, graph.nodes[0].label);
  for (const edge of graph.edges) {
    const cell = cells.find(c => c.id === edge.id);
    assert.equal(cell.source, edge.source);
    assert.equal(cell.target, edge.target);
  }
});
test('bad endpoints, duplicate IDs and unsupported labels fail before layout', () => {
  for (const mutate of [
    g => { g.edges[0].target = 'missing'; },
    g => { g.nodes[1].id = g.nodes[0].id; },
    g => { g.edges[0].id = g.nodes[0].id; },
    g => { g.nodes[0].label = '\u0001'; },
    g => { g.edges[0].label = 'must not silently disappear'; },
  ]) {
    const graph = structuredClone(fixture); mutate(graph);
    assert.throws(() => validateGraph(graph));
  }
});
test('undersized labels fail instead of silently shrinking or clipping text', async () => {
  const graph = structuredClone(fixture); graph.nodes[0].width = 20;
  await assert.rejects(computeLayout(graph), /too small/);
});
test('geometry audit detects node overlap, detached endpoints and routes through boxes', async () => {
  const layout = await computeLayout(fixture);
  const overlap = structuredClone(layout);
  overlap.nodes[1].x = overlap.nodes[0].x; overlap.nodes[1].y = overlap.nodes[0].y;
  assert.ok(inspectGeometry(overlap).some(x => x.startsWith('Node overlap')));
  const detached = structuredClone(layout); detached.edges[0].points[0].x += 500;
  assert.ok(inspectGeometry(detached).some(x => x.startsWith('Detached route')));
  const through = {width: 500, height: 200, nodes: [
    {id:'s', x:0, y:0, width:100, height:100}, {id:'middle',x:150,y:0,width:100,height:100}, {id:'t',x:300,y:0,width:100,height:100},
  ], edges:[{id:'e',source:'s',target:'t',points:[{x:100,y:50},{x:300,y:50}]}]};
  assert.ok(inspectGeometry(through).some(x => x.includes('Route through node e/middle')));
});
test('CLI handles paths with spaces and refuses to overwrite any existing output', async t => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'figure test '));
  t.after(() => fs.rm(temp, {recursive:true, force:true}));
  const input = path.join(temp, 'source.json'), output = path.join(temp, 'new figure.drawio');
  const inputText = JSON.stringify(fixture);
  await fs.writeFile(input, inputText);
  const cli = fileURLToPath(new URL('../scripts/drawio.mjs', import.meta.url));
  const run = () => spawnSync(process.execPath, [cli, input, output], {encoding:'utf8'});
  assert.equal(run().status, 0);
  const existing = await fs.readFile(output, 'utf8');
  assert.notEqual(run().status, 0);
  assert.equal(await fs.readFile(output, 'utf8'), existing);
  assert.equal(await fs.readFile(input, 'utf8'), inputText);
  await fs.unlink(output);
  assert.notEqual(run().status, 0); // An existing sidecar also protects the bundle.
  await assert.rejects(fs.access(output));
});
