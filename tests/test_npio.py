# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""


import unittest as unittest
import sys as sys
sys.setrecursionlimit(1000)

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

from cdxcore.npio import _DTYPE_TO_CODE, _CODE_TO_DTYPE, to_file, read_into, from_file
from cdxcore.subdir import SubDir
import numpy as np

class Test(unittest.TestCase):

    def test_npi(self):

        sub = SubDir("?;*.bin", delete_everything_upon_exit=True )
        try:
            np.random.seed(1231)
    
            array = (np.random.normal(size=(1000,3))*100.).astype(np.int32)
            file  = sub("test", create_directory=True).full_file_name("test")
            
            to_file( file, array )
            
            test = from_file( file )
            self.assertTrue( np.all( test==array ) )

            test = from_file( file, validate_dtype=np.int32 )
            self.assertTrue( np.all( test==array ) )

            test = from_file( file, validate_shape=(1000,3) )
            self.assertTrue( np.all( test==array ) )
            
            test = from_file( file, read_only=True )
            self.assertTrue( np.all( test==array ) )
            with self.assertRaises(ValueError):
                test[0,0] = 2

            with self.assertRaises(OSError):
                test = from_file( file, validate_dtype=np.float32 )
            with self.assertRaises(OSError):
                test = from_file( file, validate_shape=(3,1000) )
                
            test = np.empty( (1000,3), dtype=np.int32 )
            read_into( file, test )

            test = np.empty( (1000,3), dtype=np.float32 )
            with self.assertRaises(OSError):
                read_into( file, test )

            test = np.empty( (3,1000), dtype=np.int32 )
            with self.assertRaises(OSError):
                read_into( file, test )

            # continuous memory?
            array = np.zeros((4,4), dtype=np.int8)
            for i in range(array.shape[-1]):
                array[:,i] = i
            
            x = array[:,1]
            self.assertFalse( x.data.contiguous )
            with self.assertRaises(RuntimeError):
                to_file( file, x )
            to_file( file, x, cont_block_size_mb=100 )

        finally:
            sub.delete_everything(keep_directory=False)
            
            
if __name__ == '__main__':
    unittest.main()


