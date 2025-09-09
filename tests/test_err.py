# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest as unittest
import warnings as warnings

def import_local():
    """
    In order to be able to run our tests manually from the 'tests' directory
    we force import from the local package.
    We also force reloading all modules to make sure we are not running old code.
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

    # reload modules
    import importlib as imp
    modules = sys.modules.copy()
    for name, mdata in modules.items():
        if name[:len(me)] == me:
            imp.reload(mdata)
            print("Reloaded", name)
#import_local()

from cdxcore.err import fmt, error, verify, warn, warn_if

class Test(unittest.TestCase):

    def test_fmt(self):

        self.assertEqual(fmt("number %d %d",1,2),"number 1 2")
        self.assertEqual(fmt("number %(two)d %(one)d",one=1,two=2),"number 2 1")
        self.assertEqual(fmt("number {two:d} {one:d}",one=1,two=2),"number 2 1")
        self.assertEqual(fmt("number {two:s} {one:d}",one=1,two="II"),"number II 1")
        with self.assertRaises(KeyError):
            fmt("one {two/2:d} also one {one:d}",one=1,two=2)
        one_ = 1
        two_ = 2
        self.assertEqual(fmt(lambda : f"one {one_} also one {two_//2}"),"one 1 also one 1")
        self.assertEqual(fmt(lambda one, two: f"one {one} also one {two//2}", one=1, two=2),"one 1 also one 1")

        with self.assertRaises(KeyError):
            fmt("number %(two)d %(one)d",one=1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1,2,3)
        with self.assertRaises(TypeError):
            fmt("number $(one)d",1)
        with self.assertRaises(ValueError):
            fmt("number %d %(one)d",2,one=1)

        with self.assertRaises(ValueError):
            error("one {one} two {two}", one=1, two=2, exception=ValueError)
        with self.assertRaises(TypeError):
            error("one {one} two {two}", one=1, two=2, exception=TypeError)
        with self.assertRaises(TypeError):
            verify(False,"one {one} two {two}", one=1, two=2, exception=TypeError)
        verify(True,"one {one} two {two}", one=1, two=2, exception=TypeError)

        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=UserWarning)
            warnings.filterwarnings("error", category=RuntimeWarning)

            with self.assertRaises(UserWarning):
                warn("one {one} two {two}", one=1, two=2, warning=UserWarning)
            with self.assertRaises(RuntimeWarning):
                warn("one {one} two {two}", one=1, two=2, warning=RuntimeWarning)
            with self.assertRaises(RuntimeWarning):
                warn_if(True,"one {one} two {two}", one=1, two=2, warning=RuntimeWarning)
            warn_if(False,"one {one} two {two}", one=1, two=2, warning=RuntimeWarning)

if __name__ == '__main__':
    unittest.main()


