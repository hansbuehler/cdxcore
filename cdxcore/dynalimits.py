"""
Beta Version Do Not Use
-----------------------
"""
from matplotlib.gridspec import GridSpec#NOQA
import numpy as np
from .err import verify, warn

class AutoLimits( object ):
    """
    Max/Min limit manger for dynamic figures.

    Parameters
    ----------
        low_quantile : float
            Lower quantile to use for computing a 'min' y value. Set to 0 to use 'min'.
        high_quantile : float
            Higher quantile to use for computing a 'min' y value. Set to 1 to use 'max'.
        min_length : int
            Minimum length data must have to use quantile(). If less data is presented,
            use min/max, respectively.
        lookback : int
            How many steps to lookback for any calculation. None to use all steps
    """

    def __init__(self, low_quantile, high_quantile, min_length : int = 10, lookback : int = None ) -> None:
        """
        Initialize AutoLimits.
        """

        verify( low_quantile >=0., "'low_quantile' must not be negative", exception=ValueError )
        verify( high_quantile <=1., "'high_quantile' must not exceed 1", exception=ValueError )
        verify( low_quantile<=high_quantile, "'low_quantile' not exceed 'high_quantile'", exception=ValueError )
        self.lo_q = low_quantile
        self.hi_q = high_quantile
        self.min_length = int(min_length)
        self.lookback = int(lookback) if not lookback is None else None
        self.max_y = None
        self.min_y = None
        self.min_x = None
        self.max_x = None

    def update(self, *args, axis=None ):
        """
        Add a data set to the min/max calc.

        If the x axis is ordinal for 'y':
            update(y, axis=axis )
            In this case x = np.linspace(1,y.shape[0],y.shape[0])

        Specifcy x axis 
            update(x, y, axis=axis )

        Parameters
        ----------
            *args:
                Either y or x,y
            axis: 
                along which axis to compute min/max/quantiles
        """
        assert len(args) in [1,2], ("'args' must be 1 or 2", len(args))

        y = args[-1]
        x = args[0] if len(args) > 1 else None

        if len(y) == 0:
            return
        if axis is None:
            axis  = None if len(y.shape) <= 1 else tuple(list(y.shape)[1])

        y_len = y.shape[0]
        if not self.lookback is None:
            y = y[-self.lookback:,...]
            x = x[-self.lookback:,...] if not x is None else None
            
        min_y = np.min( np.quantile( y, self.lo_q, axis=axis ) ) if self.lo_q > 0. and len(y) > self.min_length else np.min( y )
        max_y = np.max( np.quantile( y, self.hi_q, axis=axis ) ) if self.hi_q < 1. and len(y) > self.min_length else np.max( y )
        assert min_y <= max_y, ("Internal error", min_y, max_y, y)
        self.min_y = min_y if self.min_y is None else min( self.min_y, min_y )
        self.max_y = max_y if self.max_y is None else max( self.max_y, max_y )

        if x is None:
            self.min_x  = 1
            self.max_x  = y_len if self.max_x is None else max( y_len, self.max_x )
        else:
            min_        = np.min( x )
            max_        = np.max( x )
            self.min_x  = min_ if self.max_x is None else min( self.min_x, min_ )
            self.max_x  = max_ if self.max_x is None else max( self.max_x, max_ )

        return self
            
    def set( self, *, min_x = None, max_x = None,
                      min_y = None, max_y = None ) -> type:
        """
        Overwrite any of the extrema.
        Imposing an extrema also sets the other side if this would violate the requrest eg if min_x is set the function also floors self.max_x at min_x
        Returns 'self.'
        """
        verify( min_x is None or max_x is None or min_x <= max_x, "'min_x' and 'max_'x are in wrong order", min_x, max_x, exception=ValueError )
        if not min_x is None:
            self.min_x = min_x
            self.max_x = min( self.max_x, min_x )
        if not max_x is None:
            self.min_x = max( self.min_x, max_x )
            self.max_x = max_x

        verify( min_y is None or max_y is None or min_y <= max_y, "'min_y' and 'max_'x are in wrong order", min_y, max_y, exception=ValueError )
        if not min_y is None:
            self.min_y = min_y
            self.max_y = min( self.max_y, min_y )
        if not max_y is None:
            self.min_y = max( self.min_y, max_y )
            self.max_y = max_y
        return self

    def bound( self, *,  min_x_at_least = None, max_x_at_most = None,  # <= boundary limits
                         min_y_at_least = None, max_y_at_most = None,
                         ):
        """
        Bound extrema
        """
        verify( min_x_at_least is None or max_x_at_most is None or min_x_at_least <= max_x_at_most, "'min_x_at_least' and 'max_x_at_most'x are in wrong order", min_x_at_least, max_x_at_most, exception=ValueError )
        if not min_x_at_least is None:
            self.min_x = max( self.min_x, min_x_at_least )
            self.max_x = max( self.max_x, min_x_at_least )
        if not max_x_at_most is None:
            self.min_x = min( self.min_x, max_x_at_most )
            self.max_x = min( self.max_x, max_x_at_most )
            
        verify( min_y_at_least is None or max_y_at_most is None or min_y_at_least <= max_y_at_most, "'min_y_at_least' and 'max_y_at_most'x are in wrong order", min_y_at_least, max_y_at_most, exception=ValueError )
        if not min_y_at_least is None:
            self.min_y = max( self.min_y, min_y_at_least )
            self.max_y = max( self.max_y, min_y_at_least )
        if not max_y_at_most is None:
            self.min_y = min( self.min_y, max_y_at_most )
            self.max_y = min( self.max_y, max_y_at_most )
        return self

    def set_a_lim( self, ax,*, is_x,
                               min_d, 
                               rspace,
                               min_set = None,
                               max_set = None,
                               min_at_least = None,
                               max_at_most = None ):
        """ Utility function """
        min_ = self.min_x if is_x else self.min_y
        max_ = self.max_x if is_x else self.max_y
        ax_scale = (ax.get_xaxis() if is_x else ax.get_yaxis()).get_scale()
        label = "x" if is_x else "y"
        f = ax.set_xlim if is_x else ax.set_ylim
        
        if min_ is None or max_ is None:
            warn( "No data recevied yet; ignoring call" )
            return
        assert min_ <= max_, ("Internal error (1): min and max are not in order", label, min_, max_)

        verify( min_set is None or max_set is None or min_set <= max_set, lambda : f"'min_set_{label}' exceeds 'max_set_{label}': found {min_set:.4g} and {max_set:.4g}, respectively", exception=RuntimeError )
        verify( min_at_least is None or max_at_most is None or min_at_least <= max_at_most, lambda : f"'min_at_least_{label}' exceeds 'max_at_most_{label}': found {min_at_least:.4g} and {max_at_most:.4g}, respectively", exception=RuntimeError )

        if not min_set is None:
            min_ = min_set
            max_ = max(min_set, max_)
        if not max_set is None:
            min_ = min(min_, max_set)
            max_ = max_set
        if not min_at_least is None:
            min_ = max( min_, min_at_least )
            max_ = max( max_, min_at_least )
        if not max_at_most is None:
            min_ = min( min_, max_at_most )
            max_ = min( max_, max_at_most )
        
        assert min_ <= max_, ("Internal error (2): min and max are not in order", label, min_, max_)

        if isinstance( max_, int ):
            verify( ax_scale == "linear", lambda : f"Only 'linear' {label} axis supported for integer based {label} coordinates; found '{ax_scale}'", exception=AttributeError )
            max_ = max(max_, min_+1)
            f( min_, max_ )
        else:
            d = max( max_-min_, min_d ) * rspace
            if ax_scale == "linear":
                f( min_ - d, max_ + d )
            else:
                verify( ax_scale == "log", lambda : f"Only 'linear' and 'log' {label} axis scales are supported; found '{ax_scale}'", exception=AttributeError )
                verify( min_ > 0., lambda : f"Minimum for 'log' {label} axis must be positive; found {min_:.4g}", exception=ValueError )
                rdx = np.exp( d )
                f( min_ / rdx, max_ * rdx )
        return self

    def set_ylim(self, ax, *, min_dy : float = 1E-4, yrspace : float = 0.001, min_set_y = None, max_set_y = None, min_y_at_least = None, max_y_at_most = None ):
        """
        Set x limits  for 'ax'. See set_lims()
        """
        return self.set_a_lim( ax, is_x=False, min_d=min_dy, rspace=yrspace, min_set=min_set_y, max_set=max_set_y, min_at_least=min_y_at_least, max_at_most=max_y_at_most )
        
    def set_xlim(self, ax, *, min_dx : float = 1E-4, xrspace : float = 0.001, min_set_x = None, max_set_x = None, min_x_at_least = None, max_x_at_most = None ):
        """
        Set x limits  for 'ax'. See set_lims()
        """
        return self.set_a_lim( ax, is_x=True, min_d=min_dx, rspace=xrspace, min_set=min_set_x, max_set=max_set_x, min_at_least=min_x_at_least, max_at_most=max_x_at_most )

    def set_lims( self, ax, *, x : bool = True, y : bool = True,
                               min_dx : float = 1E-4, min_dy = 1E-4, xrspace = 0.001, yrspace = 0.001,
                               min_set_x = None, max_set_x = None, min_x_at_least = None, max_x_at_most = None,
                               min_set_y = None, max_set_y = None, min_y_at_least = None, max_y_at_most = None):
        """
        Set x and/or y limits  for 'ax'.

        For example for the x axis: let
            dx := max( max_x - min_x, min_dx )*xrspace

        For linear axes:
            set_xlim( min_x - dy, max_x + dx )

        For logarithmic axes
            set_xlim( min_x * exp(-dx), max_x * exp(dx) )
            
        Parameters
        ----------
            ax :
                matplotlib plot
            x, y: bool
                Whether to apply x and y limits.
            min_dx, min_dy:
                Minimum distance
            xrspace, yspace:
                How much of the distance to add to left and right.
                The actual distance added to max_x is dx:=max(min_dx,max_x-min_x)*xrspace
            min_set_x, max_set_x, min_set_y, max_set_y:
                If not None, set the respective min/max accordingly.
            min_x_at_least, max_x_at_most, min_y_at_least, max_y_at_most:
                If not None, bound the respecitve min/max accordingly.
        """
        if x: self.set_xlim(ax, min_dx=min_dx, xrspace=xrspace, min_set_x=min_set_x, max_set_x=max_set_x, min_x_at_least=min_x_at_least, max_x_at_most=max_x_at_most)
        if y: self.set_ylim(ax, min_dy=min_dy, yrspace=yrspace, min_set_y=min_set_y, max_set_y=max_set_y, min_y_at_least=min_y_at_least, max_y_at_most=max_y_at_most)
        return self
