"""

Tools for dynamic plotting in Jupyer/IPython.

The aim of the toolkit is making it easier to develop
animated visualization with :mod:`matplotlib`,
for example during training with machine learing kits such as
*pyTorch*.

It also makes the creation of subplots more streamlined.

This has been tested with Anaconda's
JupyterHub and ``%matplotlib inline``. 

Overview
--------

Animated Graphs, Simple
^^^^^^^^^^^^^^^^^^^^^^^

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
  
  If possible, use the ``with figure(...) as fig`` pattern which will ennsure that :meth:`cdxcore.dynaplot.DynaFig.close`
  is called.

Here is an example of animated line plots using :func:`cdxcore.dynaplot.DynaFig.store`::

    %matplotlib inline
    import numpy as np
    import time
    from cdxcore.dynaplot import figure, MODE
    
    x  = np.linspace(0,1,100)
    pm = 0.2
    
    with figure(col_size=10) as fig:
        ax  = fig.add_subplot()
        ax2 = fig.add_subplot()
        ax2.sharey(ax)
        store = fig.store()    
        fig.render()
        
        for i in range(10):
            y = np.random.random(size=(100,))
            ax.set_title(f"Test {i}")
            ax2.set_title(f"Test {i}")
        
            store.remove() # delete all prviously stored elements
            store += ax.plot(x,y,":", label=f"data {i}")
            store += ax2.plot(x,y,"-",color="red", label=f"data {i}")
            store += ax2.fill_between( x, y-pm, y+pm, color="blue", alpha=0.2 )
            store += ax.legend()
        
            fig.render()
            time.sleep(0.5)
            
.. image:: /_static/dynaplot.gif

In above example we used the ``with`` context of a :class:`cdxcore.dynaplot.DynaFig` figure.
The point of using ``with`` where convenient is that it will call :meth:`cdxcore.dynaplot.DynaFig.close`
which will avoid duplicate copies of the figure in jupyter.

To do close the figure manually, call :meth:`cdxcore.dynaplot.DynaFig.close` directy:
    
.. code-block:: python
   :emphasize-lines: 9, 30

    %matplotlib inline
    import numpy as np
    import time
    from cdxcore.dynaplot import figure, MODE
    
    x  = np.linspace(0,1,100)
    pm = 0.2
    
    fig = figure(col_size=10)
    ax  = fig.add_subplot()
    ax2 = fig.add_subplot()
    ax2.sharey(ax)
    store = fig.store()    
    fig.render()
    
    for i in range(10):
        y = np.random.random(size=(100,))
        ax.set_title(f"Test {i}")
        ax2.set_title(f"Test {i}")
    
        store.remove() # delete all prviously stored elements
        store += ax.plot(x,y,":", label=f"data {i}")
        store += ax2.plot(x,y,"-",color="red", label=f"data {i}")
        store += ax2.fill_between( x, y-pm, y+pm, color="blue", alpha=0.2 )
        store += ax.legend()
    
        fig.render()
        time.sleep(0.5)
        
    fig.close() 

Here is an example with 
animated 3D plots, calling :meth:`matplotlib.axes.Axes.remove` manually::
    
    %matplotlib inline
    import numpy as np
    from cdxcore.dynaplot import figure
    import math
        
    x = np.linspace(0.,2.*math.pi,51)
    y = x
    
    with figure() as fig:
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
    import time
    from cdxcore.dynaplot import figure
     
    x = np.linspace(0,1,100)
    
    with figure(title="Multi Graph", fig_size=(10,6), columns=4) as fig:
        lines  = []
        ref_ax = None
        for k in range(9):
            ax = fig.add_subplot()
            ax.set_title("Test %ld" % k)
            y = np.random.random(size=(100,1))
            l = ax.plot(x,y,":",color="red", label="data")
            lines.append(l)
            ax.legend()
            
            if not ref_ax is None:
                ax.sharey(ref_ax)
                ax.sharex(ref_ax)
            else:
                ref_ax = ax
        fig.render()
    
        for i in range(5):
            time.sleep(0.2)
            for l in lines:
                y = np.random.random(size=(100,1))
                l[0].set_ydata( y )
            fig.render()
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
    
    x = np.linspace(-2.,+2,21)
    
    with figure(tight=False) as fig:
        ax = fig.add_subplot()
        ax.plot( x, np.sin(x) )
        fig.render()
    
        ax = fig.add_axes( (0.5,0.5,0.3,0.3), "axes" )
        ax.plot( x, np.cos(x) )

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
    
    with figure(fig_size=(14,6)) as fig:
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
        
.. image:: /_static/colors.gif

Here is a view of the first 20 colors of the four supported maps, computed with::
    
    %matplotlib inline
    from cdxcore.dynaplot import figure, color_names, color
    import numpy as np
    x = np.linspace(-2.*np.pi,+2*np.pi,101)
    N = 20
    with figure(f"Color tables up to #{N}", figsize=(20,15), columns=2) as fig:
        for color_name in color_names:
            ax  = fig.add_subplot(color_name)
            for i in range(N):
                r =1./(i+1)
                ax.plot( x, np.sin(x*r), color
                        
.. image:: /_static/colormap.gif

The classes :class:`cdxcore.dynaplot.colors_css4`, :class:`cdxcore.dynaplot.colors_base`, :class:`cdxcore.dynaplot.colors_tableau`, :class:`cdxcore.dynaplot.colors_xkcd` 
are generators for the same colors.


Known Issues
^^^^^^^^^^^^

Some users reported that the package does not update figures consistently in some versions of Jupyter, in particular with VSCode.
In this case, please try changing the ``draw_mode`` parameter when calling :func:`cdxcore.dynaplot.figure`.

Import
------
.. code-block:: python

    from cdxcore.dynaplot import figure
    
Documentation
-------------
"""
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec, SubplotSpec#NOQA
import matplotlib.colors as mcolors
from matplotlib.artist import Artist
from matplotlib.axes import Axes
import io as io
import gc as gc
import types as types
import numpy as np
from collections.abc import Collection
from .deferred import Deferred
from .util import verify, warn
from .dynalimits import AutoLimits
from .pretty import PrettyObject as pdct
from .err import verify_inp

class MODE:
    """
    How to draw 
    graphs. The best mode depends on the output IPython implementation.
    """ 
    HDISPLAY = 0x01
    """ Call :func:`IPython.display.display`. """
    
    CANVAS_IDLE = 0x02
    """ Call `matplotlib.pyplot.figure.canvas.draw_idle <https://matplotlib.org/stable/api/backend_bases_api.html#matplotlib.backend_bases.FigureCanvasBase.draw_idle>`__ """
    
    CANVAS_DRAW = 0x04
    """ Call `matplotlib.pyplot.figure.canvas.draw_idle <https://matplotlib.org/stable/api/backend_bases_api.html#matplotlib.backend_bases.FigureCanvasBase.draw>`__ """

    PLT_SHOW = 0x80
    """ Call :func:`matplotlib.pyplot.show`. """
       
    DEFAULT = HDISPLAY
    """ Setting which works for Jupyter lab and VSCode with ``%matplotlib inline`` as far as we can tell. """


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
    Deferred wrapper around a :class:`matplotlib.axes.Axes` objects returned by :meth:`cdxcore.dynaplot.DynaFig.add_subplot` or similar.
    
    *You should not need to know that this object is not actually a* :class:`matplotlib.axes.Axes`.
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
            
        self._fig_id      = fig_id
        self._fig_list    = fig_list
        self._row         = row
        self._col         = col
        self._spec_pos    = spec_pos
        self._axes_rect   = rect
        self._title       = title
        self._plots       = {}
        self._kwargs      = dict(kwargs)
        self._ax          = None
        self._projection  = projection
        self.__auto_lims  = None
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
        assert self._ax is None, "Internal error; function called twice?"
        
        def handle_kw_share( kw ):
            """ handle sharex and sharey """
            v = self._kwargs.pop(kw, None)
            if v is None:
                return
            if isinstance( v, Axes ):
                self._kwargs[kw] = v
            assert isinstance( v, DynaAx ), ("Cannot",kw,"with type:", type(v))
            assert not v._ax is None, ("Cannot", kw, "with provided axis: it has bnot been creatred yet. That usually means that you mnixed up the order of the plots")
            self._kwargs[kw] = v._ax
            
        handle_kw_share("sharex")
        handle_kw_share("sharey")
        
        if not self._row is None:
            # add_axes
            num     = 1 + self._col + self._row*cols
            self._ax = plt_fig.add_subplot( rows, cols, num, projection=self._projection, **self._kwargs )
        elif not self._spec_pos is None:
            # add_subplot with grid spec
            self._ax = plt_fig.add_subplot( self._spec_pos.deferred_result, projection=self._projection, **self._kwargs )            
        else:
            # add_axes
            self._ax = plt_fig.add_axes( self._axes_rect, projection=self._projection, **self._kwargs )        

        if not self._title is None:
            self._ax.set_title(self._title)

        # handle common functions which expect an 'axis' as argument
        # and auto-translate any DynaAx's 
        # Just sharex() and sharey() for the moment.
        ref_ax    = self._ax
        ax_sharex = ref_ax.sharex
        def sharex(self, other):
            if isinstance(other, DynaAx):
                verify( not other._ax is None, "Cannot sharex() with provided axis: 'other' has not been created yet. That usually means that you have mixed up the order of the plots")
                other = other._ax
            return ax_sharex(other)
        ref_ax.sharex = types.MethodType(sharex,ref_ax)

        ax_sharey = ref_ax.sharey
        def sharey(self, other):
            if isinstance(other, DynaAx):
                verify( not other._ax is None, "Cannot sharey() with provided axis: 'other' has not been created yet. That usually means that you have mixed up the order of the plots")
                other = other._ax
            return ax_sharey(other)
        ref_ax.sharey = types.MethodType(sharey,ref_ax)

        # call all deferred operations
        self.deferred_resolve( self._ax )
        
    def remove(self):
        """
        Equivalent of :meth:`matplotlib.axes.Axes.remove`: removes this axis from
        the underlying figure. Note that this will not trigger
        a removal from the actual visualization until :meth:`cdxcore.dynaplot.DynaFig.render` 
        is called.
        """
        assert self in self._fig_list, ("Internal error: axes not contained in figure list")
        self._fig_list.remove(self)
        self._ax.remove()
        self._ax = None
        #gc.collect()
        
    # automatic limit handling
    # -------------------------
    
    def plot(self, *args, scalex=True, scaley=True, data=None, **kwargs ):
        """
        Wrapper around :meth:`matplotlib.axes.Axes.plot`.

        This function wrapper does not support the ``data`` interface
        of :meth:`matplotlib.axes.Axes.plot`.

        If automatic limits are not used, this is a wrapper with deferred pass-through.
        If automatic limits are used, then this function will update 
        the underlying automated limits accordingly.
        
        Parameters
        ----------
            args, scalex, scaley, data, kwargs : ...
                See :meth:`matplotlib.axes.plot`.
            
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
        self._kwargs = dict(kwargs)
        _DynaDeferred.__init__(self,f"gridspec#{cnt}({nrows},{ncols})")

    def __str__(self):
        return self.deferred_info[1:]
        
    def _initialize( self, plt_fig ):
        """ Lazy initialization """
        assert self.grid is None, ("_initialized twice?")
        if len(self._kwargs) == 0:
            self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols )
        else:
            # wired error in my distribution
            try:
                self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols, **self._kwargs )
            except TypeError as e:
                estr = str(e)
                if estr != "GridSpec.__init__() got an unexpected keyword argument 'kwargs'":
                    raise e
                warn("Error calling matplotlib GridSpec() with **kwargs: %s; will attempt to ignore any kwargs.", estr)
                self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols )
        self.deferred_resolve( self.grid )

class DynaFig(_DynaDeferred):
    """
    Deferred wrapper around :class:`matplotlib.figure.Figure`.
    
    Provides a simple :meth:`cdxcore.dynaplot.DynaFig.add_subplot` without the need to pre-specify axes positions
    as is common for :mod:`matplotlib`.
    
    Construct elements of this class with :func:`cdxcore.dynaplot.figure`.
    """

    def __init__(self, title    : str|None = None, *,
                       row_size : int = 5,
                       col_size : int = 4,
                       fig_size : tuple[int]|None = None,
                       columns  : int = 5,
                       tight    : bool = True,
                       draw_mode: int = MODE.DEFAULT,
                       **fig_kwargs ):
        """
        __init__
        """
        if not fig_size is None:
            verify( not 'figsize' in fig_kwargs, "Cannot specify both `figsize` and `fig_size`", exception=ValueError)
            fig_kwargs['figsize'] = fig_size
                
        self._hdisplay     = None
        self._axes         = []   #: 
                                 #: 
        self._grid_specs   = []
        self._fig          = None
        self._row_size     = int(row_size)
        self._col_size     = int(col_size)
        self._cols         = int(columns) if not columns is None else None
        self._tight        = bool(tight)
        self._tight_para   = None
        self._fig_kwargs   = dict(fig_kwargs)
        if self._tight:
            self._fig_kwargs['tight_layout'] = True
        verify( self._row_size > 0, "'row_size' must be positive", exception=ValueError)
        verify( self._col_size > 0, "'col_size' must be positive", exception=ValueError)
        verify( self._cols is None or self._cols > 0, "'columns' must be positive or None", exception=ValueError)
        self._this_row    = 0
        self._this_col    = 0
        self._max_col     = 0
        self._fig_title   = title
        self._closed      = False
        self._enter_count = 0
        self.draw_mode    = draw_mode
        #: A combination of :class:`cdxcore.dynaplot.MODE` flags on how to draw plots
        #: once they were rendered. The required function call differs by IPython platform.
        #: The default, :attr:`cdxcore.dynaplot.MODE.DEFAULT` draws well on Jupyter notebooks
        #: and VSCode if :func:`cdxcore.dynaplot.dynamic_backend` was called
        #: (which sets ``%matplotlib inline``).

        verify( not 'cols' in fig_kwargs, "Unknown keyword 'cols'. Did you mean 'columns'?", exception=ValueError)
        
        dyna_title = ( title if len(title) <= 20 else ( title[:17] + "..." ) ) if not title is None else None
        _DynaDeferred.__init__(self, f"figure('{dyna_title}')" if not title is None else "figure()" )

    def __str__(self):
        return self.deferred_info[1:]

    def __del__(self): # NOQA
        """ Ensure the figure is closed """
        self.close()

    # properties
    # ----------

    @property
    def axes(self) -> list[DynaAx]:
        """
        List of axes. Until :meth:`cdxcore.dynaplot.DynaFig.render` is called, these are :class:`cdxcore.dynaplot.DynaAx` objects;
        afterwards, these are :class:`matplotlib.axes.Axes` objects.
        """
        return self._axes

    @property
    def fig(self) -> plt.Figure|None:
        """
        Returns the figure or ``None`` if it was not yet rendered.
        """
        return self._fig
    
    @property
    def hdisplay(self):
        """
        Returns the :class:`IPython.display.DisplayHandle` for the current display, if
        ``MODE.HDISPLAY`` was used for ``draw_mode`` when the figure was constructed, and if the figure
        was rendered yet. Otherwise returns ``None``.
        """
        return self._hdisplay
    
    @property
    def is_closed(self) -> bool:
        """ Returrns whether the figure was closed """
        return self._closed
    
    # functionality
    # -------------

    def add_subplot(self, title     : str|None = None, *,
                          new_row   : bool|None = None,
                          spec_pos  : type|None = None,
                          projection: str|None = None,
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
        is set. Use :meth:`cdxcore.dynaplot.DynaFig.add_axes` to draw plots at any time.
        1
        Parameters
        ----------
            title : str | None, default ``None``
                Optional title for the plot.

            new_row : bool | None, default ``None``
                Whether to force a new row and place this polt in the first column. Default is ``False``.

            spec_pos : grid spec | None, default ``None``
                Grid spec position from :meth:`cdxcore.dynaplot.DynaFig.add_gridspec`, or ``None``.

            projection : str | None, default ``None``
                What ``projection`` to use. The default ``None`` matches the default choice for
                :meth:`matplotlib.figure.Figure.add_subplot`.

            kwargs : dict
                other arguments to be passed to matplotlib's :meth:`matplotlib.figure.Figure.add_subplot`.
                
        Returns
        -------
            Axis : :class:`cdxcore.dynaplot.DynaAx`
                A wrapper around an matplotlib axis.
        """
        verify( not self._closed, "Cannot call add_subplot() after close() was called")
        verify( self._fig is None, "Cannot call add_subplot() after render() was called. Use add_axes() instead")

        # backward compatibility:
        # previous versions has "new_row" first.
        assert title is None or isinstance(title, str), ("'title' must be a string or None, not", type(title))
        title   = str(title) if not title is None else None
            
        if not spec_pos is None:
            assert new_row is None, ("Cannot specify 'new_row' when 'spec_pos' is specified")
            ax = DynaAx( fig_id=hash(self),
                         fig_list=self._axes,
                         row=None, 
                         col=None,
                         title=title,
                         spec_pos=spec_pos, 
                         rect=None,
                         projection=projection, 
                         kwargs=dict(kwargs) )
            
        else:
            new_row = bool(new_row) if not new_row is None else False
            
            if new_row:
                if self._this_col > 0:
                    self._this_row = self._this_row + 1
                    self._this_col = 0
            else:
                if not self._cols is None and ( self._this_col >= self._cols ):
                    self._this_row = self._this_row + 1
                    self._this_col = 0

            if self._max_col < self._this_col:
                self._max_col = self._this_col
            ax = DynaAx( fig_id=hash(self),
                         fig_list=self._axes,
                         row=self._this_row,
                         col=self._this_col,
                         spec_pos=None,
                         rect=None,
                         title=title,
                         projection=projection,
                         kwargs=dict(kwargs) )
            self._this_col += 1
        assert ax in self._axes
        return ax

    add_plot = add_subplot

    def add_subplots( self, *titles, sharex : DynaAx|bool|None = None, sharey : DynaAx|bool|None = None, **kwargs ) -> list[DynaAx]:
        """
        Generate a number of sub-plots in one function call.
        
        Use strings to generate subplots with such titles, ``\n`` for a new row, and integers
        to mass-generate a number of plots.
        
        This example generates a 2x2 block of plots::
            
            from cdxcore.dynaplot import figure
            
            with figure("Test", col_size=4, row_size=4) as fig:
                axA1, axA2, axB1, axB2 = fig.add_subplot("A1", "A2", "\n", "B1", "B2")
            
        Parameters
        ----------
        titles : list
            A list if strings, integers, ``\n`` and/or ``None``'s: a string generates a sub-plot with that title;
            an int generates as many subplots, and ``\n`` starts a new row. ``None`` skips the entry.
            This is useful when creating conditional lists of sub-plots, e.g.::
                
                from cdxcore.dynaplot import figure
                
                with figure("Test", col_size=4, row_size=4) as fig:
                    axA1, axA2, axB1, axB2 = fig.add_subplot("A1", "A2" if show2 else None, "\n", "B1", "B2" if show2 else None)
                    if show2: assert not axA2 is None and not axB2 is None
                    if not show2: assert axA2 is None and axB2 is None
                            
            ``None`` will not create an empty slot; it will simply not generate the plot.
            To generate empty slots or span plots over several columsn or rows,
            use :meth:`cdxcore.dynaplot.DynaFig.add_subplot` with ``grid_spec``.
                    
            Note that the number of columns is usually limited by the ``columns`` parameter
            when :func:`cdxcore.dynaplot.figure` is called. You can set ``columns`` to ``None``
            to freely generate blocks of graphs.
            
        sharex : DynaAx | bool | None, default ``None``
            Can be used to share the x axis either with a specific axis, or with the first axis generated
            by this function call (``True``). If ``False`` or ``None`` this keyword has no effect.
            
        sharey : DynaAx | bool | None, default ``None``
            Can be used to share the y axis either with a specific axis, or with the first axis generated
            by this function call (``True``). If ``False`` or ``None`` this keyword has no effect.
            
        Returns
        -------
            Sub-plots: tuple
                A tuple of sub-plots, one for each ``title``.
        """
        if len(titles) == 0:
            return ()
        r = []
        first_ix = None
        for tt in titles:
            if tt is None:
                r.append(None)
            elif tt=="\n":
                self.next_row()
            elif isinstance(tt,int):
                verify( tt>=0, "'titles': found negative integer?", exception=ValueError)
                first_ix = len(r) if first_ix is None else first_ix
                r += [ self.add_subplot(**kwargs) for _ in range(tt) ]
            else:
                verify( isinstance(tt,str), lambda : f"'titles' must contain None, int's or strings. Found type {type(tt)}.", exception=ValueError)
                first_ix = len(r) if first_ix is None else first_ix
                r.append( self.add_subplot(tt, **kwargs) )
        
        # share either implicitly or from a given plot
        start = 0
        if isinstance(sharex, bool):
            sharex = r[first_ix] if not first_ix is None else None
            start  = (first_ix+1) if not first_ix is None else None
            assert first_ix is None or not sharex is None, ("Internal error")
        if not sharex is None:
            for ax in r[start:]:
                if not ax is None:
                    ax.sharex(sharex)
        start = 0
        if isinstance(sharey, bool):
            sharey = r[first_ix] if not first_ix is None else None
            start  = (first_ix+1) if not first_ix is None else None
            assert first_ix is None or not sharey is None, ("Internal error")
        if not sharey is None:
            for ax in r[start:]:
                if not ax is None:
                    ax.sharey(sharey)
        return r
    
    def add_axes( self, 
                  rect      : tuple, 
                  title     : str|None = None, *,
                  projection: str|None = None,
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
            
            title : str | None, default ``None``
                Title for the plot, or ``None`` for no plot.
                
            projection : str | None, default ``None``
                What ``projection`` to use. The default ``None`` matches the default choice for
                :meth:`matplotlib.figure.Figure.add_axes`
    
            args, kwargs :
                keyword arguments to be passed to :meth:`matplotlib.figure.Figure.add_axes`.

        Returns
        -------
            Axis : :class:`cdxcore.dynaplot.DynaAx`
                A wrapper around an matplotlib axis.
        """
        verify( not self._closed, "Cannot call add_subplot() after close() was called")
        verify( not isinstance(rect,str), "'rect' is a string ... did you mix up the order of 'title' and 'rect'?")
        title   = str(title) if not title is None else None
        if not isinstance(rect, tuple):
            rect = tuple(rect)
        verify( len(rect)==4, lambda:f"'rect' must be a tuple of length 4. Found '{rect}'")
        verify( np.isfinite(rect).all(), lambda:f"'rect' has infinite elements: {rect}")
        
        ax = DynaAx( fig_id=hash(self),
                     fig_list=self._axes, 
                     row=None, 
                     col=None, 
                     title=title, 
                     spec_pos=None, 
                     rect=rect,
                     projection=projection, 
                     kwargs=dict(kwargs) )
        assert ax in self._axes
        if not self._fig is None:
            ax._initialize( self._fig, rows=None, cols=None )        
        return ax
    
    def add_gridspec(self, ncols=1, nrows=1, **kwargs):
        """
        Wrapper for :meth:`matplotlib.figure.Figure.add_gridspec`, returning a defered ``GridSpec``.
        """
        grid = _DynaGridSpec( ncols=ncols, nrows=nrows, cnt=len(self._grid_specs), kwargs=kwargs )
        self._grid_specs.append( grid )
        return grid

    def next_row(self):
        """
        Skip to next row. 
    
        The next plot generated by :meth:`cdxcore.dynaplot.DynaFig.add_subplot` will 
        appears in the first column of the next row.
        """
        verify( self._fig is None, "Cannot call next_row() after render() was called")
        if self._this_col == 0:
            return
        self._this_col = 0
        self._this_row = self._this_row + 1

    def render(self, draw : bool = True ):
        """
        Draw all axes.
        
        If this function does not display the plots you generated, review the
        ``draw_mode`` parameter provided to :func:`cdxcore.dynaplot.figure` or :func:`cdxcore.dynaplot.DynaFig`, respectively, 

        Once called, no further plots can be added, but the plots can be updated in place.
        
        Parameters
        ----------
        draw : bool, default ``True``
            If False, then the figure is created, but not drawn.
            You usually use ``False`` when planning to use
            :func:`cdxcore.dynaplot.DynaFig.savefig` or :func:`cdxcore.dynaplot.DynaFig.to_bytes`.
        """
        verify( not self._closed, "Cannot call render() after close() was called")
        if len(self._axes) == 0:
            return
        if self._fig is None:
            # create figure
            if not 'figsize' in self._fig_kwargs:
                self._fig_kwargs['figsize'] = ( self._col_size*(self._max_col+1), self._row_size*(self._this_row+1))
            self._fig  = plt.figure( **self._fig_kwargs )
            if self._tight:
                self._fig.tight_layout()
                self._fig.set_tight_layout(True)
            if not self._fig_title is None:
                self._fig.suptitle( self._fig_title )
            # create all grid specs
            for gs in self._grid_specs:
                gs._initialize( self._fig )
            # create all axes
            for ax in self._axes:
                ax._initialize( self._fig, rows=self._this_row+1, cols=self._max_col+1 )
            # execute all deferred calls to fig()
            self.deferred_resolve( self._fig )
            
        if not draw:
            return
        if self.draw_mode & MODE.HDISPLAY:
            if self._hdisplay is None:
                from IPython import display
                self._hdisplay = display.display(display_id=True)
                verify( not self._hdisplay is None, "Could not optain current IPython display ID from IPython.display.display(). Set DynaFig.MODE = 'canvas' for an alternative mode")
            self._hdisplay.update(self._fig)
        if self.draw_mode & MODE.CANVAS_IDLE:
            self._fig.canvas.draw_idle()
        if self.draw_mode & MODE.CANVAS_DRAW:
            self._fig.canvas.draw()
        if self.draw_mode & MODE.PLT_SHOW:
            plt.show()

    def savefig(self, fname : str,
                      silent_close : bool = True, 
                      **kwargs ):
        """
        Saves the figure to a file.
        
        Wrapper around :func:`matplotlib.pyplot.savefig`. Essentially, `this function <https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html>`__
        writes the figure to a file
        rather than displaying itl.

        Parameters
        ----------
        fname : str
            `filename or file-like object <https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html>`__

        silent_close : bool, default ``True``
            If ``True`` (the default), call :meth:`cdxcore.dynaplot.DynaFig.close` once the figure was saved to disk.
            Unless the figure was drawn before, this means that the figure will not be displayed in jupyter, and
            subsequent activity is blocked.
            
        kwargs : dict
            These arguments will be passed to :meth:`matplotlib.pyplot.savefig`.
        """
        verify( not self._closed, "Cannot call savefig() after close() was called")
        if self._fig is None:
            self.render(draw=False)
        self._fig.savefig( fname, **kwargs )
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
        silent_close : bool, default ``True``
            If ``True``, call :meth:`cdxcore.dynaplot.DynaFig.close` after this genersating the byte streanm.
            Unless the figure was drawn before, this means that the figure will not be displayed in jupyter, and
            subsequent activity is blocked.

        Returns
        -------
        image : bytes
            Buyte stream of the image.
        """
        verify( not self._closed, "Cannot call savefig() after close() was called")
        img_buf = io.BytesIO()
        if self._fig is None:
            self.render(draw=False)
        self._fig.savefig( img_buf )
        if silent_close:
            self.close(render=False)
        data = img_buf.getvalue()
        img_buf.close()
        return data
    
    @staticmethod
    def store():
        """ Create a :class:`cdxcore.dynaplot.FigStore`. Such a store allows managing graphical elements (artists) dynamically. See the examples
        in the introduction. """
        return FigStore()

    def close(self, render          : bool = True, 
                    clear           : bool = False ):
        """
        Closes the figure. 
        
        Call this to avoid a duplicate in jupyter output cells.
        By dault this function will call :meth:`cdxcore.dynaplot.DynaFig.render` to draw the figure, and then close it.

        Parameters
        ----------
            render : bool, default ``True``
                If  ``True``, the default, this function will call :meth:`cdxcore.dynaplot.DynaFig.render` and therefore renders the figure before closing the figure.
            clear  : bool, default ``False``
                If ``True``, all axes will be cleared. *This is experimental.* The default is ``False``.
        """
        if not self._closed:
            # magic wand to avoid printing an empty figure message
            if clear:
                if not self._fig is None:
                    def repr_magic(self):
                        return type(self)._repr_html_(self) if len(self._axes) > 0 else "</HTML>"
                    self._fig._repr_html_ = types.MethodType(repr_magic,self._fig)
                    self.delaxes( self._axes, render=render )
            elif render:
                self.render(draw=True)
            if not self._fig is None:
                plt.close(self._fig)
        self._fig      = None
        self._closed   = True
        self._hdisplay = None
        gc.collect()
        
    def remove_all_axes(self, *, render : bool = False):
        """ Calls :meth:`cdxcore.dynaplot.DynaAx.remove` for all :attr:`cdxcore.dynaplot.DynaFig.axes` """
        while len(self._axes) > 0:
            self._axes[0].remove()
        if render:
            self.render(draw=True)
        
    def delaxes( self, ax : DynaAx, *, render : bool = False ):
        """
        Equivalent of :meth:`matplotlib.figure.Figure.delaxes`, but this function can also take a list.
        """
        verify( not self._closed, "Cannot call render() after close() was called")
        if isinstance( ax, Collection ):
            ax = list(ax)
            for x in ax:
                x.remove()
        else:
            assert ax in self._axes, ("Cannot delete axes which wasn't created by this figure")
            ax.remove()
        if render:
            self.render()
            
    # context for cleaning up
    # -----------------------
    
    def __enter__(self):
        self._enter_count += 1
        return self
    
    def __exit__(self, *args, **kwargs):
        self._enter_count -= 1
        if self._enter_count <= 0:
            self.close()
        return False

def figure( title    : str|None = None, *,
            row_size : int = 5,
            col_size : int = 4,
            fig_size : tuple[int]|None = None,
            columns  : int = 5,
            tight    : bool = True,
            draw_mode: int = MODE.DEFAULT,
            add_plots: int|list|None = None,
            **fig_kwargs ):
    """
    Creates a dynamic figure of type :class:`cdxcore.dynaplot.DynaFig`.
    
    By default the ``fig_size`` of the underlying :class:`matplotlib.figure.Figure`
    will be derived from the number of plots vs ``cols``, ``row_size`` and ``col_size``
    as ``(col_size* (N%col_num),  row_size (N//col_num))``.
    
    If ``fig_size`` is specified then ``row_size`` and ``col_size`` are ignored.
    
    Once the figure is constructed,
    
    1) Use :meth:`cdxcore.dynaplot.DynaFig.add_subplot` to add plots (without the cumbersome need       to know the number of plots in advance);
    
    2) Call :meth:`cdxcore.dynaplot.DynaFig.render` to place those plots.
    
    3) Call :meth:`cdxcore.dynaplot.DynaFig.close` to close the figure and avoid duplicate copies in Jupyter; a convient wrapper is to use
      ``with`` to ensure ``close()`` gets called. This pattern is used below.
    
    **Examples:**

    Simply use :meth:`cdxcore.dynaplot.DynaFig.add_subplot` without the
    matplotlib need to pre-specify axes positions::
        
        from cdxcore.dynaplot import figure    
        with dynaplot.figure("Two plots") as fig:
            ax = fig.add_subplot("1")
            ax.plot(x,y)
            ax = fig.add_subplot("2")
            ax.plot(x,y)
        
    Here is an example using :meth:`matplotlib.figure.Figure.add_gridspec`::
        
        from cdxcore.dynaplot import figure    
        with dynaplot.figure() as fig:
            gs  = fig.add_gridspec(2,2)
            ax = fig.add_subplot( gs[:,0] )
            ax.plot(x,y)
            ax = fig.add_subplot( gs[:,1] )
            ax.plot(x,y)
        
    **Important Functions:**    
    
    The returned :class:`cdxcore.dynaplot.DynaFig` will 
    defer all other function calls to the figure
    object until :meth:`cdxcore.dynaplot.DynaFig.render`
    or :meth:`cdxcore.dynaplot.DynaFig.close` are called.
    Whenever you use ``with`` at the end of the context window :meth:`cdxcore.dynaplot.DynaFig.close`
    will be called for you.
    
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
        title : str, default ``None``
            An optional title which will be passed to :meth:`matplotlib.pyplot.suptitle`.
            
        fig_size : tuple[int] | None, default ``None``
            By default the ``fig_size`` of the underlying :func:`matplotlib.pyplot.figure`
            will be derived from the number of plots vs ``cols``, ``row_size`` and ``col_size``
            as ``(col_size* (N%col_num),  row_size (N//col_num))``.
            
            If ``fig_size`` is specified then ``row_size`` and ``col_size`` are ignored.

        row_size : int, default ``5``
            Size for a row for matplot lib. Default is 5.
            This is ignored if ``fig_size`` is specified.
            
        col_size : int, default ``4``
            Size for a column for matplot lib. Default is 4.
            This is ignored if ``fig_size`` is specified.

        columns : int, default ``5``
            How many columns to use when :meth:`cdxcore.dynaplot.DynaFig.add_subplot` is used.
            If omitted then the default is 5.

        tight : bool, default ``True``
            Short cut for :meth:`matplotlib.figure.Figure.set_tight_layout`. The default is ``True``.
            
            Note that when ``tight`` is ``True`` and :meth:`cdxcore.dynaplot.DynaFig.add_axes` 
            is called a :class:`UserWarning` is generated. Turn ``tight`` off to avoid this.
            
        draw_mode : int, default ``MODE.DEFAULT``
            A combination of :class:`cdxcore.dynaplot.MODE` flags on how to draw plots
            once they were rendered. The required function call differs by IPython platform.
            The default, :attr:`cdxcore.dynaplot.MODE.DEFAULT` draws well on Jupyter notebooks
            and in VSCode if ``%matplotlin inline`` or ``widget`` is used. The latter requires the
            packages ``ipympl`` and ``ipywidgets``.
            
            Use the function :func:`cdxcore.dynaplot.dynamic_backend` to
            set the ``widget`` mode if possible.
            
        fig_kwargs :
            Other matplotlib parameters for :func:`matplotlib.pyplot.figure` to
            create the figure. 

     
    Returns
    -------
        figure: :class:`cdxcore.dynaplot.DynaFig`
            A dynamic figure. 
    """
    fig = DynaFig(  title=title,
                    row_size=row_size,
                    col_size=col_size,
                    fig_size=fig_size,
                    columns=columns,
                    tight=tight,
                    draw_mode=draw_mode,
                    **fig_kwargs
                    )
    return fig

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
    to call :meth:`cdxcore.dynaplot.DynaFig.store` on your figure.
    
    The above pattern is not speed or memory optimal. It is more efficient to modify the `artist <https://matplotlib.org/stable/tutorials/artists.html>`__
    directly. While true, for most applications a somewhat rude cancel+replace is simpler. ``FigStore`` was introduced to facilitiate that.    
    """

    def __init__(self):
        """ Create FigStore() objecy """
        self._elements = []

    def add(self, element : Artist):
        """
        Add an element to the store.
        The same operation is available using ``+=``.
        
        Parameters
        ----------
            element : :class:`matplotlib.artist.Artist`
                Graphical matplot element derived from :class:`matplotlib.artist.Artist` such as :class:`matplotlib.lines.Line2D`; 
                or a ``Collection`` of the above; or ``None``.
                
        Returns
        -------
            self : ``Figstore``
                Returns ``self``. This way compound statements ``a.add(x).add(y).add(z)`` work.
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
            raise ValueError(f"Cannot add element of type '{type(element).__name__}' as it is not derived from matplotlib.artist.Artist, nor is it a Collection")
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
                raise RuntimeError(f"Cannot remove() element of type '{type(e).__name__}' as it is not derived from matplotlib.artist.Artist, nor is it a Collection")
    
        while len(self._elements) > 0:
            rem( self._elements.pop(0) )
        self._elements = []
        #gc.collect()
        
    clear = remove
    
def store():
    """ Creates a :class:`cdxcore.dynaplot.FigStore` which can be used to dynamically update a figure. """
    return FigStore()

# ----------------------------------------------------------------------------------
# x/y lim support
# ----------------------------------------------------------------------------------

def min_o_min( *args, default : float|None = None ):
    """
    Computes minimum of minima.
    
    This function iterates through all arguments, and takes the minimum of all minima.
    Parmaters can be numbers, :class:`numpy.ndarray` arrays or lists of the former.
    
    This function is useful when calling :meth:`matplotlib.axes.Axes.set_xlim`
    or :meth:`matplotlib.axes.Axes.set_ylim`.
    
    Parameters
    ----------
        args : list[int|float|np.ndarray|None|list]
            Numbers, :class:`numpy.ndarray` arrays or lists of the former.
            Elements which are ``None`` are skipped.
            
        default : float|None, default ``None``
            Default value if ``args`` was empty.
            
    Returns
    -------
        min : float|None
            The minimum of all minima, or ``default`` if no elements were found.
    """
    
    r = None
    for a in args:
        if a is None:
            continue            
        if isinstance(a, np.ndarray):
            a = np.min(a)
        elif isinstance(a, (int, float, np.number)):
            a = float(a)
        else:
            a = min_o_min(*a)
        r = min(r,a) if not r is None else a
    return r if not r is None else default

def max_o_max( *args, default : float|None = None ):
    """
    Computes maximum of maxima.
    
    This function iterates through all arguments, and takes the maximum of all maxima.
    Parmaters can be numbers, :class:`numpy.ndarray` arrays or lists of the former.
    
    This function is useful to compute arguments for :meth:`matplotlib.axes.Axes.set_xlim`
    or :meth:`matplotlib.axes.Axes.set_ylim`. 

    Parameters
    ----------
        args : list[int|float|np.ndarray|None|list]
            Numbers, :class:`numpy.ndarray` arrays or lists of the former.
            Elements which are ``None`` are skipped.
            
        default : float|None, default ``None``
            Default value if ``args`` was empty.
            
    Returns
    -------
        max : float|None
            The maximum of all maxima, or ``default`` if no elements were found.
    """
    r = None
    for a in args:
        if a is None:
            continue
        if isinstance(a, np.ndarray):
            a = np.max(a)
        elif isinstance(a, (int, float, np.number)):
            a = float(a)
        else:
            a = max_o_max(*a)
        r = max(r,a) if not r is None else a
    return r

def m_o_m( *args, pos_floor : float|None = None, buf : float = 0.05, min_dx : float = 0.01 ):
    """
    Computes :func:`cdxcore.dynaplot.min_o_min` and :func:`cdxcore.dynaplot.max_o_max`
    for ``args`` to obtain their minimum of minima and maximum of maxima.

    This function is useful to compute arguments for :meth:`matplotlib.axes.Axes.set_xlim`
    or :meth:`matplotlib.axes.Axes.set_ylim`.
    
    If ``pos_floor`` is ``None`` then the function returns::
        
        dx = max( min_dx, max_ - min_ )
        return min_ - dx*buf, max_dx*buf
    
    If ``pos_floor`` is not ``None``, then the function floors ``min_ - dx*buf`` at ``pos_floor``.
    
    *Usage*::

        from cdxcore.dynaplot import figure, m_o_m
        import numpy as np
            
        x = np.random.normal(size=(10,))
        y = np.random.normal(size=(8,2))
        z = [ np.random.normal(size=(3,2)), 0.1, None ]
        
        with figure() as fig:
            ax = fig.add_subplot()
            ax.plot( x )
            ax.plot( y )
            ax.plot( z[1] )
            ax.set_ylim( *m_o_m(x,y,z, min_dx=0.01) )                
    
    Returns
    -------
        min, max : float|None, float|None
            The adjusted minimum and maximum values as discussed above.
            The function returns ``None, None`` if ``args`` does not contain any numbers.
            Such result can be passed directly to :meth:`matplotlib.axes.Axes.set_xlim` or
            :meth:`matplotlib.axes.Axes.set_ylim` as both accept ``None`` as default values.
    
    """
    min_ = min_o_min( *args )
    if min_ is None:
        return None, None
    max_ = max_o_max( *args )
    assert not max_ is None, ("Internal error - max None but min isn't??")
    assert min_ <= max_, ("Min/max order wrong", min_, max_)

    if buf is None or buf == 0.:
        return min_, max_
    
    dx   = max( min_dx, max_ - min_ )
    if pos_floor is None:
        return min_ - dx*buf, max_ + dx*buf
    else:
        verify( min_ > 0., lambda : f"Cannot use 'buf' in 'pos' mode: 'min_o_min' of the inputs is not positive, but {min_:.4g}")
        verify_inp( pos_floor >= 0., "'pos_floor' cannot be negative")
        rmin = max( min_ - dx*buf, min_*pos_floor )
        return rmin, max_+dx*buf

# ----------------------------------------------------------------------------------
# axis utilities
# ----------------------------------------------------------------------------------

def focus_line(left : float, 
               right : float, 
               N : int,*,
               concentration : float = 0.9,
               power : float|int=2,
               focus : float|None = None,
               focus_on_grid : bool = False,
               eps : float=1E-8,
               dtype : type = None ):
    r"""
    Returns a line from ``left`` to ``right`` which has more points in ``focus``.

    This function computes a number of points on a line between ``left`` and ``right`` such that points around ``focus``
    are more dense. The ``concentration`` parameter allowws to blend between linear and focused points.

    The function is an appropriately scaled and shifted version of $x \mapsto x (1-c) + c\, x|x|^{p-1}$ where $c$ is concentration.

    Parameters
    ----------
        left, right : float, float
            Left hand and right hand points.

        N : int,
            Number of points; must be at least 3.

        concentration : float, default ``0.9``
            How much concentration: maximum is ``1`` while ``0`` give a linear distibution of points.

        focus : float|None, default ``None``
            Focus point. If not provided, the mid-point is used.

        focus_on_grid : bool, default ``None``
            Whether to place ``focus`` on the grid.

        dtype : type, default ``None``
            Numpy dtype.

    Returns
    -------
        points : :class:`numpy.ndarray`
            Numpy vector
    """

    left = float(left)
    right = float(right)
    if not focus is None:
        verify_inp( left<focus and focus<right, "'left', 'focus', and 'right' must be in order")
    else:
        verify_inp( left<right, "'left' and 'right' must be in order")
        focus = 0.5 * (left+right)
        
    verify_inp( N>=3, "'N' must be at least 3")
    verify_inp( concentration >=0. and concentration <= 1., "'concentration' must be within [0,1]")

    x     = np.linspace( - 1.,  +1., N )
    x     = x*(1.-concentration)+concentration*x*( np.pow(np.abs(x), power-1 ) if power>1 else 1.)
    assert np.abs( x[0]+x[-1] )<1E-8, ("Internal error", x[0], x[-1] )    
    x     /= x[-1]
    x[x<0.] *= (left-focus)/x[0]
    x[x>0.] *= (right-focus)/x[-1]
    x     += focus
    x[0]  = left
    x[-1] = right 
    return x

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

    table : str, default ``css4``
        Which `color table from matplotlib <https://matplotlib.org/stable/users/explain/colors/index.html>`__ to use: `"css4"`, `"base"`, `"tableau"` or `"xkcd"`.
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
    """ Iterator for `xkcd <https://xkcd.com/color/rgb/>`__ matplotlib colors """
    return colors("xkcd")

