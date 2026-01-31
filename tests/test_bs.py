# -*- coding: utf-8 -*-
"""Tests for cdxcore.bs

Created on 2026-01-31
"""

import math
import unittest
import warnings

import numpy as np


def _norm_cdf(x: float) -> float:
    # Standard normal CDF via erf; avoids depending on scipy in the test.
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_call_reference(k: float, vol: float, sqrtT: float) -> float:
    """Reference BS call price in pure price domain (F=1, df=1)."""
    vf = vol * sqrtT
    if k == 0.0 or vf == 0.0:
        return max(1.0 - k, 0.0)
    d1 = -math.log(k) / vf + 0.5 * vf
    d2 = d1 - vf
    return _norm_cdf(d1) - k * _norm_cdf(d2)


def _import_bs_or_skip():
    try:
        from cdxcore.bs import BS as BSFlag, bs as bs_instance, is_number
        from cdxcore.verbose import Context
    except Exception as e:  # pragma: no cover
        raise unittest.SkipTest(
            "cdxcore.bs could not be imported (likely missing optional deps like scipy/cvxpy): "
            + repr(e)
        )
    return BSFlag, bs_instance, is_number, Context


class TestBSBasics(unittest.TestCase):
    def test_is_number(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()
        self.assertTrue(is_number(1))
        self.assertTrue(is_number(1.5))
        self.assertTrue(is_number(np.float64(1.2)))
        self.assertFalse(is_number("1"))
        self.assertFalse(is_number(None))

    def test_scalar_call_price_delta_dk_match_reference(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        k = 0.8
        vol = 0.2
        sqrtT = 1.0

        price = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.PRICE)
        delta = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DELTA)
        dk = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DK)

        # reference
        vf = vol * sqrtT
        d1 = -math.log(k) / vf + 0.5 * vf
        d2 = d1 - vf

        self.assertAlmostEqual(price, _bs_call_reference(k, vol, sqrtT), places=12)
        self.assertAlmostEqual(delta, _norm_cdf(d1), places=12)
        # bs returns d/dk (call) as -N(d2)
        self.assertAlmostEqual(dk, -_norm_cdf(d2), places=12)

    def test_scalar_intrinsic_blending(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        # vol*sqrtT == 0 -> intrinsic
        k = 1.2
        vol = 0.0
        sqrtT = 1.0
        price = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.PRICE)
        delta = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DELTA)
        vega = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.VEGA)
        gamma = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.GAMMA)
        theta = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.THETA)

        self.assertEqual(price, 0.0)
        self.assertEqual(delta, 0.0)
        self.assertEqual(vega, 0.0)
        self.assertEqual(gamma, 0.0)
        self.assertEqual(theta, 0.0)

        # k == 0 -> intrinsic
        k = 0.0
        vol = 0.2
        sqrtT = 1.0
        price = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.PRICE)
        delta = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DELTA)
        self.assertEqual(price, 1.0)
        self.assertEqual(delta, 1.0)

    def test_put_call_adjustments(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        k = 1.1
        vol = 0.3
        sqrtT = 0.8

        call_price = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.PRICE, is_call=True)
        put_price = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.PRICE, is_call=False)
        self.assertAlmostEqual(put_price, call_price + k - 1.0, places=12)

        call_delta = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DELTA, is_call=True)
        put_delta = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DELTA, is_call=False)
        self.assertAlmostEqual(put_delta, call_delta - 1.0, places=12)

        call_dk = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DK, is_call=True)
        put_dk = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.DK, is_call=False)
        # From implementation: N2 -> N2-1 for puts, and return -N2
        self.assertAlmostEqual(put_dk, call_dk + 1.0, places=12)

    def test_vector_outputs_and_logk_masking(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        k = np.array([0.0, 0.8, 1.0, 1.2], dtype=np.float64)
        vol = np.array([0.2, 0.2, 0.0, 0.2], dtype=np.float64)
        sqrtT = np.array([1.0, 1.0, 1.0, 0.0], dtype=np.float64)  # last is intrinsic via sqrtT==0

        res = bs(k=k, vol=vol, sqrtT=sqrtT, what=BSFlag.PRICE | BSFlag.DELTA | BSFlag.VEGA | BSFlag.LOGK)
        self.assertTrue(hasattr(res, "price"))
        self.assertTrue(hasattr(res, "delta"))
        self.assertTrue(hasattr(res, "vega"))
        self.assertTrue(hasattr(res, "logK"))

        self.assertEqual(res.price.shape, k.shape)
        self.assertEqual(res.delta.shape, k.shape)
        self.assertEqual(res.vega.shape, k.shape)
        self.assertEqual(res.logK.shape, k.shape)

        # intrinsic points: k==0 or vf==0
        intrinsic_mask = (k == 0.0) | ((vol * sqrtT) == 0.0)
        # logK should be 0 where intrinsic mask is true
        np.testing.assert_allclose(res.logK[intrinsic_mask], 0.0)
        # vega should be 0 at intrinsic points
        np.testing.assert_allclose(res.vega[intrinsic_mask], 0.0)
        # prices match intrinsic call payoff max(1-k,0)
        intrinsic = np.maximum(1.0 - k, 0.0)
        np.testing.assert_allclose(res.price[intrinsic_mask], intrinsic[intrinsic_mask])

    def test_input_validation_raises(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        with self.assertRaises(ValueError):
            _ = bs(k=-0.1, vol=0.2, sqrtT=1.0)
        with self.assertRaises(ValueError):
            _ = bs(k=0.9, vol=-0.2, sqrtT=1.0)
        with self.assertRaises(ValueError):
            _ = bs(k=0.9, vol=0.2, sqrtT=-1.0)


class TestImpliedVol(unittest.TestCase):
    def test_implied_recovers_known_vol_call(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        strikes = np.array([0.8, 1.0, 1.2], dtype=np.float64)
        sqrtT = 0.7
        vol_true = 0.3
        prices = bs.price(k=strikes, vol=vol_true, sqrtT=sqrtT, is_call=True)

        vols = bs.implied(
            strikes=strikes,
            prices=prices,
            is_call=True,
            sqrtT=sqrtT,
            price_tol=1e-7,
            default_vol=0.2,
            max_iters=200,
            ret_only_vols=True,
            verbose=Context.quiet,
        )
        np.testing.assert_allclose(vols, vol_true, atol=1e-6, rtol=0.0)

    def test_implied_recovers_known_vol_put_array(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        strikes = np.array([[0.9, 1.1], [0.8, 1.2]], dtype=np.float64)
        sqrtT = np.array([[0.5, 0.5], [0.9, 0.9]], dtype=np.float64)
        is_call = np.array([[False, False], [True, False]])
        vol_true = 0.25

        prices = bs.price(k=strikes, vol=vol_true, sqrtT=sqrtT, is_call=is_call)
        vols = bs.implied(
            strikes=strikes,
            prices=prices,
            is_call=is_call,
            sqrtT=sqrtT,
            price_tol=1e-7,
            default_vol=0.2,
            max_iters=200,
            ret_only_vols=True,
            verbose=Context.quiet,
        )
        self.assertEqual(vols.shape, strikes.shape)
        np.testing.assert_allclose(vols, vol_true, atol=5e-6, rtol=0.0)

    def test_implied_intrinsic_returns_default_vol(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        strikes = np.array([1.5, 2.0], dtype=np.float64)
        sqrtT = 1.0
        # call intrinsic is 0
        prices = np.zeros_like(strikes)
        default_vol = 0.123

        vols = bs.implied(
            strikes=strikes,
            prices=prices,
            is_call=True,
            sqrtT=sqrtT,
            price_tol=1e-7,
            default_vol=default_vol,
            max_iters=50,
            ret_only_vols=True,
            verbose=Context.quiet,
        )
        np.testing.assert_allclose(vols, default_vol, atol=0.0, rtol=0.0)

    def test_implied_warn_only_clips_bad_prices(self):
        BSFlag, bs, is_number, Context = _import_bs_or_skip()

        strikes = np.array([0.8, 1.2], dtype=np.float64)
        sqrtT = 1.0
        # below intrinsic for call when strike<1
        prices = np.array([0.0, 0.0], dtype=np.float64)

        with self.assertRaises(ValueError):
            _ = bs.implied(
                strikes=strikes,
                prices=prices,
                is_call=True,
                sqrtT=sqrtT,
                price_tol=1e-6,
                default_vol=0.2,
                warn_only=False,
                ret_only_vols=True,
                verbose=Context.quiet,
            )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            vols = bs.implied(
                strikes=strikes,
                prices=prices,
                is_call=True,
                sqrtT=sqrtT,
                price_tol=1e-6,
                default_vol=0.2,
                warn_only=True,
                ret_only_vols=True,
                verbose=Context.quiet,
            )
            self.assertTrue(len(w) >= 1)
            self.assertEqual(vols.shape, strikes.shape)


if __name__ == "__main__":
    unittest.main()
