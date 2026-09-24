"""Original-operation island boundaries, including raw COPY_OUT exits."""
import unittest

from src.q3.attention_islands import extract
from src.q3.attention_rows import _ports, _recognize
from src.q3.construct import Index, UnsupportedStructure
from tests.q3.test_attention_rows import GraphBuilder, attention_ffn_graph, attention_graph


def three_lane_graph():
    """A three-leaf original numerator: ADD(ADD(weighted0, weighted1), weighted2)."""
    builder = GraphBuilder()
    vector, weight, scalar = builder.source(), builder.source(), builder.source(2)
    front = [builder.op("MATMUL", "PIPE_M", 2, [vector, weight], pos="L1")
             for _ in range(7)]
    q, *kv = front
    ks, vs = kv[:3], kv[3:]

    def op(kind, inputs, pipe="PIPE_V", size=64):
        return builder.op(kind, pipe, 2, inputs, size=size,
                          pos="L1" if pipe == "PIPE_M" else "UB")

    scores = [op("DIV", [op("MATMUL", [q[1], k[1]], "PIPE_M")[1], scalar])
              for k in ks]
    red = [op("REDUCE", [s[1]], size=16) for s in scores]
    def maximum(a, b):
        delta = op("SUB", [a[1], b[1]], size=16)
        relu = op("RELU", [delta[1]], size=16)
        return op("ADD", [b[1], relu[1]], size=16)
    max_root = maximum(maximum(red[0], red[1]), red[2])
    exps = [op("EXP", [op("SUB", [s[1], max_root[1]])[1]]) for s in scores]
    reductions = [op("REDUCE", [e[1]], size=16) for e in exps]
    denominator = op("ADD", [op("ADD", [reductions[0][1], reductions[1][1]], size=16)[1],
                             reductions[2][1]], size=16)
    weighted = [op("MATMUL", [e[1], v[1]], "PIPE_M") for e, v in zip(exps, vs)]
    inner = op("ADD", [weighted[0][1], weighted[1][1]])
    numerator = op("ADD", [inner[1], weighted[2][1]])
    sink = op("DIV", [numerator[1], denominator[1]])
    builder.op("COPY_OUT", "PIPE_MTE3", 0, [sink[1]], pos="DDR")
    return builder, sink[0], weighted[0][0]


class AttentionIslandTests(unittest.TestCase):
    def test_numerator_children_are_unchanged_single_operation_islands(self):
        builder, expected = attention_graph()
        graph = builder.graph
        ops_before = [dict(op) for op in graph["ops"]]
        index = Index(graph)
        ports = _ports(index)
        blocks = extract(index, ports, _recognize(index, ports))
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        self.assertEqual(block["kind"], "attention_row")
        self.assertEqual(block["sink"], expected["sink"])
        self.assertEqual(block["nodes"], tuple(u for u in index.order if u in expected["nodes"]))
        numerator = next(p for p in index.pred[expected["sink"]]
                         if index.pred[p] == {island[0] for island in block["islands"]})
        self.assertEqual(block["islands"], tuple((u,) for u in index.order
                                                 if u in index.pred[numerator]))
        self.assertTrue(all(index.ops[island[0]]["op"] == "MATMUL"
                            for island in block["islands"]))
        self.assertEqual(graph["ops"], ops_before)

    def test_raw_copy_out_from_nonroot_rejects_row(self):
        builder, sink, leaf = three_lane_graph()
        index = Index(builder.graph)
        ports = _ports(index)
        rows = _recognize(index, ports)
        original = extract(index, ports, rows)[0]
        self.assertTrue(any(leaf in island[:-1] for island in original["islands"]))
        output = next(iter(ports.outputs[leaf]))
        builder.op("COPY_OUT", "PIPE_MTE3", 0, [output], pos="DDR")
        changed = Index(builder.graph)
        with self.assertRaisesRegex(UnsupportedStructure, f"attention row {sink} rejected"):
            extract(changed, _ports(changed), rows)

    def test_ffn_island_is_only_tail_matmul_and_blocks_are_disjoint(self):
        builder, _, diamonds = attention_ffn_graph(2)
        index = Index(builder.graph)
        ports = _ports(index)
        blocks = extract(index, ports, _recognize(index, ports))
        self.assertEqual([block["kind"] for block in blocks], ["attention_row", "ffn", "ffn"])
        self.assertEqual([block["islands"] for block in blocks[1:]],
                         [((diamond[-1][0],),) for diamond in diamonds])
        self.assertEqual([block["sink"] for block in blocks[1:]],
                         [diamond[-1][0] for diamond in diamonds])
        all_nodes = [u for block in blocks for u in block["nodes"]]
        self.assertEqual(len(all_nodes), len(set(all_nodes)))
        for block, diamond in zip(blocks[1:], diamonds):
            self.assertEqual(block["nodes"],
                             tuple(u for u in index.order if u in {op[0] for op in diamond}))


if __name__ == "__main__":
    unittest.main()
