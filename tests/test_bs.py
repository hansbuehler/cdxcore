# -*- coding: utf-8 -*-
"""Tests for cdxcore.bs

Created on 2026-01-31
"""

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

import unittest as unittest

from cdxcore.bs import bs
import numpy as np
import math as math

class TestBS(unittest.TestCase):
    
    def test_bs(self):
        np.random.seed(21123)
        
        x = np.linspace( 0.7,1.3,11 )
        vol = 0.2
        c = bs.price( x, vol=vol, sqrtT=0.5, is_call=True )
        p = bs.price( x, vol=vol, sqrtT=0.5, is_call=False )
        f1 = c-p
        f2 = 1. - x

        self.assertLess( np.max( np.abs( f1 - f2 ) ), 1E-8 )

        v = bs.implied( x, c, is_call=True, sqrtT=0.5, price_tol=1E-6 )
        c2 = bs.price( x, vol=v, is_call=True, sqrtT=0.5 )
        self.assertLess( np.max( np.abs( c - c2 ) ), 1E-6 )

        vr = bs.implied( x, c, is_call=True, sqrtT=1., price_tol=1E-6 )
        vr /= 0.5
        cr = bs.price( x, vol=vr, is_call=True, sqrtT=0.5 )
        self.assertLess( np.max( np.abs( c - cr ) ), 1E-6 )
        
        v = bs.implied( x, p, is_call=False, sqrtT=0.5, price_tol=1E-7 )
        p2 = bs.price( x, vol=v, is_call=False, sqrtT=0.5 )
        self.assertLess( np.max( np.abs( p - p2 ) ), 1E-7 )

        vr = bs.implied( x, p, is_call=False, sqrtT=1., price_tol=1E-7 )
        vr /= 0.5
        pr = bs.price( x, vol=vr, is_call=False, sqrtT=0.5 )
        self.assertLess( np.max( np.abs( p - pr ) ), 1E-6 )
        
        c2 = bs( x, vol=0.2, sqrtT=0.5, is_call=True )
        self.assertLess( np.max( np.abs( c - c2 ) ), 1E-8 )
        
        p2 = bs( x, vol=0.2, sqrtT=0.5, is_call=False )
        self.assertLess( np.max( np.abs( p - p2 ) ), 1E-8 )

        # array tests
        N = 11
        x = np.linspace( 0.7,1.3,N )
        v = np.exp( np.random.normal( size=(N,)) )
        sqrtT = np.exp( np.random.normal( size=(N,)) )
        ic = np.random.choice( [True,False], size=(N,), replace=True)
        price = bs.price( k=x, vol=v, sqrtT=sqrtT, is_call=ic )
        vega  = bs.vega( k=x, vol=v, sqrtT=sqrtT, is_call=ic )
        delta = bs.delta( k=x, vol=v, sqrtT=sqrtT, is_call=ic )
        gamma = bs.gamma( k=x, vol=v, sqrtT=sqrtT, is_call=ic )
        theta = bs.theta(k=x, vol=v, sqrtT=sqrtT, is_call=ic )
        dK    = bs.dk(k=x, vol=v, sqrtT=sqrtT, is_call=ic )
        
        price_, delta_, dk_, vega_, gamma_, theta_ = bs( k=x, vol=v, sqrtT=sqrtT, is_call=ic, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )['price','delta','dk','vega','gamma','theta']
        self.assertTrue( np.all( price_ == price ) )
        self.assertTrue( np.all( delta_ == delta ) )
        self.assertTrue( np.all( dk_ == dK ) )
        self.assertTrue( np.all( gamma_ == gamma ) )
        self.assertTrue( np.all( vega_ == vega ) )
        self.assertTrue( np.all( theta_ == theta ) )

        # float tests
        price = bs.price( k=0.8, vol=0.2, sqrtT=1., is_call=False)
        vega  = bs.vega( k=0.8, vol=0.2, sqrtT=1., is_call=False)
        delta = bs.delta( k=0.8, vol=0.2, sqrtT=1, is_call=False)
        gamma = bs.gamma( k=0.8, vol=0.2, sqrtT=1, is_call=False)
        theta = bs.theta( k=0.8, vol=0.2, sqrtT=1, is_call=False)
        dK    = bs.dk( k=0.8, vol=0.2, sqrtT=1, is_call=False)

        price_, delta_, dk_,vega_,  gamma_, theta_ = bs( k=0.8, vol=0.2, sqrtT=1., is_call=False, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )['price','delta','dk','vega','gamma','theta']
            
        self.assertEqual( price, price )
        self.assertEqual( delta_, delta )
        self.assertEqual( dk_, dK )
        self.assertEqual( gamma_, gamma )
        self.assertEqual( vega_, vega )
        self.assertEqual( theta_, theta )

        r = bs( k=0.8, vol=0.2, sqrtT=1., is_call=False, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )
        self.assertEqual( list(r.keys()), ['price','delta','dk','gamma','vega','theta'] )
        r = bs( k=0.8, vol=0.2, sqrtT=1., is_call=False, what=bs.PRICE|bs.THETA|bs.GAMMA|bs.DELTA )
        self.assertEqual( list(r.keys()), ['price','delta','gamma','theta'] )
        
        price_, delta_, dk_, gamma_, vega_, theta_ = bs( k=0.8, vol=0.2, sqrtT=1., is_call=False, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )
        
        self.assertEqual( price, price )
        self.assertEqual( delta_, delta )
        self.assertEqual( dk_, dK )
        self.assertEqual( gamma_, gamma )
        self.assertEqual( vega_, vega )
        self.assertEqual( theta_, theta )
        
        
    
    


if __name__ == "__main__":
    unittest.main()
