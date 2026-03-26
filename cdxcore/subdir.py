from __future__ import annotations
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
    
* ``PICKLE``: standard pickling with default extension "pck".

* ``JSON_PICKLE``: uses the :mod:`jsonpickle` package; default extension "jpck".
  The advantage of this format over "PICKLE" is that it is somewhat human-readable.
  However, ``jsonpickle`` uses compressed formats for complex objects such as :mod:`numpy`
  arrays, hence readablility is somewhat limited. Using "JSON_PICKLE"
  comes at cost of slower i/o speed.

* ``JSON_PLAIN``: calls :func:`cdxcore.util.plain` is an output-only format to generate human readable files
  which (usually) cannot be loaded back from disk.
  In this mode ``SubDir`` converts objects into plain Python objects before using :mod:`json`
  to write them to disk.
  That means that deserialized data does not have the correct object structure
  for being restored properly.
  However, such files are much easier to read.

* ``BLOSC`` uses `blosc <https://github.com/blosc/python-blosc>`__
  to read/write compressed binary data. The blosc compression algorithm is very fast,
  hence using this mode will not usually lead to notably slower performance than using
  "PICKLE" but will generate smaller files, depending on your data structure.  
  The default extension for "BLOSC" is "zbsc".

* ``GZIP``: uses :mod:`gzip` to 
  to read/write compressed binary data. The default extension is "pgz".
  
* ``POLARS_PARQUET`` writes :class:`polars.DataFrames` using parquet files.
  In this mode, only parquet files can be read and written. Versioning is supported.

* ``PANDAS_PARQUET`` writes :class:`pandas.DataFrames` using parquet files.
  In this mode, only parquet files can be read and written. Versioning is supported.

* ``PYTREE_HDF5`` writes pytrees, i.e. colllections of collections of numpy arrays using HDF5 files.
  Versioning is supported.

**Summary of properties i/o modes:**

+----------------+------------------+----------------+-------+-------------+-----------+------------+
| Format         | Restores objects | Human readable | Speed | Compression | Extension | Types      | 
+================+==================+================+=======+=============+===========+============+
| PICKLE         | yes              | no             | high  | no          | .pck      | all        |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| JSON_PLAIN     | no               | yes            | low   | no          | .json     | all        |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| JSON_PICKLE    | yes              | limited        | low   | no          | .jpck     | all        |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| BLOSC          | yes              | no             | high  | yes         | .zbsc     | all        |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| GZIP           | yes              | no             | high  | yes         | .pgz      | all        |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| POLARS_PARQUET | yes              | no             | high  | yes         | .prq      | polars     |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| PANDAS_PARQUET | yes              | no             | high  | yes         | .pdq      | pandas     |
+----------------+------------------+----------------+-------+-------------+-----------+------------+
| PYTREE_HDF5    | yes              | no             | high  | yes         | .h5       | numpy      |
+----------------+------------------+----------------+-------+-------------+-----------+------------+

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

To delete a file, use either of the following::

    subdir.delete("file")
    del subdir['file']

All of these are *silent*, and will by default not throw errors if ``file`` does not exist.


In order to throw an error use::

    subdir.delete('file', raise_on_error=True)

A few member functions assist in deleting a number of files:

* :func:`cdxcore.subdir.SubDir.delete_all_files`: delete all files in the directory with matching extension. Do not delete sub directories, or files with extensions different to our own.
* :func:`cdxcore.subdir.SubDir.delete_all_content`: delete all files with our extension, including in all sub-directories. If a sub-directory is left empty
  upon ``delete_all_content`` delete it, too.
* :func:`cdxcore.subdir.SubDir.delete_everything`: deletes *everything*, not just files with matching extensions.

Caching
^^^^^^^

A :class:`cdxcore.subdir.SubDir` object offers an advanced context for caching calls to :class:`collection.abc.Callable`
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

**See** :dec:`cdxcore.subdir.SubDir.cache` **for full feature set.**

Import
------
.. code-block:: python

    from cdxcore.subdir import SubDir
    
Documentation
-------------
"""

import os as os
import uuid as uuid
import threading as threading
import pickle as pickle
import tempfile as tempfile
import shutil as shutil
import types as types
import datetime as datetime
import inspect as inspect
import platform as platform
from collections import OrderedDict
from collections.abc import Collection, Mapping, Callable, Iterable
from enum import Enum
from functools import update_wrapper
from typing import Any, Iterator

import polars as pl
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import json as json
import gzip as gzip
import blosc as blosc
import h5py as h5py

import sys as sys
from .err import verify, error, warn, fmt as txtfmt, verify_inp, warn_if#NOQA
from .pretty import PrettyObject
from .verbose import Context
from .version import Version, version as version_decorator, VersionError
from .util import fmt_list, fmt_filename, DEF_FILE_NAME_MAP, plain, is_filename, fmt_dict, ActiveFormat, qualified_name
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
    General purpose file formats for :class:`cdxcore.subdir.SubDir`.
    
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | Format         | Restores objects | Human readable | Speed | Compression | Extension | Types      | 
    +================+==================+================+=======+=============+===========+============+
    | PICKLE         | yes              | no             | high  | no          | .pck      | all        |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | JSON_PLAIN     | no               | yes            | low   | no          | .json     | all        |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | JSON_PICKLE    | yes              | limited        | low   | no          | .jpck     | all        |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | BLOSC          | yes              | no             | high  | yes         | .zbsc     | all        |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | GZIP           | yes              | no             | high  | yes         | .pgz      | all        |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | POLARS_PARQUET | yes              | no             | high  | yes         | .prq      | polars     |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | PANDAS_PARQUET | yes              | no             | high  | yes         | .pdq      | pandas     |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    | PYTREE_HDF5    | yes              | no             | high  | yes         | .h5       | numpy      |
    +----------------+------------------+----------------+-------+-------------+-----------+------------+
    
    :class:`cdxcore.subdir.SubDir` supports ``POLARS_PARQUET`` and ``PANDAS_PARQUET`` for reading and writing :class:`polars.DataFrame` 
    and :class:`pandas.DataFrame` files
    to parquet. Version information is stored in meta data. 
    When used, the object passed to :meth:`cdxcore.subdir.write` must be of the correct data frame type.
    """
    PICKLE = 0       #: Standard binary :mod:`pickle` format.
    JSON_PICKLE = 1  #: :mod:`jsonpickle` format.
    JSON_PLAIN = 2   #: ``json`` format.
    BLOSC = 3        #: :mod:`blosc` binary compressed format.
    GZIP = 4         #: :mod:`gzip` binary compressed format.
    POLARS_PARQUET = 10  # :class:`polars.DataFrame` i/o with parquet
    PANDAS_PARQUET = 11  # :class:`pandas.DataFrame` i/o with parquet
    PYTREE_HDF5 = 12 #: Pytree i/o for nested collections of numpy arrays
    
PICKLE = Format.PICKLE
JSON_PICKLE = Format.JSON_PICKLE
JSON_PLAIN = Format.JSON_PLAIN
BLOSC = Format.BLOSC
GZIP = Format.GZIP
POLARS_PARQUET = Format.POLARS_PARQUET
PANDAS_PARQUET = Format.PANDAS_PARQUET
PYTREE_HDF5 = Format.PYTREE_HDF5

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
    
    def __init__(self, mode : str|CacheMode|None = None ) -> None:
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
    created. This way all sub directories have the same
    caching behaviour. 
    
    Parameters
    ----------
    exclude_arg_types : list[type | str], optional
        List of types or names of types to exclude from producing unique ids from function arguments.
        Strings are compated to ``type(arg).__name__``.

        Defaults to ``[Context]``.
        
    cache_mode : CacheMode, default ``ON``
        Top level cache control.
        Set to "OFF" to turn off all caching.
        
    max_filename_length : int, default ``48``
        Maximum filename length. If unique id's exceed the file name a hash of length
        ``hash_length`` will be intergated into the file name.
        See :class:`cdxcore.uniquehash.NamedUniqueHash`.
        
    hash_length : int, default ``8``
        Length of the hash used to make sure each filename is unique
        See :class:`cdxcore.uniquehash.NamedUniqueHash`.
        
    debug_verbose : :class:`cdxcore.verbose.Context` | None, default ``None``
        If not ``None`` print caching process messages to this object.
        
    keep_last_arguments : bool, default ``False``
        Keep a dictionary of all parameters as string representations after each function call.
        If the function ``F`` was decorated using :meth:``cdxcore.subdir.SubDir.cache``,
        you can access this information via ``F.cache_info.last_arguments``.

        Note that strings are limited to 100 characters per argument to avoid memory
        overload when large objects are passed.   
    """
    
    def __init__(self, *,
                    exclude_arg_types  : list[type|str] = [Context],
                    cache_mode         : CacheMode = CacheMode.ON,
                    max_filename_length: int = 48,
                    hash_length        : int = 8,
                    debug_verbose      : Context = None,
                    keep_last_arguments: bool = False
                    ) -> None:
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

    def __unique_hash__( self, unique_hash, debug_trace ) -> str:
        """ hash function """
        return unique_hash(self.cache_mode,self.exclude_arg_types,self.keep_last_arguments,
                           self.labelledFileName, self.uniqueFileName,debug_trace=debug_trace)
            
default_cacheController = CacheController()

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
    
    **Polars**
    
    A ``SubDir`` can read and write :class:`polars.DataFrame` if the format is set to :attr:`cdxcore.subdir.Format.POLARS_PARQUET`::
        
        import polars as pl
        import numpy as np
        from cdxcore.subdir import SubDir
        
        x = np.linspace(0,1,5)
        y = np.sin(x)
        df = pl.DataFrame({"x":pl.Series(x,pl.Float32), "y":pl.Series(y,pl.Float32)})
        
        sub = SubDir("!/polars", fmt=SubDir.POLARS_PARQUET)
        sub.write("test", df)
        r = sub.read("test", raise_on_error=True)
        assert np.all(r == df)

    Version handling is supported with parquet files.

    **Pandas**
    
    A ``SubDir`` can read and write :class:`pandas.DataFrame` if the format is set to :attr:`cdxcore.subdir.Format.PANDAS_PARQUET`::
        
        import pandas as pd
        import numpy as np
        from cdxcore.subdir import SubDir
        
        x = np.linspace(0,1,5)
        y = np.sin(x)
        df = pd.DataFrame({"x":x, "y":y})
        
        sub = SubDir("!/pandas", fmt=SubDir.PANDAS_PARQUET)
        sub.write("test", df)
        r = sub.read("test", raise_on_error=True)
        assert np.all(r == df)

    Version handling is supported with parquet files.

    Parameters
    ----------
    name : str:
        Name of the directory.
        
        The name may start with any of the following special characters:

        * ``'.'`` for current directory.
        * ``'~'`` for home directory.
        * ``'!'`` for system default temp directory. Note that outside any administator imposed policies, sub directories 
          of ``!`` are permanent.
        * ``'?'`` for a temporary temp directory; see :meth:`cdxcore.subdir.SubDir.temp_temp_dir` regarding semantics.
                    Most importantly, every ``SubDir`` will be constructed with a different (truly) temporary sub directory.
                    If used, ``delete_everything_upon_exit`` is always ``True``.
 
        The directory name may also contain a formatting string for defining ``ext`` on the fly:
        for example use ``"!/test;*.bin"`` to specify a directory ``"test"`` in the user's
        temp directory with extension ``"bin"``.
        
        The directory name can be set to ``None`` in which case it is always empty
        and attempts to write to it fail with  :class:`EOFError`.
        
    parent : str | SubDir | None, default ``None``
        Parent directory. 
        
        If ``parent`` is a :class:`cdxcore.subdir.SubDir` then its parameters are used
        as default values.
        
    ext : str | None, default ``None``
        Extension for files managed by this ``SubDir``. All files managed by ``self`` will share the same extension.

        If set to ``""`` no extension is assigned to this directory. That mean that
        all files are considered. For example,
        :meth:`cdxcore.subdir.SubDir.files` then returns all files contained in the directory, not
        just files with a specific extension.
        
        If ``ext`` is ``None``, then use ``parent.ext`` or if ``parent`` was provided, or otherwise
        the extension defined by ``fmt``:
            
        * 'pck' for the default PICKLE format.
        * 'json' for JSON_PLAIN.
        * 'jpck' for JSON_PICKLE.
        * 'zbsc' for BLOSC.
        * 'pgz' for GZIP.
        * 'prq' for POLARS_PARQUET.
        * 'pdq' for PANDAS_PARQUET.
        * 'h5' for PYTREE_HDF5.
        
    fmt : :class:`cdxcore.subdir.Format` | None, default ``Format.PICKLE``

        One of the :class:`cdxcore.subdir.Format` codes.
        
        If ``ext`` is left to ``None`` and ``parent`` is ``None`` 
        then setting the a format will also set the corrsponding ``ext``.

    create_directory : bool | None, default ``False``
    
        Whether to create the directory upon creation of the ``SubDir`` object; otherwise it will be created upon first
        :meth:`cdxcore.subdir.SubDir.write`.
        
        Set to ``None`` to use the setting of the parent directory, or ``False`` if no parent
        is specified.

    cache_controller : :class:`cdxcore.subdir.CacheController` | None, default ``None``
    
        An object which fine-tunes the behaviour of :meth:`cdxcore.subdir.SubDir.cache`.
        See :class:`cdxcore.subdir.CacheController` documentation for further details. 

    delete_everything : bool, default ``False``
    
        Delete all contents in the newly defined sub directory upon creation.
        
    delete_everything_upon_exit : bool, default ``False``
    
        Delete all contents of the current exist if ``self`` is deleted.
        This is the always ``True`` if the ``"?/"`` pretext was used.
        
        Note, however, that this will only be executed once the object is garbage collected.

        Default is, for some good reason, is ``False``.            
    """

    RET_SUB_DIR = object()  #: :meta private: Sentinel for returning a sub directory handle.

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
    
    POLARS_PARQUET = Format.POLARS_PARQUET
    """ :meta private: """
    
    PANDAS_PARQUET = Format.PANDAS_PARQUET
    """ :meta private: """
    
    PYTREE_HDF5 = Format.PYTREE_HDF5
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

    def __init__(self, name : str|SubDir|None, 
                       parent : str|SubDir|None = None, *, 
                       ext : str|None = None, 
                       fmt : Format|None = None, 
                       create_directory : bool|None = None,
                       cache_controller : CacheController|None = None,
                       delete_everything : bool = False,
                       delete_everything_upon_exit : bool = False
                       ) -> None:
        """
        Instantiates a sub directory which contains files with a common extension.

        """
        create_directory = bool(create_directory) if not create_directory is None else None
        ext              = SubDir._extract_ext(ext) if not ext is None else None
        
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
            assert self._ext=="" or self._ext==self.EXT_FMT_AUTO or self._ext[0] == ".", ("Extension error", self._ext)
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
            assert self._ext=="" or self._ext==self.EXT_FMT_AUTO or self._ext[0] == ".", ("Extension error", self._ext)
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

        # name
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
                ext  = SubDir._extract_ext(_ext)
                name = name[:ext_i]
                del _ext
            del ext_i
            
        # extension
        if ext is None:
            self._ext = self.EXT_FMT_AUTO if parent is None else parent._ext
        else:
            self._ext = ext
        assert self._ext=="" or self._ext==self.EXT_FMT_AUTO or self._ext[0] == ".", ("Extension error", self._ext)
            
        # create_directory
        if create_directory is None:
            self._crt = False if parent is None else parent._crt
        else:
            self._crt = bool(create_directory)
            
        # cache controller
        if cache_controller is None:
            self._cctrl = parent._cctrl if not parent is None else None               
        else:
            assert type(cache_controller).__name__ == CacheController.__name__, ("'cache_controller' should be of type 'CacheController'", type(cache_controller))
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
        if getattr(self, "_tclean", False):
            self.delete_everything(keep_directory=False)
        self._path = None

    @staticmethod
    def expand_std_root( name ) -> str:
        """
        Expands ``name`` by a standardized root directory.
            
        The first character of ``name`` can be either of:
            
        * ``"!"`` returns :meth:`cdxcore.subdir.SubDir.temp_dir()`.
        * ``"."`` returns :meth:`cdxcore.subdir.SubDir.working_dir()`.
        * ``"~"`` returns :meth:`cdxcore.subdir.SubDir.user_dir()`.
        
        If neither of these matches the first character, ``name``
        is returned as is.
        
        This function does not support ``"?"`` because ``"?"`` used in the constructor
        represents a new directory every time it is used.
        
        This function returns a string.
        """
        if len(name) < 2 or name[0] not in ['.','!','~'] or name[1] not in ["\\","/"]:
            return name
        if name[0] == '!':
            return SubDir.temp_dir() + name[2:]
        elif name[0] == ".":
            return SubDir.working_dir() + name[2:]
        else:
            return SubDir.user_dir() + name[2:]

    def create_directory( self ) -> SubDir:
        """
        Creates the current directory if it doesn't exist yet.
        Returns ``self``.
        """
        # create directory/clean up
        if self._path is None:
            return self
        # create directory
        if not os.path.exists( self._path[:-1] ):
            try:
                os.makedirs( self._path[:-1] )
                return
            except FileExistsError:
                pass
        if not os.path.isdir(self._path[:-1]):
            raise NotADirectoryError(txtfmt( "Cannot use sub directory %s: object exists but is not a directory", self._path[:-1] ))
        return self

    def path_exists(self) -> bool:
        """ Whether the current directory exists """
        if self._path is None:
            return False
        return os.path.exists( self._path[:-1] )
        
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
        assert self._ext=="" or self._ext==self.EXT_FMT_AUTO or self._ext[0] == ".", ("Extension error", self._ext)
        return self._ext if self._ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def auto_ext( self, ext_or_fmt : str|Format = None ) -> str:
        """
        Computes the effective extension based on theh inputs ``ext_or_fmt``,
        and the current settings for ``self``.

        If ``ext_or_fmt`` is set to ``"*"`` then the extension associated to
        the format of ``self`` is returned.
        
        Parameters
        ----------
        ext_or_fmt : str | :class:`cdxcore.subdir.Format` | None, default ``None``
            An extension or a format.
        
        Returns
        -------
        ext : str
            The extension with leading ``'.'``.
        """
        if isinstance(ext_or_fmt, Format):
            r = self._auto_ext(ext_or_fmt)
        else:
            ext = self._ext if ext_or_fmt is None else SubDir._extract_ext(ext_or_fmt)
            r = ext if ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)
            del ext
        assert r=="" or r[0] == ".", ("Extension error", self._ext, ext_or_fmt)
        return r

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
    def cache_controller(self) -> CacheController:
        """ Returns an assigned :class:`cdxcore.subdir.CacheController`, or ``None`` """
        return self._cctrl if not self._cctrl is None else default_cacheController
    
    @property
    def cache_mode(self) -> CacheMode:
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
        if fmt == Format.POLARS_PARQUET:
            return ".prq"
        if fmt == Format.PANDAS_PARQUET:
            return ".pdq"
        if fmt == Format.PYTREE_HDF5:
            return ".h5"
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
        
        * Accepts '.ext' and 'ext'
        * Detects use of directories
        * Returns '*' if ext='*'
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
        verify( ext[0] != "?", "Extension '%s' cannot start with '?' (this symbol indicates a temporary directory)", ext, exception=ValueError )
        return "." + ext
            
    # -- public utilities --

    def full_file_name(self, file : str, *, ext : str = None) -> str:
        """
        Returns fully qualified file name, based on a given unqualified file name (e.g. without path or extension).

        Parameters
        ----------
        file : str
            Core file name without path or extension.
        ext : str | None, default ``None``
            If not ``None``, use this extension rather than :attr:`cdxcore.subdir.SubDir.ext`.

        Returns
        -------
        Filename : str | None
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
        assert len(ext) == 0 or ext[0]==".", ("Extension error", ext)
        if len(ext) > 0 and file[-len(ext):] != ext:
            return self._path + file + ext
        return self._path + file

    @staticmethod
    def temp_dir() -> str:
        """
        Return system temp directory. Short-cut to :func:`tempfile.gettempdir`.
        
        This function creates a "permanent temporary" directoy (i.e. under ``/tmp/`` for Linux or ``%TEMP%`` for Windows).
        Most importantly, it is somewhat persisient: you expect it to be there after a reboot.
        
        To cater for the use case of a one-off temporary directory use :meth:`cdxcore.subdir.SubDir.temp_temp_dir`.

        This function is called when the ``!`` parameter is used when constructing
        :class:`cdxcore.subdir.SubDir` objects.

        Returns
        -------
            Path : str
                This function returns a string contains trailing ``'/'``.
        """
        d = tempfile.gettempdir()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-1", d)
        return d + "/"

    @staticmethod
    def temp_temp_dir() -> str:
        """
        Returns a temporary temp directory name using :func:`tempfile.mkdtemp` which is temporary 
        for the current process and thread, and is not guaranteed to be  persisted e.g. when the system is rebooted.        
        Accordingly, this function will return a different directory upon every function call.

        This function is called when the ``?/`` is used when constructing
        :class:`cdxcore.subdir.SubDir` objects.

        **Implementation notoce:**
        
        In most cirsumstances, a temporary temp directioy is *not* deleted from a system upon reboot.
        Do not rely on regular clean ups.
        It is strongly recommended to clean up after usage, for example using the pattern::
            
            from cdxcore.subdir import SubDir
            import shutil
            
            try:
                tmp_dir = SubDir.temp_temp_dir()
                
                ...
            finally:
                shutil.rmtree(tmp_dir)
 
        Returns
        -------
            Path : str
                This function returns a string contains trailing ``'/'``.
       
        """
        d = tempfile.mkdtemp()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-1", d)
        return d + "/"

    @staticmethod
    def working_dir() -> str:
        """
        Return current working directory. Short-cut for :func:`os.getcwd`.

        This function is called when the ``./`` is used when constructing
        :class:`cdxcore.subdir.SubDir` objects.

        Returns
        -------
            Path : str
                This function returns a string contains trailing ``'/'``.
       
        """
        d = os.getcwd()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-2", d)
        return d + "/"

    @staticmethod
    def user_dir() -> str:
        """
        Return current working directory. Short-cut for :func:`os.path.expanduser` with parameter ``' '``.

        This function is called when the ``~/`` is used when constructing
        :class:`cdxcore.subdir.SubDir` objects.

        Returns
        -------
            Path : str
                This function returns a string contains trailing ``'/'``.
       
        """
        d = os.path.expanduser('~')
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-3", d)
        return d + "/"

    # -- read --

    def _read_reader( self, reader, file : str, default : Any|None, raise_on_error : bool, *, ext : str = None ) -> Any|None:
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
                    default : Any|None = None,
                    raise_on_error : bool = False,
                    *,
                    version : str |None= None,
                    ext : str|None = None,
                    fmt : Format|None = None,
                    delete_wrong_version : bool = True,
                    handle_version : int = 0
                    ) -> Any|None:
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

            elif fmt == Format.POLARS_PARQUET:
                ok   = True
                if not version is None:
                    meta         = pl.read_parquet_metadata(full_file_name)
                    test_version = meta.get("version", None)
                    if handle_version == SubDir.VER_RETURN:
                        return test_version
                    ok = (version == "*" or test_version == version)
                if ok:
                    if handle_version == SubDir.VER_CHECK:
                        return True
                    data = pl.read_parquet(full_file_name)
                    return data
                
            elif fmt == Format.PANDAS_PARQUET:
                ok   = True
                if not version is None:
                    test_version = pq.read_metadata(full_file_name).metadata or {}
                    test_version = test_version.get(b'cdxcore.subdir.version', None)
                    test_version = test_version.decode("utf-8") if not test_version is None else None
                    if handle_version == SubDir.VER_RETURN:
                        return test_version
                    ok = (version == "*" or test_version == version)
                if ok:
                    if handle_version == SubDir.VER_CHECK:
                        return True
                    data = pd.read_parquet(full_file_name)
                    return data
                
            elif fmt == Format.PYTREE_HDF5:
                ok   = True
                with h5py.File(full_file_name, "r") as f:
                    if not version is None:
                        test_version = f.attrs.get("version", None)
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return True
                        def read_h5(h, top:str):
                            r = dict()
                            for k,v in h.items():
                                if isinstance(v, h5py.Dataset):
                                    if k[:4] == "_1_N":
                                        v = v[()]
                                        assert isinstance(v, (float, int, np.generic)), ("Internal error: expected numeric dataset to be read as a number, but got type %s", type(v))
                                        r[k[4:]] = v
                                        continue
                                    if k[:4] == "_1_S":
                                        v = v[()]
                                        v = v.decode("utf-8")
                                        assert isinstance(v, str), ("Internal error: expected string dataset to be read as a string, but got type %s", type(v))
                                        r[k[4:]] = v
                                        continue
                                    if k[:4] == "_1_D":
                                        v = v[()]
                                        v = v.decode("utf-8")
                                        r[k[4:]] = datetime.date.fromisoformat(v)
                                        continue
                                    if k[:4] == "_1_d":
                                        v = v[()]
                                        v = v.decode("utf-8")
                                        r[k[4:]] = datetime.datetime.fromisoformat(v)
                                        continue
                                    if k[:4] == "_1_T":
                                        v = v[()]
                                        v = v.decode("utf-8")
                                        r[k[4:]] = datetime.time.fromisoformat(v)
                                        continue
                                    else:
                                        r[k] = v[()]
                                elif isinstance(v, h5py.Group):
                                    r[k] = read_h5( v, top=f"{top}.{k}" )
                            return r
                        verify( set(f) == {'root'}, f"Cannot load H5 file: file must contain unique root note 'root'. Found nodes {sorted(f)}. Full file name '{full_file_name}'.")
                        return read_h5(f["root"],file)
                
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
                    default : Any|None = None,
                    raise_on_error : bool = False,
                    *,
                    version : str|None = None,
                    delete_wrong_version : bool = True,
                    ext : str|None = None,
                    fmt : Format|None = None
                    ) -> Any|None:
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
            
        raise_on_error : bool, default ``False``
            Whether to raise an exception if reading an existing file failed.
            By default this function fails silently and returns the default.
            
        version : str | None, default ``None``
            If not ``None``, specifies the version of the current code base.
            
            In this case, this version will be compared to the version of the file being read.
            If they do not match, read fails (either by returning default or throwing a :class:`cdxcore.version.VersionError` exception).

            You can specify version ``"*"`` to accept any version.
            Note that this is distinct
            to using ``None`` which stipulates that the file should not 
            have version information.
            
        delete_wrong_version : bool, default ``True``
            If ``True``, and if a wrong version was found, delete the file.

        ext : str | None, default ``None``
            Extension overwrite, or a list thereof if ``file`` is a list.
            
            Use:
                
            * ``None`` to use directory's default.
            * ``'*'`` to use the extension implied by ``fmt``.
            * ``""`` to turn of extension management.
            
        fmt : :class:`cdxcore.subdir.Format` | None, default ``None``
            File :class:`cdxcore.subdir.Format` or ``None`` to use the directory's default.
            
            Note:
                
            * ``fmt`` cannot be a list even if ``file`` is.
            * Unless ``ext`` or the SubDir's extension is ``'*'``, changing the format does not automatically change the extension.

        Returns
        -------
        Content : type | list
            For a single ``file`` returns the content of the file if successfully read, or ``default`` otherwise.
            If ``file`` is a list, this function returns a list of contents.
                
        Raises
        ------
        Version error : :class:`cdxcore.version.VersionError`:
            If the file's version did not match the ``version`` provided.
            
        Version present : :class:`cdxcore.subdir.VersionPresentError`:
            When attempting to read a file without ``version`` which has a version this exception is raised.
            
        I/O errors : ``Exception``
            Various standard I/O errors are raisedas usual.
            
        """
        return self._read( file=file,
                           default=default,
                           raise_on_error=raise_on_error,
                           version=version,
                           ext=ext,
                           fmt=fmt,
                           delete_wrong_version=delete_wrong_version,
                           handle_version=SubDir.VER_NORMAL )

    def is_version( self, file : str, version : str|None = None, raise_on_error : bool = False, *, ext : str|None = None, fmt : Format|None = None, delete_wrong_version : bool = True ) -> bool:
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
 
        delete_wrong_version : bool, default ``True``
            If ``True``, and if a wrong version was found, delete ``file``.
            
        ext : str | None, default ``None``
            Extension overwrite, or a list thereof if ``file`` is a list.
            
            Set to:
                
            * ``None`` to use directory's default.
            * ``"*"`` to use the extension implied by ``fmt``.
            * ``""`` for no extension.
            
        fmt : :class:`cdxcore.subdir.Format` | None, default ``None``
            File format or ``None`` to use the directory's default.
            Note that ``fmt`` cannot be a list even if ``file`` is.

        Returns
        -------
            Status : bool
                Returns ``True`` only if the file exists, has version information, and its version is equal to ``version``.
        """
        return self._read( file=file,default=False,raise_on_error=raise_on_error,version=version,ext=ext,fmt=fmt,delete_wrong_version=delete_wrong_version,handle_version=SubDir.VER_CHECK )

    def get_version( self, file : str, raise_on_error : bool = False, *, ext : str|None = None, fmt : Format|None = None ) -> str:
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
 
        delete_wrong_version : bool, default ``True``
            If ``True``, and if a wrong version was found, delete ``file``.
            
        ext : str | None, default ``None``
            Extension overwrite, or a list thereof if ``file`` is a list.
            
            Set to:
                
            * ``None`` to use directory's default.
            * ``"*"`` to use the extension implied by ``fmt``.
            * ``""`` for no extension.
            
        fmt : :class:`cdxcore.subdir.Format` | None, default ``None``
            File format or ``None`` to use the directory's default.
            Note that ``fmt`` cannot be a list even if ``file`` is.

        Returns
        -------
        version : str
            The version.
        """
        return self._read( file=file,default=None,raise_on_error=raise_on_error,version="",ext=ext,fmt=fmt,delete_wrong_version=False,handle_version=SubDir.VER_RETURN )

    def read_string( self, file : str, default : Any|None = None, raise_on_error : bool = False, *, ext : str|None = None ) -> str:
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

    def _write( self, writer, file : str, obj, raise_on_error : bool, *, ext : str|None = None ) -> bool:
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
                     obj : Any,
                     raise_on_error : bool = True,
                     *,
                     version : str|None = None,
                     ext : str|None = None,
                     fmt : Format|None = None ) -> bool:
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
                
            raise_on_error : bool, default ``
                If ``False``, this function will return ``False`` upon failure.

            version : str | None, default ``None``
                If not ``None``, specifies the version of the code which generated ``obj``.
                This version will be written to the beginning of the file.

            ext : str | None, default ``None``
                Extension, or list thereof if ``file`` is a list.
                
                * Use ``None`` to use directory's default extension.
                * Use ``"*"`` to use the extension implied by ``fmt``.

            fmt : :class:`cdxcore.subdir.Format` | None, default ``None``
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
            # if a version is attempted to be read but is not present
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

                elif fmt == Format.POLARS_PARQUET:
                    # only if a version is provided write it into the file
                    if not isinstance( obj, pl.DataFrame ):
                        raise ValueError(f"When using format POLARS_PARQUET you must save only polars DataFrames. Found type '{type(obj)}'.")
                    obj.write_parquet( full_file_name, metadata = None if version is None else dict(version=version) )

                elif fmt == Format.PANDAS_PARQUET:
                    # only if a version is provided write it into the file
                    if not isinstance( obj, pd.DataFrame ):
                        raise ValueError(f"When using format PANDAS_PARQUET you must save only pandas DataFrames. Found type '{type(obj)}'.")

                    table = pa.Table.from_pandas(obj)
                    if not version is None:
                        meta = dict(table.schema.metadata or {})
                        meta[b"cdxcore.subdir.version"] = version.encode("utf-8")
                        table = table.replace_schema_metadata(meta)
                        del meta
                    pq.write_table(table, full_file_name)
                    del table
                    
                elif fmt == PYTREE_HDF5:
                    with h5py.File(full_file_name, "w") as f:
                        if not version is None:
                            f.attrs["version"] = version.encode("utf-8")
                    
                        dtstr = h5py.string_dtype(encoding='utf-8')
                        def write_h5(f, k, v, top:str):
                            if k[:3] == '_1_':
                                raise ValueError("Cannot write '{full_file_name}: HDF5 format does not allow key names starting with '_1_'. Found '{k}'.")
                            if isinstance( v, np.ndarray ):
                                f.create_dataset(k, data=v)
                                return
                            if isinstance(v, str):
                                f.create_dataset('_1_S'+k, data=np.array(v, dtype=dtstr))
                                return
                            if isinstance( v, (int, np.integer, float, np.floating)):                                          
                                f.create_dataset('_1_N'+k, data=np.array(v))
                                return 
                            if isinstance( v, datetime.datetime):
                                f.create_dataset('_1_d'+k, data=np.array(v.isoformat(),dtype=dtstr))
                                return
                            if isinstance( v, datetime.date):
                                f.create_dataset('_1_D'+k, data=np.array(v.isoformat(),dtype=dtstr))
                                return 
                            if isinstance( v, datetime.time):
                                f.create_dataset('_1_T'+k, data=np.array(v.isoformat(),dtype=dtstr))
                                return
                            if isinstance( v, Mapping ):
                                grp = f.create_group(k)
                                ktop = f"{top}.{k}"
                                for kk, kv in v.items():
                                    write_h5( grp, kk, kv, top = ktop)
                                return
                            raise ValueError(f"Cannot write HDF5 file: key {top}.{k} is of unsupported type {type(v)}. Full file name: '{full_file_name}'")
                        write_h5(f,"root",obj,file)
                    
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

    def write_string( self, file : str, line : str, raise_on_error : bool = True, *, ext : str|None = None ) -> bool:
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

    def files(self, *, ext : str|None = None) -> list:
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

    def sub_dirs(self) -> list[str]:
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

    # delete
    # ------

    def delete( self, file : str, raise_on_error: bool  = False, *, ext : str|None = None ):
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

    def delete_all_files( self, raise_on_error : bool = False, *, ext : str|None = None ):
        """
        Deletes all valid keys in this sub directory with the correct extension.
        
        Parameters
        ----------
        raise_on_error : bool
            Set to ``False`` to quietly ignore errors.
            
        ext : str | None, default ``None``
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

    def delete_all_content( self, delete_self : bool = False, raise_on_error : bool = False, *, ext : str|None = None ):
        """
        Deletes all valid keys and subdirectories in this sub directory.
        
        Does not delete files with other extensions.
        Use :meth:`cdxcore.subdir.SubDir.delete_everything` if the aim is to delete, well, everything.

        Parameters
        ----------
        delete_self: bool
            Whether to delete the directory itself as well, or only its contents.
            If ``True``, the current object will be left in ``None`` state.
            
        raise_on_error: bool
            ``False`` for silent failure
            
        ext : str | None, default ``None``
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
        If ``keep_directory`` is ``False``, then the directory referred to by this object will also be deleted.

        In this case, ``self`` will be set to ``None`` state.
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

    # file ops
    # --------

    def exists(self, file : str, *, ext : str|None = None ) -> bool:
        """
        Checks whether a file exists.

        Parameters
        ----------
        file :
            Filename, or list of filenames.
            
        ext : str | None, default ``None``
            Extension to be used:
                
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

    def get_creation_time( self, file : str, *, ext : str|None = None ) -> datetime.datetime:
        """
        Returns the creation time of a file.
        
        See comments on :func:`os.path.getctime` for system compatibility information.

        Parameters
        ----------
        file :
            Filename, or list of filenames.
            
        ext : str | None, default ``None``
            Extension to be used:
                
            * ``None`` for the directory default.
            * ``""`` to not use an automatic extension.
            * ``"*"`` to use the extension associated with the format of the directory.

        Returns
        -------
        Datetime : :class:`datetime.datetime`
            A single ``datetime`` if ``file`` is a string, otherwise a list of ``datetime``'s.
            Returns ``None`` if an error occurred.
        """
        return self._getFileProperty( file=file, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getctime(x)) )

    def get_last_modification_time( self, file : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last modification time a file.
        
        See comments on :func:`os.path.getmtime` for system compatibility information.

        Parameters
        ----------
        file :
            Filename, or list of filenames.
            
        ext : str | None, default ``None``
            Extension to be used:
                
            * ``None`` for the directory default.
            * ``""`` to not use an automatic extension.
            * ``"*"`` to use the extension associated with the format of the directory.

        Returns
        -------
        Datetime : :class:`datetime.datetime`
            A single ``datetime`` if ``file`` is a string, otherwise a list of ``datetime``'s.
            Returns ``None`` if an error occurred.
        """
        return self._getFileProperty( file=file, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getmtime(x)) )

    def get_last_access_time( self, file : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last access time of a file.
        
        See comments on :func:`os.path.getatime` for system compatibility information.

        Parameters
        ----------
        file :
            Filename, or list of filenames.
            
        ext : str | None, default ``None``
            Extension to be used:
                
            * ``None`` for the directory default.
            * ``""`` to not use an automatic extension.
            * ``"*"`` to use the extension associated with the format of the directory.

        Returns
        -------
        Datetime : :class:`datetime.datetime`
            A single ``datetime`` if ``file`` is a string, otherwise a list of ``datetime``'s.
            Returns ``None`` if an error occurred.
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
            File size if ``file``, or ``None`` if an error occurred.
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
    # ---------
    
    def temp_file_name( self, file : str|None = None ):
        """
        Returns a unique temporary file name.
        
        The file name is generated by applying a unique hash
        to the current directory, ``file``, the current process and thread IDs, and
        :meth:`datetime.datetime.now`.
        
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
   
    # object interface
    # ----------------

    def __call__(self, element : str|None = None,
                       default : Any = RET_SUB_DIR,
                       raise_on_error : bool = False,
                       *,
                       version : str|None = None,
                       ext : str|None = None,
                       fmt : Format|None = None,
                       delete_wrong_version : bool = True,
                       create_directory : bool|None = None ) -> Any:
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
            element : str | None
                File or directory name, or a list thereof.

                ``element`` can be ``None`` if ``default`` is left at its dummy value ``SubDir.RET_SUB_DIR`` (the default)
                in which case ``__call__`` refers to the current directory.
                
            default : Any, default ``SubDir.RET_SUB_DIR``
                If specified, this function reads ``element`` with
                ``read( element, default, *args, **kwargs )``.

                If ``default`` is not specified and left at the dummy value ``SubDir.RET_SUB_DIR``, then this function returns a new sub-directory by calling
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
        if default is SubDir.RET_SUB_DIR:
            if not element is None and not isinstance(element, str):
                if not isinstance(element, Collection): 
                    raise ValueError(txtfmt("'element' must be a string or an iterable object. Found type '%s;", type(element)))
                return [ SubDir( k,parent=self,ext=ext,fmt=fmt,create_directory=create_directory) for k in element ]
            return SubDir(element,parent=self,ext=ext,fmt=fmt,create_directory=create_directory)
        verify( not element is None, "Cannot use 'None' as filename", exception=ValueError)
        return self.read( file=element,
                          default=default,
                          raise_on_error=raise_on_error,
                          version=version,
                          delete_wrong_version=delete_wrong_version,
                          ext=ext,
                          fmt=fmt )

    def __getitem__( self, file ) -> Any:
        """
        Reads ``file`` using :meth:`cdxcore.subdir.SubDir.read`.
        If '`file'` does not exist, throw a :class:`KeyError`.
        """
        return self.read( file=file, default=None, raise_on_error=True )

    def __setitem__( self, file : str, value : Any):
        """ Writes ``value`` to ``file`` using :meth:`cdxcore.subdir.SubDir.write`. """
        self.write(file,value)

    def __delitem__(self,file : str):
        """ Silently delete ``file`` using :meth:`cdxcore.subdir.SubDir.delete`. """
        self.delete(file, False )

    def __len__(self) -> int:
        """ Return the number of files in this directory with matching extension. """
        return len(self.files())

    def __iter__(self) -> Iterator:
        """ Returns an iterator which allows traversing through all files below in this directory with matching extension. """
        return self.files().__iter__()

    def __contains__(self, file : str) -> bool:
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
            def __init__(_) -> None:
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
    
    def __add__(self, directory : str|SubDir ) -> SubDir:
        """
        Returns a the subdirectory ``directory`` of ``self``.
        """
        return SubDir(directory,parent=self)
    
    # unique hash
    # -----------
    
    def __unique_hash__( self, unique_hash, debug_trace ) -> str:
        """ Default unique has iterates contents - so files contained in this directory """
        return unique_hash(path=self._path,
                           ext=self._ext, 
                           fmt=self._fmt, 
                           cctrl=self._cctrl, 
                           #crt=self._crt, 
                           #tclean=self._tclean
                           debug_trace=debug_trace)

    # pickling
    # --------
    
    def __getstate__(self) -> Mapping:
        """ Return state to pickle """
        return dict( path=self._path, ext=self._ext, fmt=self._fmt, crt=self._crt, cctrl=self._cctrl, tclean=self._tclean )    

    def __setstate__(self, state : Mapping):
        """ Restore pickle """
        self._path = state['path']
        self._ext = state['ext']
        self._fmt = state['fmt']
        self._crt = state['crt']
        self._cctrl = state['cctrl']
        self._tclean = state['tclean']

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

    def cache( self,  version              : str|None = None , *,
                      dependencies         : list|None = None, 
                      label                : Callable|None = None,
                      uid                  : Callable|None = None,
                      name                 : str|None = None, 
                      in_sub_dir           : Callable|None = None,
                      exclude_args         : list[str]|None = None,
                      include_args         : list[str]|None = None,
                      exclude_arg_types    : list[type|str]|None = None,
                      version_auto_class   : bool = True,
                      name_of_func_name_arg: str = "func_name") -> Callable:
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
        the :class:`cdxcore.cache.CacheController` parameter for in :class:`cdxcore.subdir.SubDir`:
        
        .. code-block:: python

            from cdxcore.subdir import SubDir
            
            class Debugger:
                def output( cond, message ):
                    print(message)
            
            ctrl    = CacheController(exclude_arg_types=[Debugger])   # <- exclude 'Debugger' parameters from hasing
            cache   = SubDir("!/.cache")

            @cache.cache("0.1", dependencies=[f])
            def g(x,y,debugger : Debugger): # <-- 'debugger' is a non-functional parameter
                debugger.output(f"h(x={x},y={y})")  
                return g(x,y)**2
            
        **Unique IDs and File Naming**
                         
        The *unique call ID of a decorated function* is by logicaly generated by its fully qualified name
        and a unique hash of its functional parameters.
        
        By default, :class:`cdxcore.uniquehash.NamedUniqueHash` is used to compute unique hashes.
        Key default behaviours of :class:`cdxcore.uniquehash.NamedUniqueHash`:
            
        * :class:`cdxcore.uniquehash.NamedUniqueHash` hashes objects via their ``__dict__`` or ``__slot__`` members.
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
        to the function including its ``func_name`` are passed to the function.::

            @cache.cache("0.1", label=lambda x,y: f"h({x},{y})", exclude_args='debug') 
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

            @cache.cache("0.1", uid=lambda x,y: f"h2({x},{y})", exclude_args='debug') 
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
        the parameter ``uid`` can also be a :meth:`str.format` string or a callable.
            
        **Controlliong which Parameters to Hash**
            
        To specify which parameters are pertinent for identifying a unique ID, use:
            
        * ``include_args``: list of functions arguments to include. If ``None``, use all parameteres as input in the next step
        
        * ``exclude_args``: list of function arguments to exclude, if not ``None``.
        
        * ``exclude_arg_types``: a list of types or names of type to exclude.
          This is helpful if control flow is managed with dedicated data types.
          An example of such a type is :class:`cdxcore.verbose.Context` which is used to print hierarchical output messages.
          Types can be globally excluded using a :class:`cdxcore.subdir.CacheController`
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
            _ = b.f(y=1)   # same unique call ID as previous call
                           # -> restore result from disk
            
        **WARNING:**

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
            cache   = SubDir("!/.cache", cache_controller =
                             CacheController(debug_verbose=Context("all")))
            cache.delete_all_content()   # for illustration

            class A(object):
                def __init__(self,x):
                    self.x = x
                def f(self,y):
                    return self.x*y
            
            a = A(x=1)
            f = cache.cache("0.1", uid=lambda self, y : f"a.f({y})")(a.f)  # <- decorate bound 'f'.
            r = c(y=2)

        In this case the function ``f`` is bound to ``a``. The object is added as ``self`` to the function
        parameter list even though the bound function parameter list does not include ``self``.
        This, together with the comments on hashing objects above, ensures that (hashed) changes to ``a`` will
        be reflected in the unique call ID for the member function.

        Managing Caching Accross a Project
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

        For project-wide use it is usually convenient to control caching at the level of a 
        project-wide cache root directory.
        The classs :class:`cdxcore.subdir.VersionedCacheRoot` is a thin convenience wrapper around a :class:`cdxcore.subdir.SubDir`
        with a :class:`cdxcore.subdir.CacheController`.
        
        The idea is to have a central file, ``cache.py`` which contains the central root for caching.
        We recommend using an environment variable to be able to control the location of this directory
        out side the code. Here is an example with an environment variable ``PROJECT_CACHE_DIR``::
            
            # file cache.py
            
            from cdxcore.subdir import VersionedCacheRoot
            import os as os
                        
            cache_root = VersionedCacheRoot(
                               os.getenv("PROJECT_CACHE_DIR", "!/.cache")
                               )

        In a particular project file, say ``pipeline.py`` create a file-local cache directory
        and use it::
            
            # file pipeline.py
            
            from cache import cache_root
            
            cache_dir = cache_root("pipeline")
            
            @cache_dir.cache("0.1")
            def f(x):
                return x+2
            
            @cache_dir.cache("0.1", dependencies=[f])
            def g(x)
                return f(x)**2
            
            # ...
            
        In case you have issues with caching you can use the central root directory to turn on tracing 
        accross your project:

        .. code-block:: python
           :emphasize-lines: 4

            from cdxcore.verbose import Context
            cache_root = VersionedCacheRoot(
                               os.getenv("PROJECT_CACHE_DIR", "!/.cache"),
                               debug_verbose=Context.all    # turn full traing on
                            )

        Parameters
        ----------
        version : str | None, default ``None``
            Version of the function.
            
            * If ``None`` then a common ``F`` must be decorated manually 
              ith :dec:`cdxcore.version.version`.
            * If set, the function ``F`` is automatically first decorated
              with :dec:`cdxcore.version.version` for you.
            
        dependencies : list[type] | None, default ``None``
            A list of version dependencies, either by reference or by name.
            See :dec:`cdxcore.version.version` for details on
            name lookup if strings are used.
        
        label : str | Callable | None, default ``None``
            Specify a human-readable label for the function call given its parameters.
            
            This label is used to generate the cache file name, and is also printed in when tracing
            hashing operations. Labels are not assumed to be unique, hence a unique hash of
            the label and the parameters to this function will be appended to generate
            the actual cache file name.
            
            Use ``uid`` instead if ``label`` represents valid unique filenames. You cannot specify both ``uid`` and ``label``.
            If neither ``uid`` and ``label`` are present, ``name`` will be used.
            
            A ``label`` can contain directory information, i.e. ``label = lambda x, y : f"x/y"`` is a valid pattern.
            
            **Usage:**
            
            * If ``label`` is a ``Callable`` then ``label( func_name=name, **parameters )`` will be called
              to generate the actual label.
              
              The parameter ``func_name`` refers to the qualified
              name of the function. Its value can be overwitten by ``name``, while the parameter name itself
              can be overwritten using ``name_of_func_name_arg``, see below.

            * If ``label`` is a plain string without ``{}`` formatting: use this string as-is.
            
            * If ``label`` is a string with ``{}`` formatting, then ``label.format( func_name=name, **parameters )``
              will be used to generate the actual label. 
              
              The parameter ``func_name`` refers to the qualified
              name of the function. Its value can be overwitten by ``name``, while the parameter name itself
              can be overwritten using ``name_of_func_name_arg``, see below.
            
            See above for examples.
            
            ``label`` cannot be used alongside ``uid``.
            
        uid : str | Callable | None, default ``None``
            Alternative to ``label`` which is assumed to generate a unique cache file name. It has the same
            semantics as ``label``. When used, parameters to the decorated function are not hashed
            as the ``uid`` is assumed to be already unique. The string must be a valid file name. 

            A ``uid`` can contain directory information separated by ``/`` i.e.
           ``uid = lambda x, y : f"x/y"`` is a valid pattern. Each sub-directory must be a valid directory. Do not use ``\\`` even under windows.
            
            Use ``label`` if the id is not unique. You cannot specify both ``uid`` and ``label``.
            If neither ``uid`` and ``label`` are present, ``name`` will be used (as non-unique ``label``).
        
        name : str | None, default ``None``
            Name of this function which is used either on its own if neither ``label`` not ``uid`` are used,
            or which passed as a parameter ``func_name`` to either the callable or the
            formatting operator. See above for more details.
            
            If ``name`` is not specified it defaults to ``__qualname__`` expanded
            by the module name the function is defined in.
        
        include_args : list[str] | None, default ``None``
            List of arguments to include in generating an unqiue ID, or ``None`` for all.
        
        exclude_args : list[str] | None, default ``None``
            List of arguments to exclude from generating an unique ID. Examples of such non-functional arguments
            are workflow controls (debugging) and i/o elements.
            
        exclude_arg_types : list[type | str] | None, default ``None``
            List of parameter types or names of type to exclude from generating an unique ID. Examples of such non-functional arguments
            are workflow controls (debugging) and i/o elements. Strings are compated to ``type(arg).__name__``.

        in_sub_dir : str | Callable | None, default ``None``
            Allows specifying a sub-directory for the cached files, using the same formatting logic as for ``label``.
            
        version_auto_class : bool, default ``True``
            Whether to automaticallty add version dependencies on base classes or, for member functions, on containing
            classes. This is the ``auto_class`` parameter for :dec:`cdxcore.version.version`.
            
        name_of_func_name_arg : str, default ``"func_name"``
            When formatting ``label`` or ``uid``, by default ``"func_name"`` is used to refer to the current
            function name. If there is already a parameter ``func_name`` for the function, an error will be raised.
            Use this flag to change the parameter name. Example::

                from cdxcore.subdir import SubDir
                cache = SubDir("?/temp")

                @cache.cache("0.1")
                def f( func_name, x ):
                    pass
                
                f("test", 1)
                
            Generates a :class:`RuntimeError` ``f@__main__: 'func_name' is a reserved keyword
            and used as formatting parameter
            name for the function name. Found it also in the function parameter list. Use 'name_of_name_arg' to change the internal parameter name used.``.

            Instead, use:            
            
            .. code-block:: python

                @cache.cache("0.1", x : f"{new_func_name}(): {func_name} {x}", 
                                    name_of_func_name_arg="new_func_name")
                def f( func_name, x ):
                    pass

        Returns
        -------
        Decorated F: Callable
        
            A decorated ``F`` whose ``__call__`` implements the cached call to ``F``.
            
            This decorator has a member ``cache_info``
            of type :class:`cdxcore.subdir.CacheInfo`
            which can be used to access information on caching activity.

            * Information available at any time after decoration:
                
              * ``F.cache_info.name`` : qualified name of the function
              * ``F.cache_info.signature`` : signature of the function
        
            * Additonal information available during a call to a decorated function ``F``, and thereafter
              (these proprties are not thread-safe):
                
              * ``F.cache_info.version`` : unique version string reflecting all dependencies.
              * ``F.cache_info.filename`` : unique filename used for caching logic during the last function call.
              * ``F.cache_info.label`` : last label generated, or ``None``.
              * ``F.cache_info.arguments`` : arguments parsed to create a unique call ID, or ``None``.

            * Additonal information available after a call to ``F`` (these proprties are not thread-safe):
                
              * ``F.cache_info.last_cached`` : whether the last function call returned a cached object.
                
            The decorated ``F()`` has additional function parameters, namely:
                
            * ``override_cache_mode`` : ``CacheMode`` | None, default ``None``
            
              Allows overriding the ``CacheMode`` temporarily, in particular you can set it to ``"off"``.
               
            * ``track_cached_files`` : :class:`cdxcore.subdir.CacheTracker` | None, default ``None``
            
              Allows passing a :class:`cdxcore.subdir.CacheTracker`
              object to keep track of all
              files used (loaded from or saved to). 
              The function :meth:`cdxcore.subdir.CacheTracker.delete_cache_files` can be used
              to delete all files involved in caching.

            * ``return_cache_uid`` : bool, default ``False``
            
              If ``True``, then the decorated function will return a tuple ``uid, result``
              where ``uid`` is the unique filename generated for this function call,
              and where ``result`` is the actual result from the function, cached or not.
              This ``uid`` is thread-safe.
              
              Usage::
                  
                  from cdxcore.subdir import SubDir
                  cache_dir = SubDir("!/.cache")
                  
                  @cache_dir.cache()
                  def f(x, y):
                      return x*y
                  
                  uid, xy = f( x=1, y=2, return_cache_uid=True )
                  
              This pattern is thread-safe when compared to using::
              
                  xy = f( x=1, y=2 )
                  uid = f.cache_info.filename                  
        """
        def wrap( F : Callable ):
            wrapper = _CacheWrapper(F=F,
                                subdir = self,
                                version = version,
                                dependencies = dependencies,
                                label = label,
                                uid = uid,
                                name = name,
                                in_sub_dir = in_sub_dir,
                                exclude_args = exclude_args,
                                include_args = include_args,
                                exclude_arg_types = exclude_arg_types,
                                version_auto_class = version_auto_class,
                                name_of_func_name_arg = name_of_func_name_arg)
            return wrapper.wrapper()
        return wrap

# ========================================================================
# Caching, convenience
# ========================================================================

def VersionedCacheRoot( directory          : str|SubDir, *,
                        ext                : str|None = None, 
                        fmt                : Format|None = None,
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
        
    ext : str | None, default ``None``
        Extension, which will automatically be appended to file names.
        The default value depends on ``fmt`; for ``Format.PICKLE`` it is "pck".
        
    fmt : :class:`cdxcore.subdir.Format` | None, default ``None``
        File format; if ``ext`` is not specified, the format drives the extension, too.
        The default ``None`` becomes ``Format.PICKLE``.

    create_directory : bool, default ``False``
        Whether to create the directory upon creation. 
        
    controller_kwargs: dict
        Parameters passed to :class:`cdxcore.subdir.CacheController``.
        
        Common parameters used:
            
        * ``exclude_arg_types``: list of types or names of types to exclude when auto-generating function
          signatures from function arguments.
          An example is :class:`cdxcore.verbose.Context` which is used to print progress messages.
          
        * ``max_filename_length``: maximum filename length.
        
        * ``hash_length``: length used for hashes, see :class:`cdxcore.uniquehash.UniqueHash`.
        
        * ``debug_verbose`` set to ``Context.all`` after importing ``from cdxcore.verbose import Context``
          will turn on tracing all caching operations.
        
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
    def __init__(self) -> None:
        """ track cache files """
        self._files = []
    def __iadd__(self, new_file : str) -> CacheTracker:
        """ Add a new file to the tracker """
        self._files.append( new_file )
        return self
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

class CacheInfo(PrettyObject):
    """
    Information on cfunctions decorated with :dec:`cdxcore.subdir.SubDir.cache`.
    
    Functions decorated with :dec:`cdxcore.subdir.SubDir.cache` 
    will have a member ``cache_info`` of this type
    """
    def __init__(self, name: str, idversion: str, keep_last_arguments : bool ) -> None:
        """
        :meta private:
        """
        self.name        = name                  #: Decoded name of the function.        
        self.unique_id   = None                  #: Unique ID of the last function call.
        self.filename    = None                  #: Unique filename of the last function call.
        self.path        = None                  #: Fully qualified path where the file was stored.
        self.label       = None                  #: Label of the last function call.
        self.version     = idversion             #: (hash) version used. This is equal to ``F.version.unique_id64``.
        self.last_cached = None                  #: Whether the last function call restored data from disk.
        
        if keep_last_arguments:             
            self.last_arguments = None                #: Last arguments used. This member is only present if ``keep_last_arguments`` was set to ``True`` for the relevant :class:`cdxcore.subdir.CacheController`.

class _CacheWrapper(object):
    
    def __init__(self,  F                    : Callable,  
                        subdir               : SubDir|str, *,
                        version              : str|None = None,
                        dependencies         : list|None = None,
                        label                : str|Callable = None,
                        uid                  : str|Callable = None,
                        name                 : str = None,
                        in_sub_dir           : str|Callable = None,
                        exclude_args         : set[str] = None,
                        include_args         : set[str] = None,
                        exclude_arg_types    : set[type] = None,
                        version_auto_class   : bool = True,
                        name_of_func_name_arg: str = "func_name") -> None:
        
        # check F
        # -------
        verify_inp( not F is None, "'F' cannot be None")
        verify_inp( not inspect.isclass(F), lambda : f"Cannot wrap classes: {qualified_name(F'@')}")
        
        def assess(F):
            qual_name   = qualified_name(F,"@") if name is None else str(name)
            is_method   = inspect.ismethod(F) or isinstance(F, types.BuiltinMethodType)# for *bound* methods
            is_function = inspect.isfunction(F) or isinstance(F, types.BuiltinFunctionType)
    
            if not is_method and not is_function:
                # if F is neither a function or method, attempt to decorate (bound) __call__
                if not callable(F):
                    raise ValueError(f"'{qual_name}' is not callable")    
                F_ = getattr(F, "__call__", None)
                if F_ is None:
                    raise ValueError(f"{qual_name}' is callable, but has no '__call__'. F is of type {type(F)}")
                if not self.debug_verbose is None:
                    self.debug_verbose.write(f"cache({qual_name}): 'F' is an object; will use bound __call__")
                return assess(F.__call__)
            
            if is_method:
                if getattr(F, "__self__", None) is None:
                    raise RuntimeError(f"Method {qual_name} must have '__self__' member")
            else:
                assert is_function
                if F.__name__ == "__new__":
                    raise ValueError(f"You cannot decorate __new__ ('{qual_name}').")                    
            return F, is_method, is_function, qual_name      
                
        F,\
        self._is_method,\
        self._is_function,\
        qual_name                   = assess(F)

        # process inputs
        # --------------

        self._subdir                = SubDir(subdir) if not isinstance(subdir,SubDir) else subdir
        self._uid_or_label          = uid if label is None else label
        self._unique                = not uid is None
        self._in_sub_dir            = in_sub_dir
        self._name                  = str(name) if not name is None else qual_name
        self._exclude_args          = set(exclude_args) if not exclude_args is None and len(exclude_args) > 0 else None
        self._include_args          = set(include_args) if not include_args is None and len(include_args) > 0 else None
        self.cache_controller.versioned[self._name] = self

        exclude_arg_types     = set(exclude_arg_types) if not exclude_arg_types is None and len(exclude_arg_types) > 0 else set()
        global_exlc_at        = set(self.cache_controller.exclude_arg_types) if not self.cache_controller.exclude_arg_types is None and len(self.cache_controller.exclude_arg_types) > 0 else set()
        self._exclude_types   = exclude_arg_types | global_exlc_at

        # equip F with a version
        # ----------------------

        self._F          = self._ensure_has_version( F, version=str(version) if not version is None else None,
                                                     dependencies=list(dependencies) if not dependencies is None else None,
                                                     auto_class=bool(version_auto_class),
                                                     allow_default=False )
        self._signature  = inspect.signature(F)  


        # uid/label
        # ----------
        
        which                 = 'uid' if self._unique else 'label'     
        name_of_func_name_arg = str(name_of_func_name_arg)
        reserved             = {}
        reserved[name_of_func_name_arg] = self._name
        self._uid_or_label = self._uid_or_label if not self._uid_or_label is None else self._name
        self._uid_or_label = ActiveFormat(self._uid_or_label,label=which,name=self._name,reserved_keywords=reserved ) 
        self._in_sub_dir   = ActiveFormat(self._in_sub_dir,label="in_sub_dir",name=self._name,reserved_keywords=reserved ) if not self._in_sub_dir is None else None

        # wrap up
        # -------

        if not self.debug_verbose is None:
            self.debug_verbose.write(f"cache({self._name}): function registered for caching into '{self._subdir.path}'.")

    @property
    def version(self) -> Version:
        """ Returns the :class:`cdxcore.version.Version` information of F """
        return self._F.version
    @property
    def cache_controller(self) -> CacheController:
        """ Returns the associated :class:`cdxcore.subdir.CacheController` of the underlying :class:`cdxcore.subdir.SubDir` """
        return self._subdir.cache_controller
    @property
    def cache_mode(self) -> CacheMode:
        """ Returns the :class:`cdxcore.subdir.CacheMode` of the underlying :class:`cdxcore.subdir.CacheController` """ 
        return self.cache_controller.cache_mode
    @property
    def debug_verbose(self) -> Context:
        """ Returns the debug :class:`cdxcore.verbose.Context` used to print caching information, or ``None`` """
        return self.cache_controller.debug_verbose

    @staticmethod
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

    def cache_relevant_arguments(self, args : Collection, kwargs : Mapping ):
        """
        Expert usage: Returns all relevant function arguments for generating labels/uid's according to the exclusion/inclusion settings.
        
        Parameters
        ----------
            args : Collection
                Positional arguments for the underlying function ``F``.
            kwargs : Mapping
                Keyword arguments for the underlying function ``F``.
                
        Returns
        -------
            arguments : dict
                Dictionary of all arguments, including default values
        """
        arguments = self._signature.bind(*args,**kwargs)
        arguments.apply_defaults()
        arguments = arguments.arguments # ordered dict

        # add 'self' for methods                
        if self._is_method:
            # add __self__ to the beginning of all arguments
            full_arguments = OrderedDict()
            if 'self' in set(arguments):
                raise RuntimeError(f"'self' found in bound method '{self.name}' argument list {fmt_dict(self.signature.bind(*args,**kwargs).arguments)}.")
            self__ = getattr(self._F, "__self__", None)
            assert not self__ is None, ("Internal error - was checked above???", self.name, self._F, type(self._F))
            try:
                full_arguments['self'] = self__
            except AttributeError as e:
                raise AttributeError(f"Error extracting '__self__' for {self.name}: {e}") from e
            full_arguments |= arguments
            arguments = full_arguments
            del full_arguments
            
        # filter dictionary
        if not self._exclude_args is None or not self._include_args is None:
            argus  = set(arguments)
            excl   = set(self._exclude_args) if not self._exclude_args is None else set()
            if not self._exclude_args is None: 
                if self._exclude_args > argus:
                    raise ValueError(f"{self.name}: 'exclude_args' contains unknown argument names: exclude_args {sorted(self._exclude_args)} while argument names are {sorted(argus)}.")
            if not self._include_args is None:     
                if self._include_args > argus:
                    raise ValueError(f"{self.name}: 'include_args' contains unknown argument names: include_args {sorted(self._iinclude_args)} while argument names are {sorted(argus)}.")
                excl = argus - self._iinclude_args
            if not self._exclude_args is None:
                excl |= self._exclude_args
            for arg in excl:
                if arg in arguments:
                    del arguments[arg]
            del excl, argus

        if not self._exclude_types is None:
            excl = []
            for k, v in arguments.items():
                if type(v) in self._exclude_types or type(v).__name__ in self._exclude_types:
                    excl.append( k )
            for arg in excl:
                if arg in arguments:
                    del arguments[arg]
        return arguments
    
    def cache_create_id( self, args : Collection, kwargs : Mapping ) -> tuple:
        """
        Expert usage: Creates a unique_id, filename, a label, the sub_dir, and the list of relevant function arguments for parsing the function arguments when ``F(*args,**kwargs)`` is called.
        
        Parameters
        ----------
            args : Collection
                Positional arguments for the underlying function ``F``.
            kwargs : Mapping
                Keyword arguments for the underlying function ``F``.
        
        Returns
        -------
            unique_id : str
                The unique_id for ``F(*args,**kwargs)``.
            filename : str
                Filename for ``F(*args,**kwargs)``, without extension.
            label : str
                The readable label for the function call without hash information (hence not necessarily unique).
            sub_dir : :class:`cdxcore.subdir.SubDir`
                The  directory where ``filename`` is located.
            arguments : Mapping | None
                Result of calling :meth:`cxcore.subdir._CacheWrapper.cache_relevant_arguments`
                if that was required, ``None`` otherwise.
                This is returned for operational efficiency.
        """
        
        uniqueFileName   = self.cache_controller.uniqueFileName
        labelledFileName = self.cache_controller.labelledFileName

        # generate unique 'filename'
        # --------------------------
        
        arguments = None
        
        if not self._uid_or_label.is_simple_str:
            arguments         = self.cache_relevant_arguments(args=args,kwargs=kwargs) if arguments is None else arguments
            full_uid_or_label = self._uid_or_label(**arguments)
        else:
            full_uid_or_label = self._uid_or_label()
            
        if self._unique and "\\" in full_uid_or_label:
            raise ValueError(f"The unique filename '{full_uid_or_label}' computed for '{self._name}' contains '\\'. Use forward slashes to define a directory structure instead.")

        fn_sub_dir   = None
        rix          = full_uid_or_label.rfind("/")
        uid_or_label = full_uid_or_label
        if rix != -1:
            if rix==len(full_uid_or_label)-1:
                raise ValueError(f"The unique filename '{full_uid_or_label}' computed for '{self._name}' terminates with '/'. When using directories also make sure the filename is present.")
            fn_sub_dir   = full_uid_or_label[:rix].split("/")
            uid_or_label = full_uid_or_label[rix+1:]
        del rix

        if self._unique:
            if not is_filename(uid_or_label):
                raise ValueError(f"The unique filename '{full_uid_or_label}' computed for '{self._name}' contains invalid characters for a filename. When using `uid` make sure that "+\
                                 "the returned filename is indeed a valid filename (and unique)")
            if not fn_sub_dir is None:
                for psd in fn_sub_dir:
                    if not is_filename(psd):
                        raise ValueError(f"The unique filename '{full_uid_or_label}' computed for '{self._name}' contains invalid characters in the directory '{psd}'. When using `uid` make sure that "+\
                                        "the returned filename and each of the sub directories is indeed a valid filename (and unique)")              

            label    = uid_or_label
            filename = uniqueFileName( uid_or_label )
        else:
            arguments = self.cache_relevant_arguments(args=args,kwargs=kwargs) if arguments is None else arguments
            label     = uid_or_label
            filename  = labelledFileName( uid_or_label, **arguments )
        del uid_or_label

        # subdir
        # ------
            
        sub_dir = self._subdir
        if not self._in_sub_dir is None:
            if self._in_sub_dir.is_simple_str:
                sub_dir_name = self._in_sub_dir()
            else:
                arguments    = self.cache_relevant_arguments(args=args,kwargs=kwargs) if arguments is None else arguments
                sub_dir_name = self._in_sub_dir( **arguments )
            sub_dir      = sub_dir(sub_dir_name)
            del sub_dir_name
            
        unique_id = None
        if not fn_sub_dir is None:
            unique_id = ""
            for psd in fn_sub_dir:
                if psd=="":
                    raise ValueError(f"The generated filename '{full_uid_or_label}' computed for '{self._name}' contains invalid empty sub-directory.")
                psd       = psd if self._unique else fmt_filename(psd)
                sub_dir   = sub_dir(psd)
                unique_id += psd + "/"

        unique_id = filename if unique_id is None else ( unique_id + filename )
        return unique_id, filename, label, sub_dir, arguments

    def wrapper(self) -> Callable:
        """ Function wrapper which returns the wrapped callable for ``F`` """
        
        idversion = self._F.version.unique_id64
        assert isinstance(idversion, str)
        
        def execute(    *args,
                        override_cache_mode : CacheMode|None = None, 
                        track_cached_files  : CacheTracker|None = None,
                        return_cache_uid    : bool = False,
                        cache_generate_only : bool = False,
                        **kwargs
                    ):     
            """
            Cached execution of the wrapped function ``F`` with additional functionality.
            
            Once the function returns :attr:`cdxcore.subdir._CacheWrapper.cache_info`
            contains pertinent information regarding caching, for example
            if the result returned by this function was cached and if so what file
            was used.
            
            Parameters
            ----------
                args : Collection
                    Keyword arguments for the cached function F.
                    
                kwargs : Collection
                    Keyword arguments for the cached function F.
                    
                override_cache_mode : :class:`cdxcore.subdir.CacheMode` | None, default ``None
                    Changes the caching mode for this function call.
                    For example you can force re-computation by passing ``update``.
    
                track_cached_files : :class:`cdxcore.subdir.CacheTracker` | None, default ``None
                    Allows tracking all cached files - for example for mass deletion.
                    
                return_cache_uid : bool, default ``False``
                    If ``True``, then this function returns not only the result
                    of ``F``, the tuple ``unique_id, result``. This is a thread-safe
                    method of obtaining a ``unique_id`` for a given function call.
                    
                cache_generate_only : bool, default ``False``
                    When ``True`` the function will return a status indicator whether the cached function was called.
                    It therefore returns:
                     
                    * ``False`` if the object this function
                       would compute exists with the correct version (without loading much of it from disk). 
                    * ``True`` if the object did not exist, or had the wrong version, and was therefore re-computed and
                       stored on disk.

                    Using this keyword is an efficient method to generate a list of all objects that would be generated by a function call, without actually loading them from disk.

                    Under the hood this function calls :meth:`cdxcore.subdir.SubDir.is_version`
                    which is a fast operation even for large files.
                    
            Returns
            -------
                Result : Any
                    Return from the function ``F(*args,**kwargs)``, cached or not.
                    
                filename, Result : Any
                    Return from the function ``F(*args,**kwargs)``, cached or not.
            """
            unique_id, filename, label, sub_dir, arguments = self.cache_create_id(args=args,kwargs=kwargs)
                 
            # store process information
            # -------------------------
    
            execute.cache_info.label      = label
            execute.cache_info.filename   = filename # this is the unique ID for this call
            execute.cache_info.unique_id  = unique_id 
            execute.cache_info.path       = sub_dir.path
            
            if self.cache_controller.keep_last_arguments:
                arguments      = self.cache_relevant_arguments(args=args,kwargs=kwargs) if arguments is None else arguments
                info_arguments = OrderedDict()
                for argname, argvalue in arguments.items():
                    info_arguments[argname] = str(argvalue)[:100]
                execute.cache_info.arguments = info_arguments
                del argname, argvalue
            del arguments
                
            # determine version, cache mode
            # -----------------------------
    
            cache_mode = CacheMode(override_cache_mode) if not override_cache_mode is None else self.cache_mode
            del override_cache_mode
    
            # execute caching
            # ---------------

            verify_inp( not cache_generate_only or cache_mode.write, lambda : f"Cannot use 'cache_generate_only' with cache mode {cache_mode}: must allow writing.")
                    
            if cache_mode.delete:
                verify_inp( not cache_generate_only, lambda : f"Cannot use 'cache_generate_only' with cache mode {cache_mode}: cannot force deletion.")
                sub_dir.delete( filename )

            elif cache_mode.read:
                if cache_generate_only and sub_dir.is_version( filename, version=idversion ):
                    execute.cache_info.last_cached = True
                    if not self.debug_verbose is None:
                        self.debug_verbose.write(f"cache({self._name}): confirmed for '{label}' cache '{sub_dir.full_file_name(filename)}' exists and has version '{idversion}'.")
                    # return status "not generated"
                    if return_cache_uid:
                        return unique_id, False
                    return False
                    
                class Tag:
                    pass
                tag = Tag()
                r = sub_dir.read( filename, tag, version=idversion )
                        
                if not r is tag:
                    if not track_cached_files is None:
                        track_cached_files += self._fullFileName(filename)
     
                    execute.cache_info.last_cached = True 
                    if not self.debug_verbose is None:
                        self.debug_verbose.write(f"cache({self._name}): read '{label}' from cache '{sub_dir.full_file_name(filename)}' with version '{idversion}'.")
    
                    if cache_generate_only:
                        # do not return actual result, but a status indicator "was generated"
                        r = False
                    if return_cache_uid:
                        return unique_id, r
                    return r
            else:
                verify_inp( not cache_generate_only, lambda : f"Cannot use 'cache_generate_only' with cache mode {cache_mode}: must allow reading.")

            r = self._F(*args, **kwargs)
            
            if cache_mode.write:
                sub_dir.write(filename,r,version=idversion)      
                if not track_cached_files is None:
                    track_cached_files += sub_dir.full_file_name(filename)
            execute.cache_info.last_cached = False
    
            if not self.debug_verbose is None:
                if cache_mode.write:
                    self.debug_verbose.write(f"cache({self._name}): called '{label}' and wrote result into '{sub_dir.full_file_name(filename)}' with version '{idversion}'.")
                else:
                    self.debug_verbose.write(f"cache({self._name}): called '{label}' but did *not* write into '{sub_dir.full_file_name(filename)}' (version '{idversion}').")
    
            if cache_generate_only:
                # do not return actual result, but status indicator "was generated"
                r = True
            if return_cache_uid:
                return unique_id, r
            return r

        execute.cache_info   = CacheInfo( self._name, 
                                          idversion=idversion, 
                                          keep_last_arguments=self.cache_controller.keep_last_arguments )
        update_wrapper( wrapper=execute, wrapped=self._F )
        return execute

        





