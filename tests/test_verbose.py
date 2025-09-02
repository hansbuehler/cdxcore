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
import_local()

from cdxcore.verbose import Context
from cdxcore.uniquehash import uniqueHash

class Test(unittest.TestCase):

    def test_verbose(self):
        
        class Channel(object):
            def __init__(self):
                self.track = []
            def __call__(self, msg : str, flush : bool ):
                self.track.append( (msg, flush) )
            def __str__(self):
                return str( self.track )
        
        def f_sub( num=3, context = Context.quiet ):
            context.report(0, "Entering loop")
            for i in range(num):
                context.report(1, "Number %ld", i)

        def f_main( context = Context.quiet ):
            context.write( "First step" )
            # ... do something
            context.report( 1, "Intermediate step 1" )
            context.report( 1, "Intermediate step 2\nwith newlines" )
            # ... do something
            f_sub( context=context(1) )
            # ... do something
            context.write( "Final step" )

        channel = Channel()
        context = Context(1,channel=channel)
        f_main(context)
        self.assertEqual( str(channel), r"[('00: First step\n', True), ('01:   Intermediate step 1\n', True), ('01:   Intermediate step 2\n01:   with newlines\n', True), ('01:   Entering loop\n', True), ('00: Final step\n', True)]")

        channel = Channel()
        context = Context(2,channel=channel)
        f_main(context)
        self.assertEqual( str(channel), r"[('00: First step\n', True), ('01:   Intermediate step 1\n', True), ('01:   Intermediate step 2\n01:   with newlines\n', True), ('01:   Entering loop\n', True), ('02:     Number 0\n', True), ('02:     Number 1\n', True), ('02:     Number 2\n', True), ('00: Final step\n', True)]")

        channel = Channel()
        context = Context("all",channel=channel)
        f_main(context)
        self.assertEqual( str(channel), r"[('00: First step\n', True), ('01:   Intermediate step 1\n', True), ('01:   Intermediate step 2\n01:   with newlines\n', True), ('01:   Entering loop\n', True), ('02:     Number 0\n', True), ('02:     Number 1\n', True), ('02:     Number 2\n', True), ('00: Final step\n', True)]")

        channel = Channel()
        context = Context(None,channel=channel)
        f_main(context)
        self.assertEqual( str(channel), r"[('00: First step\n', True), ('01:   Intermediate step 1\n', True), ('01:   Intermediate step 2\n01:   with newlines\n', True), ('01:   Entering loop\n', True), ('02:     Number 0\n', True), ('02:     Number 1\n', True), ('02:     Number 2\n', True), ('00: Final step\n', True)]")

        channel = Channel()
        context = Context("quiet",channel=channel)
        f_main(context)
        self.assertEqual( str(channel), r"[]")

        verbose1 = Context(1)
        verbose1.level = 2
        verbose2 = Context(2,indent=3)
        verbose2.level = 3
        self.assertEqual( uniqueHash( verbose1 ), uniqueHash( verbose2 ) )    
        
        verbose = Context("all")
        self.assertEqual( verbose.fmt(0,"test {x}", x=1),   "00: test 1")
        self.assertEqual( verbose.fmt(1,"test %(x)d", x=1), "01:   test 1")
        self.assertEqual( verbose.fmt(2,"test %d", 1),      "02:     test 1")
        verbose = Context(1)
        self.assertEqual( verbose.fmt(0,"test {x}", x=1),   "00: test 1")
        self.assertEqual( verbose.fmt(1,"test %(x)d", x=1), "01:   test 1")
        self.assertEqual( verbose.fmt(2,"test %d", 1),      None)
        verbose = Context(1)
        x = 1
        self.assertEqual( verbose.fmt(0,lambda : f"test {x}"),   "00: test 1")
        
        def f():
            raise RuntimeError("I should not happen")
        verbose.fmt(2,f)
        def f():
            raise RuntimeError("I should happen")
        with self.assertRaises(RuntimeError):
            verbose.fmt(1,f)

        
if __name__ == '__main__':
    unittest.main()


