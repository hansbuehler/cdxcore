"""
Overview
--------

Tools for dynamic/animated plotting in Jupyer/IPython.
The aim of the toolkit is making it easier to develop
animated visualization with :mod:`matplotlib`,
for example during training with machine learing kits such as
*pyTorch*. This has been tested with Anaconda's
JupyterHub and ``%matplotlib inline``. 

It also makes the creation of subplots more streamlined.

The package now contains a lazy method to manage updates to graphs (animations).
This is implemented as follows:

* Create a figure with :func:`cdxcore.dynaplot.figure`. Then call :func:`cdxcore.dynaplot.DynaFig.store`
  to return an "element store".

* When creating new matplotlib elements such as plots, figures, fills, lines, add them to the store with ``store +=``. Do not add elements you wish to retain
  (for example legends if the dictionary of plots stays the same between updates).

* Call :meth:`cdxcore.dynaplot.DynaFig.render` to render all graphical elements. Do not call :meth:`cdxcore.dynaplot.DynaFig.close`.

* To update your elements (i.e. animation) call
  :meth:`cdxcore.dynaplot.FigStore.remove` to remove all old graphical elements
  (this function calls :meth:`matplotlib.axes.Axes.remove`).

* Then re-create the cleared elements, and call :meth:`cdxcore.dynaplot.DynaFig.render` again.
  
* When your animation is finished, call :meth:`cdxcore.dynaplot.DynaFig.close`.

  If you do not call close, you will likely see
  unwanted copies of your plots in Jupyter.

Here is an example of animated line plots using :func:`cdxcore.dynaplot.DynaFig.store`::

    %matplotlib inline
    import numpy as np
    from cdxcore.dynaplot import figure   # 'figure' is an alias for DynaFig
    
    x  = np.linspace(0,1,100)
    pm = 0.2
    
    fig = figure(col_size=10)
    ax  = fig.add_subplot()
    ax2 = fig.add_subplot()
    ax2.sharey(ax)
    store = fig.store()
    
    fig.render()
    
    import time
    for i in range(5):
        y = np.random.random(size=(100,))
        ax.set_title(f"Test {i}")
        ax2.set_title(f"Test {i}")
    
        store.remove() # delete all previously stored elements
        store += ax.plot(x,y,":", label=f"data {i}")
        store += ax2.plot(x,y,"-",color="red", label=f"data {i}")
        store += ax2.fill_between( x, y-pm, y+pm, color="blue", alpha=0.2 )
        store += ax.legend()
    
        fig.render()
        time.sleep(0.5)
    fig.close()

.. image:: /_static/dynaplot.gif

This example shows the use of ``store`` with different elements.

Here is an example with 
animated 3D plots, calling :meth:`matplotlib.axes.Axes.remove` manually::
    
    %matplotlib inline
    import numpy as np
    from cdxcore.dynaplot import figure   # 'figure' is an alias for DynaFig
    import math
        
    x = np.linspace(0.,2.*math.pi,51)
    y = x
    
    fig  = figure()
    ax1  = fig.add_subplot(projection='3d')
    ax2  = fig.add_subplot(projection='3d')
    ax1.set_xlim(0.,2.*math.pi)
    ax1.set_ylim(0.,2.*math.pi)
    ax1.set_zlim(-2,+2)
    ax1.set_title("Color specified")
    ax2.set_xlim(0.,2.*math.pi)
    ax2.set_ylim(0.,2.*math.pi)
    ax2.set_zlim(-2,+2)
    ax2.set_title("Color not specified")
    fig.render()
    r1 = None
    r2 = None
    import time
    for i in range(50):
        time.sleep(0.01)
        z = np.cos( float(i)/10.+x )+np.sin( float(i)/2.+y )
        if not r1 is None: r1.remove()
        if not r2 is None: r2.remove()
        r1 = ax1.scatter( x,y,z, color="blue" )
        r2 = ax2.scatter( 2.*math.pi-x,math.pi*(1.+np.sin( float(i)/2.+y )),z )
        fig.render()
    fig.close()
    print("/done")

.. image:: /_static/dynaplot3D.gif

The `jupyter notebook <https://github.com/hansbuehler/cdxcore/blob/main/notebooks/dynaplot.ipynb>`__
contains a few more examples. 

Simpler sub_plot
^^^^^^^^^^^^^^^^

The package lets you create sub plots without having to know the number of plots in advance.
You have the following two main
options when creating a new :func:`cdxcore.dynaplot.figure`:
    
* Define as usual ``figsize``, and specify the number of ``columns``. In this case
  the figure will arrange plots you add with
  :meth:`cdxcore.dynaplot.DynaFig.add_subplot` iteratively
  with at most ``columns`` plots per row. ``add_subplot()`` will not need
  any additional positional arguments.
  
* Instead, you can specify ``col_size``, ``row_size``, and ``columns``: the
  first two define the size per subplot. Like before you then add your sub plots using 
  :meth:`cdxcore.dynaplot.DynaFig.add_subplot` without any additional
  positioning arguments.

  Assuming you add N subplots, then the overall ``figsize`` will be ``(col_size* (N%col_num),  row_size (N//col_num))``.

When adding plots with :meth:`cdxcore.dynaplot.DynaFig.add_subplot` you can
make it skip to the first column in the next row, 
by calling :meth:`cdxcore.dynaplot.DynaFig.next_row`.

The example also shows that we can specify titles for subplots and figures easily::
    
    %matplotlib inline
    import numpy as np
    from cdxcore.dynaplot import figure   # 'figure' is an alias for DynaFig

    fig    = figure(title="Multi Graph", columns=4)
    ref_ax = None
    x = np.linspace(0,1,100)
    for k in range(9):
        ax = fig.add_subplot(f"Test {k}")
        y = np.random.random(size=(100,1))
        ax.plot(x,y,":",color="red", label="data")
        ax.legend(loc="upper left")
        
        if not ref_ax is None:
            ax.sharey(ref_ax)
            ax.sharex(ref_ax)
        else:
            ref_ax = ax
    fig.close()

.. image:: /_static/multi.gif
    
Grid Spec
^^^^^^^^^

Another method to place plots is by explicitly positioning them using
a :class:`matplotlib.gridspec.GridSpec`. In line with the paradigm
of delayed creation, use :meth:`cdxcore.dynaplot.DynaFig.add_gridspec`
to generate a deferred grid spec. 

Example::

    %matplotlib inline
    from cdxcore.dynaplot import figure
    import numpy as np
    x = np.linspace(-2.,+2,101)
    y = np.tanh(x)
    fig = figure("Grid Spec Example", figsize=(10,5))
    gs  = fig.add_gridspec(2,2)
    
    ax = fig.add_subplot("1", spec_pos=gs[0,0] )
    ax.plot(x,y)
    ax = fig.add_subplot("2", spec_pos=gs[:,1] )
    ax.plot(x,y)
    ax = fig.add_subplot("3", spec_pos=gs[1,0] )
    ax.plot(x,y)
    fig.close()

.. image:: /_static/gridspec.gif

Color Management
^^^^^^^^^^^^^^^^

Use :func:`cdxcore.dynaplot.color_css4`, :func:`cdxcore.dynaplot.color_base`, :func:`cdxcore.dynaplot.color_tableau`, :func:`cdxcore.dynaplot.color_xkcd` 
to return an *i* th element of the respective `matplotlib color
table <https://matplotlib.org/stable/gallery/color/named_colors.html>`__.
This simplifies using consistent colors accross different plots or when re-creating plots during an animation.
    
Example of using the same colors by order in two plots::

    %matplotlib inline
    import numpy as np
    import math
    import time
    from cdxcore.dynaplot import figure, color_base   # 'figure' is an alias for DynaFig
    
    x = np.linspace(0.,2.*math.pi,51)
    
    fig = figure(fig_size=(14,6))
    ax = fig.add_subplot("Sin")
    store = fig.store()
    # draw 10 lines in the first sub plot, and add a legend
    for i in range(10):
        y = np.sin(x/(i+1))
        ax.plot( x, y, color=color_base(i), label=f"f(x/{i+1})" )
    ax.legend(loc="lower right")
    
    # draw 10 lines in the second sub plot.
    # use the same colors for the same scaling of 'x'
    ax = fig.add_subplot("Cos")
    
    for i in range(10):
        z = np.cos(x/(i+1))
        store += ax.plot( x, z, color=color_base(i) )
    fig.render()
    
    # animiate, again with the same colors
    for p in np.linspace(0.,4.,11,endpoint=False):
        time.sleep(0.1)
        store.clear() # alias for 'remove'
        for i in range(10):
            z = np.cos((x+p)/(i+1))
            store += ax.plot( x, z, color=color_base(i) )
        fig.render()
    
    fig.close()
    
.. image:: /_static/colors.gif

Here is a view of the first 20 colors of the four supported maps:
    
.. image:: /_static/colormap.gif

The classes :class:`cdxcore.dynaplot.colors_css4`, :class:`cdxcore.dynaplot.colors_base`, :class:`cdxcore.dynaplot.colors_tableau`, :class:`cdxcore.dynaplot.colors_xkcd` 
are generators for the same colors.

Known Issues
^^^^^^^^^^^^

Some users reported that the package does not work in some versions of Jupyter, in particular with VSCode.
In this case, please try changing the ``draw_mode`` parameter when calling :func:`cdxcore.dynaplot.figure`.

Import
------
.. code-block:: python

    fronm cdxcore.dynaplot import figure
    
Documentation
-------------
"""
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec, SubplotSpec#NOQA
import matplotlib.colors as mcolors
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from IPython import display
import io as io
import gc as gc
import types as types
from collections.abc import Collection
from .deferred import Deferred
from .util import verify, warn
from .dynalimits import AutoLimits
from .pretty import PrettyObject as pdct

class MODE:
    """
    How to draw 
    graphs. The best mode depends on the output IPython implementation.
    """ 
    HDISPLAY = 0x01
    """ Call :func:`IPython.display.display`. """
    
    CANVAS_IDLE = 0x02
    """ Call :meth:`matplotlib.pyplot.figure.canvas.draw_idle`. """
    
    CANVAS_DRAW = 0x04
    """ Call :meth:`matplotlib.pyplot.figure.canvas.draw`. """

    PLT_SHOW = 0x80
    """ Call :func:`matplotlib.pyplot.show`. """
       
    JUPYTER = HDISPLAY
    """ Setting which works for Jupyter lab as far as we can tell. """
    
    VSCODE = HDISPLAY|PLT_SHOW
    """ Setting which works for VSCode it seems. Feedback welome. """
         
class _DynaDeferred( Deferred ):
    """ Internal class which implements the required deferral method """
    __setitem__ = Deferred._deferred_handle("__setitem__", num_args=2, fmt="{parent}[{arg0}]={arg1}")
    __getitem__ = Deferred._deferred_handle("__getitem__", num_args=1, fmt="{parent}[{arg0}]")
    
    def deferred_create_action( self, **kwargsa ):
        """
        Creates a deferred action created during another deferred action.
        """
        return _DynaDeferred( **kwargsa )

class DynaAx(_DynaDeferred):
    """
    Deferred wrapper around a :class:`matplotlib.pyplot.axis` objects returned by :meth:`cdxcore.dynaplot.DynaFig.add_subplot` or similar.
    
    *You should not need to know that this object is not actually a* :class:`matplotlib.pyplot.axis`.
    *If you receive error messages which you do not understand, please contact the authors of this 
    module.*
    """

    def __init__(self, *, 
                       fig_id    : str, 
                       fig_list  : list,
                       row       : int, 
                       col       : int, 
                       spec_pos  : SubplotSpec,
                       rect      : tuple,
                       title     : str, 
                       projection: str,
                       kwargs    : dict):
        """ Creates internal object which defers the creation of various graphics to a later point """
        if row is None:
            assert col is None, "Consistency error 1"
            
            if not spec_pos is None:
                assert rect is None, "Consistency error 2"
            else:
                assert not rect is None, "Consistency error 3"
        else:
            assert not col is None and spec_pos is None and rect is None, "Consistency error 4"
            
        self.fig_id      = fig_id
        self.fig_list    = fig_list
        self.row         = row
        self.col         = col
        self.spec_pos    = spec_pos
        self.axes_rect   = rect
        self.title       = title
        self.plots       = {}
        self.kwargs      = dict(kwargs)
        self.ax          = None
        self.projection  = projection
        self.__auto_lims = None
        assert not self in fig_list
        
        if not row is None:
            label = f"subplot#{len(fig_list)}({row},{col})"
        elif not rect is None:
            label = f"subplot#{len(fig_list)}({rect[0]},{rect[1]},{rect[2]},{rect[3]})"
        else:
            label = "subplot#{len(fig_list)}()"
            
        _DynaDeferred.__init__(self,label)   # no more item assignments without tracking
        fig_list.append( self )
        
    def __str__(self):
        return self.deferred_info[1:]
    
    def _initialize( self, plt_fig, rows : int, cols : int):
        """
        Creates the underlying (deferred) :class:`matplotlib.pyplot.axis` by calling all "caught" functions in sequece for the figure ``plt_fig``.
        'rows' and 'cols' count the columns and rows specified by add_subplot() and are ignored by add_axes()
        """
        assert self.ax is None, "Internal error; function called twice?"
        
        def handle_kw_share( kw ):
            """ handle sharex and sharey """
            v = self.kwargs.pop(kw, None)
            if v is None:
                return
            if isinstance( v, Axes ):
                self.kwargs[kw] = v
            assert isinstance( v, DynaAx ), ("Cannot",kw,"with type:", type(v))
            assert not v.ax is None, ("Cannot", kw, "with provided axis: it has bnot been creatred yet. That usually means that you mnixed up the order of the plots")
            self.kwargs[kw] = v.ax
            
        handle_kw_share("sharex")
        handle_kw_share("sharey")
        
        if not self.row is None:
            # add_axes
            num     = 1 + self.col + self.row*cols
            self.ax = plt_fig.add_subplot( rows, cols, num, projection=self.projection, **self.kwargs )
        elif not self.spec_pos is None:
            # add_subplot with grid spec
            self.ax = plt_fig.add_subplot( self.spec_pos.deferred_result, projection=self.projection, **self.kwargs )            
        else:
            # add_axes
            self.ax = plt_fig.add_axes( self.axes_rect, projection=self.projection, **self.kwargs )        

        if not self.title is None:
            self.ax.set_title(self.title)

        # handle common functions which expect an 'axis' as argument
        # and auto-translate any DynaAx's 
        # Just sharex() and sharey() for the moment.
        ref_ax    = self.ax
        ax_sharex = ref_ax.sharex
        def sharex(self, other):
            if isinstance(other, DynaAx):
                verify( not other.ax is None, "Cannot sharex() with provided axis: 'other' has not been created yet. That usually means that you have mixed up the order of the plots")
                other = other.ax
            return ax_sharex(other)
        ref_ax.sharex = types.MethodType(sharex,ref_ax)

        ax_sharey = ref_ax.sharey
        def sharey(self, other):
            if isinstance(other, DynaAx):
                verify( not other.ax is None, "Cannot sharey() with provided axis: 'other' has not been created yet. That usually means that you have mixed up the order of the plots")
                other = other.ax
            return ax_sharey(other)
        ref_ax.sharey = types.MethodType(sharey,ref_ax)

        # call all deferred operations
        self.deferred_resolve( self.ax )
        
    def remove(self):
        """
        Equivalent of :meth:`matplotlib.axes.Axes.remove`: removes this axis from
        the underlying figure. Note that this will not trigger
        a removal from the actual visualization until :meth:`cdxcore.dynaplot.DynaFig.render` 
        is called.
        """
        assert self in self.fig_list, ("Internal error: axes not contained in figure list")
        self.fig_list.remove(self)
        self.ax.remove()
        self.ax = None
        gc.collect()
        
    # automatic limit handling
    # -------------------------
    
    def plot(self, *args, scalex=True, scaley=True, data=None, **kwargs ):
        """
        Wrapper around :func:`matplotlib.axes.plot`.

        This function wrapper does not support the ``data`` interface
        of :func:`matplotlib.axes.plot`.

        If automatic limits are not used, this is a wrapper with deferred pass-through.
        If automatic limits are used, then this function will update 
        the underlying automated limits accordingly.
        
        Parameters
        ----------
            args, scalex, scaley, data, kwargs : ...
                See :func:`matplotlib.axes.plot`.
            
        Returns
        -------
            plot : ``Deferred`` 
                This function will return a wrapper around an actual ``axis``
                which is used to defer actioning any subsequent
                calls to until :meth:`cdxcore.dynaplot.DynaFig.render` 
                is called.
                
                *You should not need to consider this. If you encounter
                problems in usability please contact the authors.*        
        """
        plot = _DynaDeferred.__getattr__(self,"plot") 
        if self.__auto_lims is None:
            return plot( *args, scalex=scalex, scaley=scaley, data=data, **kwargs )
        
        assert data is None, ("Cannot use 'data' for automatic limits yet")
        assert len(args) > 0, "Must have at least one position argument (the data)"

        def add(x,y,fmt):
            assert not y is None
            if x is None:
                self.limits.update(y, scalex=scalex, scaley=scaley)
            else:
                self.limits.update(x,y, scalex=scalex, scaley=scaley)

        type_str = [ type(_).__name__ for _ in args ]
        my_args  = list(args)
        while len(my_args) > 0:
            assert not isinstance(my_args[0], str), ("Fmt string at the wrong position", my_args[0], "Argument types", type_str)
            if len(my_args) == 1:
                add( x=None, y=my_args[0], fmt=None )
                my_args = my_args[1:]
            elif isinstance(my_args[1], str):
                add( x=None, y=my_args[0], fmt=my_args[1] )
                my_args = my_args[2:]
            elif len(my_args) == 2:
                add( x=my_args[0], y=my_args[1], fmt=None )
                my_args = my_args[2:]
            elif isinstance(my_args[2], str):
                add( x=my_args[0], y=my_args[1], fmt=my_args[2] )
                my_args = my_args[3:]
            else:
                add( x=my_args[0], y=my_args[1], fmt=None )
                my_args = my_args[2:]
        return plot( *args, scalex=scalex, scaley=scaley, data=data, **kwargs )
    
    def auto_limits( self, low_quantile, high_quantile, min_length : int = 10, lookback : int = None ):
        """
        Add automatic limits using :class:`cdxcore.dynalimits.AutoLimits`.

        Parameters
        ----------
            low_quantile : float
                Lower quantile to use for computing a 'min' y value. Set to 0 to use the actual 'min'.
            high_quantile : float
                Higher quantile to use for computing a 'min' y value. Set to 1 to use the actual 'max'.
            min_length : int, optional
                Minimum length data must have to use :func:`numpy.quantile`.
                If less data is presented, use min/max, respectively.
                Default is ``10``.
            lookback : int
                How many steps to lookback for any calculation. ``None`` to use all steps.
                
        """
        assert self.__auto_lims is None, ("Automatic limits already set")
        self.__auto_lims = AutoLimits( low_quantile=low_quantile, high_quantile=high_quantile, min_length=min_length, lookback=lookback )
        return self

    def set_auto_lims(self, *args, **kwargs):
        """
        Apply :class:`cdxcore.dynalimits.AutoLimits` for this axis.
        See :class:`cdxcore.dynalimits.AutoLimits.set_lims` for parameter description.
        """
        assert not self.__auto_lims is None, ("Automatic limits not set. Use auto_limits()")
        self.__auto_lims.set_lims( *args, ax=self, **kwargs)
    
class _DynaGridSpec(_DynaDeferred):
    """ _DynaDeferred GridSpec """
     
    def __init__(self, nrows : int, ncols : int, cnt : int, kwargs : dict):
        self.grid   = None
        self.nrows  = nrows
        self.ncols  = ncols
        self.kwargs = dict(kwargs)
        _DynaDeferred.__init__(self,f"gridspec#{cnt}({nrows},{ncols})")

    def __str__(self):
        return self.deferred_info[1:]
        
    def _initialize( self, plt_fig ):
        """ Lazy initialization """
        assert self.grid is None, ("_initialized twice?")
        if len(self.kwargs) == 0:
            self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols )
        else:
            # wired error in my distribution
            try:
                self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols, **self.kwargs )
            except TypeError as e:
                estr = str(e)
                if estr != "GridSpec.__init__() got an unexpected keyword argument 'kwargs'":
                    raise e
                warn("Error calling matplotlib GridSpec() with **kwargs: %s; will attempt to ignore any kwargs.", estr)
                self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols )
        self.deferred_resolve( self.grid )

class DynaFig(_DynaDeferred):
    """
    Deferred wrapper around :class:`matplotlib.pyplot.figure`.
    
    Wraps matplotlib :class:`matplotlib.pyplot.figure`. Provides a simple :meth:`cdxcore.dynaplot.DynaFig.add_subplot` without the need to pre-specify axes positions
    as is common for :mod:`matplotlib`.
    
    See :func:`cdxcore.dynaplot.figure` for more information.
    """

    def __init__(self, title    : str = None, *,
                       row_size : int = 5,
                       col_size : int = 4,
                       fig_size : tuple[int] = None,
                       columns  : int = 5,
                       tight    : bool = True,
                       draw_mode: int = MODE.JUPYTER,
                       **fig_kwargs ):
        """

        """
        self.hdisplay   = None
        self.axes       = []   #: List of axes. Until; :meth:`cdxcore.dynaplot.DynaFig.render` is called, these are :class:`cdxcore.dynaplot.DynaAx` objects;
                               #: afterwards, these are :class:`matplotlib.pyplot.axis` objects.
        self.grid_specs = []
        self.fig        = None
        self.row_size   = int(row_size)
        self.col_size   = int(col_size)
        self.cols       = int(columns)
        self.tight      = bool(tight)
        self.tight_para = None
        self.fig_kwargs = dict(fig_kwargs)
        if self.tight:
            self.fig_kwargs['tight_layout'] = True
        verify( self.row_size > 0 and self.col_size > 0 and self.cols > 0, "Invalid input.", exception=ValueError)
        self.this_row  = 0
        self.this_col  = 0
        self.max_col   = 0
        self.fig_title = title
        self.closed    = False
        self.draw_mode = draw_mode

        verify( not 'cols' in fig_kwargs, "Unknown keyword 'cols'. Did you mean 'columns'?", exception=ValueError)
        
        if not fig_size is None:
            verify( not 'figsize' in fig_kwargs, "Cannot specify both `figsize` and `fig_size`", exception=ValueError)
            fig_kwargs['figsize'] = fig_size
        
        _DynaDeferred.__init__(self, f"figure('{str(title)[:20]}')" if not title is None else"figure()" )

    def __str__(self):
        return self.deferred_info[1:]

    def __del__(self): # NOQA
        """ Ensure the figure is closed """
        self.close()

    def add_subplot(self, title     : str = None, *,
                          new_row   : bool = None,
                          spec_pos  : type = None,
                          projection: str = None,
                          **kwargs) -> DynaAx:
        """
        Adds a subplot.

        Compared to :meth:`matplotlib.figure.Figure.add_subplot` this function does not require the tedious positioning arguments which are
        required when using :meth:`matplotlib.figure.Figure.add_subplot`.
        This function also allows to directly specify a plot title.

        *Implementation Comment:*
        
        This function returns a wrapper which defers the creation of the actual sub plot until
        :meth:`cdxcore.dynaplot.DynaFig.render` or :meth:`cdxcore.dynaplot.DynaFig.close` is called.
        Thus this function cannot be called after :meth:`cdxcore.dynaplot.DynaFig.render` was called as then the geometry of the plots
        is set. Use :meth:`cdxcore.dynaplot.DynaFig.add_axes` to draw plots in any position.
        
        Parameters
        ----------
            title : str, optional
                Optional title for the plot.

            new_row : bool, optional
                Whether to force a new row and place this polt in the first column. Default is ``False``.

            spec_pos : optional
                Grid spec position, or ``None``.

            projection : str, optional
                What ``projection`` to use. The default ``None`` matches the default choice for
                :meth:`matplotlib.figure.Figure.add_subplot`.

            kwargs : dict
                other arguments to be passed to matplotlib's :meth:`matplotlib.figure.Figure.add_subplot`.
        """
        verify( not self.closed, "Cannot call add_subplot() after close() was called")
        verify( self.fig is None, "Cannot call add_subplot() after render() was called. Use add_axes() instead")

        # backward compatibility:
        # previous versions has "new_row" first.
        assert title is None or isinstance(title, str), ("'title' must be a string or None, not", type(title))
        title   = str(title) if not title is None else None
            
        if not spec_pos is None:
            assert new_row is None, ("Cannot specify 'new_row' when 'spec_pos' is specified")
            ax = DynaAx( fig_id=hash(self),
                         fig_list=self.axes,
                         row=None, 
                         col=None,
                         title=title,
                         spec_pos=spec_pos, 
                         rect=None,
                         projection=projection, 
                         kwargs=dict(kwargs) )
            
        else:
            new_row = bool(new_row) if not new_row is None else False
            if (self.this_col >= self.cols) or ( new_row and not self.this_col == 0 ):
                self.this_col = 0
                self.this_row = self.this_row + 1
            if self.max_col < self.this_col:
                self.max_col = self.this_col
            ax = DynaAx( fig_id=hash(self),
                         fig_list=self.axes,
                         row=self.this_row,
                         col=self.this_col,
                         spec_pos=None,
                         rect=None,
                         title=title,
                         projection=projection,
                         kwargs=dict(kwargs) )
            self.this_col += 1
        assert ax in self.axes
        return ax

    add_plot = add_subplot
    
    def add_axes( self, 
                  rect      : tuple, 
                  title     : str|None = None, *,
                  projection: str = None,
                  **kwargs ) -> DynaAx:
        """
        Add a freely placed sub plot.
        
        Like :meth:`matplotlib.figure.Figure.add_axes` this function allows placing a plot
        at a given position within a figure using ``rect``. This plot may 
        overlay previously generated plots.
        
        This function can be called after the :meth:`cdxcore.dynaplot.DynaFig.close` was called.
        
        Note that using this function with a ``tight`` figure will result in a :class:`UserWarning`.
        Use ``tight=False`` when constructing your figure to avoid this warning.
        
        Parameters
        ----------
            rect : tuple (left, bottom, width, height)
                The dimensions (left, bottom, width, height) of the new plot.
                All quantities are in fractions of figure width and height.
            
            title : str, optional
                Title for the plot, or ``None`` for no plot.
                
            projection : str, optional
                What ``projection`` to use. The default ``None`` matches the default choice for
                :meth:`matplotlib.figure.Figure.add_axes`

            args, kwargs :
                keyword arguments to be passed to :meth:`matplotlib.figure.Figure.add_axes`.
        """
        verify( not self.closed, "Cannot call add_subplot() after close() was called")

        title   = str(title) if not title is None else None
        
        ax = DynaAx( fig_id=hash(self),
                     fig_list=self.axes, 
                     row=None, 
                     col=None, 
                     title=title, 
                     spec_pos=None, 
                     rect=rect,
                     projection=projection, 
                     kwargs=dict(kwargs) )
        assert ax in self.axes
        if not self.fig is None:
            ax._initialize( self.fig, rows=None, cols=None )        
        return ax
    
    def add_gridspec(self, ncols=1, nrows=1, **kwargs):
        """
        Wrapper for :meth:`matplotlib.figure.Figure.add_gridspec`, returning a defered ``GridSpec``.
        """
        grid = _DynaGridSpec( ncols=ncols, nrows=nrows, cnt=len(self.grid_specs), kwargs=kwargs )
        self.grid_specs.append( grid )
        return grid

    def next_row(self):
        """
        Skip to next row. 
    
        The next plot generated by :meth:`cdxcore.dynaplot.DynaFig.add_subplot` will 
        appears in the first column of the next row.
        """
        verify( self.fig is None, "Cannot call next_row() after render() was called")
        if self.this_col == 0:
            return
        self.this_col = 0
        self.this_row = self.this_row + 1

    def render(self, draw : bool = True ):
        """
        Draw all axes.
        
        If this function does not display the plots you generated, review the
        ``draw_mode`` parameter provided to :func:`cdxcore.dynaplot.figure` or :func:`cdxcore.dynaplot.DynaFig`, respectively, 

        Once called, no further plots can be added, but the plots can be updated in place.
        
        Parameters
        ----------
            draw : bool
                If False, then the figure is created, but not drawn.
                You usually use ``False`` when planning to use
                :func:`cdxcore.dynaplot.DynaFig.savefig` or :func:`cdxcore.dynaplot..DynaFig.to_bytes`.
        """
        verify( not self.closed, "Cannot call render() after close() was called")
        if len(self.axes) == 0:
            return
        if self.fig is None:
            # create figure
            if not 'figsize' in self.fig_kwargs:
                self.fig_kwargs['figsize'] = ( self.col_size*(self.max_col+1), self.row_size*(self.this_row+1))
            self.fig  = plt.figure( **self.fig_kwargs )
            if self.tight:
                self.fig.tight_layout()
                self.fig.set_tight_layout(True)
            if not self.fig_title is None:
                self.fig.suptitle( self.fig_title )
            # create all grid specs
            for gs in self.grid_specs:
                gs._initialize( self.fig )
            # create all axes
            for ax in self.axes:
                ax._initialize( self.fig, rows=self.this_row+1, cols=self.max_col+1 )
            # execute all deferred calls to fig()
            self.deferred_resolve( self.fig )
            
        if not draw:
            return
        if self.draw_mode & MODE.HDISPLAY:
            if self.hdisplay is None:
                self.hdisplay = display.display(display_id=True)
                verify( not self.hdisplay is None, "Could not optain current IPython display ID from IPython.display.display(). Set DynaFig.MODE = 'canvas' for an alternative mode")
            self.hdisplay.update(self.fig)
        if self.draw_mode & MODE.CANVAS_IDLE:
            self.fig.canvas.draw_idle()
        if self.draw_mode & MODE.CANVAS_DRAW:
            self.fig.canvas.draw()
        if self.draw_mode & MODE.PLT_SHOW:
            plt.show()
        gc.collect() # for some unknown reason this is required in VSCode

    def savefig(self, fname : str,
                      silent_close : bool = True, 
                      **kwargs ):
        """
        Saves the figure to a file.
        
        Wrapper around :func:`matplotlib.pyplot.savefig`. Essentially, this function writes the figure to a file]
        rather than displaying itl.

        Parameters
        ----------
            fname : str
                `filename or file-like object <https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html>`__

            silent_close : bool
                If ``True`` (the default), call :meth:`cdxcore.dynaplot.DynaFig,close` once the figure was saved to disk.
                Unless the figure was drawn before, this means that the figure will not be displayed in jupyter, and
                subsequent activity is blocked.
                
            kwargs : dict
                These arguments will be passed to :meth:`matplotlib.pyplot.savefig`.
        """
        verify( not self.closed, "Cannot call savefig() after close() was called")
        if self.fig is None:
            self.render(draw=False)
        self.fig.savefig( fname, **kwargs )
        if silent_close:
            self.close(render=False)

    def to_bytes(self, silent_close : bool = True ) -> bytes:
        """
        Convert figure to a byte stream.
        
        This stream can be used to generate a IPython image using::

            from IPython.display import Image, display
            bytes = fig.to_bytes()
            image = Image(data=byes)
            display(image)

        Parameters
        ----------
            silent_close : bool, optional
                If ``True``, call :meth:`cdxcore.dynaplot.DynaFig,close` after this genersating the byte streanm.
                Unless the figure was drawn before, this means that the figure will not be displayed in jupyter, and
                subsequent activity is blocked.

        Returns
        -------
            image : bytes
                Buyte stream of the image.
        """
        verify( not self.closed, "Cannot call savefig() after close() was called")
        img_buf = io.BytesIO()
        if self.fig is None:
            self.render(draw=False)
        self.fig.savefig( img_buf )
        if silent_close:
            self.close(render=False)
        data = img_buf.getvalue()
        img_buf.close()
        return data
    
    @staticmethod
    def store():
        """ Create a FigStore(). Such a store allows managing graphical elements (artists) dynamically. """
        return FigStore()

    def close(self, render          : bool = True, 
                    clear           : bool = False ):
        """
        Closes the figure. 
        
        Call this to avoid a duplicate in jupyter output cells.
        By dault this function will call :meth:`cdxcore.dynaplot.DynaFig,render` to draw the figure, and then close it.

        Parameters
        ----------
            render : bool, optional
                If  `True``, the default, this function will call :meth:`cdxcore.dynaplot.DynaFig,render` and therefore renders the figure before closing the figure.
            clear  :
                If ``True``, all axes will be cleared. *This is experimental.* The default is ``False``.
        """
        if not self.closed:
            # magic wand to avoid printing an empty figure message
            if clear:
                if not self.fig is None:
                    def repr_magic(self):
                        return type(self)._repr_html_(self) if len(self.axes) > 0 else "</HTML>"
                    self.fig._repr_html_ = types.MethodType(repr_magic,self.fig)
                    self.delaxes( self.axes, render=render )
            elif render:
                self.render(draw=True)
            if not self.fig is None:
                plt.close(self.fig)
        self.fig      = None
        self.closed   = True
        self.hdisplay = None
        gc.collect()
        
    def get_axes(self) -> list:
        """ Equivalent to ``self.axes`` """
        verify( not self.closed, "Cannot call render() after close() was called")
        return self.axes
    
    def remove_all_axes(self, *, render : bool = False):
        """ Calles :meth:`cdxcore.dynalot.DynaAx.remove` for all axes """
        while len(self.axes) > 0:
            self.axes[0].remove()
        if render:
            self.render(draw=True)
        
    def delaxes( self, ax : DynaAx, *, render : bool = False ):
        """
        Equivalent of :func:`matplotlib.figure.Figure.delaxes`, but this function can also take a list.
        """
        verify( not self.closed, "Cannot call render() after close() was called")
        if isinstance( ax, Collection ):
            ax = list(ax)
            for x in ax:
                x.remove()
        else:
            assert ax in self.axes, ("Cannot delete axes which wasn't created by this figure")
            ax.remove()
        if render:
            self.render()

def figure( title    : str = None, *,
            row_size : int = 5,
            col_size : int = 4,
            fig_size : tuple[int] = None,
            columns  : int = 5,
            tight    : bool = True,
            draw_mode: int = MODE.JUPYTER,
            **fig_kwargs ):
    """
    Creates a dynamic figure of type :class:`cdxcore.dynaplot.DynaFig`.
    
    By default the ``fig_size`` of the underlying :class:`matplotlib.pyplot.figure`
    will be derived from the number of plots vs ``cols``, ``row_size`` and ``col_size``
    as ``(col_size* (N%col_num),  row_size (N//col_num))``.
    
    If ``fig_size`` is specified then ``row_size`` and ``col_size`` are ignored.
    
    Once the figure is constructed,
    
    1) Use :meth:`cdxcore.dynaplot.DynaFig.add_subplot` to add plots (without the cumbersome need       to know the number of plots in advance);
    
    2) Call :meth:`cdxcore.dynaplot.DynaFig.render` to place those plots.
    
    3) Call :meth:`cdxcore.dynaplot.DynaFig.close` to close the figure and avoid duplicate copies in Jupyter.
    
    **Examples:**

    Simply use :meth:`cdxcore.dynaplot.DynaFig.add_subplot` without the
    matplotlib need to pre-specify axes positions::
        
        from cdxcore.dynaplot import figure    
        fig = dynaplot.figure("Two plots")
        ax = fig.add_subplot("1")
        ax.plot(x,y)
        ax = fig.add_subplot("2")
        ax.plot(x,y)
        fig.render()
        
    Here is an example using :meth:`matplotlib.figure.Figure.add_gridspec`::
        
        from cdxcore.dynaplot import figure    
        fig = dynaplot.figure()
        gs  = fig.add_gridspec(2,2)
        ax = fig.add_subplot( gs[:,0] )
        ax.plot(x,y)
        ax = fig.add_subplot( gs[:,1] )
        ax.plot(x,y)
        fig.render()
        
    **Important Functions:**    
    
    The returned :class:`cdxcore.dynaplot.DynaFig` will 
    defer all other function calls to the figure
    object until :meth:`cdxcore.dynaplot.DynaFig.render`
    or :meth:`cdxcore.dynaplot.DynaFig.close` are called.
    
    The following direct members are important for using the framework:
    
    * :meth:`cdxcore.dynaplot.DynaFig.add_subplot`:
      create a sub plot. No need to provide the customary
      rows, cols, and total number as this will computed for you.
    
    * :meth:`cdxcore.dynaplot.DynaFig.render`:
      draws the figure as it is.
      Call this function if the underlying graphs are modified
      as in the various example discussed here.

    * :meth:`cdxcore.dynaplot.DynaFig.close`:
      close the figure.

      If you do not call this function 
      you will likely see duplicate copies of the figure in jupyter.

    Parameters
    ----------
        title : str, optional
            An optional title which will be passed to :meth:`matplotlib.pyplot.suptitle`.
            
        fig_size : tuple[int], optional
            By default the ``fig_size`` of the underlying :class:`matplotlib.pyplot.figure`
            will be derived from the number of plots vs ``cols``, ``row_size`` and ``col_size``
            as ``(col_size* (N%col_num),  row_size (N//col_num))``.
            
            If ``fig_size`` is specified then ``row_size`` and ``col_size`` are ignored.

        row_size : int, optional
            Size for a row for matplot lib. Default is 5.
            This is ignored if ``fig_size`` is specified.
            
        col_size : int, optional
            Size for a column for matplot lib. Default is 4.
            This is ignored if ``fig_size`` is specified.

        columns : int, optional
            How many columns to use when :meth:`cdxcore.dynaplot.DynaFig.add_subplot` is used.
            If omitted then the default is 5.

        tight : bool, optional
            Short cut for :meth:`matplotlib.figure.Figure.set_tight_layout`. The default is ``True``.
            
            Note that when ``tight`` is ``True`` and :meth:`cdxcore.dynaplot.DynaFig.add_axes` 
            is called a :class:`UserWarning` is generated. Turn ``tight`` off to avoid this.

        draw_mode : int, optional
            A combination of :class:`cdxcore.dynaplot.MODE` flags on how to draw plots
            once they were rendered. The required function call differs by IPython platform.
            The default, :attr:`cdxcore.dynaplot.MODE.JUPYTER` draws well on Jupyter notebooks.
            For VSCode, you might need :attr:`cdxcore.dynaplot.MODE.VSCODE`.
            
        fig_kwargs :
            Other matplotlib parameters for :func:`matplotlib.pyplot.figure` to
            create the figure. 

     
    Returns
    -------
        figure: :class:`cdxcore.dynaplot.DynaFig`
            A dynamic figure. 
    """
    return DynaFig( title=title,
                    row_size=row_size,
                    col_size=col_size,
                    fig_size=fig_size,
                    columns=columns,
                    tight=tight,
                    draw_mode=draw_mode,
                    **fig_kwargs
                    )

# ----------------------------------------------------------------------------------
# Utility class for animated content
# ----------------------------------------------------------------------------------

class FigStore( object ):
    """
    Utility class to manage dynamic content by removing old graphical elements (instead of using element-specifc update).

    Allows implementing a fairly cheap dynamic pattern::
        
        from cdxbasics.dynaplot import figure
        import time as time
        
        fig = figure()
        ax = fig.add_subplot()
        store = fig.store()
        
        x = np.linspace(-2.,+2,21)
        
        for i in range(10):
            store.remove()
            store += ax.plot( x, np.sin(x+float(i)) )
            fig.render()
            time.sleep(1)
            
        fig.close()
        
    As in the example above, the most convenient way to create a ``FigStore`` object is 
    to call `:meth:`cdxcore.dynaplot.DynaFig.store` on your figure.
    """

    def __init__(self):
        """ Create FigStore() objecy """
        self._elements = []

    def add(self, element : Artist):
        """
        Add an element to the store.
        The same operation is available using +=
        
        Parameters
        ----------
            element : :class:`matplotlib.artist.Artist`
                Graphical matplot element derived from :class:`matplotlib.artist.Artist` such as :class:`matplotlib.lines.Line2D`; 
                or a ``Collection`` of the above; or ``None``.
                
        Returns
        -------
            ``self`` : ``Figstore``
                This way compound statements ``a.add(x).add(y).add(z)`` work.
        """
        if element is None:
            return self
        if isinstance(element, Artist):
            self._elements.append( element )
            return self
        if isinstance(element, _DynaDeferred):
            self._elements.append( element )
            return self
        if not isinstance(element,Collection):
            raise ValueError("Cannot add element of type '{type(element).__name__}' as it is not derived from matplotlib.artist.Artist, nor is it a Collection")
        for l in element:
            self += l
        return self

    def __iadd__(self, element : Artist):
        """ += operator replacement for 'add' """
        return self.add(element)

    def remove(self):
        """
        Removes all elements by calling their :meth:`matplotlib.artist.Artist.remove` function.
        Handles any ``Collection`` of such elements is as well.
        """
        def rem(e):
            if isinstance(e, Artist):
                e.remove()
                return
            if isinstance(e,Collection):
                for l in e:
                    rem(l)
                return
            if isinstance(e, _DynaDeferred):
                if not e.deferred_was_resolved:
                    raise RuntimeError("Error: remove() was called before the figure was rendered. Call figure.render() before removing elements.")
                rem( e.deferred_result )
                return
            if not e is None:
                raise RuntimeError("Cannot remove() element of type '{type(e).__name__}' as it is not derived from matplotlib.artist.Artist, nor is it a Collection")
    
        while len(self._elements) > 0:
            rem( self._elements.pop(0) )
        self._elements = []
        gc.collect()
        
    clear = remove
    
def store():
    """ Creates a :class:`cdxcore.dynaplot.FigStore` which can be used to dynamically update a figure. """
    return FigStore()

# ----------------------------------------------------------------------------------
# color management
# ----------------------------------------------------------------------------------

def color_css4(i : int):
    """ Returns the *i*'th css4 color:
    
    .. figure:: https://matplotlib.org/stable/_images/sphx_glr_named_colors_003_2_00x.png
    """
    names = list(mcolors.CSS4_COLORS)
    name  = names[i % len(names)]
    return mcolors.CSS4_COLORS[name]

def color_base(i : int):
    """ Returns the *i*'th base color:
    
    .. figure:: https://matplotlib.org/stable/_images/sphx_glr_named_colors_001_2_00x.png  
    """
    names = list(mcolors.BASE_COLORS)
    name  = names[i % len(names)]
    return mcolors.BASE_COLORS[name]

def color_tableau(i : int):
    """ Returns the *i*'th tableau color:
    
    .. figure:: https://matplotlib.org/stable/_images/sphx_glr_named_colors_002_2_00x.png
    """
    names = list(mcolors.TABLEAU_COLORS)
    name  = names[i % len(names)]
    return mcolors.TABLEAU_COLORS[name]

def color_xkcd(i : int):
    """ Returns the *i* th `xkcd color <https://xkcd.com/color/rgb/>`__. """
    names = list(mcolors.XKCD_COLORS)
    name  = names[i % len(names)]
    return mcolors.XKCD_COLORS[name]

_color_map = pdct(dict(css4=color_css4,
                  base=color_base,
                  tableau=color_tableau,
                  xkcd=color_xkcd
                  ))
""" Maps names of colors to their color function. """

color_names = list(_color_map)
""" List of available colors names. """

def color(i : int, table : str ="css4"):
    """
    Returns a color with a given index to allow consistent colouring.

    Parameters
    ----------
    i : int
        Integer number. Colors will be rotated.

    table : str, optional
        Which color table from :func:`matplotlib.colors` to use: `"css4"`, `"base"`, `"tableau"` or `"xkcd"`.
        Default is ``"css4"``.

    Returns
    -------
        Color code : str
            
    """
    verify( table in _color_map, "Invalid color code '%s'. Must be 'css4' (the default), 'base', 'tableau', or 'xkcd'", table, exception=ValueError )
    return _color_map[table](i)

def colors(table : str = "css4"):
    """
    Returns a generator for the colors of the specified table.        

    Parameters
    ----------
    table : str, optional 
        Which color table from `matplotlib.colors <https://matplotlib.org/stable/gallery/color/named_colors.html>`__
        to use: ``"css4"``, ``"base"``, ``"tableau"``,  or ``"xkcd"``.
        Default is ``"css4"``.

    Returns
    -------
        Generator for colors.
            Use ``next()`` or iterate.
    """
    num = 0
    while True:
        yield color(num,table)
        num = num + 1

def colors_css4():
    """ Iterator for "css4" matplotlib colors:
    
    .. figure:: https://matplotlib.org/stable/_images/sphx_glr_named_colors_003_2_00x.png
    
    """
    return colors("css4")

def colors_base():
    """ Iterator for "base" matplotlib colors:

    .. figure:: https://matplotlib.org/stable/_images/sphx_glr_named_colors_001_2_00x.png          
    """
    return colors("base")

def colors_tableau():
    """ Iterator for ""tableau"" matplotlib colors:"

    .. figure:: https://matplotlib.org/stable/_images/sphx_glr_named_colors_002_2_00x.png
    """
    return colors("tableau")

def colors_xkcd():
    """ Iterator for `xkcd <https://xkcd.com/color/rgb/>`__. matplotlib colors """
    return colors("xkcd")

