
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

from cdxcore.jcpool import JCPool, Context
import numpy as np

class Test(unittest.TestCase):

    def test_pool(self):
        
        self.maxDiff = None
        
        pool    = JCPool(2)
        
        class Channel(object):
            """ utility to collect all traced messages """
            def __init__(self):
                self.messages = []
            def __call__(self, msg, flush):
                self.messages.append( msg )
        
        def f( ticker, tdata, verbose : Context ):
            # some made up results
            q  = np.quantile( tdata, 0.35, axis=0 )
            tx = q[0]
            ty = q[1]
            # not in a unittest --> time.sleep( np.exp(tdata[0,0]) )
            verbose.write(f"Result for {ticker}: {tx:.2f}, {ty:.2f}")
            return tx, ty
        
        np.random.seed(1231)
        tickerdata =\
         { 'SPY': np.random.normal(size=(1000,2)),
           'GLD': np.random.normal(size=(1000,2)), 
           'BTC': np.random.normal(size=(1000,2))
         } 

        # iterator mode        
        channel      = Channel()
        verbose_main = Context("all", channel=channel)
        
        verbose_main.write("Launching analysis")
        with pool.context( verbose_main ) as verbose:
            for ticker, tx, ty in pool.parallel(
                        { ticker: pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose(2) )
                        for ticker, tdata in tickerdata.items() } ):
                verbose.report(1,f"Returned {ticker} {tx:.2f}, {ty:.2f}")
        verbose_main.write("Analysis done")

        l = sorted( channel.messages )
        self.assertEqual( str(l), r"['00: 01:   Returned BTC -0.38, -0.42\n', '00: 01:   Returned GLD -0.47, -0.42\n', '00: 01:   Returned SPY -0.42, -0.41\n', '00: 02:     Result for BTC: -0.38, -0.42\n', '00: 02:     Result for GLD: -0.47, -0.42\n', '00: 02:     Result for SPY: -0.42, -0.41\n', '00: Analysis done\n', '00: Launching analysis\n']")

        # dict mode
        channel      = Channel()
        verbose_main = Context("all", channel=channel)
        
        verbose_main.write("Launching analysis")
        with pool.context( verbose_main ) as verbose:
            l = pool.parallel_to_dict(
                        { ticker: pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose(2) )
                          for ticker, tdata in tickerdata.items() } )
        verbose_main.write("Analysis done")
        self.assertEqual( type(l), dict )

        l = sorted( channel.messages )
        self.assertEqual( str(l), r"['00: 02:     Result for BTC: -0.38, -0.42\n', '00: 02:     Result for GLD: -0.47, -0.42\n', '00: 02:     Result for SPY: -0.42, -0.41\n', '00: Analysis done\n', '00: Launching analysis\n']")

        # list mode            
        channel      = Channel()
        verbose_main = Context("all", channel=channel)
        
        verbose_main.write("Launching analysis")
        with pool.context( verbose_main ) as verbose:
            l = pool.parallel_to_list(
                        pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose(2) )
                        for ticker, tdata in tickerdata.items() )
        verbose_main.write("Analysis done")
        self.assertEqual( type(l), list )

        l = sorted( channel.messages )
        self.assertEqual( str(l), r"['00: 02:     Result for BTC: -0.38, -0.42\n', '00: 02:     Result for GLD: -0.47, -0.42\n', '00: 02:     Result for SPY: -0.42, -0.41\n', '00: Analysis done\n', '00: Launching analysis\n']")
            
if __name__ == '__main__':
    unittest.main()




