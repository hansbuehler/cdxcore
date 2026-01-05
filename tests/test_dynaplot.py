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
globals()["IS_DYNAPLOT_TEST_RUN"] = True
from cdxcore.dynaplot import m_o_m
import numpy as np

class Test(unittest.TestCase):
    
    def test_version(self):
        # test dependency
        np.random.seed( 12123123 )
        x = np.random.normal(size=(10,))
        y = np.random.normal(size=(8,2))
        z = [ np.random.normal(size=(3,2)), 0.1, None ]
        r = m_o_m(x,y,z)
        r = tuple( int(ri*100) for ri in r)
        
        self.assertEqual( r, (-288, 314))
        
if __name__ == '__main__':
    unittest.main()


