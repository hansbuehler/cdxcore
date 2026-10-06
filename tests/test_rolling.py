# -*- coding: utf-8 -*-
"""
Tests for cdxcore.rolling:
rolling_ew_std, robust_rolling_ew, robust_rolling_dt_ew, robust_fixed_window.
"""
try:
    from import_local import import_local
    import_local()
except ModuleNotFoundError:
    pass

import math
import unittest as unittest
import warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import integrate

from cdxcore import rolling as S

MAD   = 1.482602218505602
EPS   = np.finfo( np.float64 ).eps
BAD   = ( AssertionError, ValueError, TypeError )

# ------------------------------------------------
# Reference implementations (plain python loops)
# -------------------------------------------------

def ref_correction( cutoff ):
    phi = lambda z: math.exp( -0.5*z*z ) / math.sqrt( 2.*math.pi )
    return 1. / ( 2. * integrate.quad( lambda z: z * phi(z), 0., cutoff )[0] + cutoff * math.erfc( cutoff / math.sqrt(2.) ) )

def ref_terminal_weights( w ):
    # the weights follow from linearity of the recursion s = (1-w) s + w x
    n = len(w)
    q = np.zeros( n )
    for i in range( n ):
        s = 0.
        for j in range( n ):
            s = (1.-w[j])*s + w[j]*(1. if j == i else 0.)
        q[i] = s
    return q / q.sum()

def ref_wmedian( v, q ):
    o = np.argsort( v, kind="stable" )
    c = np.cumsum( q[o] )
    return v[o][ np.nonzero( c >= 0.5 )[0][0] ]

def ref_ew_std( x, window, init, cutoff ):
    x   = np.asarray( x, dtype=np.float64 )
    a   = 1./window
    loc = np.full( len(x), np.nan )
    var = np.full( len(x), np.nan )
    loc[init-1] = x[:init].mean()
    var[init-1] = np.mean( ( x[:init] - loc[init-1] )**2 )
    floor2      = ( EPS * max( 1., np.max( np.abs( x[:init] ) ) ) )**2
    for i in range( init, len(x) ):
        pv  = max( var[i-1], floor2 )
        ps  = math.sqrt( pv )
        d   = x[i] - loc[i-1]
        cl  = min( cutoff*ps, max( -cutoff*ps, d ) )
        loc[i] = loc[i-1] if abs(d) > cutoff*ps else loc[i-1] + a*d
        var[i] = (1.-a) * ( pv + a*cl*cl )
    return loc, np.sqrt( var )

def ref_robust( x, w, init, cutoff, dt=None, min_scale=None ):
    """ Level mode if dt is None, otherwise increment mode returning drift rate and diffusion scale """
    x    = np.asarray( x, dtype=np.float64 )
    w    = np.asarray( w, dtype=np.float64 )
    q    = ref_terminal_weights( w[:init] )
    c    = ref_correction( cutoff )
    if dt is None:
        m0 = ref_wmedian( x[:init], q )
        r0 = np.abs( x[:init] - m0 )
    else:
        m0 = ref_wmedian( x[:init] / dt[:init], q )
        r0 = np.abs( x[:init] - m0*dt[:init] ) / np.sqrt( dt[:init] )
    floor = min_scale if min_scale is not None else EPS * max( 1., np.max( r0 ) )
    loc   = np.full( len(x), np.nan )
    dis   = np.full( len(x), np.nan )
    otl   = np.zeros( len(x), dtype=bool )
    loc[init-1] = m0
    dis[init-1] = max( MAD * ref_wmedian( r0, q ), floor )
    for i in range( init, len(x) ):
        ps = max( dis[i-1], floor )
        if dt is None:
            r = x[i] - loc[i-1]
            z = r
        else:
            r = x[i] - loc[i-1]*dt[i]
            z = r / math.sqrt( dt[i] )
        otl[i] = abs(z) > cutoff*ps
        cl     = min( cutoff*ps, max( -cutoff*ps, z ) )
        loc[i] = loc[i-1] if otl[i] else loc[i-1] + w[i] * ( r if dt is None else r/dt[i] )
        dis[i] = max( (1.-w[i])*ps + w[i]*c*abs(cl), floor )
    return loc, dis, otl

def ew_weights( dt, twindow ):
    return - np.expm1( - np.asarray( dt, dtype=np.float64 ) / twindow )

def make_series( n=400, seed=1 ):
    rng = np.random.default_rng( seed )
    x   = rng.standard_normal( n )
    if n > 310:
        x[100]     += 12.
        x[300:310] += 5.
    dt  = rng.uniform( 0.002, 0.02, n )
    return x, dt

class Base( unittest.TestCase ):

    def assertSame( self, a, b, rtol=1e-10, atol=0. ):
        self.assertEqual( len(a), len(b) )
        for u, v in zip( a, b ):
            u, v = np.asarray( u ), np.asarray( v )
            self.assertEqual( u.shape, v.shape )
            if u.dtype == bool or v.dtype == bool:
                self.assertTrue( np.array_equal( u, v ) )
            else:
                np.testing.assert_allclose( u, v, rtol=rtol, atol=atol, equal_nan=True )

# ------------------------------------------------
# Helpers
# -------------------------------------------------

class TestHelpers( Base ):

    def test_cutoff_correction(self):
        for c in [ 0.1, 1., 2.5, 3., 6. ]:
            self.assertAlmostEqual( S._cutoff_correction( c ), ref_correction( c ), places=9 )
        self.assertAlmostEqual( S._cutoff_correction( 1e6 ), math.sqrt( math.pi / 2. ), places=9 )

    def test_cutoff_correction_is_consistent(self):
        # the correction makes E[c * min(|Z|,cutoff)] equal to E|Z|-calibrated sigma=1 for Z ~ N(0,1)
        z = np.random.default_rng( 0 ).standard_normal( 2_000_000 )
        for c in [ 1.5, 2.5, 4. ]:
            self.assertAlmostEqual( S._cutoff_correction( c ) * np.mean( np.minimum( np.abs(z), c ) ), 1., delta=0.005 )

    def test_terminal_weights(self):
        rng = np.random.default_rng( 3 )
        for n in [ 1, 2, 5, 12 ]:
            w = rng.uniform( 0.01, 0.9, n )
            q = S._terminal_weights( w )
            self.assertAlmostEqual( q.sum(), 1., places=12 )
            np.testing.assert_allclose( q, ref_terminal_weights( w ), rtol=1e-12 )
        q = S._terminal_weights( np.array( [ 0.3, 0.2, 1. ] ) ) # a unit weight forgets everything before
        np.testing.assert_allclose( q, [ 0., 0., 1. ], atol=1e-15 )
        q = S._terminal_weights( np.full( 6, 0.5 ) )          # recent observations weigh more
        self.assertTrue( np.all( np.diff( q ) > 0. ) )

    def test_wmedian(self):
        rng = np.random.default_rng( 4 )
        for n in [ 1, 2, 7, 10 ]:
            v = rng.standard_normal( n )
            q = rng.uniform( size=n ); q /= q.sum()
            self.assertEqual( S._wmedian( v, q ), ref_wmedian( v, q ) )
        self.assertEqual( S._wmedian( np.array( [ 1., 2., 100. ] ), np.array( [ 0.2, 0.2, 0.6 ] ) ), 100. )

    def test_min_scale(self):
        self.assertEqual( S._min_scale( np.array( [ -3., 2. ] ), None ), EPS * 3. )
        self.assertEqual( S._min_scale( np.array( [ 0.1 ] ), None ), EPS )
        self.assertEqual( S._min_scale( np.array( [ 5. ] ), 0.5 ), 0.5 )
        for bad in [ 0., -1. ]:
            with self.assertRaises( BAD ):
                S._min_scale( np.array( [ 1. ] ), bad )

# ------------------------------------------------
# rolling_ew_std
# -------------------------------------------------

class TestRollingEwStd( Base ):

    def test_reference(self):
        x, _ = make_series()
        for window, init, cutoff in [ (20., 10, 2.5), (5., 1, 1.), (200., 50, 3.), (20, 10, 1e9), (1.5, 3, 2.5) ]:
            with self.subTest( window=window, init=init, cutoff=cutoff ):
                self.assertSame( S.rolling_ew_std( x, window, init, cutoff ), ref_ew_std( x, window, init, cutoff ) )

    def test_textbook_recursion_without_outliers(self):
        y = np.random.default_rng( 5 ).standard_normal( 1000 )
        m, s = S.rolling_ew_std( y, 20., 10, 1e9 )
        a = 1./20.
        mm, v = y[:10].mean(), y[:10].var()
        for t in range( 10, 1000 ):
            d  = y[t] - mm
            mm += a*d
            v  = (1.-a) * ( v + a*d*d )
        self.assertAlmostEqual( m[-1], mm, places=12 )
        self.assertAlmostEqual( s[-1], math.sqrt( v ), places=12 )

    def test_warmup_is_nan(self):
        x, _ = make_series()
        m, s = S.rolling_ew_std( x, 20., 10 )
        self.assertTrue( np.all( np.isnan( m[:9] ) ) and np.all( np.isnan( s[:9] ) ) )
        self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( np.isfinite( s[9:] ) ) )
        self.assertAlmostEqual( m[9], x[:10].mean(), places=12 )
        self.assertAlmostEqual( s[9], x[:10].std(), places=12 )

    def test_init_edges(self):
        x, _ = make_series( 30 )
        for init in [ 1, 2, 29, 30 ]:
            m, s = S.rolling_ew_std( x, 5., init )
            self.assertEqual( len( m ), 30 )
            self.assertTrue( np.all( np.isfinite( m[init-1:] ) ) and np.all( np.isfinite( s[init-1:] ) ) )
        m, s = S.rolling_ew_std( x[:1], 5., 1 )
        self.assertEqual( ( m[0], s[0] ), ( x[0], 0. ) )

    def test_constant_series(self):
        m, s = S.rolling_ew_std( np.full( 50, 3. ), 10., 5 )
        self.assertTrue( np.all( np.isfinite( s[4:] ) ) )
        np.testing.assert_allclose( m[4:], 3. )
        np.testing.assert_allclose( s[4:], 0., atol=1e-12 )
        m, s = S.rolling_ew_std( np.zeros( 50 ), 10., 5 )
        self.assertTrue( np.all( np.isfinite( s[4:] ) ) )

    def test_spike_is_capped(self):
        x = np.random.default_rng( 6 ).standard_normal( 200 )
        x[150] = 1e6
        m, s = S.rolling_ew_std( x, 20., 10, 2.5 )
        a, c = 1./20., 2.5
        self.assertLessEqual( s[150]**2, ( 1.-a ) * ( 1. + a*c*c ) * s[149]**2 * ( 1. + 1e-12 ) )
        self.assertEqual( m[150], m[149] )
        self.assertLess( s[150], 1.5 * s[149] )

    def test_gaussian_level(self):
        z = 2. + 3. * np.random.default_rng( 7 ).standard_normal( 40000 )
        m, s = S.rolling_ew_std( z, 400., 100 )
        self.assertAlmostEqual( np.mean( s[-20000:] ), 3., delta=0.15 )
        self.assertAlmostEqual( np.mean( m[-20000:] ), 2., delta=0.15 )

    def test_invalid(self):
        x, _ = make_series( 30 )
        for kw in [ dict(window=1.), dict(window=0.5), dict(window=0.), dict(window=-5.),
                    dict(init=0), dict(init=31), dict(init=-1), dict(init=2.5), dict(cutoff=0.), dict(cutoff=-1.) ]:
            args = dict( window=5., init=5, cutoff=2.5 ); args.update( kw )
            with self.subTest( **kw ):
                with self.assertRaises( BAD ):
                    S.rolling_ew_std( x, **args )

# ------------------------------------------------
# robust_rolling_ew
# -------------------------------------------------

class TestRobustRollingEw( Base ):

    def test_reference(self):
        x, _ = make_series()
        for window, init, cutoff, ms in [ (20., 10, 2.5, None), (5., 1, 1., None), (200., 50, 3., None), (1.5, 3, 2.5, None), (20., 10, 2.5, 0.7), (20., 399, 2.5, None), (20., 400, 2.5, None) ]:
            with self.subTest( window=window, init=init, cutoff=cutoff, min_scale=ms ):
                self.assertSame( S.robust_rolling_ew( x, window, init, cutoff, ms, on_zero_init="ignore" ),   # window=1.5 puts more than half the weight on the last observation
                                 ref_robust( x, np.full( len(x), 1./window ), init, cutoff, min_scale=ms ) )

    def test_warmup_and_flags(self):
        x, _ = make_series()
        m, s, o = S.robust_rolling_ew( x, 20., 10 )
        self.assertTrue( np.all( np.isnan( m[:9] ) ) and np.all( np.isnan( s[:9] ) ) )
        self.assertFalse( np.any( o[:10] ) )
        self.assertTrue( o[100] )
        self.assertTrue( np.all( o[300:303] ) )                     # a sustained shift raises consecutive flags
        self.assertLess( o[110:290].mean(), 0.05 )                   # false positives of a Gaussian at 2.5 sigma
        self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( s[9:] > 0. ) )
        self.assertEqual( m[100], m[99] )                           # outliers leave the location untouched
        self.assertEqual( o.dtype, np.bool_ )

    def test_gaussian_consistency(self):
        z = -1. + 2. * np.random.default_rng( 8 ).standard_normal( 60000 )
        m, s, o = S.robust_rolling_ew( z, 400., 100 )
        self.assertAlmostEqual( np.mean( s[-30000:] ), 2., delta=0.1 )
        self.assertAlmostEqual( np.mean( m[-30000:] ), -1., delta=0.15 )
        self.assertLess( np.mean( o[-30000:] ), 0.03 )

    def test_shift_adapts(self):
        z = np.random.default_rng( 9 ).standard_normal( 2000 )
        z[1000:] += 4.
        m, s, o = S.robust_rolling_ew( z, 20., 20 )
        self.assertTrue( o[1000] )
        self.assertAlmostEqual( np.mean( m[-200:] ), 4., delta=0.4 )
        self.assertFalse( o[1500:].mean() > 0.05 )

    def test_constant_and_degenerate(self):
        cm = warnings.catch_warnings()                                  # constant data has a zero initial MAD
        cm.__enter__()
        self.addCleanup( cm.__exit__, None, None, None )
        warnings.simplefilter( "ignore" )
        for data in [ np.zeros( 40 ), np.full( 40, 7. ), np.full( 40, -1e-300 ) ]:
            m, s, o = S.robust_rolling_ew( data, 10., 5 )
            self.assertTrue( np.all( np.isfinite( s[4:] ) ) and np.all( s[4:] > 0. ) and np.all( np.isfinite( m[4:] ) ) )
            self.assertFalse( o.any() )
        data = np.zeros( 40 ); data[30] = 1.
        m, s, o = S.robust_rolling_ew( data, 10., 5 )
        self.assertTrue( o[30] and np.all( np.isfinite( s[4:] ) ) )
        m, s, o = S.robust_rolling_ew( np.array( [ 5. ] ), 10., 1 )
        self.assertEqual( ( m[0], o[0] ), ( 5., False ) )

    def test_min_scale(self):
        x, _ = make_series()
        m, s, o = S.robust_rolling_ew( x, 20., 10, min_scale=50. )
        np.testing.assert_array_equal( s[9:], 50. )
        self.assertFalse( o.any() )

    def test_invalid(self):
        x, _ = make_series( 30 )
        for kw in [ dict(window=1.), dict(window=0.), dict(window=-1.),
                    dict(init=0), dict(init=31), dict(init=2.5), dict(cutoff=0.), dict(cutoff=-1.),
                    dict(min_scale=0.), dict(min_scale=-1.) ]:
            args = dict( window=5., init=5, cutoff=2.5 ); args.update( kw )
            with self.subTest( **kw ):
                with self.assertRaises( BAD ):
                    S.robust_rolling_ew( x, **args )

# ------------------------------------------------
# robust_fixed_window
# -------------------------------------------------

class TestRobustFixedWindow( Base ):

    def test_values(self):
        loc, scale = S.robust_fixed_window( [ 1., 2., 3., 4., 100. ] )
        self.assertEqual( loc, 3. )
        self.assertAlmostEqual( scale, MAD, places=12 )
        self.assertIsInstance( loc, float ); self.assertIsInstance( scale, float )

    def test_normal_sample(self):
        z = 1. + 2.5 * np.random.default_rng( 10 ).standard_normal( 100000 )
        loc, scale = S.robust_fixed_window( z )
        self.assertAlmostEqual( loc, 1., delta=0.03 ); self.assertAlmostEqual( scale, 2.5, delta=0.05 )

    def test_increments(self):
        rng = np.random.default_rng( 11 )
        dt  = rng.uniform( 0.001, 0.01, 100000 )
        x   = 3. * dt + 0.8 * np.sqrt( dt ) * rng.standard_normal( len(dt) )
        loc, scale = S.robust_fixed_window( x, dt, scale_by_dt=True, normalize_by_dt=True )
        self.assertAlmostEqual( scale, 0.8, delta=0.02 )
        self.assertAlmostEqual( loc, 3., delta=0.6 )
        # reference formula
        rate = np.median( x / dt )
        res  = ( x - rate*dt ) / np.sqrt( dt )
        sig  = MAD * np.median( np.abs( res - np.median( res ) ) )
        self.assertAlmostEqual( loc, rate, places=12 ); self.assertAlmostEqual( scale, sig, places=12 )
        ref  = np.median( dt )
        l2, s2 = S.robust_fixed_window( x, dt, scale_by_dt=True, normalize_by_dt=False )
        self.assertAlmostEqual( l2, rate*ref, places=12 ); self.assertAlmostEqual( s2, sig*math.sqrt( ref ), places=12 )

    def test_dt_ignored_without_scale_by_dt(self):
        x, dt = make_series( 50 )
        self.assertEqual( S.robust_fixed_window( x, dt ), S.robust_fixed_window( x ) )

    def test_min_scale(self):
        loc, scale = S.robust_fixed_window( np.full( 10, 2. ) )
        self.assertEqual( ( loc, scale ), ( 2., 2.*EPS ) )
        self.assertEqual( S.robust_fixed_window( np.full( 10, 2. ), min_scale=0.3 ), ( 2., 0.3 ) )
        self.assertEqual( S.robust_fixed_window( [ 4. ] )[0], 4. )

    def test_invalid(self):
        x, dt = make_series( 20 )
        for kw in [ dict(scale_by_dt=True), dict(normalize_by_dt=True), dict(dt=dt, normalize_by_dt=True),
                    dict(dt=dt[:5], scale_by_dt=True), dict(dt=-dt, scale_by_dt=True), dict(dt=dt*0., scale_by_dt=True),
                    dict(cutoff=0.), dict(min_scale=0.) ]:
            with self.subTest( keys=list( kw ) ):
                with self.assertRaises( BAD ):
                    S.robust_fixed_window( x, **kw )
        with self.assertRaises( ValueError ):
            S.robust_fixed_window( x, dt, scale_by_dt=False, normalize_by_dt=True )

# ------------------------------------------------
# robust_rolling_dt_ew
# -------------------------------------------------

class TestRobustRollingDtEw( Base ):

    def test_reference(self):
        x, dt = make_series()
        for tw, init, cutoff, sb, nb, ms in [ (0.25, 10, 2.5, False, False, None), (0.25, 10, 2.5, True, False, None), (0.25, 10, 2.5, True, True, None),
                                              (0.05, 1, 1.5, True, True, None), (1., 40, 3., False, False, None), (0.25, 10, 2.5, False, False, 0.4),
                                              (0.25, 10, 2.5, True, False, 0.4), (0.25, 399, 2.5, True, True, None) ]:
            with self.subTest( tw=tw, init=init, cutoff=cutoff, scale_by_dt=sb, normalize_by_dt=nb, min_scale=ms ):
                w   = ew_weights( dt, tw )
                loc, dis, otl = ref_robust( x, w, init, cutoff, dt=dt if sb else None, min_scale=ms )
                if sb and not nb:
                    loc, dis = loc*dt, dis*np.sqrt( dt )
                self.assertSame( S.robust_rolling_dt_ew( x, dt, tw, init, cutoff, sb, nb, ms ), ( loc, dis, otl ) )

    def test_constant_dt_level_matches_ew(self):
        x, _ = make_series()
        window, d = 20., 0.01
        tw = - d / math.log1p( - 1./window )
        self.assertSame( S.robust_rolling_dt_ew( x, np.full( len(x), d ), tw, 10 ), S.robust_rolling_ew( x, window, 10 ) )

    def test_constant_dt_increments_match_ew(self):
        x, _ = make_series()
        window, d = 20., 0.01
        tw   = - d / math.log1p( - 1./window )
        m, s, o = S.robust_rolling_ew( x / d, window, 10 )
        dm, ds, do = S.robust_rolling_dt_ew( x, np.full( len(x), d ), tw, 10, scale_by_dt=True, normalize_by_dt=True )
        self.assertSame( ( dm, ds, do ), ( m, s*math.sqrt( d ), o ) )

    def test_normalization_modes(self):
        x, dt = make_series()
        m, s, o   = S.robust_rolling_dt_ew( x, dt, scale_by_dt=True, normalize_by_dt=True )
        m2, s2, o2 = S.robust_rolling_dt_ew( x, dt, scale_by_dt=True, normalize_by_dt=False )
        self.assertSame( ( m2, s2, o2 ), ( m*dt, s*np.sqrt( dt ), o ) )

    def test_warmup_and_flags(self):
        x, dt = make_series()
        for sb in [ False, True ]:
            m, s, o = S.robust_rolling_dt_ew( x, dt, 0.25, 10, scale_by_dt=sb, normalize_by_dt=sb )
            self.assertTrue( np.all( np.isnan( m[:9] ) ) and np.all( np.isnan( s[:9] ) ) )
            self.assertFalse( np.any( o[:10] ) )
            self.assertTrue( o[100] and o[300] )
            self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( s[9:] > 0. ) )

    def test_increment_statistics(self):
        rng = np.random.default_rng( 12 )
        n   = 200000
        dt  = rng.uniform( 0.001, 0.01, n )
        x   = 0.5 * dt + 0.8 * np.sqrt( dt ) * rng.standard_normal( n )
        m, s, o = S.robust_rolling_dt_ew( x, dt, twindow=5., init=200, scale_by_dt=True, normalize_by_dt=True )
        self.assertAlmostEqual( np.mean( s[-100000:] ), 0.8, delta=0.04 )
        self.assertAlmostEqual( np.mean( m[-100000:] ), 0.5, delta=0.5 )
        self.assertLess( np.mean( o[-100000:] ), 0.03 )

    def test_extreme_time_steps(self):
        cm = warnings.catch_warnings()                                  # unit weights have a zero initial MAD
        cm.__enter__()
        self.addCleanup( cm.__exit__, None, None, None )
        warnings.simplefilter( "ignore" )
        rng = np.random.default_rng( 13 )
        x   = rng.standard_normal( 100 )
        for dt in [ np.full( 100, 1e-20 ), np.full( 100, 1e5 ), np.exp( rng.uniform( -20., 8., 100 ) ) ]:
            with self.subTest( dt=dt[0] ):
                m, s, o = S.robust_rolling_dt_ew( x, dt, 0.25, 10 )
                self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( np.isfinite( s[9:] ) ) )
        dt = np.exp( rng.uniform( -15., 3., 100 ) )
        m, s, o = S.robust_rolling_dt_ew( x*np.sqrt( dt ), dt, 0.25, 10, scale_by_dt=True, normalize_by_dt=True )
        self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( np.isfinite( s[9:] ) ) )

    def test_invalid(self):
        x, dt = make_series( 30 )
        dt    = dt[:30]
        for kw in [ dict(dt=dt[:10]), dict(dt=-dt), dict(dt=dt*0.), dict(dt=dt.reshape(1,-1)),
                    dict(twindow=0.), dict(twindow=-1.),
                    dict(init=0), dict(init=31), dict(init=2.5), dict(cutoff=0.),
                    dict(min_scale=0.),
                    dict(normalize_by_dt=True), dict(scale_by_dt=1), dict(scale_by_dt=True, normalize_by_dt=1.), dict(scale_by_dt="yes") ]:
            args = dict( dt=dt, twindow=0.25, init=5, cutoff=2.5 ); args.update( kw )
            with self.subTest( keys=list( kw ) ):
                with self.assertRaises( BAD ):
                    S.robust_rolling_dt_ew( x, **args )
        with self.assertRaises( ValueError ):
            S.robust_rolling_dt_ew( x, dt, normalize_by_dt=True )
        with self.assertRaises( BAD ):                                  # below a nanosecond in increment mode
            S.robust_rolling_dt_ew( x, np.full( 30, 1e-20 ), scale_by_dt=True )

# ------------------------------------------------
# Zero initial MAD: zero-inflated, non-negative data
# -------------------------------------------------

def zero_inflated( n, seed=0, init=10, zeros_in_init=7, p_zero=0.1, mean=1. ):
    """ Non-negative series, e.g. variances: exponentially distributed with zeros. The first 'init' observations have 'zeros_in_init' zeros. """
    rng = np.random.default_rng( seed )
    x   = rng.exponential( mean, n ) * ( rng.uniform( size=n ) > p_zero )
    x[:init] = rng.exponential( mean, init ) + 0.1
    x[rng.choice( init, zeros_in_init, replace=False )] = 0.
    return x

def standard_init( x, w, dt=None ):
    """ Weighted mean and standard deviation of the initial period """
    q    = ref_terminal_weights( w )
    rate = x if dt is None else x / dt
    loc  = np.sum( q * rate )
    res  = x - loc if dt is None else ( x - loc*dt ) / np.sqrt( dt )
    return loc, math.sqrt( np.sum( q * res**2 ) )

class TestZeroInitialMad( Base ):

    def setUp(self):
        self.x  = zero_inflated( 400 )
        self.dt = np.random.default_rng( 1 ).uniform( 0.5, 1.5, 400 )
        self.calls = { "ew"         : lambda **kw: S.robust_rolling_ew( self.x, 20., 10, **kw ),
                       "dt level"   : lambda **kw: S.robust_rolling_dt_ew( self.x, self.dt, 10., 10, **kw ),
                       "dt rate"    : lambda **kw: S.robust_rolling_dt_ew( self.x, self.dt, 10., 10, scale_by_dt=True, **kw ),
                       "dt rate n"  : lambda **kw: S.robust_rolling_dt_ew( self.x, self.dt, 10., 10, scale_by_dt=True, normalize_by_dt=True, **kw ) }

    def test_data_has_zero_mad(self):
        self.assertEqual( np.median( np.abs( self.x[:10] - np.median( self.x[:10] ) ) ), 0. )

    def test_warns_by_default(self):
        for name, f in self.calls.items():
            with self.subTest( call=name ):
                with warnings.catch_warnings( record=True ) as caught:
                    warnings.simplefilter( "always" )
                    f()
                self.assertEqual( [ type( w.message ) for w in caught ], [ RuntimeWarning ] )
                self.assertIn( "on_zero_init", str( caught[0].message ) )
                self.assertTrue( caught[0].filename.endswith( "test_rolling.py" ) )   # reported at the caller
                with warnings.catch_warnings( record=True ) as caught:
                    warnings.simplefilter( "always" )
                    f( on_zero_init="warn" )
                self.assertEqual( len( caught ), 1 )

    def test_ignore_is_silent_and_unchanged(self):
        w = np.full( 400, 1./20. )
        loc, dis, otl = ref_robust( self.x, w, 10, 2.5 )
        with warnings.catch_warnings():
            warnings.simplefilter( "error" )
            self.assertSame( self.calls["ew"]( on_zero_init="ignore" ), ( loc, dis, otl ) )
            for name, f in self.calls.items():
                f( on_zero_init="ignore" )

    def test_raise(self):
        for name, f in self.calls.items():
            with self.subTest( call=name ), self.assertRaises( OverflowError ):
                f( on_zero_init="raise" )

    def test_no_message_without_zero_mad(self):
        x, dt = make_series( 100 )
        with warnings.catch_warnings():
            warnings.simplefilter( "error" )
            for mode in [ "warn", "ignore", "raise", "standard" ]:
                S.robust_rolling_ew( x, 20., 10, on_zero_init=mode )
                S.robust_rolling_dt_ew( x, dt, 0.25, 10, on_zero_init=mode )
                S.robust_rolling_dt_ew( x, dt, 0.25, 10, scale_by_dt=True, on_zero_init=mode )
        self.assertSame( S.robust_rolling_ew( x, 20., 10, on_zero_init="standard" ), S.robust_rolling_ew( x, 20., 10, on_zero_init="ignore" ) )

    def test_init_of_one_is_never_degenerate(self):
        with warnings.catch_warnings():
            warnings.simplefilter( "error" )
            for mode in [ "warn", "raise", "standard" ]:
                S.robust_rolling_ew( self.x, 20., 1, on_zero_init=mode )
                S.robust_rolling_dt_ew( self.x, self.dt, 1., 1, scale_by_dt=True, on_zero_init=mode )

    def test_standard_initialization(self):
        w   = np.full( 400, 1./20. )
        q   = ref_terminal_weights( w[:10] )
        m, s, o = S.robust_rolling_ew( self.x, 20., 10, on_zero_init="standard" )
        loc0, dis0 = standard_init( self.x[:10], w[:10] )
        self.assertAlmostEqual( m[9], loc0, places=12 ); self.assertAlmostEqual( s[9], dis0, places=12 )
        self.assertGreater( dis0, 0. )
        self.assertNotEqual( loc0, 0. )
        # the recursion itself is the usual one
        ref = ref_robust( self.x, w, 10, 2.5 )
        self.assertEqual( ref[0][9], 0. )                                     # median initialization sticks at zero
        wd  = ew_weights( self.dt, 10. )
        for dt_mode, nb in [ ( False, False ), ( True, True ), ( True, False ) ]:
            with self.subTest( scale_by_dt=dt_mode, normalize_by_dt=nb ):
                m, s, o = S.robust_rolling_dt_ew( self.x, self.dt, 10., 10, scale_by_dt=dt_mode, normalize_by_dt=nb, on_zero_init="standard" )
                loc0, dis0 = standard_init( self.x[:10], wd[:10], self.dt[:10] if dt_mode else None )
                self.assertAlmostEqual( ( m[9] / ( 1. if nb or not dt_mode else self.dt[9] ) ), loc0, places=12 )
                self.assertAlmostEqual( ( s[9] / ( 1. if nb or not dt_mode else math.sqrt( self.dt[9] ) ) ), dis0, places=12 )

    def test_standard_replaces_median_only_for_the_initial_state(self):
        # after the initial state the recursion is identical: start 'ignore' from the 'standard' state
        loc0, dis0 = standard_init( self.x[:10], np.full( 10, 1./20. ) )
        m, s, o = S.robust_rolling_ew( self.x, 20., 10, on_zero_init="standard" )
        c, floor = S._cutoff_correction( 2.5 ), EPS * max( 1., self.x[:10].max() )
        m2, s2 = loc0, dis0
        for i in range( 10, 400 ):
            ps, d = max( s2, floor ), self.x[i] - m2
            out   = abs( d ) > 2.5 * ps
            self.assertEqual( o[i], out )
            m2    = m2 if out else m2 + d / 20.
            s2    = max( ( 1. - 1./20. ) * ps + c / 20. * min( 2.5*ps, abs( d ) ), floor )
            self.assertAlmostEqual( m[i], m2, places=10 ); self.assertAlmostEqual( s[i], s2, places=10 )

    def test_median_initialization_gets_stuck(self):
        m, s, o = S.robust_rolling_ew( self.x, 20., 10, on_zero_init="ignore" )
        positive = self.x[10:] > 0.
        # the scale grows by about 10% per observation from machine precision: for the first 300 observations
        self.assertTrue( np.all( m[9:300] == 0. ) )                           # the location never moves
        self.assertTrue( np.all( o[10:300][positive[:290]] ) )                # every positive observation is an outlier
        self.assertLess( s[299], 1e-3 )

    def test_standard_recovers(self):
        m, s, o = S.robust_rolling_ew( self.x, 20., 10, on_zero_init="standard" )
        self.assertAlmostEqual( np.mean( m[-100:] ), 0.9, delta=0.35 )        # mean of the data is 0.9
        self.assertGreater( np.mean( s[-100:] ), 0.5 )
        self.assertLess( np.mean( o[-200:] ), 0.15 )
        self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( s[9:] > 0. ) )

    def test_standard_recovers_from_level_shift(self):
        rng = np.random.default_rng( 5 )
        x   = zero_inflated( 3000, seed=5, mean=1. )
        x[1000:] += 6. * ( rng.uniform( size=2000 ) > 0.1 ) + rng.exponential( 1., 2000 ) * 0.
        m, s, o = S.robust_rolling_ew( x, 20., 10, on_zero_init="standard" )
        self.assertTrue( o[1000:1010].any() )                                 # the shift is first flagged ...
        self.assertAlmostEqual( np.mean( m[-300:] ), np.mean( x[-300:] ), delta=1.0 )    # ... then tracked
        self.assertLess( np.mean( o[-300:] ), 0.15 )

    def test_constant_initial_period(self):
        x = np.concatenate( [ np.zeros( 10 ), np.ones( 50 ) ] )
        with warnings.catch_warnings():
            warnings.simplefilter( "ignore" )
            for mode in [ "warn", "standard", "ignore" ]:
                m, s, o = S.robust_rolling_ew( x, 20., 10, on_zero_init=mode )   # zero standard deviation too: same as ignoring
                self.assertSame( ( m, s, o ), S.robust_rolling_ew( x, 20., 10, on_zero_init="ignore" ) )
        with self.assertRaises( OverflowError ):
            S.robust_rolling_ew( x, 20., 10, on_zero_init="raise" )

    def test_invalid(self):
        for bad in [ "Warn", "", None, True, 1, "standard " ]:
            with self.subTest( bad=bad ), self.assertRaises( BAD ):
                S.robust_rolling_ew( self.x, 20., 10, on_zero_init=bad )
            with self.subTest( bad=bad ), self.assertRaises( BAD ):
                S.robust_rolling_dt_ew( self.x, self.dt, 1., 10, on_zero_init=bad )

# ------------------------------------------------
# Numba / input robustness
# -------------------------------------------------

def all_functions( x, dt ):
    """ Calls every public function with the same data """
    return [ lambda: S.rolling_ew_std( x, 20., 10 ),
             lambda: S.robust_rolling_ew( x, 20., 10 ),
             lambda: S.robust_rolling_dt_ew( x, dt, 0.25, 10 ),
             lambda: S.robust_rolling_dt_ew( x, dt, 0.25, 10, scale_by_dt=True ),
             lambda: S.robust_rolling_dt_ew( x, dt, 0.25, 10, scale_by_dt=True, normalize_by_dt=True ),
             lambda: S.robust_fixed_window( x ),
             lambda: S.robust_fixed_window( x, dt, scale_by_dt=True ) ]

class TestNumbaRobustness( Base ):

    def setUp(self):
        cm = warnings.catch_warnings()                                  # constant or boolean data has a zero initial MAD
        cm.__enter__()
        self.addCleanup( cm.__exit__, None, None, None )
        warnings.simplefilter( "ignore" )
        rng = np.random.default_rng( 14 )
        self.x64 = np.round( rng.standard_normal( 200 ) * 10. )
        self.x64[50] += 80.
        self.dt  = rng.uniform( 0.5, 2., 200 )

    def test_dtypes(self):
        dtypes = [ np.float16, np.float32, np.float64, np.longdouble, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64, np.bool_ ]
        for dtype in dtypes:
            for dtype_dt in [ np.float32, np.float64, np.int32 ]:
                with self.subTest( dtype=np.dtype( dtype ).name, dt=np.dtype( dtype_dt ).name ):
                    x    = self.x64
                    x    = np.abs( x ) % 120 if np.dtype( dtype ).kind in "ui" else x
                    x    = ( x > 5 ) if dtype is np.bool_ else x
                    x    = x.astype( dtype )
                    dt   = np.ceil( self.dt ).astype( dtype_dt ) if dtype_dt is np.int32 else self.dt.astype( dtype_dt )
                    for f, g in zip( all_functions( x, dt ), all_functions( x.astype( np.float64 ), dt.astype( np.float64 ) ) ):
                        got, want = f(), g()
                        if isinstance( got, float ) or isinstance( got[0], float ):
                            self.assertEqual( got, want )
                        else:
                            self.assertSame( got, want )
                            self.assertEqual( got[0].dtype, np.float64 ); self.assertEqual( got[1].dtype, np.float64 )

    def test_layouts_and_containers(self):
        base = np.round( np.random.default_rng( 15 ).standard_normal( 400 ) * 10. ) + 0.3
        dtb  = np.random.default_rng( 16 ).uniform( 0.5, 2., 400 )
        ro   = base[:200].copy(); ro.setflags( write=False )
        cases = { "strided" : ( base[::2], dtb[::2] ), "reversed" : ( base[:200][::-1], dtb[:200][::-1] ), "list" : ( list( base[:200] ), list( dtb[:200] ) ),
                  "tuple" : ( tuple( base[:200] ), tuple( dtb[:200] ) ), "readonly" : ( ro, dtb[:200] ), "fortran" : ( np.asfortranarray( base[:200] ), dtb[:200] ),
                  "big endian" : ( base[:200].astype( ">f8" ), dtb[:200].astype( ">f8" ) ), "int list" : ( [ int(v) for v in base[:200] ], dtb[:200] ),
                  "0-stride view" : ( np.lib.stride_tricks.as_strided( base[:200], ( 200, ), ( 8, ) ), dtb[:200] ) }
        for name, ( x, dt ) in cases.items():
            with self.subTest( layout=name ):
                x_ref, dt_ref = np.array( x, dtype=np.float64 ), np.array( dt, dtype=np.float64 )
                for f, g in zip( all_functions( x, dt ), all_functions( x_ref, dt_ref ) ):
                    got, want = f(), g()
                    self.assertEqual( got, want ) if isinstance( got[0], float ) else self.assertSame( got, want )
        self.assertFalse( ro.flags.writeable )

    def test_inputs_not_modified_and_not_aliased(self):
        x, dt = self.x64.copy(), self.dt.copy()
        for f in all_functions( x, dt ):
            out = f()
            if not isinstance( out[0], float ):
                for a in out:
                    self.assertFalse( np.shares_memory( a, x ) or np.shares_memory( a, dt ) )
        np.testing.assert_array_equal( x, self.x64 ); np.testing.assert_array_equal( dt, self.dt )

    def test_parameter_types(self):
        ref = S.robust_rolling_ew( self.x64, 20., 10, 3. )
        for window in [ 20, 20., np.float32( 20 ), np.float16( 20 ), np.int32( 20 ), np.int64( 20 ), np.uint8( 20 ) ]:
            for init in [ 10, np.int8( 10 ), np.int64( 10 ), np.uint16( 10 ), 10. ]:
                for cutoff in [ 3, 3., np.float32( 3 ), np.int64( 3 ), np.float16( 3 ) ]:
                    with self.subTest( window=repr( window ), init=repr( init ), cutoff=repr( cutoff ) ):
                        self.assertSame( S.robust_rolling_ew( self.x64, window, init, cutoff ), ref )
                        self.assertSame( S.rolling_ew_std( self.x64, window, init, cutoff ), S.rolling_ew_std( self.x64, 20., 10, 3. ) )
        ref = S.robust_rolling_dt_ew( self.x64, self.dt, 0.25, 10 )
        for tw in [ 0.25, np.float32( 0.25 ), np.float16( 0.25 ), np.longdouble( 0.25 ) ]:
            self.assertSame( S.robust_rolling_dt_ew( self.x64, self.dt, tw, 10 ), ref )
        for ms in [ 1, np.float32( 1 ), np.int64( 1 ), 1. ]:
            self.assertSame( S.robust_rolling_ew( self.x64, 20., 10, 3., ms ), S.robust_rolling_ew( self.x64, 20., 10, 3., 1. ) )
        for flag in [ np.bool_( True ), True ]:
            self.assertSame( S.robust_rolling_dt_ew( self.x64, self.dt, scale_by_dt=flag ), S.robust_rolling_dt_ew( self.x64, self.dt, scale_by_dt=True ) )

    def test_bad_types_and_shapes(self):
        for bad in [ None, "abc", [], np.array( [] ), np.array( 3. ), np.ones( ( 20, 2 ) ), np.ones( ( 1, 20 ) ), np.ones( ( 20, 1 ) ), np.ones( ( 2, 2, 2 ) ),
                     np.array( [ 1+2j, 3. ] * 10 ), np.array( [ "a", "b" ] * 10 ), [ [ 1., 2. ] ] * 20, 5., 5 ]:
            for name, f in [ ( "std", lambda: S.rolling_ew_std( bad, 5., 1 ) ), ( "rob", lambda: S.robust_rolling_ew( bad, 5., 1 ) ),
                             ( "fix", lambda: S.robust_fixed_window( bad ) ), ( "dt", lambda: S.robust_rolling_dt_ew( bad, np.ones( 20 ), 0.25, 1 ) ) ]:
                with self.subTest( bad=repr( bad )[:30], f=name ), warnings.catch_warnings(), self.assertRaises( BAD ):
                    warnings.simplefilter( "error" )
                    f()

    def test_scale_invariance(self):
        x, dt = self.x64, self.dt
        for k in [ 1e-100, 1e-30, 1e-6, 1e6, 1e30, 1e100, 1e150 ]:
            with self.subTest( k=k ):
                m, s, o = S.robust_rolling_ew( x*k, 20., 10, min_scale=1e-300 )
                m0, s0, o0 = S.robust_rolling_ew( x, 20., 10, min_scale=1e-300 )
                np.testing.assert_allclose( m, m0*k, rtol=1e-9, equal_nan=True ); np.testing.assert_allclose( s, s0*k, rtol=1e-9, equal_nan=True )
                self.assertTrue( np.array_equal( o, o0 ) )
                if k <= 1e100:
                    m, s = S.rolling_ew_std( x*k, 20., 10 )
                    m0, s0 = S.rolling_ew_std( x, 20., 10 )
                    if k >= 1e-6:
                        np.testing.assert_allclose( m, m0*k, rtol=1e-9, equal_nan=True ); np.testing.assert_allclose( s, s0*k, rtol=1e-9, equal_nan=True )
                    self.assertTrue( np.all( np.isfinite( s[9:] ) ) )

    def test_extreme_magnitudes_are_finite(self):
        rng = np.random.default_rng( 17 )
        x   = rng.standard_normal( 100 )
        for scale in [ 1e300, 1e-300, 1e-310, 5e-324 ]:
            with self.subTest( scale=scale ):
                for f in [ lambda: S.robust_rolling_ew( x*scale, 10., 5 ), lambda: S.rolling_ew_std( x*scale, 10., 5 ),
                           lambda: S.robust_rolling_dt_ew( x*scale, np.ones( 100 ), 1., 5 ) ]:
                    with np.errstate( over='ignore' ):
                        out = f()
                    for a in out[:2]:
                        self.assertFalse( np.any( np.isnan( a[4:] ) ) )
        for scale in [ 1e300 ]:
            self.assertTrue( np.all( np.isfinite( S.robust_rolling_ew( x*scale, 10., 5 )[1][4:] ) ) )

    def test_extreme_parameters(self):
        x = self.x64
        for cutoff in [ 1e-300, 1e-8, 38., 1e6, 1e300 ]:
            with self.subTest( cutoff=cutoff ):
                m, s, o = S.robust_rolling_ew( x, 20., 10, cutoff )
                self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( np.isfinite( s[9:] ) ) )
        for window in [ 1.0000001, 1e9, 1e15 ]:
            with self.subTest( window=window ):
                for out in [ S.robust_rolling_ew( x, window, 10 ), S.rolling_ew_std( x, window, 10 ) ]:
                    self.assertTrue( np.all( np.isfinite( out[0][9:] ) ) and np.all( np.isfinite( out[1][9:] ) ) )
        for tw in [ 1e-300, 1e-12, 1e12, 1e300 ]:
            with self.subTest( twindow=tw ):
                m, s, o = S.robust_rolling_dt_ew( x, self.dt, tw, 10 )
                self.assertTrue( np.all( np.isfinite( m[9:] ) ) and np.all( np.isfinite( s[9:] ) ) )
        m, s, o = S.robust_rolling_ew( x, 20., 10, 3., min_scale=1e300 )
        self.assertTrue( np.all( np.isfinite( s[9:] ) ) )

    def test_long_series(self):
        x  = np.random.default_rng( 18 ).standard_normal( 300000 )
        dt = np.random.default_rng( 19 ).uniform( 0.5, 1.5, len( x ) )
        for f in all_functions( x, dt ):
            out = f()
            if not isinstance( out[0], float ):
                self.assertTrue( np.all( np.isfinite( out[1][9:] ) ) )

    def test_threads(self):
        x, dt = np.random.default_rng( 20 ).standard_normal( 20000 ), np.random.default_rng( 21 ).uniform( 0.5, 1.5, 20000 )
        fs    = all_functions( x, dt )
        want  = [ f() for f in fs ]
        with ThreadPoolExecutor( 8 ) as pool:
            jobs = [ ( i, pool.submit( fs[i] ) ) for _ in range( 6 ) for i in range( len( fs ) ) ]
            for i, job in jobs:
                got = job.result()
                self.assertEqual( got, want[i] ) if isinstance( got[0], float ) else self.assertSame( got, want[i], rtol=0. )

    def test_repeated_calls_are_deterministic(self):
        for f in all_functions( self.x64, self.dt ):
            a, b = f(), f()
            self.assertEqual( a, b ) if isinstance( a[0], float ) else self.assertSame( a, b, rtol=0. )

if __name__ == '__main__':
    unittest.main()
