"""
Basic error handling and reporting functions with minimal runtime performance overhead for string formatting.

Overview
--------

The main use of this module are the functions
:func:`cdxcore.err.verify` and :func:`cdxcore.err.warn_if`.
Both test some runtime condition and will either
raise an ``Exception`` or issue a ``Warning`` if triggered. In both cases, required string formatting is only performed
if the event is actually triggered.

This way we are able to write neat code which produces robust,
informative errors and warnings without impeding runtime performance.

Example::
    
    from cdxcore.err import verify, warn_if
    import numpy as np
    
    def f( x : np.ndarray ):
        std = np.std(x,axis=0,keepdims=True)
        verify( np.all( std>1E-8 ), "Cannot normalize 'x' by standard deviation: standard deviations are {std}", std=std )
        x /= std        
        
    f( np.zeros((10,10)) )
    
raises a :class:`RuntimeError`

.. code-block:: python

    Cannot normalize 'x' by standard deviation: standard deviations are [[0. 0. 0. 0. 0. 0. 0. 0. 0. 0.]]

For warnings, we can use ``warn_if``::

    from cdxcore.err import verify, warn_if
    import numpy as np
    
    def f( x : np.ndarray ):
        std = np.std(x,axis=0,keepdims=True)
        warn_if( not np.all( std>1E-8 ), lambda : f"Normalizing 'x' by standard deviation: standard deviations are {std}" )
        x   = np.where( std<1E-8, 0., x/np.where( std<1E-8, 1., std ) )
        
    f( np.zeros((10,10)) )
    
issues a warning::

    RuntimeWarning: Normalizing 'x' by standard deviation: standard deviations are [[0. 0. 0. 0. 0. 0. 0. 0. 0. 0.]]
      warn_if( not np.all( std>1E-8 ), "Normalizing 'x' by standard deviation: standard deviations are {std}", std=std )    

Note that though we used two different approaches for message formatting, the the error messages in both cases
are only formatted if the condition in ``verify`` is not met.

Import
------
.. code-block:: python

    from cdxcore.err import verify, warn_if, error, warn
    
Documentation
-------------
"""

import warnings as warnings
import os as os
from collections.abc import Callable
import sys as sys

__has_at_least_py312__ = sys.version_info >= (3, 12)

def _fmt( text : str, args = None, kwargs = None, f : Callable =  None ) -> str:
    """ Utility function. See [cdxcore.err.fmt][]() . 'f' not currently used.':meta private: """
    args   = None if not args is None and len(args) == 0 else args
    kwargs = None if not kwargs is None and len(kwargs) == 0 else kwargs
    
    # callable
    if not isinstance(text, str) and callable(text):
        # handle callable
        # we pass args and kwargs as provided
        if not args is None:
            if not kwargs is None:
                return text(* args, ** kwargs)
            else:
                return text(*args)
        elif not kwargs is None :
            return text(**kwargs)
        return text()
    text = str(text)
        
    # text
    # C-style positional parameters first
    if not args is None:
        # args are only valid for c-style %d, %s
        if not kwargs is None:
            raise ValueError("Cannot specify both 'args' and 'kwargs'", text)
        try:    
            return text % tuple(args)
        except TypeError as e:
            raise TypeError(e, text, args)
    
    # no keyword arguments --> must be plain text
    if kwargs is None:
        return text

    # text
    # python 2 and 3 mode
    kwargs = dict() if kwargs is None else kwargs
    if text.find("%(") == -1:
        return text.format(**kwargs)
    else:
        return text % kwargs
    
def fmt(text : str|Callable, * args, ** kwargs) -> str:
    """
    Basic tool for delayed string formatting.
    
    The main use case is that formatting is not executed until this function is called,
    hence potential error messages are not generated until an error actually occurs.
    See, for example, :func:`cdxcore.err.verify`.
    
    The follwing example illustrates all four supported modi operandi::
        
        from cdxcore.err import fmt
        one = 1
        fmt(lambda : f"one {one:d})   # using a lambda function
        fmt("one {one:d}", one=one)   # using python 3 string.format()
        fmt("one %(one)ld", one=one)  # using python 2 style
        fmt("one %ld", one)           # using c-style
    
    As shown, do not use f-strings directly as they are immediately executed in the scope they are typed in
    but wrap them with a ``lambda`` function.
    
    Parameters
    ----------    
    text : str | Callable
        Error text which may contain one of the following string formatting patterns:
        
        * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
          to obtain the output message.
        
        * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
        
        * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
        
        * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( * args, ** kwargs )``
          is called to obtain the output message.
          
          A common use case is using an f-string wrapped in a ``lambda`` function; see example above.
        
    * args, ** kwargs:
        See above

    Returns
    -------
    Text : str
        The formatted message.
    """
    return _fmt(text=text,args=args,kwargs=kwargs,f=fmt)

def error( text : str|Callable, *args, exception : Exception = RuntimeError, **kwargs ):
    """
    Raise an exception with string formatting.
    
    See also :func:`cdxcore.err.fmt` for formatting comments.
    The point of this function is to have an interface which is consistent with
    :func:`cdxcore.err.verify`.

    Examples::

        from cdxcore.err import error
        one = 1
        error(lambda : f"one {one:d}")  # wrapped f-string
        error("one {one:d}", one=one)   # using python 3 string.format()
        error("one %(one)ld", one=one)  # using python 2 style
        error("one %ld", one)           # using c-style
    
    As shown, do not use f-strings directly as they are immediately executed in the scope they are typed in
    but wrap them with a ``lambda`` function.

    Parameters
    ----------
    text : str | Callable
        Error text which may contain one of the following string formatting patterns:
        
        * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
          to obtain the output message.
        
        * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
        
        * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
        
        * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( * args, ** kwargs )``
          is called to obtain the output message.
          
          A common use case is using an f-string wrapped in a ``lambda`` function; see example above.
        
    exception : Exception, optional
        Which type of exception to raise. Defaults to :class:`RuntimeError`.

    * args, ** kwargs:
        See above

    Raises
    ------
    exception : exception
    """
    text = _fmt(text=text,args=args,kwargs=kwargs,f=error)
    raise exception( text )
    
def verify( cond : bool, text : str|Callable, *args, exception : Exception = RuntimeError, **kwargs ):
    """
    Raise an exception using delayed error string formatting if a condition is not met.
    
    The point of this function is to only format an error message if a condition ``cond`` is not met
    and an error is to be raised.

    Examples::
        
        from cdxcore.err import verify
        one = 1
        good = False                           # some condition
        verify(good, lambda : f"one {one:d}")  # wrapped f-string
        verify(good, "one {one:d}", one=one)   # using python 3 string.format()
        verify(good, "one %(one)ld", one=one)  # using python 2 style
        verify(good, "one %ld", one)           # using c-style
    
    As shown, do not use f-strings directly as they are immediately executed in the scope they are typed in
    but wrap them with a ``lambda`` function.
    
    Parameters
    ----------
    cond : bool
        Condition to test.
    
    text : str | Callable
        Error text which may contain one of the following string formatting patterns:
        
        * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
          to obtain the output message.
        
        * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
        
        * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
        
        * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( * args, ** kwargs )``
          is called to obtain the output message.
          
          A common use case is using an f-string wrapped in a ``lambda`` function; see example above.
        
    exception : Exception, optiona
        Which type of exception to raise. Defaults to :class:`RuntimeError`.

    * args, ** kwargs:
        See above

    Raises
    ------
    exception : exception
    """
    if not cond:
        text = _fmt(text=text,args=args,kwargs=kwargs,f=verify)
        raise exception( fmt(text, * args, ** kwargs) )

def verify_inp( cond : bool, text : str|Callable, *args, **kwargs ):
    """
    A short cut for :func:``cdxcore.err.verify`` with ``exception=ValueError``
    """
    verify( cond, text, *args, exception=ValueError, **kwargs )

_warn_skips = (os.path.dirname(__file__),)

def warn( text : str|Callable, *args, warning = RuntimeWarning, stack_level : int = 1, **kwargs ):
    """
    Issue a warning.
    
    The point of this function is to have an interface consistent with :func:`cdxcore.err.warn_if`.

    Examples::
        
        from cdxcore.err import warn
        one = 1        
        warn(lambda : f"one {one:d}")  # wrapped f-string
        warn("one {one:d}", one=one)   # using python 3 string.format()
        warn("one %(one)ld", one=one)  # using python 2 style
        warn("one %ld", one)           # using c-style
    
    As shown, do not use f-strings directly as they are immediately executed in the scope they are typed in
    but wrap them with a ``lambda`` function.
    
    Parameters
    ----------
    text : str | Callable
        Error text which may contain one of the following string formatting patterns:
        
        * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
          to obtain the output message.
        
        * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
        
        * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
        
        * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( * args, ** kwargs )``
          is called to obtain the output message.
          
          A common use case is using an f-string wrapped in a ``lambda`` function; see example above.
        
    warning : optional
        Which type of warning to issue. 
        This corresponds to the ``category`` parameter for :func:`warnings.warn`.
        Default is :class:`RuntimeWarning`.

    stack_level : int, optional
        What stack to report; see :func:`warnings.warn`.
        Default is 1, which means ``warn`` itself is not reported as part of the stack trace.

    * args, ** kwargs:
        See above
    """
    if __has_at_least_py312__:
        warnings.warn( message=text,
                    category=warning,
                    stacklevel=stack_level,
                    skip_file_prefixes=_warn_skips )
    else:
        warnings.warn( message=text,
                    category=warning,
                    stacklevel=stack_level )

def warn_if( cond : bool, text : str|Callable, *args, warning = RuntimeWarning, stack_level : int = 1, **kwargs ):    
    """
    Issue a warning with delayed string formatting if a condition is met.
    
    The point of this function is to only format an error message if a condition ``cond`` is met
    and a warning is to be issued.

    Examples::
            
        from cdxcore.err import warn_if
        one = 1       
        bad = True                            # some conditon
        warn_if(bad,lambda : f"one {one:d}")  # wrapped f-string
        warn_if(bad,"one {one:d}", one=one)   # using python 3 string.format()
        warn_if(bad,"one %(one)ld", one=one)  # using python 2 style
        warn_if(bad,"one %ld", one)           # using c-style
    
    As shown, do not use f-strings directly as they are immediately executed in the scope they are typed in
    but wrap them with a ``lambda`` function.
    
    Parameters
    ----------
    cond : bool
        Condition to test.
        
    text : str | Callable
        Error text which may contain one of the following string formatting patterns:
        
        * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
          to obtain the output message.
        
        * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
        
        * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
        
        * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( * args, ** kwargs )``
          is called to obtain the output message.
          
          A common use case is using an f-string wrapped in a ``lambda`` function; see example above.
        
    warning : optional
        Which type of warning to issue. 
        This corresponds to the ``category`` parameter for :func:`warnings.warn`.
        Default is :class:`RuntimeWarning`.

    stack_level : int, optional
        What stack to report; see :func:`warnings.warn`.
        Default is 1, which means ``warn`` itself is not reported as part of the stack trace.

    * args, ** kwargs:
        See above
    """
    if cond:
        text = _fmt(text=text,args=args,kwargs=kwargs,f=warn_if)
        if __has_at_least_py312__:
            warnings.warn( message=text,
                        category=warning,
                        stacklevel=stack_level,
                        skip_file_prefixes=_warn_skips )
        else:
            warnings.warn( message=text,
                        category=warning,
                        stacklevel=stack_level )
        

    