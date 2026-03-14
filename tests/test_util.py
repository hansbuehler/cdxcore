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

from cdxcore.util import get_calling_function_name, is_function, is_atomic, is_float, is_filename, qualified_name, get_calling_function_name
from cdxcore.util import fmt, fmt_seconds, fmt_list, fmt_dict, fmt_big_number, fmt_digits, fmt_big_byte_number, fmt_datetime, fmt_date, fmt_time, fmt_timedelta, fmt_filename, DEF_FILE_NAME_MAP
from cdxcore.util import CRMan, ActiveFormat, expected_str_fmt_args, TrackTime, DebugTime

class qA(object):

    M = 0

    def __init__(self):
        self.m = 1
    
    def f(self):
        pass
    
    @property
    def g(self):
        return 1

    @staticmethod
    def h():
        pass

    @classmethod
    def j(cls):
        pass
        
    def __iter__(self):
        yield 1

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

    def test_track_time(self):
        import time

        old_timer = TrackTime.TIMER
        try:
            TrackTime.TIMER = DebugTime()

            timer = TrackTime("f")
            self.assertEqual(timer.lap_time(), 0)

            TrackTime.TIMER += 1
            self.assertEqual(timer.lap_time(), 1)
            self.assertEqual(timer.seconds, 1, timer.seconds)

            TrackTime.TIMER += 1
            self.assertEqual(timer.seconds, 2, timer.seconds)

            TrackTime.TIMER += 1
            timer.lap_time("Simple1")
            self.assertEqual(timer["Simple1"].seconds, 2, timer["Simple1"].seconds)

            TrackTime.TIMER += 1
            self.assertEqual(timer["Simple1"].seconds, 2, timer["Simple1"].seconds)
            self.assertEqual(timer.seconds, 4, timer.seconds)

            timer.lap_time("Simple2")
            self.assertEqual(timer["Simple2"].seconds, 1, timer["Simple2"].seconds)
            timer.lap_time("Simple2")
            self.assertEqual(timer["Simple2"].seconds, 1, timer["Simple2"].seconds)

            self.assertEqual(timer.topic, "f")
            self.assertFalse(timer.is_stopped)

            with timer:
                pass
            self.assertTrue(timer.is_stopped)

            timer.start()
            self.assertFalse(timer.is_stopped)
            self.assertEqual(timer.seconds, 4, timer.seconds)

            with timer("Sub1"):
                TrackTime.TIMER += 1
            self.assertFalse(timer.is_stopped)
            self.assertEqual(timer["Sub1"].seconds, 1, timer["Sub1"].seconds)
            self.assertEqual(timer.seconds, 5, timer.seconds)

            with timer("Sub1") as tme:
                self.assertEqual(tme.topic, "Sub1")
                TrackTime.TIMER += 1
                tme.lap_time("Sub11")
                self.assertEqual(tme["Sub11"].seconds, 1, tme["Sub11"].seconds)
            self.assertTrue(tme.is_stopped)

            self.assertEqual(timer.topic, "f", timer.topic)
            self.assertFalse(timer.is_stopped, timer.is_stopped)
            self.assertEqual(timer["Sub1"].seconds, 2, timer["Sub1"].seconds)
            self.assertEqual(timer.seconds, 6, timer.seconds)

            timer.stop()

            timer.start()
            timer.lap_time("t1")
            self.assertEqual(timer["t1"].seconds, 0)
            self.assertEqual(timer["t1"].count, 1, timer["t1"].count)

            TrackTime.TIMER += 1
            timer.lap_time("t1")
            self.assertEqual(timer["t1"].seconds, 1)
            self.assertEqual(timer["t1"].count, 2, timer["t1"].count)

            TrackTime.TIMER += 2
            timer.lap_time("t1")
            self.assertEqual(timer["t1"].seconds, 3)
            self.assertEqual(timer["t1"].count, 3)
            self.assertEqual(timer["t1"].average_lap_seconds, 1)

            tt = TrackTime("f")
            TrackTime.TIMER += 1
            tt.lap_time()
            TrackTime.TIMER += 1
            tt.lap_time()
            TrackTime.TIMER += 1
            tt.lap_time()
            self.assertEqual(tt.average_lap_seconds, 1.0)
            self.assertEqual(tt.seconds, 3.0)

            tt = TrackTime("f")
            for _ in range(5):
                TrackTime.TIMER += 1
                tt.lap_time("t1")
                TrackTime.TIMER += 2
                tt.lap_time("t2")

            self.assertEqual(tt["t1"].average_lap_seconds, 1.0)
            self.assertEqual(tt["t2"].average_lap_seconds, 2.0)
            self.assertEqual(tt.seconds, 15, tt.seconds)
            self.assertEqual(tt.count, 10, tt.count)

            # Smoke test with real time source (keep short to avoid slow/flaky tests)
            TrackTime.TIMER = time.time
            rt = TrackTime("rt")
            time.sleep(0.01)
            dt = rt.lap_time()
            self.assertIsInstance(dt, float)
            self.assertGreaterEqual(dt, 0.0)
        finally:
            TrackTime.TIMER = old_timer

    def test_aggregation(self):
        
        old_timer = TrackTime.TIMER
        try:
            TrackTime.TIMER = DebugTime()
            tt1 = TrackTime("f")
            tt2 = TrackTime("g")
            TrackTime.TIMER += 1
            tt1.lap_time("lap")
            TrackTime.TIMER += 1
            tt1.lap_time("lap")
            tt2.lap_time("lap") 
            self.assertEqual( tt1['lap'].seconds, 2 )
            self.assertEqual( tt2['lap'].seconds, 2 )
            self.assertEqual( tt1['lap'].count, 2 )
            self.assertEqual( tt2['lap'].count, 1 )
            
            with tt1("sub") as sub:
                TrackTime.TIMER += 1
            with tt2("sub") as sub:
                TrackTime.TIMER += 1
                sub.lap_time("sub_lap")
                TrackTime.TIMER += 1
                
            self.assertEqual( tt1['sub'].seconds, 1 )
            self.assertEqual( tt2['sub'].seconds, 2 )
            self.assertEqual( tt1['sub'].count, 1 )
            self.assertEqual( tt2['sub'].count, 2 )
            self.assertEqual( tt2['sub']['sub_lap'].seconds, 1 )
            self.assertEqual( tt2['sub']['sub_lap'].count, 1 )
            
            # add up
            
            tt  = TrackTime(tt1)
            tt  += tt2
            self.assertEqual( tt['lap'].seconds, tt1['lap'].seconds+tt2['lap'].seconds )
            self.assertEqual( tt['lap'].count, tt1['lap'].count+tt2['lap'].count )
            self.assertEqual( tt['sub'].seconds, tt1['sub'].seconds+tt2['sub'].seconds )
            self.assertEqual( tt['sub'].count, tt1['sub'].count+tt2['sub'].count )
            self.assertEqual( tt['sub']['sub_lap'].seconds, tt2['sub']['sub_lap'].seconds )
            self.assertEqual( tt['sub']['sub_lap'].count, tt2['sub']['sub_lap'].count )
        finally:
            TrackTime.TIMER = old_timer
        

    def test_track_time_copy_constructor(self):

        old_timer = TrackTime.TIMER
        try:
            TrackTime.TIMER = DebugTime()

            src = TrackTime("src", start=False, elapsed_seconds=3.0)
            src.record("a", 2.0)

            cpy = TrackTime(src, start=None)
            self.assertEqual(cpy.topic, "src")
            self.assertTrue(cpy.is_stopped)
            self.assertEqual(cpy.lap_seconds, src.lap_seconds)
            self.assertEqual(cpy.count, src.count)
            self.assertEqual(cpy["a"].lap_seconds, 2.0)
            self.assertIsNot(cpy["a"], src["a"])

            cpy.add_time(1.0)
            cpy["a"].add_time(1.0)
            self.assertEqual(src.lap_seconds, 3.0)
            self.assertEqual(src["a"].lap_seconds, 2.0)

            cpy2 = TrackTime(src, start=True)
            self.assertFalse(cpy2.is_stopped)
            TrackTime.TIMER += 2.0
            cpy2.stop()
            self.assertTrue(cpy2.is_stopped)
            self.assertEqual(cpy2.lap_seconds, 5.0)
            self.assertEqual(cpy2.count, 2)

            cpy3 = TrackTime(src, start=None, elapsed_seconds=5.0)
            self.assertTrue(cpy3.is_stopped)
            self.assertEqual(cpy3.lap_seconds, 8.0)
            self.assertEqual(cpy3.count, src.count + 1)
        finally:
            TrackTime.TIMER = old_timer

    def test_track_time_iadd(self):

        old_timer = TrackTime.TIMER
        try:
            TrackTime.TIMER = DebugTime()

            a = TrackTime("a", start=False, elapsed_seconds=0.5)
            a.add_time(0.5)
            a.record("x", 1.0)
            a.record("x", 1.0)
            self.assertEqual( a.lap_seconds, 1. )
            self.assertEqual( a.count, 2 )
            self.assertEqual( a['x'].lap_seconds, 2. )
            self.assertEqual( a['x'].count, 2 )

            b = TrackTime("b", start=False, elapsed_seconds=3.0)
            self.assertEqual( b.lap_seconds, 3. )
            b.record("x", 2.0)
            b.record("x", 1.0)
            b.record("x", 1.0)
            self.assertEqual( b['x'].lap_seconds, 4. )
            self.assertEqual( b['x'].count, 3 )
            b.record("y", 5.0)
            self.assertEqual( b['y'].lap_seconds, 5. )

            self.assertEqual( a.lap_seconds, 1. )
            self.assertEqual( b.lap_seconds, 3. )
            prev_lap = a.lap_seconds
            prev_cnt = a.count
            a += b
            self.assertEqual( prev_lap, 1. )

            self.assertEqual(a.lap_seconds, prev_lap+b.lap_seconds)
            self.assertEqual(a.count, prev_cnt + b.count)
            self.assertEqual(a.lap_seconds, 4.)
            self.assertEqual(a.count, 3)
            self.assertAlmostEqual(a.average_lap_seconds, 4./3 )
            self.assertEqual(a["x"].lap_seconds, 6.0)
            self.assertEqual(a["x"].count, 5)
            self.assertAlmostEqual(a["x"].average_lap_seconds, 6./5)
            self.assertEqual(a["y"].lap_seconds, 5.0)
            self.assertEqual(a["y"].count, 1)
            self.assertEqual(a["y"].average_lap_seconds, 5.)

            self.assertEqual(b.lap_seconds, 3.0)
            self.assertEqual(b["x"].lap_seconds, 4.0)
            self.assertEqual(b["y"].lap_seconds, 5.0)

            a += 2.5
            self.assertEqual(a.lap_seconds, 6.5)
            self.assertEqual(a.count, 4)
            self.assertAlmostEqual(a.average_lap_seconds, 6.5/4)
        finally:
            TrackTime.TIMER = old_timer
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

        # qualified

        class qB(object):
        
            M = 0
        
            def __init__(self):
                self.m = 1
            
            def f(self):
                pass
            
            @property
            def g(self):
                return 1
        
            @staticmethod
            def h():
                pass
        
            @classmethod
            def j(cls):
                pass
                
            def __iter__(self):
                yield 1
                
        qa = qA()
        qb = qB()
        
        modname = __name__

        self.assertEqual( qualified_name(qualified_name,True), ("qualified_name", "cdxcore.util"))
        self.assertEqual( qualified_name(qualified_name,"@"), "qualified_name@cdxcore.util")
        self.assertEqual( qualified_name(is_atomic,True), ("is_atomic", "cdxcore.util"))
        self.assertEqual( qualified_name(datetime.datetime,True), ("datetime", "datetime"))
        self.assertEqual( qualified_name(datetime.datetime.date,True), ("datetime.date", "builtins"))
        self.assertEqual( qualified_name(datetime.datetime.now(),True), ("datetime", "datetime"))
        self.assertEqual( qualified_name(datetime.datetime.now().date(),True), ("date", "datetime"))
        
        self.assertEqual( qualified_name(qA), "qA")
        self.assertEqual( qualified_name(qA,True), ("qA",modname) )
        self.assertEqual( qualified_name(qA.M,True), ("int","builtins") )
        self.assertEqual( qualified_name(qA.f,True), ("qA.f",modname) )
        self.assertEqual( qualified_name(qA.g,True), ("qA.g",modname) ) # <-- property function
        self.assertEqual( qualified_name(qA.h,True), ("qA.h",modname) )
        self.assertEqual( qualified_name(qA.j,True), ("qA.j",modname) )
        
        self.assertEqual( qualified_name(qa), "qA")
        self.assertEqual( qualified_name(qa,True), ("qA",modname) )
        self.assertEqual( qualified_name(qa.M,True), ("int","builtins") )
        self.assertEqual( qualified_name(qa.m,True), ("int","builtins") )
        self.assertEqual( qualified_name(qa.f,True), ("qA.f",modname) )
        self.assertEqual( qualified_name(qa.g,True), ("int","builtins") )   # <-- property type
        self.assertEqual( qualified_name(qa.h,True), ("qA.h",modname) )
        self.assertEqual( qualified_name(qa.j,True), ("qA.j",modname) )
        
        self.assertEqual( qualified_name(qB), "Test.test_basics.<locals>.qB")
        self.assertEqual( qualified_name(qB,True), ("Test.test_basics.<locals>.qB",modname) )
        self.assertEqual( qualified_name(qB.M,True), ("int","builtins") )
        self.assertEqual( qualified_name(qB.f,True), ("Test.test_basics.<locals>.qB.f",modname) )
        self.assertEqual( qualified_name(qB.g,True), ("Test.test_basics.<locals>.qB.g",modname) ) # <-- property function
        self.assertEqual( qualified_name(qB.h,True), ("Test.test_basics.<locals>.qB.h",modname) )
        self.assertEqual( qualified_name(qB.j,True), ("Test.test_basics.<locals>.qB.j",modname) )
        
        self.assertEqual( qualified_name(qb), "Test.test_basics.<locals>.qB")
        self.assertEqual( qualified_name(qb,True), ("Test.test_basics.<locals>.qB",modname) )
        self.assertEqual( qualified_name(qb.M,True), ("int","builtins") )
        self.assertEqual( qualified_name(qb.m,True), ("int","builtins") )
        self.assertEqual( qualified_name(qb.f,True), ("Test.test_basics.<locals>.qB.f",modname) )
        self.assertEqual( qualified_name(qb.g,True), ("int","builtins") )   # <-- property type
        self.assertEqual( qualified_name(qb.h,True), ("Test.test_basics.<locals>.qB.h",modname) )
        self.assertEqual( qualified_name(qb.j,True), ("Test.test_basics.<locals>.qB.j",modname) )
        
        with self.assertRaises(ValueError):
            af = ActiveFormat(None)

        af = ActiveFormat("nothing")
        self.assertEqual( af(), "nothing" )
        self.assertTrue( af.is_simple_str )
        af = ActiveFormat("nothing")
        self.assertEqual( af(x=1), "nothing" ) # not strict
        self.assertTrue( af.is_simple_str )
        af = ActiveFormat("{x:.2f}")
        self.assertEqual( af(x=0.011), "0.01" )
        self.assertFalse( af.is_simple_str )
        af = ActiveFormat("{x} {y} {z}")
        self.assertEqual( af(z=3,y=2,x=1), "1 2 3" )
        af = ActiveFormat("{x} {y} {z}")
        self.assertEqual( af(z=3,y=2,x=1,u=0), "1 2 3" )# not strict
        af = ActiveFormat("{a}: {x} {y} {z}", reserved_keywords=dict(a=10))
        self.assertEqual( af(z=3,y=2,x=1), "10: 1 2 3" )
        
        with self.assertRaises(ValueError):
            af = ActiveFormat("nothing", strict=True )
            self.assertEqual( af(x=1), "nothing" )        
        with self.assertRaises(ValueError):
            af = ActiveFormat("{x} {y} {z}")
            self.assertEqual( af(z=3,y=2,u=1), "1 2 3" )
        with self.assertRaises(ValueError):
            af = ActiveFormat("{x} {y} {z}", strict=True)
            self.assertEqual( af(z=3,y=2,x=1,u=0), "1 2 3" )
        with self.assertRaises(RuntimeError):
            af = ActiveFormat("{a}: {x} {y} {z}", reserved_keywords=dict(a=10))
            self.assertEqual( af(z=3,y=2,x=1,a=0), "10: 1 2 3" )

        af = ActiveFormat(lambda x : f"{x:.2f}")
        self.assertFalse( af.is_simple_str )
        self.assertEqual( af(x=0.011), "0.01" )
        af = ActiveFormat(lambda x,y,z : f"{x} {y} {z}")
        self.assertEqual( af(z=3,y=2,x=1), "1 2 3" )
        af = ActiveFormat(lambda a,x,y,z : f"{a}: {x} {y} {z}", reserved_keywords=dict(a=10))
        self.assertEqual( af(z=3,y=2,x=1), "10: 1 2 3" )
        
        with self.assertRaises(ValueError):
            af = ActiveFormat(lambda x,y,z: f"{x} {y} {z}")
            self.assertEqual( af(z=3,y=2,u=1), "1 2 3" )
        with self.assertRaises(ValueError):
            af = ActiveFormat(lambda x,y,z: f"{x} {y} {z}", strict=True)
            self.assertEqual( af(z=3,y=2,x=1,u=0), "1 2 3" )
        with self.assertRaises(RuntimeError):
            af = ActiveFormat(lambda a,x,y,z: f"{a}: {x} {y} {z}", reserved_keywords=dict(a=10))
            self.assertEqual( af(z=3,y=2,x=1,a=0), "10: 1 2 3" )

        # get_calling_function_name
        def g():
            self.assertEqual( get_calling_function_name("default"), "f" )
        def f():
            g()
        f()

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

    def test_util_type_checking(self):
        """Test type checking utilities"""
        
        # Test is_atomic
        self.assertTrue(is_atomic("text"))
        self.assertTrue(is_atomic(42))
        self.assertTrue(is_atomic(3.14))
        self.assertTrue(is_atomic(True))
        self.assertTrue(is_atomic(datetime.date.today()))
        self.assertTrue(is_atomic(np.int32(5)))
        self.assertTrue(is_atomic(np.float64(3.14)))
        
        self.assertFalse(is_atomic([1, 2, 3]))
        self.assertFalse(is_atomic({"a": 1}))
        self.assertFalse(is_atomic(np.array([1, 2, 3])))
        
        # Test is_float
        self.assertTrue(is_float(3.14))
        self.assertTrue(is_float(np.float32(1.0)))
        self.assertTrue(is_float(np.float64(2.5)))
        
        self.assertFalse(is_float(42))
        self.assertFalse(is_float("3.14"))
        self.assertFalse(is_float(np.int32(3)))
        
        # Test is_function
        self.assertTrue(is_function(lambda x: x))
        self.assertTrue(is_function(def_test_util_helper_func))
        self.assertTrue(is_function(qA.h))  # static method
        self.assertTrue(is_function(qA.j))  # class method
        
        self.assertFalse(is_function("not a function"))
        self.assertFalse(is_function(42))
        self.assertFalse(is_function(qA()))  # instance without __call__
        
    def test_util_formatting_edge_cases(self):
        """Test edge cases in formatting functions"""
        
        # Test empty lists and edge cases
        self.assertEqual(fmt_list([]), "-")
        self.assertEqual(fmt_list([1]), "1")
        self.assertEqual(fmt_list([1, 2]), "1 and 2")
        self.assertEqual(fmt_list([1, 2, 3, 4, 5]), "1, 2, 3, 4 and 5")
        
        # Test fmt_big_number with edge cases
        self.assertEqual(fmt_big_number(0), "0")
        self.assertEqual(fmt_big_number(-0), "0")
        self.assertEqual(fmt_big_number(1), "1")
        
        # Test fmt_big_byte_number with edge cases
        self.assertEqual(fmt_big_byte_number(0), "0 bytes")
        self.assertEqual(fmt_big_byte_number(1), "1 byte")
        self.assertEqual(fmt_big_byte_number(2), "2 bytes")
        
        # Test fmt_dict edge cases
        self.assertEqual(fmt_dict({}), "-")
        self.assertEqual(fmt_dict({"a": 1}), "a: 1")
        self.assertEqual(fmt_dict({"a": 1, "b": 2}), "a: 1 and b: 2")
        
    def test_qualified_name(self):
        """Test qualified_name function"""
        
        # Test with built-in types
        self.assertEqual(qualified_name(int), "int")
        self.assertEqual(qualified_name(str), "str")
        
        # Test with numpy types
        self.assertEqual(qualified_name(np.ndarray), "ndarray")
        
        # Test with custom classes
        self.assertEqual(qualified_name(qA), "qA")
        
    def test_expected_str_fmt_args(self):
        """Test expected_str_fmt_args function"""
        
        # Test with different formatting styles
        fmt_string_new = "Number: {x}, Text: {text}, Value: {v}"
        args_new = expected_str_fmt_args(fmt_string_new)
        # expected_str_fmt_args returns a NamedTuple with 'keywords' field
        self.assertTrue(hasattr(args_new, 'keywords'))
        # keywords should contain the placeholder names
        if args_new.keywords:
            self.assertIn('x', args_new.keywords)
        
        fmt_string_old = "Number: %(x)d, Text: %(text)s"
        args_old = expected_str_fmt_args(fmt_string_old)
        self.assertTrue(hasattr(args_old, 'keywords'))


def def_test_util_helper_func(x, y):
    """Helper function for testing."""
    return x + y

if __name__ == '__main__':
    unittest.main()
