# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""
try:
    from import_local import import_local
    import_local()
except ModuleNotFoundError:
    pass

import unittest as unittest
    
"""
Imports
"""
from cdxcore.version import version

@version("1.0")
def f(x):
    return x
@version("2.0", dependencies=[f])
def g1(x):
    return f(x)
@version("2.1", dependencies=[f])
def g2(x):
    return f(x)
class A(object):
    @version("2.2")
    def r1(self, x):
        return x
    @version("2.3", dependencies=['A.r1', 'g1'])
    def r2(self, x):
        return x
@version("XV")
class B(object):
    def f(self, x):
        return x
    @version("1")
    def t1(self):
        return
    @version("2", auto_class=True)
    def t2(self):
        return
    @version("3", auto_class=False)
    def t3(self):
        return

@version("3.0", dependencies=['g1', g2, 'A.r1', A.r2, B])
def h(x,y):
    a = A()
    return g1(x)+g2(y)+a.r1(x)+a.r2(y)

@version("0.0.1")
class baseA(object):
    pass
@version("0.0.2")
class baseB(baseA):
    pass
@version("0.0.3", auto_class=False)
class baseC(baseA):
    pass

bA = baseA()

@version("2", dependencies=[bA]) # <- actually not a great use case to make a function dependent on an object (instead of the class)
def baf(x):
    return x

class AA(object):
    def __init__(self, x=2):
        self.x = x
    @version(version="0.4.1")
    def h(self, y):
        return self.x*y

@version(version="0.3.0")
def Ah(x,y):
    return x+y

@version(version="0.0.2", dependencies=[Ah])
def Af(x,y):
    return Ah(y,x)

@version(version="0.0.1", dependencies=["Af", AA.h])
def Ag(x,z):
    a = AA()
    return Af(x*2,z)+a.h(z)

class Empty:
    pass

class Test(unittest.TestCase):
    
    def test_version(self):
        # test dependency
        
        a = A()
        b = B()
        bA = baseA()
        bB = baseB()
        bC = baseC()
        
        self.assertEqual( h.version.input, "3.0" )
        self.assertEqual( h.version.full, "3.0 { A.r1: 2.2, A.r2: 2.3 { A.r1: 2.2, g1: 2.0 { f: 1.0 } }, B: XV, g1: 2.0 { f: 1.0 }, g2: 2.1 { f: 1.0 } }" )
        self.assertEqual( h.version.unique_id48, "3.0 { A.r1: 2.2, A.r2: 2.3 { A.r1: 2.2, 2695aabd" )
        self.assertEqual( h.version.is_dependent( g2 ), "2.1" )
        self.assertEqual( h.version.is_dependent( "g2" ), "2.1" )
        self.assertEqual( h.version.is_dependent( f ), "1.0" )
        self.assertEqual( h.version.is_dependent( "f" ), "1.0" )
        self.assertEqual( h.version.is_dependent( B ), "XV" )
        self.assertEqual( h.version.is_dependent( b ), "XV" )
        self.assertEqual( h.version.is_dependent( A.r2 ), "2.3" )
        self.assertEqual( h.version.is_dependent( a.r2 ), "2.3" )
        self.assertEqual( b.t1.version.full, "1 { B: XV }" )
        self.assertEqual( b.t2.version.full, "2 { B: XV }" )
        self.assertEqual( b.t3.version.full, "3" )
        self.assertEqual( baf.version.full, "2 { baseA: 0.0.1 }" )

        self.assertEqual( baseA.version.full, "0.0.1")
        self.assertEqual( baseB.version.full, "0.0.2 { baseA: 0.0.1 }")
        self.assertEqual( baseC.version.full, "0.0.3")
        self.assertEqual( bA.version.full, "0.0.1")
        self.assertEqual( bB.version.full, "0.0.2 { baseA: 0.0.1 }")
        self.assertEqual( bC.version.full, "0.0.3")

        Ag(1,2)
        
        self.assertEqual( Ag.version.input, "0.0.1")
        self.assertEqual( Ag.version.full, "0.0.1 { AA.h: 0.4.1, Af: 0.0.2 { Ah: 0.3.0 } }")
        self.assertEqual( Ag.version.unique_id48, "0.0.1 { AA.h: 0.4.1, Af: 0.0.2 { Ah: 0.3.0 } }")
        self.assertEqual( Ag.version.dependencies,('0.0.1', {'AA.h': '0.4.1', 'Af': ('0.0.2', {'Ah': '0.3.0'})}) )
            
        # built in 
        print2 = version("0.1")(print)        
        self.assertEqual( print2.version, "0.1")
        self.assertEqual( print2.__name__, "VersionBuiltinFunctionWrapper(print)")
        
        Empty.__new__ = version("0.1")(Empty.__new__)
        _ = Empty()
        self.assertEqual( Empty.__new__.version, "0.1")
        self.assertEqual( Empty.__new__.__name__, "VersionBuiltinFunctionWrapper(__new__)")
        
if __name__ == '__main__':
    unittest.main()


