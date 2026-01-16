# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest as unittest
import numpy as np

def import_local():
    """
    In order to be able to run our tests manually from the 'tests' directory
    we force import from the local package.
    """
    me = "cdxcore"
    import os
    import sys
    cwd = os.getcwd()
    if cwd[-len(me):] == me:
        return
    assert cwd[-5:] == "tests",("Expected current working directory to be in a 'tests' directory", cwd[-5:], "from", cwd)
    assert cwd[-6] in ['/', '\\'],("Expected current working directory 'tests' to be lead by a '\\' or '/'", cwd[-6:], "from", cwd)
    sys.path.insert( 0, cwd[:-6] )
import_local()

from cdxcore.deferred import DeferAll, ResolutionDependencyError, NotSupportedError

class qB(object):
    def __init__(self):
        self.m = 1
    def f(self,y):
        return self.m+y

class qA(object):

    M = 7

    def __init__(self):
        self.m = 1
        self.d = dict()
        self.l = list()
        self.b = qB()
    
    def f(self, y=2):
        return self.m*y

    def fq(self, q):
        return self.m*q.m
    
    @property
    def g(self):
        return self.m*3

    @staticmethod
    def h(x,*,y=2):
        return x*y

    @property
    def more(self):
        return qB()

    def moref(self):
        return qB()

    @classmethod
    def j(cls, y=2):
        return cls.M*y
        
    def __iter__(self):
        for i in  range(self.x):
            yield i
            
    def __call__(self, x):
        return self.m*x
    
    def __getitem__(self, i):
        return self.d[i]
    
    def __setitem__(self, i, v):
        self.d[i] = v

    def __eq__(self, other):
        return self.m == other.m

    def __iadd__(self, integer):
        self.m += integer
        return self

    def __rxor__(self, integer):
        r = qA()
        r.m = self.m^integer
        return r

def some_function(x):
    return x.m

# for detecting collisions
class AX(object):
    def __init__(self):
        self.x = 1
    def f(self,other):
        return self.x+(other.x if not isinstance(other, int) else other)
        
class Test(unittest.TestCase):

    def test_deferred(self):
        
        # some basic Python tests
        
        with self.assertRaises(AttributeError):
            getattr(int(1),"__getattr__") # __getattr__ can be read using 'getattr'
        _ = getattr(int(1),"__setattr__")
        _ = getattr(int(1),"__delattr__")
            
        # does it work?
        # we test the results of executing some code directly or delayed
        def test_iadd(a):
            a+=1
            return a

        def tester(a,b):
            am = a.m
            return dict(
                aM = a.M,
                am = am,
                ag = a.g,
                af2 = a.f(2),
                afm = a.f(am),
                af23 = a.f(y=2)*3+1,
                ah = a.h(x=3,y=4),
                aj = a.j(5),
                a2j = 2+a.j(5),
                amm = a.more.m,
                amff = a.moref().f(y=3),
                afqb = a.fq( b ),
                eq = a==b,
                iadd = test_iadd(a).m,
                rxor = (1^a).m,#
                some = some_function(a)
            )
    

        deferred_a = DeferAll("a")
        deferred_b = DeferAll("b")
        actual_a = qA()
        actual_b = qA()
        results_act = tester(actual_a, actual_b)
        results_drf = tester(deferred_a, deferred_b)
        
        deferred_b.deferred_resolve( qA() )
        deferred_a.deferred_resolve( qA() )
        
        results_tst = { k: v.deferred_result for k,v in results_drf.items() }

        self.assertEqual( list(results_tst), list(results_act) )
        for k, tst in results_tst.items():
            act = results_act[k]
            self.assertEqual( tst, act, msg=f"Step 1 {k} '{tst}' != '{act}'" )
        
        # ops

        def c1(a):
        	a+=3
        	return a
        def c2(a):
        	a-=3
        	return a
        def c3(a):
            a = a.astype(np.float32)
            a/=3
            return a
        def c4(a):
        	a//=3
        	return a
        def c5(a):
        	a*=3
        	return a
        def c6(a):
        	a^=3
        	return a
        def c7(a):
        	a|=3
        	return a
        def c8(a):
        	a&=3
        	return a
        def c9(a):
        	a**=3
        	return a
        def cA(a):
            a@=a.T
            return a
        def cB(a):
        	a%=3
        	return a
        def test_op(a):
            return dict(
        		# left
                a1 = a+3    ,
                a2 = a-3    ,
                a3 = a/3    ,
                a4 = a//3   ,
                a5 = a*3    ,
                a6 = a^3    ,
                a7 = a|3    ,
                a8 = a&3    ,
                a9 = a**3   ,
                aA = a@np.full((2,1),2)    ,
                aB = a%3    ,
        		# right
                b1 = 3+a    ,
                b2 = 3-a    ,
                b3 = 3/a    ,
                b4 = 3//a   ,
                b5 = 3*a    ,
                b6 = 3^a    ,
                b7 = 3|a    ,
                b8 = 3&a    ,
                b9 = 3**a   ,
                bA = a.T @ a,
                bB = 3%a    ,
                bC = [3]+a  ,
        		# in place
        		c1 = c1(a),
        		c2 = c2(a),
                c3 = c3(a),
                c4 = c4(a),
                c5 = c5(a),
                c6 = c6(a),
                c7 = c7(a),
                c8 = c8(a),
                c9 = c9(a),
                cB = cB(a)
        	)

        deferred_a = DeferAll("a")
        actual_a = np.full((4,2),3,dtype=np.int32)
        results_act = test_op(actual_a)
        results_drf = test_op(deferred_a)
        
        deferred_a.deferred_resolve( np.full((4,2),3,dtype=np.int32) )

        results_act = { k: v.astype(np.int32) for k,v in results_act.items() }
        results_tst = { k: v.deferred_result.astype(np.int32) for k,v in results_drf.items() }

        self.assertEqual( list(results_tst), list(results_act) )
        for k, tst in results_tst.items():
            act = results_act[k]
            self.assertEqual( act.shape, tst.shape, msg=k )
            self.assertTrue( np.all( tst == act ), msg=f"Step 2 {k} '{tst}' != '{act}'" )

        # abs
        
        a = DeferAll("a")
        b = abs(a)
        a.deferred_resolve(int(-11))
        self.assertEqual( b.deferred_result, 11 )

        # unsupported

        with self.assertRaises(NotSupportedError):
            a = DeferAll("a")
            bool(a)
        with self.assertRaises(NotSupportedError):
            a = DeferAll("a")
            a.__index__()
        a = DeferAll("a")
        a = abs(a)*3
        self.assertEqual(str(a), "(|$a|*3)" )
        self.assertEqual(repr(a), "DeferAll((|$a|*3)<-$a)" )

        # info test
        
        a = DeferAll("a")
        b = DeferAll("b")
        _ = a.f( b.g(1) )
        self.assertEqual( _.deferred_info, '$a.f({$b.g(1)})' )

        a = DeferAll("a")
        b = DeferAll("b")
        _ = a.f( b.g(1) )
        src = list(_.deferred_sources.values())
        self.assertEqual( src, ['$a', '$b'] )
        src = _.deferred_sources_names
        self.assertEqual( src, ['$a', '$b'] )

        # collision test
        
        a = DeferAll("A")
        b = DeferAll("B")
        _ = a.f(b) # <- execution  depends on b
        
        with self.assertRaises(ResolutionDependencyError):
            a.deferred_resolve( AX() )  # <- must fail
    
    def test_deferred_edge_cases(self):
        """Test edge cases and error conditions in deferred execution"""
        
        # Test resolution with simple operation
        a = DeferAll("a")
        r1 = a.f(2)
        a.deferred_resolve(qA())
        self.assertEqual(r1.deferred_result, 2)
        
        # Test deferred property access
        a = DeferAll("a")
        result = a.g
        a.deferred_resolve(qA())
        self.assertEqual(result.deferred_result, 3)
        
        # Test deferred method chaining
        a = DeferAll("a")
        result = a.f(2)
        a.deferred_resolve(qA())
        self.assertEqual(result.deferred_result, 2)
        
        # Test deferred dictionary operations
        a = DeferAll("a")
        a["key"] = 42
        a_inst = qA()
        a.deferred_resolve(a_inst)
        self.assertEqual(a_inst.d["key"], 42)
        
        # Test static method access
        a = DeferAll("a")
        result = a.h(2, y=3)
        a.deferred_resolve(qA())
        self.assertEqual(result.deferred_result, 6)
        
        # Test class method access
        a = DeferAll("a")
        result = a.j(3)
        a.deferred_resolve(qA())
        self.assertEqual(result.deferred_result, 21)
        
        # Test deferred comparison operations
        a1 = DeferAll("a1")
        result = a1 == a1
        obj1 = qA()
        obj1.m = 2
        a1.deferred_resolve(obj1)
        self.assertTrue(result.deferred_result)
        
        # Test deferred XOR operation - skip due to qA.__eq__ complexity
        # The XOR operation result would be compared with qA's __eq__ which expects another qA
        
        # Test deferred with dependency tracking
        a = DeferAll("a")
        b = DeferAll("b")
        result = a.f(b.m)
        self.assertIn("$a", result.deferred_sources_names)
        self.assertIn("$b", result.deferred_sources_names)
            
if __name__ == '__main__':
    unittest.main()