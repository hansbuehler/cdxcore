# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest as unittest
import numpy as np
import datetime as datetime
from zoneinfo import ZoneInfo

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
#import_local()

from cdxcore.util import is_function, is_atomic, is_float, is_filename
from cdxcore.util import fmt, fmt_seconds, fmt_list, fmt_dict, fmt_big_number, fmt_digits, fmt_big_byte_number, fmt_datetime, fmt_date, fmt_time, fmt_timedelta, fmt_filename, DEF_FILE_NAME_MAP

class Test(unittest.TestCase):

    def test_fmt(self):

        self.assertEqual(fmt("number %d %d",1,2),"number 1 2")
        self.assertEqual(fmt("number %(two)d %(one)d",one=1,two=2),"number 2 1")

        with self.assertRaises(KeyError):
            fmt("number %(two)d %(one)d",one=1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1,2,3)
    
        # fmt_seconds
        self.assertEqual(fmt_seconds(10.212),"10s")  
        self.assertEqual(fmt_seconds(1.0212),"1s")  
        self.assertEqual(fmt_seconds(0.10212),"0.1s")  
        self.assertEqual(fmt_seconds(0.0010212),"1.02ms")  
    
        # fmt_list
        self.assertEqual(fmt_list([2,5.,3]), "2, 5.0 and 3")
        self.assertEqual(fmt_list([2,5.,3],link=""), "2, 5.0, 3")
        self.assertEqual(fmt_list([2,5.,3],link=","), "2, 5.0, 3")
        self.assertEqual(fmt_list([2,5.,3],link=", and"), "2, 5.0, and 3")
        self.assertEqual(fmt_list(sorted([2,5.,3])), "2, 3 and 5.0")
        self.assertEqual(fmt_list([2,5.,3],sort=True), "2, 3 and 5.0")
        self.assertEqual(fmt_list(i for i in [2,3,5.]), "2, 3 and 5.0")
        self.assertEqual(fmt_list([1.]), "1.0")
        self.assertEqual(fmt_list([]), "-")
        self.assertEqual(fmt_list([], none="X"), "X")
        
        # fmt_dict
        self.assertEqual(fmt_dict( dict(y=2, x=1, z=3) ),"y: 2, x: 1 and z: 3")
        self.assertEqual(fmt_dict( dict(y=2, x=1, z=3), sort=True ),"x: 1, y: 2 and z: 3")
        self.assertEqual(fmt_dict( dict(y=2, x=1, z=3), sort=True, link=", and" ),"x: 1, y: 2, and z: 3")

        # fmt_big_number
        self.assertEqual(fmt_digits(1), "1")
        self.assertEqual(fmt_digits(0), "0")
        self.assertEqual(fmt_digits(-1), "-1")
        self.assertEqual(fmt_digits(999), "999")
        self.assertEqual(fmt_digits(1000), "1,000")
        self.assertEqual(fmt_digits(1001), "1,001")
        self.assertEqual(fmt_digits(9999), "9,999")
        self.assertEqual(fmt_digits(10000), "10,000")
        self.assertEqual(fmt_digits(123456789), "123,456,789")
        self.assertEqual(fmt_digits(-123456789), "-123,456,789")

        # fmt_big_number
        self.assertEqual(fmt_big_number(1), "1")
        self.assertEqual(fmt_big_number(999), "999")
        self.assertEqual(fmt_big_number(1000), "1000")
        self.assertEqual(fmt_big_number(1001), "1001")
        self.assertEqual(fmt_big_number(9999), "9999")
        self.assertEqual(fmt_big_number(10000), "10K")
        self.assertEqual(fmt_big_number(10001), "10K")
        self.assertEqual(fmt_big_number(10010), "10.01K")
        self.assertEqual(fmt_big_number(10100), "10.1K")
        self.assertEqual(fmt_big_number(12345), "12.35K")
        self.assertEqual(fmt_big_number(123456789), "123.46M")
        self.assertEqual(fmt_big_number(12345678912), "12.35B")
        self.assertEqual(fmt_big_number(1234567890123456789), "1,234,567.89T")
        self.assertEqual(fmt_big_number(-123456789), "-123.46M")
    
        # fmt_big_byte_number
        self.assertEqual(fmt_big_byte_number(0), "0 bytes")
        self.assertEqual(fmt_big_byte_number(1), "1 byte")
        self.assertEqual(fmt_big_byte_number(2), "2 bytes")
        self.assertEqual(fmt_big_byte_number(-1), "-1 byte")
        self.assertEqual(fmt_big_byte_number(-2), "-2 bytes")
        self.assertEqual(fmt_big_byte_number(1024*10-1), "10239 bytes")
        self.assertEqual(fmt_big_byte_number(1024*10), "10KB")
        self.assertEqual(fmt_big_byte_number(1024*10+1), "10KB")
        self.assertEqual(fmt_big_byte_number(1024*10+10), "10.01KB")
        self.assertEqual(fmt_big_byte_number(12345), "12.06KB")
        self.assertEqual(fmt_big_byte_number(123456789), "117.74MB")
        self.assertEqual(fmt_big_byte_number(12345678912), "11.5GB")
        self.assertEqual(fmt_big_byte_number(1234567890123456789), "1,122,832.96TB")
        self.assertEqual(fmt_big_byte_number(-123456789), "-117.74MB")

        self.assertEqual(fmt_big_byte_number(0,str_B=False), "0")
        self.assertEqual(fmt_big_byte_number(1,str_B=False), "1")
        self.assertEqual(fmt_big_byte_number(2,str_B=False), "2")
        self.assertEqual(fmt_big_byte_number(-1,str_B=False), "-1")
        self.assertEqual(fmt_big_byte_number(-2,str_B=False), "-2")
        self.assertEqual(fmt_big_byte_number(1024*10-1,str_B=False), "10239")
        self.assertEqual(fmt_big_byte_number(1024*10,str_B=False), "10K")
        self.assertEqual(fmt_big_byte_number(1024*10+1,str_B=False), "10K")
        self.assertEqual(fmt_big_byte_number(1024*10+10,str_B=False), "10.01K")
        self.assertEqual(fmt_big_byte_number(12345,str_B=False), "12.06K")
        self.assertEqual(fmt_big_byte_number(123456789,str_B=False), "117.74M")
        self.assertEqual(fmt_big_byte_number(12345678912,str_B=False), "11.5G")
        self.assertEqual(fmt_big_byte_number(1234567890123456789,str_B=False), "1,122,832.96T")
        self.assertEqual(fmt_big_byte_number(-123456789,str_B=False), "-117.74M")
        
        # fmt_datetime
        tz  = ZoneInfo("America/New_York")
        tz2 = ZoneInfo("Asia/Tokyo")
        tz3 = ZoneInfo("GMT")
        plain = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3 )
        timz  = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, tzinfo=tz )
        micro = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=3232 )
        lots  = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=3232, tzinfo=tz )
        lots2 = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=0, tzinfo=tz2 )
        lots3 = datetime.datetime( year=1974, month=3, day=17, hour=16, minute=2, second=3, microsecond=0, tzinfo=tz3 )
        self.assertEqual(plain.tzinfo,None)
        self.assertNotEqual(lots.tzinfo,None)
        self.assertEqual(fmt_datetime(plain), "1974-03-17 16:02:03")
        self.assertEqual(fmt_datetime(plain, sep=''), "1974-03-17 160203")
        self.assertEqual(fmt_datetime(plain.date()), "1974-03-17")
        self.assertEqual(fmt_datetime(plain.time()), "16:02:03")
        self.assertEqual(fmt_datetime(micro), "1974-03-17 16:02:03,3232")
        self.assertEqual(fmt_datetime(micro,ignore_ms=True), "1974-03-17 16:02:03")
        self.assertEqual(fmt_datetime(micro.date()), "1974-03-17")
        self.assertEqual(fmt_datetime(micro.time()), "16:02:03,3232")
        self.assertEqual(fmt_datetime(timz), "1974-03-17 16:02:03")
        self.assertEqual(fmt_datetime(timz.date()), "1974-03-17")
        self.assertEqual(fmt_datetime(timz.time()), "16:02:03")
        self.assertEqual(fmt_datetime(timz.timetz()), "16:02:03")
        self.assertEqual(fmt_datetime(timz.timetz(),ignore_tz=False), "16:02:03")
        self.assertEqual(fmt_datetime(lots), "1974-03-17 16:02:03,3232")
        self.assertEqual(fmt_datetime(lots,ignore_ms=True), "1974-03-17 16:02:03")
        self.assertEqual(fmt_datetime(lots.date()), "1974-03-17")
        self.assertEqual(fmt_datetime(lots.time()), "16:02:03,3232")
        self.assertEqual(fmt_datetime(lots.timetz()), "16:02:03,3232")
        self.assertEqual(fmt_datetime(lots,ignore_tz=False), "1974-03-17 16:02:03,3232-4")
        self.assertEqual(fmt_datetime(lots,ignore_ms=True,ignore_tz=False), "1974-03-17 16:02:03-4")
        self.assertEqual(fmt_datetime(lots.date(),ignore_tz=False), "1974-03-17")
        self.assertEqual(fmt_datetime(lots.time(),ignore_tz=False), "16:02:03,3232") # timezone for time's is not supported
        self.assertEqual(fmt_datetime(lots.timetz(),ignore_tz=False), "16:02:03,3232") # timezone for time's is not supported
        self.assertEqual(fmt_datetime(lots2,ignore_tz=False), "1974-03-17 16:02:03+9")
        self.assertEqual(fmt_datetime(lots2,ignore_ms=True,ignore_tz=False), "1974-03-17 16:02:03+9")
        self.assertEqual(fmt_datetime(lots2.date(),ignore_tz=False), "1974-03-17")
        self.assertEqual(fmt_datetime(lots2.timetz(),ignore_tz=False), "16:02:03") # timezone for time's is not supported
        self.assertEqual(fmt_datetime(lots3,ignore_tz=False), "1974-03-17 16:02:03")
        self.assertEqual(fmt_datetime(lots3,ignore_ms=True,ignore_tz=False), "1974-03-17 16:02:03")
        self.assertEqual(fmt_datetime(lots3.date(),ignore_tz=False), "1974-03-17")
        self.assertEqual(fmt_datetime(lots3.timetz(),ignore_tz=False), "16:02:03") # timezone for time's is not supported

        # fmt_date
        self.assertEqual(fmt_date(plain), "1974-03-17" )
        self.assertEqual(fmt_date(datetime.date( year=2001, month=2, day=3 )), "2001-02-03" )
    
        # fmt_time
        self.assertEqual(fmt_time(plain), "16:02:03" )
        self.assertEqual(fmt_time(micro), "16:02:03,3232" )
        self.assertEqual(fmt_time(micro, sep="."), "16.02.03,3232")
        self.assertEqual(fmt_time(micro, sep=".", ignore_ms=True), "16.02.03")
        self.assertEqual(fmt_time(datetime.time( hour=1, minute=2, second=3, microsecond=4 )), "01:02:03,4")
    
        # fmt_timedelta
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=2, seconds=2+60*3+60*60*4, microseconds=1 )), "+2d4h3m2s1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=2+60*3+60*60*4, microseconds=1 )), "+4h3m2s1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=-(2+60*3+60*60*4), microseconds=-1 )), "-4h3m2s1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=-(2+60*3+60*60*4), microseconds=1 )), "-4h3m1s999999ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=(2+60*3+60*60*4), microseconds=-1 )), "+4h3m1s999999ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=2+60*3, microseconds=1 )), "+3m2s1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=2, microseconds=1 )), "+2s1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=0, microseconds=1 )), "+1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=0, microseconds=-1 )), "-1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=0, microseconds=0 )), "")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=1, microseconds=-1000000 )), "")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=2, seconds=2+60*3+60*60*4, microseconds=1 ), sep="::,"), "+2d:4h:3m:2s,1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=2+60*3+60*60*4, microseconds=1 ), sep="::,"), "+4h:3m:2s,1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=-(2+60*3+60*60*4), microseconds=-1 ), sep="::,"), "-4h:3m:2s,1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=-(2+60*3+60*60*4), microseconds=1 ), sep="::,"), "-4h:3m:1s,999999ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=0, seconds=(2+60*3+60*60*4), microseconds=-1 ), sep="::,"), "+4h:3m:1s,999999ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=2+60*3, microseconds=1 ), sep="::,"), "+3m:2s,1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=2, microseconds=1 ), sep="::,"), "+2s,1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=0, microseconds=1 ), sep="::,"), "+1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=0, microseconds=-1 ), sep="::,"), "-1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=0, microseconds=0 ), sep="::,"), "")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=1, microseconds=-1000000 ), sep="::,"), "")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=-2, seconds=-2-60*3, microseconds=-1 ), sep="  _"), "-2d 3m 2s_1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=-2-60*3, microseconds=-1 ), sep="  _"), "-3m 2s_1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( seconds=-2-60*3, microseconds=-1 ), sep=''), "-3m2s1ms")
        self.assertEqual(fmt_timedelta(datetime.timedelta( days=-2, seconds=-2-60*3-60*60*4, microseconds=-1 ), sep=[";", "", "_"] ), "-2d;4h3m2s_1ms")
        
        # fmt_filename
        self.assertEqual( DEF_FILE_NAME_MAP, {
                         '/' : "_",
                         '\\': "_",
                         '|' : "_",
                         ':' : ";",
                         '>' : ")",
                         '<' : "(",
                         '?' : "!",
                         '*' : "@",
                         } )
        self.assertEqual( fmt_filename("2*2/4=x"), "2@2_4=x" )
        self.assertEqual( fmt_filename("K:X;Z"), "K;X;Z" )
        self.assertEqual( fmt_filename("*"), "@" )
        self.assertEqual( fmt_filename("."), "." )  # technically a valid filename, but a reserved name at that

        with self.assertRaises(ValueError):
            self.assertEqual( fmt_filename("2*2/4=x", by="wrong"), "2@2_4=x" )

        BLANK =   {      '/' : "",
                         '\\': "",
                         '|' : "",
                         ':' : "",
                         '>' : "",
                         '<' : "",
                         '?' : "",
                         '*' : "",
                         } 
        self.assertEqual( fmt_filename("2*2/4=x", by=BLANK), "224=x" )
        
        # is_filename
        self.assertTrue( is_filename("hans") )
        self.assertFalse( is_filename("h/ans") )
        self.assertFalse( is_filename("h?ans") )
        
        
    def test_basics(self):

        # is_function
        self.assertFalse( is_function(1) )
        self.assertFalse( is_function("text") )        
        self.assertTrue( is_function(self.test_basics) )
        self.assertTrue( is_function(lambda x: x) )
        
        def f(x,y):
            return x
        self.assertTrue( is_function(f) )
        def ff():
            self.assertTrue( is_function(ff) )
        ff()

        class A(object):
            def __init__(self, x=1):
                self.x = x
            def f(self, y):
                return self.x*y
            @property
            def square(self):
                return self.x**2
            @staticmethod
            def g(y):
                return y**2
        class B(object):
            def __call__(self, x):
                return x**2
        class C(object):
            def __iter__(self):
                for i in range(5):
                    yield i

        a = A()
        b = B()
        c = C()
        self.assertFalse( is_function(A) )
        self.assertFalse( is_function(B) )
        self.assertFalse( is_function(C) )
        self.assertFalse( is_function(a) )
        self.assertFalse( is_function(b) )
        self.assertFalse( is_function(c) )
        self.assertTrue( is_function(A.__init__) )
        self.assertTrue( is_function(A.f) )
        self.assertFalse( is_function(A.square) )
        self.assertTrue( is_function(A.g) )
        self.assertTrue( is_function(a.__init__) )
        self.assertTrue( is_function(a.f) )
        self.assertFalse( is_function(a.square) )  # <-- properties are not considered as function
        self.assertTrue( is_function(a.g) )
        self.assertTrue( is_function(B.__init__) )
        self.assertTrue( is_function(B.__call__ ) )
        self.assertTrue( is_function(b.__init__) )
        self.assertTrue( is_function(b.__call__ ) )
        self.assertFalse( is_function(b) )         # <-- properties are not considered as function
        self.assertTrue( callable(b) )
        self.assertFalse( is_function(c) )
        self.assertTrue( is_function(i for i in c) )
        self.assertTrue( is_function(lambda x : x*x) )

        # is_atomic
        self.assertTrue( is_atomic(0) )
        self.assertTrue( is_atomic(0.1) )
        self.assertTrue( is_atomic("c") )
        self.assertFalse( is_atomic(b'\x02') )
        self.assertTrue( is_atomic("text") )
        self.assertFalse( is_atomic(complex(0.,-1)) )
        self.assertTrue( is_atomic(True) )
        self.assertTrue( is_atomic(1==0) )
        self.assertTrue( is_atomic(datetime.date(year=2005, month=2, day=1)) )
        self.assertFalse( is_atomic(datetime.time(hour=4)) )
        self.assertFalse( is_atomic(datetime.datetime(year=2005, month=2, day=1, hour=4)) )
        self.assertTrue( is_atomic(1==0) )
        self.assertTrue( is_atomic(1==0) )
        self.assertFalse( is_atomic(A) )
        self.assertFalse( is_atomic(a) )
        self.assertFalse( is_atomic(f) )
        self.assertFalse( is_atomic([1,2]) )
        self.assertFalse( is_atomic([]) )
        self.assertFalse( is_atomic({}) )
        self.assertFalse( is_atomic({'x':2}) )
        self.assertFalse( is_atomic({'x':2}) )
        
        self.assertEqual( is_atomic(np.int_(0)), True  )
        self.assertEqual( is_atomic(np.int32(0)), True  )
        self.assertEqual( is_atomic(np.int64(0)), True  )
        self.assertEqual( is_atomic(np.complex128(0)), True  )
        self.assertEqual( is_atomic(np.datetime64()), True  )
        self.assertEqual( is_atomic(np.timedelta64()), True  )
        self.assertEqual( is_atomic(np.ushort(0)), True  )
        self.assertEqual( is_atomic(np.float32(0)), True  )
        self.assertEqual( is_atomic(np.float64(0)), True  )
        self.assertEqual( is_atomic(np.ulonglong(0)), True  )
        self.assertEqual( is_atomic(np.longdouble(0)), True  )
        self.assertEqual( is_atomic(np.half(0)), True  )

        # is_float
        self.assertFalse( is_float(0) )
        self.assertTrue( is_float(0.1) )
        self.assertFalse( is_float(1==2) )
        self.assertFalse( is_float("0.1") )
        self.assertFalse( is_float(complex(0.,-1.)) )
        self.assertTrue( is_float(np.float16(0.1)) )
        self.assertTrue( is_float(np.float32(0.1)) )
        self.assertTrue( is_float(np.float64(0.1)) )
        self.assertFalse( is_float(np.int16(0.1)) )
        self.assertFalse( is_float(np.int32(0.1)) )
        self.assertFalse( is_float(np.int64(0.1)) )
        self.assertFalse( is_float(np.complex64(0.1)) )
        
if __name__ == '__main__':
    unittest.main()


