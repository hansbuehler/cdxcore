"""
Basic
`Black & Scholes <https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model>`__ pricing routines.

Overview
--------

This module offers with the ``bs`` instance of :class:`cdxcore.bs.BS` a basic Black & Scholes pricing framework for the drift-less case::

    from cdxbasics.bs import bs
    call = bs.price(1.,vol=0.2,sqrtT=0.1)

Aside from the respective pricing functions and greeks, ``bs`` object also offers
with :meth:`cdxcore.bs.BS.implied`
a "mass" implied volatility
solver. It can solve implied volatilities for a large number of options in one big Euler/bisection search.

The module contains the :class:`cdxcore.bs.BS`, whose use case is to define the member :attr:`cdxcore.bs.bs`
which provides the pricing functionality.
    
Import
------
.. code-block:: python

    from cdxcore.bs import bs
    
Documentation
-------------
"""

from __future__ import annotations

from .pretty import PrettyValueObject
from .verbose import Context   # is now a local include
from .err import verify, verify_inp
from .util import fmt_digits

import math as math
import warnings as warnings
from enum import IntFlag, auto, Enum
import numpy as np
from collections.abc import Mapping

# Optional dependencies
try:
    from scipy.special import ndtr  # fast N(0,1) CDF
except ModuleNotFoundError:  # pragma: no cover
    warnings.warn("SciPy not found, using fallback ndtr implementation")
    _sqrt2 = math.sqrt(2.0)

    def ndtr(x):
        """Standard normal CDF for scalars/arrays.

        Fallback implementation used when SciPy is not installed.
        """
        if isinstance(x, np.ndarray):
            # Use vectorize to preserve shape for arbitrary ndarrays.
            return 0.5 * (1.0 + np.vectorize(lambda t: math.erf(float(t) / _sqrt2))(x))
        return 0.5 * (1.0 + math.erf(float(x) / _sqrt2))

_inv_sqrt_2pi = 1.0 / np.sqrt(2.0 * np.pi)

def _is_number( x ):
    """ Whether 'x' is a number """
    return isinstance( x, (float, int, np.number) )

class BSFLAGS(IntFlag):
    PRICE = auto()  #: Flag to request Price, for a call: N1 - k N2
    DELTA = auto()  #: Flag to request Delta: N1 for a call
    DK = auto()     #: Flag to request dK: -N2 for a call
    GAMMA = auto()  #: Flag to request Gamma
    VEGA = auto()   #: Flag to request Vega 
    THETA = auto()  #: Flag to request Theta
    LOGK = auto()   #: Flag to request logK, set to 1 where k=0 or vol*sqrtT=0

class BS(object):
    """
    Base class for the computation of Black & Scholes analytics
    in drift-less ("pure") price domain.
    
    The class is synthactic sugar; simply use the one instance ``bs`` via::
        
        from cdxcore.bs import bs
        
    Then you can do::
    
        call = bs.price( 1., 0.2, sqrtT=0.5 )
        vega = bs.vega( 1., 0.2, sqrtT=0.5 )
        
    The most useful function is ``bs.implied`` documented under :meth:`cdxcore.bs.BS.implied``.
    """

    PRICE = BSFLAGS.PRICE  #: Flag to request Price, for a call: N1 - k N2
    DELTA = BSFLAGS.DELTA  #: Flag to request Delta: N1 for a call
    DK    = BSFLAGS.DK     #: Flag to request dK: -N2 for a call
    GAMMA = BSFLAGS.GAMMA  #: Flag to request Gamma
    VEGA  = BSFLAGS.VEGA   #: Flag to request Vega 
    THETA = BSFLAGS.THETA  #: Flag to request Theta, here defined as derivative in time-to-expiry (e.g. it is positive!).
    LOGK  = BSFLAGS.LOGK   #: Flag to request logK, set to 1 where k=0 or vol*sqrtT=0

    def __init__(self):
        self._eps = 1E-8

    def __call__( self, 
                  k : np.ndarray|float, 
                  vol : np.ndarray|float, 
                  sqrtT : np.ndarray|float=1., 
                  what : int = PRICE, 
                  is_call : np.ndarray|bool = True, *, 
                  logK : np.ndarray|float|None = None, 
                  eps : float | None = None ) -> PrettyValueObject|np.ndarray|float:
        r"""
        Compute Black Scholes call option prices, and greeks in drift-less price domain efficiently.
        
        This function aims to support almost any broadcast combination for its inputs.
        
        The function returns values for the intrinsic call/put functions when strikes or sqrt-variances approach zero.
        
        Example of using broadcastable shapes::
            
            from cdxcore.bs import bs, np
            sqrtT = np.array( [0.2, 0.4] ).reshape((1,2))
            nms   = np.linspace( -1,+1,11 ).reshape((11,1))
            k     = np.exp( nms * sqrtT )
            v     = np.random.normal( size=(11,1) )**2
            sqrtT = np.array( [0.2, 0.4] ).reshape((1,2))
    
            price, vega = bs( k=k, vol=v, sqrtT=sqrtT, what=bs.PRICE|bs.VEGA )['price','vega']         
            assert price.shape == (11,2)
            
        Parameters
        ----------
        k : np.ndarray | float
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.

        what : combination of :class:`cdxcore.bs.BSFLAGS` flags, default ``BS.PRICE``
            A bitmask indicating what to compute. Can be any combination of:

            * ``BS.PRICE`` : Call price
            * ``BS.DELTA`` : Delta
            * ``BS.DK``    : Derivative in strike
            * ``BS.VEGA``  : Vega
            * ``BS.GAMMA`` : Gamma
            * ``BS.THETA`` : Theta as derivative in time-to-expiry, e.g. *it is positive*.
            * ``BS.LOGK``  : Log-strike, with 1 whereever ``k==0``. This is mainly useful to avoid recomputing ``log(k)`` multiple times.

            Note that if only one item is requested the function returns a ``np.ndarray`` or ``float``.
            Otherwise it will return a :class:`cdxcore.pretty.PrettyValueObject` with the requested outputs as attributes.
            The following then works as expected::

                from cdxcore.bs import bs
                price, vega = bs( k=0.8, vol=0.2, sqrtT=1., what=bs.PRICE|bs.VEGA )['price','vega'] 

            The order of items is always "price", "delta", "dk", "gamma", "vega", "theta", "logK"
            *whichever was requested*; hence you can also do::

                price, vega = bs( k=0.8, vol=0.2, sqrtT=1., what=bs.PRICE|bs.VEGA )

        logK : np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.
            The function will mask this array where ``k==0``, hence ``logK`` can be left ``NaN`` in those locations.

        eps : float | None, default ``None``
            An optional precision tolerance for the internal checks. If not provided, the default is ``bs._eps`` (1E-8).
            Note that the function will cap/floor the values of prices or greeks with the respective bounds even if the
            validity test passed. Hence, if ``eps`` 
            is set to a large number, this will lead to floored/capped outputs. Note, however, that some bounds such
            as the maximum value of a call of spot are not tight.

        Returns
        -------
        result : np.ndarray | float | PrettyValueObject[str, np.ndarray|float]
            If only one ``what`` was requested, this function returns a ``float`` or ``np.ndarray`` for whatever calculation
            was requested.
            
            If several ``what`` were requested, this function returns a ``PrettyObject`` with the requested outputs as attributes, named and in order:

            * ``price``
            * ``delta``
            * ``dk``
            * ``vega``
            * ``gamma``
            * ``theta`` (positive!)
            * ``logK``

            That means you can access the result as follows::
                
                from cdxcore.bs import bs
                price, vega = bs( k=0.8, vol=0.2, sqrtT=1., what=bs.PRICE|bs.VEGA )['price','vega'] 
                
            or in order of "price", "delta", "dk", "gamma", "vega", "theta", "logK" (whenever requested) directly in tuple notation::

                price, gamma, vega = bs( k=0.8, vol=0.2, sqrtT=1., what=bs.PRICE|bs.VEGA|bs.GAMMA )

        Raises
        ------
        input errors: :class:`ValueError`
            If any of the inputs is invalid, e.g. negative strikes or volatilities, or if the "what" bitmask is zero or not a valid combination of flags.

        precision errors: :class:`FloatingPointError`
            In case any of the calculated values are outside their theoretical bounds by more than some tolerance.
            The tolerance level is set by ``self._eps`` which can be changed for debugging; however please raise issues of this type to the authors.
        """
        assert np.all(np.isfinite(k)), ("Infinite k found")
        assert np.all(np.isfinite(vol)), ("Infinite volatilities found")
        assert np.all(np.isfinite(sqrtT)), ("Infinite sqrtT values found")
        verify_inp( np.min(k) >= 0., "'k' cannot be negative")
        verify_inp( np.min(vol) >= 0., "'vol' cannot be negative")
        verify_inp( np.min(sqrtT) >= 0., "'sqrtT' cannot be negative")
        verify_inp( isinstance(what, IntFlag), "'what' must be a bitmask of BS items" )
        verify_inp( what != 0, "'what' cannot be zero" )

        need_N1   = (what & (BS.DELTA|BS.PRICE)) != 0
        need_N2   = (what & (BS.DK|BS.PRICE)) != 0
        need_pd1  = (what & (BS.VEGA|BS.GAMMA|BS.THETA)) != 0
        need_logK = (what & BS.LOGK) != 0

        vf   = vol * sqrtT
        
        if _is_number( k ) and _is_number( vf ):
            verify( logK is None or _is_number(logK), "'logK' must be of same shape as 'k'" )
            verify( not isinstance(is_call, np.ndarray), "'is_call' must be a single boolean when 'k', 'vol', 'sqrtT' are numbers" )
            if k==0. or vf==0.:
                pd1   = _inv_sqrt_2pi
                delta =  1. if k<1. else 0.
                dk    = -1. if k<1. else 0.
                C     = max( 1.-k, 0. )
                # Mask log-strike in intrinsic regime (k==0 or vol*sqrtT==0)
                logK  = ( 0. if not need_logK or k==0. else math.log(k) ) if logK is None else logK
                vega  = 0.
                gamma = 0.
                theta = 0.
            else:
                logK =  math.log(k) if logK is None else logK
                d1    = -logK / vf + 0.5 * vf
                d2    = d1 - vf
                N1    = ndtr(d1) if need_N1 else None
                N2    = ndtr(d2) if need_N2 else None
                C     = N1 - k * N2 if (what & BS.PRICE) else None
                delta = N1
                dk    = -N2 if not N2 is None else None
                del N1, N2

                if need_pd1:
                    pd1   = _inv_sqrt_2pi * math.exp(-0.5 * d1**2)
                    vega  = pd1 * sqrtT if (what & BS.VEGA) else None
                    gamma = pd1 / vf if (what & BS.GAMMA) else None
                    theta = 0.5 * vol * pd1 / sqrtT if (what & BS.THETA) else None
                    del pd1
                else:
                    vega = None
                    gamma = None
                    theta = None

            eps = self._eps if eps is None else eps
            if not C is None:
                assert np.isfinite(C), "Infinite C"
                I = max(0.,1-k)
                if not (C <= 1.+eps and C >= I-eps): raise FloatingPointError("Internal C bound error", C, 1., I)
                C= min(1.,max(C,I))
            if not delta is None:
                assert np.isfinite(delta), "Infinite delta"            
                if not (delta >= -eps and delta <= 1.+eps): raise FloatingPointError("Internal Delta bound error", delta, 0., 1.)
                delta = min(1.,max(delta,0.))
            if not dk is None:
                assert np.isfinite(dk), "Infinite dk"
                if not (dk <= eps and dk >= -1.-eps): raise FloatingPointError("Internal dk bound error", dk, -1., 0.)
                dk = min(0.,max(dk,-1.))
            if not vega is None:
                assert np.isfinite(vega), "Infinite vega"
                max_vega = sqrtT * _inv_sqrt_2pi
                if not (vega >= -eps and vega <= max_vega+eps): raise FloatingPointError("Internal Vega bound error", vega, 0., max_vega)
                vega = min(max_vega, max(vega,0.))
            if not gamma is None:
                assert np.isfinite(gamma), "Infinite gamma"
                max_gamma = _inv_sqrt_2pi / vf
                if not (gamma >= -eps and gamma <= max_gamma+eps): raise FloatingPointError("Internal Gamma bound error", gamma, 0., max_gamma)
                gamma = min(max_gamma, max(gamma,0.))  
            if not theta is None:
                assert np.isfinite(theta), "Infinite theta"
                max_theta = 0.5 * vol * _inv_sqrt_2pi / sqrtT
                if not (theta >= -eps and theta <= max_theta+eps): raise FloatingPointError("Internal Theta bound error", theta, 0., max_theta)
                theta = min(max_theta, max(theta,0.))

        else:
            dtype = (k if isinstance(k,np.ndarray) else vf).dtype
            f0    = dtype.type(0.) 
            f1    = dtype.type(1.)
            verify( logK is None or logK.shape == k.shape, "'logK' must be of same shape as 'k'" )
            intr = (k==0.) | (vf==0.)
            if np.sum(intr) == k.size:
                # all options are intrinsic
                delta =   np.where(k < 1., f1, f0) if (what & BS.DELTA) else None
                dk    = - np.where(k < 1., f1, f0) if (what & BS.DK) else None
                C     = np.maximum( f1-k, f0 )
                vega  = np.zeros_like(k) if (what & BS.VEGA) else None
                gamma = ( vega if not vega is None else np.zeros_like(k)) if (what & BS.GAMMA) else None
                _z    = vega if not vega is None else gamma 
                theta = ( np.zeros_like(k) if _z is None else _z ) if (what & BS.THETA) else None
                if need_logK and logK is None:
                    logK  = np.log( np.where( k==0., f1, k ) )
                del _z
            else:
                # some options are intrinsic
                intr = intr if np.any(intr) else None

                if logK is None:
                    logK = np.log( np.where( k==0., f1, k ) ) if not intr is None else np.log(k)
                vf_  = np.where( intr, f1, vf ) if not intr is None else vf

                d1    = (-logK / vf_) + 0.5 * vf 
                d2    = d1 - vf
                N1    = ( np.where(intr, f1, ndtr(d1)) if not intr is None else ndtr(d1) ) if need_N1 else None
                N2    = ( np.where(intr, f1, ndtr(d2)) if not intr is None else ndtr(d2) ) if need_N2 else None
                C     = ( np.where(intr, np.maximum(f0,f1-k), N1 - k * N2 ) if not intr is None else (N1 - k * N2) ) if (what & BS.PRICE) else None
                delta = N1 
                dk    = -N2 if not N2 is None else None 
                del N1, N2

                if need_pd1:
                    pd1   = _inv_sqrt_2pi * np.exp(-0.5 * d1**2) 
                    pd1   = np.where( intr, f0, pd1 ) if not intr is None else pd1
                    vega  = np.where(intr, f0, pd1 * sqrtT) if (what & BS.VEGA) else None
                    gamma = pd1 / ( np.where(intr,f1,vf) if not intr is None else vf ) if (what & BS.GAMMA) else None
                    theta = 0.5 * vol * pd1 / ( np.where(intr,f1,sqrtT) if not intr is None else sqrtT ) if (what & BS.THETA) else None
                    del pd1
                else:
                    vega = None
                    gamma = None
                    theta = None

            eps = self._eps if eps is None else eps
            if not C is None:
                assert np.all(np.isfinite(C)), "Infinite C"
                I = np.maximum(1.-k,0.)
                if not np.all(C-eps <= 1.):
                    raise FloatingPointError(f"Internal C bound error: #overshoot: {np.sum(C > 1.+eps)} by {np.min(C - 1.)}")
                if not np.all(C+eps >= I):
                    raise FloatingPointError(f"Internal C bound error: #undershoot: {np.sum(C < I-eps)}, by {np.max(I - C)}")
                C = np.minimum(1.,np.maximum(C,I))
            if not delta is None:
                assert np.all(np.isfinite(delta)), "Infinite delta"
                if not np.all(delta >= -eps):
                    raise FloatingPointError(f"Internal Delta bound error: #undershoot: {np.sum(delta < -eps)} by {np.max(-eps - delta)}")
                if not np.all(delta <= 1.+eps):
                    raise FloatingPointError(f"Internal Delta bound error: #overshoot: {np.sum(delta > 1.+eps)} by {np.max(delta - (1.+eps))}")
                delta = np.minimum(1.,np.maximum(delta,0.))
            if not dk is None:
                assert np.all(np.isfinite(dk)), "Infinite dk"
                if not np.all(dk <= eps):
                    raise FloatingPointError(f"Internal dk bound error: #undershoot: {np.sum(dk < -1.-eps)} by {np.max(-eps - dk)}")
                if not np.all(dk >= -1.-eps):
                    raise FloatingPointError(f"Internal dk bound error: #overshoot: {np.sum(dk > eps)} by {np.max(dk - eps)}")
                dk = np.minimum(0.,np.maximum(dk,-1.))
            if not vega is None:
                assert np.all(np.isfinite(vega)), "Infinite vega"
                max_vega = sqrtT * _inv_sqrt_2pi
                if not np.all(vega >= -eps):
                    raise FloatingPointError(f"Internal Vega bound error: #undershoot: {np.sum(vega < -eps)} by {np.max(-eps - vega)}")
                if not np.all(vega <= max_vega+eps):
                    raise FloatingPointError(f"Internal Vega bound error: #overshoot: {np.sum(vega > max_vega+eps)} by {np.max(vega - (max_vega+eps))}")
                vega = np.minimum(max_vega, np.maximum(vega,0.))
            if not gamma is None:
                assert np.all(np.isfinite(gamma)), "Infinite gamma"
                max_gamma = _inv_sqrt_2pi / vf
                if not np.all(gamma >= -eps):
                    raise FloatingPointError(f"Internal Gamma bound error: #undershoot: {np.sum(gamma < -eps)} by {np.max(-eps - gamma)}")
                if not np.all(gamma <= max_gamma+eps):
                    raise FloatingPointError(f"Internal Gamma bound error: #overshoot: {np.sum(gamma > max_gamma+eps)} by {np.max(gamma - (max_gamma+eps))}")
                gamma = np.minimum(max_gamma, np.maximum(gamma,0.))
            if not theta is None:
                assert np.all(np.isfinite(theta)), "Infinite theta"
                max_theta = 0.5 * vol * _inv_sqrt_2pi / sqrtT
                if not np.all(theta >= -eps):
                    raise FloatingPointError(f"Internal Theta bound error: #undershoot: {np.sum(theta < -eps)} by {np.max(-eps - theta)}")
                if not np.all(theta <= max_theta+eps):
                    raise FloatingPointError(f"Internal Theta bound error: #overshoot: {np.sum(theta > max_theta+eps)} by {np.max(theta - (max_theta+eps))}")
                theta = np.minimum(max_theta, np.maximum(theta,0.))

        assert not (what & BS.PRICE) or not C is None
        assert not (what & BS.DELTA) or not delta is None
        assert not (what & BS.DK) or not dk is None
        assert not (what & BS.VEGA) or not vega is None
        assert not (what & BS.GAMMA) or not gamma is None
        assert not (what & BS.THETA) or not theta is None

        # convert to puts
        if isinstance(is_call, np.ndarray):
            if np.any( ~is_call ):
                # C-P=1-K => P=C-1+K
                C = np.where( is_call, C, C + k - 1. ) if not C is None else None
                delta = np.where( is_call, delta, delta - 1. ) if not delta is None else None
                dk = np.where( is_call, dk, dk + 1. ) if not dk is None else None
        elif not bool(is_call):
            C = C + k - 1. if not C is None else None
            delta = delta - 1. if not delta is None else None
            dk = dk + 1. if not dk is None else None

        if what == BS.PRICE:
            return C
        if what == BS.DELTA:
            return delta
        if what == BS.DK:
            return dk
        if what == BS.VEGA:
            return vega
        if what == BS.GAMMA:
            return gamma
        if what == BS.THETA:
            return theta
        if what == BS.LOGK:
            return logK
        # flags in order ``price, delta, dk, gamma, vega, theta, logK``
        ret = PrettyValueObject()
        if what & BS.PRICE:
            ret.price = C
        if what & BS.DELTA:
            ret.delta = delta
        if what & BS.DK:
            ret.dk = dk
        if what & BS.GAMMA:
            ret.gamma = gamma
        if what & BS.VEGA:
            ret.vega = vega
        if what & BS.THETA:
            ret.theta = theta
        if what & BS.LOGK:
            ret.logK = logK
        assert len(ret) > 1, "Should have returned single item earlier"
        return ret
    
    @staticmethod
    def pure_to_cash( pure : Mapping, *, fwd : float, df : float ) -> PrettyValueObject:
        """
        Converts dictionary of ``pure`` price and greeks into market price and greeks.

        Assume ``Cp(T,k) = E[(X_T-k)^+]`` where ``X`` is a pure log-normal martingale.
        Let ``C(T,K) := DF F Cp(T, K/F)`` be the market call price. 

        Then:
        ```python
        Delta     = dC/dK = DF Delta^p
        Gamma     = d^2C/dK^2 = DF Gamma^p / F
        Vega      = dC/dsigma = DF F Vega^p
        Opt_Theta = dC/dt = DF F Theta^p (this is optionality theta, excluding curve and carry)
        DK        = dC/dF = DF DK^p
        ```
        
        Note that this function computes "optionality theta" as the decay due to loss of optionality,
        and excludes the effect on a change in discount factor or forward.
        
        Parameters
        ----------
        pure : ``Mapping``
            A dictionary containing any of the greeks above.
        fwd : float
            Forward price.
        df : float
            Discount factor.

        Returns
        -------
        mkt : :class:`cdxcore.pretty.PrettyValueObject`
            A dictionary with the same inputs as ``pure``; if ``theta`` was present in pure, then
            this object will contain ``opt_theta``.
        """        
        verify_inp( fwd > 0., lambda : f"'fwd' must be positive, found {fwd}" )
        verify_inp( df > 0., lambda : f"'df' must be positive, found {df}" )
        mkt = PrettyValueObject()
        if "price" in pure:
            mkt.price = pure['price'] * df * fwd
        if "delta" in pure:
            mkt.delta = pure['delta'] * df
        if "dk" in pure:
            mkt.dk = pure['dk'] * df
        if "gamma" in pure:
            mkt.gamma = pure['gamma'] * df / fwd
        if "vega" in pure:
            mkt.vega = pure['vega'] * df * fwd
        if "theta" in pure:
            mkt.opt_theta = pure['theta'] * df * fwd
        return mkt

    def price( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None, eps : float|None = None ):
        r"""
        Compute Black Scholes option prices in drift-less price domain.
        
        Parameters
        ----------
        k : np.ndarray
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.
            
        is_call : np.ndarray | bool, default ``True``
            Whether to compute call (``True``) or put (``False``) prices.

        logK: np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.

        eps : float | None, default ``None``
            An optional precision tolerance for internal price validation checks. If not provided, the default is ``bs._eps`` (1E-8).
                
        Returns
        -------
        price : np.ndarray
            Black Scholes prices
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.PRICE, eps=eps )

    def delta( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None, eps : float|None = None ):
        r"""
        Compute Black Scholes option deltas in drift-less price domain.
        
        Parameters
        ----------
        k : np.ndarray
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.
            
        is_call : np.ndarray | bool, default ``True``
            Whether to compute call (``True``) or put (``False``) prices.

        logK: np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.

        eps : float | None, default ``None``
            An optional precision tolerance for greek validation checks. If not provided, the default is ``bs._eps`` (1E-8).
                             
        Returns
        -------
        delta : np.ndarray
            Black Scholes deltas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.DELTA, eps=eps )

    def dk( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None, eps : float|None = None ):
        r"""
        Compute Black Scholes dk (derivative in k) in drift-less price domain.
        
        Parameters
        ----------
        k : np.ndarray
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.
            
        is_call : np.ndarray | bool, default ``True``
            Whether to compute call (``True``) or put (``False``) prices.

        logK: np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.

        eps : float | None, default ``None``
            An optional precision tolerance for internal price validation checks. If not provided, the default is ``bs._eps`` (1E-8).
                
        Returns
        -------
        dk : np.ndarray
            Black Scholes dk (derivative in k)
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.DK, eps=eps )

    def gamma( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None, eps : float|None = None ):
        r"""
        Compute Black Scholes option gamma in drift-less price domain.
        
        Parameters
        ----------
        k : np.ndarray
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.
            
        is_call : np.ndarray | bool, default ``True``
            Whether to compute call (``True``) or put (``False``) prices.

        logK: np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.

        eps : float | None, default ``None``
            An optional precision tolerance for greek validation checks. If not provided, the default is ``bs._eps`` (1E-8).
                
        Returns
        -------
        gamma : np.ndarray
            Black Scholes gammas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.GAMMA, eps=eps )

    def vega( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None, eps : float|None = None ):
        r"""
        Compute Black Scholes option vega in drift-less price domain.
        
        Parameters
        ----------
        k : np.ndarray
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.
            
        is_call : np.ndarray | bool, default ``True``
            Whether to compute call (``True``) or put (``False``) prices.

        logK: np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.

        eps : float | None, default ``None``
            An optional precision tolerance for greek validation checks. If not provided, the default is ``bs._eps`` (1E-8).
                
        Returns
        -------
        vega : np.ndarray
            Black Scholes vegas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.VEGA, eps=eps )

    def theta( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True,*,  logK : np.ndarray|float|None = None, eps : float|None = None ):
        r"""
        Compute Black Scholes option theta in drift-less price domain.
        
        Parameters
        ----------
        k : np.ndarray
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.
            
        is_call : np.ndarray | bool, default ``True``
            Whether to compute call (``True``) or put (``False``) prices.

        logK: np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.

        eps : float | None, default ``None``
            An optional precision tolerance for greek validation checks. If not provided, the default is ``bs._eps`` (1E-8).
                
        Returns
        -------
        theta : np.ndarray
            Black Scholes thetas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.THETA, eps=eps )

    def implied(
        self,
        k: np.ndarray,
        prices: np.ndarray,
        is_call: np.ndarray | bool = True,
        sqrtT: np.ndarray | float = 1.0, *,
        price_tol: np.ndarray | float = 1e-6,
        vol_min: float = 0.01,
        vol_max: float = 5.0,
        default_vol: np.ndarray | float = 0.,
        mask : np.ndarray|None = None,
        max_iters: int = 100,
        eps: float = 1e-10,
        min_vega: float = 1e-12,
        ret_only_vols: bool = True,
        on_exceed_bounds : str|None = "warn",
        verbose: Context = Context.quiet,
    ) -> PrettyValueObject|np.ndarray:
        """
        Solve for implied volatilities using a robust bisection and Newton-Raphson hybrid method.
        This function is designed to be run for a large number of potentially unrelated options, for example for a time series of surfaces of options.

        This routine:

        1) Assigns ``max_vol`` to every option whose price is at or above the option price implied by ``vol_max``, and ``vol_min`` to every option whose price is at or below
           the option price implied by ``vol_min``.
        
        2) Initializes the search at ``default_vol`` if it is an array, or otherwise using the `closed-form approximation (20) <https://repub.eur.nl/pub/1472/ERS%202004%20054%20FA.pdf>`__.
           If ``default_vol`` is a float, then it is only used where the approximation fails to yield a value.
        
        3) Run a hybrid bisection and Newton-Raphson method to find the implied volatilities for the remaining options until the maximum number of itersations, ``max_iters``, is reached
           or the method has converged in the sense that::

                |price(vol) - market_price| < price_tol

        By default the function just returns the implied volatilities, or their last best guesses.
        If ``ret_only_vols`` is set to ``False``,
        then it returns a :class:`cdxcore.pretty.PrettyValueObject` containing the fitted prices, a boolean area indicating issues, and an error statistics object
        in the following fields:

        * ``vols`` contains the fitted volatilities.
        * ``fits`` contains the the prices at the fitted volatilities.
        * ``prices`` contains the input prices at those values.
        * ``failed`` contains a boolean array indicating which fits did not converge.

        * ``max_iters``: the input ``max_iters``.
        * ``iters``: iterations used.
        * ``max_err``: maximum price error.
        * ``l1_err``: average price error.
        * ``l2_err``: quadratic average price error.

        Parameters
        ----------
            k : np.ndarray
                Strikes.

            prices : np.ndarray
                Prices in the same shape as ``k``.

            is_call : np.ndarray | bool, default ``True``
                Boolean or boolean array of shape compatible with ``k``.

            sqrtT : np.ndarray | float, default ``1``
                Square-root of time as float or array compatible with ``k``.

            price_tol : np.ndarray | float, default ``1E-6``
                Price tolerance (typically a fraction of spreads) as
                float or array or array compatible with ``k``.
                A standard value is ``0.1*spread``.

            vol_min : float, default ``0.01``
                Minimum volatility.

            vol_max : float, default ``5``
                Maximum volatility.

            default_vol : np.ndarray | float, default ``0.``
                Default and initial volatility guess as float or array compatible with ``k``.
                See description above. Also note that ``default_vol`` will be clipped to the range ``[vol_min, vol_max]``.
                
            mask : np.ndarray | None, default ``None``
                A numpy array boolean mask to indicate which options to process.
                The implied vol of options excluded by ``mask`` will be set to ``default_vol``.

            max_iters : int, default ``100``
                Maximum iterations. Usually the routine uses very few iterations.

            eps : float, default ``1E-10``
                Only used to decide whether stirke or sqrtVar are zero.

            min_vega : float, default ``1E-12``
                Minimum vega for taking an updates step.

            ret_only_vols : bool, default ``True``
                Return only vols.

            on_exceed_bounds : ``error`` | ``warn`` | ``quiet`` | None, default ``warn``
                What to do if the input data violate basic option price bounds such as intrinsic from below or
                unit/strike from above, respectively. 
                ``None`` is equivalent to ``quiet``.

            verbose : :class:`cdxcore.verbose.Context`, default :attr:`cdxcore.verbose.Context.quiet`
                For printing progress information.

        Returns
        -------
        results : np.ndarray | PrettyValueObject
            See above.
        """
        if k.shape != prices.shape:
            raise ValueError(f"'k' and 'prices' must have the same shape; found {k.shape} and {prices.shape}")
        if np.min(k) < -0.0:
            raise ValueError(f"'k' must be positive; found {np.min(k):.4g}")
        if np.min(price_tol) < 1e-8:
            raise ValueError( f"'price_tol' must be bigger than 1E-8. Found a minimum of {np.min(price_tol):.6g}" )
        if np.min(default_vol) < 0.0:
            raise ValueError(f"'default_vol' must be non-negative; found minimum {np.min(default_vol):.4g}")
        if vol_min < 0.:
            raise ValueError(f"'vol_min' must be non-negative; found {vol_min:.4g}")
        if vol_min>=vol_max:
            raise ValueError(f"'vol_min' must be smaller than 'vol_max'; found {vol_min:.4g} and {vol_max:.4g}")     
        if min_vega <= 0.:
            raise ValueError(f"'min_vega' must be positive; found {min_vega:.4g}")
        if max_iters <= 0:
            raise ValueError(f"'max_iters' must be positive; found {max_iters}")
        shape = prices.shape
        assert np.all(np.isfinite(prices)), "Infinite input prices"
        if not mask is None and not isinstance(mask, np.ndarray):
            raise ValueError("'mask' must be an ndarray")

        # convert into same shape if not float
        def match_shape_or_float( x, dtype ):
            if not isinstance( x, np.ndarray):
                return dtype.type(x)
            if x.shape == k.shape:
                return x
            return np.full_like( k, np.asarray(x,copy=False), dtype=dtype )

        dtype       = np.result_type(k.dtype, np.float64)
        is_call     = match_shape_or_float( is_call, np.dtype(np.bool_) )
        sqrtT       = match_shape_or_float( sqrtT, dtype )   
        price_tol   = match_shape_or_float( price_tol, dtype )
        mask        = match_shape_or_float( mask.astype(np.bool_), np.bool_ ) if not mask is None else None
        default_vol = match_shape_or_float( default_vol, dtype)
        default_vol = np.clip( default_vol, vol_min, vol_max )  

        if len(prices.shape) > 1:
            # reshape to flat arrays
            k           = k.reshape((-1,))
            prices      = prices.reshape((-1,))
            is_call     = is_call.reshape((-1,)) if isinstance(is_call, np.ndarray) else is_call
            sqrtT       = sqrtT.reshape((-1,)) if isinstance(sqrtT, np.ndarray) else sqrtT
            price_tol   = price_tol.reshape((-1,)) if isinstance(price_tol, np.ndarray) else price_tol
            default_vol = default_vol.reshape((-1,)) if isinstance(default_vol, np.ndarray) else default_vol
            mask        = mask.reshape((-1,)) if not mask is None else None

        f0   = dtype.type(0.)
        f1   = dtype.type(1.)
        fits = np.zeros_like(prices)  # output prices
        vols = np.zeros_like(prices)  # output vol
        intr = np.maximum( f0, np.where( is_call, f1 - k, k - f1) )
        total = len(fits) if mask is None else np.sum(mask)

        upper = np.where(is_call, f1, k)
        err_min = prices - intr   < 0. 
        err_max = prices - upper  > 0.
        
        if not mask is None:
            err_min = np.where( mask, err_min, 0. )
            err_max = np.where( mask, err_max, 0. )

        if np.any(err_min < 0.) or np.any(err_max > 0.):            
            str_err_min = None
            if np.any(err_min < 0.):                
                str_err_min = f"Found {fmt_digits(np.sum(err_min < 0.))} of {fmt_digits(total)} prices below instrinc value; worst undershoot is {np.min(prices - intr):.4g}. "
                ixs = np.arange(len(err_min))[ err_min < 0. ]
                if len(ixs) > 10:
                    str_err_min += "Showing first 10 violations: "
                    ixs = ixs[:10]
                else:
                    str_err_min += "Violations: "
                for ix in ixs:
                    str_err_min += f"price[{ix}] {prices[ix]} < intrinsic[{ix}] {intr[ix]}, "
                str_err_min = str_err_min[:-2] + "."
            str_err_min = None
            if np.any(err_max > 0.):                
                str_err_max = f"Found {fmt_digits(np.sum(err_max > 0.))} of {fmt_digits(total)} prices above their  upper bound; worst overshoot is {np.max(prices - upper):.4g}. "
                ixs = np.arange(len(err_max))[ err_max > 0. ]
                if len(ixs) > 10:
                    str_err_max += "Showing first 10 violations: "
                    ixs = ixs[:10]
                else:
                    str_err_max += "Violations: "
                for ix in ixs:
                    str_err_max += f"price[{ix}] {prices[ix]} > upper[{ix}] {upper[ix]}, "
                str_err_max = str_err_max[:-2] + "."
                
            if not str_err_min is None and not str_err_max is None:
                err = str_err_min + " " + str_err_max
            else:
                err = str_err_min if not str_err_min is None else str_err_max

            if on_exceed_bounds == "error":
                raise ValueError(err)
            elif on_exceed_bounds == "warn":
                warnings.warn(err)
            else:
                verify_inp( on_exceed_bounds is None or on_exceed_bounds == "quiet", lambda : f"'on_exceed_bounds' must be 'error', 'warn', or 'quiet'. Found '{on_exceed_bounds}'")
            prices = np.maximum( intr, np.minimum( prices, upper ) )
        del err_min, err_max, upper

        logK = np.log( np.where( k==0., f1, k ) )
        price_min = self.price(k=k, sqrtT=sqrtT, vol=vol_min, is_call=is_call, logK=logK, eps=eps)
        price_max = self.price(k=k, sqrtT=sqrtT, vol=vol_max, is_call=is_call, logK=logK, eps=eps)
        assert price_min.shape == prices.shape
        assert price_max.shape == prices.shape

        def IX(v, mask):
            return v[mask] if isinstance(v, np.ndarray) else v

        tme = verbose.timer()
        verbose.write(f"Computing implied vols for {total} options:")

        # boundary cases
        # --------------

        # identify intrinsic
        done = (k <= eps) | (sqrtT <= eps) | (np.abs(intr - prices) <= price_tol) 
        if not mask is None:
            done |= ~mask
            del mask
            
        fits[done] = intr[done]
        vols[done] = IX(default_vol, done)
                                
        work = ~done
        verbose.report(1, lambda: f"Used intrinsic value for {sum(done)} options.")

        # identify options priced at or beyond vol_max
        done = (price_max - prices <= price_tol) & work
        fits[done] = price_max[done]
        vols[done] = vol_max
        work &= ~done
        verbose.report(1, lambda: f"Used maximum volatility {vol_max:.3f} for {sum(done)} options.")

        # identify options priced at or beyond vol_min
        ## RS FIX: vol_min wasn't masked with work
        # done           = prices - price_min <= price_tol
        done = (prices - price_min <= price_tol) & work
        fits[done] = price_min[done]
        vols[done] = vol_min
        work &= ~done
        verbose.report(1, lambda: f"Used minimum volatility {vol_min:.3f} for {sum(done)} options.")

        if not np.any(work):
            verbose.report(1, lambda: "*** No further implied volatilities to be computed ***")
        else:
            # initial guess
            # -------------
            # https://repub.eur.nl/pub/1472/ERS%202004%20054%20FA.pdf (20)
            ## RS MOD: Generalizing to both calls and puts

            if not isinstance(default_vol, np.ndarray):
                S = 1.0
                X = k[work]
                PR_raw = prices[work]
                isc_work = IX(is_call,work)

                # C-P=1-K => P=C-1+K => C=P+1-K
                C_eq = np.where(isc_work, PR_raw, PR_raw + S - X)

                # [27-01-2026 RS] FIX: 
                # C_eq is a call-equivalent price, so guard it against CALL price bounds, not put bounds
                # The original code used price_min/price_max which are computed with is_call, 
                # but C_eq should be clipped to call bounds regardless of option type (puts too)
                
                # C_eq = np.minimum(np.maximum(C_eq, price_min[work]), price_max[work])  # guard
                call_price_min = price_min[work] + np.where( isc_work, f0, S - X )
                call_price_max = price_max[work] + np.where( isc_work, f0, S - X )
                C_eq = np.minimum(np.maximum(C_eq, call_price_min), call_price_max)

                vols[work] = (
                    np.sqrt(2.0 * np.pi)
                    / (2.0 * (S + X))
                    * (
                        2.0 * C_eq
                        + X
                        - S
                        + np.sqrt(
                            np.maximum(
                                0, (2.0 * C_eq + X - S) ** 2 - 2.0 * (S + X) * ((X - S) ** 2) / (S * np.pi)
                            )
                        )
                    )
                    / IX(sqrtT,work)
                )
                if not np.all(np.isfinite(vols)):
                    verbose.report( 1, lambda: f"**** Found {sum(~np.isfinite(vols))} infinite initial guess vols" )
                    vols[~np.isfinite(vols)] = float(default_vol)

                del call_price_min, call_price_max, C_eq, PR_raw, isc_work, S, X
            del price_min, price_max, default_vol, done

            vols[work] = np.clip(vols[work], vol_min, vol_max)
            assert np.all(np.isfinite(vols)), "Infinite vols"

            vols_min = np.full_like(vols, vol_min)
            vols_max = np.full_like(vols, vol_max)

            # train
            # -----

            iters = 0
            while True:
                # check convergence
                # -----------------
                fits[work] = self.price( k=k[work], sqrtT=IX(sqrtT, work), vol=vols[work], is_call=IX(is_call, work), logK=IX(logK, work), eps=eps )
                done = (np.abs(fits - prices) < price_tol) & work
                work &= ~done
                if not np.any(work):
                    verbose.report( 2, lambda: f"\rStep {iters}/{max_iters}: implied vol for the remaining {sum(done)} options computed.", end="")
                    break

                if iters >= max_iters:
                    verbose.report(2, lambda: f"\rReached maximum iterations {max_iters} with {sum(work)} options left to do.", end="")
                    break

                # iteration
                # ---------

                iters += 1
                res_max_err = np.max(np.abs(fits[work] - prices[work]) / IX(price_tol, work))
                if tme.interval_test(0.5):
                    verbose.report(2, lambda: f"\rStep {iters}/{max_iters}: implied vol for {sum(done)} options computed; {sum(work)} options with a maximum error of {res_max_err:.4g} left to do.",end="")
                del done, res_max_err

                # adjust min/max
                too_low = (fits < prices) & work
                vols_min[too_low] = vols[too_low]
                too_high = (fits > prices) & work
                vols_max[too_high] = vols[too_high]

                # first order:
                # prices(x) = prices(x0) + prices'(x0) * (x-x0)
                # =>
                # x ~ ( prices(x) - prices(x0) ) / prices'(x0) + x0

                test_vega = self.vega( k=k[work], sqrtT=IX(sqrtT, work), vol=vols[work], logK=IX(logK, work), eps=eps )
                newton_step = (prices[work] - fits[work]) / np.maximum( test_vega, min_vega )
                new_vols = vols[work] + newton_step

                # [27-01-2026 RS] FIX: 
                # --- Newton-Raphson Oscillation Fallback using Bisection --- #
                # Use Newtown-Bisection hybrid step to prevent overshoot
                # c.f. `nbs/tests/test_fit_implied.py` analysis
                # Use bisection when Newton step would jump outside the bracketed interval
                # This prevents oscillation when vega is very small (e.g., deep ITM puts)
                use_bisection = (new_vols < vols_min[work]) | (new_vols > vols_max[work])
                if np.any(use_bisection):
                    bisection_vols = 0.5 * (vols_min[work] + vols_max[work])
                    new_vols = np.where(use_bisection, bisection_vols, new_vols)
                # --------------------------------------------------------- #
                err1 = (vols[work] == vols_min[work]) & (new_vols < vols[work])
                err2 = (vols[work] == vols_max[work]) & (new_vols > vols[work])

                if sum(err1 | err2) > 0:
                    err1 = (
                        f"{sum(err1)} cases where a vega step at the current lower vol would take vol even lower"
                        if sum(err1) > 0
                        else None
                    )
                    err2 = (
                        f"{sum(err2)} cases where a vega step at the current upper vol would take vol even higher"
                        if sum(err2) > 0
                        else None
                    )
                    if err1 is not None and err2 is not None:
                        raise RuntimeError(f"Convergence error: had {err1} and {err2}.")
                    raise RuntimeError(
                        f"Convergence error: had {err1 if err1 is not None else err2}."
                    )

                vols[work] = np.clip(new_vols, vols_min[work], vols_max[work])
                del new_vols, newton_step, test_vega, too_low, too_high, err1, err2

        if ret_only_vols and not verbose.shall_report():
            return vols.reshape(shape)

        iters      = int(iters)
        max_iters  = int(max_iters)
        num_failed = np.sum(work)
        max_err    = float(np.max(np.abs(fits - prices)))
        l1_err     = float(np.mean(np.abs(fits - prices)))
        l2_err     = float(np.std(fits - prices))

        verbose.write(
            lambda: f"\rImplied vol calculation for {total} options finished using {iters}/{max_iters} iterations. "
            + ( f"Failed to converge for {num_failed} options. " if num_failed > 0 else "Converged for all options. " )
            + f"Max error {max_err:.3f}, L1 error {l1_err:.3f}, L2 error {l2_err:.3f}. "
            + f"This took {tme}. "
        )

        vols = vols.reshape(shape)
        if ret_only_vols:
            return vols

        fits   = fits.reshape(shape)
        prices = prices.reshape(shape)
        failed = work.reshape(shape)

        return PrettyValueObject(
                vols=vols,
                fits=fits,
                prices=prices,
                failed=failed,
                num_failed=num_failed,
                max_err=max_err,
                l1_err=l1_err,
                l2_err=l2_err,
            )

bs = BS()
"""
Main instance of the :class:`cdxcore.bs.BS` class.

This is synthatic sugar for being able to write::

    from cdxcore.bs import bs
    price, vega = bs( k, vol, sqrtT, is_call, what=BS.PRICE|BS.VEGA )

or::

    gamma = bs.gamma( k, vol, sqrtT, is_call )
"""
    
