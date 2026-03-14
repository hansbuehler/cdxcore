# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

try:
    import import_local
except ModuleNotFoundError:
    pass
import unittest as unittest
import sys
sys.setrecursionlimit(100)    
"""
Imports
"""
from cdxcore.subdir import SubDir, CacheMode, VersionError, VersionPresentError, VersionedCacheRoot, CacheTracker, CacheController, CacheInfo
from cdxcore.version import version, VersionError
from cdxcore.uniquehash import unique_hash16
from cdxcore.verbose import Context
from cdxcore.pretty import PrettyObject   
from collections import OrderedDict
import numpy as np
import polars as pl

class Test(unittest.TestCase):

    def test_subdir(self):
        pass

        sub = SubDir("?/.tmp_test_for_cdxcore.subdir", delete_everything=True )
        sub['y'] = 2
        sub.write('z',3)
        sub.write_string('l',"hallo")
        sub.write(['a','b'],[11,22])

        lst = str(sorted(sub.files()))
        self.assertEqual(lst, "['a', 'b', 'y', 'z']")
        lst = str(sorted(sub.files(ext="txt")))
        self.assertEqual(lst, "['l']")

        # test naming
        self.assertEqual( str(sub), sub.path + ";*" + sub.ext )
        self.assertEqual( repr(sub), "SubDir(" + sub.path + ";*" + sub.ext + ")" )

        # read them all back
        self.assertEqual(sub['y'],2)
        self.assertEqual(sub['z'],3)
        self.assertEqual(sub.read_string('l'),"hallo")
        self.assertEqual(sub['a'],11)
        self.assertEqual(sub['b'],22)
        self.assertEqual(sub(['a','b'], None), [11,22])
        self.assertEqual(sub.read(['a','b']), [11,22])
        self.assertEqual(sub[['a','b']], [11,22])
        self.assertEqual(sub(['aaaa','bbbb'], None), [None,None])

        # test alternatives
        self.assertEqual(sub.read('y'),2)
        self.assertEqual(sub.read('y',None),2)
        self.assertEqual(sub.read('u',None),None)
        self.assertEqual(sub('y',None),2)
        self.assertEqual(sub('u',None),None)

        # missing objects
        with self.assertRaises(AttributeError):
            print(sub.x2)
        with self.assertRaises(KeyError):
            print(sub['x2'])
        with self.assertRaises(KeyError):
            print(sub.read('x2',raise_on_error=True))

        # delete & confirm they are gone
        del sub['y']
        sub.delete('z')

        del sub['x'] # silent
        with self.assertRaises(KeyError):
            sub.delete('x',raise_on_error=True)

        # sub dirs
        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", delete_everything=True )
        s1 = sub("subDir1")
        s2 = sub("subDir2/")
        s3 = SubDir("subDir3/",parent=sub)
        s4 = SubDir("subDir4", parent=sub)
        self.assertEqual(s1.path, sub.path + "subDir1/")
        self.assertEqual(s2.path, sub.path + "subDir2/")
        self.assertEqual(s3.path, sub.path + "subDir3/")
        self.assertEqual(s4.path, sub.path + "subDir4/")
        lst = str(sorted(sub.sub_dirs()))
        self.assertEqual(lst, "[]")
        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", delete_everything=True )
        s1 = sub("subDir1", create_directory=True)
        s2 = sub("subDir2/", create_directory=True)
        s3 = SubDir("subDir3/",parent=sub, create_directory=True)
        s4 = SubDir("subDir4", parent=sub, create_directory=True)
        self.assertEqual(s1.path, sub.path + "subDir1/")
        self.assertEqual(s2.path, sub.path + "subDir2/")
        self.assertEqual(s3.path, sub.path + "subDir3/")
        self.assertEqual(s4.path, sub.path + "subDir4/")
        lst = str(sorted(sub.sub_dirs()))
        self.assertEqual(lst, "['subDir1', 'subDir2', 'subDir3', 'subDir4']")

        sub.delete_all_content()
        self.assertEqual(len(sub.files()),0)
        self.assertEqual(len(sub.sub_dirs()),0)
        sub.delete_everything()

        # test vectors
        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", delete_everything=True )
        sub[['y','z']] = [2,3]

        self.assertEqual(sub[['y','z']], [2,3])
        with self.assertRaises(KeyError):
            self.assertEqual(sub[['y','z','r']], [2,3,None])
        self.assertEqual(sub.read(['y','r'],default=None), [2,None])
        self.assertEqual(sub(['y','r'],default=None), [2,None])

        sub.write(['a','b'],1)
        self.assertEqual(sub.read(['a','b']),[1,1])
        with self.assertRaises(ValueError):
            sub.write(['x','y','z'],[1,2])
        sub.delete_everything()

        # test setting ext
        sub1 = "!/.tmp_test_for_cdxcore.subdir"
        fd1  = SubDir(sub1).path
        sub  = SubDir("!/.tmp_test_for_cdxcore.subdir/test;*.bin", delete_everything=True )
        self.assertEqual(sub.path, fd1+"test/")
        fn   = sub.full_file_name("file")
        self.assertEqual(fn,fd1+"test/file.bin")
        sub.delete_everything()
        
        sub1 = sub(ext=".tst")
        self.assertEqual(sub.path,sub1.path)
        self.assertEqual(sub1.full_file_name("test"),sub.path+"test.tst")

        # test versioning
        sub = SubDir("!/.tmp_test_for_cdxcore.subdir")
        version = "1.0.0"
        sub.write("test", "hans", version=version )
        r = sub.read("test", version=version )
        self.assertEqual(r, "hans")
        r = sub.read("test", "nothans", version="2.0.0", delete_wrong_version=False )
        self.assertEqual(r, "nothans")
        self.assertTrue(sub.exists("test"))
        r = sub.is_version("test", version=version )
        self.assertTrue(r)
        r = sub.is_version("test", version="2.0.0" )
        self.assertFalse(r)
        r = sub.read("test", "nothans", version="2.0.0", delete_wrong_version=True )
        self.assertFalse(sub.exists("test"))
        sub.delete_everything()

        # test JSON
        x = np.ones((10,))
        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", fmt=SubDir.JSON_PICKLE )
        sub.write("test", x)
        r = sub.read("test", None, raise_on_error=True)
        r = sub.read("test", None)
        self.assertEqual( list(x), list(r) )
        self.assertEqual(sub.ext, ".jpck")
        sub.delete_everything()

        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", fmt=SubDir.JSON_PLAIN )
        sub.write("test", x)
        r = sub.read("test", None)
        self.assertEqual( list(x), list(r) )
        self.assertEqual(sub.ext, ".json")
        sub.delete_everything()

        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", fmt=SubDir.BLOSC )
        sub.write("test_2", x)
        r = sub.read("test_2", None, raise_on_error=True )
        self.assertEqual( list(x), list(r) )
        self.assertEqual(sub.ext, ".zbsc")
        sub.write("test", x, version="1")
        r = sub.read("test", None, version="1")
        self.assertEqual( list(x), list(r) )
        with self.assertRaises(VersionError):
            r = sub.read("test", None, version="2", raise_on_error=True)
            # wrong version
        sub.delete_everything()

        sub = SubDir("!/.tmp_test_for_cdxcore.subdir", fmt=SubDir.GZIP )
        sub.write("test", x)
        r = sub.read("test", None )
        self.assertEqual( list(x), list(r) )
        self.assertEqual(sub.ext, ".pgz")
        sub.write("test", x, version="1")
        r = sub.read("test", None, version="1")
        self.assertEqual( list(x), list(r) )
        with self.assertRaises(VersionError):
            r = sub.read("test", None, version="2", raise_on_error=True)
            # wrong version
        
    def test_new(self):
        subdir0 = SubDir("my_directory")      # relative to current working directory
        subdir1 = SubDir("./my_directory")    # relative to current working directory
        subdir2 = SubDir("~/my_directory")    # relative to home directory
        subdir3 = SubDir("!/my_directory")    # relative to default temp directory

        subdir11 = SubDir("my_directory", ".")      # relative to home directory
        subdir22 = SubDir("my_directory", "~")      # relative to default temp directory
        subdir33 = SubDir("my_directory", "!")      # relative to current directory
        subdir44 = SubDir("my_directory", subdir3)  # subdir2 is relative to `subdir`
        
        
        self.assertEqual( subdir0.path, subdir11.path )
        self.assertEqual( subdir1.path, subdir11.path )
        self.assertEqual( subdir2.path, subdir22.path )
        self.assertEqual( subdir3.path, subdir33.path )
        self.assertEqual( subdir3.path + "my_directory/", subdir44.path )

        subdir1 = SubDir("?/test")
        subdir2 = SubDir("?/test")
        
        self.assertNotEqual( subdir1.path, subdir2.path )
        del subdir1, subdir2

        # extension handling
        
        subdir = SubDir("!/extension_test", fmt=SubDir.BLOSC )
        self.assertEqual( subdir.ext, ".zbsc" )
        subdir = subdir("", fmt=SubDir.GZIP )
        self.assertEqual( subdir.ext, ".pgz" )
        subdir = subdir("", fmt=SubDir.JSON_PICKLE )
        self.assertEqual( subdir.ext, ".jpck" )
        subdir = subdir("", fmt=SubDir.JSON_PLAIN )
        self.assertEqual( subdir.ext, ".json" )
        subdir = subdir("", fmt=SubDir.PICKLE )
        self.assertEqual( subdir.ext, ".pck" )

        subdir0 = SubDir("!/temp;*.bin")
        subdir1 = SubDir("!/temp", ext="bin")
        subdir2 = SubDir("!/temp", ext=".bin")
        self.assertEqual( subdir0, subdir1 )
        self.assertEqual( subdir0, subdir2 )

        with self.assertRaises(ValueError):
            subdir = SubDir("!/temp;*.bin", ext="notbin")
            
        # version
        
        version = "0.1"
        data = [12,34,56]
        
        def test_format(fmt, excset=False ):
            subdir.write("test", data,  version=version, fmt=fmt )
            _ = subdir.read("test", version=version, fmt=fmt )
            self.assertEqual( data, _ )
            with self.assertRaises(VersionError):
                _ = subdir.read("test", version="x1", fmt=fmt, raise_on_error=True )
                
            # no version error
            subdir.write("test", data, version=version, fmt=fmt )
            
            if not excset:
                # json_pickle throws no exception...
                _ = subdir.read("test", raise_on_error=True, fmt=fmt )
            else:
                with self.assertRaises(VersionPresentError):
                    _ = subdir.read("test", raise_on_error=True, fmt=fmt )

        test_format( SubDir.PICKLE, True )
        test_format( SubDir.BLOSC, True )
        test_format( SubDir.GZIP, True )
        test_format( SubDir.JSON_PICKLE )
        
        # copy constructor with overwrite
        
        d1 = SubDir("?/test_subdir", ext="e1")
        d2 = SubDir(d1)
        self.assertEqual( d1.path, d2.path )
        self.assertEqual( d1.fmt, d2.fmt )
        self.assertEqual( d1.ext, d2.ext )

        d1 = SubDir("?/test_subdir", ext="e1")
        d2 = SubDir(d1, ext="e2")
        self.assertEqual( d1.path, d2.path )
        self.assertEqual( d1.fmt, d2.fmt )
        self.assertEqual( d1.ext, ".e1" )
        self.assertEqual( d2.ext, ".e2" )

        d1 = SubDir("?/test_subdir", fmt=SubDir.BLOSC )
        d2 = SubDir(d1, fmt=SubDir.GZIP )
        self.assertEqual( d1.path, d2.path )
        self.assertEqual( d1.fmt, SubDir.BLOSC )
        self.assertEqual( d2.fmt, SubDir.GZIP )
        self.assertEqual( d1.ext, ".zbsc" )
        self.assertEqual( d2.ext, ".pgz" )

        d1 = SubDir("?/test_subdir", ext="tmp", fmt=SubDir.BLOSC )
        d2 = SubDir(d1, fmt=SubDir.GZIP )
        self.assertEqual( d1.path, d2.path )
        self.assertEqual( d1.fmt, SubDir.BLOSC )
        self.assertEqual( d2.fmt, SubDir.GZIP )
        self.assertEqual( d1.ext, ".tmp" )
        self.assertEqual( d2.ext, d1.ext )

    def test_cache_mode(self):

        on = CacheMode("on")
        gn = CacheMode("gen")
        of = CacheMode("off")
        cl = CacheMode("clear")
        up = CacheMode("update")
        ro = CacheMode("readonly")

        with self.assertRaises(KeyError):
            _ = CacheMode("OFF")

        allc = [on, gn, of, cl, up, ro]

        self.assertEqual( [ x.is_on for x in allc ], [True, False, False, False, False, False ] )
        self.assertEqual( [ x.is_gen for x in allc ], [False, True, False, False, False, False ] )
        self.assertEqual( [ x.is_off for x in allc ], [False, False, True, False, False, False ] )
        self.assertEqual( [ x.is_clear for x in allc ], [False, False, False, True, False, False ] )
        self.assertEqual( [ x.is_update for x in allc ], [False, False, False, False, True, False ] )
        self.assertEqual( [ x.is_readonly for x in allc ], [False, False, False, False, False, True ] )

        self.assertEqual( [ x.read for x in allc ],  [True, True, False, False, False, True] )
        self.assertEqual( [ x.write for x in allc ], [True, True, False, False, True, False] )
        self.assertEqual( [ x.delete for x in allc ], [False, False, False, True, True, False ] )
        self.assertEqual( [ x.del_incomp for x in allc ], [True, False, False, True, True, False ] )            

    def test_unique_hash(self):
        
        self.assertNotEqual( unique_hash16(SubDir.GZIP), unique_hash16(SubDir.PICKLE) ) 

        
        sub  = SubDir("!/test_unique_hash")
        sub2 = SubDir("!/test_unique_hash")
        sub3 = sub2("sub")
        sub4 = sub2(ext="tst")
        sub5 = sub2(fmt=SubDir.GZIP)
        uid  = unique_hash16(sub)
        self.assertEqual(uid, unique_hash16(sub2))
        self.assertNotEqual(uid, unique_hash16(sub3))
        self.assertNotEqual(uid, unique_hash16(sub4))
        self.assertNotEqual(uid, unique_hash16(sub5))
        sub.write("dummy", {})
        self.assertEqual(uid, unique_hash16(sub))
        sub.delete_everything(False)

class A(object):
    def __init__(self, x):
        self.x = x
class B(object):
    def __init__(self, x):
        self.x = x
     
raw_sub = VersionedCacheRoot("?/subdir_cache_test2", exclude_arg_types=[A] )

class C(object):
    def __init__(self, x):
        self.x = x
    @raw_sub.cache("0.1")
    def f(self, y):
        return self.x*y

class Test2(unittest.TestCase):

    def test_cache( self ):
        
        sub = SubDir("!/xx", ext="ABC")
        self.assertEqual( sub.ext, ".ABC")

        sub = VersionedCacheRoot("?/subdir_cache_test", exclude_arg_types=[A] )

        subsub = sub("sub", ext="tst")
        x = subsub.full_file_name( "hallo")
        self.assertEqual( x[-9:], "hallo.tst" )

        @sub.cache("1.0")
        def f(x):
            return x
        
        _ = f(1)
        _ = f(1)
        self.assertTrue( f.cache_info.last_cached )

        @sub.cache("1.0")
        def g(x):
            return x
        
        # a new B object each time -> no caching
        _ = f(B(1))
        _ = f(B(1))
        self.assertTrue( f.cache_info.last_cached )
        _ = f(B(1))
        _ = f(B(2))
        self.assertFalse( f.cache_info.last_cached )
        _ = f(B(1))
        _ = f(B(1), override_cache_mode="clear")
        self.assertFalse( f.cache_info.last_cached )

        # same B object each time -> no caching
        _ = f(B(1))
        _ = f(B(1))
        self.assertTrue( f.cache_info.last_cached )
        _ = f(B(1), cache_generate_only=True)
        self.assertEqual(_, False ) # was not generated
        self.assertTrue( f.cache_info.last_cached )
        _ = f(B(3), cache_generate_only=True)
        self.assertFalse( f.cache_info.last_cached )
        self.assertEqual(_, True ) # was not generated

        with self.assertRaises(ValueError):
            _ = f(B(2), cache_generate_only=True, override_cache_mode="clear")
        _ = f(B(23), override_cache_mode="readonly")
        _ = f(B(23))
        self.assertFalse( f.cache_info.last_cached )
                
        # a new A object each time -> caching, as we ignore 'A' types
        _ = f(A(1))
        _ = f(A(2))
        self.assertTrue( f.cache_info.last_cached )
        
        @sub.cache("1.0", label=lambda x: f"f({x})")
        def f(x):
            return x
        
        _ = f(1)
        self.assertEqual( f.cache_info.filename[:5], "f(1) " )
        uid, _ = f(1, return_cache_uid=True)
        self.assertEqual( uid[:5], "f(1) " )
        
        @sub.cache("1.0", uid=lambda x: f"f({x})")
        def f(x):
            return x
        
        _ = f(1)
        self.assertEqual( f.cache_info.filename, "f(1)" )
        uid, _ = f(1, return_cache_uid=True)
        self.assertEqual( uid, "f(1)" )
        
        # test member caching
        
        c = C(2.)
        _ = c.f(y=3)
        self.assertFalse( c.f.cache_info.last_cached )
        _ = c.f(3)
        self.assertTrue( c.f.cache_info.last_cached )
        _ = c.f(2)
        self.assertFalse( c.f.cache_info.last_cached )
        
        # test versioning
        
        @version("F")
        def F(x):
            return x
        
        @sub.cache("G")
        def G(x):
            return x
        
        @sub.cache("H", dependencies=[F,G])
        def H(x):
            return G(x)*F(x)

        _ = H(2.)
        self.assertEqual( H.cache_info.version, "H { Test2.test_cache.<locals>.F: F, Test2.test_cache.<l 19b17778" )        
        self.assertEqual( H.cache_info.version, H.version.unique_id64 )        

        # decorate live member functions
        
        class AA(object):
            def __init__(self,x):
                self.x = x
            def afa(self,y):
                return self.x*y
        
        a = AA(x=1)
        faa = sub.cache("0.1", label=lambda y : f"a.f({y})")(a.afa)  # <- decorate bound 'f'.
        _ = faa(y=2)  
        self.assertFalse( faa.cache_info.last_cached )
        self.assertEqual( faa.cache_info.version, "0.1" )
        _ = faa(y=2)  
        self.assertTrue( faa.cache_info.last_cached )
                
        # funcname

        sub = VersionedCacheRoot("?/subdir_cache_test", exclude_arg_types=[A], keep_last_arguments=True)
        
        @sub.cache("0.1", label=lambda new_func_name, func_name, x, y : f"{new_func_name}(): {func_name} {x} {y}", name_of_func_name_arg="new_func_name")
        def f( func_name, x, y ):
            pass
        f("test",1,y=2)
        self.assertTrue( isinstance(f.cache_info, CacheInfo))
        self.assertTrue( list(f.cache_info.arguments.keys()) == ['func_name', 'x', 'y'] )
        self.assertTrue( list(f.cache_info.arguments.values()) == ['test', '1', '2'] )
        
        # this should just work
        @sub.cache("0.1", label=lambda func_name, x : f"{func_name} {x}")
        def f( func_name, x ):
            pass
        with self.assertRaises(RuntimeError):
            f("test",1)        
            
        # cuttinf off
        @sub.cache("0.1", uid=lambda x,y: f"h2({x},{y})_______________________________________________________________________", exclude_args='debug') 
        def h2(x,y,debug=False):
            if debug:
                print(f"h(x={x},y={y})")  
            return x*y
        h2(1,1)
        self.assertEqual( h2.cache_info.filename, "h2(1,1)________________________________ 46a70d67" )

        with self.assertRaises(RuntimeError):
            # using 'func_name' as parameter
            @sub.cache("0.1", label=lambda func_name, x : f"{func_name} {x}")
            def f( func_name, x ):
                pass
            f("test",1)
            
        with self.assertRaises(ValueError):
            # 'z' does not exist
            @sub.cache("0.1", label=lambda x, z : f"x={x}, z={x}")
            def f(x,y):
                return x*y
            _ = f(1,2)
            
        
    def test_cache_subdir(self):
        
        @version("0.1")
        def f( x ):
            return x*2
        @version("0.1")
        def h(x,y):
            return x*y

        root = SubDir("?/cache_test")

        f_1 = root.cache()(f)
        f_1(2)
        self.assertEqual(f_1.cache_info.path[-11:], "cache_test/")
        
        f_2 = root.cache( in_sub_dir=lambda x : f"D{x:d}")(f)
        f_2(2)
        self.assertEqual(f_2.cache_info.path[-14:], "cache_test/D2/")

        f_3 = root.cache( label=lambda x, func_name : f"E{x:d}/{func_name} {x}")(f)
        f_3(2)
        self.assertEqual(f_3.cache_info.path[-14:], "cache_test/E2/")

        f_4 = root.cache( in_sub_dir="D{x}", label=lambda x, func_name : f"E{x:d}/{func_name} {x}")(f)
        f_4(2)
        self.assertEqual(f_4.cache_info.path[-17:], "cache_test/D2/E2/")

        h1 = root.cache( uid=lambda x,y : f"{x}/{y}")(h)
        h1(2,3)
        self.assertEqual(h1.cache_info.path[-13:], "cache_test/2/")
        self.assertEqual(h1.cache_info.filename, "3")
        self.assertEqual(h1.cache_info.unique_id, "2/3")

        h1 = root.cache( label=lambda x,y : f"{x}/{y}")(h)
        h1(2,3)
        self.assertEqual(h1.cache_info.path[-13:], "cache_test/2/")
        self.assertEqual(h1.cache_info.filename, "3 b5bb289e")
        self.assertEqual(h1.cache_info.unique_id, "2/3 b5bb289e")

        # invalid file names
        with self.assertRaises(ValueError):
            h1 = root.cache( uid=lambda x,y : f"{x}:/{y}")(h)
            h1(2,3)
        # invalid file names
        with self.assertRaises(ValueError):
            h1 = root.cache( uid=lambda x,y : f"{x}\\/{y}")(h)
            h1(2,3)

        h1 = root.cache( label=lambda x,y : f"{x}:/{y}")(h)
        h1(2,3)
        self.assertEqual(h1.cache_info.path[-14:], "cache_test/2;/")
        self.assertEqual(h1.cache_info.filename, "3 b5bb289e")
        self.assertEqual(h1.cache_info.unique_id, "2;/3 b5bb289e")

        h1 = root.cache( label=lambda x,y : f"{x}\\/{y}")(h)
        h1(2,3)
        self.assertEqual(h1.cache_info.path[-14:], "cache_test/2_/")
        self.assertEqual(h1.cache_info.filename, "3 b5bb289e")
        self.assertEqual(h1.cache_info.unique_id, "2_/3 b5bb289e")
        
    def test_cache_version(self):
        """ version changes """
        
        sub = SubDir("?/.tmp_test_edge_cases", delete_everything=True) #, cache_controller=CacheController(debug_verbose=Context("all")))
        try:
            def f(x, uid="f"):
                return dict(x=x)

            f1 = sub.cache("0.1")(f)
            _  = f1(1)
            self.assertEqual(f1.cache_info.last_cached, False)
            _  = f1(1)
            self.assertEqual(f1.cache_info.last_cached, True)

            def f(x, uid="f"):
                return dict(x=x)
            f1 = sub.cache("0.2")(f)
            _  = f1(1)
            self.assertEqual(f1.cache_info.last_cached, False)

        finally:
            sub.delete_everything()

    def test_subdir_edge_cases(self):
        """Test edge cases in SubDir functionality"""
        
        sub = SubDir("?/.tmp_test_edge_cases", delete_everything=True)
        try:
            # Test with special characters in filenames
            sub["test-file"] = "value1"
            self.assertEqual(sub["test-file"], "value1")
            
            # Test overwriting values
            sub["test"] = 1
            sub["test"] = 2
            self.assertEqual(sub["test"], 2)
            
            # Test with numpy arrays
            arr = np.array([1, 2, 3, 4, 5])
            sub["array"] = arr
            loaded_arr = sub["array"]
            self.assertTrue(np.array_equal(arr, loaded_arr))
            
            # Test with nested structures
            nested = {"a": {"b": {"c": 42}}}
            sub["nested"] = nested
            self.assertEqual(sub["nested"], nested)
            
            # Test exists method
            self.assertTrue(sub.exists("array"))
            self.assertFalse(sub.exists("nonexistent"))
            
            # Test file listing with different extensions
            sub_txt = SubDir("?/.tmp_test_txt", ext="txt", delete_everything=True)
            sub_txt.write_string("note1", "Hello")
            sub_txt.write_string("note2", "World")
            txt_files = sorted(sub_txt.files())
            self.assertIn("note1", txt_files)
            self.assertIn("note2", txt_files)
            sub_txt.delete_everything()
            
            # Test as_dict conversion
            d_items = sub.as_dict() if hasattr(sub, 'as_dict') else sub
            if isinstance(d_items, dict):
                self.assertIn("array", d_items)
                self.assertIn("nested", d_items)
            
        finally:
            sub.delete_everything()

    def test_polars(self):
        
        sub = SubDir("?/.tmp_test_edge_cases", delete_everything=True, fmt=SubDir.POLARS_PARQUET )
        self.assertEqual(sub.ext,".prq")
        try:
            np.random.seed(21232)
            x = np.random.normal(size=(20,)).astype(np.int32)
            y = np.random.normal(size=(20,)).astype(np.int32)
            
            df = pl.DataFrame( {'x': pl.Series( x, dtype=pl.Int32 ), 'y' : pl.Series( y, dtype=pl.Int32 ) } )
        
            sub.write("test", df)        
            r = sub.read("test", raise_on_error=True)
            self.assertTrue( np.all( r==df) )
            
            sub.write("test", df, version="0.1")        
            r = sub.read("test", version="0.1", raise_on_error=True)
            self.assertTrue( np.all( r==df) )

            sub.write("test", df, version="0.1")        
            r = sub.read("test", version="*", raise_on_error=True)
            self.assertTrue(np.all( r==df) )

            sub.write("test", df, version="0.1")   
            with self.assertRaises(VersionError):
                r = sub.read("test", version="0.2", raise_on_error=True)

            with self.assertRaises(ValueError):
                sub.write("test", [1,2,3], raise_on_error=True ) # attempt to write non-polar object
                
            sub.write("test", [1,2,3], fmt=SubDir.PICKLE, ext="prq") # hard overwrite format         
            with self.assertRaises(KeyError):
                sub.read("test", raise_on_error=True)            
        
        finally:
            sub.delete_everything()

    def test_subdir_file_operations(self):
        """Test various file operations in SubDir"""
        
        sub = SubDir("?/.tmp_test_file_ops", delete_everything=True)
        try:
            # Test write and read with defaults
            self.assertIsNone(sub.read("missing", None))
            
            # Test batch operations
            sub.write(["a", "b", "c"], [1, 2, 3])
            result = sub.read(["a", "b", "c"])
            self.assertEqual(result, [1, 2, 3])
            
            # Test update operations
            sub["x"] = {"old": "value"}
            sub["x"] = {"new": "value"}
            self.assertEqual(sub["x"], {"new": "value"})
            
            # Test deletion
            sub["temp"] = "temporary"
            self.assertTrue(sub.exists("temp"))
            del sub["temp"]
            self.assertFalse(sub.exists("temp"))
            
        finally:
            sub.delete_everything()
if __name__ == '__main__':
    unittest.main()