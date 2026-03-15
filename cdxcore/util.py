from __future__ import annotations

"""
Basic utilities for Python such as type management, formatting, some trivial timers.

Import
------
.. code-block:: python

    import cdxcore.util as util
    
Documentation
-------------
"""

import datetime as datetime
import types as types
import psutil as psutil
from collections.abc import Mapping, Collection, Callable
import sys as sys
import time as time
from collections import OrderedDict
from sortedcontainers import SortedDict
import numpy as np
import pandas as pd
from .err import fmt, _fmt, verify, error, warn_if, warn ,verify_inp #NOQA
import inspect as inspect
from string import Formatter
from typing import Iterator, Any
from prettytable import PrettyTable

# =============================================================================
# basic indentification short cuts
# =============================================================================

__types_functions = None

#: a set of all ``types`` considered functions
def types_functions() -> tuple[type]:
    """ Returns a set of all ``types`` considered functions """
    global __types_functions
    if __types_functions is None:
        fs = set()
        try: fs.add(types.FunctionType)
        except: pass
        try: fs.add(types.LambdaType)
        except: pass
        try: fs.add(types.CodeType)
        except: pass
        #types.MappingProxyType
        #types.SimpleNamespace
        try: fs.add(types.GeneratorType)
        except: pass
        try: fs.add(types.CoroutineType)
        except: pass
        try: fs.add(types.AsyncGeneratorType)
        except: pass
        try: fs.add(types.MethodType)
        except: pass
        try: fs.add(types.BuiltinFunctionType)
        except: pass
        try: fs.add(types.BuiltinMethodType)
        except: pass
        try: fs.add(types.WrapperDescriptorType)
        except: pass
        try: fs.add(types.MethodWrapperType)
        except: pass
        try: fs.add(types.MethodDescriptorType)
        except: pass
        try: fs.add(types.ClassMethodDescriptorType)
        except: pass
        #types.ModuleType,
        #types.TracebackType,
        #types.FrameType,
        try: fs.add(types.GetSetDescriptorType)
        except: pass
        try: fs.add(types.MemberDescriptorType)
        except: pass
        try: fs.add(types.DynamicClassAttribute)
        except: pass
        __types_functions = tuple(fs)
    return __types_functions

def is_function(f) -> bool:
    """
    Checks whether ``f`` is a function in an extended sense.
    
    Check :func:`cdxcore.util.types_functions` for what is tested against.
    In particular ``is_function`` does not test positive for properties.    
    """
    return isinstance(f,types_functions())

def is_atomic( o: object ) -> bool:
    """
    Whether an element is atomic.
    
    Returns ``True`` if ``o`` is a
    ``string``, ``int``, ``float``, :class:`datedatime.date`, ``bool``, 
    or a :class:`numpy.generic`
    """
    if type(o) in [str,int,bool,float,datetime.date]:
        return True
    if isinstance(o,np.generic):
        return True
    return False

def is_float( o: object ) -> bool:
    """ Checks whether a type is a ``float`` which includes numpy floating types """
    if type(o) is float:
        return True
    if isinstance(o,np.floating):
        return True
    return False

def get_calling_function_name(default : str) -> str:
    """
    When called from a function, returns the name of the calling function. Otherwise returns ``default``.
    
    Example::

        from cdxcore.util import get_calling_function_name
    
        def g():
            print(get_calling_function_name("no caller")) # -> prints "f

        def f():
            g()
    """
    frame = inspect.currentframe() # that's us
    if frame is None:
        return default
    frame = frame.f_back
    if frame is None:
        return default
    frame = frame.f_back
    if frame is None:
        return default
    return frame.f_code.co_name

# =============================================================================
# python basics
# =============================================================================

def _get_recursive_size(obj: object, seen: set[int] | None = None) -> int:
    """
    Recursive helper for sizeof
    :meta private: 
    """
    if seen is None:
        seen = set()  # Keep track of seen objects to avoid double-counting

    # Get the size of the current object
    size = sys.getsizeof(obj)

    # Avoid counting the same object twice
    if id(obj) in seen:
        return 0
    seen.add(id(obj))

    if isinstance( obj, (np.ndarray, pd.DataFrame) ):
        size += obj.nbytes
    elif isinstance(obj, Mapping):
        for key, value in obj.items():
            size += _get_recursive_size(key, seen)
            size += _get_recursive_size(value, seen)
    elif isinstance(obj, Collection):
        for item in obj:
            size += _get_recursive_size(item, seen)
    else:
        try:
            size += _get_recursive_size( obj.__dict__, seen )
        except:
            pass
        try:
            size += _get_recursive_size( obj.__slots__, seen )
        except:
            pass
    return size

def getsizeof(obj : Any) -> int:
    """
    Approximates the size of an object.
    
    In addition to calling :func:`sys.getsizeof` this function
    also iterates embedded containers, numpy arrays, and panda dataframes.
    :meta private: 
    """
    return _get_recursive_size(obj,None)    

def qualified_name( x : Any|None, module : bool|str = False ) -> str:
    """
    Return qualified name including module name of some Python element.
    
    For the most part, this function will try to :func:`getattr` the ``__qualname__``
    and ``__name__`` of ``x`` or its type. If all of these fail, an attempt is
    made to convert ``type(x)`` into a string.
    
    **Class Properties**
    
    When reporting qualified names for a :dec:`property`, there is a nuance:
    at class level, a property will be identified by its underlying function
    name. Once an object is created, though, the property will be identified
    by the return type of the property::
        
        class A(object):
            def __init__(self):
                self.x = 1
            @property
                def p(self):
                    return x

        qualified_name(A.p)    # -> "A.p"
        qualified_name(A().p)  # -> "int"
           
    Parameters
    ----------
        x : Any
            Some Python element.
            
        module : bool | str, default ``False``
            Whether to also return the containing module if available.
            Use a string as separator to append the module name
            to the returned name::
                
                # define in module test.py                
                def f():
                    pass
                
                # in another module
                from test import f
                qualified_name(f,"@") -> f@test
                
    Returns
    -------
        qualified name : str
            The name, if ``module`` is ``False``.
            
        (qualified name, module_name) : tuple
            The name, if ``module`` is ``True``.
            Note that the module name returned might be ``""`` if no module
            name could be determined.
            
        ``{qualified name}{module}{module_name}`` : str
            If ``module`` is a string.
            
    Raises
    ------
        :class:`RuntimeError` if not qualfied name for ``x`` or its type could be found.
    """
    if x is None:
        if isinstance(module, str) or not module:
            return "None"
        else:
            return "None", ""
    
    # special cases
    if isinstance(x, property):
        x = x.fget
    
    name = getattr(x, "__qualname__", None)
    if name is None:
        name = getattr(x, "__name__", None)
    if name is None:
        name = getattr(type(x), "__qualname__", None)
    if name is None:
        name = getattr(type(x), "__name__", None)
    if name is None:
        name = str(type(x))
    if not isinstance(module, str) and not module:
        return name

    mdl = getattr(x, "__module__", None)
    if mdl is None:
        mdl = getattr(type(x), "__module__", "")
    if isinstance(module, str):
        return name + module + mdl
    return name, mdl    

# =============================================================================
# string formatting
# =============================================================================

def fmt_seconds( seconds : float, *, eps : float = 1E-8 ) -> str:
    """
    Generate format string for seconds, e.g. "23s"" for ``seconds=23``, or "1:10" for ``seconds=70``.
    
    Parameters
    ----------
    seconds : float
        Seconds as a float.
        
    eps : float
        anything below ``eps`` is considered zero. Default ``1E-8``.

    Returns
    -------
    Seconds : string
    """
    assert eps>=0., ("'eps' must not be negative")
    if seconds < -eps:
        return "-" + fmt_seconds(-seconds, eps=eps)

    if seconds <= eps:
        return "0s"
    if seconds < 0.01:
        return "%.3gms" % (seconds*1000.)
    if seconds < 2.:
        return "%.2gs" % seconds
    seconds = int(seconds)
    if seconds < 60:
        return "%lds" % seconds
    if seconds < 60*60:
        return "%ld:%02ld" % (seconds//60, seconds%60)
    return "%ld:%02ld:%02ld" % (seconds//60//60, (seconds//60)%60, seconds%60)

def fmt_list( lst : list, *, none : str = "-", link : str = "and", sort : bool = False ) -> str:
    """
    Returns a formatted string of a list, its elements separated by commas and (by default) a final 'and'.
    
    If the list is ``[1,2,3]`` then the function will return ``"1, 2 and 3"``.
    
    Parameters
    ----------
    lst  : list.
        The ``list()`` operator is applied to ``lst``, so it will resolve dictionaries and generators.
    none : str, optional
        String to be used when ``list`` is empty. Default is ``"-"``.
    link : str, optional
        String to be used to connect the last item. Default is ``"and"``.
    sort : bool, optional
        Whether to sort the list. Default is ``False``.

    Returns
    -------
    Text : str
        String.
    """
    if lst is None:
        return str(none)
    lst  = list(lst)
    if len(lst) == 0:
        return none
    if len(lst) == 1:
        return str(lst[0])
    if sort:
        lst = sorted(lst)
    if link=="," or link=="":
        link = ", "
    elif link == "and": # make the default fast
        link = " and "
    elif link[:1] == ",":
        link = ", " + link[1:].strip() + " "
    else:
        link = " " + link.strip() + " "
                
    s    = ""
    for k in lst[:-1]:
        s += str(k) + ", "
    return s[:-2] + link + str(lst[-1])

def fmt_dict( dct : dict, *, sort : bool = False, none : str = "-", link : str = "and" ) -> str:
    """
    Return a readable representation of a dictionary.
    
    This assumes that the elements of the dictionary itself can be formatted well with :func:`str()`.
    
    For a dictionary ``dict(a=1,b=2,c=3)`` this function will return ``"a: 1, b: 2, and c: 3"``.

    Parameters
    ----------
    dct : dict
        The dictionary to format.
    sort : bool, optional
        Whether to sort the keys. Default is ``False``.
    none :  str, optional
        String to be used if dictionary is empty. Default is ``"-"``.
    link : str, optional
        String to be used to link the last element to the previous string. Default is ``"and"``.

    Returns
    -------
    Text : str
        String.
    """
    if len(dct) == 0:
        return str(none)
    if sort:
        keys = sorted(dct)
    else:
        keys = list(dct)
    strs = [ str(k) + ": " + str(dct[k]) for k in keys ]
    return fmt_list( strs, none=none, link=link, sort=False )

def fmt_digits( integer : int, sep : str = "," ):
    """
    String representation of an integer with 1000 separators: 10000 becomes "10,000".
    
    Parameters
    ----------
    integer : int
        The number. The function will :func:`int()` the input which allows
        for processing of a number of inputs (such as strings) but
        might cut off floating point numbers.
        
    sep : str
        Separator; ``","`` by default.

    Returns
    -------
    Text : str
        String.
    """
    if isinstance( integer, float ):
        raise ValueError("float value provided", integer)
    integer = int(integer)
    if integer < 0:
        return "-" + fmt_digits( -integer, sep )
    assert integer >= 0
    if integer < 1000:
        return "%ld" % integer
    else:
        return fmt_digits(integer//1000, sep) + ( sep + "%03ld" % (integer % 1000) )

def fmt_big_number( number : int ) -> str:
    """
    Return a formatted big number string, e.g. 12.35M instead of all digits.
    
    Uses decimal system and "B" for billions.
    Use :func:`cdxcore.util.fmt_big_byte_number` for byte sizes i.e. 1024 units.

    Parameters
    ----------
    number : int
        Number to format.

    Returns
    -------
    Text : str
        String.
    """
    if isinstance( number, float ):
        raise ValueError("float value provided", number)
    if number < 0:
        return "-" + fmt_big_number(-number)
    if number >= 10**13:
        number = number/(10**12)
        
        if number > 10*3:
            intg   = int(number)
            rest   = number - intg
            lead   = fmt_digits(intg)
            rest   = "%.2f" % round(rest,2)
            return f"{lead}{rest[1:]}T"
        else:
            number = round(number,2)
            return "%gT" % number
    if number >= 10**10:
        number = number/(10**9)
        number = round(number,2)
        return "%gB" % number
    if number >= 10**7:
        number = number/(10**6)
        number = round(number,2)
        return "%gM" % number
    if number >= 10**4:
        number = number/(10**3)
        number = round(number,2)
        return "%gK" % number
    return str(number)

def fmt_big_byte_number( byte_cnt : int, str_B : bool = True ) -> str:
    """
    Return a formatted big byte string, e.g. 12.35MB.
    Uses 1024 as base for KB.
    
    Use :func:`cdxcore.util.fmt_big_number` for converting general numbers
    using 1000 blocks instead.

    Parameters
    ----------
    byte_cnt : int
        Number of bytes.
        
    str_B : bool
        If ``True``, return ``"GB"``, ``"MB"`` and ``"KB"`` units.
        Moreover, if ``byte_cnt` is less than 10KB, then this will add ``"bytes"``
        e.g. ``"1024 bytes"``.

        If ``False``, return ``"G"``, ``"M"`` and ``"K"`` only, and do not
        add ``"bytes"`` to smaller ``byte_cnt``.

    Returns
    -------
    Text : str
        String.
    """
    if isinstance( byte_cnt, float ):
        raise ValueError("float value provided", byte_cnt)
    if byte_cnt < 0:
        return "-" + fmt_big_byte_number(-byte_cnt,str_B=str_B)
    if byte_cnt >= 10*1024*1024*1024*1024:
        byte_cnt = byte_cnt/(1024*1024*1024*1024)
        if byte_cnt > 1024:
            intg   = int(byte_cnt)
            rest   = byte_cnt - intg
            lead   = fmt_digits(intg)
            rest   = "%.2f" % round(rest,2)
            s = f"{lead}{rest[1:]}T"
        else:
            byte_cnt = round(byte_cnt,2)
            s = "%gT" % byte_cnt
    elif byte_cnt >= 10*1024*1024*1024:
        byte_cnt = byte_cnt/(1024*1024*1024)
        byte_cnt = round(byte_cnt,2)
        s = "%gG" % byte_cnt
    elif byte_cnt >= 10*1024*1024:
        byte_cnt = byte_cnt/(1024*1024)
        byte_cnt = round(byte_cnt,2)
        s = "%gM" % byte_cnt
    elif byte_cnt >= 10*1024:
        byte_cnt = byte_cnt/1024
        byte_cnt = round(byte_cnt,2)
        s = "%gK" % byte_cnt
    else:
        if byte_cnt==1:
            return "1" if not str_B else "1 byte"
        return str(byte_cnt) if not str_B else f"{byte_cnt} bytes"
    return s if not str_B else s+"B"

def fmt_datetime(dt        : datetime.datetime|datetime.date|datetime.time, *, 
                 sep       : str = ':', 
                 ignore_ms : bool = False,
                 ignore_tz : bool = True
                 ) -> str:
    """
    Convert :class:`datetime.datetime` to a string of the form "YYYY-MM-DD HH:MM:SS".
    
    If present, microseconds are added as digits::
        
        YYYY-MM-DD HH:MM:SS,MICROSECONDS
        
    Optionally a time zone is added via::
        
        YYYY-MM-DD HH:MM:SS+HH
        YYYY-MM-DD HH:MM:SS+HH:MM
        
    Output is reduced accordingly if ``dt`` is a :class:`datetime.time`
    or :class:`datetime.date`.
    
    Parameters
    ----------
    dt : :class:`datetime.datetime`, :class:`datetime.date`, or :class:`datetime.time`
        Input.

    sep : str, optional
        Separator for hours, minutes, seconds. The default ``':'`` is most appropriate for visualization
        but is not suitable for filenames.

    ignore_ms : bool, optional
        Whether to ignore microseconds. Default ``False``.

    ignore_tz : bool, optional
        Whether to ignore the time zone. Default ``True``.

    Returns
    -------
    Text : str
        String.
    """
    if not isinstance(dt, datetime.datetime):
        if isinstance(dt, datetime.date):
            return fmt_date(dt)
        else:
            assert isinstance(dt, datetime.time), "'dt' must be datetime.datetime, datetime.date, or datetime.time. Found %s" % type(dt)
            return fmt_time(dt,sep=sep,ignore_ms=ignore_ms)

    s = fmt_date(dt.date()) + " " +\
        fmt_time(dt.timetz(),sep=sep,ignore_ms=ignore_ms)

    if ignore_tz or dt.tzinfo is None:
        return s

    # time zone handling
    # pretty obscure: https://docs.python.org/3/library/datetime.html#tzinfo-objects
    tzd     = dt.tzinfo.utcoffset(dt)
    assert not tzd is None, ("tzinfo.utcoffset() returned None")
    assert tzd.microseconds == 0, ("Timezone date offset with microseconds found", tzd )
    seconds = tzd.days * 24*60*60 + tzd.seconds
    if seconds==0:
        return s
    sign    = "+" if seconds >= 0 else "-"
    seconds = abs(seconds)
    hours   = seconds//(60*60)
    minutes = (seconds//60)%60
    seconds = seconds%60
    if minutes == 0:
        s += sign + str(hours)
    else:
        s += f"{sign}{hours}{sep}{minutes:02d}"
    return s
    
def fmt_date(dt : datetime.date) -> str:
    """
    Returns string representation for a date of the form "YYYY-MM-DD".
    
    If passed a :class:`datetime.datetime`, it will format its :func:`datetime.datetime.date`.
    """
    if isinstance(dt, datetime.datetime):
        dt = dt.date()
    assert isinstance(dt, datetime.date), "'dt' must be :class:`datetime.date`. Found %s" % type(dt)
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"

def fmt_time(dt        : datetime.time, *,
             sep       : str = ':',
             ignore_ms : bool = False
             ) -> str:
    """
    Convers a time to a string with format "HH:MM:SS".
    
    Microseconds are added as digits::

        HH:MM:SS,MICROSECONDS
        
    If passed a :class:`datetime.datetime`, then this function will format
    only its :func:`datetime.datetime.time` part.

    **Time Zones**
    
    Note that while :class:`datetime.time` objects may carry a ``tzinfo`` time zone object,
    the corresponding :func:`datetime.time.utcoffset` function returns ``None`` if we do not
    provide a ``dt`` parameter, see
    `tzinfo documentation <https://docs.python.org/3/library/datetime.html#tzinfo-objects>`__.
    That means :func:`datetime.time.utcoffset` is only useful if we have :class:`datetime.datetime`
    object at hand. 
    That makes sense as a time zone can change date as well.
    
    We therefore here do not allow ``dt`` to contain
    a time zone.
        
    Use :func:`cdxcore.util.fmt_datetime` for time zone support
        
    Parameters
    ----------
    dt : :class:`datetime.time`
        Input.
    sep : str, optional
    
        Separator for hours, minutes, seconds. The default ``':'`` is most appropriate for visualization
        but is not suitable for filenames.
        
    ignore_ms : bool
        Whether to ignore microseconds. Default is ``False``.
            
    Returns
    -------
    Text : str
        String.
    """
    if isinstance(dt, datetime.datetime):
        dt = dt.timetz()
 
    assert isinstance(dt, datetime.time), "'dt' must be datetime.time. Found %s" % type(dt)
    if ignore_ms or dt.microsecond == 0:
        return f"{dt.hour:02d}{sep}{dt.minute:02d}{sep}{dt.second:02d}"
    else:
        return f"{dt.hour:02d}{sep}{dt.minute:02d}{sep}{dt.second:02d},{dt.microsecond}"  

def fmt_timedelta(dt      : datetime.timedelta, *,
                  sep     : str = "" )  -> str:
    """
    Returns string representation for a time delta in the form "DD:HH:MM:SS,MS".
    
    Parameters
    ----------
    dt : :class:`datetime.timedelta`
        Timedelta.
        
    sep :
        Identify the three separators: between days, and HMS and between microseconds:
        
        .. code-block:: python

            DD*HH*MM*SS*MS
              0  1  1  2

        * ``sep`` can be a string, in which case:
            * If it is an empty string, all separators are ``''``.
            * A single character will be reused for all separators.
            * If the string has length 2, then the last character is used for ``'2'``.
            * If the string has length 3, then the chracters are used accordingly.

        * ``sep`` can also be a collection ie a ``tuple`` or ``list``. In this case each element is used accordingly.
            
    Returns
    -------
    Text : str
        String with leading sign. Returns "" if ``timedelta`` is 0.
    """
    assert isinstance(dt, datetime.timedelta), "'dt' must be datetime.timedelta. Found %s" % type(dt)

    if isinstance(sep, str):
        if len(sep) == 0:
            sepd   = ''
            sephms = ''
            sepms  = ''
        elif len(sep) == 1:
            sepd   = sep
            sephms = sep
            sepms  = sep
        elif len(sep) == 2:
            sepd   = sep[0]
            sephms = sep[0]
            sepms  = sep[-1]
        else:
            if len(sep) != 3: raise ValueError(f"'sep': if a string is provided, its length must not exceed 3. Found '{sep}'")
            sepd   = sep[0]
            sephms = sep[1]
            sepms  = sep[2]
    elif isinstance(sep, Collection):
        if len(sep) != 3: raise ValueError("'sep': if a collection is provided, it must be of length 3")
        sepd   = str( sep[0] ) if not sep[0] is None else ""
        sephms = str( sep[1] ) if not sep[1] is None else ""
        sepms  = str( sep[2] ) if not sep[2] is None else ""

    microseconds = (dt.seconds + dt.days*24*60*60)*1000000+dt.microseconds
    if microseconds==0:
        return ""
    
    sign         = "+" if microseconds >= 0 else "-"
    microseconds = abs(microseconds)

    if microseconds < 1000000:
        return f"{sign}{microseconds}ms"
        
    seconds      = microseconds//1000000
    microseconds = microseconds%1000000
    rest         = "" if microseconds == 0 else f"{sepms}{microseconds}ms"

    if seconds < 60:        
        return f"{sign}{seconds}s{rest}"
    
    minutes      = seconds//60
    seconds      = seconds%60   
    rest         = rest if seconds==0 else f"{sephms}{seconds}s{rest}"
    if minutes < 60:
        return f"{sign}{minutes}m{rest}"

    hours        = minutes//60
    minutes      = minutes%60
    rest         = rest if minutes==0 else f"{sephms}{minutes}m{rest}"
    if hours <= 24:        
        return f"{sign}{hours}h{rest}"

    days         = hours//24
    hours        = hours%24
    rest         = rest if hours==0 else f"{sepd}{hours}h{rest}"
    return f"{sign}{days}d{rest}"

def fmt_now() -> str:
    """ Returns the :func:`cdxcore.util.fmt_datetime` applied to :func:`datetime.datetime.now` """
    return fmt_datetime(datetime.datetime.now())

DEF_FILE_NAME_MAP = {  
                 '/' : "_",
                 '\\': "_",
                 '|' : "_",
                 ':' : ";",
                 '>' : ")",
                 '<' : "(",
                 '?' : "!",
                 '*' : "@",
                 }
"""
Default map from characters which cannot be used for filenames under either
Windows or Linux to valid characters.
"""

def fmt_filename( filename : str , by : str | Mapping = "default" ) -> str:
    r"""
    Replaces invalid filename characters such as ``\\``, ``:``, or ``/`` by a different character.
    The returned string is technically a valid file name under both Windows and Linux.
    
    However, that does not prevent the filename to be a reserved name, for example "." or "..".
    
    Parameters
    ----------
    filename : str
        Input string.
        
    by : str | Mapping, optional.
        A dictionary of characters and their replacement.
        The default value ``"default"`` leads to using :data:`cdxcore.util.DEF_FILE_NAME_MAP`.
    
    Returns
    -------
    Text : str
        Filename
    """
    if not isinstance(by, Mapping):
        if not isinstance(by, str):
            raise ValueError(f"'by': must be a Mapping or 'default'. Found type {type(by).__qualname__}")
        if by != "default":
            raise ValueError(f"'by': must be a Mapping or 'default'. Found string '{by}'")                            
        by = DEF_FILE_NAME_MAP

    for c, cby in by.items():
        filename = filename.replace(c, cby)
    return filename
fmt_filename.DEF_FILE_NAME_MAP = DEF_FILE_NAME_MAP

def is_filename( filename : str , by : str | Collection = "default" ) -> bool:
    """
    Tests whether a filename is indeed a valid filename.

    Parameters
    ----------
    filename : str
        Supposed filename.
        
    by : str | Collection, optional
        A collection of invalid characters.
        The default value ``"default"`` leads to using
        they keys of :data:`cdxcore.util.DEF_FILE_NAME_MAP`.
    
    Returns
    -------
    Validity : bool
        ``True`` if ``filename`` does not contain any invalid characters contained in ``by``.
    """
    
    if not isinstance(by, Mapping):
        if not isinstance(by, str):
            raise ValueError(f"'by': must be a Mapping or 'default'. Found type {type(by).__qualname__}")
        if by != "default":
            raise ValueError(f"'by': must be a Mapping or 'default'. Found string '{by}'")                            
        by = DEF_FILE_NAME_MAP

    for c in by:
        if c in filename:
            return False
    return True

def expected_str_fmt_args(fmt: str) -> Mapping:
    """
    Inspect a ``{}`` Python format string and report what arguments it expects.
    
    Returns
    -------
        Information : Mapping
            A dictionary containing:
                
            * ``auto_positional``: count of'{}' fields
            * ``positional_indices``: explicit numeric field indices used (e.g., ``{0}``, ``{2}``)
            * ``keywords``: named fields used (e.g., ``{user}``, ``{price:.2f}``)
    """
    f = Formatter()
    pos = set()
    auto = 0
    kws = set()

    for literal, field, spec, conv in f.parse(fmt):
        if field is None:
            continue
        # Keep only the first identifier before attribute/index access
        head = field.split('.')[0].split('[')[0]
        if head == "":               # '{}' → automatic positional
            auto += 1
        elif head.isdigit():         # '{0}', '{2}' → explicit positional
            pos.add(int(head))
        else:                        # '{name}' → keyword
            kws.add(head)

    from cdxcore.pretty import PrettyObject# avoid loop imports
    return PrettyObject( positional=auto,
                         posindices=pos,
                         keywords=kws
                       )

class ActiveFormat( object ):
    """
    Format as a string or callable.
    
    This class allows a user to specify a format string either by a Python :func:`str.format` string
    or a ``Callable``.
    
    Example::
        
        from cdxcore.util import ActiveFormat
        
        fmt = ActiveFormat("{x:.2f}", "test format" )
        print( fmt(x=1) )

        fmt = ActiveFormat(lambda x : f"{x:.2f}", "test format" )
        print( fmt(x=1) )
        
    The advantage of using the ``lambda x : {x:.2f}`` method is that it allows 
    fairly complex formatting and data expressions at the formatting stage.

    Parameters
    ----------
    fmt : str | Callable
            Either a Python :func:`str.format` string containing ``{}`` for formatting, or a callable which returns a string.
            
        label : str, default ``Format string``
            A descriptive string for error messages referring the format string, typically in the format
            ``f{which} '{fmt}' cannot have positional arguments...``
            
        name : str | None, default ``None``
            A name for the formatting string. If not provided, the name will be auto-generated: If ``fmt`` is a string, this string will be used;
            if ``fmt`` is a callable then :func:`cdxcore.util.qualified_name` is used.
            
        reserved_keywords : dict | None, default ``None``
            Mechanism for defining default keywords which are provided by the environment, not the user.
            For example::
                
                from cdxcore.util import ActiveFormat
                
                fmt = ActiveFormat("{name} {x:.2f}", "test format", reserved_keywords=dict(name="test") )
                print( fmt(x=1) )
                
        strict : bool, default ``False``
            If ``False`` this function does not validate that all arguments passed to :meth:`cdxcore.util.ActiveFormat.__call__`
            have to be understood by the formatting function. This is usally the best solution as the calling entity
            just passes everything and the formatter selects what it needs.
            
            Set to ``True`` to validate that the passed arguments match exactly the expected arguments.
    """            
    
    def __init__(self, fmt : str|Callable, label : str = "Format string", name : str|None = None, reserved_keywords : Mapping|None = None, strict : bool = False ) -> None:
        """ __init__ """        
        verify_inp( not fmt is None, "'fmt' cannot be None")

        if isinstance( fmt, str ):
            r = expected_str_fmt_args( fmt )
            if r.positional + len(r.posindices) > 0:
                raise ValueError("f{label}: '{fmt}' cannot have positional arguments (empty brackets {} or brackets with integer position {1}). Use only named arguments.")
            r = list(r.keywords)
            n = fmt if name is None else name
        else:
            if not inspect.isfunction(fmt) and not inspect.ismethod(fmt):
                if not callable(fmt):
                    raise ValueError(f"{label}: '{qualified_name(fmt,'@')}' is not callable")
                fmt = fmt.__call__
                assert inspect.isfunction(fmt) or inspect.ismethod(fmt), ("Internal error - function or method expected", fmt, type(fmt))
            r = list( inspect.signature(fmt).parameters )
            n = qualified_name(fmt,"@") if name is None else name
            assert not n is None and not n == "None", ("None?", n, n is None, qualified_name(fmt,"@"), fmt)

        self.label   = label      # a descriptive name for the meaning of the formatting string or function for error messages
        self.name    = n          # a descriptive name for the formatting string or function itself, by default the string if it is a string, or the qualified name if not.
            
        self._fmt    = fmt 
        self._strict = strict
        self._required_all_arguments = r if len(r) > 0 else None # list of arguments this string or function expects
        self._reserved_keywords     = reserved_keywords if not reserved_keywords is None else dict()
        
    @property
    def is_simple_str(self) -> bool:
        """ Whether the current object represents a string which does not require any arguments """
        return  self._required_all_arguments is None
        
    def __str__(self) -> str:
        return f"ActiveFormat({self.label}:{self.name})({fmt_list(sorted(self._required_all_arguments))})"
    
    @property
    def required_arguments(self) -> set:
        """ Returns a set of arguments ``__call__`` needs to format. This excludes ``reserved_keywords``. """
        if self._required_all_arguments is None:
            return set()
        return set(self._required_all_arguments) - set(self._reserved_keywords)

    def __call__( __self__call__, **arguments ) -> str:
        """
        Execute the format string.
        
        Parameters
        ----------
        arguments : Mapping
            All arguments to be passed to the format string or function.

            If this object was constructed with ``strict=True`` then the list of arguments
            must match :attr:`cdxcore.util.ActiveFormat.required_arguments` except for
            :attr:`cdxcore.util.ActiveFormat.reserved_keywords`.

        Returns
        -------
        text : str
            Formatted string.
        """
        self = __self__call__ # ugly way of enuring that 'self' can be part of the arguments
        if self._strict:
            excess  = set(arguments) - self.required_arguments
            if len(excess) > 0:
                excess = sorted(excess)
                raise ValueError(f"'{self.label}': formatting function '{self.name}' does not require arguments {fmt_list(excess)}")
        
        if self._required_all_arguments is None:
            # label function or string does not need any parameters
            return self._fmt if isinstance( self._fmt, str ) else self.fmt()
            
        fmt_arguments = {}
        for k in self._required_all_arguments:
            if k in self._reserved_keywords:
                value   = self._reserved_keywords[k]
                if k in arguments:
                    error(f"{self.label}: '{k}' is a reserved keyword with value '{str(value)}'. "+\
                          f"You cannot use it in the explicit parameter list for '{self.name}'.")
                fmt_arguments[k] = value
            else:
                if not k in arguments:  
                    args_ = [ f"'{_}'" for _ in arguments ]
                    raise ValueError(f"'{self.label}': formatting function '{self.name}' expected a parameter '{k}' which is not present "+\
                                     f"in the list of parameters: {fmt_list(args_)}.")
                fmt_arguments[k] = arguments[k]

        # call format or function                    
        if isinstance( self._fmt, str ):
            return str.format( self._fmt, **fmt_arguments )

        try:
            r = self._fmt(**fmt_arguments)
        except Exception as e:
            raise type(e)(f"'{self.label}': attempt to call '{self.name}' of type {type(self._fmt)} failed: {e}")
        if not isinstance(r, str):
            raise ValueError(f"'{self.label}': the callable '{self.name}' must return a string. Found {type(r) if not r is None else None}")
        return r
    
# =============================================================================
# Conversion of arbitrary python elements into re-usable versions
# =============================================================================

def plain( inn, *, sorted_dicts : bool = False,
                   native_np    : bool = False,
                   dt_to_str    : bool = False):
    """
    Converts a python structure into a simple atomic/list/dictionary collection such
    that it can be read without the specific imports used inside this program.

    For example, objects are converted into dictionaries of their data fields.

    Parameters
    ----------
    inn :
        some object.
    sorted_dicts : bool, optional
        use SortedDicts instead of dicts. Since Python 3.7 all dictionaries are sorted anyway.
    native_np : bool, optional
        convert numpy to Python natives.
    dt_to_str : bool, optional
        convert dates, times, and datetimes to strings.

    Returns
    -------
    Text : str
        Filename
    """
    def rec_plain( x ):
        return plain( x, sorted_dicts=sorted_dicts, native_np=native_np, dt_to_str=dt_to_str )
    # basics
    if is_atomic(inn) or inn is None:
        return inn
    if isinstance(inn,(datetime.time,datetime.date,datetime.datetime)):
        return fmt_datetime(inn) if dt_to_str else inn
    if not np is None:
        if isinstance(inn,np.ndarray):
            return inn if not native_np else rec_plain( inn.tolist() )
        if isinstance(inn, np.integer):
            return int(inn)
        elif isinstance(inn, np.floating):
            return float(inn)
    # can't handle functions --> return None
    if is_function(inn) or isinstance(inn,property):
        return None
    # dictionaries
    if isinstance(inn,Mapping):
        r  = { k: rec_plain(v) for k, v in inn.items() if not is_function(v) and not isinstance(v,property) }
        return r if not sorted_dicts else SortedDict(r)
    # pandas
    if not pd is None and isinstance(inn,pd.DataFrame):
        rec_plain(inn.columns)
        rec_plain(inn.index)
        rec_plain(inn.to_numpy())
        return
    # lists, tuples and everything which looks like it --> lists
    if isinstance(inn,Collection):
        return [ rec_plain(k) for k in inn ]
    # handle objects as dictionaries, removing all functions
    if not getattr(inn,"__dict__",None) is None:
        return rec_plain(inn.__dict__)
    # nothing we can do
    raise TypeError(fmt("Cannot handle type %s", type(inn)))

# =============================================================================
# Misc Jupyter
# =============================================================================

def is_jupyter() -> bool:
    """
    Whether we operate in a jupter session.
    Somewhat unreliable function. Use with care.
    
    :meta private: 
    """
    parent_process = psutil.Process().parent().cmdline()[-1]
    return  'jupyter' in parent_process

# =============================================================================
# Timer
# =============================================================================

class TrackTime(object):
    """
    Track execution time and sub-topic timings.

    The timer keeps a running total of elapsed seconds and can record *laps*.
    Each lap updates the timer's internal reference time (so subsequent laps measure time since
    the previous :meth:`cdxcore.util.TrackTime.lap_time` call).

    You can also record lap time under a named sub topic. Sub topics are stored as a dictionary
    of child ``TrackTime`` instances and can be accessed via ``timer["topic"]``.

    Deterministic testing is supported by overriding the class attribute :attr:`cdxcore.util.TrackTime.TIMER`
    with a callable that returns the "current" time in seconds. In normal usage, leave it at its
    default (:func:`time.time`).

    **Examples**
    
    Basic usage with laps::

        from cdxcore.util import TrackTime
        import time

        t = TrackTime("work")
        time.sleep(0.1)
        t.lap_time()
        time.sleep(0.1)
        t.lap_time()
        print(t.seconds) # -> around 0.2

    Track two alternating sub topics::

        t = TrackTime("work")
        for _ in range(10):
            # ... do task 1 ...
            t.lap_time("t1")
            # ... do task 2 ...
            t.lap_time("t2")
        print(t["t1"].average_lap_seconds)
        print(t["t2"].average_lap_seconds)

    Time a block using a sub topic as a context manager::

        with t("io"):
            # ... do IO ...
            pass

    Notes
    -----
    - :attr:`cdxcore.util.TrackTime.seconds` is the total elapsed seconds for this timer up to current time, if the time is running. Call :meth:`cdxcore.util.TrackTime.stop` to stop it.
    - :attr:`cdxcore.util.TrackTime.count` is the number of recorded laps/updates for this timer.

    Parameters
    ----------

    topic : str | TrackTime | None, default ``None``
        Name of the timer topic. If ``None`` this function will attempt to determine the name of the calling function and use it as topic name.
        If a ``TrackTime`` object is passed, a deep copy will be made.

    start : bool | None, default ``True``
        Whether to start the timer immediately. If ``False``, the timer will remain stopped until :meth:`cdxcore.util.TrackTime.start` is called.
        Use ``None`` to keep the same start state as the passed ``TrackTime`` object. If ``None`` and no ``TrackTime`` object is passed, the timer will start immediately.

    elapsed_seconds : float | None, default ``None``
        If not ``None``, this is the initial number of seconds to start with. This can be used to create a timer which starts with some pre-recorded time.    
        If not ``None``, this sets the internal lap count to 1, otherwise it is set to 0.
    """

    TIMER: Callable[[], float] = time.time
    """Callable used to compute current time in seconds.

    Defaults to :func:`time.time`. For deterministic tests, assign a custom callable to
    :attr:`cdxcore.util.TrackTime.TIMER` such as :class:`cdxcore.util.DebugTime`.
    """

    def __init__(
        self,
        topic: str|TrackTime|None = None,
        start: bool|None = None,
        *,
        elapsed_seconds: float | None = None,
    ) -> None:
        if isinstance(topic, TrackTime):
            # Create a deep copy of the topic
            self._subs:dict[str, TrackTime] = { s: TrackTime(t,start=None) for s,t in topic._subs.items() }
            self._topic: str = topic._topic
            self._ref: float | None = topic._ref
            self._offset: float = topic._offset + ( elapsed_seconds if not elapsed_seconds is None else 0.)
            self._count: int = topic._count + ( 1 if not elapsed_seconds is None else 0 )
            if not start is None:
               self._ref = self.time() if start else None  # reference time; None if stopped
            return

        topic = topic if topic is not None else get_calling_function_name("TrackTime")
        self._subs: dict[str, TrackTime] = {}  # hierarchy of sub-topics
        self._topic: str = str(topic)
        self._ref: float | None = self.time() if (start is None or start) else None  # reference time; None if stopped
        self._offset: float = 0.0 if elapsed_seconds is None else float(elapsed_seconds)
        self._count: int = 0 if elapsed_seconds is None else 1

    def time(self) -> float:
        """Return current time in seconds.

        This calls :attr:`cdxcore.util.TrackTime.TIMER`, which defaults to :func:`time.time`.
        """
        return float(self.TIMER())

    def __str__(self) -> str:
        """ Print representation of self """
        return f"{self._topic} {self.fmt_seconds()}"
    
    @property
    def topic(self) -> str:
        """ Returns the current topic """
        return self._topic
    
    @property
    def has_sub_topics(self)-> bool:
        """ Whether this timer has sub topics. """
        return len(self._subs) > 0
    
    @property
    def is_stopped(self) -> bool:
        """ Whether the timer is stopped """
        return self._ref is None

    @property
    def count(self) -> int:
        """ How many laps were recorded (how many times seconds were added to this timer) """
        return self._count
    
    @property
    def reference_time(self) -> float|None:
        """ Returns the reference time since when progress is measured, or ``None`` if the current timer is stopped """
        return self._ref

    def add_time(self, seconds: float) -> None:
        """ Manual lap count: Add ``seconds`` to this timer's accumulated time and increment :attr:`count`. """
        self._offset += float(seconds)
        self._count += 1

    def start(self) -> None:
        """Start the timer if it is currently stopped."""
        if self._ref is None:
            self._ref = self.time() 

    def stop(self, record_lap : bool = True) -> float:
        """ Stops the timer, records a lap if ``record_lap`` is ``True``, and returns seconds elapsed so far """
        if not self._ref is None and record_lap:
            self.add_time( self.time() - self._ref )
        self._ref = None
        return self._offset

    def lap_time(self, sub_topic: str | None = None) -> float | None:
        """
        Record the elapsed time since the last lap and reset the lap reference time to "now".
        
        This computes the seconds elapsed since :attr:`cdxcore.util.TrackTime.reference_time`, adds them to this timer,
        resets the reference time to "now", and returns the elapsed seconds.
        
        If ``sub_topic`` is provided, the same elapsed seconds are also recorded into the sub topic timer
        ``self[sub_topic]``.

        Example::

            from cdxcore.util import TrackTime
            import time
            
            tt = TrackTime("f")
            for i in range(3):
                time.sleep(1)
                tt.lap_time()
            print(tt.average_lap_seconds) # -> around 1

       This function can also be used to track lap time for sub topics::
       
            from cdxcore.util import TrackTime
            import time

            tt = TrackTime("f")
            for i in range(5):
                time.sleep(1)
                tt.lap_time("t1")

                time.sleep(0.2)
                tt.lap_time("t2")

            print(tt["t1"].average_lap_seconds) # -> around 1
            print(tt["t2"].average_lap_seconds) # -> around 0.2
            print(tt.seconds) # -> around 6
            print(tt.count) # == 10
       
        Parameters
        ----------
        sub_topic : str | None, default ``None``
            Sub topic to store the elapsed seconds under, or ``None`` to only update this timer.

        Returns
        -------
        seconds : float | None
            The elapsed seconds since the last lap, or ``None`` if the timer is stopped and no
            recording is requested.
        """
        if self.is_stopped:
            if sub_topic is None:
                return None
            raise ValueError(f"Cannot record '{sub_topic}': current topic '{self._topic}' is stopped")
            
        tm           = self.time() 
        seconds      = tm -self._ref
        self._ref    = tm
        self.add_time( seconds )

        if not sub_topic is None:
            self.record( sub_topic, seconds )

        return seconds

    def record( self, sub_topic : str, seconds : float ) -> TrackTime:
        """
        Manually record ``seconds`` a sub topic, and increase the lap count for the sub topic. Does not increment ``self``.
        Returns the associated sub timer. If a new timer is created, it will be in stopped mode.

        Use :meth:`cdxcore.util.TrackTime.lap_time` instead to record the seconds elapsed since :attr:`cdxcore.util.TrackTime.reference_time`
        for a sub topic.
        """
        tt = self._subs.get(sub_topic, None)
        if tt is None:
            tt = TrackTime( sub_topic, start=False, elapsed_seconds=seconds  )
            self._subs[sub_topic] = tt
        else:
            tt.add_time( seconds )
        return tt
    
    @property
    def seconds(self) -> float:
        """Total elapsed seconds since construction, including current time since last lap reference time if the timer is running. """
        return self._offset if self._ref is None else ( self._offset + self.time()  -self._ref )

    @property
    def lap_seconds(self) -> float:
        """
        Total seconds recorded for all laps, *excluding* the currently running time.

        For example::

            from cdxcore.util import TrackTime
            import time

            tt = TrackTime()
            time.sleep(1)
            tt.lap_time()
            time.sleep(1)
            tt.lap_time()
            time.sleep(1)
            print( tt.lap_seconds ) # -> around 2 NOT 3
        """
        return self._offset

    @property
    def average_lap_seconds(self) -> float|None:
        """
        Average lap seconds added to this timer *excluding* the current running lap if the timer is running.

        That means::

            from cdxcore.util import TrackTime
            import time

            tt = TrackTime()
            time.sleep(1)
            tt.lap_time()
            time.sleep(2)
            print( tt.average_lap_seconds ) # -> 1 not 1.5
        """
        return None if self.count == 0 else ( float(self.lap_seconds) / float(self.count) )
    
    def fmt_seconds(self) -> str:
        """
        A human readable string for :attr:`cdxcore.util.TrackTime.seconds`, e.g. "1s" or "3:21"
        computed using :func:`cdxcore.util.fmt_seconds`. This includes time until now if the
        timer was not stopped.
        """
        return fmt_seconds(self.seconds)

    def fmt_lap_seconds(self) -> str:
        """
        A human readable string for :attr:`cdxcore.util.TrackTime.lap_seconds`, e.g. "1s" or "3:21"
        computed using :func:`cdxcore.util.fmt_seconds`. This only counts full laps, not any currently running lap/interval.
        """
        return fmt_seconds(self.lap_seconds)

    def fmt_average_lap_seconds(self) -> str:
        """
        A human readable string for :attr:`cdxcore.util.TrackTime.average_lap_seconds`, e.g. "1s" or "3:21"
        computed using :func:`cdxcore.util.fmt_seconds`.
        """
        return fmt_seconds(self.average_lap_seconds)

    def __call__(self, sub_topic, start : bool = True) -> TrackTime:
        """
        Get or create a timed sub topic.

        The returned object is a :class:`cdxcore.util.TrackTime` and can be used as a context manager.

        Example::

            from cdxcore.util import TrackTime
            tt = TrackTime()

            with tt("io"):
                # ... do IO ...
                pass
                
            with tt("processing") as pt:
                # ... do processing ...
                with pt("subprocessing") as spt:
                    # ... do sub processing ...
                    pass    
                pass

        Parameters
        ----------
        sub_topic : str
            Name of the sub topic to get or create. If the sub topic does not exist, it is created and returned.

        start : bool, default ``True``
            Whether to start the sub topic timer immediately. If ``False``, the sub topic timer 
            will remain stopped until :meth:`cdxcore.util.TrackTime.start` is called on it.

        Returns
        -------
            sub_timer : :class:`cdxcore.util.TrackTime`
                The timer for the sub topic. If the sub topic does not exist, it is created and returned. If it already exists, it is returned as is.   

        Raises
        ------
            In use: :class:`KeyError`
                If a sub topic is currently running (i.e. is not :meth:`cdxcore.util.TrackTime.is_stopped`), a :class:`KeyError` is raised.                
        """
        
        tt = self._subs.get(sub_topic, None)
        if tt is None:
            tt = TrackTime( sub_topic, start=start )
            self._subs[sub_topic] = tt
        else:
            if not tt.is_stopped:
                raise KeyError(sub_topic, f"Sub-topic '{sub_topic}' of '{self._topic}' is in use")
            if start:
                tt.start()
        return tt

    def __enter__(self) -> TrackTime:
        """
        Start a context manager to track timing for this topic.
        This function starts the timer.
        """
        self.start()
        return self
        
    def __exit__(self, *args, **kwargs) -> bool:
        self.stop()
        return False

    # mimic a dictionary
    # ------------------
    
    def values(self) -> Iterator:
        """ :meth:`dict.values` for the dictionary of sub topics """
        return self._subs.values()
    def keys(self) -> Iterator:
        """ :meth:`dict.keys` for the dictionary of sub topics """
        return self._subs.keys()
    def items(self) -> Iterator:
        """ :meth:`dict.items` for the dictionary of sub topics """
        return self._subs.items()
    def __getitem__(self, sub_topic : str) -> TrackTime:
        return self._subs[sub_topic]

    def get(self, sub_topic: str, default: float | TrackTime | None = None, *, clone_default : bool = True ) -> TrackTime | None:
        """
        Return sub topic timer if present; otherwise create it from ``default``.

        Parameters
        ----------
        sub_topic : str
            Sub topic name.

        default : float | TrackTime | None, default ``None``
            - If a :class:`cdxcore.util.TrackTime` instance, it will be inserted and returned.
            - If a ``float``, a stopped sub timer with that initial elapsed seconds is created.
            - If ``None``, this returns ``None``.

        clone_default: bool, default ``True``
            If ``True`` and ``default`` is a :class:`cdxcore.util.TrackTime`, a clone of it is created for the sub topic.
            Otherwise, the same instance is used.
    
        Returns
        -------
            sub_timer : :class:`cdxcore.util.TrackTime` | None
                The sub topic timer if it exists, or if it was created from ``default``; otherwise ``None``.   
        """
        tt = self._subs.get(sub_topic, None)
        if tt is not None:
            return tt
        if isinstance(default, TrackTime):
            if clone_default:
                default = TrackTime(default, start=None)
            self._subs[sub_topic] = default
            return default
        if default is None:
            return None
        tt = TrackTime(sub_topic, start=False, elapsed_seconds=float(default))
        self._subs[sub_topic] = tt
        return tt
    
    def add(self, timer : TrackTime | float) -> TrackTime:
        """
        Add the seconds of another timer including its sub topics to this timer.
        This does not change the other timer.

        Returns ``self`` for chaining.
        """
        
        if not isinstance(timer, TrackTime):
            self.add_time(float(timer))
            return self

        def recurse( to, frm ):
            to._offset += frm._offset
            to._count  += frm._count
            for sub_topic, sub_frm in frm.items():
                sub_to = to.get(sub_topic, None)
                if sub_to is None:
                    to._subs[sub_topic] = TrackTime(sub_frm, start=None)
                else:
                    recurse(sub_to, sub_frm)

        recurse(self,timer)
        return self
    
    def __iadd__(self, timer : TrackTime | float) -> None:
        """ In-place addition of another timer or seconds to this timer. """
        return self.add(timer)

    def __add__(self, timer : TrackTime | float) -> TrackTime:
        """ Addition of another timer or seconds to this timer. """
        me = TrackTime(self, start=None)
        me += timer
        return me

class DebugTime(object):
    """ Simple object that counts the number of times ``__call__`` was called. Used for writing tests for :class:`cdxcore.util.TrackTime` """
    def __init__(self, init : float = 0.):
        self.cnt = init
    def __call__(self) -> float:
        return self.cnt
    def __iadd__(self, add : float):
        self.cnt += add
        return self
    def sleep(self, add : float):
        """ Increment 'time' by ``add`` seconds. """
        self.cnt += add
    def time(self) -> float:
        """ Return current 'time' """
        return self.cnt

class Timer(object):
    """
    Micro utility to measure passage of time.

    Example::

        from cdxcore.util import Timer
        with Timer() as t:
            .... do somthing ...
            print(f"This took {t}.")
    """
    
    def __init__(self) -> None:
        self.time = time.time()
        self.intv = None
        
    def reset(self):
        """ Resets the timer. """
        self.time = time.time()
        self.intv = None
        
    def __enter__(self):
        self.reset()
        return self
    
    def __str__(self):
        """
        Seconds elapsed since construction or :meth:`cdxcore.util.Timer.reset`,
        formatted using :func:`cdxcore.util.Timer.fmt_seconds`
        """
        return self.fmt_seconds
    
    def interval_test( self, interval : float ) -> bool:
        r"""
        Tests if ``interval`` seconds have passed.
        If yes, reset timer and return True. Otherwise return False.
        
        Usage::
            
            from cdxcore.util import Timer
            tme = Timer()
            for i in range(n):
                if tme.test_dt_seconds(2.):
                    print(f"\\r{i+1}/{n} done. Time taken so far {tme}.", end='', flush=True)
            print("\\rDone. This took {tme}.")

        """
        if interval is None:
            self.intv = self.seconds
            return True
        if self.intv is None:
            self.intv = self.seconds
            return True
        if self.seconds - self.intv > interval:
            self.intv = self.seconds
            return True
        return False            

    @property
    def fmt_seconds(self):
        """
        Seconds elapsed since construction or :meth:`cdxcore.util.Timer.reset`, formatted using :func:`cdxcore.util.fmt_seconds`
        """
        return fmt_seconds(self.seconds)

    @property
    def seconds(self) -> float:
        """ Seconds elapsed since construction or :meth:`cdxcore.util.Timer.reset` """
        return time.time() - self.time

    @property
    def minutes(self) -> float:
        """ Minutes passed since construction or :meth:`cdxcore.util.Timer.reset` """
        return self.seconds / 60.

    @property
    def hours(self) -> float:
        """ Hours passed since construction or :meth:`cdxcore.util.Timer.reset` """
        return self.minutes / 60.

    def __exit__(self, *kargs, **wargs):
        return False

# =============================================================================
# Printing support
# =============================================================================

class CRMan(object):
    r"""
    Carriage Return ("\\r") manager.    
    
    This class is meant to enable efficient per-line updates using "\\r" for text output with a focus on making it work with both Jupyter and the command shell.
    In particular, Jupyter does not support the ANSI `\\33[2K` 'clear line' code. To simulate clearing
    lines, ``CRMan`` keeps track of the length of the current line, and clears it by appending spaces to a message
    following "\\r"
    accordingly.
                                                         
    *This functionality does not quite work accross all terminal types which were tested. Main focus is to make
    it work for Jupyer for now. Any feedback on
    how to make this more generically operational is welcome.*
    
    .. code-block:: python

        crman = CRMan()
        print( crman("\rmessage 111111"), end='' )
        print( crman("\rmessage 2222"), end='' )
        print( crman("\rmessage 33"), end='' )
        print( crman("\rmessage 1\n"), end='' )
    
    prints::
        
        message 1     
    
    While
    
    .. code-block:: python

        print( crman("\rmessage 111111"), end='' )
        print( crman("\rmessage 2222"), end='' )
        print( crman("\rmessage 33"), end='' )
        print( crman("\rmessage 1"), end='' )
        print( crman("... and more.") )
        
    prints

    .. code-block:: python
    
        message 1... and more
    """
    
    def __init__(self) -> None:
        """
        See :class:`cdxcore.crman.CRMan`               
        :meta private:
        """
        self._current = ""
        
    def __call__(self, message : str) -> str:
        r"""
        Convert `message` containing "\\r" and "\\n" into a printable string which ensures
        that a "\\r" string does not lead to printed artifacts.
        Afterwards, the object will retain any text not terminated by "\\n".
        
        Parameters
        ----------
        message : str
            message containing "\\r" and "\\n".
            
        Returns
        -------
        Message: str
            Printable string.
        """
        if message is None:
            return

        lines  = message.split('\n')
        output = ""
        
        # first line
        # handle any `current` line
        
        line   = lines[0]
        icr    = line.rfind('\r')
        if icr == -1:
            line = self._current + line
        else:
            line = line[icr+1:]
        if len(self._current) > 0:
            # print spaces to clear current line in terminals which do not support \33[2K'
            output    += '\r' + ' '*len(self._current) + '\r' + '\33[2K' + '\r'
        output        += line
        self._current = line
            
        if len(lines) > 1:
            output       += '\n'
            self._current = ""
            
            # intermediate lines
            for line in lines[1:-1]:
                # support multiple '\r', but in practise only the last one will be printed
                icr    =  line.rfind('\r')
                line   =  line if icr==-1 else line[icr+1:]
                output += line + '\n'
                
            # final line
            # keep track of any residuals in `current`
            line      = lines[-1]
            if len(line) > 0:
                icr           = line.rfind('\r')
                line          = line if icr==-1 else line[icr+1:]
                output        += line
                self._current += line
        
        return output
            
    def reset(self):
        """
        Reset object.
        """
        self._current = ""
        
    @property
    def current(self) -> str:
        """
        Return current string.
        
        This is the string that ``CRMan`` is currently visible to the user
        since the last time a new line was printed.
        """
        return self._current
        
    def write(self, text : str, 
                    end : str = '', 
                    flush : bool = True, 
                    channel : Callable = None ):
        r"""
        Write to a ``channel``,
        
        Writes ``text`` to ``channel`` taking into account any ``current`` lines
        and any "\\r" and "\\n" contained in ``text``.
        The ``end`` and ``flush`` parameters mirror those of
        :func:`print`.
                                                                 
        Parameters
        ----------
        text : str
            Text to print, containing "\\r" and "\\n".
        end, flush : optional
            ``end`` and ``flush`` parameters mirror those of :func:`print`.
        channel : Callable
            Callable to output the residual text. If ``None``, the default, use :func:`print` to write to ``stdout``.
        """
        text = self(text+end)
        if channel is None:
            print( text, end='', flush=flush )
        else:
            channel( text, flush=flush )
        return self







