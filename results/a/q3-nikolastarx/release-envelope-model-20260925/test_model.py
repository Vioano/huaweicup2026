"""Finite exact model checks; no official code, candidate scoring or resources."""
import unittest
from model import signature,value,direct,uniformly_no_slower


class ReleaseModelTests(unittest.TestCase):
    def test_independent_event_recurrence(self):
        fixtures=[([1,8,1],[0,2,0],[None,None,'a'],3),
                  ([1,1,8],[0,0,2],[None,'a',None],3),
                  ([1,1],[0,1],['a','b'],2),
                  ([3,2,7,1],[4,0,5,2],[None,'a','b','a'],9),
                  ([],[],[],5)]
        count=0
        for work,uses,keys,c in fixtures:
            sig=signature(work,uses,keys,c)
            for a,b in ((0,0),(1,10),(10,1),(100,100)):
                releases={k:{'a':a,'b':b}[k] for k in sig['lags']}
                self.assertEqual(value(sig,releases),direct(work,uses,keys,c,releases))
                count+=1
        self.assertEqual(count,20)

    def test_partial_and_full_are_incomparable(self):
        full=signature([1,8,1],[0,2,0],[None,None,'a'],3)
        partial=signature([1,1,8],[0,0,2],[None,'a',None],3)
        self.assertEqual(full,{'base':13,'lags':{'a':4}})
        self.assertEqual(partial,{'base':11,'lags':{'a':10}})
        self.assertFalse(uniformly_no_slower(full,partial))
        self.assertFalse(uniformly_no_slower(partial,full))
        self.assertLess(value(partial,{'a':1}),value(full,{'a':1}))
        self.assertGreater(value(partial,{'a':10}),value(full,{'a':10}))

    def test_midchain_release_changes_answer(self):
        sig=signature([1,1],[0,1],['a','b'],2)
        self.assertEqual(value(sig,{'a':0,'b':0}),3)
        self.assertEqual(value(sig,{'a':0,'b':100}),102)

    def test_dominance_and_domain(self):
        a={'base':8,'lags':{'x':3,'y':4}}
        b={'base':9,'lags':{'x':3,'y':5}}
        self.assertTrue(uniformly_no_slower(a,b))
        self.assertFalse(uniformly_no_slower(b,a))
        with self.assertRaises(ValueError):
            uniformly_no_slower(a,{'base':8,'lags':{'x':3}})
        with self.assertRaises(ValueError):
            value(a,{'x':0})


if __name__=='__main__':
    unittest.main()
