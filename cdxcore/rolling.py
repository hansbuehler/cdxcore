r"""
Robust rolling statistics.

Recursive exponentially weighted estimators of location and scale, in particular robust versions which use
the median and MAD for initialization, flag outliers, and do not let them move the location. They are available
for regular time steps (:func:`cdxcore.rolling.robust_rolling_ew`) and irregular time steps
(:func:`cdxcore.rolling.robust_rolling_dt_ew`). :func:`cdxcore.rolling.robust_fixed_window` is the non-recursive analogue.

.. code-block:: python

    import numpy as np
    from cdxcore.rolling import robust_rolling_ew, robust_rolling_dt_ew

    x = np.random.normal( size=1000 )
    x[500] = 10.

    loc, vol, outlier = robust_rolling_ew( x, window=20 )          # outlier[500] is True

    dt = np.random.uniform( 0.001, 0.01, size=1000 )
    dx = 0.1 * dt + 0.2 * np.sqrt( dt ) * np.random.normal( size=1000 )
    mu, sigma, outlier = robust_rolling_dt_ew( dx, dt, twindow=0.25, scale_by_dt=True, normalize_by_dt=True )

If `numba <https://numba.pydata.org/>`__ is installed the recursions are compiled, otherwise they run as plain python loops.
"""

import math
import warnings
import numpy as np

try:
    from numba import njit
except ModuleNotFoundError:   # pragma: no cover
    def njit( *args, **kwargs ):
        """ Replacement for numba's njit if numba is not installed """
        if len(args) == 1 and callable( args[0] ) and not kwargs:
            return args[0]
        return lambda f: f

MAD_NORMAL_SCALE = 1.482602218505602
"""Gaussian consistency factor for a median absolute deviation."""

_eps = np.finfo( np.float64 ).eps
_nano_y = 1./(255.*24.*60.*60.*1000.*1000.) # one microsecond in years of 255 days: the smallest supported time step

def _prep_series( x : np.ndarray, name : str ) -> np.ndarray:
    assert not np.iscomplexobj( x ), ("Error:", name, "must be real")
    x = np.asarray( x, dtype=np.float64 )
    assert x.ndim == 1 and x.size > 0, ("Error:", name, "must be a non-empty one-dimensional array; shape", x.shape)
    return x

def _prep_dt( x : np.ndarray, dt : np.ndarray ) -> np.ndarray:
    dt = _prep_series( dt, "dt" )
    assert dt.shape == x.shape, ("Error: 'x' and 'dt' must have the same shape", x.shape, dt.shape)
    assert np.min( dt ) > 0., ("Error: 'dt' must be strictly positive")
    return dt

def _prep_float( value : float, name : str ) -> float:
    assert np.ndim( value ) == 0 and not np.iscomplexobj( value ), ("Error:", name, "must be a real number", value)
    value = float( value )
    assert value > 0., ("Error:", name, "must be positive", value)
    return value

def _prep_init( init : int, n : int ) -> int:
    assert np.ndim( init ) == 0 and float( init ).is_integer(), ("Error: 'init' must be an integer", init)
    assert 1 <= init <= n, ("Error: 'init' must be in [1, len(x)]", init, n)
    return int( init )

def _prep_flags( scale_by_dt : bool, normalize_by_dt : bool ) -> None:
    assert isinstance( scale_by_dt, (bool, np.bool_) ), ("Error: 'scale_by_dt' must be a bool", scale_by_dt)
    assert isinstance( normalize_by_dt, (bool, np.bool_) ), ("Error: 'normalize_by_dt' must be a bool", normalize_by_dt)
    if normalize_by_dt and not scale_by_dt:
        raise ValueError( "'normalize_by_dt=True' requires 'scale_by_dt=True'; post-hoc normalization of irregular levels is invalid" )

def _min_scale( v : np.ndarray, min_scale : float ) -> float:
    if min_scale is None:
        return _eps * max( 1., float( np.max( np.abs( v ) ) ) )
    return _prep_float( min_scale, "min_scale" )

def _cutoff_correction( cutoff : float ) -> float:
    """ 1/E[min(|Z|,cutoff)] for a standard normal Z: makes the average clipped absolute innovation consistent with the standard deviation """
    return 1. / ( math.sqrt( 2. / math.pi ) * - math.expm1( - 0.5 * cutoff * cutoff ) + cutoff * math.erfc( cutoff / math.sqrt( 2. ) ) )

def _terminal_weights( w : np.ndarray ) -> np.ndarray:
    """ Weights of the initial observations in the terminal state of an exponentially weighted recursion with weights 'w' """
    q = w * np.append( np.cumprod( (1.-w)[::-1] )[::-1][1:], 1. )
    assert np.sum( q ) > 0., "Error: the exponential weights of the initial period underflow"
    return q / np.sum( q )

def _wmedian( x : np.ndarray, q : np.ndarray ) -> float:
    return np.quantile( x, 0.5, weights=q, method="inverted_cdf" )

_ON_ZERO_INIT = ( "warn", "ignore", "raise", "standard" )

def _prep_on_zero_init( on_zero_init : str ) -> str:
    assert on_zero_init in _ON_ZERO_INIT, ("Error: 'on_zero_init' must be one of", _ON_ZERO_INIT, "; found", on_zero_init)
    return on_zero_init

def _init_state( x : np.ndarray, dt : np.ndarray|None, q : np.ndarray, on_zero_init : str, stacklevel : int ) -> tuple:
    """
    Initial location, normalized absolute residuals at that location and scale of the initial period 'x' with weights 'q'.
    The location is the weighted median of 'x' if 'dt' is None, and of 'x/dt' otherwise, in which case residuals are (x-loc*dt)/sqrt(dt).
    """
    rate  = x if dt is None else x / dt
    resid = lambda loc: np.abs( x - loc ) if dt is None else np.abs( x - loc * dt ) / np.sqrt( dt )
    loc0  = _wmedian( rate, q )
    res0  = resid( loc0 )
    dis0  = MAD_NORMAL_SCALE * _wmedian( res0, q )
    if dis0 == 0. and len(x) > 1 and on_zero_init != "ignore":
        msg = f"The median absolute deviation of the initial period is zero (location {loc0:g}): observations which differ from the location will be flagged as outliers and cannot move it. Consider on_zero_init='standard'"
        if on_zero_init == "raise":
            raise OverflowError( msg )
        if on_zero_init == "warn":
            warnings.warn( msg, RuntimeWarning, stacklevel=stacklevel )
        else:
            loc0 = float( np.sum( q * rate ) )
            res0 = resid( loc0 )
            dis0 = math.sqrt( float( np.sum( q * res0 * res0 ) ) )
    return loc0, res0, dis0

def _new_state( n : int, init : int, loc0 : float, dis0 : float ) -> tuple:
    loc = np.full( n, np.nan )
    dis = np.full( n, np.nan )
    otl = np.zeros( n, dtype=np.bool_ )
    loc[init-1] = loc0
    dis[init-1] = dis0
    return loc, dis, otl

@njit(nogil=True)
def _inner_ew_std( x, w, init, cutoff, floor2, loc, dis ):
    for i in range(init, x.shape[0]):
        var    = max( dis[i-1], floor2 )
        vol    = np.sqrt( var )
        d_i    = x[i] - loc[i-1]
        dd_i   = min( cutoff * vol, max( - cutoff * vol, d_i ) )
        loc[i] = loc[i-1] if np.abs( d_i ) > cutoff * vol else loc[i-1] + w * d_i
        dis[i] = (1.-w) * ( var + w * dd_i**2 )

def rolling_ew_std( x : np.ndarray, window : float, init : int = 10, cutoff : float = 2.5 ):
    """
    Computes a standard recursive exponentially weighted mean and volatility, initialized over ``init`` steps.

    With ``w = 1/window`` and the innovation ``d[t] = x[t] - m[t-1]`` the update rule is:

    .. code-block:: python

        m[t] = m[t-1] + w * d[t]
        v[t] = (1-w) * ( v[t-1] + w * d[t]**2 )

    Here ``v`` is the variance; the function returns ``sqrt(v)``.

    An outlier is identified if ``|d[t]|`` exceeds ``cutoff * sqrt(v[t-1])``.
    In that case the mean is not updated, and the variance is updated with the capped innovation:

    .. code-block:: python

        m[t] = m[t-1]
        v[t] = (1-w) * ( v[t-1] + w * clip( d[t], -cutoff*sqrt(v[t-1]), cutoff*sqrt(v[t-1]) )**2 )

    The state is initialized at index ``init-1`` with the mean and variance of ``x[:init]``;
    earlier elements are NaN.

    Parameters
    ----------
    x : np.ndarray
        One-dimensional time series.
    window : float
        The parametrization ``w = 1/window`` means that any new observation gets the same weight
        as it would get in a rolling estimator with size ``window``. Must be greater than 1.
    init : int, optional
        Initial period. Default ``10``.
    cutoff : float, optional
        Normalized innovations exceeding this level are considered outliers. Default ``2.5``.

    Returns
    -------
    mean : np.ndarray
        Exponentially weighted mean.
    vol : np.ndarray
        Exponentially weighted volatility, i.e. a standard deviation.
    """
    x            = _prep_series( x, "x" )
    window       = _prep_float( window, "window" )
    assert window > 1., ("Error: 'window' must be greater than 1", window)
    init         = _prep_init( init, x.shape[0] )
    cutoff       = _prep_float( cutoff, "cutoff" )
    loc          = np.full( x.shape[0], np.nan )
    dis          = np.full( x.shape[0], np.nan )
    loc[init-1]  = np.mean( x[:init] )
    dis[init-1]  = np.mean( (x[:init] - loc[init-1])**2 )
    floor2       = ( _eps * max( 1., np.max( np.abs( x[:init] ) ) ) )**2
    _inner_ew_std( x, 1./window, init, cutoff, floor2, loc, dis )
    return loc, np.sqrt( dis )

@njit(nogil=True)
def _inner_robust_ew( x, w, loc, dis, otl, init, cutoff, corr, floor ):
    for i in range(init, x.shape[0]):
        vol    = max( dis[i-1], floor )
        d_i    = x[i] - loc[i-1]
        otl[i] = np.abs( d_i ) > cutoff * vol
        dd_i   = min( cutoff * vol, max( - cutoff * vol, d_i ) )
        loc[i] = loc[i-1] if otl[i] else loc[i-1] + w[i] * d_i
        dis[i] = max( (1.-w[i]) * vol + w[i] * corr * np.abs( dd_i ), floor )

@njit(nogil=True)
def _inner_robust_dt_ew( x, dt, w, loc, dis, otl, init, cutoff, corr, floor ):
    for i in range(init, x.shape[0]):
        vol    = max( dis[i-1], floor )
        r_i    = x[i] - loc[i-1] * dt[i]
        z_i    = r_i / np.sqrt( dt[i] )
        otl[i] = np.abs( z_i ) > cutoff * vol
        zz_i   = min( cutoff * vol, max( - cutoff * vol, z_i ) )
        loc[i] = loc[i-1] if otl[i] else loc[i-1] + w[i] / dt[i] * r_i
        dis[i] = max( (1.-w[i]) * vol + w[i] * corr * np.abs( zz_i ), floor )

def _robust_level_ew( x : np.ndarray, w : np.ndarray, init : int, cutoff : float, min_scale : float, on_zero_init : str ):
    floor        = _min_scale( x[:init], min_scale )
    q            = _terminal_weights( w[:init] )
    loc0, _, dis0 = _init_state( x[:init], None, q, on_zero_init, 4 )
    loc, dis, otl = _new_state( x.shape[0], init, loc0, max( dis0, floor ) )
    _inner_robust_ew( x, w, loc, dis, otl, init, cutoff, _cutoff_correction( cutoff ), floor )
    return loc, dis, otl

def robust_rolling_ew( x : np.ndarray, window : float, init : int = 10, cutoff : float = 2.5, min_scale : float|None = None, on_zero_init : str = "warn" ):
    """
    Computes a robust recursive exponentially weighted mean and volatility.

    With ``w = 1/window``, the innovation ``d[t] = x[t] - m[t-1]`` and
    ``c = 1/E[min(|Z|,cutoff)]`` for a standard normal ``Z``, the update rule is:

    .. code-block:: python

        m[t] = m[t-1] + w * d[t]
        v[t] = (1-w) * v[t-1] + w * c * abs( clip( d[t], -cutoff*v[t-1], cutoff*v[t-1] ) )

    An outlier is identified if ``|d[t]|`` exceeds ``cutoff * v[t-1]``.
    In that case the mean is not updated: ``m[t] = m[t-1]``. The volatility is updated
    using the capped innovation as above and is floored at ``min_scale``.

    The state at index ``init-1`` is initialized with the median and MAD (scaled by 1.4826) of ``x[:init]``,
    weighted by the weights the observations have in the terminal state of the recursion.
    Earlier elements are NaN.

    Parameters
    ----------
    x : np.ndarray
        One-dimensional time series.
    window : float
        The parametrization ``w = 1/window`` means that any new observation gets the same weight
        as it would get in a rolling estimator with size ``window``. Must be greater than 1.
    init : int, optional
        Initial period. Default ``10``.
    cutoff : float, optional
        Normalized innovations exceeding this level are considered outliers. Default ``2.5``.
    min_scale : float, optional
        Floor for the volatility. Defaults to machine precision times ``max(1, max(|x[:init]|))``.
    on_zero_init : str, optional
        What to do if the median absolute deviation (MAD) of the initial period is zero. This happens if more than half
        of the (weighted) observations equal the median, e.g. for zero-inflated non-negative series such as variances or volumes.
        The initial volatility is then only ``min_scale``, any later observation which differs from the location is flagged as
        an outlier and cannot move it, and the location can stay stuck for a long time. It does not apply if ``init`` is 1.
        Options:

        * ``"warn"``: issue a ``RuntimeWarning`` and continue. This is the default.
        * ``"ignore"``: continue silently.
        * ``"raise"``: raise an ``OverflowError``.
        * ``"standard"``: initialize with the (weighted) mean and standard deviation of the initial period instead
          of the median and MAD. If the initial period is constant the standard deviation is zero as well,
          and the result is as for ``"ignore"``.

    Returns
    -------
    mean : np.ndarray
        Robust mean.
    vol : np.ndarray
        Robust volatility, i.e. a standard deviation, not a variance.
    outlier : np.ndarray
        Boolean array which is ``True`` where an outlier was detected.
    """
    x      = _prep_series( x, "x" )
    window = _prep_float( window, "window" )
    assert window > 1., ("Error: 'window' must be greater than 1", window)
    init   = _prep_init( init, x.shape[0] )
    cutoff = _prep_float( cutoff, "cutoff" )
    on_zero_init = _prep_on_zero_init( on_zero_init )
    return _robust_level_ew( x, np.full( x.shape[0], 1./window ), init, cutoff, min_scale, on_zero_init )

def robust_fixed_window( x : np.ndarray,
                         dt : np.ndarray|None = None,
                         cutoff : float = 2.5,
                         scale_by_dt : bool = False,
                         normalize_by_dt : bool = False,
                         min_scale : float|None = None ):
    """
    Robust location and scale of a fixed set of equally weighted samples.

    This is the non-recursive analogue of :func:`robust_rolling_dt_ew`: the location is the median,
    and the scale is the MAD around it, multiplied by 1.4826.
    There is no warm-up and no outlier mask; ``cutoff`` is only retained to match the interface
    of the recursive functions.

    If ``dt`` is provided and ``scale_by_dt`` is ``True`` then the model

    .. code-block:: python

        x[i] = mu * dt[i] + sigma * sqrt(dt[i]) * eps[i]

    is assumed: ``mu`` is the median of ``x/dt``, and ``sigma`` is the scaled MAD of the residuals
    ``(x[i] - mu*dt[i]) / sqrt(dt[i])``.
    If ``normalize_by_dt`` is ``True`` the function returns ``mu`` and ``sigma``.
    Otherwise it returns ``mu*dt_ref`` and ``sigma*sqrt(dt_ref)`` where ``dt_ref`` is the median of ``dt``,
    i.e. quantities in the units of ``x``.

    Parameters
    ----------
    x : np.ndarray
        One-dimensional samples.
    dt : np.ndarray, optional
        Time steps, strictly positive. Ignored unless ``scale_by_dt`` is ``True``.
    cutoff : float, optional
        Not used. Default ``2.5``.
    scale_by_dt : bool, optional
        Use the increment model described above. Requires ``dt``. Default ``False``.
    normalize_by_dt : bool, optional
        Return drift rate and diffusion scale. Requires ``scale_by_dt``. Default ``False``.
    min_scale : float, optional
        Floor for the scale. Defaults to machine precision times ``max(1, max(|x|))``.

    Returns
    -------
    location : float
        Robust location.
    scale : float
        Robust scale, i.e. a standard deviation, not a variance.
    """
    _prep_flags( scale_by_dt, normalize_by_dt )
    x = _prep_series( x, "x" )
    _prep_float( cutoff, "cutoff" )
    assert dt is not None or not scale_by_dt, "Error: 'dt' must be provided if 'scale_by_dt' is True"
    if dt is not None:
        dt = _prep_dt( x, dt )
    floor = _min_scale( x, min_scale )
    if not scale_by_dt:
        loc = np.median( x )
        return float( loc ), float( max( MAD_NORMAL_SCALE * np.median( np.abs( x - loc ) ), floor ) )

    loc = np.median( x / dt )
    res = ( x - loc * dt ) / np.sqrt( dt )
    dis = max( MAD_NORMAL_SCALE * np.median( np.abs( res - np.median( res ) ) ), floor )
    if normalize_by_dt:
        return float( loc ), float( dis )
    dt_ref = np.median( dt )
    return float( loc * dt_ref ), float( dis * np.sqrt( dt_ref ) )

def robust_rolling_dt_ew( x  : np.ndarray,
                          dt : np.ndarray,
                          twindow : float = 0.25,
                          init : int = 10,
                          cutoff : float = 2.5,
                          scale_by_dt : bool = False,
                          normalize_by_dt : bool = False,
                          min_scale : float|None = None,
                          on_zero_init : str = "warn" ):
    """
    Computes a robust recursive exponentially weighted mean and volatility for irregular time steps.

    The per-step weight is ``w[t] = 1 - exp(-dt[t]/twindow)``, which is approximately ``dt[t]/twindow``.
    With ``c = 1/E[min(|Z|,cutoff)]`` for a standard normal ``Z`` the update rule is as follows.

    If ``scale_by_dt`` is ``False``, with the innovation ``d[t] = x[t] - m[t-1]``:

    .. code-block:: python

        m[t] = m[t-1] + w[t] * d[t]
        v[t] = (1-w[t]) * v[t-1] + w[t] * c * abs( clip( d[t], -cutoff*v[t-1], cutoff*v[t-1] ) )

    If ``x`` is itself a return-type quantity such as ``dS`` for a stock, use ``scale_by_dt=True``.
    The drift ``m`` is then a rate, and the innovation is normalized by ``sqrt(dt)``:

    .. code-block:: python

        d[t] = ( x[t] - m[t-1]*dt[t] ) / sqrt(dt[t])
        m[t] = m[t-1] + w[t] / dt[t] * ( x[t] - m[t-1]*dt[t] )
        v[t] = (1-w[t]) * v[t-1] + w[t] * c * abs( clip( d[t], -cutoff*v[t-1], cutoff*v[t-1] ) )

    If all time steps are equal to ``dt`` and ``twindow = window*dt``, this is equivalent to
    :func:`robust_rolling_ew` except that the estimated quantity is the mean of ``dx/dt``,
    and the volatility is that of ``(dx - m*dt)/sqrt(dt)``.

    An outlier is identified if ``|d[t]|`` exceeds ``cutoff * v[t-1]``.
    In that case ``m[t] = m[t-1]``. The volatility is updated using the capped innovation
    and is floored at ``min_scale``.

    The state at index ``init-1`` is initialized with the median and MAD (scaled by 1.4826) of ``x[:init]``,
    or of ``x[:init]/dt[:init]`` and of the normalized innovations if ``scale_by_dt`` is ``True``.
    These are weighted by the weights the observations have in the terminal state of the recursion.
    Earlier elements are NaN.

    Parameters
    ----------
    x : np.ndarray
        One-dimensional time series.
    dt : np.ndarray
        Time steps, strictly positive, same shape as ``x``.
    twindow : float, optional
        Time constant of the weights: a new observation gets the weight ``1 - exp(-dt/twindow)``.
        Default ``0.25``.
    init : int, optional
        Initial period. Default ``10``.
    cutoff : float, optional
        Normalized innovations exceeding this level are considered outliers. Default ``2.5``.
    scale_by_dt : bool, optional
        Scale returns by ``dt`` and volatilities by ``sqrt(dt)`` during estimation, see above.
        Default ``False``.
    normalize_by_dt : bool, optional
        Requires ``scale_by_dt``; otherwise a ``ValueError`` is raised.
        If ``True`` return the drift rate ``m`` and volatility ``v``.
        If ``False`` return ``m*dt`` and ``v*sqrt(dt)``, i.e. quantities in the units of ``x``.
        Default ``False``.
    min_scale : float, optional
        Floor for the volatility, in the units of the normalized innovation. Defaults to machine precision times
        the largest absolute normalized value of the first ``init`` steps (at least 1).
    on_zero_init : str, optional
        What to do if the median absolute deviation (MAD) of the initial period is zero. This happens if more than half
        of the (weighted) observations equal the median, e.g. for zero-inflated non-negative series such as variances or volumes.
        The initial volatility is then only ``min_scale``, any later observation which differs from the location is flagged as
        an outlier and cannot move it, and the location can stay stuck for a long time. It does not apply if ``init`` is 1.
        Options:

        * ``"warn"``: issue a ``RuntimeWarning`` and continue. This is the default.
        * ``"ignore"``: continue silently.
        * ``"raise"``: raise an ``OverflowError``.
        * ``"standard"``: initialize with the (weighted) mean and standard deviation of the initial period instead
          of the median and MAD. If the initial period is constant the standard deviation is zero as well,
          and the result is as for ``"ignore"``.

    Returns
    -------
    mean : np.ndarray
        Robust mean.
    vol : np.ndarray
        Robust volatility, i.e. a standard deviation, not a variance.
    outlier : np.ndarray
        Boolean array which is ``True`` where an outlier was detected relative to the previous state.
        ``outlier[init-1]`` is always ``False``.
    """
    _prep_flags( scale_by_dt, normalize_by_dt )
    x       = _prep_series( x, "x" )
    dt      = _prep_dt( x, dt )
    init    = _prep_init( init, x.shape[0] )
    cutoff  = _prep_float( cutoff, "cutoff" )
    twindow = _prep_float( twindow, "twindow" )
    on_zero_init = _prep_on_zero_init( on_zero_init )
    w       = - np.expm1( - dt / twindow )

    if not scale_by_dt:
        return _robust_level_ew( x, w, init, cutoff, min_scale, on_zero_init )

    assert np.min( dt ) >= _nano_y, ("Error: found too small 'dt':", np.min(dt), "which is less than the minimum time step", _nano_y )
    q             = _terminal_weights( w[:init] )
    loc0, res0, dis0 = _init_state( x[:init], dt[:init], q, on_zero_init, 3 )
    floor         = _min_scale( res0, min_scale )
    loc, dis, otl = _new_state( x.shape[0], init, loc0, max( dis0, floor ) )
    _inner_robust_dt_ew( x, dt, w, loc, dis, otl, init, cutoff, _cutoff_correction( cutoff ), floor )
    if not normalize_by_dt:
        loc *= dt
        dis *= np.sqrt( dt )
    return loc, dis, otl
