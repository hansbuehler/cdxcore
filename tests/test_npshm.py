# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""


import unittest as unittest
import sys as sys
import platform as platform
import gc as gc
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

from cdxcore.npshm import create_shared_array, attach_shared_array, read_shared_array, delete_shared_array
from cdxcore.npio import to_file
from cdxcore.subdir import SubDir
import numpy as np

class Test(unittest.TestCase):

    def test_npi(self):

        sub = SubDir("?;*.bin", delete_everything_upon_exit=True )
        try:
            np.random.seed(1231)
    
            test_name = f"npshm test {np.random.randint(0x100**2)}"
            test = create_shared_array( test_name, shape=(10,3), dtype=np.int32, force=False, full=0 )
            
            with self.assertRaises(FileExistsError):
                test = create_shared_array( test_name, shape=(11,3), dtype=np.int32, force=False )

            verf = attach_shared_array( test_name, validate_dtype=test.dtype, validate_shape=test.shape, read_only=True )
            self.assertTrue( np.all( verf==test ))
            test[:4,2] = 1
            self.assertTrue( np.all( verf==test ))
    
            with self.assertRaises(FileNotFoundError):
                _ = attach_shared_array( test_name + "xxx" )
                
            # delete under linux
            
            if platform.system()[0].upper() == "L":
                delete_shared_array( test_name )
                
                # existing links still work
                self.assertTrue( np.all( verf==test ))
                test[:4,1] = 2
                self.assertTrue( np.all( verf==test ))
    
                with self.assertRaises(FileNotFoundError):
                    # fails - shared file is removed
                    _ = attach_shared_array( test_name, read_only=True )
                    del _
                
            del test
            del verf
            gc.collect()
    
            # reading files 
            array = (np.random.normal(size=(1000,3))*100.).astype(np.int32)
            
            sub   = SubDir("?;*.bin", delete_everything_upon_exit=True )
            file  = sub.full_file_name("test_read_shared")
            
            to_file( file, array )
            
            _ = read_shared_array( file, name="test_reading_files" )
            self.assertTrue( np.all( _==array ) )
            
            del _, array
            gc.collect()


        finally:
            sub.delete_everything(keep_directory=False)
            
            
if __name__ == '__main__':
    unittest.main()


