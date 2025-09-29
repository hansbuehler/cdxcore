"""
Utilities for file i/o, directory management and
streamlined versioned caching.

Overview
--------

The key idea is to provide transparent, concise :mod:`pickle` access to the file system
via the :class:`cdxcore.subdir.SubDir` class.

**Key design features:**

* Simple path construction via ``()`` operator. By default directories which do not exist yet
  are only created upon writing a first file.
     
* Files managed by :class:`cdxcore.subdir.SubDir` all have the same extension.

* Files support "fast versioning": the version of a file can be read without having to read the
  entire file.
  
* :dec:`cdxcore.subdir.SubDir.cache` implements a convenient versioned caching framework.

Directories
^^^^^^^^^^^

The core of the framework is the :class:`cdxcore.subdir.SubDir` class which represents a directory
with files of a given extension.

Simply write::

    from cdxcore.subdir import SubDir
    subdir = SubDir("my_directory")      # relative to current working directory
    subdir = SubDir("./my_directory")    # relative to current working directory
    subdir = SubDir("~/my_directory")    # relative to home directory
    subdir = SubDir("!/my_directory")    # relative to default temp directory
    subdir = SubDir("?!/my_directory")   # relative to a temporary temp directory; this directory will be cleared upon (orderly) exit of ``SubDir``.
    
Note that ``my_directoy`` will not be created if it does not exist yet. It will be created the first
time we write a file.

You can specify a parent for relative path names::

    from cdxcore.subdir import SubDir
    subdir = SubDir("my_directory", "~")      # relative to home directory
    subdir = SubDir("my_directory", "!")      # relative to default temp directory
    subdir = SubDir("my_directory", ".")      # relative to current directory
    subdir2 = SubDir("my_directory", subdir)  # subdir2 is relative to `subdir`

Change the extension to "bin"::

    from cdxcore.subdir import SubDir
    subdir = SubDir("~/my_directory;*.bin")     
    subdir = SubDir("~/my_directory", ext="bin")    
    subdir = SubDir("my_directory", "~", ext="bin")    

You can turn off extension management by setting the extension to ``""``::

    from cdxcore.subdir import SubDir
    subdir = SubDir("~/my_directory", ext="")

You can also use :meth:`cdxcore.subdir.SubDir.__call__` to generate sub directories::

    from cdxcore.subdir import SubDir
    parent = SubDir("~/parent")
    subdir = parent("subdir")

Be aware that when the operator :meth:`cdxcore.subdir.SubDir.__call__`
is called with two keyword arguments, then it reads files.

You can obtain a list of all sub directories in a directory by using :meth:`cdxcore.subdir.SubDir.sub_dirs`.
The list of files with the corresponding extension is accessible via :meth:`cdxcore.subdir.SubDir.files`. 

File Format
^^^^^^^^^^^

:class:`cdxcore.subdir.SubDir` supports file i/o with a number of different file formats:
    
* "PICKLE": standard pickling with default extension "pck".

* "JSON_PICKLE": uses the :mod:`jsonpickle` package; default extension "jpck".
  The advantage of this format over "PICKLE" is that it is somewhat human-readable.
  However, ``jsonpickle`` uses compressed formats for complex objects such as :mod:`numpy`
  arrays, hence readablility is somewhat limited. Using "JSON_PICKLE"
  comes at cost of slower i/o speed.

* "JSON_PLAIN": calls :func:`cdxcore.util.plain` is an output-only format to generate human readable files
  which (usually) cannot be loaded back from disk.
  In this mode ``SubDir`` converts objects into plain Python objects before using :mod:`json`
  to write them to disk.
  That means that deserialized data does not have the correct object structure
  for being restored properly.
  However, such files are much easier to read.

* "BLOSC" uses `blosc <https://github.com/blosc/python-blosc>`__
  to read/write compressed binary data. The blosc compression algorithm is very fast,
  hence using this mode will not usually lead to notably slower performance than using
  "PICKLE" but will generate smaller files, depending on your data structure.
  
  The default extension for "BLOSC" is "zbsc".

* "GZIP": uses :mod:`gzip` to 
  to read/write compressed binary data. The default extension is "pgz".

**Summary of properties:**

+--------------+------------------+----------------+-------+-------------+-----------+
| Format       | Restores objects | Human readable | Speed | Compression | Extension |
+==============+==================+================+=======+=============+===========+
| PICKLE       | yes              | no             | high  | no          | .pck      |
+--------------+------------------+----------------+-------+-------------+-----------+
| JSON_PLAIN   | no               | yes            | low   | no          | .json     |
+--------------+------------------+----------------+-------+-------------+-----------+
| JSON_PICKLE  | yes              | limited        | low   | no          | .jpck     |
+--------------+------------------+----------------+-------+-------------+-----------+
| BLOSC        | yes              | no             | high  | yes         | .zbsc     |
+--------------+------------------+----------------+-------+-------------+-----------+
| GZIP         | yes              | no             | high  | yes         | .pgz      |
+--------------+------------------+----------------+-------+-------------+-----------+


You may specify the file format when instantiating :class:`cdxcore.subdir.SubDir`::

    from cdxcore.subdir import SubDir
    subdir = SubDir("~/my_directory", fmt=SubDir.PICKLE)
    subdir = SubDir("~/my_directory", fmt=SubDir.JSON_PICKLE)
    ...

If ``ext`` is not specified the extension will defaulted to 
the respective default extension of the format requested.

Reading Files
^^^^^^^^^^^^^

To read the data contained in a ``file`` from our subdirectory
with its reference extension use :meth:`cdxcore.subdir.SubDir.read`::

    from cdxcore.subdir import SubDir
    subdir = SubDir("!/test")
    
    data = subdir.read("file")                 # returns the default `None` if file.pck is not found
    data = subdir.read("file", default=[])     # returns the default [] if file.pck is not found

This function will return the "default" (which in turns defaults to ``None``)
if "file.pck" does not exist.
You can opt to raise an error instead of returning a default
by using ``raise_on_error=True``::

    data = subdir.read("file", raise_on_error=True)  # raises 'KeyError' if not found

When calling ``read()`` you may specify an alternative extension::

    data = subdir.read("file", ext="bin")     # change extension to "bin"
    data = subdir.read("file.bin", ext="")    # no automatic extension

Specifying a different format for :meth:`cdxcore.subdir.SubDir.read` only changes
the extension automatically if you have not overwritten it before:

.. code-block:: python

    subdir = SubDir("!/test")                              # default format PICKLE with extension pck
    data   = subdir.read("file", fmt=Subdir.JSON_PICKLE )  # uses "json" extension
    
    subdir = SubDir("!/test", ext="bin")                   # user-specified extension
    data   = subdir.read("file", fmt=Subdir.JSON_PICKLE )  # keeps using "bin"
    
You can also use the :meth:`cdxcore.subdir.SubDir.__call__` to read files, in which case you must specify a default value
(if you don't, then the operator will return a sub directory)::

    data = subdir("file", None)   # returns None if file is not found

You can also use item notation to access files.
In this case, though, an error will be thrown if the file does not exist::

    data = subdir['file']   # raises KeyError if file is not found

You can read a range of files in one function call::

    data = subdir.read( ["file1", "file2"] )   # returns list

Finally, you can also iterate through all existing files using iterators::

    # manual loading
    for file in subdir:
        data = subdir.read(file)
        ...
        
    # automatic loading, with "None" as a default
    for file, data in subdir.items():
        ...

To obtain a list of all files in our directory which have the correct extension, use :meth:`cdxcore.subdir.SubDir.files`.

Writing Files
^^^^^^^^^^^^^

Writing files mirrors reading them::

    from cdxcore.subdir import SubDir
    subdir = SubDir("!/test")
    
    subdir.write("file", data)
    subdir['file'] = data

You may specifify different a extension::

    subdir.write("file", data, ext="bin")

You can also specify a file :class:`cdxcore.subdir.Format`.
The extension will be changed automatically if you have not set it manually::

    subdir = SubDir("!/test")
    subdir.write("file", data, fmt=SubDir.JSON_PICKLE )   # will write to "file.json"

To write several files at once, write::

    subdir.write(["file1", "file"], [data1, data2])

Note that when writing to a file, :meth:`cdxcore.subdir.SubDir.write`
will first write to a temporary file, and then rename this file into the target file name.
The temporary file name is generated by applying :func:`cdxcore.uniquehash.unique_hash48`
to the
target file name, 
current time, process and thread ID, as well as the machines's UUID. 
This is done to reduce collisions between processes/machines accessing the same files,
potentially accross a network.
It does not remove collision risk entirely, though.

Filenames
^^^^^^^^^

:class:`cdxcore.subdir.SubDir` transparently handles directory access and extensions.
That means a user usually only uses ``file`` names which do not contain either.
To  obtain the full qualified filename given a "file" use :meth:`cdxcore.subdir.SubDir.full_file_name`.

Reading and Writing Versioned Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:class:`cdxcore.subdir.SubDir` supports versioned files.
If versions are used, then they *must* be used for both reading and writing.
:dec:`cdxcore.version.version` provides a standard decorator framework for definining
versions for classes and functions including version dependencies.

If a ``version`` is provided for :func:`cdxcore.subdir.SubDir.write`
then ``SubDir`` will write the version in a block ahead of the main content of the file.
In case of the PICKLE format, this is a byte string. In case of JSON_PLAIN and JSON_PICKLE this is line of
text starting with ``#`` ahead of the file. (Note that this violates
the JSON file format.)
  
Writing a short version block ahead of the main data allows :func:`cdxcore.subdir.SubDir.read`
to read this version information back quickly without reading the entire file.
``read()`` does attempt so if its called with a ``version`` parameter.
In this case it will compare the read version with the provided version,
and only return the main content of the file if versions match.

Use :func:`cdxcore.subdir.SubDir.is_version` to check whether a given file has a specific version.
Like ``read()`` this function only reads the information required to obtain the information and will
be much faster than reading the whole file.

*Important:* if a file was written with a ``version``, then it has to be read again with a test version.
You can specify ``version="*"`` for :func:`cdxcore.subdir.SubDir.read` to match any version.

**Examples:**

Writing a versioned file::

    from cdxcore.subdir import SubDir
    sub_dir = SubDir("!/test_version)
    sub_dir.write("test", [1,2,3], version="0.0.1" )

To read ``[1,2,3]`` from "test" we need to use the correct version::

    _ = sub_dir.read("test", version="0.0.1") 

The following will not read "test" as the versions do not match::

    _ = sub_dir.read("test", version="0.0.2")

By default :func:`cdxcore.subdir.SubDir.read` 
will not fail if a version mismatch is encountered; rather it will
attempt to delete the file and then return the ``default`` value.

This can be turned off
with the keyword ``delete_wrong_version`` set to ``False``.

You can ignore the version used to writing a file by using ``"*"`` as version::

    _ = sub_dir.read("test", version="*")

Note that reading files which have been written with a ``version`` without
``version`` keyword will fail because ``SubDir`` will only append additional version information
to the file if required.

Test existence of Files
^^^^^^^^^^^^^^^^^^^^^^^

To test existence of 'file' in a directory, use one of::

    subdir.exist('file')
    'file' in subdir

Deleting files
^^^^^^^^^^^^^^

To delete a 'file', use any of the following::

    subdir.delete("file")
    del subdir['file']

All of these are *silent*, and will not throw errors if ``file`` does not exist.
In order to throw an error use::

    subdir.delete('file', raise_on_error=True)

A few member functions assist in deleting a number of files:

* :func:`cdxcore.subdir.SubDir.delete_all_files`: delete all files in the directory with matching extension. Do not delete sub directories, or files with extensions different to our own.
* :func:`cdxcore.subdir.SubDir.delete_all_content`: delete all files with our extension, including in all sub-directories. If a sub-directory is left empty
  upon ``delete_all_content`` delete it, too.
* :func:`cdxcore.subdir.SubDir.delete_everything`: deletes *everything*, not just files with matching extensions.

Caching
^^^^^^^

A :class:`cdxcore.subdir.SubDir` object offers an advanced context for caching calls to :class:`collection.abc.Callable``
objects with :dec:`cdxcore.subdir.SubDir.cache`.

    .. code-block:: python

        from cdxcore.subdir import SubDir
        cache   = SubDir("!/.cache")
        cache.delete_all_content()   # for illustration
        
        @cache.cache("0.1")
        def f(x,y):
            return x*y
        
        _ = f(1,2)    # function gets computed and the result cached
        _ = f(1,2)    # restore result from cache
        _ = f(2,2)    # different parameters: compute and store result

This involves keying the cache by the function name and its current parameters using :class:`cdxcore.uniquehash.UniqueHash`,
and monitoring the functions version using :dec:`cdxcore.version.version`. The caching behaviour itself can be controlled by
specifying the desired :class:`cdxcore.subdir.CacheMode`.

See :dec:`cdxcore.subdir.SubDir.cache` for full feature set.

Import
------
.. code-block:: python

    import cdxcore.uniquehash as uniquehash
    
Documentation
-------------
"""

import os as os
import uuid as uuid
import threading as threading
import pickle as pickle
import tempfile as tempfile
import shutil as shutil
import datetime as datetime
import inspect as inspect
import platform as platform
from collections import OrderedDict
from collections.abc import Collection, Mapping, Callable, Iterable
from enum import Enum
from functools import update_wrapper
        
import json as json
import gzip as gzip
import blosc as blosc
import sys as sys
from .err import verify, error, warn, fmt as txtfmt
from .pretty import PrettyObject
from .verbose import Context
from .version import Version, version as version_decorator, VersionError
from .util import fmt_list, fmt_filename, DEF_FILE_NAME_MAP, plain, is_filename
from .uniquehash import unique_hash48, UniqueLabel, NamedUniqueHash, named_unique_filename48_8


"""
:meta private:
compression
"""

def _import_jsonpickle():
    """ For some dodgy reason importing `jsonpickle` normally causes my tests to fail with a recursion error """
    jsonpickle = sys.modules.get('jsonpickle', None)
    if jsonpickle is None:
        import jsonpickle as jsonpickle
        import jsonpickle.ext.numpy as jsonpickle_numpy
        jsonpickle_numpy.register_handlers()
    return jsonpickle

def _remove_trailing( path ):
    if len(path) > 0:
        if path[-1] in ['/' or '\\']:
            return _remove_trailing(path[:-1])
    return path

_BLOSC_MAX_USE   = 1147400000
# Maximum blosc buffer size we use, as blosc seems to have issues with too large files.
# The actual maximum `blosc buffer size <https://www.blosc.org/python-blosc2/reference/autofiles/low_level/blosc2.MAX_BUFFERSIZE.html>`__
# seems too generous/

# ========================================================================
# Basics
# ========================================================================

class Format(Enum):
    """
    File formats for :class:`cdxcore.subdir.SubDir`.
    
    +--------------+------------------+----------------+-------+-------------+-----------+
    | Format       | Restores objects | Human readable | Speed | Compression | Extension |
    +==============+==================+================+=======+=============+===========+
    | PICKLE       | yes              | no             | high  | no          | .pck      |
    +--------------+------------------+----------------+-------+-------------+-----------+
    | JSON_PLAIN   | no               | yes            | low   | no          | .json     |
    +--------------+------------------+----------------+-------+-------------+-----------+
    | JSON_PICKLE  | yes              | limited        | low   | no          | .jpck     |
    +--------------+------------------+----------------+-------+-------------+-----------+
    | BLOSC        | yes              | no             | high  | yes         | .zbsc     |
    +--------------+------------------+----------------+-------+-------------+-----------+
    | GZIP         | yes              | no             | high  | yes         | .pgz      |
    +--------------+------------------+----------------+-------+-------------+-----------+
    """
    PICKLE = 0       #: Standard binary :mod:`pickle` format.
    JSON_PICKLE = 1  #: :mod:`jsonpickle` format.
    JSON_PLAIN = 2   #: ``json`` format.
    BLOSC = 3        #: :mod:`blosc` binary compressed format.
    GZIP = 4         #: :mod:`gzip` binary compressed format.
    
PICKLE = Format.PICKLE
JSON_PICKLE = Format.JSON_PICKLE
JSON_PLAIN = Format.JSON_PLAIN
BLOSC = Format.BLOSC
GZIP = Format.GZIP

class VersionPresentError(RuntimeError):
    """
    Exception raised in case a file was read which had a version, but no test version
    was provided.
    """
    pass

# ========================================================================
# Caching utilities
# ========================================================================

class CacheMode(object):
    """
    A class which encodes standard behaviour of a caching strategy.

    **Summary mechanics:**
        
    +-----------------------------------------+-------+-------+-------+---------+--------+----------+
    | Action                                  | on    | gen   | off   | update  | clear  | readonly |
    +=========================================+=======+=======+=======+=========+========+==========+
    | load cache from disk if exists          | x     | x     |       |         |        | x        |
    +-----------------------------------------+-------+-------+-------+---------+--------+----------+
    | write updates to disk                   | x     | x     |       |  x      |        |          |
    +-----------------------------------------+-------+-------+-------+---------+--------+----------+
    | delete existing object                  |       |       |       |         | x      |          |
    +-----------------------------------------+-------+-------+-------+---------+--------+----------+
    | delete existing object if incompatible  | x     |       |       |  x      | x      |          |
    +-----------------------------------------+-------+-------+-------+---------+--------+----------+      


    **Standard Caching Semantics**

    Assuming we wish to cache results from calling a function ``f`` in a file named ``filename``
    in a directory ``directory``, then this is the ``CacheMode`` waterfall:

    .. code-block:: python

        def cache_f( filename : str, directory : SubDir, version : str, cache_mode : CacheMode ):
            if cache_mode.delete:
                directory.delete(filename)
            if cache_mode.read:
                r = directory.read(filename,
                                   default=None,  
                                   version=version,
                                   raise_on_error=False,
                                   delete_wrong_version=cache_mode.del_incomp
                                   )
                if not r is None:
                    return r
            
            r = f(...) # compute result
            
            if cache_mode.write:
                directory.write(filename,
                                r,
                                version=version,
                                raise_on_error=False
                                )
    
            return r

    See :func:`cdxcore.subdir.SubDir.cache` for a comprehensive
    implementation.

    Parameters
    ----------
        mode : str, optional
            Which mode to use: ``"on"``, ``"gen"``, ``"off"``, ``"update"``, ``"clear"`` or ``"readonly"``.
            
            The default is ``None`` in which case ``"on"`` is used.
    """

    ON = "on"  
    GEN = "gen"
    OFF = "off"
    UPDATE = "update"
    CLEAR = "clear"
    READONLY = "readonly"

    MODES = [ ON, GEN, OFF, UPDATE, CLEAR, READONLY ]
    """
    List of available modes in text form.
    This list can be used as ``cast`` parameter when calling :func:`cdxcore.config.Config.__call__`::
    
        from cdxcore.config import Config
        from cdxcore.subdir import CacheMode
        
        def get_cache_mode( config : Config ) -> CacheMode:
            return CacheMode( config("cache_mode", "on", CacheMode.MODES, CacheMode.HELP) )
    """
        
    HELP = "'on' for standard caching; 'gen' for caching but keep existing incompatible files; 'off' to turn off; 'update' to overwrite any existing cache; 'clear' to clear existing caches; 'readonly' to read existing caches but not write new ones"
    """
    Standard ``config`` help text, to be used with  :func:`cdxcore.config.Config.__call__` as follows::
        
        from cdxcore.config import Config
        from cdxcore.subdir import CacheMode
        
        def get_cache_mode( config : Config ) -> CacheMode:
            return CacheMode( config("cache_mode", "on", CacheMode.MODES, CacheMode.HELP) )
    """
    
    def __init__(self, mode : str = None ):
        """
        :meta private:
        """
        if isinstance( mode, CacheMode ):
            return# id copy constuctor
        mode      = self.ON if mode is None else mode
        self.mode = mode.mode if isinstance(mode, CacheMode) else str(mode)
        if not self.mode in self.MODES:
            raise KeyError( self.mode, "Caching mode must be 'on', 'off', 'update', 'clear', or 'readonly'. Found " + self.mode )
        self._read   = self.mode in [self.ON, self.READONLY, self.GEN]
        self._write  = self.mode in [self.ON, self.UPDATE, self.GEN]
        self._delete = self.mode in [self.UPDATE, self.CLEAR]
        self._del_in = self.mode in [self.UPDATE, self.CLEAR, self.ON]

    def __new__(cls, *kargs, **kwargs):
        """ Copy constructor """
        if len(kargs) == 1 and len(kwargs) == 0 and isinstance( kargs[0], CacheMode):
            return kargs[0]
        return super().__new__(cls)

    @property
    def read(self) -> bool:
        """ Whether to load any existing cached data. """
        return self._read

    @property
    def write(self) -> bool:
        """ Whether to cache newly computed data to disk. """
        return self._write

    @property
    def delete(self) -> bool:
        """ Whether to delete existing data. """
        return self._delete

    @property
    def del_incomp(self) -> bool:
        """ Whether to delete existing data if it is not compatible or has the wrong version. """
        return self._del_in

    def __str__(self) -> str:# NOQA
        return self.mode
    def __repr__(self) -> str:# NOQA
        return self.mode

    def __eq__(self, other) -> bool:# NOQA
        return self.mode == other
    def __neq__(self, other) -> bool:# NOQA
        return self.mode != other

    @property
    def is_off(self) -> bool:
        """ Whether this cache mode is OFF. """
        return self.mode == self.OFF

    @property
    def is_on(self) -> bool:
        """ Whether this cache mode is ON. """
        return self.mode == self.ON

    @property
    def is_gen(self) -> bool:
        """ Whether this cache mode is GEN. """
        return self.mode == self.GEN

    @property
    def is_update(self) -> bool:
        """ Whether this cache mode is UPDATE. """
        return self.mode == self.UPDATE

    @property
    def is_clear(self) -> bool:
        """ Whether this cache mode is CLEAR. """
        return self.mode == self.CLEAR

    @property
    def is_readonly(self) -> bool:
        """ Whether this cache mode is READONLY. """
        return self.mode == self.READONLY

class CacheController( object ):
    r"""
    Central control parameters for caching.
    
    When a parameter object of this type
    is assigned to a :class:`cdxcore.subdir.SubDir`,
    then it is passed on when sub-directories are
    created. This way all ``SubDir`` have the same
    caching behaviour.
    
    See :class:`cdxcore.subdir.CacheController` for
    a list of control parameters.

    Parameters
    ----------
        exclude_arg_types : list[type], optional
            List of types to exclude from producing unique ids from function arguments.
    
            Defaults to ``[Context]``.
            
        cache_mode : CacheMode, optional
            Top level cache control.
            Set to "OFF" to turn off all caching.
            Default is "ON".
            
        max_filename_length : int, optional
            Maximum filename length. If unique id's exceed the file name a hash of length
            ``hash_length`` will be intergated into the file name.
            See :class:`cdxcore.uniquehash.NamedUniqueHash`.
            Default is ``48``.
            
        hash_length : int, optional
            Length of the hash used to make sure each filename is unique
            See :class:`cdxcore.uniquehash.NamedUniqueHash`.
            Default is ``8``.
            
        debug_verbose : :class:`cdxcore.verbose.Context`, optional
            If not ``None`` print caching process messages to this object.
            
            Default is ``None``.
            
        keep_last_arguments : bool, optional
            Keep a dictionary of all parameters as string representations after each function call.
            If the function ``F`` was decorated using :meth:``cdxcore.subdir.SubDir.cache``,
            you can access this information via ``F.cache_info.last_arguments``.

            Note that strings are limited to 100 characters per argument to avoid memory
            overload when large objects are passed.    
            
            Default is ``False``.
    """
    
    def __init__(self, *,
                    exclude_arg_types  : list[type] = [Context],
                    cache_mode         : CacheMode = CacheMode.ON,
                    max_filename_length: int = 48,
                    hash_length        : int = 8,
                    debug_verbose      : Context = None,
                    keep_last_arguments: bool = False
                    ):
        """
        :meta private:
        """
        max_filename_length         = int(max_filename_length)
        hash_length                 = int(hash_length)
        assert max_filename_length>0, ("'max_filename_length' must be positive")
        assert hash_length>0 and hash_length<=max_filename_length, ("'hash_length' must be positive and at most 'max_filename_length'")
        assert max_filename_length>=hash_length, ("'hash_length' must not exceed 'max_filename_length")
        self.cache_mode             = CacheMode(cache_mode if not cache_mode is None else CacheMode.ON)
        self.debug_verbose          = Context(debug_verbose) if isinstance(debug_verbose, (int,str)) else debug_verbose
        self.exclude_arg_types      = set(exclude_arg_types) if not exclude_arg_types is None else None
        self.versioned              = PrettyObject()  # list
        self.labelledFileName       = NamedUniqueHash(max_length=max_filename_length,id_length=hash_length,filename_by=DEF_FILE_NAME_MAP)
        self.uniqueFileName         = UniqueLabel(max_length=max_filename_length,id_length=hash_length,filename_by=None)
        self.keep_last_arguments    = keep_last_arguments

default_cacheController = CacheController()
#

# ========================================================================
# SubDir
# ========================================================================

class SubDir(object):
    r"""
    ``SubDir`` implements a transparent i/o
    interface for storing data in files.
    
    **Directories**

    Instantiate a ``SubDir`` with a directory name. There are some
    pre-defined relative system paths the name can refer to::
    
        from cdxcore.subdir import SubDir
        parent  = SubDir("!/subdir")         # relative to system temp directory
        parent  = SubDir("~/subdir")         # relative to user home directory
        parent  = SubDir("./subdir")         # relative to current working directory (explicit)
        parent  = SubDir("subdir")           # relative to current working directory (implicit)
        parent  = SubDir("/tmp/subdir")      # absolute path (linux)
        parent  = SubDir("C:/temp/subdir")   # absolute path (windows)
        parent  = SubDir("")                 # current working directory
        
    Sub-directories can be generated in a number of ways::

        subDir = parent('subdir')              # using __call__
        subDir = SubDir('subdir', parent)      # explicit constructor
        subDir = SubDir('subdir', parent="!/") # explicit constructor with parent being a string

    Files managed by ``SubDir`` will usually have the same extension.
    This extension can be specified with ``ext``, or as part of the directory string::
        
        subDir = SubDir("~/subdir", ext="bin") # set extension to 'bin'
        subDir = SubDir("~/subdir;*.bin")      # set extension to 'bin'
                 
    Leaving the extension as default ``None`` allows ``SubDir`` to automatically use
    the extension associated with any specified format.

    **Copy Constructor**

    The constructor is shallow.

    **File I/O**

    Write data with :meth:`cdxcore.subdir.SubDir.write`::

        subDir.write('item3',item3)          # explicit
        subDir['item1'] = item1              # dictionary style

    Note that :meth:`cdxcore.subdir.SubDir.write` can write to multiple files at the same time.

    Read data with :meth:`cdxcore.subdir.SubDir.read`::

        item = subDir('item', 'i1')          # returns 'i1' if not found.
        item = subdir.read('item')           # returns None if not found
        item = subdir.read('item','i2')      # returns 'i2' if not found
        item = subDir['item']                # raises a KeyError if not found

    Treat files in a directory like dictionaries::

        for file in subDir:
            data = subDir[file]
            f(item, data)

        for file, data in subDir.items():
            f(item, data)

    Delete items::

        del subDir['item']                    # silently fails if 'item' does not exist
        subDir.delete('item')                 # silently fails if 'item' does not exist
        subDir.delete('item', True)           # raises a KeyError if 'item' does not exit

    Cleaning up::

        parent.delete_all_content()        # silently deletes all files with matching extensions, and sub directories.

    **File Format**

    ``SubDir`` supports a number of file formats via :class:`cdxcore.subdir.Format`.
    Those can be controlled with the ``fmt`` keyword in various functions not least
    :class:`cdxcore.subdir.SubDir`::

        subdir = SubDir("!/.test", fmt=SubDir.JSON_PICKLE)

    See :class:`cdxcore.subdir.Format` for supported formats.

    Parameters
    ----------
        name : str:
            Name of the directory.
            
            The name may start with any of the following special characters:

            * ``'.'`` for current directory.
            * ``'~'`` for home directory.
            * ``'!'`` for system default temp directory.
            * ``'?'`` for a temporary temp directory. In this case ``delete_everything_upon_exit`` is always ``True``.
 
            The directory name may also contain a formatting string for defining ``ext`` on the fly:
            for example use ``"!/test;*.bin"`` to specify a directory ``"test"`` in the user's
            temp directory with extension ``"bin"``.
            
            The directory name can be set to ``None`` in which case it is always empty
            and attempts to write to it fail with  :class:`EOFError`.
            
        parent : str | SubDir, optional
            Parent directory. 
            
            If ``parent`` is a :class:`cdxcore.subdir.SubDir` then its parameters are used
            as default values here.

            Default is ``None``.
            
        ext : str, optional
            Extension for files managed by this ``SubDir``. All files will share the same extension.

            If set to ``""`` no extension is assigned to this directory. That means, for example, that
            :meth:`cdxcore.subdir.SubDir.files` returns all files contained in the directory, not
            just files with a specific extension.
            
            If ``None``, use an extension depending on ``fmt``:
                
            * 'pck' for the default PICKLE format.
            * 'json' for JSON_PLAIN.
            * 'jpck' for JSON_PICKLE.
            * 'zbsc' for BLOSC.
            * 'pgz' for GZIP.
            
            Default is ``None``.
            
        fmt : :class:`cdxcore.subdir.Format`, optional

            One of the :class:`cdxcore.subdir.Format` codes.
            If ``ext`` is left to ``None`` then setting the a format will also set the corrsponding ``ext``.
            
            Default is ``Format.PICKLE``.

        create_directory : bool | None, optional
        
            Whether to create the directory upon creation of the ``SubDir`` object; otherwise it will be created upon first
            :meth:`cdxcore.subdir.SubDir.write`.
            
            Set to ``None`` to use the setting of the parent directory, or ``False`` if no parent
            is specified.
            
            Default is ``False``.

        cache_controller : :class:`cdxcore.subdir.CacheController`, optional
        
            An object which fine-tunes the behaviour of :meth:`cdxcore.subdir.SubDir.cache`.
            See that function's documentation for further details. Default is ``None``.

        delete_everything : bool, optional
        
            Delete all contents in the newly defined sub directory upon creation.

            Default is ``False``.
            
        delete_everything_upon_exit : bool, optional
        
            Delete all contents of the current exist if ``self`` is deleted.
            This is the always ``True`` if the ``"?/"`` pretext was used.
            
            Note, however, that this will only be executed once the object is garbage collected.

            Default is, for some good reason, ``False``.            
    """

    class __RETURN_SUB_DIRECTORY(object):
        pass
    """ :meta private: """

    Format = Format # :meta private
    """ The same as :class:`cdxcore.subdir.Format` for convenience """
    
    PICKLE = Format.PICKLE     
    """ :meta private: """
    
    JSON_PICKLE = Format.JSON_PICKLE
    """ :meta private: """
    
    JSON_PLAIN = Format.JSON_PLAIN
    """ :meta private: """
    
    BLOSC = Format.BLOSC
    """ :meta private: """
    
    GZIP = Format.GZIP
    """ :meta private: """
    
    RETURN_SUB_DIRECTORY = __RETURN_SUB_DIRECTORY
    """ :meta private: """
    
    DEFAULT_FORMAT = Format.PICKLE
    """ Default :class:`cdxcore.subdir.Format`: ``Format.PICKLE`` """
    
    EXT_FMT_AUTO = "*"
    """ :meta private: """

    MAX_VERSION_BINARY_LEN = 128
    """ :meta private: """
    
    VER_NORMAL   = 0
    """ :meta private: """
    VER_CHECK    = 1
    """ :meta private: """
    VER_RETURN   = 2
    """ :meta private: """

    def __init__(self, name : str, 
                       parent : str|type = None, *, 
                       ext : str = None, 
                       fmt : Format = None, 
                       create_directory : bool = None,
                       cache_controller : CacheController = None,
                       delete_everything : bool = False,
                       delete_everything_upon_exit : bool = False
                       ):
        """
        Instantiates a sub directory which contains files with a common extension.

        """
        create_directory = bool(create_directory) if not create_directory is None else None
        
        # copy constructor support
        if isinstance(name, SubDir):
            assert parent is None, "Internal error: copy construction does not accept 'parent' keyword"
            self._path   = name._path
            self._ext    = name._ext if ext is None else ext
            self._fmt    = name._fmt if fmt is None else fmt
            self._crt    = name._crt if create_directory is None else create_directory
            self._cctrl  = name._cctrl if cache_controller is None else cache_controller
            self._tclean = False # "_clean" is not inherited
            if delete_everything: raise ValueError( "Cannot use 'delete_everything' when cloning a directory")
            return

        # reconstruction from a dictionary
        if isinstance(name, Mapping):
            assert parent is None, "Internal error: dictionary construction does not accept 'parent keyword"
            self._path   = name['_path']
            self._ext    = name['_ext'] if ext is None else ext
            self._fmt    = name['_fmt'] if fmt is None else fmt
            self._crt    = name['_crt'] if create_directory is None else create_directory
            self._cctrl  = name['_cctrl'] if cache_controller is None else cache_controller
            self._tclean = name['_tclean']
            if delete_everything: raise ValueError( "Cannot use 'delete_everything' when cloning a directory")
            return

        # parent
        if isinstance(parent, str):
            parent = SubDir( parent, ext=ext, fmt=fmt, create_directory=create_directory, cache_controller=cache_controller )
        if not parent is None and not isinstance(parent, SubDir):
            raise ValueError( "'parent' must be SubDir, str, or None. Found object of type '{type(parent)}'")

        # operational flags
        _name  = name if not name is None else "(none)"

        # format
        if fmt is None:
            assert parent is None or not parent._fmt is None
            self._fmt = parent._fmt if not parent is None else self.DEFAULT_FORMAT
            assert not self._fmt is None
        else:
            self._fmt = fmt
            assert not self._fmt is None

        # extension
        if not name is None:
            if not isinstance(name, str): raise ValueError( txtfmt("'name' must be string. Found object of type %s", type(name) ))
            name   = name.replace('\\','/')

            # avoid windows file names on Linux
            if platform.system() != "Windows" and name[1:3] == ":/":
                raise ValueError( txtfmt("Detected use of windows-style drive declaration %s in path %s.", name[:3], name ))

            # extract extension information
            ext_i = name.find(";*.")
            if ext_i >= 0:
                _ext = name[ext_i+3:]
                if not ext is None and ext != _ext:
                    raise ValueError( txtfmt("Canot specify an extension both in the name string ('%s') and as 'ext' ('%s')", _name, ext))
                ext  = _ext
                name = name[:ext_i]
        if ext is None:
            self._ext = self.EXT_FMT_AUTO if parent is None else parent._ext
        else:
            self._ext = SubDir._extract_ext(ext)
            
        # create_directory
        if create_directory is None:
            self._crt = False if parent is None else parent._crt
        else:
            self._crt = bool(create_directory)
            
        # cache controller
        assert cache_controller is None or type(cache_controller).__name__ == CacheController.__name__, ("'cache_controller' should be of type 'CacheController'", type(cache_controller))
        self._cctrl = cache_controller

        # name
        self._tclean = delete_everything_upon_exit  # delete directory upon completion
        if name is None:
            if not parent is None and not parent._path is None:
                name = parent._path[:-1]
        else:
            # expand name
            name = _remove_trailing(name)
            if name == "" and parent is None:
                name = "."
            if name[:1] in ['!', '~', '?'] or name[:2] == "./" or name == ".":
                if len(name) > 1 and name[1] != '/':
                    raise ValueError( txtfmt("If 'name' starts with '%s', then the second character must be '/' (or '\\' on windows). Found 'name' set to '%s'", name[:1], _name ))
                if name[0] == '!':
                    name = SubDir.temp_dir()[:-1] + name[1:]
                elif name[0] == ".":
                    name = SubDir.working_dir()[:-1] + name[1:]
                elif name[0] == "?":
                    name = SubDir.temp_temp_dir()[:-1] + name[1:]
                    self._tclean = True
                else:
                    assert name[0] == "~", ("Internal error", name[0] )
                    name = SubDir.user_dir()[:-1] + name[1:]
            elif name == "..":
                error("Cannot use name '..'")
            elif not parent is None:
                # path relative to 'parent'
                if not parent.is_none:
                    name    = os.path.join( parent._path, name )

        # create directory/clean up
        if name is None:
            self._path = None
        else:
            # expand path
            self._path = os.path.abspath(name) + '/'
            self._path = self._path.replace('\\','/')

            if delete_everything:
                self.delete_everything(keep_directory=self._crt)
            if self._crt:
                self.create_directory()
                
    def __del__(self):
        """
        Delete all of the current directory if ``tclean`` is ``True``
        """
        if self._tclean:
            self.delete_everything(keep_directory=False)

    @staticmethod
    def expand_std_root( name ):
        """
        Expands ``name`` by a standardized root directory if provided:
            
        The first character of ``name`` can be either of:
            
        * ``"!"`` returns :meth:`cdxcore.subdir.SubDir.temp_dir()`.
        * ``"."`` returns :meth:`cdxcore.subdir.SubDir.working_dir()`.
        * ``"~"`` returns :meth:`cdxcore.subdir.SubDir.user_dir()`.
        
        If neither of these matches the first character, ``name``
        is returned as is.
        
        This function does not support ``"?"``.
        """
        if len(name) < 2 or name[0] not in ['.','!','~'] or name[1] not in ["\\","/"]:
            return name
        if name[0] == '!':
            return SubDir.temp_dir() + name[2:]
        elif name[0] == ".":
            return SubDir.working_dir() + name[2:]
        else:
            return SubDir.user_dir() + name[2:]

    def create_directory( self ):
        """
        Creates the current directory if it doesn't exist yet.
        """
        # create directory/clean up
        if self._path is None:
            return
        # create directory
        if not os.path.exists( self._path[:-1] ):
            try:
                os.makedirs( self._path[:-1] )
                return
            except FileExistsError:
                pass
        if not os.path.isdir(self._path[:-1]):
            raise NotADirectoryError(txtfmt( "Cannot use sub directory %s: object exists but is not a directory", self._path[:-1] ))

    def path_exists(self) -> bool:
        """ Whether the current directory exists """
        return os.path.exists( self._path[:-1] ) if not self._path is None else False
        
    # -- a few basic properties --

    def __str__(self) -> str: # NOQA
        if self._path is None: return "(none)"
        ext = self.ext
        return self._path if len(ext) == 0 else self._path + ";*" + ext

    def __repr__(self) -> str: # NOQA
        if self._path is None: return "SubDir(None)"
        return "SubDir(%s)" % self.__str__()

    def __eq__(self, other) -> bool: # NOQA
        """ Tests equality between to SubDirs, or between a SubDir and a directory """
        if isinstance(other,str):
            return self._path == other
        verify( isinstance(other,SubDir), "Cannot compare SubDir to object of type '%s'", type(other).__name__, exception=TypeError )
        return self._path == other._path and self._ext == other._ext and self._fmt == other._fmt

    def __bool__(self) -> bool:
        """ Returns True if 'self' is set, or False if 'self' is a None directory """
        return not self.is_none

    def __hash__(self) -> str: #NOQA
        return hash( (self._path, self._ext, self._fmt) )

    @property
    def is_none(self) -> bool:
        """ Whether this object is ``None`` or not. For such ``SubDir`` object no files exists, and writing any file will fail. """
        return self._path is None

    @property
    def path(self) -> str:
        """
        Return current path, including trailing ``'/'``.
        
        Note that the path may not exist yet. If existence is required, consider using
        :meth:`cdxcore.subdir.SubDir.existing_path`.
        """
        return self._path

    @property
    def existing_path(self) -> str:
        """
        Return current path, including training ``'/'``.
        
        ``existing_path`` ensures that the directory structure exists (or raises an exception).
        Use :meth:`cdxcore.subdir.SubDir.path` if creation on the fly is not desired.
        """
        self.create_directory()
        return self.path

    @property
    def fmt(self) -> Format:
        """ Returns current :class:`cdxcore.subdir.Format`. """
        return self._fmt
    
    @property
    def ext(self) -> str:
        """
        Returns the common extension of the files in this directory, including leading ``'.'``.
        Resolves ``"*"`` into the extension associated with the current :class:`cdxcore.subdir.Format`.
        """
        return self._ext if self._ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def auto_ext( self, ext_or_fmt : str|Format = None ) -> str:
        """
        Computes the effective extension based on theh inputs ``ext_or_fmt``,
        and the current settings for ``self``.

        If ``ext_or_fmt`` is set to ``"*"`` then the extension associated to
        the format of ``self`` is returned.
        
        Parameters
        ----------
            ext_or_fmt : str or :class:`cdxcore.subdir.Format`
                An extension or a format.
        
        Returns
        -------
            ext : str
                The extension with leading ``'.'``.
        """
        if isinstance(ext_or_fmt, Format):
            return self._auto_ext(ext_or_fmt)
        else:
            ext = self._ext if ext_or_fmt is None else SubDir._extract_ext(ext_or_fmt)
            return ext if ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def auto_ext_fmt( self, *, ext : str = None, fmt : Format = None ) -> tuple[str]:
        """
        Computes the effective extension and format based on inputs ``ext`` and ``fmt``,
        each of which defaults to the respective values of ``self``.

        Resolves an ``ext`` of ``"*"`` into the extension associated with ``fmt``.

        Returns
        -------
            (ext, fmt) : tuple
                Here ``ext`` contains the leading ``'.'`` and ``fmt`` is
                of type :class:`cdxcore.subdir.Format`.
        """
        if isinstance(ext, Format):
            verify( fmt is None or fmt == ext, "If 'ext' is a Format, then 'fmt' must match 'ext' or be None. Found '%s' and '%s', respectively.", ext, fmt, exception=ValueError )
            return self._auto_ext(ext), ext

        fmt = fmt if not fmt is None else self._fmt
        ext = self._ext if ext is None else SubDir._extract_ext(ext)
        ext = ext if ext != self.EXT_FMT_AUTO else self._auto_ext(fmt)
        return ext, fmt
    
    @property
    def cache_controller(self):
        """ Returns an assigned :class:`cdxcore.subdir.CacheController`, or ``None`` """
        return self._cctrl if not self._cctrl is None else default_cacheController
    
    @property
    def cache_mode(self):
        """ Returns the :class:`cdxcore.subdir.CacheMode` associated with the underlying cache controller """
        return self.cache_controller.cache_mode

    # -- static helpers --

    @staticmethod
    def _auto_ext( fmt : Format ) -> str:
        """ Default extension for a given format, including leading '.' """
        if fmt == Format.PICKLE:
            return ".pck"
        if fmt == Format.JSON_PLAIN:
            return ".json"
        if fmt == Format.JSON_PICKLE:
            return ".jpck"
        if fmt == Format.BLOSC:
            return ".zbsc"
        if fmt == Format.GZIP:
            return ".pgz"
        error("Unknown format '%s'", str(fmt))

    @staticmethod
    def _version_to_bytes( version : str ) -> bytearray:
        """
        Convert string version to byte string of at most size
        :data:`cdxcore.subdir.SubDir.MAX_VERSION_BINARY_LEN` + 1
        """
        if version is None:
            return None
        version_    = bytearray(version,'utf-8')
        if len(version_) >= SubDir.MAX_VERSION_BINARY_LEN:
            raise ValueError(txtfmt("Cannot use version '%s': when translated into a bytearray it exceeds the maximum version lengths of '%ld' (byte string is '%s')", version, SubDir.MAX_VERSION_BINARY_LEN-1, version_ ))
        ver_        = bytearray(SubDir.MAX_VERSION_BINARY_LEN)
        l           = len(version_)
        ver_[0]     = l
        ver_[1:1+l] = version_
        assert len(ver_) == SubDir.MAX_VERSION_BINARY_LEN, ("Internal error", len(ver_), ver_)
        return ver_
    
    @staticmethod
    def _extract_ext( ext : str ) -> str:
        """
        Checks that 'ext' is an extension, and returns .ext.
        -- Accepts '.ext' and 'ext'
        -- Detects use of directories
        -- Returns '*' if ext='*'
        """
        assert not ext is None, ("'ext' should not be None here")
        verify( isinstance(ext,str), "Extension 'ext' must be a string. Found type %s", type(ext).__name__, exception=ValueError )
        # auto?
        if ext == SubDir.EXT_FMT_AUTO:
            return SubDir.EXT_FMT_AUTO        
        # remove leading '.'s
        while ext[:1] == ".":
            ext = ext[1:]
        # empty extension -> match all files
        if ext == "":
            return ""
        # ensure extension has no directiory information
        sub, _ = os.path.split(ext)
        verify( len(sub) == 0, "Extension '%s' contains directory information", ext)

        # remove internal characters
        verify( ext[0] != "!", "Extension '%s' cannot start with '!' (this symbol indicates the temp directory)", ext, exception=ValueError )
        verify( ext[0] != "~", "Extension '%s' cannot start with '~' (this symbol indicates the user's directory)", ext, exception=ValueError )
        return "." + ext
            
    # -- public utilities --

    def full_file_name(self, file : str, *, ext : str = None) -> str:
        """
        Returns fully qualified file name.
        
        The function tests that ``file`` does not contain directory information.

        Parameters
        ----------
            file : str
                Core file name without path or extension.
            ext : str
                If not ``None``, use this extension rather than :attr:`cdxcore.subdir.SubDir.ext`.

        Returns
        -------
            Filename : str
                Fully qualified system file name.
                If ``self`` is ``None``, then this function returns ``None``; if ``file`` is ``None`` then this function also returns ``None``.
        """
        if self._path is None or file is None:
            return None
        file = str(file)
        verify( len(file) > 0, "'file' cannot be empty")

        sub, _ = os.path.split(file)
        verify( len(sub) == 0, "Key '%s' contains directory information", file)

        verify( file[0] != "!", "Key '%s' cannot start with '!' (this symbol indicates the temp directory)", file, exception=ValueError )
        verify( file[0] != "~", "Key '%s' cannot start with '~' (this symbol indicates the user's directory)", file, exception=ValueError )
        verify( file[0] != "?", "Key '%s' cannot start with '?' (this symbol indicates the user's directory)", file, exception=ValueError )

        ext = self.auto_ext( ext )
        if len(ext) > 0 and file[-len(ext):] != ext:
            return self._path + file + ext
        return self._path + file
    full_file_name = full_file_name # backwards compatibility

    @staticmethod
    def temp_dir() -> str:
        """
        Return system temp directory. Short-cut to :func:`tempfile.gettempdir`.
        Result contains trailing ``'/'``.
        """
        d = tempfile.gettempdir()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-1", d)
        return d + "/"

    @staticmethod
    def temp_temp_dir() -> str:
        """
        Return a temporary temp directory name using :func:`tempfile.mkdtemp`. 
        Noet that this function will return a different directory upon every function call.

        It is strongly recommended to clean up after usage, for example using the pattern::
            
            from cdxcore.subdir import SubDir
            import shutil
            
            try:
                tmp_dir = SubDir.temp_temp_dir()
                
                ...
            finally:
                shutil.rmtree(tmp_dir)
 
        Result contains trailing ``'/'``.
        """
        d = tempfile.mkdtemp()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-1", d)
        return d + "/"

    @staticmethod
    def working_dir() -> str:
        """
        Return current working directory. Short-cut for :func:`os.getcwd`.
        Result contains trailing ``'/'``.
        """
        d = os.getcwd()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-2", d)
        return d + "/"

    @staticmethod
    def user_dir() -> str:
        """
        Return current working directory. Short-cut for :func:`os.path.expanduser` with parameter ``' '``.
        Result contains trailing ``'/'``.
        """
        d = os.path.expanduser('~')
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-3", d)
        return d + "/"

    # -- read --

    def _read_reader( self, reader, file : str, default, raise_on_error : bool, *, ext : str = None ):
        """
        Utility function for read() and readLine()

        Parameters
        ----------
            reader( file, full_file_name, default )
                A function which is called to read the file once the correct directory is identified
                file : file (for error messages, might include '/')
                full_file_name : full file name
                default value
            file : str or list
                str: fully qualified file
                list: list of fully qualified names
            default :
                default value. None is a valid default value
                list : list of defaults for a list of keys
            raise_on_error : bool
                If True, and the file does not exist, throw exception
            ext :
                Extension or None for current extension.
                list : list of extensions for a list of keys
        """
        # vector version
        if not isinstance(file,str):
            if not isinstance(file, Collection): raise ValueError(txtfmt( "'file' must be a string, or an interable object. Found type %s", type(file)))
            l = len(file)
            if default is None or isinstance(default,str) or not isinstance(default, Collection):
                default = [ default ] * l
            else:
                if len(default) != l: raise ValueError(txtfmt("'default' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(default), l ))
            if ext is None or isinstance(ext, str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: raise ValueError(txtfmt("'ext' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(ext), l ))
            return [ self._read_reader(reader=reader,file=k,default=d,raise_on_error=raise_on_error,ext=e) for k, d, e in zip(file,default,ext) ]

        # deleted directory?
        if self._path is None:
            verify( not raise_on_error, "Trying to read '%s' from an empty directory object", file, exception=NotADirectoryError)
            return default

        # single file
        if len(file) == 0: raise ValueError(txtfmt("'file' missing (the filename)" ))
        sub, key_ = os.path.split(file)
        if len(sub) > 0:
            return self(sub)._read_reader(reader=reader,file=key_,default=default,raise_on_error=raise_on_error,ext=ext)
        if len(key_) == 0: ValueError(txtfmt("'file' %s indicates a directory, not a file", file))

        # don't try if directory doesn't exist
        full_file_name = self.full_file_name(file,ext=ext)
        if not self.path_exists():
            if raise_on_error:
                raise KeyError(file, full_file_name)
            return default
        
        # does file exit?
        if not os.path.exists(full_file_name):
            if raise_on_error:
                raise KeyError(file,full_file_name)
            return default
        if not os.path.isfile(full_file_name):
            raise IOError(txtfmt( "Cannot read '%s': object exists, but is not a file (full path %s)", file, full_file_name ))

        # read content
        # delete existing files upon read error
        try:
            return reader( file, full_file_name, default )
        except EOFError as e:
            try:
                os.remove(full_file_name)
                warn("Cannot read '%s'; file deleted (full path '%s').\nError: %s",file,full_file_name, str(e))
            except Exception as e:
                warn("Cannot read '%s'; subsequent attempt to delete file failed (full path '%s''): %s",file,full_file_name,str(e))
        except FileNotFoundError as e:
            if raise_on_error:
                raise KeyError(file, full_file_name, str(e)) from e
        except VersionError as e:
            if raise_on_error:
                raise e
        except VersionPresentError as e:
            if raise_on_error:
                raise e
        except Exception as e:
            if raise_on_error:
                raise KeyError(file, full_file_name, str(e)) from e
        except (ImportError, BaseException) as e:
            e.add_note( file )
            e.add_note( full_file_name )
            raise e
        return default

    def _read( self, file : str,
                    default = None,
                    raise_on_error : bool = False,
                    *,
                    version : str = None,
                    ext : str = None,
                    fmt : Format = None,
                    delete_wrong_version : bool = True,
                    handle_version : int = 0
                    ):
        """ See read() """
        ext, fmt = self.auto_ext_fmt(ext=ext, fmt=fmt)
        version  = str(version) if not version is None else None
        version  = version if handle_version != SubDir.VER_RETURN else ""
        assert not fmt == self.EXT_FMT_AUTO, ("'fmt' is '*' ...?")

        if version is None and fmt in [Format.BLOSC, Format.GZIP]:
            # blosc and gzip have unexpected side effects
            # a version is attempted to be read but is not present
            # (e.g. blosc causes a MemoryError)
            version = ""            

        def reader( file, full_file_name, default ):
            test_version = "(unknown)"
            
            def handle_pickle_error(e):
                err = "invalid load key, '\\x03'."
                if not version is None or e.args[0] != err:
                    raise e
                raise VersionPresentError(
                                   f"Error reading '{full_file_name}': encountered an unpickling error '{err}' "+\
                                   f"while attempting to read file using {str(fmt)}. "+\
                                    "This is likely caused by attempting to read a file which was written with "+\
                                    "version information without providing a test version during read(). If the version is of the file "+\
                                    "is not important, use `version=\"*\"'", e) from e
            if fmt == Format.PICKLE:
                # we do not read any version information if not requested
                with open(full_file_name,"rb") as f:
                    # handle version as byte string
                    ok      = True
                    if not version is None:
                        test_len     = int( f.read( 1 )[0] )
                        test_version = f.read(test_len)
                        test_version = test_version.decode("utf-8")
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return True
                        try:
                            data = pickle.load(f)
                        except pickle.UnpicklingError as e:
                            handle_pickle_error(e)
                        return data

            elif fmt == Format.BLOSC:
                # we do not write 
                # any version information if not requested
                with open(full_file_name,"rb") as f:
                    # handle version as byte string
                    ok      = True
                    if not version is None: # it's never None
                        test_len     = int( f.read( 1 )[0] )
                        test_version = f.read(test_len)
                        test_version = test_version.decode("utf-8")
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return True
                        nnbb       = f.read(2)
                        num_blocks = int.from_bytes( nnbb, 'big', signed=False )
                        data       = bytearray()
                        for i in range(num_blocks):
                            blockl = int.from_bytes( f.read(6), 'big', signed=False )
                            if blockl>0:
                                bdata  = blosc.decompress( f.read(blockl) )
                                data  += bdata
                                del bdata
                        try:
                            data = pickle.loads(data)
                        except pickle.UnpicklingError as e:
                            handle_pickle_error(e)
                        return data

            elif fmt == Format.GZIP:
                # always read version information
                with gzip.open(full_file_name,"rb") as f:
                    # handle version as byte string
                    ok      = True
                    if not version is None: # it's never None
                        test_len     = int( f.read( 1 )[0] )
                        test_version = f.read(test_len)
                        test_version = test_version.decode("utf-8")
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return True
                        data = pickle.load(f)
                        return data

            elif fmt in [Format.JSON_PLAIN, Format.JSON_PICKLE]:
                # only read version information if requested
                with open(full_file_name,"rt",encoding="utf-8") as f:
                    # handle versioning
                    ok      = True
                    if not version is None:
                        test_version = f.readline()
                        if test_version[:2] != "# ":
                            raise VersionError("Error reading '{full_file_name}' using {fmt}: file does not appear to contain a version (it should start with '# ')",
                                               version_found="",
                                               version_expected=version)                                               
                        test_version = test_version[2:]
                        if test_version[-1:] == "\n":
                            test_version = test_version[:-1]
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return ok
                        # read
                        if fmt == Format.JSON_PICKLE:
                            jsonpickle = _import_jsonpickle()
                            return jsonpickle.decode( f.read() )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: unknown Format", fmt)
                            return json.loads( f.read() )
            else:
                raise NotImplementedError(fmt, txtfmt("Unknown format '%s'", fmt ))

            # arrive here if version is wrong
            # delete a wrong version

            if version == "":
                raise VersionPresentError(f"Error reading '{full_file_name}' using {fmt}: the file has version '{test_version}', but was attempted to be read without "+\
                                           "a test version. If you intended to accept any version, use 'version=\"*\"' instead.")

            deleted = ""
            if delete_wrong_version:
                try:
                    os.remove(full_file_name)
                    e = None
                except Exception as e_:
                    e = str(e_)
            if handle_version == SubDir.VER_CHECK:
                return False
            if not raise_on_error:
                return default
            deleted = " (file was deleted)" if e is None else " (attempt to delete file failed: %s)" % e
            raise VersionError( f"Error reading '{full_file_name}' using {fmt}: found version '{test_version}' not '{version}'{deleted}",
                                version_found=test_version,
                                version_expected=version
                                )

        return self._read_reader( reader=reader, file=file, default=default, raise_on_error=raise_on_error, ext=ext )

    def read( self, file : str,
                    default = None,
                    raise_on_error : bool = False,
                    *,
                    version : str = None,
                    delete_wrong_version : bool = True,
                    ext : str = None,
                    fmt : Format = None
                    ):
        """
        Read data from a file if the file exists, or return ``default``.

        * Supports ``file`` containing directory information.
        * Supports ``file`` (and ``default``as well as ``ext``) being iterable.
          Examples::
              
            from cdxcore.subdir import SubDir
            files = ['file1', 'file2']
            sd = SubDir("!/test")

            sd.read( files )          # both files are using default None
            sd.read( files, 1 )       # both files are using default '1'
            sd.read( files, [1,2] )   # files use defaults 1 and 2, respectively

            sd.read( files, [1] )      # produces error as len(keys) != len([1])

          Strings are iterable but are treated as single value.
          Therefore::
              
            sd.read( files, '12' )      # the default value '12' is used for both files
            sd.read( files, ['1','2'] ) # use defaults '1' and '2', respectively

        Parameters
        ----------
            file : str
                A file name or a list thereof. ``file`` may contain subdirectories.
                
            default :
                Default value, or default values if ``file`` is a list.
                
            raise_on_error : bool
                Whether to raise an exception if reading an existing file failed.
                By default this function fails silently and returns the default.
                
            version : str
                If not ``None``, specifies the version of the current code base.
                
                In this case, this version will be compared to the version of the file being read.
                If they do not match, read fails (either by returning default or throwing a :class:`cdxcore.version.VersionError` exception).

                You can specify version ``"*"`` to accept any version.
                Note that this is distinct
                to using ``None`` which stipulates that the file should not 
                have version information.
                
            delete_wrong_version : bool
                If ``True``, and if a wrong version was found, delete the file.

            ext : str
                Extension overwrite, or a list thereof if ``file`` is a list.
                
                Use:
                    
                * ``None`` to use directory's default.
                * ``'*'`` to use the extension implied by ``fmt``.
                * ``""`` to turn of extension management.
                
            fmt : :class:`cdxcore.subdir.Format`
                File :class:`cdxcore.subdir.Format` or ``None`` to use the directory's default.
                
                Note:
                    
                * ``fmt`` cannot be a list even if ``file`` is.
                * Unless ``ext`` or the SubDir's extension is ``'*'``, changing the format does not automatically change the extension.

        Returns
        -------
            Content 
                For a single ``file`` returns the content of the file if successfully read, or ``default`` otherwise.
                If ``file``` is a list: list of contents.
                
        Raises
        ------
            :class:`cdxcore.version.VersionError`:
                If the file's version did not match the ``version`` provided.
                
        """
        return self._read( file=file,
                           default=default,
                           raise_on_error=raise_on_error,
                           version=version,
                           ext=ext,
                           fmt=fmt,
                           delete_wrong_version=delete_wrong_version,
                           handle_version=SubDir.VER_NORMAL )

    def is_version( self, file : str, version : str = None, raise_on_error : bool = False, *, ext : str = None, fmt : Format = None, delete_wrong_version : bool = True ):
        """
        Tests the version of a file.

        Parameters
        ----------
            file : str
                A filename, or a list thereof.
 
            version : str
                Specifies the version to compare the file's version with.
                
                You can use ``"*"`` to match any version.

            raise_on_error : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
 
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete ``file``.
                
            ext : str
                Extension overwrite, or a list thereof if file is a list.
                
                Set to:
                    
                * ``None`` to use directory's default.
                * ``"*"`` to use the extension implied by ``fmt``.
                * ``""`` for no extension.
                
            fmt : :class:`cdxcore.subdir.Format`
                File format or ``None`` to use the directory's default.
                Note that ``fmt`` cannot be a list even if ``file`` is.

        Returns
        -------
            Status : bool
                Returns `True` only if the file exists, has version information, and its version is equal to ``version``.
        """
        return self._read( file=file,default=False,raise_on_error=raise_on_error,version=version,ext=ext,fmt=fmt,delete_wrong_version=delete_wrong_version,handle_version=SubDir.VER_CHECK )

    def get_version( self, file : str, raise_on_error : bool = False, *, ext : str = None, fmt : Format = None ):
        """
        Returns a version stored in a file.
        
        This requires that the file has previously been saved with a version.
        Otherwise this function will have unpredictable results.

        Parameters
        ----------
            file : str
                A filename, or a list thereof. 

            raise_on_error : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
 
            delete_wrong_version : bool
                If ``True``, and if a wrong version was found, delete ``file``.
                
            ext : str
                Extension overwrite, or a list thereof if ``file`` is a list.
                
                Set to:
                    
                * ``None`` to use directory's default.
                * ``"*"`` to use the extension implied by ``fmt``.
                * ``""`` for no extension.
                
            fmt : :class:`cdxcore.subdir.Format`
                File format or ``None`` to use the directory's default.
                Note that ``fmt`` cannot be a list even if ``file`` is.

        Returns
        -------
            version : str
        """
        return self._read( file=file,default=None,raise_on_error=raise_on_error,version="",ext=ext,fmt=fmt,delete_wrong_version=False,handle_version=SubDir.VER_RETURN )

    def read_string( self, file : str, default = None, raise_on_error : bool = False, *, ext : str = None ) -> str:
        """
        Reads text from a file. Removes trailing EOLs.
        
        Returns the read string, or a list of strings if ``file`` was iterable.
        """
        verify( not isinstance(ext, Format), "Cannot change format when writing strings. Found extension '%s'", ext)
        ext = ext if not ext is None else self._ext
        ext = ext if ext != self.EXT_FMT_AUTO else ".txt"

        def reader( file, full_file_name, default ):
            with open(full_file_name,"rt",encoding="utf-8") as f:
                line = f.readline()
                if len(line) > 0 and line[-1] == '\n':
                    line = line[:-1]
                return line
        return self._read_reader( reader=reader, file=file, default=default, raise_on_error=raise_on_error, ext=ext )

    # -- write --

    def _write( self, writer, file : str, obj, raise_on_error : bool, *, ext : str = None ) -> bool:
        """ Utility function for write() and writeLine() """
        if self._path is None:
            raise EOFError("Cannot write to '%s': current directory is not specified" % file)
        self.create_directory()

        # vector version
        if not isinstance(file,str):
            if not isinstance(file, Collection): error( "'file' must be a string or an interable object. Found type %s", type(file), exception=ValueError)
            l = len(file)
            if obj is None or isinstance(obj,str) or not isinstance(obj, Collection):
                obj = [ obj ] * l
            else:
                if len(obj) != l: error("'obj' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(obj), l, exception=ValueError )
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(ext), l, exception=ValueError )
            ok = True
            for k,o,e in zip(file,obj,ext):
                ok |= self._write( writer, k, o, raise_on_error=raise_on_error, ext=e )
            return ok

        # single file
        if not len(file) > 0: error("'file is empty (the filename)" )
        sub, file = os.path.split(file)
        if len(file) == 0: error("'file '%s' refers to a directory, not a file", file)
        if len(sub) > 0:
            return SubDir(sub,parent=self)._write(writer,file,obj, raise_on_error=raise_on_error,ext=ext )

        # write to temp file, then rename into target file
        # this reduces collision when i/o operations are slow
        full_file_name = self.full_file_name(file,ext=ext)
        tmp_file       = self.temp_file_name( file )
        tmp_i          = 0
        fullTmpFile    = self.full_file_name(tmp_file,ext="tmp" if not ext=="tmp" else "_tmp")
        while os.path.exists(fullTmpFile):
            fullTmpFile = self.full_file_name(tmp_file) + "." + str(tmp_i) + ".tmp"
            tmp_i       += 1
            if tmp_i >= 10:
                raise RuntimeError("Failed to generate temporary file for writing '%s': too many temporary files found. For example, this file already exists: '%s'" % ( full_file_name, fullTmpFile ) )

        # write
        if not writer( file, fullTmpFile, obj ):
            return False
        assert os.path.exists(fullTmpFile), ("Internal error: file does not exist ...?", fullTmpFile, full_file_name)
        try:
            if os.path.exists(full_file_name):
                os.remove(full_file_name)
            os.rename(fullTmpFile, full_file_name)
        except Exception as e:
            os.remove(fullTmpFile)
            if raise_on_error:
                raise e
            return False
        return True

    def write( self, file : str,
                     obj,
                     raise_on_error : bool = True,
                     *,
                     version : str = None,
                     ext : str = None,
                     fmt : Format = None ) -> bool:
        """
        Writes an object to file.
        
        * Supports ``file`` containing directories.
        * Supports ``file`` being a list.
          In this case, if ``obj`` is an iterable it is considered the list of values for the elements of ``file``.
          If ``obj`` is not iterable, it will be written into all files from ``file``::

              from cdxcore.subdir import SubDir

              keys = ['file1', 'file2']
              sd = SubDir("!/test")
              sd.write( keys, 1 )               # works, writes '1' in both files.
              sd.write( keys, [1,2] )           # works, writes 1 and 2, respectively
              sd.write( keys, "12" )            # works, writes '12' in both files
              sd.write( keys, [1] )             # produces error as len(keys) != len(obj)

        If the current directory is ``None``, then the function raises an :class:`EOFError` exception.

        Parameters
        ----------
            file : str
                Core filename, or list thereof.
                
            obj :
                Object to write, or list thereof if ``file`` is a list.
                
            raise_on_error : bool
                If ``False``, this function will return ``False`` upon failure.

            version : str
                If not ``None``, specifies the version of the code which generated ``obj``.
                This version will be written to the beginning of the file.

            ext : str
                Extension, or list thereof if ``file`` is a list.
                
                * Use ``None`` to use directory's default extension.
                * Use ``"*"`` to use the extension implied by ``fmt``.

            fmt : :class:`cdxcore.subdir.Format`
                File format or ``None`` to use the directory's default.
                Note that ``fmt`` cannot be a list even if ``file`` is.
                Note that unless ``ext`` or the SubDir's extension is '*',
                changing the format does not automatically change the extension used.

        Returns
        -------
            Success : bool         
                Boolean to indicate success if ``raise_on_error`` is ``False``.
        """
        ext, fmt = self.auto_ext_fmt(ext=ext, fmt=fmt)
        version  = str(version) if not version is None else None
        assert ext != self.EXT_FMT_AUTO, ("'ext' is '*'...?")

        if version=='*': error("You cannot write version '*'. Use None to write a file without version.")
        
        if version is None and fmt in [Format.BLOSC, Format.GZIP]:
            # blosc and gzip have unexpected side effects
            # a version is attempted to be read but is not present
            # (e.g. blosc causes a MemoryError)
            version = ""            

        def writer( file, full_file_name, obj ):
            try:
                if fmt == Format.PICKLE:
                    # only if a version is provided write it into the file
                    with open(full_file_name,"wb") as f:
                        # handle version as byte string
                        if not version is None:
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: error("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        pickle.dump(obj,f,-1)

                elif fmt == Format.BLOSC:
                    # only if a version is provided write it into the file
                    with open(full_file_name,"wb") as f:
                        # handle version as byte string
                        if not version is None: # it's never None
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: error("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        pdata      = pickle.dumps(obj)  # returns data as a bytes object
                        del obj
                        len_data   = len(pdata)
                        num_blocks = max(0,len_data-1) // _BLOSC_MAX_USE + 1
                        f.write(num_blocks.to_bytes(2, 'big', signed=False))
                        for i in range(num_blocks):
                            start  = i*_BLOSC_MAX_USE
                            end    = min(len_data,start+_BLOSC_MAX_USE)
                            assert end>start, ("Internal error; nothing to write")
                            block  = blosc.compress( pdata[start:end] )
                            blockl = len(block)
                            f.write( blockl.to_bytes(6, 'big', signed=False) )
                            if blockl > 0:
                                f.write( block )
                            del block
                        del pdata

                elif fmt == Format.GZIP:
                    # only if a version is provided write it into the file
                    with gzip.open(full_file_name,"wb") as f:
                        # handle version as byte string
                        if not version is None: # it's never None
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: error("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        pickle.dump(obj,f,-1)

                elif fmt in [Format.JSON_PLAIN, Format.JSON_PICKLE]:
                    # only if a version is provided write it into the file
                    with open(full_file_name,"wt",encoding="utf-8") as f:
                        if not version is None:
                            f.write("# " + version + "\n")
                        if fmt == Format.JSON_PICKLE:
                            jsonpickle = _import_jsonpickle()
                            f.write( jsonpickle.encode(obj) )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: invalid Format", fmt)
                            f.write( json.dumps( plain(obj, sorted_dicts=True, native_np=True, dt_to_str=True ), default=str ) )

                else:
                    raise NotImplementedError(fmt, txtfmt("Internal error: invalid format '%s'", fmt))
            except Exception as e:
                if raise_on_error:
                    raise e
                return False
            return True
        return self._write( writer=writer, file=file, obj=obj, raise_on_error=raise_on_error, ext=ext )

    def write_string( self, file : str, line : str, raise_on_error : bool = True, *, ext : str = None ) -> bool:
        """
        Writes a line of text into a file.
        
        * Supports ``file``` containing directories.
        * Supports ``file``` being a list.
          In this case, ``line`` can either be the same value for all file's or a list, too.

        If the current directory is ``None``, then the function throws an EOFError exception
        """
        verify( not isinstance(ext, Format), "Cannot change format when writing strings. Found extension '%s'", ext, exception=ValueError )
        ext = ext if not ext is None else self._ext
        ext = ext if ext != self.EXT_FMT_AUTO else ".txt"
        
        if len(line) == 0 or line[-1] != '\n':
            line += '\n'
        def writer( file, full_file_name, obj ):
            try:
                with open(full_file_name,"wt",encoding="utf-8") as f:
                    f.write(obj)
            except Exception as e:
                if raise_on_error:
                    raise e
                return False
            return True
        return self._write( writer=writer, file=file, obj=line, raise_on_error=raise_on_error, ext=ext )

    # -- iterate --

    def files(self, *, ext : str = None) -> list:
        """
        Returns a list of files in this subdirectory with the current extension, or the specified extension.

        In other words, if the extension is ".pck", and the files are "file1.pck", "file2.pck", "file3.bin"
        then this function will return [ "file1", "file2" ]

        If ``ext`` is:
        
        * ``None``, then the directory's default extension will be used.
        * ``""`` then this function will return all files in this directory.
        * ``"*"`` then the extension corresponding to the current format will be used.

        This function ignores directories. Use :meth:`cdxcore.subdir.SubDir.sub_dirs` to retrieve those.
        """
        if not self.path_exists():
            return []
        ext   = self.auto_ext( ext )
        ext_l = len(ext)
        keys = []
        with os.scandir(self._path) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                if ext_l > 0:
                    if len(entry.name) <= ext_l or entry.name[-ext_l:] != ext:
                        continue
                    keys.append( entry.name[:-ext_l] )
                else:
                    keys.append( entry.name )
        return keys

    def sub_dirs(self) -> list:
        """
        Retrieve a list of all sub directories.
        
        If ``self`` does not refer to an existing directory, then this function returns an empty list.
        """
        # do not do anything if the object was deleted
        if not self.path_exists():
            return []
        subdirs = []
        with os.scandir(self._path[:-1]) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                subdirs.append( entry.name )
        return subdirs

    # -- delete --

    def delete( self, file : str, raise_on_error: bool  = False, *, ext : str = None ):
        """
        Deletes ``file``.
        
        This function will quietly fail if ``file`` does not exist unless ``raise_on_error``
        is set to ``True``.

        Parameters
        ----------
            file :
                filename, or list of filenames
                
            raise_on_error : bool, default ``False``
                If ``False``, do not throw :class:`KeyError` if file does not exist
                or another error occurs.
                
            ext : str | None, default ``None``
                Extension, or list thereof if ``file`` is a list.
                
                Use
                
                * ``None`` for the directory default.
                * ``""`` to not use an automatic extension.
                * ``"*"`` to use the extension associated with the format of the directory.
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raise_on_error: raise EOFError("Cannot delete '%s': current directory not specified" % file)
            return
            
        # vector version
        if not isinstance(file,str):
            if not isinstance(file, Collection): error( "'file' must be a string or an interable object. Found type %s", type(file))
            l = len(file)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(ext), l )
            for k, e in zip(file,ext):
                self.delete(k, raise_on_error=raise_on_error, ext=e)
            return

        # handle directories in 'file'
        if len(file) == 0: error( "'file' is empty" )
        sub, key_ = os.path.split(file)
        if len(key_) == 0: error("'file' %s indicates a directory, not a file", file)
        if len(sub) > 0: return SubDir(sub,parent=self).delete(key_,raise_on_error=raise_on_error,ext=ext)
        # don't try if directory doesn't existy
        if not self.path_exists():
            if raise_on_error:
                raise KeyError(file)
            return        
        full_file_name = self.full_file_name(file, ext=ext)
        if not os.path.exists(full_file_name):
            if raise_on_error:
                raise KeyError(file)
        else:
            os.remove(full_file_name)

    def delete_all_files( self, raise_on_error : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys in this sub directory with the correct extension.
        
        Parameters
        ----------
            raise_on_error : bool
                Set to ``False`` to quietly ignore errors.
                
            ext : str
                Extension to be used:
                    
                * ``None`` for the directory default.
                * ``""`` to not use an automatic extension.
                * ``"*"`` to use the extension associated with the format of the directory.
        """
        if self._path is None:
            if raise_on_error: raise EOFError("Cannot delete all files: current directory not specified")
            return
        if not self.path_exists():
            return
        self.delete( self.files(ext=ext), raise_on_error=raise_on_error, ext=ext )

    def delete_all_content( self, delete_self : bool = False, raise_on_error : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys and subdirectories in this sub directory.
        
        Does not delete files with other extensions.
        Use :meth:`cdxcore.subdir.SubDir.delete_everything` if the aim is to delete, well, everything.

        Parameters
        ----------
            delete_self: bool
                Whether to delete the directory itself as well, or only its contents.
            raise_on_error: bool
                ``False`` for silent failure
            ext: str
                Extension for keys, or ``None`` for the directory's default.
                Use ``""`` to match all files regardless of extension.
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raise_on_error: raise EOFError("Cannot delete all contents: current directory not specified")
            return
        if not self.path_exists():
            return
        # delete sub directories
        subdirs = self.sub_dirs();
        for subdir in subdirs:
            SubDir(subdir, parent=self).delete_all_content( delete_self=True, raise_on_error=raise_on_error, ext=ext )
        # delete keys
        self.delete_all_files( raise_on_error=raise_on_error,ext=ext )
        # delete myself
        if not delete_self:
            return
        rest = list( os.scandir(self._path[:-1]) )
        txt = str(rest)
        txt = txt if len(txt) < 50 else (txt[:47] + '...')
        if len(rest) > 0:
            if raise_on_error: error( "Cannot delete my own directory %s: directory not empty: found %ld object(s): %s", self._path,len(rest), txt)
            return
        os.rmdir(self._path[:-1])   ## does not work ????
        self._path = None

    def delete_everything( self, keep_directory : bool = True ):
        """
        Deletes the entire sub directory will all contents.
        
        *WARNING:* deletes *all* files and sub-directories, not just those with the present extension.
        If ``keep_directory`` is ``False``, the directory referred to by this object will also be deleted.
        In this case, ``self`` will be set to ``None``.
        """
        if self._path is None:
            return
        if not self.path_exists():
            return
        shutil.rmtree(self._path[:-1], ignore_errors=True)
        if not keep_directory and os.path.exists(self._path[:-1]):
            os.rmdir(self._path[:-1])
            self._path = None
        elif keep_directory and not os.path.exists(self._path[:-1]):
            os.makedirs(self._path[:-1])

    # -- file ops --

    def exists(self, file : str, *, ext : str = None ) -> bool:
        """
        Checks whether a file exists.

        Parameters
        ----------
            file :
                Filename, or list of filenames.
                
            ext : str
                Extension, or list thereof if ``file`` is a list.
                
                Use
                
                * ``None`` for the directory default.
                * ``""`` to not use an automatic extension.
                * ``"*"`` to use the extension associated with the format of the directory.

        Returns
        -------
            Status : bool
                If ``file`` is a string, returns ``True`` or ``False``, else it will return a list of ``bool`` values.
        """
        # vector version
        if not isinstance(file,str):
            verify( isinstance(file, Collection), "'file' must be a string or an interable object. Found type %s", type(file))
            l = len(file)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.exists(k,ext=e) for k,e in zip(file,ext) ]
        # empty directory
        if self._path is None:
            return False
        # handle directories in 'file'
        if len(file) == 0: raise ValueError("'file' missing (the filename)")
        sub, key_ = os.path.split(file)
        if len(key_) == 0: raise IsADirectoryError( file, txtfmt("'file' %s indicates a directory, not a file", file) )
        if len(sub) > 0:
            return self(sub).exists(file=key_,ext=ext)
        # if directory doesn't exit
        if not self.path_exists():
            return False
        # single file
        full_file_name = self.full_file_name(file, ext=ext)
        if not os.path.exists(full_file_name):
            return False
        if not os.path.isfile(full_file_name):
            raise IsADirectoryError("Structural error: file %s: exists, but is not a file (full path %s)",file,full_file_name)
        return True
    
    def _getFileProperty( self, *, file : str, ext : str, func ):
        # vector version
        if not isinstance(file,str):
            verify( isinstance(file, Collection), "'file' must be a string or an interable object. Found type %s", type(file))
            l = len(file)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'file' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self._getFileProperty(file=k,ext=e,func=func) for k,e in zip(file,ext) ]
        # empty directory
        if self._path is None:
            return None
        # handle directories in 'file'
        if len(file) == 0: raise ValueError("'file' missing (the filename)")
        sub, key_ = os.path.split(file)
        if len(key_) == 0: raise IsADirectoryError( file, txtfmt("'file' %s indicates a directory, not a file", file) )
        if len(sub) > 0: return self(sub)._getFileProperty(file=key_,ext=ext,func=func)
        # if directory doesn't exit
        if not self.path_exists():
            return None
        # single file
        full_file_name = self.full_file_name(file, ext=ext)
        if not os.path.exists(full_file_name):
            return None
        return func(full_file_name)

    def get_creation_time( self, file : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the creation time of a file.
        
        See comments on :func:`os.path.getctime` for system compatibility information.

        Parameters
        ----------
            file :
                filename, or list of filenames.
            ext :
                Extension, or list thereof if ``file`` is an extension.
                Use:
                    
                * ``None`` for the directory default.
                * ``""`` for no automatic extension.
                * A :class:`cdxcore.subdir.Format` to use the default extension for that format.

        Returns
        -------
            Datetime : :class:`datetime.datetime`
                A single ``datetime`` if ``file`` is a string, otherwise a list of ``datetime``'s.
                Returns ``None`` if an error occured.
        """
        return self._getFileProperty( file=file, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getctime(x)) )

    def get_last_modification_time( self, file : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last modification time a file.
        
        See comments on :func:`os.path.getmtime` for system compatibility information.

        Parameters
        ----------
            file :
                filename, or list of filenames.
            ext :
                Extension, or list thereof if ``file`` is an extension.
                Use:
                    
                * ``None`` for the directory default.
                * ``""`` for no automatic extension.
                * A :class:`cdxcore.subdir.Format` to use the default extension for that format.

        Returns
        -------
            Datetime : :class:`datetime.datetime`
                A single ``datetime`` if ``file`` is a string, otherwise a list of ``datetime``'s.
                Returns ``None`` if an error occured.
        """
        return self._getFileProperty( file=file, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getmtime(x)) )

    def get_last_access_time( self, file : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last access time of a file.
        
        See comments on :func:`os.path.getatime` for system compatibility information.

        Parameters
        ----------
            file : str
                Filename, or list of filenames.

            ext : str
                Extension, or list thereof if ``file`` is an extension.
                    
                * Use ``None`` for the directory default.
                * Use ``""`` for no automatic extension.

        Returns
        -------
            Datetime : :class:`datetime.datetime`
                A single ``datetime`` if ``file`` is a string, otherwise a list of ``datetime``'s.
                Returns ``None`` if an error occured.
        """
        return self._getFileProperty( file=file, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getatime(x)) )

    def file_size( self, file : str, *, ext : str = None ) -> int:
        """
        Returns the file size of a file.
        
        See comments on :func:`os.path.getatime` for system compatibility information.

        Parameters
        ----------
            file : str
                Filename, or list of filenames.

            ext : str
                Extension, or list thereof if ``file`` is an extension.
                    
                * Use ``None`` for the directory default.
                * Use ``""`` for no automatic extension.

        Returns
        -------
            File size if ``file``, or ``None`` if an error occured.
        """
        return self._getFileProperty( file=file, ext=ext, func=lambda x : os.path.getsize(x) )

    def rename( self, source : str, target : str, *, ext : str = None ):
        """
        Rename a file.
        
        This function will raise an exception if not successful.

        Parameters
        ----------
            source, target : str
                Filenames.
                
            ext : str
                Extension.
                
                * Use ``None`` for the directory default.
                * Use ``""`` for no automatic extension.
        """
        # empty directory
        if self._path is None:
            return

        # handle directories in 'source'
        if len(source) == 0: raise ValueError("'source' missing (the filename)")
        sub, source_ = os.path.split(source)
        if len(source_) == 0: raise IsADirectoryError( source, txtfmt("'source' %s indicates a directory, not a file", source ))
        if len(sub) > 0:
            src_full = self(sub).full_file_name(file=source_,ext=ext)
        else:
            src_full = self.full_file_name( source, ext=ext )
            
        # handle directories in 'target'
        if len(target) == 0: raise ValueError("'target' missing (the filename)" )
        sub, target_ = os.path.split(target)
        if len(target_) == 0: raise IsADirectoryError( target, txtfmt("'target' %s indicates a directory, not a file", target))
        if len(sub) > 0:
            tar_dir  = self(sub)
            tar_dir.create_directory()
            tar_full = tar_dir.full_file_name(file=target_,ext=ext)
        else:
            tar_full = self.full_file_name( target, ext=ext )
            self.create_directory()
            
        os.rename(src_full, tar_full)

    # utilities
    
    def temp_file_name( self, file : str|None = None ):
        """
        Returns a unique temporary file name.
        
        The file name is generated by applying a unique hash
        to the current directory, ``file``, the current process and thread IDs, and
        :func:`datetime.datetime.now`.
        
        If ``file`` is not ``None`` it will be used as a label.
        
        This function returns just the file name. Use :meth:`cdxcore.subdir.SubDir.full_temp_file_name`
        to get a full temporary file name including path and extension.

        Parameters
        ----------
        file : str | None, default ``None``
            An optional file. If provided, :func:`cdxcore.uniquehash.named_unique_filename48_8`
            is used to generate the temporary file which means that a portion of ``file``
            will head the returned temporary name.
            
            If ``file`` is ``None``, :func:`cdxcore.uniquehash.unique_hash48`
            is used to generate a 48 character hash.

        Returns
        -------
            Temporary file name : str
                The file name.
        """
        if file is None or file=="":
            return unique_hash48( str(self), file, uuid.getnode(), os.getpid(), threading.get_ident(), datetime.datetime.now() )
        else:
            return named_unique_filename48_8( file, str(self), uuid.getnode(), os.getpid(), threading.get_ident(), datetime.datetime.now() )
    
    def full_temp_file_name(self, file : str|None = None, *, ext : str | None = None, create_directory : bool = False ):
        """
        Returns a fully qualified unique temporary file name with path and extension
        
        The file name is generated by applying a unique hash
        to the current directory, ``file``, the current process and thread IDs, and
        :func:`datetime.datetime.now`.
        
        If ``file`` is not ``None`` it will be used as a label.
        
        This function returns the fully qualified file name. Use :meth:`cdxcore.subdir.SubDir.temp_file_name`
        to only a file name.

        Parameters
        ----------
        file : str | None, default ``None``
            An optional file. If provided, :func:`cdxcore.uniquehash.named_unique_filename48_8`
            is used to generate the temporary file which means that a portion of ``file``
            will head the returned temporary name.
            
            If ``file`` is ``None``, :func:`cdxcore.uniquehash.unique_hash48`
            is used to generate a 48 character hash.

        ext : str | None, default ``None``
            Extension to use, or ``None`` for the extrension of ``self``.

        Returns
        -------
            Temporary file name : str
                The fully qualified file name.
        """
        if create_directory:
            self.create_directory()
        return self.full_file_name( self.temp_file_name(file), ext=ext )
    
    
    @staticmethod
    def remove_bad_file_characters( file : str, by : str="default" ) -> str:
        """
        Replaces invalid characters in a filename using the map ``by``.
        
        See :func:`cdxcore.util.fmt_filename` for documentation and further options.
        """
        return fmt_filename( file, by=by )
   
    if False:
        def unqiueLabelToKey( self, unique_label:str, id_length:int=8, separator:str='-', max_length:int=64 ) -> str:
            """
            Converts a unique label which might contain invalid characters into a unique file name, such that the full file name does not exceed 'max_length' bytes.
            The returned file has the format 
                name + separator + ID
            where ID has length id_length.
            If unique_label is already guaranteed to be a valid filename, use unqiueLongFileNameToKey() instead.
            """
            len_ext      = len(self.ext)
            assert len_ext < max_length, ("'max_length' must exceed the length of the extension", max_length, self.ext)
            uqf          = UniqueLabel( max_length=max_length-len_ext, id_length=id_length, separator=separator, filename_by="default" )
            return uqf( unique_label )
       
        def unqiueLongFileNameToKey( self, unique_filename:str, id_length:int=8, separator:str='-', max_length:int=64 ) -> str:
            """
            Converts a unique filename which might be too long to a unique filename such that the total length plus 'ext' does not exceed 'max_length' bytes.
            If the filename is already short enough, no change is made.
    
            If 'unique_filename' is not guaranteed to be a valid filename, use unqiueLabelToKey() instead.
            """
            len_ext      = len(self.ext)
            assert len_ext < max_length, ("'max_length' must exceed the length of the extension", max_length, self.ext)
            uqf          = UniqueLabel( max_length=max_length-len_ext, id_length=id_length, separator=separator )
            return uqf( unique_filename )
   
    # -- dict-like interface --

    def __call__(self, element : str,
                       default = RETURN_SUB_DIRECTORY,
                       raise_on_error : bool = False,
                       *,
                       version : str|None = None,
                       ext : str|None = None,
                       fmt : Format|None = None,
                       delete_wrong_version : bool = True,
                       create_directory : bool|None = None ):
        """
        Read either data from a file, or return a new sub directory.
        
        If only the ``element`` argument is used, then this function returns a new sub directory
        named ``element``.
        
        If both ``element`` and ``default`` arguments are used, then this function attempts to read the file ``element``
        from disk, returning ``default`` if it does not exist.

        Assume we have a subdirectory ``sd``::
        
            from cdxcore.subdir import SubDir
            sd  = SubDir("!/test")

        Reading files::
            
            x   = sd('file', None)                   # reads 'file' with default value None
            x   = sd('sd/file', default=1)           # reads 'file' from sub directory 'sd' with default value 1
            x   = sd('file', default=1, ext="tmp")   # reads 'file.tmp' with default value 1

        Create sub directory::
            
            sd2 = sd("subdir")                       # creates and returns handle to subdirectory 'subdir'
            sd2 = sd("subdir1/subdir2")              # creates and returns handle to subdirectory 'subdir1/subdir2'
            sd2 = sd("subdir1/subdir2", ext=".tmp")  # creates and returns handle to subdirectory 'subdir1/subdir2' with extension "tmp"
            sd2 = sd(ext=".tmp")                     # returns handle to current subdirectory with extension "tmp"

        Parameters
        ----------
            element : str
                File or directory name, or a list thereof.
                
            default : optional
                If specified, this function reads ``element`` with
                ``read( element, default, *args, **kwargs )``.

                If ``default`` is not specified, then this function returns a new sub-directory by calling
                ``SubDir(element,parent=self,ext=ext,fmt=fmt)``.

            create_directory : bool, default ``None``
                *When creating sub-directories:*
                
                Whether or not to instantly create the sub-directory. The default, ``None``, is to inherit the behaviour from ``self``.
                
            raise_on_error : bool, default ``False``
                *When reading files:*
                
                Whether to raise an exception if reading an existing file failed.
                By default this function fails silently and returns ``default``.
                
            version : str | None, default ``None``
                *When reading files:*
                
                If not ``None``, specifies the version of the current code base.
                
                In this case, this version will be compared to the version of the file being read.
                If they do not match, read fails (either by returning default or throwing a :class:`cdxcore.version.VersionError` exception).

                You can specify version ``"*"`` to accept any version.
                Note that this is distinct
                to using ``None`` which stipulates that the file should not 
                have version information.

            delete_wrong_version : bool, default ``True``.
                *When reading files:*
                
                If ``True``, and if a wrong version was found, delete the file.

            ext : str | None, default is ``None``.
                *When reading files:*
                
                Extension to be used, or a list thereof if ``element`` is a list. Defaults
                to the extension of ``self``.
                
                Semantics:
                    
                * ``None`` to use the default extension of ``self``.
                * ``"*"`` to use the extension implied by ``fmt``.
                * ``""`` to turn off extension management.

                *When creating sub-directories:*
                
                Extension for the new subdirectory; set to ``None`` to inherit the parent's extension.

            fmt : :class:`cdxcore.subdir.Format` | None, default ``None``
                *When reading files:*
                
                File format or ``None`` to use the directory's default.
                Note that ``fmt`` cannot be a list even if ``element`` is.
                Unless 
                ``ext`` or the SubDir's extension is ``"*"``, changing the
                format does not automatically change the extension.

                *When creating sub-directories:*
                
                Format for the new sub-directory; set to ``None`` to inherit the parent's format.
                                
        Returns
        -------
        Object : type | SubDir
            Either the value in the file, a new sub directory, or lists thereof.
        """
        if default == SubDir.RETURN_SUB_DIRECTORY:
            if not isinstance(element, str):
                if not isinstance(element, Collection): 
                    raise ValueError(txtfmt("'element' must be a string or an iterable object. Found type '%s;", type(element)))
                return [ SubDir( k,parent=self,ext=ext,fmt=fmt,create_directory=create_directory) for k in element ]
            return SubDir(element,parent=self,ext=ext,fmt=fmt,create_directory=create_directory)
        return self.read( file=element,
                          default=default,
                          raise_on_error=raise_on_error,
                          version=version,
                          delete_wrong_version=delete_wrong_version,
                          ext=ext,
                          fmt=fmt )

    def __getitem__( self, file ):
        """
        Reads ``file`` using :meth:`cdxcore.subdir.SubDir.read`.
        If '`file'` does not exist, throw a :class:`KeyError`.
        """
        return self.read( file=file, default=None, raise_on_error=True )

    def __setitem__( self, file, value):
        """ Writes ``value`` to ``file`` using :meth:`cdxcore.subdir.SubDir.write`. """
        self.write(file,value)

    def __delitem__(self,file):
        """ Silently delete ``file`` using :meth:`cdxcore.subdir.SubDir.delete`. """
        self.delete(file, False )

    def __len__(self) -> int:
        """ Return the number of files in this directory with matching extension. """
        return len(self.files())

    def __iter__(self):
        """ Returns an iterator which allows traversing through all files below in this directory with matching extension. """
        return self.files().__iter__()

    def __contains__(self, file):
        """ Tests whether ``file`` :meth:`cdxcore.subdir.SubDir.exists`. """
        return self.exists(file)
    
    def items(self, *, ext : str|None = None, raise_on_error : bool = False) -> Iterable:
        """
        Dictionary-style iterable of filenames and their content.

        Usage::
            
            subdir = SubDir("!")
            for file, data in subdir.items():
                print( file, str(data)[:100] )

        Parameters
        ----------
            ext : str | None, default ``None``
                Extension or ``None`` for the directory's current extension. Use ``""``
                for all file extension.
        
        Returns
        -------
            Iterable
                An iterable generator
        """       
        class ItemIterable(Iterable):
            def __init__(_):
                _._files  = self.files(ext=ext)
                _._subdir = self
            def __len__(_):
                return len(_._files)
            def __iter__(_):
                for file in _._files:
                    data = _._subdir.read(file, ext=ext, raise_on_error=raise_on_error)
                    yield file, data
        return ItemIterable()

    # convenient path ops
    # -------------------
    
    def __add__(self, directory : str) -> str:
        """
        Returns a the subdirectory ``directory`` of ``self``.
        """
        return SubDir(directory,parent=self)

    # pickling
    # --------
    
    def __getstate__(self):
        """ Return state to pickle """
        return dict( path=self._path, ext=self._ext, fmt=self._fmt, crt=self._crt )    

    def __setstate__(self, state):
        """ Restore pickle """
        self._path = state['path']
        self._ext = state['ext']
        self._fmt = state['fmt']
        self._crt = state['crt']

    @staticmethod
    def as_format( format_name : str ) -> int:
        """
        Converts a named format into the respective format code.
        
        Example::
        
            format = SubDir.as_format( config("format", "pickle", SubDir.FORMAT_NAMES, "File format") )    
        """
        format_name = format_name.upper()
        if not format_name in SubDir.FORMAT_NAMES:
            raise LookupError(f"Unknown format name '{format_name}'. Must be one of: {fmt_list(SubDir.FORMAT_NAMES)}")
        return Format[format_name]
    

    # caching
    # -------

    def cache( self,  version             : str = None , *,
                      dependencies        : list = None, 
                      label               : Callable = None,
                      uid                 : Callable = None,
                      name                : str = None, 
                      exclude_args        : list[str] = None,
                      include_args        : list[str] = None,
                      exclude_arg_types   : list[type] = None,
                      version_auto_class  : bool = True):
        """
        Advanced versioned caching for callables.
        
        Versioned caching is based on the following two simple principles:
            
        1) **Unique Call IDs:**

           When a function is called with some parameters, the wrapper identifies a unique ID based
           on the qualified name of the function and on its runtime functional parameters (ie those
           which alter the outcome of the function).
           When a function is called the first time with a given unique call ID, it will store
           the result of the call to disk. If the function is called with the same call ID again,
           the result is read from disk and returned.

           To compute unique call IDs :class:`cdxcore.uniquehash.NamedUniqueHash` is used
           by default.

        2) **Code Version:**
    
           Each function has a version, which includes dependencies on other functions or classes.
           If the version of data on disk does not match the current version, it is deleted
           and the generating function is called again. This way you can use your code to drive updates
           to data generated with cached functions.               
           
           Behind the scenes this is implemented using :dec:`cdxcore.version.version` which means
           that the version of a cached function can also depend on versions of non-cached functions
           or other objects.
           
        Caching Functions
        ^^^^^^^^^^^^^^^^^
        
        Caching a simple function ``f`` is staight forward:

        .. code-block:: python

            from cdxcore.subdir import SubDir
            cache   = SubDir("!/.cache")
            cache.delete_all_content()   # for illustration
            
            @cache.cache("0.1")
            def f(x,y):
                return x*y
            
            _ = f(1,2)    # function gets computed and the result cached
            _ = f(1,2)    # restore result from cache
            _ = f(2,2)    # different parameters: compute and store result

        Cache another function ``g`` which calls ``f``, and whose version therefore on ``f``'s version:
        
        .. code-block:: python

            @cache.cache("0.1", dependencies=[f])
            def g(x,y):
                return g(x,y)**2

        **Debugging**
        
        When using automated caching it
        is important to understand how changes in parameters and the version of the a function
        affect caching. To this end, :dec:`cdxcore.subdir.SubDir.cache` supports
        a tracing mechanism via the use of a :class:`cdxcore.subdir.CacheController`:

        .. code-block:: python

            from cdxcore.subdir import SubDir, CacheController, Context
            
            ctrl    = CacheController( debug_verbose=Context("all") )
            cache   = SubDir("!/.cache", cache_controller=ctrl )
            cache.delete_all_content()   # <- delete previous cached files, for this example only
            
            @cache.cache("0.1")
            def f(x,y):
                return x*y
            
            _ = f(1,2)    # function gets computed and the result cached
            _ = f(1,2)    # restore result from cache
            _ = f(2,2)    # different parameters: compute and store result
            
        Returns:

        .. code-block:: python
            
            00: cache(f@__main__): function registered for caching into 'C:/Users/hans/AppData/Local/Temp/.cache/'.
            00: cache(f@__main__): called 'f@__main__' version 'version 0.1' and wrote result into 'C:/Users/hans/AppData/Local/Temp/.cache/f@__main__ 668a6b111549e288.pck'.
            00: cache(f@__main__): read 'f@__main__' version 'version 0.1' from cache 'C:/Users/hans/AppData/Local/Temp/.cache/f@__main__ 668a6b111549e288.pck'.
            00: cache(f@__main__): called 'f@__main__' version 'version 0.1' and wrote result into 'C:/Users/hans/AppData/Local/Temp/.cache/f@__main__ b5609542d7da0b04.pck'.
            
        **Non-Functional Parameters**

        A function may have non-functional parameters which do not alter the function's outcome.
        An example are ``debug`` flags:

        .. code-block:: python
                         
            from cdxcore.subdir import SubDir
            cache   = SubDir("!/.cache")

            @cache.cache("0.1", dependencies=[f], exclude_args='debug')
            def g(x,y,debug): # <--' 'debug' is a non-functional parameter
                if debug:
                    print(f"h(x={x},y={y})")  
                return g(x,y)**2
                         
        You can define certain types as non-functional for *all* functions wrapped
        by :meth:`cdxcore.subdir.SubDir.cache` when construcing
        the :class:`cdccore.cache.CacheController` parameter for in :class:`cdxcore.subdir.SubDir`:
        
        .. code-block:: python

            from cdxcore.subdir import SubDir
            
            class Debugger:
                def output( cond, message ):
                    print(message)
            
            ctrl    = CacheController(exclude_arg_types=[Debugger])   # <- exclude 'Debugger' parameters from hasing
            cache   = SubDir("!/.cache")

            @cache.cache("0.1", dependencies=[f], exclude_args='debug')
            def g(x,y,debugger : Debugger): # <-- 'debugger' is a non-functional parameter
                debugger.output(f"h(x={x},y={y})")  
                return g(x,y)**2
            
        **Unique IDs and File Naming**
                         
        The unique call ID of a decorated functions is by default generated by its fully qualified name
        and a unique hash of its functional parameters.
        
        Key default behaviours of :class:`cdxcore.uniquehash.NamedUniqueHash`:
            
        * The ``NamedUniqueHash`` hashes objects via their ``__dict__`` or ``__slot__`` members.
          This can be overwritten for a class by implementing ``__unique_hash__``; see :class:`cdxcore.uniquehash.NamedUniqueHash`.
          
        * Function members of objects or any members starting with '_' are not hashed
          unless this behaviour is changed using :class:`cdxcore.subdir.CacheController`.
          
        * Numpy and panda frames are hashed using their byte representation.
          That is slow and not recommended. It is better to identify numpy/panda inputs
          via their generating characteristic ID.
                           
        Either way, hashes are not particularly human readable. It is often useful
        to have unique IDs and therefore filenames which carry some context information.
        
        This can be achieved by using ``label``:

        .. code-block:: python

            from cdxcore.subdir import SubDir, CacheController
            ctrl    = CacheController( debug_verbose=Context("all") )
            cache   = SubDir("!/.cache", cache_controller=ctrl )
            cache.delete_all_content()   # for illustration
            
            @cache.cache("0.1")                     # <- no ID 
            def f1(x,y):
                return x*y
            
            @cache.cache("0.1", label="f2({x},{y})") # <- label uses a string to be passed to str.format()
            def f2(x,y):
                return x*y
            
        We can also use a function to generate a ``label``. In that case all parameters
        to the function including its ``name`` are passed to the function. In below example
        we eat any parameters we are not interested in with ``** _``:

        .. code-block:: python

            @cache.cache("0.1", label=lambda x,y,**_: f"h({x},{y})", exclude_args='debug') 
            def h(x,y,debug=False):
                if debug:
                    print(f"h(x={x},y={y})")  
                return x*y

        We obtain:

        .. code-block:: python

            f1(1,1)
            f2(1,1)
            h(1,1)        
            
            00: cache(f1@__main__): function registered for caching into 'C:/Users/hans/AppData/Local/Temp/.cache/'.
            00: cache(f2@__main__): function registered for caching into 'C:/Users/hans/AppData/Local/Temp/.cache/'.
            00: cache(h@__main__): function registered for caching into 'C:/Users/hans/AppData/Local/Temp/.cache/'.
            00: cache(f1@__main__): called 'f1@__main__' version 'version 0.1' and wrote result into 'C:/Users/hans/AppData/Local/Temp/.cache/f1@__main__ ef197d80d6a0bbb0.pck'.
            00: cache(f2@__main__): called 'f2(1,1)' version 'version 0.1' and wrote result into 'C:/Users/hans/AppData/Local/Temp/.cache/f2(1,1) bdc3cd99157c10f7.pck'.
            00: cache(h@__main__): called 'h(1,1)' version 'version 0.1' and wrote result into 'C:/Users/hans/AppData/Local/Temp/.cache/h(1,1) d3fdafc9182070f4.pck'.            

        Note that the file names ``f2(1,1) bdc3cd99157c10f7.pck``
        and ``h(1,1) d3fdafc9182070f4.pck`` for the ``f2`` and ``h`` function calls are now easier to read as
        they are comprised of the label
        of the function and a terminal hash key.
        The trailing hash is appended because we do not assume that the label returned by ``label`` is unique.
        Therefore, a hash generated from all the ``label`` itself and
        all pertinent arguments will be appended to the filename.
        
        If we know how to generate truly unique IDs which are always valid filenames, then we can use ``uid``
        instead of ``label``:
        
        .. code-block:: python

            @cache.cache("0.1", uid=lambda x,y,**_: f"h2({x},{y})", exclude_args='debug') 
            def h2(x,y,debug=False):
                if debug:
                    print(f"h(x={x},y={y})")  
                return x*y
            h2(1,1)
            
        yields::
            
            00: cache(h2@__main__): function registered for caching into 'C:/Users/hans/AppData/Local/Temp/.cache/'.
            00: cache(h2@__main__): called 'h2(1,1)' version 'version 0.1' and wrote result into 'C:/Users/hans/AppData/Local/Temp/.cache/h2(1,1).pck'.            
            
        In particular, the filename is now ``h2(1,1).pck`` without any hash.
        If ``uid`` is used the parameter of the function are not hashed. Like ``label`` 
        the parameter ``uid`` can also be a :func:`str.format` string or a callable.
            
        **Controlliong which Parameters to Hash**
            
        To specify which parameters are pertinent for identifying a unique id, use:
            
        * ``include_args``: list of functions arguments to include. If ``None``, use all parameteres as input in the next step
        
        * ``exclude_args``: list of function arguments to exclude, if not ``None``.
        
        * ``exclude_arg_types``: a list of types to exclude.
          This is helpful if control flow is managed with dedicated data types.
          An example of such a type is :class:`cdxcore.verbose.Context` which is used to print hierarchical output messages.
          Types can be globally excluded using a :class:`cdccore.cache.CacheController`
          when calling
          :class:`cdxcore.subdir.SubDir`.
                       
        **Numpy/Pandas**

        Numpy/Panda data should not be hashed for identifying unique call IDs.
        Instead, use the defining characteristics for generating the data frames.
        
        For example:

        .. code-block:: python
            
            from cdxcore.pretty import PrettyObject
            from cdxcore.subdir import SubDir
            cache   = SubDir("!/.cache")
            cache.delete_all_content()   # for illustration
            
            @cache.cache("0.1")
            def load_src( src_def ):
                result = ... load ...
                return result

            # ignore 'src_result'. It is uniquely identified by 'src_def' -->
            @cache.cache("0.1", dependencies=[load_src], exclude_args=['data'])  
            def statistics( stats_def, src_def, data ):
                stats = ... using data
                return stats
            
            src_def = PrettyObject()
            src_def.start = "2010-01-01"
            src_def.end = "2025-01-01"
            src_def.x = 0.1

            stats_def = PrettyObject()
            stats_def.lambda = 0.1
            stats_def.window = 100

            data  = load_src( src_def )
            stats = statistics( stats_def, src_def, data )

        While instructive, this case is not optimal: we do not really need to load ``data``
        if we can reconstruct ``stats`` from ``data`` (unless we need ``data`` further on).
        
        Consider therefore:

        .. code-block:: python

            @cache.cache("0.1")
            def load_src( src_def ):
                result = ... load ...
                return result

            # ignore 'src_result'. It is uniquely identified by 'src_def' -->
            @cache.cache("0.1", dependencies=[load_src])  
            def statistics_only( stats_def, src_def ):
                data  = load_src( src_def )    # <-- embedd call to load_src() here
                stats = ... using src_result
                return stats
            
            stats = statistics_only( stats_def, src_def )

        Caching Member Functions
        ^^^^^^^^^^^^^^^^^^^^^^^^

        You can cache member functions like any other function.
        Note that :dec:`cdxcore.version.version` information are by default inherited, i.e. member functions will be dependent on the version of their 
        defining class, and class versions will be dependent on their base classes' versions:
            
        .. code-block:: python

            from cdxcore.subdir import SubDir, version
            cache   = SubDir("!/.cache")
            cache.delete_all_content()   # for illustration
            
            @version("0.1")
            class A(object):
                def __init__(self, x):
                    self.x = x

                @cache.cache("0.1")
                def f(self, y):
                    return self.x*y
        
            a = A(x=1)
            _ = a.f(y=1)   # compute f and store result
            _ = a.f(y=1)   # load result back from disk
            a.x = 2
            _ = a.f(y=1)   # 'a' changed: compute f and store result
            b = A(x=2)
            _ = b.f(y=1)   # same unique call ID as previous call -> restore result from disk
            
        **WARNING**
        :class:`cdxcore.uniquehash.UniqueHash` does *not* by default process members of objects or dictionaries
        which start with a "_". This behaviour can be changed using :class:`cdxcore.subdir.CacheController`.
        For reasonably complex objects it is recommended to implement for your objects 
        the a custom hashing function::
        
            __unique_hash__( self, uniqueHash : UniqueHash, debug_trace : DebugTrace  )

        This function is described at :class:`cdxcore.uniquehash.UniqueHash`.
            
        Caching Bound Member Functions
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

        Caching bound member functions is technically quite different to caching a function of a class in general,
        but also supported:
            
        .. code-block:: python
        
            from cdxcore.subdir import SubDir, version
            cache   = SubDir("!/.cache", cache_controller : CacheController(debug_verbose=Context("all")))
            cache.delete_all_content()   # for illustration

            class A(object):
                def __init__(self,x):
                    self.x = x
                def f(self,y):
                    return self.x*y
            
            a = A(x=1)
            f = cache.cache("0.1", id=lambda self, y : f"a.f({y})")(a.f)  # <- decorate bound 'f'.
            r = c(y=2)

        In this case the function ``f`` is bound to ``a``. The object is added as ``self`` to the function
        parameter list even though the bound function parameter list does not include ``self``.
        This, together with the comments on hashing objects above, ensures that (hashed) changes to ``a`` will
        be reflected in the unique call ID for the member function.

        Caching Classes
        ^^^^^^^^^^^^^^^

        Classes can also be cached. In this case the creation of a class is cached, i.e. a call to
        the class constructor restores the respectiv object from disk.

        This is done in two steps:
            
        1) first, the class itself is decorated using 
           :dec:`cdxcore.subdir.SubDir.cache`
           to provide version information at class level. Only version information are provided here.
           
        2) Secondly, decorate ``__init__``. You do not need to specify a version
           for ``__init__`` as its version usually coincides with the version of the class. At ``__init__``
           you define how unique IDs are generated from the parameters passed to object construction.

        Simple example:
            
        .. code-block:: python
    
            from cdxcore.subdir import SubDir
            cache   = SubDir("!/.cache")
            cache.delete_all_content()   # for illustration
            
            @cache.cache("0.1")
            class A(object):
                
                @cache.cache(exclude_args=['debug'])
                def __init__(self, x, debug):
                    if debug:
                        print("__init__",x)
                    self.x = x
                    
            a = A(1)    # caches 'a'
            b = A(1)    # reads the cached object into 'b'

        **Technical Comments**
        
        The function ``__init__`` does not actually return a value; for this reason
        behind the scenes it is actually ``__new__`` which is being decorated.
        Attempting to cache-decorate ``__new__`` manually will lead to an exception.

        A nuance for ``__init__`` vs ordinary member function is that the
        ``self`` parameter is non-functional
        (in the sense that it is an empty object when ``__init__`` is called).
        ``self`` is therefore automatically excluded from computing a unique call ID.
        That also means ``self`` is not part of the arguments passed to ``uid``:
        
        .. code-block:: python
        
            @cache.cache("0.1")
            class A(object):
                
                @cache.cache("0.1", id=lambda x, debug: f"A.__init__(x={x})")  # <-- 'self' is not passed to the lambda function; no need to add **_
                def __init__(self, x, debug):
                    if debug:
                        print("__init__",x)
                    self.x = x

        Decorating classes with ``__slots__`` does not yet work.
                                    
        See also
        ^^^^^^^^

        For project-wide use it is usually inconvenient to control caching at the level of a 
        project-wide cache root directory.
        See :class:`cdxcore.subdir.VersionedCacheRoot` for a thin convenience wrapper around a :class:`cdxcore.subdir.SubDir`
        with a :class:`cdxcore.subdir.CacheController`.
        
        Parameters
        ----------
        version : str, optional
            Version of the function.
            
            * If ``None`` then ``F`` must be decorated with :dec:`cdxcore.version.version`.
            * If set, the function ``F`` is first decorated with :dec:`cdxcore.version.version`.
            
        dependencies : list[type], optional
            A list of version dependencies, either by reference or by name.
            See :dec:`cdxcore.version.version` for details on name lookup if strings are used.
        
        label : str | Callable
            Specify a human-readable label for the function call given its parameters.
            This label is used to generate the cache file name, and is also printed in when tracing
            hashing operations. Labels are not assumed to be unique, hence a unique hash of
            the label and the parameters to this function will be appended to generate
            the actual cache file name.
            
            Use ``uid`` instead if ``label`` represents valid unique filenames.
            
            
            **Usage:**
            
            * If ``label`` is a plain string without ``{}`` formatting: use this string as-is.
            
            * If ``label`` is a string with ``{}`` formatting, then ``label.format( name=name, **parameters )``
              will be used to generate the actual label.
            
            * If ``label`` is a ``Callable`` then ``label( name=name, **parameters )`` will be called
              to generate the actual label.

            See above for examples.
            
            ``label`` cannot be used alongside ``uid``.
            
        uid : str | Callable
            Alternative to ``label`` which is assumed to generate a unique cache file name. It has the same
            semantics as ``label``. When used, parameters to the decorated function are not hashed.
            
            ``uid`` be used alongside ``label``.
        
        name : str, optional
            Name of this function which is used either on its own if neither ``label`` not ``uid`` are used.
            If either of them is used, ``name`` is passed as a parameter to either the callable or the
            formatting operator.
            
            If ``name`` is not specified it defaults to ``__qualname__`` expanded
            by the module name the function is defined in.
        
        include_args : list[str]
            List of arguments to include in generating an unqiue ID, or ``None`` for all.
        
        exclude_args : list[str]:
            List of arguments to exclude from generating an unique ID.
            
        exclude_arg_types : list[type]
            List of parameter types to exclude from generating an unique ID.
            
        version_auto_class : bool
            Whether to automaticallty add version dependencies on base classes or, for member functions, on containing
            classes. This is the ``auto_class`` parameter for :dec:`cdxcore.version.version`.
            
        Returns
        -------
        Decorated F: Callable
        
            A decorator ``cache(F)`` whose ``__call__`` implements the cached call to ``F``.
            
            This callable has a member ``cache_info``
            of type :class:`cdxcore.subdir.CacheInfo`
            which can be used to access information on caching activity.

            * Information available at any time after decoration:**
                
              * ``F.cache_info.name`` : qualified name of the function
              * ``F.cache_info.signature`` : signature of the function
        
            * Additonal information available during a call to a decorated function F, and thereafter:                    
                
              * ``F.cache_info.version`` : unique version string reflecting all dependencies.
              * ``F.cache_info.filename`` : unique filename used for caching logic during the last function call.
              * ``F.cache_info.label`` : last label generated, or ``None``.
              * ``F.cache_info.arguments`` : arguments parsed to create a unique call ID, or ``None``.

            * Additonal information available after a call to ``F``:
                
              * ``F.cache_info.last_cached`` : whether the last function call returned a cached object.
                
            The decorated ``F()`` has additional function parameters, namely:
                
            * ``override_cache_mode`` : allows to override caching mode temporarily, in particular you can set it to ``"off"``.
            * ``track_cached_files`` : allows passing a :class:`cdxcore.subdir.CacheTracker`
              object to keep track of all
              files used (loaded from or saved to). 
              The function :meth:`cdxcore.subdir.CacheTracker.delete_cache_files` can be used
              to delete all files involved in caching.
        """
        return CacheCallable(subdir = self,
                             version = version,
                             dependencies = dependencies,
                             label = label,
                             uid = uid,
                             name = name,
                             exclude_args = exclude_args,
                             include_args = include_args,
                             exclude_arg_types = exclude_arg_types,
                             version_auto_class = version_auto_class )

    def cache_class( self, 
                     version             : str = None , *,
                     name                : str = None,
                     dependencies        : list = None, 
                     version_auto_class  : bool = True
                     ):
        """
        Short-cut for :dec:`cdxcore.subdir.SubDir.cache` applied to classes
        with a reduced number of available parameters.
        
        Example::

            cache   = SubDir("!/.cache")
            
            @cache.cache_class("0.1")
            class A(object):
                
                @cache.cache(exclude_args=['debug'])
                def __init__(self, x, debug):
                    if debug:
                        print("__init__",x)
                    self.x = x

        """
        return self.cache( name=name,
                           version=version,
                           dependencies=dependencies,
                           version_auto_class=version_auto_class)        

# ========================================================================
# Caching, convenience
# ========================================================================

def VersionedCacheRoot( directory          : str, *,
                        ext                : str = None, 
                        fmt                : Format = None,
                        create_directory   : bool = False,
                        **controller_kwargs
                        ):
    """
    Create a root directory for versioned caching on disk
    using :dec:`cdxcore.subdir.SubDir.cache`.
    
    **Usage:**

    In a central file, define a root directory for all caching activity::
        
        from cdxcore.subdir import VersionedCacheRoot
        vroot = VersionedCacheRoot("!/cache")

    Create sub-directories as suitable, for example::
        
        vtest = vroot("test")

    Use these for caching::
            
        @vtest.cache("1.0")
        def f1( x=1, y=2 ):
            print(x,y)
            
        @vtest.cache("1.0", dps=[f1])
        def f2( x=1, y=2, z=3 ):
            f1( x,y )
            print(z)
    
    Parameters
    ----------
        directory : str
            Name of the root directory for caching.
            
            Using SubDir the following Short-cuts are supported:
                
            * ``"!/dir"`` creates ``dir`` in the temporary directory.
            * ``"~/dir"`` creates ``dir`` in the home directory.
            * ``"./dir"`` creates ``dir`` relative to the current directory.
            
        ext : str
            Extension, which will automatically be appended to file names.
            The default value depends on ``fmt`; for ``Format.PICKLE`` it is "pck".
            
        fmt : :class:`cdxcore.subdir.Format`
            File format; if ``ext`` is not specified, the format drives the extension, too.
            Default is ``Format.PICKLE``.

        create_directory : bool
            Whether to create the directory upon creation. Default is ``False``.
            
        controller_kwargs: dict
            Parameters passed to :class:`cdxcore.subdir.CacheController``.
            
            Common parameters used:
                
            * ``exclude_arg_types``: list of types or names of types to exclude when auto-generating function
              signatures from function arguments.
              An example is :class:`cdxcore.verbose.Context` which is used to print progress messages.
              
            * ``max_filename_length``: maximum filename length.
            
            * ``hash_length``: length used for hashes, see :class:`cdxcore.uniquehash.UniqueHash`.
        
    Returns
    -------
        Root : :class:`cdxcore.subdir.SubDir`
            A root directory suitable for caching.
    """    
    controller = CacheController(**controller_kwargs) if len(controller_kwargs) > 0 else None
    return SubDir( directory, ext=ext, fmt=fmt, create_directory=create_directory, cache_controller=controller )

version = version_decorator
                
class CacheTracker(object):
    """
    Utility class to track caching and be able to delete all dependent objects.
    """
    def __init__(self):
        """ track cache files """
        self._files = []
    def __iadd__(self, new_file):
        """ Add a new file to the tracker """
        self._files.append( new_file )
    def delete_cache_files(self):
        """ Delete all tracked files """
        for file in self._files:
            if os.path.exists(file):
                os.remove(file)
        self._files = []
    def __str__(self) -> str:#NOQA
        return f"Tracked: {self._files}"
    def __repr__(self) -> str:#NOQA
        return f"Tracked: {self._files}"

class CacheInfo(object):
    """
    Information on cfunctions decorated with :dec:`cdxcore.subdir.SubDir.cache`.
    
    Functions decorated with :dec:`cdxcore.subdir.SubDir.cache` 
    will have a member ``cache_info`` of this type
    """
    def __init__(self, name, F, keep_last_arguments):
        """
        :meta private:
        """
        self.name        = name                  #: Decoded name of the function.
        
        self.signature   = inspect.signature(F)  #: :func:`inspect.signature` of the function.
    
        self.filename    = None                  #: Unique filename of the last function call.
        self.label       = None                  #: Label of the last function call.
        self.version     = None                  #: Last version used.
        
        self.last_cached = None                  #: Whether the last function call restored data from disk.
        
        if keep_last_arguments:             
            self.arguments = None                #: Last arguments used. This member is only present if ``keep_last_arguments`` was set to ``True`` for the relevant :class:`cdxcore.subdir.CacheController`.

def _ensure_has_version( F,
                         version      : str = None,
                         dependencies : list = None,
                         auto_class   : bool = True,
                         allow_default: bool = False):
    """
    Sets a version if requested, or ensures one is present
    """
    if version is None and not dependencies is None:
        raise ValueError(f"'{F.__qualname__}: you cannot specify version 'dependencies' without specifying also a 'version'")
    
    version_info = getattr(F,"version", None)
    if not version_info is None and type(version_info).__name__ != Version.__name__:
        raise RuntimeError(f"'{F.__qualname__}: has a 'version' member, but it is not of class 'Version'. Found '{type(version_info).__name__}'")

    if version is None:
        if not version_info is None:
            return F
        if allow_default:
            version = "0"
        else:
            raise ValueError(f"'{F.__qualname__}': cannot determine version. Specify 'version'")
    elif not version_info is None:
        raise ValueError(f"'{F.__qualname__}: function already has version information; cannot set version '{version}' again")
    return version_decorator( version=version,
                              dependencies=dependencies,
                              auto_class=auto_class)(F)

def _qualified_name( F, name ):
    """
    Return qualified name including module name, robustly
    """
    if name is None:
        try:
            name = F.__qualname__
        except:
            try:
                name = F.__name__
            finally:
                pass
            verify( not name is None, "Cannot determine qualified name for 'F': it has neither __qualname__ nor a type with a name. Please specify 'name'", exception=RuntimeError)
        try:
            name = name + "@" + F.__module__
        except:
            warn( f"Cannot determine module name for '{name}' of {type(F)}" )
    return name

class CacheCallable(object):
    """
    Wrapper for a cached function.
    
    This is the wrapper returned by :dec:`cdxcore.subdir.SubDir.cache`.    
    """
    
    def __init__(self, 
                    subdir              : SubDir, *,
                    version             : str = None,
                    dependencies        : list,
                    label               : Callable = None,
                    uid                 : Callable = None,
                    name                : str = None,
                    exclude_args        : set[str] = None,
                    include_args        : set[str] = None,
                    exclude_arg_types   : set[type] = None,
                    version_auto_class  : bool = True,
                    name_of_name_arg    : str = "name"):
        """
        Utility class for :dec:`cdxcore.subdir.SubDir.cache`.
        
        *Do not use directly.*
        """
        if not label is None and not uid is None:
            error("Cannot specify both 'label' and 'uid'.")
        
        self._subdir              = SubDir(subdir)
        self._version             = str(version) if not version is None else None
        self._dependencies        = list(dependencies) if not dependencies is None else None
        self._label               = label
        self._uid                 = uid
        self._name                = str(name) if not name is None else None
        self._exclude_args        = set(exclude_args) if not exclude_args is None and len(exclude_args) > 0 else None
        self._include_args        = set(include_args) if not include_args is None and len(include_args) > 0 else None
        self._exclude_arg_types   = set(exclude_arg_types) if not exclude_arg_types is None and len(exclude_arg_types) > 0 else None
        self._version_auto_class  = bool(version_auto_class)
        self._name_of_name_arg    = str(name_of_name_arg)
        
    @property
    def uid_or_label(self) -> Callable:
        """ ID or label """
        return self._uid if self._label is None else self._label
    @property
    def unique(self) -> bool:
        """ Whether the ID is unique """
        return not self._uid is None
    @property
    def cache_controller(self) -> CacheController:
        """ Returns the :class:`cdxcore.subdir.CacheController` """
        return self._subdir.cache_controller
    @property
    def cache_mode(self) -> CacheMode:
        """ Returns the :class:`cdxcore.subdir.CacheMode` of the underlying :class:`cdxcore.subdir.CacheController` """ 
        return self.cache_controller.cache_mode
    @property
    def debug_verbose(self) -> Context:
        """ Returns the debug :class:`cdxcore.verbose.Context` used to print caching information, or ``None`` """
        return self.cache_controller.debug_verbose
    @property
    def labelledFileName(self) -> Callable:
        """ Returns ``labelledFileName()`` of the underlying :class:`cdxcore.subdir.CacheController` """ 
        return self.cache_controller.labelledFileName
    @property
    def uniqueFileName(self) -> Callable:
        """ Returns ``uniqueFileName()`` of the underlying :class:`cdxcore.subdir.CacheController` """ 
        return self.cache_controller.uniqueFileName
    @property
    def global_exclude_arg_types(self) -> list[type]:
        """ Returns ``exclude_arg_types`` of the underlying :class:`cdxcore.subdir.CacheController` """ 
        return self.cache_controller.exclude_arg_types
    
    def __call__(self, F : Callable):
        """
        Decorate ``F`` as cachable callable.
        See :dec:`cdxcore.subdir.SubDir.cache` for documentation.
        """
        if inspect.isclass(F):
            if not self._label is None: raise ValueError("'{F.__qualname__}': when decorating a class specify 'label' for __init__, not the class")
            if not self._uid is None: raise ValueError("'{F.__qualname__}': when decorating a class specify 'uid' for __init__, not the class")
            if not self._exclude_args is None: raise ValueError("'{F.__qualname__}': when decorating a class specify 'exclude_args' for __init__, not the class")
            if not self._include_args is None: raise ValueError("'{F.__qualname__}': when decorating a class specify 'include_args' for __init__, not the class")
            if not self._exclude_arg_types is None: raise ValueError("'{F.__qualname__}': when decorating a class specify 'exclude_arg_types' for __init__, not the class")
            return self._wrap_class(F)

        return self._wrap( F )
        
    def _wrap_class(self, C : type):
        """
        Wrap class
        
        This wrapper:
            
        * Assigns a :dec:`cdxcore.version.version` for the class (if not yet present).
        * Extracts from ``__init__`` the wrapper to decorate`` __new__``.
        """
        debug_verbose = self.cache_controller.debug_verbose

        assert not inspect.isclass(C), ("Not a class", C)
         
        # apply decorator provided for __init__ to __new__                    
        C__init__           = getattr(C, "__init__", None)
        if C__init__ is None:
            raise RuntimeError("'{F.__qualname__}': define and decorate __init__")
        init_cache_callable = getattr(C__init__, "init_cache_callable", None)
        if init_cache_callable is None:
            raise RuntimeError("'{F.__qualname__}': must also decorate __init__")
        assert type(init_cache_callable).__name__ == CacheCallable.__name__, (f"*** Internal error: '{C.__qualname__}': __init__ has wrong type for 'init_cache_callable': {type(init_cache_callable)} ?")
        
        C__init__.init_cache_callable = None # tell the __init__ wrapper we have processed this information
        
        C__new__                          = C.__new__
        class_parameter                   = list(inspect.signature(C__new__).parameters)[0]        
        init_cache_callable._exclude_args = {class_parameter} if init_cache_callable._exclude_args is None else ( init_cache_callable._exclude_args | {class_parameter})
        init_cache_callable._name         = _qualified_name( C, self._name ) if init_cache_callable._name is None else init_cache_callable._name
        
        C.__new__ = init_cache_callable._wrap( C__new__, is_new = True )
        C.__new__.cache_info.signature = inspect.signature(C__init__)  # signature of the function

        # apply version
        # this also ensures that __init__ picks up a version dependency on the class itse
        # (as we forceed 'auto_class' to be true)
        C = _ensure_has_version( C, version=self._version,
                                    dependencies=self._dependencies,
                                    auto_class=self._version_auto_class)
            
        if not debug_verbose is None:
            debug_verbose.write(f"cache_class({C.__qualname__}): class wrapped; class parameter '{class_parameter}' to __new__ will be ignored.")

        return C

    def _wrap(self, F : Callable, is_new : bool = False):
        """
        Decorate callable 'F'.
        """
        debug_verbose = self.cache_controller.debug_verbose
        assert not inspect.isclass(F), ("Internal error")
        
        # check validity
        # --------------
        # Cannot currently decorate classes.

        
        is_method = inspect.ismethod(F)
        if is_method:
            assert not getattr(F, "__self__", None) is None, ("Method type must have __self__...?", F.__qualname__ )
        elif not inspect.isfunction(F):
            # if F is neither a function or class, attempt to decorate (bound) __call__
            if not callable(F):
                raise ValueError(f"{F.__qualname__}' is not callable")    
            F_ = getattr(F, "__call__", None)
            if F_ is None:
                raise ValueError(f"{F.__qualname__}' is callable, but has no '__call__'. F is of type {type(F)}")
            if not debug_verbose is None:
                debug_verbose.write(f"cache({F.__qualname__}): 'F' is an object; will use bound __call__")
            F = F_
            del F_
        else:
            # __new__ should not be decorated manually
            if not is_new and F.__name__ == "__new__":
                raise ValueError(f"You cannot decorate __new__ of '{F.__qualname__}'.")            

        # handle __init__
        # ---------------
        
        if F.__name__ == "__init__":
            # the decorate __init__ has two purposes
            # 1) during initializaton keep ahold of 'self' which will be the decorator for __new__ in fact
            # 2) during runtime, deciding based upon '__new__' caching status wherer to run the original __init__
            
            def execute_init( self, *args, **kwargs ):
                """
                Overwriting __init__ directly does not work as __init__ does not return anything.
                """                
                # ensure '__new__' was processed.
                # this will happen when the class is wrapped
                if not execute_init.init_cache_callable is None:
                    raise RuntimeError(f"Class '{type(self).__qualname__}': __init__ was decorated for caching but it seems the class '{type(self).__qualname__}' was not decorated, too.")

                __magic_cache_call_init__ = getattr(self, "__magic_cache_call_init__", None)
                assert not __magic_cache_call_init__ is None, ("*** Internal error: __init__ called illegally")

                if __magic_cache_call_init__:
                    # call __init__
                    F( self, *args, **kwargs )
                    #if not debug_verbose is None:
                    #    debug_verbose.write(f"cache({type(self).__qualname__}): __init__ called")
                else:
                    pass
                    # do not call __init___
                    #if not debug_verbose is None:
                    #    debug_verbose.write(f"cache({type(self).__qualname__}): __init__ skipped")
                self.__magic_cache_call_init__ = None

            update_wrapper( wrapper=execute_init, wrapped=F )
            
            # for class decorator to pick up.
            # ClassCallable() will set this to None before excecute_init
            # is called (ie before the first object is created)
            execute_init.init_cache_callable = self  
            return execute_init
            
        # version
        # -------
        # Decorate now or pick up existing @version

        F = _ensure_has_version( F, version=self._version,
                                    dependencies=self._dependencies,
                                    auto_class=self._version_auto_class,
                                    allow_default=is_new )
        
        # name
        # ----
        
        name = _qualified_name( F, self._name )

        # any other function
        # ------------------

        exclude_types = ( self._exclude_arg_types if not self._exclude_arg_types is None else set() )\
                      | ( self.global_exclude_arg_types if not self.global_exclude_arg_types is None else set())

        def execute( *args, override_cache_mode : CacheMode = None, 
                            track_cached_files  : CacheTracker = None,
                            **kwargs ):     
            """
            Cached execution of the wrapped function
            """
            
            if is_new:
                # if 'F' is __new__ then we might need to turn off all caching when deserializing cached objects from disk
                if execute.__new_during_read:
                    return F(*args, **kwargs)
            
            # determine unique id_ for this function call
            # -------------------------------------------
            
            uid_or_label = self.uid_or_label
            filename     = None
            if isinstance(uid_or_label, str) and self.unique:
                # if 'id' does not contain formatting codes,
                # and the result is 'unique' then do not bother collecting
                # function arguments
                try:
                    filename = uid_or_label.format()   # throws a KeyError if 'id' contains formatting information
                except KeyError:
                    pass

            if not filename is None:
                # generate name with the unique string provided by the user
                if not is_filename(filename):
                    raise ValueError(f"The unique filename '{filename}' computed for '{name}' contains invalid characters for filename. When using `uid` make sure that "+\
                                     "the returned ID is a valid filename (and unique)")
                label     = filename
                filename  = self.uniqueFileName( filename )
                arguments = None
                
            else:
                # get dictionary of named arguments
                arguments = execute.cache_info.signature.bind(*args,**kwargs)
                arguments.apply_defaults()
                arguments = arguments.arguments # ordered dict

                if is_new:
                    # delete 'cls' from argument list
                    assert len(arguments) >= 1, ("*** Internal error", F.__qualname__, is_new, arguments)
                    del arguments[list(arguments)[0]]
                argus     = set(arguments)

                # filter dictionary
                if not self._exclude_args is None or not self._include_args is None:
                    excl = set(self._exclude_args) if not self._exclude_args is None else set()
                    if not self._exclude_args is None: 
                        if self._exclude_args > argus:
                            raise ValueError(f"{name}: 'exclude_args' contains unknown argument names: exclude_args {sorted(self._exclude_args)} while argument names are {sorted(argus)}.")
                    if not self._include_args is None:     
                        if self._include_args > argus:
                            raise ValueError(f"{name}: 'include_args' contains unknown argument names: include_args {sorted(self._iinclude_args)} while argument names are {sorted(argus)}.")
                        excl = argus - self._iinclude_args
                    if not self._exclude_args is None:
                        excl |= self._exclude_args
                    for arg in excl:
                        if arg in arguments:
                            del arguments[arg]
                    del excl

                if len(exclude_types) > 0:
                    excl = []
                    for k, v in arguments.items():
                        if type(v) in exclude_types or type(v).__name__ in exclude_types:
                            excl.append( k )
                    for arg in excl:
                        if arg in arguments:
                            del arguments[arg]
                                
                # did the user provide a label or unique ID?
                if uid_or_label is None:
                    uid_or_label = name
                    
                else:
                    if self._name_of_name_arg in arguments:
                        error(f"{name}: '{self._name_of_name_arg}' is a reserved keyword and used as parameter name for the function name. Found it also in the function parameter list. Use 'name_of_name_arg' to change the internal parameter name used.")

                    # add standard arguments
                    full_arguments = OrderedDict()
                    if is_method:
                        assert not 'self' in set(arguments), ("__self__ found in bound method argument list...?", F.__qualname__, execute.cache_info.signature.bind(*args,**kwargs).arguments )
                        full_arguments['self'] = F.__self__                    
                    full_arguments[self._name_of_name_arg] = name
                    for k,v in arguments.items():
                        full_arguments[k] = v
                    arguments = full_arguments
                    del full_arguments, k, v

                    # call format or function                    
                    if isinstance( uid_or_label, str ):
                        try:
                            uid_or_label = str.format( uid_or_label, **arguments )
                        except KeyError as e:
                            raise KeyError(e, f"Error while generating id for '{name}' using format string '{uid_or_label}': {e}. Available arguments: {list(arguments)}")

                    else:
                        which = 'uid' if not self._uid is None else 'label'
                        try:
                            uid_or_label = uid_or_label(**arguments)
                        except TypeError as e:
                            raise TypeError(e, f"Error while generating '{which}' for '{name}' using a function: {e}. Available arguments: {list(arguments)}")
                        except Exception as e:
                            raise type(e)(f"Error while generating '{which}' for '{name}': attempt to call '{which}' of type {type(uid_or_label)} failed: {e}")
                        assert isinstance(uid_or_label, str), ("Error:", which, "callable must return a string. Found",type(uid_or_label))

                if self.unique:
                    if not is_filename(uid_or_label):
                        raise ValueError(f"The unique filename '{uid_or_label}' computed for '{name}' contains invalid characters for filename. When using `uid` make sure that "+\
                                         "the returned filename is indeed a valid filename (and unique)")

                    label    = uid_or_label
                    filename = self.uniqueFileName( uid_or_label )
                else:
                    label    = uid_or_label
                    filename = self.labelledFileName( uid_or_label, **arguments )

            # determine version, cache mode
            # ------------------

            version_   = self._version if not self._version is None else F.version.unique_id64
            cache_mode = CacheMode(override_cache_mode) if not override_cache_mode is None else self.cache_mode
            del override_cache_mode

            # store process information
            # -------------------------

            execute.cache_info.label    = str(label) if not label is None else None
            execute.cache_info.filename = filename
            execute.cache_info.version  = version_
            
            if self.cache_controller.keep_last_arguments:
                info_arguments = OrderedDict()
                for argname, argvalue in arguments.items():
                    info_arguments[argname] = str(argvalue)[:100]
                execute.cache_info.arguments = info_arguments
                del argname, argvalue
            
            # execute caching
            # ---------------

            if cache_mode.delete:
                self._subdir.delete( filename )
            elif cache_mode.read:
                class Tag:
                    pass
                tag = Tag()
                if not is_new:
                    r = self._subdir.read( filename, tag, version=version_ )
                else:
                    try:
                        execute.__new_during_read = True
                        r = self._subdir.read( filename, tag, version=version_ )
                    finally:
                        execute.__new_during_read = False
                        
                if not r is tag:
                    if not track_cached_files is None:
                        track_cached_files += self._fullFileName(filename)
                    execute.cache_info.last_cached = True 
                    if not debug_verbose is None:
                        debug_verbose.write(f"cache({name}): read '{label}' version 'version {version_}' from cache '{self._subdir.full_file_name(filename)}'.")
                    if is_new:
                        assert r.__magic_cache_call_init__ is None, ("**** Internal error. __init__ should reset __magic_cache_call_init__", F.__qualname__, label)
                        r.__magic_cache_call_init__ = False # since we called __new__, __init__ will be called next

                    return r
            
            r = F(*args, **kwargs)
            
            if is_new:
                # __new__ created the object, but __init__ was not called yet to initialize it
                # we simulate this here
                cls = args[0]
                assert not cls is None and inspect.isclass(cls), ("*** Internal error", cls)
                r.__magic_cache_call_init__ = True
                cls.__init__( r, *args[1:], **kwargs )
                assert r.__magic_cache_call_init__ is None, ("**** Internal error. __init__ should reset __magic_cache_call_init__")
            
            if cache_mode.write:
                self._subdir.write(filename,r,version=version_)      
                if not track_cached_files is None:
                    track_cached_files += self._subdir.full_file_name(filename)
            execute.cache_info.last_cached = False

            if is_new:
                assert r.__magic_cache_call_init__ is None, ("**** Internal error. __init__ should reset __magic_cache_call_init__")
                r.__magic_cache_call_init__ = False # since we called __new__, __init__ will be called next
                #debug_verbose.write(f"cache({name}): called __init__ after __new__ with: {args[1:]} / {kwargs}")
            
            if not debug_verbose is None:
                if cache_mode.write:
                    debug_verbose.write(f"cache({name}): called '{label}' version 'version {version_}' and wrote result into '{self._subdir.full_file_name(filename)}'.")
                else:
                    debug_verbose.write(f"cache({name}): called '{label}' version 'version {version_}' but did *not* write into '{self._subdir.full_file_name(filename)}'.")
            return r

        update_wrapper( wrapper=execute, wrapped=F )
        execute.cache_info = CacheInfo(name, F, self.cache_controller.keep_last_arguments)
            
        if is_new:
            execute.__new_during_read = False
        
        if not debug_verbose is None:
            debug_verbose.write(f"cache({name}): {'function' if not is_new else 'class constructor function'} registered for caching into '{self._subdir.path}'.")
        self.cache_controller.versioned[name] = execute
        return execute          



