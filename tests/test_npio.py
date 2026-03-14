# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import import_local # for local testing
import unittest as unittest
import sys as sys
sys.setrecursionlimit(1000)


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
            
    def test_npio_edge_cases(self):
        """Test edge cases in numpy binary I/O"""
        
        sub = SubDir("?;*.bin", delete_everything_upon_exit=True )
        try:
            # Test all supported dtypes
            for dtype_name, dtype_code in _DTYPE_TO_CODE.items():
                if dtype_name in ['bool', 'int8', 'int16', 'int32', 'int64', 
                                  'uint16', 'uint32', 'uint64', 'float32', 'float64']:
                    dtype = _CODE_TO_DTYPE[dtype_code]
                    array = np.array([1, 2, 3], dtype=dtype)
                    file = sub(f"test_{dtype_name}", create_directory=True).full_file_name("test")
                    
                    to_file(file, array)
                    result = from_file(file)
                    self.assertEqual(result.dtype, dtype)
                    self.assertTrue(np.all(result == array))
            
            # Test 1D arrays
            array = np.array([1, 2, 3, 4, 5], dtype=np.int32)
            file = sub("test_1d", create_directory=True).full_file_name("test")
            to_file(file, array)
            result = from_file(file)
            self.assertEqual(result.shape, (5,))
            self.assertTrue(np.all(result == array))
            
            # Test 3D arrays
            array = np.random.randint(0, 100, (5, 4, 3), dtype=np.int32)
            file = sub("test_3d", create_directory=True).full_file_name("test")
            to_file(file, array)
            result = from_file(file)
            self.assertEqual(result.shape, (5, 4, 3))
            self.assertTrue(np.all(result == array))
            
            # Test read_only mode prevents modification
            array = np.array([1, 2, 3], dtype=np.int32)
            file = sub("test_ro", create_directory=True).full_file_name("test")
            to_file(file, array)
            read_only_array = from_file(file, read_only=True)
            with self.assertRaises(ValueError):
                read_only_array[0] = 999
            
            # Test large array
            large_array = np.random.randint(0, 1000, (100, 100, 10), dtype=np.int32)
            file = sub("test_large", create_directory=True).full_file_name("test")
            to_file(file, large_array)
            result = from_file(file)
            self.assertEqual(result.shape, (100, 100, 10))
            self.assertTrue(np.all(result == large_array))
            
            # Test float arrays with NaN and Inf
            float_array = np.array([1.0, np.nan, np.inf, -np.inf, 0.0], dtype=np.float32)
            file = sub("test_float", create_directory=True).full_file_name("test")
            to_file(file, float_array)
            result = from_file(file)
            # Note: NaN comparison is special
            self.assertTrue(np.isnan(result[1]))
            self.assertTrue(np.isinf(result[2]))
            self.assertTrue(np.isinf(result[3]))
            self.assertEqual(result[0], 1.0)
            self.assertEqual(result[4], 0.0)
            
        finally:
            sub.delete_everything(keep_directory=False)
            
if __name__ == '__main__':
    unittest.main()

