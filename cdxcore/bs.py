# -*- coding: utf-8 -*-
"""
Created on Thu Sep 25 17:25:04 2025 by HB
Last Updated on Tues Oct 7 10:26 2025 by RS
"""

from .pretty import PrettyObject, PrettyValueObject
from .verbose import Context   # is now a local include
from .err import verify, verify_inp
from .util import fmt_digits

import math as math
import warnings as warnings
from enum import IntFlag, auto
import numpy as np

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

try:
    import cvxpy as cp
except ModuleNotFoundError:  # pragma: no cover
    cp = None

inv_sqrt_2pi = 1.0 / np.sqrt(2.0 * np.pi)

def is_number( x ):
    """ Whether 'x' is a nuumber """
    return isinstance( x, (float, int, np.number) )

class BSFLAGS(IntFlag):
    PRICE = auto()  # Price, for a call (N1 - k N2)
    DELTA = auto()  # Delta (N1 for a call)
    DK = auto()     # dK (-N2 for a call)
    GAMMA = auto()  # Gamma
    VEGA = auto()   # Vega 
    THETA = auto()  # Theta
    LOGK = auto()   # logK with 1. where k=0 or vol*sqrtT=0

class BS(object):
    """
    Base class for the computation of Black & Scholes analytics
    in "pure" price domain/
    """

    PRICE = BSFLAGS.PRICE  # price
    DELTA = BSFLAGS.DELTA  # delta
    DK    = BSFLAGS.DK     # dk
    GAMMA = BSFLAGS.GAMMA  # gamma
    VEGA  = BSFLAGS.VEGA   # vega
    THETA = BSFLAGS.THETA  # theta
    LOGK  = BSFLAGS.LOGK   # logK (for reuse)

    def __init__(self):
        pass

    def __call__( self, k : np.ndarray|float, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., what : int = PRICE, is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None ) -> PrettyValueObject|np.ndarray|float:
        r"""
        Compute Black Scholes call option prices, delta, and dk in pure price domain.
        Essentially these are all the quantities which require computation of ``N(d1)`` and ``N(d2)``.
        
        The function blends into the intrinsic functions for $$k\downarrow0$ or $\mathrm{vol}\,\sqrt{t} \downarrow0$.
        
        Parameters
        ----------
        k : np.ndarray | float
            Strikes.
            
        vol : np.ndarray | float
            Volatilities or a single volatility.
            
        sqrtT : np.ndarray | float, default ``1``
            Square-root of time.

        what : BS, default ``BS.PRICE``
            A bitmask indicating what to compute. Can be any combination of:

            * ``BS.PRICE`` : Call price
            * ``BS.DELTA`` : Delta
            * ``BS.DK``    : Derivative in strike
            * ``BS.VEGA``  : Vega
            * ``BS.GAMMA`` : Gamma
            * ``BS.THETA`` : Theta
            * ``BS.LOGK``  : Log-strike, with 0. whereever ``k==0``. This is mainly useful to avoid recomputing ``log(k)`` multiple times.

            Note that if only one item is requested the function returns a ``np.ndarray`` or ``float``.
            Otherwise it will return a `cdxcore.pretty.PrettyValueObject` with the requested outputs as attributes.
            The following then works as expected::

                from aae.tools.bs import bs
                price, vega = bs( k=0.8, vol=0.2, sqrtT=1., what=bs.PRICE|bs.VEGA )['price','vega'] 

            The order of items is ``price, delta, dk, gamma, vega, theta, logK`` *whichever was requested*; hence you can also do::

                price, vega = bs( k=0.8, vol=0.2, sqrtT=1., what=bs.PRICE|bs.VEGA )

        logK : np.ndarray | float | None, default ``None``
            An optional pre-computed log-strike. If provided, this is used instead of computing ``log(k)`` internally.
            The function will mask this array where ``k==0``, hence ``logK`` can be left ``NaN`` in those locations.

        Returns
        -------
        result : np.ndarray|float|PrettyValueObject[str, np.ndarray|float]
            Returns a ``PrettyObject`` with the requested outputs as attributes, named

            * ``price``
            * ``delta``
            * ``dk``
            * ``vega``
            * ``gamma``
            * ``theta``
            * ``logK``

            See comments above on using this in one-line assignments.
        """
        assert np.all(np.isfinite(k)), ("Infinite strikes found")
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
        if is_number( k ) and is_number( vf ):
            verify( logK is None or is_number(logK), "'logK' must be of same shape as 'k'" )
            verify( not isinstance(is_call, np.ndarray), "'is_call' must be a single boolean when 'k', 'vol', 'sqrtT' are numbers" )
            if k==0. or vf==0.:
                pd1   = inv_sqrt_2pi
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
                    pd1   = inv_sqrt_2pi * math.exp(-0.5 * d1**2)
                    vega  = pd1 / sqrtT if (what & BS.VEGA) else None
                    gamma = pd1 / vf if (what & BS.GAMMA) else None
                    theta = 0.5 * vol * pd1 / sqrtT if (what & BS.THETA) else None
                    del pd1
                else:
                    vega = None
                    gamma = None
                    theta = None
        else:
            dtype = (k if isinstance(k,np.ndarray) else vf).dtype
            f0    = dtype.type(0.) 
            f1    = dtype.type(1.)
            verify( logK is None or logK.shape == k.shape, "'logK' must be of same shape as 'k'" )
            intr = (k==0.) | (vf==0.)
            if np.sum(intr) == k.size:
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
                    pd1   = inv_sqrt_2pi * np.exp(-0.5 * d1**2) 
                    pd1   = np.where( intr, f0, pd1 ) if not intr is None else pd1
                    vega  = pd1 / ( np.where(intr,f1,sqrtT) if not intr is None else sqrtT ) if (what & BS.VEGA) else None
                    gamma = pd1 / ( np.where(intr,f1,vf) if not intr is None else vf ) if (what & BS.GAMMA) else None
                    theta = 0.5 * vol * pd1 / ( np.where(intr,f1,sqrtT) if not intr is None else sqrtT ) if (what & BS.THETA) else None
                    del pd1
                else:
                    vega = None
                    gamma = None
                    theta = None

        assert not (what & BS.PRICE) or not C is None
        assert not (what & BS.DELTA) or not delta is None
        assert not (what & BS.DK) or not dk is None
        assert C is None or np.all(np.isfinite(C)), "Infinite C"
        assert delta is None or np.all(np.isfinite(delta)), "Infinite delta"
        assert dk is None or np.all(np.isfinite(dk)), "Infinite dk"
        assert vega is None or np.all(np.isfinite(vega)), "Infinite vega"
        assert gamma is None or np.all(np.isfinite(gamma)), "Infinite gamma"
        assert theta is None or np.all(np.isfinite(theta)), "Infinite theta"

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

        ret = PrettyObject()
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
        # flags        
        if what & BS.LOGK:
            ret.logK = logK
        if what & BS.PRICE:
            ret.price = C
        if what & BS.DELTA:
            ret.delta = N1
        if what & BS.DK:
            ret.dk = -N2
        if what & BS.VEGA:
            ret.vega = vega
        if what & BS.GAMMA:
            ret.gamma = gamma
        if what & BS.THETA:
            ret.theta = theta
        if what & BS.LOGK:
            ret.logK = logK
        assert len(ret) > 1, "Should have returned single item earlier"
        return ret

    def price( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None ):
        r"""
        Compute Black Scholes option prices in pure price domain.
        
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
                
        Returns
        -------
        price : np.ndarray
            Black Scholes prices
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.PRICE )

    def delta( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None ):
        r"""
        Compute Black Scholes option deltas in pure price domain.
        
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
                
        Returns
        -------
        delta : np.ndarray
            Black Scholes deltas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.DELTA )

    def dk( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None ):
        r"""
        Compute Black Scholes dk (derivative in k) in pure price domain.
        
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
                
        Returns
        -------
        dk : np.ndarray
            Black Scholes dk (derivative in k)
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.DK )

    def gamma( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None ):
        r"""
        Compute Black Scholes option gamma in pure price domain.
        
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
                
        Returns
        -------
        gamma : np.ndarray
            Black Scholes gammas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.GAMMA )

    def vega( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True, *, logK : np.ndarray|float|None = None ):
        r"""
        Compute Black Scholes option vega in pure price domain.
        
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
                
        Returns
        -------
        vega : np.ndarray
            Black Scholes vegas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.VEGA )

    def theta( self, k : np.ndarray, vol : np.ndarray|float, sqrtT : np.ndarray|float=1., is_call : np.ndarray|bool = True,*,  logK : np.ndarray|float|None = None ):
        r"""
        Compute Black Scholes option theta in pure price domain.
        
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
                
        Returns
        -------
        theta : np.ndarray
            Black Scholes thetas
        """
        return self( k=k, vol=vol, sqrtT=sqrtT, is_call=is_call, logK=logK, what=BS.THETA )

    def implied(
        self,
        strikes: np.ndarray,
        prices: np.ndarray,
        is_call: np.ndarray | bool = True,
        sqrtT: np.ndarray | float = 1.0,
        price_tol: np.ndarray | float = 1e-6,
        vol_min: float = 0.01,
        vol_max: float = 5.0,
        default_vol: np.ndarray | float = 0.,
        max_iters: int = 100,
        eps: float = 1e-10,
        min_vega: float = 1e-12,
        ret_only_vols: bool = True,
        warn_only : bool = False,
        verbose: Context = Context.quiet,
    ) -> PrettyValueObject|np.ndarray:
        """
        Solve for implied volatilities using a robust bisection and Newton-Raphson hybrid method.
        This function is designed to be run for a large number of potentially unrelated options, for example for a time series of surfaces of options.

        This routine

        1) Assigns ``max_vol`` to every option whose price is at or above the option price implied by ``vol_max``, and ``vol_min`` to every option whose price is at or below
        the option price implied by ``vol_min``.
        2) Initializes the search at ``default_vol`` if it is an array, or otherwise using the closed-form approximation https://repub.eur.nl/pub/1472/ERS%202004%20054%20FA.pdf (20).
        If ``default_vol`` is a float, then it is only used where the approximation fails to yield a value.
        3) Run a hybrid bisection and Newton-Raphson method to find the implied volatilities for the remaining options until

                ``|price(vol) - market_price| < price_tol`` 

        By default the function just returns the implied volatilities, or their last best guess, but if ``ret_only_vols`` is set to ``False``,
        then it returns a :class:`cdxcore.pretty.PrettyValueObject` containing the fitted prices, a boolean area indicating issues, and an error statistics object
        in the following fields:

            * ``vols`` contains the fitted volatilities;
            * ``fits`` contaisn the 
            * ``prices`` contains the input prices at those values.
            * ``failed`` contains a boolean array indicating which fits did not converge.

            * ``max_iters``: the input ``max_iters``.
            * ``iters``: iterations used.
            * ``max_err``: maximum price error.
            * ``l1_err``: average price error.
            * ``l2_err``: quadratic average price error.

            vols=vols,
                fits=fits,
                prices=prices,
                failed=failed,
                num_failed=num_failed,
                max_err=max_err,
                l1_err=l1_err,
                l2_err=l2_err,
        Parameters
        ----------
            strikes : np.ndarray
                Any shape.

            prices : np.ndarray
                Prices in the same shape as ``strikes``.

            is_call : np.ndarray | bool, default ``True``
                Boolean or boolean array of shape compatible with ``strikes``.

            sqrtT : np.ndarray | float, default ``1``
                Square-root of time as float or array compatible with ``strikes``.

            price_tol : np.ndarray | float, default ``1E-6``
                Price tolerance (typically a fraction of spreads) as
                float or array or array compatible with ``strikes``.
                A standard value is ``0.1*spread``.

            vol_min : float, default ``0.01``
                Minimum volatility.

            vol_max : float, default ``5``
                Maximum volatility.

            default_vol : np.ndarray | float, default ``0.``
                Default and initial volatility guess as float or array compatible with ``strikes``.
                See description above. Also note that ``default_vol`` will be clipped to the range ``[vol_min, vol_max]``.

            max_iters : int, default ``100``
                Maximum iterations. Usually the routine uses very few iterations.

            eps : float, default ``1E-10``
                Only used to decide whether stirke or sqrtVar are zero.

            min_vega : float, default ``1E-12``
                Minimum vega for taking an updates step.

            ret_only_vols : bool, default ``True``
                Return only vols.

            warn_only : bool, default ``False``
                If ``True``, warn of any input data issues but proceed afterwards. Does not affect consistency errors.

            verbose : :class:`cdxcore.verbose.Context`, default :attr:`cdxcore.verbose.Context.quiet`
                For printing progress information.

        Returns
        -------
        results : np.ndarray | PrettyValueObject
            See above.
        """
        if strikes.shape != prices.shape:
            raise ValueError(f"'strikes' and 'prices' must have the same shape; found {strikes.shape} and {prices.shape}")
        if np.min(strikes) < -0.0:
            raise ValueError(f"'strikes' must be positive; found {np.min(strikes):.4g}")
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

        # convert into same shape if not float
        def match_shape_or_float( x, dtype ):
            if not isinstance( x, np.ndarray):
                return dtype.type(x)
            if x.shape == strikes.shape:
                return x
            return np.full_like( strikes, np.asarray(x,copy=False), dtype=dtype )

        dtype       = np.result_type(strikes.dtype, np.float64)
        is_call     = match_shape_or_float( is_call, np.dtype(np.bool_) )
        sqrtT       = match_shape_or_float( sqrtT, dtype )   
        price_tol   = match_shape_or_float( price_tol, dtype )
        default_vol = match_shape_or_float( default_vol, dtype)
        default_vol = np.clip( default_vol, vol_min, vol_max )  

        if len(prices.shape) > 1:
            # reshape to flat arrays
            strikes     = strikes.reshape((-1,))
            prices      = prices.reshape((-1,))
            is_call     = is_call.reshape((-1,)) if isinstance(is_call, np.ndarray) else is_call
            sqrtT       = sqrtT.reshape((-1,)) if isinstance(sqrtT, np.ndarray) else sqrtT
            price_tol   = price_tol.reshape((-1,)) if isinstance(price_tol, np.ndarray) else price_tol
            default_vol = default_vol.reshape((-1,)) if isinstance(default_vol, np.ndarray) else default_vol

        f0   = dtype.type(0.)
        f1   = dtype.type(1.)
        fits = np.zeros_like(prices)  # output prices
        vols = np.zeros_like(prices)  # output vol
        intr = np.maximum( f0, np.where( is_call, f1 - strikes, strikes - f1) )
        total = len(fits)

        upper = np.where(is_call, f1, strikes)
        err_min = prices - intr
        err_max = prices - upper
        if np.any(err_min < 0.) or np.any(err_max > 0.):
            
            err_min = f"Found {fmt_digits(np.sum(err_min < 0.))} of {fmt_digits(total)} prices below instrinc value; worst undershoot is {np.min(err_min):.4g}." if np.any(err_min < 0.) else None
            err_max = f"Found {fmt_digits(np.sum(err_max > 0.))} of {fmt_digits(total)} prices above upper bound; worst overshoot is {np.max(err_max):.4g}." if np.any(err_max > 0.) else None

            if not err_min is None and not err_max is None:
                err = err_min + " " + err_max
            elif not err_min is None:
                err = err_min
            else:
                err = err_max

            if not warn_only:
                raise ValueError(err)
            warnings.warn(err)
            prices = np.maximum( intr, np.minimum( prices, upper ) )
        del err_min, err_max, upper

        logK = np.log( np.where( strikes==0., f1, strikes ) )
        price_min = self.price(k=strikes, sqrtT=sqrtT, vol=vol_min, is_call=is_call, logK=logK)
        price_max = self.price(k=strikes, sqrtT=sqrtT, vol=vol_max, is_call=is_call, logK=logK)
        assert price_min.shape == prices.shape
        assert price_max.shape == prices.shape

        def IX(v, mask):
            return v[mask] if isinstance(v, np.ndarray) else v

        tme = verbose.timer()
        verbose.write(f"Computing implied vols for {total} options:")

        # boundary cases
        # --------------

        # identify intrinsic
        done = (strikes <= eps) | (sqrtT <= eps) | (np.abs(intr - prices) <= price_tol)
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
                X = strikes[work]
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
                fits[work] = self.price( k=strikes[work], sqrtT=IX(sqrtT, work), vol=vols[work], is_call=IX(is_call, work), logK=IX(logK, work) )
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

                test_vega = self.vega( k=strikes[work], sqrtT=IX(sqrtT, work), vol=vols[work], logK=IX(logK, work) )
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
                        f"{sum(err2)} cases where a vega step at the current lower vol would take vol even lower"
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

or

    gamma = bs.gamma( k, vol, sqrtT, is_call )
"""
    
