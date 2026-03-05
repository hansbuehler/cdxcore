# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""


import unittest as unittest
import dataclasses as dataclasses
import sys as sys
import os as os
import pickle as pickle
import tempfile as tempfile
import shutil as shutil
sys.setrecursionlimit(100)

def import_local():
    return
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

from cdxcore.pretty import PrettyObject, Sequence, PrettyHierarchy, PrettyValueObject

class A1(PrettyObject):
    def __init__(self, x=3):
        self.x=x
class A2(PrettyObject):
    def __init__(self, x): # mandatory argument
        self.x=x
        
class Test(unittest.TestCase):
    

    def test_PrettyObject(self):

        # basics        
        g1 = PrettyObject(a=1)
        g1.b = 2
        g1['c'] = 3
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)

        with self.assertRaises(AttributeError):
            _ = g1.d
        with self.assertRaises(KeyError):
            _ = g1['d']

        g1['e'] = 4
        del g1.e
        g1.f = 5
        del g1['f']
        with self.assertRaises(AttributeError):
            _ = g1.e
        with self.assertRaises(AttributeError):
            _ = g1.f
        with self.assertRaises(AttributeError):
            del g1.f


        self.assertEqual(g1.get('c',4),3)
        self.assertEqual(g1.get('d',4),4)


        g1 = PrettyObject(g1)
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)

        g1.update({ 'd':4 })
        self.assertEqual(g1.d, 4)
        g1.update(PrettyObject(e=5))
        self.assertEqual(g1.e, 5)

        g1.update({ 'd':4 },d=3)
        self.assertEqual(g1.d, 3)

        # get default
        g = PrettyObject()
        x = g.setdefault("x", 1.)
        self.assertEqual(x, 1.)
        self.assertEqual(g.x, 1.)

        # multi element        
        g1 = PrettyObject()
        g1['a','b'] = 1,2
        self.assertEqual(g1.a,1)
        self.assertEqual(g1.b,2)
        self.assertEqual(g1['a','b'], (1,2))
        
        a,b,c = g1.get(['a','b','c'],[11,22,33]) 
        self.assertEqual( a, 1 )
        self.assertEqual( b, 2 )
        self.assertEqual( c, 33 )
        self.assertTrue( not c in g1 )

        a,b,c = g1.get(a=11,b=22,c=33)
        self.assertEqual( a, 1 )
        self.assertEqual( b, 2 )
        self.assertEqual( c, 33 )
        self.assertTrue( not c in g1 )

        a,b,d = g1.setdefault(a=11,b=22,d=44)
        self.assertEqual( a, 1 )
        self.assertEqual( b, 2 )
        self.assertEqual( d, 44 )
        self.assertTrue( not c in g1 )
        self.assertTrue( g1.d, 44 )
        
        a,b,c = g1.pop(a=11,b=22,c=33)
        self.assertEqual( a, 1 )
        self.assertEqual( b, 2 )
        self.assertEqual( c, 33 )
        self.assertTrue( set(g1) == {'d'})
        
        g1 = PrettyObject()
        g1['a','b'] = 1,2
        
        a,b = g1 # this unpacks labels
        self.assertEqual(a,"a")
        self.assertEqual(b,"b")

        # functions
        def F(self,x):
            self.x = x # set 'x'
        g = PrettyObject()
        g.F = F
        g.F(2)
        self.assertEqual(g.x,2)

        g = PrettyObject(z=2)
        g.F = lambda slf, x: slf.z*x # access 'z'
        self.assertEqual(g.F(3),6)

        g2 = PrettyObject()
        g2.F = g.F
        with self.assertRaises(AttributeError):
            g2.F(3) # no 'z'
        g2.z = 3
        self.assertEqual(g2.F(3),9)
        
 
        with self.assertRaises(TypeError):
            def G():
                return 1
            g.G = G
            g.G()

        # __ does not work
        g = PrettyObject()
        g.__x = 1
        g._y = 2
        self.assertEqual(g.__x,1)    # works as usual
        self.assertEqual(g['_y'],2)  # protected works as for all python objects
        with self.assertRaises(KeyError):
            _ = g['__x']   # does not work: cannot use private members as dictionary elements
        self.assertEqual( getattr(g, "__z", None), None )
        with self.assertRaises(AttributeError):
            getattr(g, "__z",)

        # at_pos
        g1 = PrettyObject()
        g1.a=2
        g1.b=1
        g1.d=3
        g1.c=4
        self.assertEqual(g1.a, 2)
        self.assertEqual(g1.b, 1)
        self.assertEqual(g1.d, 3)
        self.assertEqual(g1.c, 4)
        self.assertEqual( g1.at_pos[3], 4)
        self.assertEqual( g1.at_pos[0:2], [2,1])
        self.assertEqual( g1.at_pos.keys[3], 'c')
        self.assertEqual( g1.at_pos.keys[0:2], ['a', 'b'])
        self.assertEqual( g1.at_pos.items[3], ('c',4))
        self.assertEqual( g1.at_pos.items[0:2], [('a',2), ('b',1)])
        
        self.assertTrue( isinstance( g1.at_pos, Sequence ))
        self.assertTrue( isinstance( g1.at_pos.keys, list ))
        self.assertTrue( isinstance( g1.at_pos.values, list ))
        self.assertTrue( isinstance( g1.at_pos.items, Sequence ))
        
        # copy
        p = PrettyObject(x=1,y=2)
        p.q1 = PrettyObject(z=3)
        p.q2 = PrettyObject(z=4)
        r = p.copy(x=11)
        p.q1.z = 33  # not shallow copy
        self.assertEqual( r.x, 11 )
        self.assertEqual( r.y, 2 )
        self.assertEqual( r.q1.z, 33 )
        self.assertEqual( r.q2.z, 4 )
        
        # iterator
        self.assertEqual( str(g1.at_pos.values), "[2, 1, 3, 4]")
        icnt = 0
        for k, v in g1.items():
            if icnt == 0:
                self.assertEqual(k, "a")
                self.assertEqual(v, 2)
            elif icnt == 1:                
                self.assertEqual(k, "b")
                self.assertEqual(v, 1)
            elif icnt == 2:                
                self.assertEqual(k, "d")
                self.assertEqual(v, 3)
            else:
                self.assertEqual( icnt, 3)
                self.assertEqual(k, "c")
                self.assertEqual(v, 4)
            icnt += 1

        @dataclasses.dataclass
        class Data:
            data : PrettyObject = PrettyObject().as_field()
        data = Data()
        with self.assertRaises(AttributeError):
            _ = data.data.x
        data = Data(PrettyObject(x=1))
        self.assertEqual(data.data.x,1)

        @dataclasses.dataclass
        class Data:
            data : PrettyObject = PrettyObject(x=2).as_field()
        data = Data()
        self.assertEqual(data.data.x,2)
        data = Data( data=PrettyObject({'x':3}))
        self.assertEqual(data.data.x,3)
        
        # comparison
        
        a = PrettyObject(x=1,y=2)
        b = PrettyObject(x=1,y=2)
        self.assertEqual( a, b)
        a = PrettyObject(x=1,y=2)
        b = PrettyObject(y=2,x=1)
        self.assertNotEqual( a, b)
        a = PrettyObject(x=1,y=2,z=3)
        b = PrettyObject(x=1,y=2)
        self.assertNotEqual( a, b)
        self.assertTrue( a>= b)
        self.assertFalse( a<=b)
        
        # OR
        
        p = PrettyObject(a=1,b=2,x=3)
        q = PrettyObject(x=44,y=55,z=66)
        self.assertEqual( p|q, dict(a=1,b=2,x=44,y=55,z=66))
        self.assertEqual( q|p, dict(x=3,y=55,z=66,a=1,b=2))        
        a = p.copy()
        a |= p
        self.assertEqual( p|q, dict(a=1,b=2,x=44,y=55,z=66))
        
                
        # I/O
        
        p = PrettyObject()
        p.x = 1
        p.q = PrettyObject(y=22)
        self.assertEqual(p.q.y,22)

        a = A1()
        a.q = PrettyObject(y=22)
        self.assertEqual(a.x,3)
        self.assertEqual(a.q.y,22)

        aa = A2(x=4)
        aa.q = PrettyObject(y=22)
        self.assertEqual(aa.x,4)
        self.assertEqual(aa.q.y,22)

        try:
            tmp_dir  = tempfile.mkdtemp()    
            self.assertNotEqual(tmp_dir[-1],"/")
            self.assertNotEqual(tmp_dir[-1],"\\")
            tmp_file = tmp_dir + "/test_pretty_object.pck"
            
            with open(tmp_file, "wb") as f:
                pickle.dump(p,f)
                
            with open(tmp_file, "rb") as f:
                p2 = pickle.load(f)
                self.assertEqual(p2,p)
                
            os.remove(tmp_file)
            
            with open(tmp_file, "wb") as f:
                pickle.dump(a,f)
                
            with open(tmp_file, "rb") as f:
                a2 = pickle.load(f)
                self.assertEqual(a2,a)
                
            os.remove(tmp_file)

            with open(tmp_file, "wb") as f:
                pickle.dump(aa,f)
                
            with open(tmp_file, "rb") as f:
                aa2 = pickle.load(f)
                self.assertEqual(aa2,aa)

            os.remove(tmp_file)
            
        finally:
            shutil.rmtree(tmp_dir)

    def test_vector(self): 
         
        r = PrettyObject()
        
        # index
        r['a','b'] = -1
        self.assertEqual((r.a,r.b), (-1,-1))
        r['a','b'] = (1,2)
        self.assertEqual((r.a,r.b), (1,2))
        r['a','b'] = 1,2
        self.assertEqual((r.a,r.b), (1,2))
        a, b = r['a','b']
        self.assertEqual((a,b), (1,2))
        with self.assertRaises(KeyError):
            a, b, c = r['a','b','c']

        # get
        a, b, c = r.get(['a','b','c'],[1,2,33])
        self.assertEqual( (a,b,c), (1,2,33))
        a, b, c = r.get(['a','b','c'],default=[1,2,33])
        self.assertEqual( (a,b,c), (1,2,33))
        a, b, c = r.get(['a','b','c'],default=44)
        self.assertEqual( (a,b,c), (1,2,44))
        with self.assertRaises(KeyError):
            a, b, c = r.get(['a','b','c'],[1,2,r.no_default])

        a, b, c = r.get(a=11,b=22,c=33)
        self.assertEqual( (a,b,c), (1,2,33))
        
        with self.assertRaises(KeyError):
            a, b, c = r.get(a=11,b=22,c=r.no_default)
            
        # getdefault
        a, b, c = r.setdefault(a=11,b=22,c=33)
        self.assertEqual( (a,b,c), (1,2,33))
        self.assertEqual( r.c, 33 )
        del r.c

        a, b, c = r.setdefault(['a','b','c'], default=33 )
        self.assertEqual( (a,b,c), (1,2,33))
        self.assertEqual( r.c, 33 )
        del r.c

        a, b, c = r.setdefault(['a','b','c'], [11,22,33] )
        self.assertEqual( (a,b,c), (1,2,33))
        self.assertEqual( r.c, 33 )
        del r.c

        # pop
        r = PrettyObject(a=1,b=2)
        self.assertEqual(set(r), {'a','b'})
        a, b = r.pop(['a', 'b'])
        self.assertEqual((a,b),(1,2))
        self.assertTrue(len(r) == 0)
        r = PrettyObject(a=1,b=2,x=-1)
        a, b = r.pop(['a', 'b'])
        self.assertEqual((a,b),(1,2))
        self.assertEqual(set(r), {'x'})
        r = PrettyObject(a=1,b=2,x=-1)
        with self.assertRaises(KeyError):
            a, b = r.pop(['a', 'b','c'])
        self.assertEqual(set(r),{'a','b','x'}) # exception did not leave 'r' in a bad state

        r = PrettyObject(a=1,b=2,x=-1)
        a, b, c = r.pop(a=11,b=22,c=33)
        self.assertEqual((a,b,c),(1,2,33))
        self.assertEqual(set(r),{'x'})

        r = PrettyObject(a=1,b=2,x=-1)
        with self.assertRaises(KeyError):
            a, b, c = r.get(a=11,b=22,c=r.no_default)
        self.assertEqual(set(r),{'a','b','x'}) # exception did not leave 'r' in a bad state
         
    def test_phierarchy(self):
        
        r = PrettyHierarchy(a=1)
        self.assertEqual(set(r),{'a'})
        self.assertEqual(r.a,1)
        
        r.b = 2
        self.assertEqual(set(r),{'a','b'})
        self.assertEqual(r.b,2)
        
        with self.assertRaises(KeyError):
            _ = r['x']
        
        r.x.c = 3
        self.assertEqual(set(r),{'a','b','x'})
        self.assertIsInstance(r.x, PrettyHierarchy)
        self.assertEqual(r.x.c,3)
        
        r.y['d'] = 4
        self.assertEqual(set(r),{'a','b','x','y'})
        self.assertIsInstance(r.y, PrettyHierarchy)
        self.assertEqual(r.y.d,4)

        # oddities
        self.assertIsInstance( r.z, PrettyHierarchy)
        
        r = PrettyHierarchy()        
        r.A = 1
        def f(x):
            pass
        f( r.a )   # -> prints an empty PrettyHierarchy
        _ = r.b        # generates an empty PrettyHierarchy
        self.assertEqual(set(r), {'A','a','b'}) # all above created entries.
        
        r = PrettyHierarchy()        
        import numpy as np
        with self.assertRaises(TypeError):
            np.sum( r.centre )

    def test__PrettyValueObject(self):

        r = PrettyValueObject(a=1,b=2)

        a,b = r
        self.assertEqual((a,b), (1,2))
        
        self.assertEqual( set(r), {1,2})

        for i, ix in enumerate(r):
            self.assertEqual(ix, i+1)

        

if __name__ == '__main__':
    unittest.main()


