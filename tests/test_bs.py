# -*- coding: utf-8 -*-
"""Tests for cdxcore.bs

Created on 2026-01-31
"""

try:
    from import_local import import_local
    import_local()
except ModuleNotFoundError:
    pass

import unittest as unittest

from cdxcore.bs import bs
import numpy as np
import math as math

class TestBS(unittest.TestCase):

    def test_implied_rejects_prices_below_intrinsic(self):
        with self.assertRaises(ValueError):
            bs.implied(
                np.array([0.8]),
                np.array([0.1]),
                is_call=True,
                on_exceed_bounds='error',
            )

    def test_implied_uses_array_default_vol_as_initial_guess(self):
        k = np.array([1.0, 0.8])
        true_vol = np.array([4.0, 1.5])
        prices = bs.price(k, true_vol, sqrtT=1.0, is_call=True)

        implied = bs.implied(
            k,
            prices,
            is_call=True,
            sqrtT=1.0,
            default_vol=true_vol,
            max_iters=1,
        )

        self.assertLess(np.max(np.abs(implied - true_vol)), 1E-12)
    
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

        vr = bs.implied( x, c, is_call=True, sqrtT=1.1, price_tol=1E-6 )
        vr /= (0.5 / 1.1)
        cr = bs.price( x, vol=vr, is_call=True, sqrtT=0.5 )
        self.assertLess( np.max( np.abs( c - cr ) ), 1E-6 )
        
        v = bs.implied( x, p, is_call=False, sqrtT=0.5, price_tol=1E-7 )
        p2 = bs.price( x, vol=v, is_call=False, sqrtT=0.5 )
        self.assertLess( np.max( np.abs( p - p2 ) ), 1E-7 )

        vr = bs.implied( x, p, is_call=False, sqrtT=1.1, price_tol=1E-7 )
        vr /= (0.5 / 1.1)
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
        price = bs.price( k=0.8, vol=0.2, sqrtT=1.1, is_call=False)
        vega  = bs.vega( k=0.8, vol=0.2, sqrtT=1.1, is_call=False)
        delta = bs.delta( k=0.8, vol=0.2, sqrtT=1.1, is_call=False)
        gamma = bs.gamma( k=0.8, vol=0.2, sqrtT=1.1, is_call=False)
        theta = bs.theta( k=0.8, vol=0.2, sqrtT=1.1, is_call=False)
        dK    = bs.dk( k=0.8, vol=0.2, sqrtT=1.1, is_call=False)

        # test each vs manual calc
        from scipy.special import ndtr
        _inv_sqrt_2pi = 1.0 / np.sqrt(2.0 * np.pi)
        k_test, vol_test, sqrtT_test = 0.8, 0.2, 1.1
        vf = vol_test * sqrtT_test
        logK = math.log(k_test)
        d1 = -logK / vf + 0.5 * vf
        d2 = d1 - vf
        N1 = ndtr(d1)
        N2 = ndtr(d2)
        pd1 = _inv_sqrt_2pi * math.exp(-0.5 * d1**2)
        
        # Manual calculations for put option
        price_manual = N1 - k_test * N2 - 1.0 + k_test  # Put = Call - 1 + K
        delta_manual = N1 - 1.0  # Put delta = Call delta - 1
        dk_manual = -N2 + 1.0    # Put dk = Call dk + 1
        gamma_manual = pd1 / vf
        vega_manual = pd1 * sqrtT_test  # Standard BS vega formula
        theta_manual = 0.5 * vol_test * pd1 / sqrtT_test
        
        self.assertAlmostEqual(price, price_manual, places=10)
        self.assertAlmostEqual(delta, delta_manual, places=10)
        self.assertAlmostEqual(dK, dk_manual, places=10)
        self.assertAlmostEqual(gamma, gamma_manual, places=10)
        self.assertAlmostEqual(vega, vega_manual, places=10)
        self.assertAlmostEqual(theta, theta_manual, places=10)

        price_, delta_, dk_,vega_,  gamma_, theta_ = bs( k=0.8, vol=0.2, sqrtT=1.1, is_call=False, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )['price','delta','dk','vega','gamma','theta']
            
        self.assertEqual( price, price )
        self.assertEqual( delta_, delta )
        self.assertEqual( dk_, dK )
        self.assertEqual( gamma_, gamma )
        self.assertEqual( vega_, vega )
        self.assertEqual( theta_, theta )

        r = bs( k=0.8, vol=0.2, sqrtT=1.1, is_call=False, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )
        self.assertEqual( list(r.keys()), ['price','delta','dk','gamma','vega','theta'] )
        r = bs( k=0.8, vol=0.2, sqrtT=1.1, is_call=False, what=bs.PRICE|bs.THETA|bs.GAMMA|bs.DELTA )
        self.assertEqual( list(r.keys()), ['price','delta','gamma','theta'] )
        
        price_, delta_, dk_, gamma_, vega_, theta_ = bs( k=0.8, vol=0.2, sqrtT=1.1, is_call=False, what=bs.PRICE|bs.VEGA|bs.THETA|bs.GAMMA|bs.DK|bs.DELTA )
        
        self.assertEqual( price, price )
        self.assertEqual( delta_, delta )
        self.assertEqual( dk_, dK )
        self.assertEqual( gamma_, gamma )
        self.assertEqual( vega_, vega )
        self.assertEqual( theta_, theta )
        
        sqrtT = np.array( [0.2, 0.4] ).reshape((1,2))
        nms   = np.linspace( -1,+1,11 ).reshape((11,1))
        k     = np.exp( nms * sqrtT )
        v     = np.random.normal( size=(11,1) )**2
        sqrtT = np.array( [0.2, 0.4] ).reshape((1,2))

        price, vega = bs( k=k, vol=v, sqrtT=sqrtT, what=bs.PRICE|bs.VEGA )['price','vega']         
        self.assertEqual( price.shape, (11,2))
        self.assertEqual( vega.shape, (11,2))

if __name__ == "__main__":
    unittest.main()
