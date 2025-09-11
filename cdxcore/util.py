"""
Overview
--------

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
from collections.abc import Mapping, Collection
import sys as sys
import time as time
from collections import OrderedDict
from sortedcontainers import SortedDict
import numpy as np
import pandas as pd
from .err import fmt, _fmt, verify, error, warn_if, warn #NOQA

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

def is_atomic( o ):
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

def is_float( o ):
    """ Checks whether a type is a ``float`` which includes numpy floating types """
    if type(o) is float:
        return True
    if isinstance(o,np.floating):
        return True
    return False

# =============================================================================
# python basics
# =============================================================================

def _get_recursive_size(obj, seen=None):
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

def getsizeof(obj):
    """
    Approximates the size of an object.
    
    In addition to calling :func:`sys.getsizeof` this function
    also iterates embedded containers, numpy arrays, and panda dataframes.
    :meta private: 
    """
    return _get_recursive_size(obj,None)    

def qualified_name( x, module : bool = False ):
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
            @property
                def p(self):
                    return x

        qualified_name(A.p)    # -> "A.p"
        qualified_name(A().p)  # -> "int"
           
    Parameters
    ----------
        x : any
            Some Python element.
            
        module : bool, optional
            Whether to also return the containing module if available.
    Returns
    -------
        qualified name : str
            The name, if ``module`` is ``False``.
            
        (qualified name, module) : tuple
            The name, if ``module`` is ``True``.
            Note that the module name returned might be ``""`` if no module
            name could be determined.
            
    Raises
    ------
        :class:`RuntimeError` if not qualfied name for ``x`` or its type could be found.
    """
    if x is None:
        if not module:
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
    if not module:
        return name

    module = getattr(x, "__module__", None)
    if module is None:
        module = getattr(type(x), "__module__", "")
    return name, module    

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
        
    Optinally a time zone is added via::
        
        YYYY-MM-DD HH:MM:SS+HH
        YYYY-MM-DD HH:MM:SS+HH:MM
        
    Output is reduced accordingly if ``dt`` is a :class:`datetime.time`
    or :class:`datetime.date`.
    
    Parameters
    ----------
    dt : :class:`datetime.datetime`, :class:`datetime.date`, or :class:`datetime.time`
        Input.

    sep : str, optional
        Seperator for hours, minutes, seconds. The default ``':'`` is most appropriate for viusalization
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
    the corresponding :func:`datetime.time.otcoffset` function returns ``None`` if we donot
    provide a ``dt`` parameter, see
    `tzinfo documentation <https://docs.python.org/3/library/datetime.html#tzinfo-objects>`__.
    That means :func:`datetime.time.otcoffset` is only useful if we have :class:`datetime.datetime`
    object at hand. 
    That makes sense as a time zone can chnage date as well.
    
    We therefore here do not allow ``dt`` to contain
    a time zone.
        
    Use :func:`cdxcore.util.fmt_datetime` for time zone support
        
    Parameters
    ----------
    dt : :class:`datetime.time`
        Input.
    sep : str, optional
    
        Seperator for hours, minutes, seconds. The default ``':'`` is most appropriate for viusalization
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
    Replaces invalid filename characters such as `\\', ':', or '/' by a differnet character.
    The returned string is technically a valid file name under both windows and linux.
    
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
    Validity : vool 
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
# Misc
# =============================================================================

class TrackTiming(object):
    """
    Simplistic class to track the time it takes to run sequential tasks.

    Usage::

        from cdxcore.util import TrackTiming
        timer = TrackTiming()   # clock starts

        # do job 1
        timer += "Job 1 done"

        # do job 2
        timer += "Job 2 done"

        print( timer.summary() )
    """

    def __init__(self):
        """ Initialize a new tracked timer """
        self.reset_all()

    def reset_all(self):
        """ Reset timer, and clear all tracked items """
        self._tracked = OrderedDict()
        self._current = time.time()

    def reset_timer(self):
        """ Reset the timer to current time """
        self._current = time.time()

    def track(self, text, *args, **kwargs ):
        """ Track 'text', formatted with 'args' and 'kwargs' """
        text = _fmt(text,args,kwargs)
        self += text

    def __iadd__(self, text : str):
        """ Track 'text' """
        text  = str(text)
        now   = time.time()
        dt    = now - self._current
        if text in self._tracked:
            self._tracked[text] += dt
        else:
            self._tracked[text] = dt
        self._current = now
        return self

    def __str__(self):
        """ Returns summary """
        return self.summary()

    @property
    def tracked(self) -> list:
        """ Returns dictionary of tracked texts """
        return self._tracked

    def summary(self, fmat : str = "%(text)s: %(fmt_seconds)s", jn_fmt : str = ", " ) -> str:
        """
        Generate summary string by applying some formatting

        Parameters
        ----------
        fmat : str, optional
            Format string using ``%()``. Arguments are ```text``, ``seconds`` (as int) and ``fmt_seconds`` (a string).
            
            Default is ``"%(text)s: %(fmt_seconds)s"``.

        jn_fmt : str, optional
            String to be used between two texts. Default ``", " ``.
            
        Returns
        -------
        Summary : str
            The combined summary string
        """
        s = ""
        for text, seconds in self._tracked.items():
            tr_txt = fmat % dict( text=text, seconds=seconds, fmt_seconds=fmt_seconds(seconds))
            s      = tr_txt if s=="" else s+jn_fmt+tr_txt
        return s

# =============================================================================
# Misc
# =============================================================================

class Timer(object):
    """
    Micro utility to measure passage of time.

    Example::

        from cdxcore.util import Timer
        with Timer() as t:
            .... do somthing ...
            print(f"This took {t}.")
    """
    
    def __init__(self):
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
        Tests if `interval` seconds have passed.
        If yes, reset timer and return True. Otherwise return False.
        
        Usage::
            
            from cdxcore.util import Timer
            tme = Timer()
            for i in range(n):
                if tme.test_dt_seconds(2.):
                    print(f"\r{i+1}/{n} done. Time taken so far {tme}.", end='', flush=True)
            print("\rDone. This took {tme}.")

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






