# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest as unittest

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

from cdxcore.crman import CRMan

class Test(unittest.TestCase):

    def test_crman(self):
        
        crman = CRMan()
        self.assertEqual( crman("test"), "test" )
        self.assertEqual( crman("test"), "\r    \r\x1b[2K\rtesttest" )
        self.assertEqual( crman("\rxxxx"), "\r        \r\x1b[2K\rxxxx" )
        self.assertEqual( crman("yyyy\n"), "\r    \r\x1b[2K\rxxxxyyyy\n" )
        self.assertEqual( crman("ab\rcde\nxyz\r01\nt"), "cde\n01\nt" )
        
        self.assertEqual( crman.current, "t" )
        crman.reset()
        self.assertEqual( crman.current, "" )
            
if __name__ == '__main__':
    unittest.main()


