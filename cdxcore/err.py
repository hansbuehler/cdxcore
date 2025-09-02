# -*- coding: utf-8 -*-
"""
## Overview
Basic error handling and reporting functions

The main purpose of this module are the functions [verify][cdxcore.err.verify]() and [warn_if][cdxcore.err.warn_if](). Both test a runtime condition and will either
raise an Exception or issue a Warning. In both cases, required string formatting is only performed if the event is actually triggered, 
much like an _assert_ with a message tuple as argument.

This way we are able to write neat code which produces robust, informative errors and warnings without impeding runtime performance.

## Import
```
from cdxcore.err import verify, warn_if, error, warn #NOQA
```
"""

import warnings as warnings
import os as os
from collections.abc import Callable
import inspect as inspect

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
                return text(*args, **kwargs)
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
        return text % tuple(args)
    # text
    # python 2 and 3 mode
    kwargs = dict() if kwargs is None else kwargs
    if text.find("%(") == -1:
        return text.format(**kwargs)
    else:
        return text % kwargs
    
    """
    try:
        if text.find("%(") == -1:
            return text.format(**kwargs)
        else:
            return text % kwargs
    except KeyError as e:
        if f is None:
            raise e
    # get closure and globals
    f = inspect.unwrap( getattr(f, "__func__", f))
    assert not f is None
    closure = dict( f.__closure__ ) if not f.__closure__ is None else {}
    globs   = dict( f.__globals__ ) if not f.__globals__ is None else {}
    kwargs  = closure | globs
    print(list(kwargs))
    if text.find("%(") == -1:
        return text.format(**kwargs)
    else:
        return text % kwargs
    """

def fmt(text : str, *args, **kwargs) -> str:
    """
    Basic delayed string formatting made easy.
    
    The main use case is that formatting is not executed until this function is called,
    hence potential error messages are not generated until an error actually occurs.
    See, for example, [verify][cdxcore.err.verify]().
    
    Examples
    ```
    fmt("one %ld", 1)              # using c-style
    fmt("one %{one}ld", one=1)     # using python 2 style
    fmt("one {one:d}", one=1)      # using python 3 string.format()
    ```
    
    Do not use f-strings directly as they are executed in the scope they are typed in.
    Use instead
    ```
    fmt( lambda : f"one {one:d}" ) # f-style with lambda
    ```
    
    Parameters
    ----------
    text : str
        Error text which may contain one parameter pattern. See examples above.
        
        * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
        
        * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
        
        * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
        
        * lambda functions: if `text` is not a string but a callable this is called.
        
    args, **kwargs:
        See above
    """
    return _fmt(text=text,args=args,kwargs=kwargs,f=fmt)

def error( text : str, *args, exception : Exception = RuntimeError, **kwargs ):
    """
    Raise an exception of type `exception` with basic formatting.
    See also [fmt][cdxcore.err.fmt]() for formatting comments.
    The point of this function is to have a consistent interface to [verify][cdxcore.err.verify]().

    Examples
    ```
    error("one %ld", 1)              # using c-style
    error("one %{one}ld", one=1)     # using python 2 style
    error("one {one:d}", one=1)      # using python 3 string.format()
    ```
    
    Do not use f-strings directly as they are executed in the scope they are typed in.
    Use instead
    ```
    error( lambda : f"one {one:d}" ) # f-style with lambda
    ```

    Parameters
    ----------
    text : str
        Error text which may contain one parameter pattern. See examples above.
        
        * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
        
        * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
        
        * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
        
        * lambda functions: if `text` is not a string but a callable this is called.
    exception : Exception
        Which type of exception to raise.
    args, **kwargs:
        See above

    Raises
    ------
    exception
    """
    text = _fmt(text=text,args=args,kwargs=kwargs,f=error)
    raise exception( fmt(text, *args, **kwargs) )
    
def verify( cond : bool, text : str, *args, exception : Exception = RuntimeError, **kwargs ):
    """
    Validate a condition `cond` and raise an exception of type `exception` if `cond` is not True.
    In that case `text` will be formatted using `args` and `kwargs`.
    The point of this function is to only format the error message if the condition `cond` is not True
    and an error is raised.

    Examples
    ```
    verify( good, "one %ld", 1)              # using c-style
    verify( good, "one %{one}ld", one=1)     # using python 2 style
    verify( good, "one {one:d}", one=1)      # using python 3 string.format()
    ```
    
    Do not use f-strings directly as they are executed in the scope they are typed in.
    Use instead
    ```
    verify( good, lambda : f"one {one:d}" )  # f-style with lambda
    ```

    Parameters
    ----------
    cond : bool
        Condition to be True. If False, an exception is raised.
    text : str
        Error text which may contain one parameter pattern. See examples above.
        
        * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
        
        * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
        
        * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
        
        * lambda functions: if `text` is not a string but a callable this is called.
    exception : Exception
        Which type of exception to raise if 'cond' is False
    args, **kwargs:
        See above

    Raises
    ------
    exception
    """
    if not cond:
        text = _fmt(text=text,args=args,kwargs=kwargs,f=verify)
        raise exception( fmt(text, *args, **kwargs) )

_warn_skips = (os.path.dirname(__file__),)

def warn( text : str, *args, warning = RuntimeWarning, stack_level : int = 1, **kwargs ):
    """
    Issue a warning of type `warning` with basic formatting.
    The point of this function is to have a consistent interface to warn_if().

    Examples
    ```
    warn("one %ld", 1)              # using c-style
    warn("one %{one}ld", one=1)     # using python 2 style
    warn("one {one:d}", one=1)      # using python 3 string.format()
    ```
    
    Do not use f-strings directly as they are executed in the scope they are typed in.
    Use instead
    ```
    warn( lambda : f"one {one:d}" ) # f-style with lambda
    ```

    Parameters
    ----------
    text : str
        Error text which may contain one parameter pattern. See examples above.
        
        * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
        
        * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
        
        * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
        
        * lambda functions: if `text` is not a string but a callable this is called.
    warning :
        Which type of warning to issue.
        This is the `category` parameter to [warnings.warn](https://docs.python.org/3/library/warnings.html#available-functions)().
    stack_level :
        What stack to report. See [warnings.warn](https://docs.python.org/3/library/warnings.html#available-functions)().
    args, **kwargs:
        See above
    """
    text = _fmt(text=text,args=args,kwargs=kwargs,f=warn)
    warnings.warn( message=text,
                   category=warning,
                   stacklevel=stack_level,
                   skip_file_prefixes=_warn_skips )

def warn_if( cond : bool, text : str, *args, warning = RuntimeWarning, stack_level : int = 1, **kwargs ):    
    """
    Test `cond` and issue a warning of type `warning` if True.
    In that case `text` will be formatted using `args` and `kwargs`.
    The point of this function is to only format the error message if the condition `cond` is True
    and a warning is generated.

    Examples
    ```
    warn_if( bad, "one %ld", 1)              # using c-style
    warn_if( bad, "one %{one}ld", one=1)     # using python 2 style
    warn_if( bad, "one {one:d}", one=1)      # using python 3 string.format()
    ```
    
    Do not use f-strings directly as they are executed in the scope they are typed in.
    Use instead
    ```
    warn_if( bad, lambda : f"one {one:d}" ) # f-style with lambda
    ```

    Parameters
    ----------
    cond : bool
        Condition to test.
    text : str
        Error text which may contain one parameter pattern. See examples above.
        
        * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
        
        * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
        
        * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
        
        * lambda functions: if `text` is not a string but a callable this is called.
    warning :
        Which type of warning to issue.
        This is the `category` parameter to [warnings.warn](https://docs.python.org/3/library/warnings.html#available-functions)().
    stack_level :
        What stack to report. See [warnings.warn](https://docs.python.org/3/library/warnings.html#available-functions)().
    args, **kwargs:
        See above
    """
    if cond:
        text = _fmt(text=text,args=args,kwargs=kwargs,f=warn_if)
        warnings.warn( message=text,
                       category=warning,
                       stacklevel=stack_level,
                       skip_file_prefixes=_warn_skips )
        

    