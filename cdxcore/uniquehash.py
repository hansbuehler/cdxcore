"""
Framework for producing unique hashes for various Python elements. Hashing is key for caching strategies and managing data pipelines effectively.
The module contains a range of utility functions to ease implementation of pipelines and other tasks where hashes of data are required.

Overview
--------

The functionality here follows by default important design principles which are discussed in :func:`cdxcore.uniquehash.UniqueHash`,
such as

* Members of objects, and elements of dictionaries which start with "_" are ignored.
* Member functions of objects or dictionaries are ignored.
* Dictionaries are assumed to be order-invariant, even though Python now
  `maintains construction order for objects <https://docs.python.org/3/whatsnew/3.6.html#whatsnew36-compactdict>`__
  and therefore also objects.

Example::

    class A(object):
        def __init__(self, x):
            self.x = x
            self._y = x*2  # protected member will not be hashed by default
    
    from cdxcore.uniquehash import UniqueHash
    uniqueHash = UniqueHash(length=12)
    a = A(2)
    print( uniqueHash(a) ) # --> "2d1dc3767730"

The module contains a few pre-defined hash functions with different hash lengths:
    
* :func:`cdxcore.uniquehash.unique_hash8`
* :func:`cdxcore.uniquehash.unique_hash16`
* :func:`cdxcore.uniquehash.unique_hash32`
* :func:`cdxcore.uniquehash.unique_hash48`
* :func:`cdxcore.uniquehash.unique_hash64`

Often it is desirable to generate readable labels or filenames which are still unique.
This can be accomplished with

* :func:`cdxcore.uniquehash.NamedUniqueHash` is used to append a unique to a descriptive name which does not
  need to be unique in itself.

* :func:`cdxcore.uniquehash.UniqueLabel` can be used to cut already unique labels down to a given maximum length.
  The function will essentially add a hash code to the end of the label, if it exceeds the maximum length.

Related functionality
---------------------

:func:`cdxcore.subdir.SubDir.cache` implements a lightweight versioned, hash-based caching mechanism
using :class:`cdxcore.uniquehash.UniqueHash`.

Import
------
.. code-block:: python

    import cdxcore.uniquehash as uniquehash
    
Documentation
-------------
"""
from __future__ import annotations

import datetime as datetime
from zoneinfo import ZoneInfo
import types as types
import hashlib as hashlib
import inspect as inspect
from collections.abc import Mapping, Collection, Sequence, Iterator, Callable
from collections import OrderedDict
import numpy as np
import pandas as pd
import struct as struct
from enum import Enum
from .util import is_function, DEF_FILE_NAME_MAP, fmt_filename
from .pretty import PrettyObject
from .verbose import Context

def _qual_name(x, with_mod=False):
    """
    Obtain a descriptive name of qualified name and module name

    :meta private:
    """#@private
    q = getattr(x, '__qualname__', x.__name__)
    if with_mod:
        m = getattr(x, "__module__", None)
        if not m is None:
            q += "@" + m
    return q

class DebugTrace(object):
    """
    Base class for tracing hashing operations. 
    
    Use either :class:`cdxcore.uniquehash.DebugTraceCollect` or
    :class:`cdxcore.uniquehash.DebugTraceVerbose` for debugging. The latter prints out tracing during the computation
    of a hash, while to former collects all this information in a simplistic data structure. Note that this can be quite memory intensive.
    """
    def _update( self, x, msg : str|None = None ):
        """ Notify processing of `x`, with an optional process `msg`
        :meta private:
        """#@private
        raise NotImplementedError()        
    def _update_topic( self, x, msg : str|None = None ):
        """ Notify processing of a topc `x` with message `msg`, and return a sub-trace context
        :meta private:
        """#@private
        raise NotImplementedError()        
    def _warning( self, msg : str):
        """ Issue warning `msg`
        :meta private:
        """#@private
        raise NotImplementedError()        

# =============================================================================
# Hashing
# =============================================================================

class UniqueHash( object ):
    """
    A calculator class which computes unique hashes of a fixed length. 
    
    There are a number of parameters which control the exact semantics
    of the hashing algorithm as it iterates through collections and objects which are are
    discussed with :class:`cdxcore.uniquehash.UniqueHash`.
    
    The base use case is to only specify the length of the unique ID string to be computed::
    
        class A(object):
            def __init__(self, x):
                self.x = x
                self._y = x*2  # protected member will not be hashed by default
        
        from cdxcore.uniquehash import UniqueHash
        uniqueHash = UniqueHash(length=12)
        a = A(2)
        print( uniqueHash(a) ) # --> "2d1dc3767730"

    The callable ``uniquehash`` can be applied to "any" Python construct.

    **Private and Protected members**

    When an object is passed to this functional its members are iterated using ``__dict__`` or ``__slots__``, respectively.
    By default this process ignores any fields in objects or dictionaries which starts with "_". The idea here is
    that "functional" parameters are stored as members, but any derived data is stored in protected members.
    This behaviour can be changed with `parse_underscore`.

    Objects can optionally implement their own hashing scheme by implementing:

    .. code-block:: python

        __unique_hash__( self, unique_hash : UniqueHash, debug_trace : DebugTrace  )
        
    This function may return a unique string, or any other non-None Python object which will then again be hashed.
    A common use case is to ignore the parameters to this function and return a tuple of members of the class which are
    pertinent for hashing::

        class CustomHash(object):
            def __init__(self, x):
                self.x  = x
                self.x2 = x*2 # dervied data; no need to hash
            def __unique_hash__( self, unique_hash : UniqueHash, debug_trace : DebugTrace  ):
                return ( self.x, )

    More generally, ``uniqueHash`` can be used to hash any elements in the object. If used, you should also pass ``debug_trace``::
        
        class CustomHash(object):
            def __init__(self, x):
                self.x  = x
                self.x2 = x*2 # dervied data; no need to hash
            def __unique_hash__( self, unique_hash : UniqueHash, debug_trace : DebugTrace  ):
                return unique_hash(self.x, debug_trace=debug_trace)

    Finally, users may also simply set ``__unique_hash__`` to a given unique string computed ahead of time::

        class CustomHash(object):
            def __init__(self, x):
                self.x  = x
                self.x2 = x*2 # dervied data; no need to hash
                self.__unique_hash__ = str(x)
                        
    **Dictionaries**
    
    Since Python 3.6 `dictionaries preserve the order <https://docs.python.org/3/whatsnew/3.6.html#whatsnew36-compactdict>`__
    in which they were constructed.
    However, Python semantics remain otherwise order-invariant, i.e. ``{'x':1, 'y':2}`` tests equal to ``{'y':2',x':1}``.
    For this reason the default behaviour here for dictionaries is to sort them before hashing their content. This also applies
    to objects processed via their ``__dict__``.

    This can be turned off by setting `sort_dicts` to ``False``.
    OrderedDicts or any classes derived from them (such as :class:`cdxcore.prettydict.pdct`)
    are processed in order and not sorted in any case.

    **Functions**

    By default function members of objects and dictionaries (which include @properties) are
    ignored. You can set `parse_functions` to ``True`` to parse a reduced text of the function code.
    There are a number of additional expert settings for handling functions, see below.
    
    **Numpy, Pandas**

    Hashing of large datasets is not advised. Use hashes on the generating parameter set instead
    where possible.
    
    Parameters
    ----------
        length : int, optional
            Intended length of the hash function. Default is ``32``.
            
        parse_underscore : bool, optional
            How to handle object members starting with "_".
            
            * ``"none"`` : ignore members starting with "_" (the default).                       
            * ``"protected"`` : ignore 'private' members declared starting with "_" and containing "__".
            * ``"private"`` : consider all members.
            
            Default is ``none``.
             
        sort_dicts : bool, optional
            Since Python 3.6 `dictionaries are ordered <https://docs.python.org/3/whatsnew/3.6.html#whatsnew36-compactdict>`__.
            That means that strictly speaking
            the two dictionaries ``{'x':1, 'y':2}`` and ``{'y':2, 'x':1}`` are not indentical;
            however Python will sematicallly still assume they are as ``==`` between the two will return True.
            Accordingly, by default this hash function assumes the order of dictionaries does __not__ 
            matter unless the are, or are derived from, :class:`OrderedDict`
            (or have their own implementation such as :class:`cdxcore.prettydict.PrettyObject`).
            
            Practically that means this function first sorts the keys of mappings before
            hashing their items. 
            
            This can be turned off by setting `sort_dicts=False`. Default is ``True``.
            
        parse_functions : bool, optional 
            If True, then the function will attempt to generate unique hashes for functions. Default is ``False``.
                
        pd_ignore_column_order : bool, optional
            (Advanced parameter).
            Whether to ingore the order of panda columns. The default is ``True``.
        np_nan_equal : bool, optional
            (Advanced parameter).
            Whether to ignore the specific type of a NaN. The default is ``False``.
        f_include_defaults : bool, optional
            (Advanced parameter).
            When parsing functions whether to include default values. Default is ``True``.
        f_include_closure : bool, optional
            (Advanced parameter).
            When parsing functions whether to include the function colusure. This can be expensive. Default is ``True``.
        f_include_globals : bool, optional
            (Advanced parameter).
            When parsing functions whether to include globals used by the function. This can be expensicve. Default is ``False``.
    """
    
    def __init__(self, length                 : int = 32, *,
                       parse_underscore       : str  = "none",
                       sort_dicts             : bool = True,
                       parse_functions        : bool = False,
                       # micro settings
                       pd_ignore_column_order : bool = True,
                       np_nan_equal           : bool = False,
                       f_include_defaults     : bool = True,
                       f_include_closure      : bool = True,
                       f_include_globals      : bool = True,
                       ) -> None:
        """
        Initializes the hash calculator which can iteratively generate hashes of a given length for arbitrary input.
        :meta public:
        """
        self.length             = int(length)

        digest_size = self.length//2
        if digest_size <= 0:
            raise ValueError("'length' must be at least 2")
        if digest_size > 64:
            raise ValueError("'length' can be at most 128 (limitation of 'haslib.blake2b')")

        self.parse_underscore   = str(parse_underscore)
        self.sort_dicts         = bool(sort_dicts)
        self.parse_functions    = bool(parse_functions)
        
        self.pd_ignore_column_order = bool(pd_ignore_column_order)
        self.np_nan_equal           = bool(np_nan_equal)

        self.f_include_defaults = bool(f_include_defaults)
        self.f_include_closure  = bool(f_include_closure)
        self.f_include_globals  = bool(f_include_globals)
        
        if parse_underscore == "none":
            self._pi = 0
        elif parse_underscore == "protected":
            self._pi = 1
        else:
            if parse_underscore != "private": raise ValueError("'parse_underscore' must be 'none', 'private', or 'protected'. Found '{self.parse_underscore}'")
            self._pi = 2

    @property
    def name(self) -> str:
        """ Returns a descriptive name of `self`. """
        return f"uniqueHash({self.length};{self.parse_underscore},{self.sort_dicts},{self.parse_functions})"
    
    def clone(self):
        """ Return a shallow copy of `self`. """
        return UniqueHash( **{ k:v for k,v in self.__dict__.items() if not k[:1] == "_"} )

    def __call__(__self__, # LEAVE THIS NAME. **kwargs might contain 'self' arguments.
                 *args, debug_trace : DebugTrace|None = None, **kwargs) -> str:
        """
        Returns a unique hash for the ``arg`` and ``kwargs`` parameters passed to this function.
        
        Example::
            
            class A(object):
                def __init__(self, x):
                    self.x = x
                    self._y = x*2  # protected member will not be hashed by default
            
            from cdxcore.uniquehash import UniqueHash
            uniqueHash = UniqueHash(12)
            a = A(2)
            print( uniqueHash(a) ) # --> "2d1dc3767730"
            
        Parameters
        ----------
        args, kwargs:
            Parameters to hash.
            
        debug_trace : :class:`cdxcore.uniquehash.DebugTrace` | None, default ``None``
            Allows tracing of hashing activity for debugging purposes.
            Two implementations of ``DebugTrace`` are available:
                
            * :class:`cdxcore.uniquehash.DebugTraceVerbose` simply prints out hashing activity to stdout.
            
            * :class:`cdxcore.uniquehash.DebugTraceCollect` collects an array of tracing information.
              The object itself is an iterable which contains the respective tracing information
              once the hash function has returned.
        
        Returns
        -------
        Hash : str
            String of at most ``self.length``.
        """
        h, _ = __self__._mk_blake( h=__self__.length//2 )
        if len(args) > 0:
            __self__._hash_any( h, args, debug_trace = debug_trace )
        if len(kwargs) > 0:
            __self__._hash_any( h, kwargs, debug_trace = debug_trace )
        return h.hexdigest()

    # Utility functions
    # -----------------
    
    @staticmethod
    def _mk_blake( h ):
        """ utility function to allow passing a hash 'h' or an 'int' :meta private: """
        if not isinstance(h, int):
            return h, False
        h = int(h)
        assert h//2>0 and h//2<64, ("'h' must be at least 2 and not exceed 128", h)
        h = hashlib.blake2b( digest_size=h ) if h > 16 else hashlib.blake2s( digest_size=h )
        return h, True
    
    def _hash_any(self, h, x, *, debug_trace = None ):
        """
        Recursive function to hash "any" object.
        
        Parameters
        ----------
            h : hash
                Hashlib algorithm
            x : any
                Value to hash.
            debug_trace :
                Optional DebugTrace object to debug uniqueHash calculations.
        """
        if x is None:
            h.update(b'\x00')
            if not debug_trace is None: debug_trace._update( None )
            return
        # numpy atomic
        if isinstance(x, np.generic):
            sz = x.itemsize
            if sz==1:
                x = x.view(np.int8)
            elif sz==2:
                x = x.view(np.int16)
            elif sz==4:
                x = x.view(np.int32)
            else:
                assert sz==8, ("Cannot handle itemsize",sz,"for numpy generic", type(x), "with value", x)
                x = x.view(np.int64)
            h.update(x.tobytes())
            if not debug_trace is None: debug_trace._update( x )
            return
        # basic elements
        if isinstance( x, bool ):
            h.update( x.to_bytes(1,'little', signed=True) )
            if not debug_trace is None: debug_trace._update( x )
            return
        if isinstance( x, int ):
            try:
                h.update( x.to_bytes(8,'little', signed=True) )
            except OverflowError:
                nbytes = max(1, (x.bit_length() + 8) // 8)  # caters for signed and unsiged.
                b = x.to_bytes(nbytes, "little", signed=True)
                h.update(b)
            if not debug_trace is None: debug_trace._update( x )
            return
        if isinstance( x, ( float, complex ) ):
            h.update( struct.pack('<d', x) )  # little-endian double
            if not debug_trace is None: debug_trace._update( x )
            return
        if isinstance( x, bytes ):
            h.update( x )
            if not debug_trace is None: debug_trace._update( x )
            return            
        if isinstance( x, str ):
            h.update( x.encode('utf-8') )
            if not debug_trace is None: debug_trace._update( x )
            return
        # datetime etc
        if isinstance(x,datetime.datetime):
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            if x.tzinfo is None:
                ts = float( (x - datetime.datetime(1970, 1, 1)).total_seconds() )
            else:
                ts = float( (x - datetime.datetime(1970, 1, 1, tzinfo=ZoneInfo("GMT"))).total_seconds() )
            self._hash_any(h, ts, debug_trace=debug_trace)
            return
        if isinstance(x,datetime.time):
            """
            tzinfo for time is useless
            if not x.tzinfo is None:
                h.update( x.utcoffset().total_seconds.to_bytes(4,'little', signed=True) )
            else:
                h.update( int(0).to_bytes(4,'little', signed=True) )                
            """
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            total_seconds = float(x.hour*60*60+x.minute*60+x.second) +\
                            float(x.microsecond) / 1000000.
            self._hash_any(h, total_seconds, debug_trace=debug_trace)
            """            
            h.update( x.hour.to_bytes(2,'little', signed=True) )
            h.update( x.minute.to_bytes(2,'little', signed=True) )
            h.update( x.second.to_bytes(2,'little', signed=True) )
            h.update( x.microsecond.to_bytes(4,'little', signed=True))
            if not debug_trace is None:
                debug_trace = debug_trace._update_topic( x )
                debug_trace._update( x.hour, "hour")
                debug_trace._update( x.minute, "minute")
                debug_trace._update( x.second, "second")
                debug_trace._update( x.microsecond, "microsecond")
                if not x.tzinfo is None:
                    debug_trace._warning( "datetime.time support for tzinfo is not working well. Use datetime.datetime")
            """
            return
        if isinstance(x,datetime.date):
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )            
            full = x.year * 10000 + x.month * 100 + x.day
            self._hash_any(h, full, debug_trace=debug_trace)
            """
            h.update( x.year.to_bytes(4,'little', signed=True) )
            h.update( x.month.to_bytes(1,'little', signed=True) )
            h.update( x.day.to_bytes(2,'little', signed=True) )
            if not debug_trace is None:
                debug_trace = debug_trace._update_topic( x )
                debug_trace._update( x.year, "year" )
                debug_trace._update( x.month, "month" )
                debug_trace._update( x.day, "day" )
            """
            return
        if isinstance(x,datetime.timedelta):
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            self._hash_any(h, x.total_seconds(), debug_trace=debug_trace )
            return
        # functions
        if is_function(x) or isinstance(x,property):
            if self.parse_functions:
                self._hash_function( h, x, debug_trace=debug_trace )
            elif not debug_trace is None:
                debug_trace._warning( f"Ignored function: {x.__qualname__}")                
            return
        # slice -> tuple
        if isinstance(x,slice):
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            self._hash_any(h, (x.start,x.stop,x.step), debug_trace=debug_trace )
            return
        # enum
        if isinstance( x, Enum):
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x, msg="Enum" )
            self._hash_any(h, (x.name, x.value), debug_trace=debug_trace )
            return
        # test presence of __unique_hash__()
        # objects can now simply set this member to a string
        if hasattr(x,"__unique_hash__"):
            unique_hash = x.__unique_hash__
            if isinstance(unique_hash, str):
                h.update(unique_hash.encode('utf-8') )
                if not debug_trace is None:
                    debug_trace = debug_trace._update_topic( x, msg="__unique_hash__ str" )
                    debug_trace._update( unique_hash )
                return                        
            debug_trace = None if debug_trace is None else debug_trace._update_topic( x, msg="__unique_hash__ function" )
            try:
                unique_hash = unique_hash( unique_hash=self.clone(), debug_trace=debug_trace )
            except Exception as e:
                raise type(e)( e, f"Exception encountered while calling '__unique_hash__' of object of type {type(x)}.")
            if unique_hash is None:
                raise TypeError(f"{type(x).__qualname__}: __unique_hash__() cannot return None")
            if isinstance(unique_hash, str):
                h.update(unique_hash.encode('utf-8') )
                if not debug_trace is None:
                    debug_trace._update( unique_hash )
            else:
                if not debug_trace is None:
                    debug_trace = debug_trace._update_topic( unique_hash )
                self._hash_any(h, unique_hash, debug_trace=debug_trace )
            return
        # numpy
        if isinstance(x,np.ndarray):
            self._hash_numpy(h, x, debug_trace=debug_trace )
            return
        # pandas
        if isinstance(x,pd.DataFrame):
            self._hash_dataFrame(h, x, debug_trace=debug_trace )
            return
        # dictionaries, and similar
        # note that objects with a __dict__ will
        # be hashed using that dictionary
        if isinstance(x,Mapping):
            assert not isinstance(x, Sequence)
            # from Python 3.7 onwards, dictionaries are ordered.
            # however, we here assume here that unless they are
            # specified as ordered, we can assume that the
            # order does not matter.
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            keys = sorted(x) if self.sort_dicts and not isinstance(x,OrderedDict) else list(x)
            for k in keys: 
                if isinstance(k,str):
                    if k[:1] == '_':
                        if self._pi == 0:
                            continue
                        if self._pi == 1 and k.find("__") != -1:
                            continue
                self._hash_any(h, (k, x[k]), debug_trace=debug_trace)
            return
        # lists, tuples and everything which looks like it --> lists
        if isinstance(x, (Sequence, Iterator)):
            assert not isinstance(x, dict)
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            for k in x:
                self._hash_any(h, k, debug_trace=debug_trace)
            return
        # all others such as sets need sorting first
        if isinstance(x, Collection):
            assert not isinstance(x, dict)
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x )
            x = sorted(x)
            for k in x:
                self._hash_any(h, k, debug_trace=debug_trace)
            return
        # objects: treat like dictionaries
        if hasattr(x,"__dict__"):
            """
            1)
             from python 3.7 onwards dictionaries are ordered.
             however, except in rare cases that order should not
             impede the equivalence of objects
            2)
             private member handling in Python is subject to name space mangling which can have curious effects.
             That's why we consider private any members staring with '_' and containing '__':
                class A(object):
                    def f(self):
                        class X(object):
                            pass
                        x = X()
                        x.__p = 1
                        print(x.__dict__)
                A().f() will print '{'_A__p': 1}' even though 'x.__p' is a private member to X.
            """
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x, "object with __dict__" )
            self._hash_any( h, _qual_name( type(x),False), debug_trace=debug_trace)
            x    = x.__dict__
            keys = sorted(x) if self.sort_dicts else list(x)
            for k in keys:
                if isinstance(k,str):
                    if k[:1] == '_':
                        if self._pi == 0:
                            continue
                        if self._pi == 1 and k.find("__") != -1:
                            continue
                self._hash_any(h, k, debug_trace=debug_trace)
                self._hash_any(h, x[k], debug_trace=debug_trace)
            return
            self._hash_any(h, x.__dict__)
            return
        if hasattr(x,"__slots__"):
            if not debug_trace is None: debug_trace = debug_trace._update_topic( x, "object with __slots__" )
            self._hash_any( h, _qual_name( type(x),False), debug_trace=debug_trace)
            for k in  x.__slots__:
                if isinstance(k,str):
                    if k[:1] == '_':
                        if self._pi == 0:
                            continue
                        if self._pi == 1 and k.find("__") != -1:
                            continue
                self._hash_any(h, k, debug_trace=debug_trace)
                self._hash_any(h, getattr(x,k), debug_trace=debug_trace)
            return
        raise TypeError(f"Cannot generate unique hash for type '{_qual_name(type(x),True)}': it does not have __dict__ or __slots__")
    
    def _hash_function( self, h, fn : Callable, *, debug_trace = None ):
        """
        Hash a function
        """
        fn = inspect.unwrap(getattr(fn, "__func__", fn))
        if inspect.isbuiltin(fn):
            # Builtins: best we can do is identity by module + qualname
            ident = _qual_name(fn,False)
            h.update( ident.encode("utf-8") )
            if not debug_trace is None: debug_trace._update( ident, "builtin function" )
            return
    
        if not inspect.isfunction(fn):
            if hasattr(fn, "__call__"):
                obj_name = _qual_name(type(fn),False)
                h.update( obj_name.encode("utf-8") )                
                if not debug_trace is None:
                    debug_trace = debug_trace._update_topic( fn, "using __call__" )
                    debug_trace._update( obj_name )
                return self._hash_function(h, fn.__call__, debug_trace = debug_trace )
            raise TypeError(f"'fn' is not a function but of type {type(fn)}.")
    
        debug_trace = None if debug_trace is None else debug_trace._update_topic( fn )
        func_name   = _qual_name(fn,False)
        self._hash_any( h, func_name )

        src = inspect.getsourcelines( fn )[0]
        if isinstance(fn,types.LambdaType) and fn.__name__ == "<lambda>":
            assert len(src) > 0, "No source code ??"
            l = src[0]
            i = l.lower().find("lambda ")
            assert i!=-1, (f"Cannot find keyword 'lambda' even though {func_name} is a LambdaType?")
            src[0] = l[i+len("lambda "):]
        # Compressed version of the code of the function 'f' where all blanks are removed"""
        src = [ l.replace("\t"," ").replace(" ","").replace("\n","") for l in src ]    
        self._hash_any( h, src )
        if not debug_trace is None:
            debug_trace._update( func_name )
            debug_trace._update( src, "reduced source code")
        del src, func_name

        if self.f_include_defaults:
            # Defaults
            if not fn.__defaults__ is None and len(fn.__defaults__) > 0:
                def_debug_trace = None if debug_trace is None else debug_trace._update_topic( fn.__defaults__, "position defaults")
                self._hash_any( h, fn.__defaults__, debug_trace = def_debug_trace )
                del def_debug_trace

            if not fn.__kwdefaults__ is None and len(fn.__kwdefaults__) > 0:
                def_debug_trace = None if debug_trace is None else debug_trace._update_topic(fn.__kwdefaults__, "keyword defauls")
                self._hash_any( h, fn.__kwdefaults__, debug_trace = def_debug_trace )
                del def_debug_trace
    
        if self.f_include_closure and not fn.__closure__ is None and len(fn.__closure__) > 0:
            # Closure cells (can be large; disable if that’s a concern)
            closure_debug_trace = None if debug_trace is None else debug_trace._update_topic( fn.__closure__, "closure" )
            for cell in fn.__closure__:
                self._hash_any( h, cell.cell_contents, debug_trace=closure_debug_trace )
            del closure_debug_trace
    
        if self.f_include_globals and len(fn.__globals__) > 0 and len(fn.__code__.co_names) > 0:
            # Referenced globals (names actually used by the code)
            g = fn.__globals__
            glb_debug_trace = None if debug_trace is None else debug_trace._update_topic( fn.__code__.co_names, "linked globals" )
            for name in sorted(fn.__code__.co_names):
                if name in g:
                    self._hash_any( h, (name, g[name]), debug_trace=glb_debug_trace )
            del glb_debug_trace
            del g
    
    def _hash_dataFrame( self, h, df : pd.DataFrame, *, debug_trace = None ):
        """
        Compute hash for a dataframe, c.f. https://stackoverflow.com/questions/49883236/how-to-generate-a-hash-or-checksum-value-on-python-dataframe-created-from-a-fix    
        Returns a hex digest that changes if the DataFrame's *content* changes.
        Does not hash attributes.
        """
        assert isinstance(df, pd.DataFrame), ("DataFrame expected", type(df))
        debug_trace = None if debug_trace is None else debug_trace._update_topic( df )
        if self.pd_ignore_column_order:
            df = df.reindex(sorted(df.columns), axis=1)
    
        # hash index
        idx_h = pd.util.hash_pandas_object(df.index, index=False, categorize=True).values
        h.update(idx_h.tobytes())
        if not debug_trace is None: debug_trace._update( idx_h )
    
        # hash each column’s content + its name + dtype
        for name, col in df.items():
            h.update(str(name).encode('utf-8'))
            h.update(str(col.dtype).encode('utf-8'))
            col_h = pd.util.hash_pandas_object(col, index=False, categorize=True).values
            h.update(col_h.tobytes())
            if not debug_trace is None:
                debug_trace._update( str(name) )
                debug_trace._update( str(col.dtype) )
                debug_trace._update( col_h )

        # attrs, if any
        attrs = getattr(df, "attrs", None)
        if not attrs is None:
            self._hash_any(h, attrs)
            if not debug_trace is None: debug_trace._update( attrs, "attrs" )
    
    def _hash_numpy( self, h, a : np.ndarray, *, debug_trace = None ):
        """
        Numpy hash
        """
        assert isinstance(a, np.ndarray), ("ndarray expected", type(a))
        a = np.asarray(a)
    
        debug_trace = None if debug_trace is None else debug_trace._update_topic( a )
        # Disallow arbitrary Python objects (define your own encoding first)
        if a.dtype.kind == 'O':
            raise TypeError("object-dtype array: map elements to bytes first (e.g., via str/utf-8).")
    
        # Datetime/timedelta: hash their int64 representation
        if a.dtype.kind in 'Mm':
            a = a.view(np.int64)
    
        # Make contiguous and normalize to little-endian for numeric types
        a_dtype = a.dtype
        # a       = np.ascontiguousarray(a)
        if a.dtype.byteorder == '>' or (a.dtype.byteorder == '=' and not np.little_endian):
            a = a.byteswap().newbyteorder()
    
        # Canonicalize NaN bits so all NaNs hash the same (float16/32/64, complex64/128)
        if self.np_nan_equal and a.dtype.kind in 'fc':
            base_bytes = (a.dtype.itemsize // (2 if a.dtype.kind == 'c' else 1))
            if base_bytes == 2:
                base = np.float16
            elif base_bytes == 4:
                base = np.float32
            else:
                assert base_bytes == 8, ("Internal error: cannot handle base_bytes", base_bytes)
                base= np.float64
            a = a.view(base)
            if np.isnan(a).any():
                a = a.copy()
                if base is np.float16:
                    qnan = np.frombuffer(np.uint16(0x7e00).tobytes(), dtype=np.float16)[0]
                elif base is np.float32:
                    qnan = np.frombuffer(np.uint32(0x7fc00000).tobytes(), dtype=np.float32)[0]
                else:  # float64
                    qnan = np.frombuffer(np.uint64(0x7ff8000000000000).tobytes(), dtype=np.float64)[0]
                a[np.isnan(a)] = qnan
                a = a.view(a_dtype)
    
        # shapes
        h.update( len(a.shape).to_bytes(4,'little', signed=False) )
        for i in a.shape:
            h.update( i.to_bytes(4,'little', signed=False) )        
        # dtype
        h.update(a.dtype.str.encode('utf-8'))    
        h.update(a.tobytes())
        if not debug_trace is None:
            debug_trace._update( a.shape )
            debug_trace._update( a.dtype.str )
            debug_trace._update( a.tobytes() )
    
# Debugging
# =========

class DebugTraceCollect(DebugTrace):
    """
    Keep track of everything parsed during hashing.
    
    The result of the trace is contained in :attr:`cdxcore.uniquehash.DebugTraceCollect.trace`.
    
    Note that `DebugTraceCollect` itself implements :class:`Collection` and :class:`Sequence` semantics
    so you can iterate it directly.
    
    Parameters
    ----------
        tostr: int
            If set to a positive integer, then any object encountered will be represented as a string with :func:`repr`,
            and the length of the string will be limited to `tostr`. This avoids generation of large amounts
            of data if the objects hashed are large (e.g. numpy arrays).
            
            If set to ``None`` then the function collects the actual elements.
    """
    def __init__(self, tostr : int | None = None ) -> None:
        """
        Initialize data collection
        """
        if tostr and tostr<=0: raise ValueError("'tostr' must be None or a positive integer")
        self.tostr = tostr
        
        #: Trace of the hashing operation.
        #: Upon completion of :meth:`cdxcore.uniquehash.UniqueHash.__call__` this list contains
        #: elements of the following type:
        #:
        #: * if `tostr` is a positive integer:
        #:    * `typex`: type of the element
        #:    * `reprx`: `repr` of the element, up to `tostr` length.
        #:    * `msg`: message occurred during hashing if any
        #:    * `child`: if the element was a container or object
        #:
        #: * if `tostr` is ``None``:    
        #:    * `x`: the element
        #:    * `msg`: message occurred during hashing if any
        #:    * `child`: if the element was a container or object
        self.trace = []     
    def _mupdate( self, x, msg, child ):
        """ Notify processing of 'x', with an optional process 'msg'
        :meta private: """#@private
        if self.tostr:
            y = PrettyObject(   typex = type(x),
                                reprx = repr(x)[:self.tostr],
                                msg   = msg,
                                child = child )
        else:
            y = PrettyObject(   x     = x,
                                msg   = msg,
                                child = child )
        self.trace.append( y )        
    def _update( self, x, msg : str|None = None ):
        """ Notify processing of `x`, with an optional process `msg`
        :meta private: """#@private
        self._mupdate( x=x, msg=msg, child=None )
    def _update_topic( self, x, msg : str|None = None ):
        """ Notify and return a sub-trace context
        :meta private: """#@private
        child = DebugTraceCollect(tostr=self.tostr)
        self._mupdate( x=x, msg=msg, child=child )
        return child
    def _warning( self, msg : str):
        """ Issue warning
        :meta private: """
        self._mupdate( x=None, msg=msg, child=None )
        
    # results
    # -------
    
    def __getitem__(self, item):
        return self.trace[item]
    def __len__(self):
        return len(self.trace)
    def __iter__(self):
        for y in self.trace:
            yield y
    def __str__(self):
        return self.trace.__repr__()
    def __repr__(self):
        return f"DebugTraceCollect({self.trace.__str__()})"
        
class DebugTraceVerbose(DebugTrace):
    """
    Live printing of tracing information with :class:`cdxcore.verbose.Context`.
    for some formatting. All objects will be reported by type and
    their string representation, sufficiently reduced if necessary.

    Parameters
    ----------
        strsize : int, optional
            Maximum string size when using :func:`repr` on reported objects.
            Default is ``50``.
            
        verbose : :class:`cdxcore.verbose.Context`, optional
            Context object or ``None`` for a new context object
            with full visibility (it prints everything).
    """
    def __init__(self, strsize : int = 50, verbose : Context|None = None ) -> None:
        """
        Initialize tracer.
        """
        if strsize<=3: raise ValueError("'strsize' must exceed 3")
        self.strsize = strsize
        self.verbose = Context("all") if verbose is None else verbose
    def _update( self, x, msg : str|None = None, is_topic : bool = False ):
        """ Notify processing of 'x', with an optional process 'msg'
        :meta private:
        """#@private
        xstr = repr(x)
        if xstr[:1] == "'" and xstr[-1] == "'":
            xstr = xstr[1:-1]
        if len(xstr) > self.strsize:
            xstr = xstr[:self.strsize-3] + "..."
        if msg is None or len(msg) == 0:
            self.verbose.write( f"{'Entering ' if is_topic else 'Using '}{type(x).__name__}: '{xstr}'" )
        else:
            self.verbose.write( f"{'Entering ' if is_topic else 'Using '}{msg} {type(x).__name__}: '{xstr}'" )
    def _update_topic( self, x, msg : str|None = None ):
        """ Notify and return a sub-trace context
        :meta private:
        """#@private
        self._update( x, msg, is_topic=True )
        return DebugTraceVerbose( self.strsize, self.verbose(1) )    
    def _warning( self, msg : str):
        """ Issue warning
        :meta private:"""#@private
        self.verbose.write( msg )
        
# =============================================================================
# Utility wrappers
# =============================================================================

def NamedUniqueHash( max_length       : int = 60,
                     id_length        : int = 16,  *,
                     separator        : str = ' ',
                     filename_by      : str|Mapping[str,str]|None = None,
                     **unique_hash_arguments 
                     ) -> Callable:
    """
    Generate user-readable unique hashes and filenames.    
    
    Returns a function::
        
        f( label, *args, **kwargs )

    which generates unique strings of at most a length of `max_length` of the format ``label + separator + ID``
    where ID has length `id_length`. Since `label` heads the resulting string this function is suited for
    use cases where a user might want an indication what a hash refers to.

    This function does not suppose that `label` is unqiue, hence the ID is prioritized.
    See :func:`cdxcore.uniquehash.UniqueLabel` for a function which assumes the label is unique.
    
    The maximum length of the returned string is `max_length`; if need be `label` will be truncated: 
    the returned string will always end in `ID`.

    The function optionally makes sure that the returned string is a valid file name using
    :func:`cdxcore.util.fmt_filename`.

    **Short Cut**
    
    Consider :func:`cdxcore.verbose.named_unique_filename48_8` if the defaults used
    for that function are suitable for your use case.

    **Important**

    It is *strongly recommended* to read the documentation for
    :class:`cdxcore.uniquehash.UniqueHash` for details on hashing logic
    and the available parameters

    Parameters
    ----------
    max_length : int, default 60
        Total length of the returned string including the ID.
        Defaults to ``60`` to allow file names with extensions of up to three letters.
        
    id_length : int, defqult 16
        Intended length of the hash `ID`, default ``16``.
        
    separator : str, default ``' '``
        Separator between `label` and `id_length`.
        Note that the separator will be included in the ID calculation, hence different separators
        lead to different IDs. Default ``' '``.
        
    filename_by : str | None, default ``None``
        If not ``None``, use :class:`cdxcore.util.fmt_filename` with ``by=filename_by`` to ensure the returned string is a valid
        filename for both windows and linux, of at most `max_length` size.
        
        If set to the string ``default``, use :data:`cdxcore.util.DEF_FILE_NAME_MAP`
        as the default mapping for :func:`cdxcore.util.fmt_filename`.
        
    ** unique_hash_arguments, optional
        Parameters passed to :class:`cdxcore.uniquehash.UniqueHash`.

    Returns
    -------
    uniqueHash : :class:`Callable`
        hash function with signature ``(label, *args, **kwargs)``.        
    """
    if id_length < 4: raise ValueError("'id_length' must be at least 4. Found {id_length}")
    if id_length > max_length: raise ValueError(f"'max_length' must not be less than 'id_length'. Founb {max_length} and {id_length}, respectivelty")
    if 'length' in unique_hash_arguments: raise ValueError("Cannot specify 'length' here. Used 'id_length' and 'max_length'")
    filename_map = ( DEF_FILE_NAME_MAP if filename_by=="default" else filename_by ) if not filename_by is None else None
    fseparator   = fmt_filename( separator, by=filename_map ) if not filename_map is None else separator

    label_length = max_length-id_length-len(fseparator)
    if label_length<=0:
        id_length    = max_length
        label_length = 0
    unique_hash  = UniqueHash( length=id_length, **unique_hash_arguments )

    def named_unique_hash(label, *args, **kwargs) -> str:
        if label_length>0:
            assert not label is None, ("'label' cannot be None", args, kwargs)
            label        = fmt_filename( label, by=filename_map ) if filename_map is not None else label
            base_hash    = unique_hash( label, separator, *args, **kwargs )
            label        = label[:label_length] + fseparator + base_hash
        else:
            label        = unique_hash( separator, *args, **kwargs )  # using 'separator' here to allow distinction at that level
        return label
    return named_unique_hash

def UniqueLabel(     max_length       : int = 60,
                     id_length        : int = 8,
                     separator        : str = ' ',
                     filename_by      : str|Mapping[str,str]|None = None) -> Callable:
    """
    Extend unique lables by a hash ID if they exceed ``max_length``.
    
    This function returns a function:: 
        
        f( unique_label )

    which generates strings of at most ``max_length``, based on a provided ``unique_label``.
    Esentially this function performs::
    
        If len(unique_label) <= max_length:
            unique_label
        else:
            unique_label + separator + ID

    where ``ID`` is a unqiue hash computed from ``unique_label`` of maximum length ``id_length``.

    This function assumes that ``unique_label`` is unique, hence the ID is dropped if ``unique_label``
    is less than ``max_length``.
    Use :func:`cdxcore.uniquehash.NamedUniqueHash` if the label is not unique, and which therefore always appends the 
    dynamically calculated unique ID.

    Note that if ``filename_by`` conversion is used, then this function will always attach the unique ID
    to the filename because
    after the conversion of the label to a filename it is no longer guaranteed that the result is unique.
    If your label is unique as a filename, do not
    use ``filename_by``. The function will return valid file names if ``label`` is a valid file name.

    Parameters
    ----------
    max_length : int, default 60
        Total length of the returned string including the ID.
        Defaults to 60 to allow file names with extensions with three letters.
        
    id_length : int, default 8
        Indicative length of the hash function, default 8.
        id_length will be reduced to `max_length` if neccessary.
        
    separator : str, default ``' '``
        Separator between the label and the unique ID.
        
        Note that the separator will be included in the ID calculation, hence different separators
        lead to different IDs.
        
    filename_by : str | None, default ``None``
        If not ``None``, use :func:`cdxcore.util.fmt_filename` with ``by=filename_by``
        to ensure the returned string is a valid
        filename for both windows and linux, of at most ``max_length`` size. Note that if ``filename_by``
        is not ``None``, then the function will always append a hash to ``unique_label``
        because it cannot asscertain that the filename conversion creates overlapping labels.
        
        If set to the string ``"default"``, use :data:`cdxcore.util.DEF_FILE_NAME_MAP`
        as the default mapping for :func:`cdxcore.util.fmt_filename`.

    Returns
    -------
    Hash function : :class:`Callable`
        Hash function with signature ``(unique_label)``.
    """
    if id_length < 4: raise ValueError("'id_length' must be at least 4. Found {id_length}")
    if id_length > max_length: raise ValueError(f"'max_length' must not be less than 'id_length'. Founb {max_length} and {id_length}, respectivelty")

    filename_map = ( DEF_FILE_NAME_MAP if filename_by=="default" else filename_by ) if not filename_by is None else None
    fseparator   = fmt_filename( separator, by=filename_map ) if not filename_map is None else separator

    if id_length>=max_length+len(fseparator):
        id_length = max_length+len(fseparator)

    unique_hash = UniqueHash( length=id_length )

    def unique_label_hash(label) -> str:
        if filename_map is None and len(label) <= max_length and len(label) > 0:
            # no filename conversion and label is short enough --> use this name
            return label
            
        base_hash    = unique_hash( label, separator )
        label_hash   = fseparator + base_hash
        if len(label_hash) >= max_length or len(label) == 0:
            # hash and separator exceed total length. Note that len(base_hash) <= max_length
            # no file name formatting needed - base_hash is a valid filebame
            label = base_hash
        else:
            # convert label to filename
            label = fmt_filename( label, by=filename_map ) if not filename_map is None else label
            label = label[:max_length-len(label_hash)] + label_hash
        return label
    return unique_label_hash

# =============================================================================
# Short cuts
# =============================================================================

def unique_hash8( *args, **kwargs ) -> str:
    """
    Short-cut for the hash function returned by :class:`cdxcore.uniquehash.UniqueHash`
    with parameter ``length=8``.
    
    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return UniqueHash(8)(*args,**kwargs)

def unique_hash16( *args, **kwargs ) -> str:
    """
    Short-cut for the hash function returned by :class:`cdxcore.uniquehash.UniqueHash`
    with parameter ``length=16``.
    
    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return UniqueHash(16)(*args,**kwargs)

def unique_hash32( *args, **kwargs ) -> str:
    """
    Short-cut for the hash function returned by :class:`cdxcore.uniquehash.UniqueHash`
    with parameter ``length=32``.
    
    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return UniqueHash(32)(*args,**kwargs)

def unique_hash48( *args, **kwargs ) -> str:
    """
    Short-cut for the hash function returned by :class:`cdxcore.uniquehash.UniqueHash`
    with parameter ``length=48``.
    
    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return UniqueHash(48)(*args,**kwargs)

def unique_hash64( *args, **kwargs ) -> str:
    """
    Short-cut for the hash function returned by :class:`cdxcore.uniquehash.UniqueHash`
    with parameter ``length=64``.
    
    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return UniqueHash(64)(*args,**kwargs)

def named_unique_filename48_8( label : str, *args, **kwargs ) -> str:
    """
    Returns a unique and valid filename which is composed of `label` and a unique ID
    computed using all of `label`, `args`, and `kwargs`.
    
    ``label`` is not assumed to be unique.
    
    Consider a use cases where an experiment defined by ``definition``
    has produced ``results`` which we wish to :mod:`pickle` to disk.
    Assume further that ``str(definition)`` provides an
    informative user-readable but
    not necessarily unique description of ``definition``.
    
    Pseudo-Code::
        
        def store_experiment( num : int, definition : object, results : object ):
            label    = f"Experiment {str(definition)}"
            filename = named_unique_hash48_8( label, (num, definition) )
            with open(filename, "wb") as f:
                pickle.dumps(results)
    
    This is the hash function returned by :class:`cdxcore.uniquehash.NamedUniqueHash`
    with parameters ``max_length=48, id_length=8, filename_by="default"``.

    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return NamedUniqueHash( max_length=48, id_length=8, filename_by="default" )(label, *args, **kwargs)
    
def unique_label48_8( label : str, as_file_name : bool = False ) -> str:
    """
    Returns a unique label. This function assumes that ``label`` is inherently unique, but
    might exceed the maximum length of 48. In that case a unique hash of length 8 is added
    to the truncated label and returned.
    
    This function may also convert any unique label into a unique, valid file name if ``as_file_name`` is ``True``.
    In that
    case it always adds an ID (because it cannot gurantee that the conversion to a file name
    is unique). By default the function does not convert to a file name.
    
    ``label`` is assumed to be unique.
    
    This is the hash function returned by :class:`cdxcore.uniquehash.UniqueLabel`
    with parameters ``max_length=48, id_length=8, filename_by=filename_by if as_file_name else None``.

    *Important* please make sure you aware of the functional considerations
    discussed in :class:`cdxcore.uniquehash.UniqueHash` around
    elements starting with `_` or function members.
    """
    return UniqueLabel( max_length=48, id_length=8, filename_by="default" if as_file_name else None )(label)
