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
            
    def test_npshm_edge_cases(self):
        """Test edge cases in shared memory numpy arrays"""
        
        sub = SubDir("?;*.bin", delete_everything_upon_exit=True )
        try:
            np.random.seed(1234)
            
            # Test 1D shared array
            test_name_1d = f"test_1d_{np.random.randint(0x100**2)}"
            array_1d = create_shared_array(test_name_1d, shape=(100,), dtype=np.float32, force=True, full=0)
            array_1d[:] = np.arange(100, dtype=np.float32)
            
            attached_1d = attach_shared_array(test_name_1d, read_only=True)
            self.assertTrue(np.allclose(attached_1d, array_1d))
            
            # Test 3D shared array
            test_name_3d = f"test_3d_{np.random.randint(0x100**2)}"
            array_3d = create_shared_array(test_name_3d, shape=(10, 20, 5), dtype=np.int32, force=True, full=-1)
            self.assertTrue(np.all(array_3d == -1))
            
            attached_3d = attach_shared_array(test_name_3d, validate_shape=(10, 20, 5), validate_dtype=np.int32)
            self.assertEqual(attached_3d.shape, (10, 20, 5))
            
            # Test different dtypes
            for dtype in [np.float32, np.int32, np.uint32, np.float64]:
                test_name = f"test_{dtype.__name__}_{np.random.randint(0x100**2)}"
                arr = create_shared_array(test_name, shape=(5, 5), dtype=dtype, force=True, full=1)
                self.assertEqual(arr.dtype, dtype)
                attached = attach_shared_array(test_name, validate_dtype=dtype)
                self.assertEqual(attached.dtype, dtype)
            
            # Test shape validation
            test_name_validate = f"test_validate_{np.random.randint(0x100**2)}"
            _ = create_shared_array(test_name_validate, shape=(15, 10), dtype=np.int32, force=True)
            
            # Should succeed with correct shape
            attached_validate = attach_shared_array(test_name_validate, validate_shape=(15, 10))
            self.assertEqual(attached_validate.shape, (15, 10))
            
            # Should fail with wrong shape
            with self.assertRaises((OSError, ValueError)):
                attach_shared_array(test_name_validate, validate_shape=(10, 15))
            
            # Test read_only access prevents modification
            test_name_readonly = f"test_readonly_{np.random.randint(0x100**2)}"
            array_rw = create_shared_array(test_name_readonly, shape=(5, 5), dtype=np.int32, force=True)
            array_rw[:] = 42
            
            array_ro = attach_shared_array(test_name_readonly, read_only=True)
            self.assertTrue(np.all(array_ro == 42))
            
            # Modifying array_rw should still be visible in read_only version
            array_rw[0, 0] = 99
            self.assertEqual(array_ro[0, 0], 99)
            
        finally:
            sub.delete_everything(keep_directory=False)
            
if __name__ == '__main__':
    unittest.main()

