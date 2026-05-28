# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

try:
    from import_local import import_local
    import_local()
except ModuleNotFoundError:
    pass

import unittest as unittest
from cdxcore.jcpool import JCPool, Context
import numpy as np

class Test(unittest.TestCase):

    def test_mp(self):
        
        self.maxDiff = None
        
        pool    = JCPool(2, threading=False)
        
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
        self.assertEqual( str(l), r"['00: Analysis done\n', '00: Launching analysis\n', '01:   Returned BTC -0.38, -0.42\n', '01:   Returned GLD -0.47, -0.42\n', '01:   Returned SPY -0.42, -0.41\n', '02:     Result for BTC: -0.38, -0.42\n', '02:     Result for GLD: -0.47, -0.42\n', '02:     Result for SPY: -0.42, -0.41\n']")

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
        self.assertEqual( str(l), r"['00: Analysis done\n', '00: Launching analysis\n', '02:     Result for BTC: -0.38, -0.42\n', '02:     Result for GLD: -0.47, -0.42\n', '02:     Result for SPY: -0.42, -0.41\n']")

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
        self.assertEqual( str(l), r"['00: Analysis done\n', '00: Launching analysis\n', '02:     Result for BTC: -0.38, -0.42\n', '02:     Result for GLD: -0.47, -0.42\n', '02:     Result for SPY: -0.42, -0.41\n']")

    def test_mt(self):
        
        self.maxDiff = None
        
        pool    = JCPool(2, threading=True)
        
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
        self.assertEqual( str(l), r"['00: Analysis done\n', '00: Launching analysis\n', '01:   Returned BTC -0.38, -0.42\n', '01:   Returned GLD -0.47, -0.42\n', '01:   Returned SPY -0.42, -0.41\n', '02:     Result for BTC: -0.38, -0.42\n', '02:     Result for GLD: -0.47, -0.42\n', '02:     Result for SPY: -0.42, -0.41\n']")



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
        self.assertEqual( str(l), r"['00: Analysis done\n', '00: Launching analysis\n', '02:     Result for BTC: -0.38, -0.42\n', '02:     Result for GLD: -0.47, -0.42\n', '02:     Result for SPY: -0.42, -0.41\n']")

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
        self.assertEqual( str(l), r"['00: Analysis done\n', '00: Launching analysis\n', '02:     Result for BTC: -0.38, -0.42\n', '02:     Result for GLD: -0.47, -0.42\n', '02:     Result for SPY: -0.42, -0.41\n']")
                        
    def test_pickle(self):
        import pickle
        pool    = JCPool(2, threading=False)
        s = pickle.dumps(pool)
        pool2 = pickle.loads(s)
        self.assertEqual( type(pool), type(pool2) )
        self.assertNotEqual( id(pool._pool), id(pool2._pool) ) # the pool is not pickled, so should be different objects

    def test_pool_config(self):
        from cdxcore.jcpool import JCPoolConfig
        pool_config = JCPoolConfig(num_workers=3, threading=True)
        pool1 = pool_config.pool()
        pool2 = pool_config.pool()
        self.assertEqual( id(pool1), id(pool2) ) # the pool is a singleton, so should be the same object
        self.assertEqual( pool1.num_workers, 3 )
        self.assertEqual( pool1.threading, True )

    def test_set_leak_detection(self):
        pool = JCPool(2, threading=False)
        self.assertTrue(pool._mem_leak_enforce)
        try:

            _old = JCPool.DEFAULT_MEM_LEAK_ENFORCE
            JCPool.DEFAULT_MEM_LEAK_ENFORCE = False

            pool = JCPool(2, threading=False)
            self.assertFalse(pool._mem_leak_enforce)
        finally:
            JCPool.DEFAULT_MEM_LEAK_ENFORCE = _old

if __name__ == '__main__':
    unittest.main()




