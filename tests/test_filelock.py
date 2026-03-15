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
import numpy as np
import datetime as datetime
from zoneinfo import ZoneInfo

from cdxcore.filelock import FileLock

class Test(unittest.TestCase):

    def test_fl(self):
        
        fn   = "filelock_test"
        lock = FileLock("!/"+fn,acquire=True, wait=False)
        self.assertTrue( lock.locked )
        self.assertEqual( lock.filename[-len(fn):], fn )
        self.assertEqual( lock.num_acquisitions, 1 )
        lock.acquire(wait=False)
        self.assertEqual( lock.num_acquisitions, 2 )
        lock.release()
        self.assertEqual( lock.num_acquisitions, 1 )
        
        with self.assertRaises(BlockingIOError):
            _ = FileLock("!/"+fn,acquire=True, wait=False)
        with self.assertRaises(TimeoutError):
            _ = FileLock("!/"+fn,acquire=True, wait=True, timeout_seconds=0.1, timeout_retry=1)
            
        lock.release()
        
        lock = FileLock("!/"+fn,acquire=True, wait=False)
        l2   = FileLock("!/"+fn,acquire=False, wait=False)
        self.assertFalse( l2.locked )
        with self.assertRaises(BlockingIOError):
            l2.acquire(wait=False)
        with self.assertRaises(TimeoutError):
            l2.acquire(wait=True, timeout_seconds=0.1, timeout_retry=1)


if __name__ == '__main__':
    unittest.main()
