# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest as unittest
import numpy as np
import pandas as pd
import datetime as datetime
from zoneinfo import ZoneInfo
from enum import Enum

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
    
"""
Imports
"""
from cdxcore.uniquehash import UniqueHash, NamedUniqueHash, UniqueLabel, unique_hash32 as unique_hash, unique_hash8, unique_hash16, unique_hash32, unique_hash48, unique_hash64, DEF_FILE_NAME_MAP, DebugTraceCollect, DebugTraceVerbose
from cdxcore.pretty import PrettyObject

PrettyOrderedDict = PrettyObject 

uniqueHashProtected = UniqueHash(32,parse_underscore="protected")
uniqueHashPrivate = UniqueHash(32,parse_underscore="private")
uniqueHashF = UniqueHash(32,parse_functions=True)

namedUniqueHash32_8 = NamedUniqueHash( max_length=32, id_length=8, parse_underscore="protected" )
uniqueLabel32_8 = UniqueLabel( max_length=32, id_length=8 )

class Test(unittest.TestCase):
    
    def __init__(self, *args, **kwargs):
        self.maxDiff = 2000
        super().__init__(*args, **kwargs)

    def test_uniqueHash(self):

        self.assertEqual( unique_hash( 1==1 ), "c8814ea06a53a108a02015477d9ea347" )
        self.assertEqual( unique_hash( "test" ), "e9ddd9926b9dcb382e09be39ba403d2c" )
        self.assertEqual( unique_hash( "test".encode("utf-8") ), "e9ddd9926b9dcb382e09be39ba403d2c" )
        self.assertEqual( unique_hash( 0 ), "d566dfb39f20d549d1c0684e94949c71" )
        self.assertEqual( unique_hash( -1 ), "265e3aae841649db057419ac7d85d399" )
        self.assertEqual( unique_hash( 0x7fff ), "1770301688382dac9c6d87284d5a3111" )
        self.assertEqual( unique_hash( 0.1 ), "f45961d9b7e8673e7c758bcfd8af7cb9" )
        self.assertEqual( unique_hash( 1E-10), "9102ac1dc2adb0aa013cd897a69f74d2" )
        self.assertEqual( unique_hash( np.nan ), "a22bbc77f337db5e2445bd5c0235812e" )
        
        self.assertEqual( unique_hash( np.float16(0) ), "ff1bed336aae497f15a0d3f534609380" )
        self.assertEqual( unique_hash( np.float32(0) ), "c566588ea757dd31297b78f8c62a4b05" )
        self.assertEqual( unique_hash( np.float64(0) ), "d566dfb39f20d549d1c0684e94949c71" )        
        self.assertEqual( unique_hash( np.int8(0) ), "9f31f3ec588c6064a8e1f9051aeab90a" )
        self.assertEqual( unique_hash( np.int8(-1) ), "df09d795132a032676a7ca47bcc2db61" )
        self.assertEqual( unique_hash( np.uint8(250) ), "5067455d73d452a04850bf2f20ee3c61" )
        self.assertEqual( unique_hash( np.int16(0) ), "ff1bed336aae497f15a0d3f534609380" )
        self.assertEqual( unique_hash( np.uint16(0xFFFF) ), "f1118c91662ef7ccc0e2f45922d41d90" )
        self.assertEqual( unique_hash( np.int32(0) ), "c566588ea757dd31297b78f8c62a4b05" )
        self.assertEqual( unique_hash( np.int64(0) ), "d566dfb39f20d549d1c0684e94949c71" )
        self.assertEqual( unique_hash( np.int64(-1) ), "265e3aae841649db057419ac7d85d399" )
        
        self.assertEqual( unique_hash( [1,2,np.float16(3),4] ), "0922f2f0d1df45dac328582df43888f2" )
        self.assertEqual( unique_hash( [2,1,np.float16(3),4] ), "a33b2ce355ea93a0153d53806e5b692b" )
        self.assertEqual( unique_hash( set([1,2,np.float16(3),4]) ), "0922f2f0d1df45dac328582df43888f2" )
        self.assertEqual( unique_hash( x for x in [1,2,np.float16(3),4] ), "64550d6ffe2c0a01a14aba1eade0200c" )
        
        # dicts
        self.assertEqual( unique_hash( {'a':"mix"} ), "cfd3448192fa25895e52426f69d550b1" )
        self.assertEqual( unique_hash( {'a':"mix", 'b':1} ), "3c85e8c0142b9b3d9c78b10106e27fdc" )
        
        r = PrettyOrderedDict()
        r.x = 1
        self.assertEqual( unique_hash( r ), "5bdac013107a78ea9ca53a6df858cfa8" )
        r.x = 2
        hashr = unique_hash( r )
        self.assertEqual( hashr, "e6b10cf5d15f3ec798eb9daa516606cf" ) # (1)
        r._x = 1
        # elements with '_' are ignored by default
        self.assertEqual( unique_hash( r ), hashr )  # same as above (1)
        self.assertEqual( unique_hash( PrettyOrderedDict(_y=100,x=2 ) ), hashr )  # same as above (1)
        self.assertEqual( unique_hash( PrettyOrderedDict(__y=100,x=2 ) ), hashr )  # same as above (1)
        # protected
        self.assertEqual( uniqueHashProtected( PrettyOrderedDict(x=2 )), hashr )  # same as (1)
        hashprot = uniqueHashProtected( PrettyOrderedDict(_y=100,x=2 ) )
        self.assertEqual( hashprot, "c1b4c0a3a39540a6438e8426be81e81d" )  # (2)
        self.assertEqual( uniqueHashProtected( PrettyOrderedDict(_y=100,__z=100,x=2 ) ), hashprot )  # same as (2)
        self.assertEqual( uniqueHashProtected( PrettyOrderedDict(__z=100,x=2 ) ), hashr )  # same as (1)
        # private
        self.assertEqual( uniqueHashPrivate( PrettyOrderedDict(x=2 ) ), hashr )  # same as (1)
        self.assertEqual( uniqueHashPrivate( PrettyOrderedDict(_y=100,x=2 ) ), hashprot )  # same as (2)
        hash3 = uniqueHashPrivate( PrettyOrderedDict(_y=100,__z=100,x=2 ) )
        hash4 = uniqueHashPrivate( PrettyOrderedDict(__z=100,x=2 ) )
        self.assertEqual( hash3, "baa7e5c21a9b5bbfbe783ad92bd5e38b" )  # (3)
        self.assertNotEqual( hash3, hashprot )
        self.assertEqual( hash4, "9cc69ec4c0e9f3f820ca63531e7ba0a2" )  # (4)
        self.assertNotEqual( hash4, hashprot )
        
        class Object(object):
            def __init__(self_):
                self_.x = [ 1,2,3. ]
                self_.y = { 'a':1, 'b':2 }
                self_.z = PrettyObject(c=3,d=4)
                self_.r = set([65,6234,1231,123123,12312])
                self_.t = (1,2,"test")
                self_.s = {1,3,4,2,5}

                def ff():
                    pass

                self_.ff = ff
                self_.gg = lambda x : x*x

                self_.a = np.array([1,2,3])
                self_.b = np.zeros((3,4,2))
                self_.c = pd.DataFrame({'a':np.array([1,2,3]),'b':np.array([10,20,30]),'c':np.array([100,200,300]),  })

                u = unique_hash(self_.b) # numpy
                self.assertEqual( u, "de8bc8a3a92214d15e50f137565ed6a7" )
                u = unique_hash(self_.c) # panda frame
                self.assertEqual( u, "6825de2c38cab22de057211b1ad01ce8" )

            def f(self_):
                pass

            @staticmethod
            def g(self_):
                pass

            @property
            def h(self_):
                return self_.x

        x = np.array([1,2,3,4.])
        u = unique_hash(x)
        self.assertEqual( u, "b45b735c27fa083d3ea50021251d178f" )
                
        o2 = [ np.float32(0), np.float64(0), np.int32(0), np.int64(0) ]
        u = unique_hash(o2)
        self.assertEqual( u, "8bae89164e1da1371c9beacc007db340" )

        o = Object()
        u = unique_hash(o)
        self.assertEqual( u, "7b0ce60d5a922b47c2e73a9604060510" )
        u = unique_hash8(o)
        self.assertEqual( u, "305c3163" )
        u = unique_hash16(o)
        self.assertEqual( u, "ea0c4db7b20fbbe4" )
        u = unique_hash32(o)
        self.assertEqual( u, "7b0ce60d5a922b47c2e73a9604060510" )
        u = unique_hash48(o)
        self.assertEqual( u, "2187ac6fbd548e81343bfb4c3ef08dd6d1264729a7f04b82" )
        u = unique_hash64(o)
        self.assertEqual( u, "840c6d1d9d6e3cc49dc6ed0ded1020674ed371588255a5230e44b4e872f57358" )
    
        class X(object):
            __slots__ = ['x', 'y']            
            def __init__(self, x, y):
                self.x = x
                self.y = y
            def __repr__(self):
                return f"X(x={self.x},y={self.y})"
        A = X
        class X(object):   # looks the same as X in non-protected mode !
            __slots__ = ['x', 'y', '_z']
            def __init__(self, x, y):
                self.x = x
                self.y = y
                self._z = x*y
            def __repr__(self):
                return f"X(x={self.x},y={self.y},_z={self._z})"
        B = X
        a1 = A(1,2)
        a2 = A(1,3)
        b  = B(1,2)
        debug_trace = DebugTraceCollect()
        hash1 = unique_hash(a1, debug_trace=debug_trace)
        trace1 = repr(debug_trace)

        debug_trace = DebugTraceCollect()
        hash2 = unique_hash(a2, debug_trace=debug_trace)
        trace2 = repr(debug_trace)

        debug_trace = DebugTraceCollect()
        hash3 = unique_hash(b,debug_trace=debug_trace)
        trace3 = repr(debug_trace)

        self.assertEqual( hash1, "610eac1fa7e30fb1f9e20a29e3f5e527" )  # (1)
        self.assertEqual( hash2, "4864ea1d65079c41841d145716ee47ff" )  # (2) != (1)
        self.assertNotEqual( hash1, hash2 )   # (1) != (2)
        self.assertEqual( hash3, "610eac1fa7e30fb1f9e20a29e3f5e527" )   # (3) == (1)
        self.assertEqual( hash3, hash1 )   # (3) == (1)
        self.assertEqual( uniqueHashProtected(a1), hash1 )  # == (1)
        self.assertEqual( uniqueHashProtected(a2), hash2 )  # == (2)
        debug_trace = DebugTraceCollect()
        hash3p = uniqueHashProtected(b,debug_trace=debug_trace)
        trace3p = repr(debug_trace)
        self.assertEqual( hash3p, "8e62d262da492b3f96fbc0be1e21fcfb" )   # != (1)
        
        r = "DebugTraceCollect([PrettyObject({'x': (X(x=1,y=2),), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': X(x=1,y=2), 'msg': 'object with __slots__', 'child': DebugTraceCollect([PrettyObject({'x': 'Test.test_uniqueHash.<locals>.X', 'msg': None, 'child': None}), PrettyObject({'x': 'x', 'msg': None, 'child': None}), PrettyObject({'x': 1, 'msg': None, 'child': None}), PrettyObject({'x': 'y', 'msg': None, 'child': None}), PrettyObject({'x': 2, 'msg': None, 'child': None})])})])})])"
        self.assertEqual(trace1,r)
        r = "DebugTraceCollect([PrettyObject({'x': (X(x=1,y=3),), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': X(x=1,y=3), 'msg': 'object with __slots__', 'child': DebugTraceCollect([PrettyObject({'x': 'Test.test_uniqueHash.<locals>.X', 'msg': None, 'child': None}), PrettyObject({'x': 'x', 'msg': None, 'child': None}), PrettyObject({'x': 1, 'msg': None, 'child': None}), PrettyObject({'x': 'y', 'msg': None, 'child': None}), PrettyObject({'x': 3, 'msg': None, 'child': None})])})])})])"
        self.assertEqual(trace2,r)
        r = "DebugTraceCollect([PrettyObject({'x': (X(x=1,y=2,_z=2),), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': X(x=1,y=2,_z=2), 'msg': 'object with __slots__', 'child': DebugTraceCollect([PrettyObject({'x': 'Test.test_uniqueHash.<locals>.X', 'msg': None, 'child': None}), PrettyObject({'x': 'x', 'msg': None, 'child': None}), PrettyObject({'x': 1, 'msg': None, 'child': None}), PrettyObject({'x': 'y', 'msg': None, 'child': None}), PrettyObject({'x': 2, 'msg': None, 'child': None})])})])})])"
        self.assertEqual(trace3,r)
        r = "DebugTraceCollect([PrettyObject({'x': (X(x=1,y=2,_z=2),), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': X(x=1,y=2,_z=2), 'msg': 'object with __slots__', 'child': DebugTraceCollect([PrettyObject({'x': 'Test.test_uniqueHash.<locals>.X', 'msg': None, 'child': None}), PrettyObject({'x': 'x', 'msg': None, 'child': None}), PrettyObject({'x': 1, 'msg': None, 'child': None}), PrettyObject({'x': 'y', 'msg': None, 'child': None}), PrettyObject({'x': 2, 'msg': None, 'child': None}), PrettyObject({'x': '_z', 'msg': None, 'child': None}), PrettyObject({'x': 2, 'msg': None, 'child': None})])})])})])"
        self.assertEqual(trace3p,r)

        o1 = PrettyObject(x=1)#, y=Object())
        o2 = PrettyObject(x=1)#, y=Object())
        o3 = PrettyObject(x=1)#, y=Object())
        o1._test = 2
        o1.__test = 3
        o2._test = 2

        self.assertTrue( not hasattr(o3, "_test" ) )
        self.assertTrue( not hasattr(o3, "__test" ) )
        
        hashbase = unique_hash( o1 )
        hashprot = uniqueHashProtected( o1 )
        hashpriv = uniqueHashPrivate( o1 )

        self.assertEqual( unique_hash( o2 ) , hashbase )
        self.assertEqual( unique_hash( o3 ) , hashbase )
        self.assertEqual( uniqueHashProtected( o2 ) , hashprot )
        self.assertNotEqual( uniqueHashProtected( o3 ) , hashprot )
        self.assertNotEqual( uniqueHashPrivate( o2 ) , hashpriv )
        self.assertNotEqual( uniqueHashPrivate( o3 ) , hashpriv )

        debug_trace = DebugTraceCollect()        
        u1 = unique_hash( o1, debug_trace=debug_trace )
        r = "[PrettyObject({'x': (PrettyObject({'x': 1, '_test': 2, '_Test__test': 3}),), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': PrettyObject({'x': 1, '_test': 2, '_Test__test': 3}), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': ('x', 1), 'msg': None, 'child': DebugTraceCollect([PrettyObject({'x': 'x', 'msg': None, 'child': None}), PrettyObject({'x': 1, 'msg': None, 'child': None})])})])})])})]"
        self.assertEqual( str(debug_trace), r) 

        # test functions
        f1 = lambda x : x*x
        f2 = lambda x : x*x
        f3 = lambda x : x+2

        u0 = uniqueHashF() # nothing
        u1 = uniqueHashF(f1)
        u2 = uniqueHashF(f2)
        u3 = uniqueHashF(f3)
        self.assertEqual(u0,"64550d6ffe2c0a01a14aba1eade0200c")
        self.assertEqual(u1,"a0c25a23de91678dc6d606b4bc68797d")
        self.assertEqual(u2,u1)
        self.assertEqual(u3,"f3050eec75ca604eaeb175b6bde2a8bb")
        self.assertNotEqual(u3,u1)

        u1 = unique_hash(f1)
        u2 = unique_hash(f2)
        u3 = unique_hash(f3)
        self.assertEqual(u1,u0)
        self.assertEqual(u2,u0)
        self.assertEqual(u3,u0)

        # test ignore warning
        debug_trace = DebugTraceCollect()        
        u1 = unique_hash( f1, debug_trace=debug_trace )
        ignore = debug_trace[0].child[0].msg
        self.assertEqual( ignore, "Ignored function: Test.test_uniqueHash.<locals>.<lambda>") 

        # globals, defaults
        def test1():
            z=10
            
            def f(x,y):
                return x*y*z
            f1 = f # otherwise simply the name will trigger a difference
            
            def f(x,y=2):
                return x*y*z
            f2 = f
            
            def f(x,*,y=2):
                return x*y*z
            f3 = f
            
            def f(x,y=2):
                return x*y*z
            f4 = f

            u1 = uniqueHashF( f1 )#, debug_trace=DebugTraceVerbose())     
            u2 = uniqueHashF( f2 )#, debug_trace=DebugTraceVerbose())     
            u3 = uniqueHashF( f3 )#, debug_trace=DebugTraceVerbose())     
            u4 = uniqueHashF( f4 )#, debug_trace=DebugTraceVerbose())     

            z=11

            u5 = uniqueHashF( f4 )

            self.assertEqual( u1, "6285055ea7e60e9860c04f9b56a76368")
            self.assertEqual( u2, "322825a47fd43cf42cb6bf313758dcb4")
            self.assertEqual( u3, "5c17e071c9e3b46471fa5f73a7aa54a5" )
            self.assertEqual( u4, u2 )  # 
            self.assertNotEqual( u5, u3 ) # global 'z' different !
        test1()
            
        # closure
        def test1(z):
            def f(x):
                return x*z
            return f
        f1 = test1(1.)
        f2 = test1(1.)
        f3 = test1(2.)
        u1 = uniqueHashF( f1 )
        u2 = uniqueHashF( f2 )
        u3 = uniqueHashF( f3 )

        self.assertEqual( u1, "cc3d356d1e7f84f1e3aacd8d8346c6ef" )            
        self.assertEqual( u2, u1 )
        self.assertNotEqual( u3, u1 )
            
        # time
        tz  = ZoneInfo("America/New_York")
        tz2 = ZoneInfo("Asia/Tokyo")
        tz3 = ZoneInfo("GMT")
        plain = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3 )
        timz  = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, tzinfo=tz )
        micro = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=3232 )
        lots  = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=3232, tzinfo=tz )
        lots2 = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=0, tzinfo=tz2 )
        lots3 = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=0, tzinfo=tz3 )
    
        plainhash =  unique_hash(plain)
        self.assertEqual( plainhash, "9142b8ffd5f12e83f94c261da5935674")  # (1)
        self.assertEqual( unique_hash(timz), "82b58ccbe7a14a31d86aaa4ff5148ddb")
        self.assertEqual( unique_hash(micro), "89c16cd9eb05f2bc92ddab0a9cce96bc")
        self.assertEqual( unique_hash(lots), "8ad007ff97156db6ab709cead44ca5c0")
        self.assertEqual( unique_hash(lots2), "045730565f1ae4f07e28f2d80a4b98c9")
        self.assertEqual( unique_hash(lots3), plainhash)  # same as (1)
    
        hash1 = unique_hash(datetime.date( year=1974, month=3, day=17 ))
        self.assertEqual( hash1, "5ea7ea54a4a5e16b41be046d62092e3d")   # (1)
        self.assertEqual( unique_hash(plain.date()),hash1 )   # same as (1)
        self.assertEqual( unique_hash(datetime.date( year=1974, month=3, day=2 )), "21c4c10490cb41431c6c444c4d49c287")  
        self.assertEqual( unique_hash(datetime.date( year=2074, month=3, day=2 )), "5498e6f3519c815393f2da1d42dda196")  
        self.assertEqual( unique_hash(datetime.time( hour=16, minute=2, second=3, microsecond=0 )), "e10f649dae2851b77f63b196b63c01c5")  
        self.assertEqual( unique_hash(datetime.time( hour=16, minute=2, second=3 )), "e10f649dae2851b77f63b196b63c01c5")  

        empty = unique_hash(datetime.timedelta())
        self.assertEqual( empty, "d566dfb39f20d549d1c0684e94949c71")
        self.assertEqual( unique_hash(datetime.timedelta( seconds=0 ) ), empty)
        self.assertEqual( unique_hash(datetime.timedelta( days=0, seconds=0 ) ), empty)
        self.assertEqual( unique_hash(datetime.timedelta( days=0, seconds=0, microseconds=0 ) ), empty)
        self.assertEqual( unique_hash(datetime.timedelta( days=0 ) ), empty)


        hash1 = unique_hash(datetime.timedelta( days=2, seconds=2+60*3+60*60*4, microseconds=1 ))
        self.assertEqual( hash1, "8fd3e750ef3e59c2526070d6ccdc3e56") # (1)
        self.assertEqual( unique_hash(datetime.timedelta( days=0, seconds=2+60*3+60*60*4+2*24*60*60, microseconds=1 )), hash1 ) 
        hash2 = unique_hash(datetime.timedelta( days=2, seconds=2+60*3+60*60*4, microseconds=0 ))
        self.assertEqual( hash2, "35fcb34c6f2e3ff5f0c58e6912916990") # !=(1)
        self.assertNotEqual( hash2, hash1 )
        
        hash1 = unique_hash(datetime.timedelta( seconds=0, microseconds=1 ))
        hash2 = unique_hash(datetime.timedelta( seconds=0, microseconds=-1 ))
        self.assertEqual( hash1, "8b56e0808aad40a2722eadd13279e619")  
        self.assertEqual( hash2, "5a7f33307048636c4071967f95c40a85") 
        self.assertNotEqual( hash2, hash1 )

        self.assertEqual( unique_hash( pd.DataFrame({'a':[1,2,3],'b':[10,20,30],'c':[100,200,300]}) ), "6825de2c38cab22de057211b1ad01ce8")
        self.assertEqual( unique_hash( pd.DataFrame({'a':[1,2,3],'b':[10,20,30],'c':[100,200,300]}, index=[1,2,3]) ), "d8f7b3a49efe9c2961e54b8feb8f1eae")
        hash1 = unique_hash( pd.DataFrame({'a':[1.,2.,3.],'b':[10.,20.,30.],'c':[100.,200.,300.]}, index=[1,2,3]) )
        self.assertEqual( hash1, "13c5e3d147fcca03fcb1de6b6b1bcef0") # (1)
        
        df = pd.DataFrame({'a':[1,2,3],'b':[10,20,30],'c':[100,200,300]}, index=[1,2,3], dtype=np.float64)
        hash2 =  unique_hash( df )
        self.assertEqual(hash2, hash1)
        df.attrs["test"] = 1        
        hash2 = unique_hash( df )
        self.assertEqual( hash2, "c038dd30487f158bd8ff638941883e8b") # != (1)
        self.assertNotEqual( hash2, hash1 )
        del df.attrs["test"]
        hash2 = unique_hash( df )
        self.assertEqual( hash2, hash1) # == (1)

        np.random.seed( 12312 )
        a = np.exp( np.random.normal( size=(20,10) ).astype( np.float64 ) )
        b = a.astype(np.float32, copy=True)
        c = a.astype(np.float16, copy=True)
        self.assertEqual( unique_hash( a ), "1bac6e6c06b9ed1603670cb6895c1aaa")
        flat = unique_hash( a.flatten() )
        self.assertEqual( flat, "a002ff5a0d035f6dc30c8a366b5cdff3") # (1)
        self.assertEqual( unique_hash( b ), "4dcc1a611fd718e957ef8e6bcff7a326")
        self.assertEqual( unique_hash( c ), "e5a2889b6aafe33389890259e73407a5")
        
        np.random.seed( 12312 )
        a2 = np.exp( np.random.normal( size=(20*10,) ).astype( np.float64 ) )
        self.assertEqual( unique_hash( a2 ), flat ) # == (1)
        
        # named
        # -----
        
        namedUniqueHash32_8 = NamedUniqueHash( max_length=32, id_length=8, parse_underscore="protected" )
        filenamedUniqueHash32_8_1 = NamedUniqueHash( max_length=32, id_length=8, parse_underscore="protected", filename_by=DEF_FILE_NAME_MAP )
        
        o1 = Object()
        o2 = Object()
        o3 = Object()
        o2._test = 2
        o3._test = 2
        o3.__test = 3

        hash1 = namedUniqueHash32_8( "object:", o1 )
        hash1f1 = filenamedUniqueHash32_8_1( "object:", o1 )
        self.assertEqual( hash1, "object: 70a87aad" )
        self.assertNotEqual( namedUniqueHash32_8( "object;", o1 ), hash1 )   # <-- no filename translation 

        self.assertEqual( hash1f1, "object; 77c68e92" )
        self.assertEqual( namedUniqueHash32_8( "object;", o1 ), hash1f1 )     # <-- with filename translation: ':' --> ';'
        self.assertNotEqual( namedUniqueHash32_8( "object;", o1 ), hash1 )   # <-- filename translation 

        hashprot = namedUniqueHash32_8( "object:", o2 )
        self.assertEqual( hashprot, "object: fd1f4e66" )
        self.assertEqual( namedUniqueHash32_8( "object:", o3 ), hashprot )

        # __unique_hash__
        # ----------------
        
        class A(object):
            """ No ID. Because members are protected by default this object is hashed as "empty" """
            def __init__(self, seed = 12312, size = (10,) ):
                np.random.seed( seed )
                self._seed = seed
                self._size = size
                self.__data = np.random.normal( size=size )  # we do not want to hash this: it is determined by the other two parameters
            @property
            def data(self):
                return self.__data
        
        class B(A):
            """ Compute unique ID at construction time """
            def __init__(self, seed = 12312, size = (100,) ):
                super().__init__(seed, size)
                self.__unique_hash__ = unique_hash( self._seed, self._size ) 

        class C(A):
            """ Use the unique_hash object passed to this function to compute the hash """
            def __unique_hash__( self, unique_hash, debug_trace ):
                return unique_hash( self._seed, self._size, debug_trace=debug_trace )        
            
        class D(A):
            """ Just return the members we care about """
            def __unique_hash__( self, unique_hash, debug_trace ):
                return ( self._seed, self._size )
            
        class E(A):
            """ Fixed string """
            def __init__(self):
                self.__unique_hash__ = "some_string"
            
        empty = unique_hash( ('Test.test_uniqueHash.<locals>.A') )
        hash1 = unique_hash( A() )
        hash2 = unique_hash( B() )
        hash3 = unique_hash( C() )
        hash4 = unique_hash( D() )
        hash5 = unique_hash( E() )
        h_5   = unique_hash( E().__unique_hash__ )
        self.assertEqual( empty, "653a05ac14649dbceebbd7f3d4a0b89f" )        
        self.assertEqual( hash1, empty )
        self.assertEqual( hash2, "ae7cc6d56596eaa20dcd6aedc6e89d85" )
        self.assertEqual( hash3, "5e387f9e86426319577d2121a4e1437b" )
        self.assertEqual( hash4, "c9b449e95339458df155752acadbebb1" )
        self.assertEqual( hash5, "79ee12b070c036e874263c6f4d70df98" )
        self.assertEqual( hash5, h_5 )

        # enum        
        class TestEnum(Enum):
            A = 1
            B = 2
        
        a = TestEnum.A
        b = TestEnum.B
        self.assertNotEqual( unique_hash(a), unique_hash(b) )

                    
            
if __name__ == '__main__':
    unittest.main()


