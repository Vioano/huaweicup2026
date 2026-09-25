"""Small exact-arithmetic mechanism fixtures; not official case scores."""
from fractions import Fraction as F
from math import ceil
import unittest

from analyze import longest


def prefix_fixture(flows, extra):
    """Rational fair sharing with rounded retirement; no evaluator imports."""
    rem, ends, cursor, done = {}, {}, dict.fromkeys(flows, 0), {}
    now = last = 0
    extra = list(extra)
    seen_extra = set()
    def project():
        items = sorted((work, item) for item, work in rem.items())
        t, prev, n, i = F(now), F(0), len(items), 0
        while i < len(items):
            work = items[i][0]
            t += (work-prev)*n
            j=i
            while j<len(items) and items[j][0]==work:
                ends[items[j][1]]=ceil(t); j+=1
            n-=j-i; prev=work; i=j
    for _ in range(100):
        elapsed=F(now-last)
        while elapsed:
            active=[u for u,w in rem.items() if w>0]
            if not active: break
            first=min(rem[u] for u in active)*len(active)
            dt=min(elapsed,first)
            for u in active: rem[u]-=dt/len(active)
            elapsed-=dt
        last=now
        for u in list(ends):
            if ends[u] <= now:
                del ends[u];del rem[u]
                if u[0] in flows:
                    cursor[u[0]]+=1
                    if cursor[u[0]]==len(flows[u[0]]): done[u[0]]=now
        project()
        for name,word in flows.items():
            if name not in done and not any(u[0]==name for u in rem):
                rem[(name,cursor[name])]=F(word[cursor[name]])
                project()
        for i,(arrival,work) in enumerate(extra):
            if arrival<=now and i not in seen_extra:
                rem[('extra',i)]=F(work);seen_extra.add(i);project()
        if len(done)==len(flows): return done
        nxt=list(ends.values())+[a for i,(a,_) in enumerate(extra) if i not in seen_extra]
        next_now=min(nxt)
        assert next_now>now
        now=next_now
    raise AssertionError('fixture budget exceeded')


class MathTests(unittest.TestCase):
    def test_realized_path(self):
        e={(0,1):{'lag':5},(1,2):{'lag':0}}
        total,starts,path=longest({0,1,2},e,{0:2,1:3,2:4})
        self.assertEqual((total,starts,path),(14,{0:0,1:7,2:10},[0,1,2]))

    def test_finish_floor_does_not_forge_start(self):
        total,starts,path=longest({0,1},{(0,1):{'lag':0}},{0:2,1:3},{0:10})
        self.assertEqual(total,13)
        self.assertEqual(starts,{0:0,1:10})

    def test_cycle_fails(self):
        with self.assertRaises(ValueError):
            longest({0,1},{(0,1):{'lag':0},(1,0):{'lag':0}},{0:1,1:1})

    def test_naive_fair_prefix_formula_is_false(self):
        flows={'A':[4,1],'B':[1,1,3,2],'C':[2],'D':[1,1,4]}
        done=prefix_fixture(flows,[(1,1)])
        naive=sum(min(sum(flows['A']),sum(x)) for x in flows.values())
        corrected=sum(flows['A'])+sum(min(sum(w),max(0,sum(flows['A'])-(len(w)-1))) for k,w in flows.items() if k!='A')
        self.assertEqual(done['A'],16)
        self.assertEqual(naive,17)
        self.assertEqual(corrected,12)
        self.assertLessEqual(corrected,done['A'])

if __name__=='__main__':
    unittest.main()
