"""
subdir
Simple class to keep track of directory sturctures and for automated caching on disk
Hans Buehler 2020
"""


import os
import os.path
import uuid
import threading
import pickle
import tempfile
import shutil
import datetime
import inspect
from collections import OrderedDict
from collections.abc import Collection, Mapping, Callable
from enum import Enum
import json as json
import platform as platform
from functools import update_wrapper
        
import numpy as np
import jsonpickle as jsonpickle
import jsonpickle.ext.numpy as jsonpickle_numpy
import gzip as gzip
import blosc as blosc

from .err import verify, warn_if, error
from .prettydict import pdct
from .verbose import Context
from .version import Version, version as version_decorator
from .util import fmt_list, fmt_filename, DEF_FILE_NAME_MAP, fmt as txtfmt, plain
from .uniquehash import uniqueHash48, uniqueLabelExt, namedUniqueHashExt

"""
compression
"""
jsonpickle_numpy.register_handlers()
BLOSC_MAX_BLOCK = 2147483631
BLOSC_MAX_USE   = 1147400000 # ... blosc really cannot handle large files

"""
Hashing
"""
uniqueFileName48 = uniqueHash48
uniqueNamedFileName48_16 = namedUniqueHashExt(max_length=48,id_length=16,filename_by=DEF_FILE_NAME_MAP)
uniqueLabelledFileName48_16 = uniqueLabelExt(max_length=48,id_length=16,filename_by=DEF_FILE_NAME_MAP)

def _remove_trailing( path ):
    if len(path) > 0:
        if path[-1] in ['/' or '\\']:
            return _remove_trailing(path[:-1])
    return path

class Format(Enum):
    """ File formats for SubDir """
    PICKLE = 0
    JSON_PICKLE = 1
    JSON_PLAIN = 2
    BLOSC = 3
    GZIP = 4
    
PICKLE = Format.PICKLE
JSON_PICKLE = Format.JSON_PICKLE
JSON_PLAIN = Format.JSON_PLAIN
BLOSC = Format.BLOSC
GZIP = Format.GZIP

"""
Use the following for config calls:
format = subdir.mkFormat( config("format", "pickle", subdir.FORMAT_NAMES, "File format") )
"""
FORMAT_NAMES = [ s.lower() for s in Format.__members__ ]
def mkFormat( name ):
    if not name in FORMAT_NAMES:
        raise LookupError(f"Unknown format name '{name}'. Must be one of: {fmt_list(name)}")
    return Format[name.upper()]

# ========================================================================
# Caching utilities
# ========================================================================

class CacheMode(object):
    """
    CacheMode
    A class which encodes standard behaviour of a caching strategy:

                                                on    gen    off     update   clear   readonly
        load cache from disk if exists          x     x     -       -        -       x
        write updates to disk                   x     x     -       x        -       -
        delete existing object                  -     -     -       -        x       -
        delete existing object if incompatible  x     -     -       x        x       -

    See SubDir.cache() for an implementation.
    """

    ON = "on"
    GEN = "gen"
    OFF = "off"
    UPDATE = "update"
    CLEAR = "clear"
    READONLY = "readonly"

    MODES = [ ON, GEN, OFF, UPDATE, CLEAR, READONLY ]
    HELP = "'on' for standard caching; 'gen' for caching but keep existing incompatible files; 'off' to turn off; 'update' to overwrite any existing cache; 'clear' to clear existing caches; 'readonly' to read existing caches but not write new ones"

    def __init__(self, mode : str = None ):
        """
        Encodes standard behaviour of a caching strategy:

                                                    on    gen    off     update   clear   readonly
            load upon start from disk if exists     x     x     -       -        -       x
            write updates to disk                   x     x     -       x        -       -
            delete existing object upon start       -     -     -       -        x       -
            delete existing object if incompatible  x     -     -       x        x       -

        Parameters
        ----------
            mode : str
                Which mode to use.
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
        """ Whether to load any existing data when starting """
        return self._read

    @property
    def write(self) -> bool:
        """ Whether to write cache data to disk """
        return self._write

    @property
    def delete(self) -> bool:
        """ Whether to delete existing data """
        return self._delete

    @property
    def del_incomp(self) -> bool:
        """ Whether to delete existing data if it is not compatible """
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
        """ Whether this cache mode is OFF """
        return self.mode == self.OFF

    @property
    def is_on(self) -> bool:
        """ Whether this cache mode is ON """
        return self.mode == self.ON

    @property
    def is_gen(self) -> bool:
        """ Whether this cache mode is GEN """
        return self.mode == self.GEN

    @property
    def is_update(self) -> bool:
        """ Whether this cache mode is UPDATE """
        return self.mode == self.UPDATE

    @property
    def is_clear(self) -> bool:
        """ Whether this cache mode is CLEAR """
        return self.mode == self.CLEAR

    @property
    def is_readonly(self) -> bool:
        """ Whether this cache mode is READONLY """
        return self.mode == self.READONLY

class CacheController( object ):
    """
    Central control for caching.
    Enabes to to turn on/off caching, debugging and tracks all versions
    """
    
    def __init__(self, *,
                    exclude_arg_types  : list[type] = [Context],
                    cache_mode         : CacheMode = CacheMode.ON,
                    max_filename_length: int = 48,
                    hash_length        : int = 16,
                    debug_verbose      : Context = None,
                    keep_last_arguments: bool = False
                    ):
        """
        Parameters to control caching behaviour when using SubDir.cache
        
        Parameters
        ----------
            exclude_arg_types :
                List of types to exclude from producing unique ids from function arguments. Defaults to [SubDir, Context]
            cache_mode :
                Top level cache control. Set to "OFF" to turn off all caching. Default is "ON"
            max_filename_length :
                Maximum filename length. If unique id's exceed the file name a hash of length 'hash_length' will be intergated into the file name.
                See cdxbasics.util.namedUniqueHashExt and cdxbasics.util.uniqueLabelExt
            hash_length :
                Length of the hash used to make sure each filename is unique
                See cdxbasics.util.namedUniqueHashExt and cdxbasics.util.uniqueLabelExt
            debug_verbose :
                If non-None print caching process messages to this object.
            keep_last_arguments :
                keep a dictionary of all parameters as string representations after each function call.
                If the function F was decorated using SubDir.cache(), you can access this information via
                    F.cache_info.last_arguments
                Note that strings are limited to 100 characters per argument to avoid memory
                overload when large objects are passed.
        """
        max_filename_length          = int(max_filename_length)
        hash_length                  = int(hash_length)
        assert max_filename_length>0, ("'max_filename_length' must be positive")
        assert hash_length>0 and hash_length<=max_filename_length, ("'hash_length' must be positive and at most 'max_filename_length'")
        assert max_filename_length>=hash_length, ("'hash_length' must not exceed 'max_filename_length")
        self.cache_mode             = CacheMode(cache_mode if not cache_mode is None else CacheMode.ON)
        self.debug_verbose          = debug_verbose
        self.exclude_arg_types      = set(exclude_arg_types) if not exclude_arg_types is None else None
        self.versioned              = pdct()  # list
        self.uniqueNamedFileName    = namedUniqueHashExt(max_length=max_filename_length,id_length=hash_length,filename_by=DEF_FILE_NAME_MAP)
        self.uniqueLabelledFileName = uniqueLabelExt(max_length=max_filename_length,id_length=hash_length,filename_by=DEF_FILE_NAME_MAP)
        self.keep_last_arguments    = keep_last_arguments

default_cacheController = CacheController()


class CacheTracker(object):
    """
    Utility class to track caching and be able to delete all dependent objects
    
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

class InitCacheInfo(object):
    pass

class CacheInfo(object):
    pass
    
# SubDir
# ======

class SubDir(object):
    """
    SubDir implements a transparent interface for storing data in files, with a common extension.
    The generic pattern is:

        1) create a root 'parentDir':
            Absolute:                      parentDir = SubDir("C:/temp/root")
            In system temp directory:      parentDir = SubDir("!/root")
            In user directory:             parentDir = SubDir("~/root")
            Relative to current directory: parentDir = SubDir("./root")

        2) Use SubDirs to transparently create hierachies of stored data:
           assume f() will want to store some data:

               def f(parentDir, ...):

                   subDir = parentDir('subdir')    <-- note that the call () operator is overloaded: if a second argument is provided, the directory will try to read the respective file.
                   or
                   subDir = SubDir('subdir', parentDir)
                    :
                    :
            Write data:

                   subDir['item1'] = item1       <-- dictionary style
                   subDir.item2 = item2          <-- member style
                   subDir.write('item3',item3)   <-- explicit

            Note that write() can write to multiple files at the same time.

        3) Reading is similar

                def readF(parentDir,...):

                    subDir = parentDir('subdir')

                    item = subDir('item', 'i1')     <-- returns 'i1' if not found.
                    item = subdir.read('item')      <-- returns None if not found
                    item = subdir.read('item','i2') <-- returns 'i2' if not found
                    item = subDir['item']           <-- throws a KeyError if not found
                    item = subDir.item              <-- throws an AttributeError if not found

        4) Treating data like dictionaries

                def scanF(parentDir,...)

                    subDir = parentDir('f')

                    for item in subDir:
                        data = subDir[item]

            Delete items:

                del subDir['item']             <-- silently fails if 'item' does not exist
                del subDir.item                <-- silently fails if 'item' does not exist
                subDir.delete('item')          <-- silently fails if 'item' does not exist
                subDir.delete('item', True)    <-- throw a KeyError if 'item' does not exit

        5) Cleaning up

                parentDir.deleteAllContent()       <-- silently deletes all files and sub directories.

        6) As of version 0.2.59 subdir supports json file formats. Those can be controlled with the 'fmt' keyword in various functions.
        The most straightfoward way is to specify the format of the directory itself:

                subdir = SubDir("!/.test", fmt=SubDir.JSON_PICKLE)

        The following formats are supported:

            SubDir.PICKLE:
                Use pickle
            SubDir.JSON_PLAIN:
                Uses cdxbasics.util.plain() to convert data into plain Python objects and writes
                this to disk as text. Loading back such files will result in plain Python objects,
                but *not* the original objects
            SubDir.JSON_PICKLE:
                Uses the jsonpickle package to load/write data in somewhat readable text formats.
                Data can be loaded back from such a file, but files may not be readable (e.g. numpy arrays
                are written in compressed form).
            SubDir.BLOSC:
                Uses https://www.blosc.org/python-blosc/ to compress data on-the-fly.
                BLOSC is much faster than GZIP but is limited to 2GB data, sadly.
            SubDir.GZIP:
                Uses https://docs.python.org/3/library/zlib.html to compress data on-the-fly
                using, essentially, GZIP.

            Summary of properties:

                          | Restores objects | Human readable | Speed | Compression
             PICKLE       | yes              | no             | high  | no
             JSON_PLAIN   | no               | yes            | low   | no
             JSON_PICKLE  | yes              | limited        | low   | no
             BLOSC        | yes              | no             | high  | yes
             GZIP         | yes              | no             | high  | yes

        Several other operations are supported; see help()

        Hans Buehler May 2020
    """

    class __RETURN_SUB_DIRECTORY(object):
        pass

    Format = Format
    PICKLE = Format.PICKLE
    JSON_PICKLE = Format.JSON_PICKLE
    JSON_PLAIN = Format.JSON_PLAIN
    BLOSC = Format.BLOSC
    GZIP = Format.GZIP

    DEFAULT_RAISE_ON_ERROR = False
    RETURN_SUB_DIRECTORY = __RETURN_SUB_DIRECTORY
    DEFAULT_FORMAT = Format.PICKLE
    DEFAULT_CREATE_DIRECTORY = False  # legacy behaviour so that self.path is a valid path
    EXT_FMT_AUTO = "*"

    MAX_VERSION_BINARY_LEN = 128

    VER_NORMAL   = 0
    VER_CHECK    = 1
    VER_RETURN   = 2
    
    def __init__(self, name : str, 
                       parent = None, *, 
                       ext : str = None, 
                       fmt : Format = None, 
                       eraseEverything : bool = False,
                       createDirectory : bool = None,
                       cacheController : CacheController = None
                       ):
        """
        Instantiates a sub directory which contains pickle files with a common extension.
        By default the directory is created.

        Absolute directories
            sd  = SubDir("!/subdir")           - relative to system temp directory
            sd  = SubDir("~/subdir")           - relative to user home directory
            sd  = SubDir("./subdir")           - relative to current working directory (explicit)
            sd  = SubDir("subdir")             - relative to current working directory (implicit)
            sd  = SubDir("/tmp/subdir")        - absolute path (linux)
            sd  = SubDir("C:/temp/subdir")     - absolute path (windows)
        Short-cut
            sd  = SubDir("")                   - current working directory

        It is often desired that the user specifies a sub-directory name under some common parent directory.
        You can create sub directories if you provide a 'parent' directory:
            sd2 = SubDir("subdir2", parent=sd) - relative to other sub directory
            sd2 = sd("subdir2")                - using call operator
        Works with strings, too:
            sd2 = SubDir("subdir2", parent="~/my_config") - relative to ~/my_config

        All files managed by SubDir will have the same extension.
        The extension can be specified with 'ext', or as part of the directory string:
            sd  = SubDir("~/subdir;*.bin")      - set extension to 'bin'

        COPY CONSTRUCTION
        This function also allows copy construction and constrution from a repr() string.

        HANDLING KEYS
        SubDirs allows reading data using the item and attribute notation, i.e. we may use
            sd = SubDir("~/subdir")
            x  = sd.x
            y  = sd['y']
        If the respective keys are not found, exceptions are thrown.

        NONE OBJECTS
        It is possible to set the directory name to 'None'. In this case the directory will behave as if:
            No files exist
            Writing fails with a EOFError.

        Parameters
        ----------
            name            - Name of the directory.
                               '.' for current directory
                               '~' for home directory
                               '!' for system default temp directory
                              May contain a formatting string for defining 'ext' on the fly:
                                Use "!/test;*.bin" to specify 'test' in the system temp directory as root directory with extension 'bin'
                              Can be set to None, see above.
            parent          - Parent directory. If provided, will also set defaults for 'ext' and 'raiseOnError'
            ext             - standard file extenson for data files. All files will share the same extension.
                              If None, use the parent extension, or if that is not specified use an extension depending on 'fmt':
                                     'pck' for the default PICKLE format
                                     'json' for JSON_PLAIN
                                     'jpck' for JSON_PICKLE
                              Set to "" to turn off managing extensions.
            fmt             - format, current pickle or json
            eraseEverything - delete all contents in the newly defined subdir
            createDirectory - whether to create the directory.
                              Otherwise it will be created upon first write().
                              Set to None to use the setting of the parent directory       
        """
        createDirectory = bool(createDirectory) if not createDirectory is None else None
        
        # copy constructor support
        if isinstance(name, SubDir):
            assert parent is None, "Internal error: copy construction does not accept 'parent' keyword"
            self._path  = name._path
            self._ext   = name._ext if ext is None else ext
            self._fmt   = name._fmt if fmt is None else fmt
            self._crt   = name._crt if createDirectory is None else createDirectory
            self._cctrl = name._cctrl if cacheController is None else cacheController
            if eraseEverything: raise ValueError( "Cannot use 'eraseEverything' when cloning a directory")
            return

        # reconstruction from a dictionary
        if isinstance(name, Mapping):
            assert parent is None, "Internal error: dictionary construction does not accept 'parent keyword"
            self._path  = name['_path']
            self._ext   = name['_ext'] if ext is None else ext
            self._fmt   = name['_fmt'] if fmt is None else fmt
            self._crt   = name['_crt'] if createDirectory is None else createDirectory
            self._cctrl = name['_cctrl'] if cacheController is None else cacheController
            if eraseEverything: raise ValueError( "Cannot use 'eraseEverything' when cloning a directory")
            return

        # parent
        if isinstance(parent, str):
            parent = SubDir( parent, ext=ext, fmt=fmt, createDirectory=createDirectory, cacheController=cacheController )
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
            
        # createDirectory
        if createDirectory is None:
            self._crt = self.DEFAULT_CREATE_DIRECTORY if parent is None else parent._crt
        else:
            self._crt = bool(createDirectory)
            
        # cache controller
        assert type(cacheController).__name__ == CacheController.__name__, ("'cacheController' should be of type 'CacheController'", type(cacheController))
        self._cctrl = cacheController

        # name
        if name is None:
            if not parent is None and not parent._path is None:
                name = parent._path[:-1]
        else:
            # expand name
            name = _remove_trailing(name)
            if name == "" and parent is None:
                name = "."
            if name[:1] in ['!', '~'] or name[:2] == "./" or name == ".":
                if len(name) > 1 and name[1] != '/':
                    raise ValueError( txtfmt("If 'name' starts with '%s', then the second character must be '/' (or '\\' on windows). Found 'name' set to '%s'", name[:1], _name ))
                if name[0] == '!':
                    name = SubDir.tempDir()[:-1] + name[1:]
                elif name[0] == ".":
                    name = SubDir.workingDir()[:-1] + name[1:]
                else:
                    assert name[0] == "~", ("Internal error", name[0] )
                    name = SubDir.userDir()[:-1] + name[1:]
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

            if eraseEverything:
                self.eraseEverything(keepDirectory=self._crt)
            if self._crt:
                self.createDirectory()

    @staticmethod
    def expandStandardRoot( name ):
        """
        Expands 'name' by a standardized root directory if provided:
        If 'name' starts with -> return
            ! -> tempDir()
            . -> workingDir()
            ~ -> userDir()
        """
        if len(name) < 2 or name[0] not in ['.','!','~'] or name[1] not in ["\\","/"]:
            return name
        if name[0] == '!':
            return SubDir.tempDir() + name[2:]
        elif name[0] == ".":
            return SubDir.workingDir() + name[2:]
        else:
            return SubDir.userDir() + name[2:]

    def createDirectory( self ):
        """
        Creates the directory if it doesn't exist yet.
        Does not do anything if is_none.
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

    def pathExists(self) -> bool:
        """ Returns True if the current directory exists """
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
        """ Whether this object is 'None' or not """
        return self._path is None

    @property
    def path(self) -> str:
        """
        Return current path, including trailing '/'
        Note that the path may not exist yet. If this is required, consider using existing_path
        """
        return self._path

    @property
    def existing_path(self) -> str:
        """
        Return current path, including training '/'.
        In addition to self.path this property ensures that the directory structure exists (or raises an exception)
        """
        self.createDirectory()
        return self.path

    @property
    def fmt(self) -> Format:
        """ Returns current format """
        return self._fmt
    
    @property
    def ext(self) -> str:
        """
        Returns the common extension of the files in this directory, including leading '.'
        Resolves '*' into the extension associated with the current format.
        """
        return self._ext if self._ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def autoExt( self, ext : str = None ) -> str:
        """
        Computes the effective extension based on inputs 'ext', defaulting to the SubDir's extension.
        Resolves '*' into the extension associated with the specified format.
        This function allows setting 'ext' also as a Format.
        
        Returns the extension with leading '.'
        """
        if isinstance(ext, Format):
            return self._auto_ext(ext)
        else:
            ext = self._ext if ext is None else SubDir._extract_ext(ext)
            return ext if ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def autoExtFmt( self, *, ext : str = None, fmt : Format = None ) -> str:
        """
        Computes the effective extension and format based on inputs 'ext' and 'fmt', each of which defaults to the SubDir's current settings.
        Resolves '*' into the extension associated with the specified format.
        This function allows setting 'ext' also as a Format.

        Returns (ext, fmt) where 'ext' contains the leading '.'
        """
        if isinstance(ext, Format):
            verify( fmt is None or fmt == ext, "If 'ext' is a Format, then 'fmt' must match 'ext' or be None. Found '%s' and '%s', respectively.", ext, fmt, exception=ValueError )
            return self._auto_ext(ext), ext

        fmt = fmt if not fmt is None else self._fmt
        ext = self._ext if ext is None else SubDir._extract_ext(ext)
        ext = ext if ext != self.EXT_FMT_AUTO else self._auto_ext(fmt)
        return ext, fmt
    
    @property
    def cacheController(self):
        """ Returns an assigned CacheController, or None """
        return self._cctrl if not self._cctrl is None else default_cacheController

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
        """ Convert string version to byte string of at most size MAX_VERSION_BINARY_LEN + 1 """
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

    def fullFileName(self, key : str, *, ext : str = None) -> str:
        """
        Returns fully qualified file name.
        The function tests that 'key' does not contain directory information.

        If 'self' is None, then this function returns None
        If key is None then this function returns None

        Parameters
        ----------
            key : str
                Core file name, e.g. the 'key' in a data base sense
            ext : str
                If not None, use this extension rather than self.ext

        Returns
        -------
            Fully qualified system file name

        [This function has an alias 'fullKeyName' for backward compatibility]
        """
        if self._path is None or key is None:
            return None
        key = str(key)
        verify( len(key) > 0, "'key' cannot be empty")

        sub, _ = os.path.split(key)
        verify( len(sub) == 0, "Key '%s' contains directory information", key)

        verify( key[0] != "!", "Key '%s' cannot start with '!' (this symbol indicates the temp directory)", key, exception=ValueError )
        verify( key[0] != "~", "Key '%s' cannot start with '~' (this symbol indicates the user's directory)", key, exception=ValueError )

        ext = self.autoExt( ext )
        if len(ext) > 0 and key[-len(ext):] != ext:
            return self._path + key + ext
        return self._path + key
    fullKeyName = fullFileName # backwards compatibility

    @staticmethod
    def tempDir() -> str:
        """
        Return system temp directory. Short cut to tempfile.gettempdir()
        Result contains trailing '/'
        """
        d = tempfile.gettempdir()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-1", d)
        return d + "/"

    @staticmethod
    def workingDir() -> str:
        """
        Return current working directory. Short cut for os.getcwd()
        Result contains trailing '/'
        """
        d = os.getcwd()
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-2", d)
        return d + "/"

    @staticmethod
    def userDir() -> str:
        """
        Return current working directory. Short cut for os.path.expanduser('~')
        Result contains trailing '/'
        """
        d = os.path.expanduser('~')
        assert len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), ("*** Internal error 13123212-3", d)
        return d + "/"

    # -- read --

    def _read_reader( self, reader, key : str, default, raiseOnError : bool, *, ext : str = None ):
        """
        Utility function for read() and readLine()

        Parameters
        ----------
            reader( key, fullFileName, default )
                A function which is called to read the file once the correct directory is identified
                key : key (for error messages, might include '/')
                fullFileName : full file name
                default value
            key : str or list
                str: fully qualified key
                list: list of fully qualified names
            default :
                default value. None is a valid default value
                list : list of defaults for a list of keys
            raiseOnError : bool
                If True, and the file does not exist, throw exception
            ext :
                Extension or None for current extension.
                list : list of extensions for a list of keys
        """
        # vector version
        if not isinstance(key,str):
            if not isinstance(key, Collection): raise ValueError(txtfmt( "'key' must be a string, or an interable object. Found type %s", type(key)))
            l = len(key)
            if default is None or isinstance(default,str) or not isinstance(default, Collection):
                default = [ default ] * l
            else:
                if len(default) != l: raise ValueError(txtfmt("'default' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(default), l ))
            if ext is None or isinstance(ext, str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: raise ValueError(txtfmt("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l ))
            return [ self._read_reader(reader=reader,key=k,default=d,raiseOnError=raiseOnError,ext=e) for k, d, e in zip(key,default,ext) ]

        # deleted directory?
        if self._path is None:
            verify( not raiseOnError, "Trying to read '%s' from an empty directory object", key, exception=NotADirectoryError)
            return default

        # single key
        if len(key) == 0: raise ValueError(txtfmt("'key' missing (the filename)" ))
        sub, key_ = os.path.split(key)
        if len(sub) > 0:
            return self(sub)._read_reader(reader=reader,key=key_,default=default,raiseOnError=raiseOnError,ext=ext)
        if len(key_) == 0: ValueError(txtfmt("'key' %s indicates a directory, not a file", key))

        # don't try if directory doesn't exist
        fullFileName = self.fullFileName(key,ext=ext)
        if not self.pathExists():
            if raiseOnError:
                raise KeyError(key, fullFileName)
            return default
        
        # does file exit?
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key,fullFileName)
            return default
        if not os.path.isfile(fullFileName):
            raise IOError(txtfmt( "Cannot read %s: object exists, but is not a file (full path %s)", key, fullFileName ))

        # read content
        # delete existing files upon read error
        try:
            return reader( key, fullFileName, default )
        except EOFError as e:
            try:
                os.remove(fullFileName)
                warn("Cannot read %s; file deleted (full path %s).\nError: %s",key,fullFileName, str(e))
            except Exception as e:
                warn("Cannot read %s; attempt to delete file failed (full path %s): %s",key,fullFileName,str(e))
        except FileNotFoundError as e:
            if raiseOnError:
                raise KeyError(key, fullFileName, str(e)) from e
        except Exception as e:
            if raiseOnError:
                raise KeyError(key, fullFileName, str(e)) from e
        except (ImportError, BaseException) as e:
            e.add_note( key )
            e.add_note( fullFileName )
            raise e
        return default

    def _read( self, key : str,
                    default = None,
                    raiseOnError : bool = False,
                    *,
                    version : str = None,
                    ext : str = None,
                    fmt : Format = None,
                    delete_wrong_version : bool = True,
                    handle_version : int = 0
                    ):
        """ See read() """
        ext, fmt = self.autoExtFmt(ext=ext, fmt=fmt)
        version  = str(version) if not version is None else None
        version  = version if handle_version != SubDir.VER_RETURN else ""
        assert not fmt == self.EXT_FMT_AUTO, ("'fmt' is '*' ...?")

        if version is None and fmt in [Format.BLOSC, Format.GZIP]:
            version = ""

        def reader( key, fullFileName, default ):
            test_version = "(unknown)"
            if fmt == Format.PICKLE or fmt == Format.BLOSC:
                with open(fullFileName,"rb") as f:
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
                        if fmt == Format.PICKLE:
                            data = pickle.load(f)
                        elif fmt == Format.BLOSC:
                            if blosc is None:
                                raise ModuleNotFoundError("blosc", "'blosc' not found.")
                            nnbb       = f.read(2)
                            num_blocks = int.from_bytes( nnbb, 'big', signed=False )
                            data       = bytearray()
                            for i in range(num_blocks):
                                blockl = int.from_bytes( f.read(6), 'big', signed=False )
                                if blockl>0:
                                    bdata  = blosc.decompress( f.read(blockl) )
                                    data  += bdata
                                    del bdata
                            data = pickle.loads(data)
                        else:
                            raise NotImplementedError(fmt, txtfmt("Unkown format '%s'", fmt))
                        return data

            elif fmt == Format.GZIP:
                if gzip is None:
                    raise ModuleNotFoundError("gzip", "'gzip' not found'")
                with gzip.open(fullFileName,"rb") as f:
                    # handle version as byte string
                    ok           = True
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
                with open(fullFileName,"rt",encoding="utf-8") as f:
                    # handle versioning
                    ok      = True
                    if not version is None:
                        test_version = f.readline()
                        if test_version[:2] != "# ":
                            raise EnvironmentError("Error reading '%s': file does not appear to contain a version (it should start with '# ')" % fullFileName)
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
                            if jsonpickle is None:
                                raise ModuleNotFoundError("jsonpickle", "'jsonpickle' not found'")
                            return jsonpickle.decode( f.read() )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: unknown Format", fmt)
                            return json.loads( f.read() )
            else:
                raise NotImplementedError(fmt, txtfmt("Unknown format '%s'", fmt ))

            # arrive here if version is wrong
            # delete a wrong version
            deleted = ""
            if delete_wrong_version:
                try:
                    os.remove(fullFileName)
                    e = None
                except Exception as e_:
                    e = str(e_)
            if handle_version == SubDir.VER_CHECK:
                return False
            if not raiseOnError:
                return default
            deleted = " (file was deleted)" if e is None else " (attempt to delete file failed: %s)" % e
            raise EnvironmentError("Error reading '%s': found version '%s' not '%s'%s" % (fullFileName,str(test_version),str(version),deleted))

        return self._read_reader( reader=reader, key=key, default=default, raiseOnError=raiseOnError, ext=ext )

    def read( self, key : str,
                    default = None,
                    raiseOnError : bool = False,
                    *,
                    version : str = None,
                    delete_wrong_version : bool = True,
                    ext : str = None,
                    fmt : Format = None
                    ):
        """
        Read pickled data from 'key' if the file exists, or return 'default'
        -- Supports 'key' containing directories
        -- Supports 'key' (and default, ext) being iterable.
           In this case any any iterable 'default' except strings are considered accordingly.
           In order to have a unit default which is an iterable, you will have to wrap it in another iterable, e.g.
           E.g.:
              keys = ['file1', 'file2']

              sd.read( keys )
              --> works, both are using default None

              sd.read( keys, 1 )
              --> works, both are using default '1'

              sd.read( keys, [1,2] )
              --> works, defaults 1 and 2, respectively

              sd.read( keys, [1] )
              --> produces error as len(keys) != len(default)

            Strings are iterable but are treated as single value.
            Therefore
                sd.read( keys, '12' )
            means the default value '12' is used for both files.
            Use
                sd.read( keys, ['1','2'] )
            in case the intention was using '1' and '2', respectively.

        Returns the read object, or a list of objects if 'key' was iterable.
        If the current directory is 'None', then behaviour is as if the file did not exist.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            default :
                Default value, or default values if key is a list
            raiseOnError : bool
                Whether to raise an exception if reading an existing file failed.
                By default this function fails silently and returns the default.
            version : str
                If not None, specifies the version of the current code base.
                In this case, this version will be compared to the version of the file being read.
                If they do not match, read fails (either by returning default or throwing an exception).
                You can specify version "*" to read any version. This is distrinct from reading a file without version.
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            For a single 'key': Content of the file if successfully read, or 'default' otherwise.
            If 'key' is a list: list of contents.
        """
        return self._read( key=key,
                           default=default,
                           raiseOnError=raiseOnError,
                           version=version,
                           ext=ext,
                           fmt=fmt,
                           delete_wrong_version=delete_wrong_version,
                           handle_version=SubDir.VER_NORMAL )

    get = read # backwards compatibility

    def is_version( self, key : str, version : str = None, raiseOnError : bool = False, *, ext : str = None, fmt : Format = None, delete_wrong_version : bool = True ):
        """
        Compares the version of 'key' with 'version'.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            version : str
                Specifies the version of the current code base to compare with.
                You can use '*' to match any version

            raiseOnError : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list.
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            Returns True only if the file exists and has the correct version.
        """
        return self._read( key=key,default=False,raiseOnError=raiseOnError,version=version,ext=ext,fmt=fmt,delete_wrong_version=delete_wrong_version,handle_version=SubDir.VER_CHECK )

    def get_version( self, key : str, raiseOnError : bool = False, *, ext : str = None, fmt : Format = None ):
        """
        Returns the version ID stored in 'key'.
        This requires that the file has previously been saved with a version.
        Otherwise this function will return unpredictable results.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            raiseOnError : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
            ext : str
                Extension overwrite, or a list thereof if key is a list.
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            Version ID.
        """
        return self._read( key=key,default=None,raiseOnError=raiseOnError,version="",ext=ext,fmt=fmt,delete_wrong_version=False,handle_version=SubDir.VER_RETURN )

    def readString( self, key : str, default = None, raiseOnError : bool = False, *, ext : str = None ) -> str:
        """
        Reads text from 'key' or returns 'default'. Removes trailing EOLs
        -- Supports 'key' containing directories#
        -- Supports 'key' being iterable. In this case any 'default' can be a list, too.

        Returns the read string, or a list of strings if 'key' was iterable.
        If the current directory is 'None', then behaviour is as if the file did not exist.

        Use 'ext' to specify the extension.
        You cannot use 'ext' to specify a format as the format is plain text.
        If 'ext' is '*' or if self._ext is '*' then the default extension is 'txt'.
        """
        verify( not isinstance(ext, Format), "Cannot change format when writing strings. Found extension '%s'", ext)
        ext = ext if not ext is None else self._ext
        ext = ext if ext != self.EXT_FMT_AUTO else ".txt"

        def reader( key, fullFileName, default ):
            with open(fullFileName,"rt",encoding="utf-8") as f:
                line = f.readline()
                if len(line) > 0 and line[-1] == '\n':
                    line = line[:-1]
                return line
        return self._read_reader( reader=reader, key=key, default=default, raiseOnError=raiseOnError, ext=ext )

    # -- write --

    def _write( self, writer, key : str, obj, raiseOnError : bool, *, ext : str = None ) -> bool:
        """ Utility function for write() and writeLine() """
        if self._path is None:
            raise EOFError("Cannot write to '%s': current directory is not specified" % key)
        self.createDirectory()

        # vector version
        if not isinstance(key,str):
            if not isinstance(key, Collection): error( "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if obj is None or isinstance(obj,str) or not isinstance(obj, Collection):
                obj = [ obj ] * l
            else:
                if len(obj) != l: error("'obj' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(obj), l )
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            ok = True
            for k,o,e in zip(key,obj,ext):
                ok |= self._write( writer, k, o, raiseOnError=raiseOnError, ext=e )
            return ok

        # single key
        if not len(key) > 0: error("'key is empty (the filename)" )
        sub, key = os.path.split(key)
        if len(key) == 0: error("'key '%s' refers to a directory, not a file", key)
        if len(sub) > 0:
            return SubDir(sub,parent=self)._write(writer,key,obj, raiseOnError=raiseOnError,ext=ext )

        # write to temp file, then rename into target file
        # this reduces collision when i/o operations are slow
        fullFileName = self.fullKeyName(key,ext=ext)
        tmp_file     = uniqueHash48( [ key, uuid.getnode(), os.getpid(), threading.get_ident(), datetime.datetime.now() ] )
        tmp_i        = 0
        fullTmpFile  = self.fullKeyName(tmp_file,ext="tmp" if not ext=="tmp" else "_tmp")
        while os.path.exists(fullTmpFile):
            fullTmpFile = self.fullKeyName(tmp_file) + "." + str(tmp_i) + ".tmp"
            tmp_i       += 1
            if tmp_i >= 10:
                raise RuntimeError("Failed to generate temporary file for writing '%s': too many temporary files found. For example, this file already exists: '%s'" % ( fullFileName, fullTmpFile ) )

        # write
        if not writer( key, fullTmpFile, obj ):
            return False
        assert os.path.exists(fullTmpFile), ("Internal error: file does not exist ...?", fullTmpFile, fullFileName)
        try:
            if os.path.exists(fullFileName):
                os.remove(fullFileName)
            os.rename(fullTmpFile, fullFileName)
        except Exception as e:
            os.remove(fullTmpFile)
            if raiseOnError:
                raise e
            return False
        return True

    def write( self, key : str,
                     obj,
                     raiseOnError : bool = True,
                     *,
                     version : str = None,
                     ext : str = None,
                     fmt : Format = None ) -> bool:
        """
        Pickles 'obj' into key.
        -- Supports 'key' containing directories
        -- Supports 'key' being a list.
           In this case, if obj is an iterable it is considered the list of values for the elements of 'keys'
           If 'obj' is not iterable, it will be written into all 'key's

              keys = ['file1', 'file2']

              sd.write( keys, 1 )
              --> works, writes '1' in both files.

              sd.read( keys, [1,2] )
              --> works, writes 1 and 2, respectively

              sd.read( keys, "12" )
              --> works, writes '12' in both files

              sd.write( keys, [1] )
              --> produces error as len(keys) != len(obj)

        If the current directory is 'None', then the function throws an EOFError exception

        Parameters
        ----------
            key : str
                Core filename ("key"), or list thereof
            obj :
                Object to write, or list thereof if 'key' is a list
            raiseOnError : bool
                If False, this function will return False upon failure
            version : str
                If not None, specifies the version of the code which generated 'obj'.
                This version will be written to the beginning of the file.
            ext : str
                Extension, or list thereof if 'key' is a list.
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            Boolean to indicate success if raiseOnError is False.
        """
        ext, fmt = self.autoExtFmt(ext=ext, fmt=fmt)
        version  = str(version) if not version is None else None
        assert ext != self.EXT_FMT_AUTO, ("'ext' is '*'...?")

        if version=='*': error("You cannot write version '*'. Use None to write a file without version.")
        if version is None and fmt in [Format.BLOSC, Format.GZIP]:
            version = ""

        def writer( key, fullFileName, obj ):
            try:
                if fmt == Format.PICKLE or fmt == Format.BLOSC:
                    with open(fullFileName,"wb") as f:
                        # handle version as byte string
                        if not version is None:
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: error("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        if fmt == Format.PICKLE:
                            pickle.dump(obj,f,-1)
                        else:
                            assert fmt == fmt.BLOSC, ("Internal error: unknown format", fmt)
                            if blosc is None:
                                raise ModuleNotFoundError("blosc", "'blosc' not found")
                            pdata      = pickle.dumps(obj)  # returns data as a bytes object
                            del obj
                            len_data   = len(pdata)
                            num_blocks = max(0,len_data-1) // BLOSC_MAX_USE + 1
                            f.write(num_blocks.to_bytes(2, 'big', signed=False))
                            for i in range(num_blocks):
                                start  = i*BLOSC_MAX_USE
                                end    = min(len_data,start+BLOSC_MAX_USE)
                                assert end>start, ("Internal error; nothing to write")
                                block  = blosc.compress( pdata[start:end] )
                                blockl = len(block)
                                f.write( blockl.to_bytes(6, 'big', signed=False) )
                                if blockl > 0:
                                    f.write( block )
                                del block
                            del pdata

                elif fmt == Format.GZIP:
                    if gzip is None:
                        raise ModuleNotFoundError("gzip", "'gzip' not found")
                    with gzip.open(fullFileName,"wb") as f:
                        # handle version as byte string
                        if not version is None:
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: error("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        pickle.dump(obj,f,-1)

                elif fmt in [Format.JSON_PLAIN, Format.JSON_PICKLE]:
                    with open(fullFileName,"wt",encoding="utf-8") as f:
                        if not version is None:
                            f.write("# " + version + "\n")
                        if fmt == Format.JSON_PICKLE:
                            if jsonpickle is None:
                                raise ModuleNotFoundError("jsonpickle", "'jsonpickle' not found")
                            f.write( jsonpickle.encode(obj) )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: invalid Format", fmt)
                            f.write( json.dumps( plain(obj, sorted_dicts=True, native_np=True, dt_to_str=True ), default=str ) )

                else:
                    raise NotImplementedError(fmt, txtfmt("Internal error: invalid format '%s'", fmt))
            except Exception as e:
                if raiseOnError:
                    raise e
                return False
            return True
        return self._write( writer=writer, key=key, obj=obj, raiseOnError=raiseOnError, ext=ext )

    set = write

    def writeString( self, key : str, line : str, raiseOnError : bool = True, *, ext : str = None ) -> bool:
        """
        Writes 'line' into key. A trailing EOL will not be read back
        -- Supports 'key' containing directories
        -- Supports 'key' being a list.
           In this case, line can either be the same value for all key's or a list, too.

        If the current directory is 'None', then the function throws an EOFError exception
        See additional comments for write()
        
        Use 'ext' to specify the extension.
        You cannot use 'ext' to specify a format as the format is plain text.
        If 'ext' is '*' or if self._ext is '*' then the default extension is 'txt'.
        """
        verify( not isinstance(ext, Format), "Cannot change format when writing strings. Found extension '%s'", ext, exception=ValueError )
        ext = ext if not ext is None else self._ext
        ext = ext if ext != self.EXT_FMT_AUTO else ".txt"
        
        if len(line) == 0 or line[-1] != '\n':
            line += '\n'
        def writer( key, fullFileName, obj ):
            try:
                with open(fullFileName,"wt",encoding="utf-8") as f:
                    f.write(obj)
            except Exception as e:
                if raiseOnError:
                    raise e
                return False
            return True
        return self._write( writer=writer, key=key, obj=line, raiseOnError=raiseOnError, ext=ext )

    # -- iterate --

    def files(self, *, ext : str = None) -> list:
        """
        Returns a list of keys in this subdirectory with the current extension, or the specified extension.

        In other words, if the extension is ".pck", and the files are "file1.pck", "file2.pck", "file3.bin"
        then this function will return [ "file1", "file2" ]

        If 'ext' is
        -- None, the directory's default extension will be used
        -- "" then this function will return all files in this directory.
        -- a Format, then the default extension of the format will be used.

        This function ignores directories. Use subDirs() to retrieve those.

        [This function has an alias 'keys']
        """
        if not self.pathExists():
            return []
        ext   = self.autoExt( ext=ext )
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
    keys = files

    def subDirs(self) -> list:
        """
        Returns a list of all sub directories
        If self does not refer to an existing directory, then this function returns an empty list.
        """
        # do not do anything if the object was deleted
        if not self.pathExists():
            return []
        subdirs = []
        with os.scandir(self._path[:-1]) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                subdirs.append( entry.name )
        return subdirs

    # -- delete --

    def delete( self, key : str, raiseOnError: bool  = False, *, ext : str = None ):
        """
        Deletes 'key'; 'key' might be a list.

        Parameters
        ----------
            key :
                filename, or list of filenames
            raiseOnError :
                if False, do not throw KeyError if file does not exist.
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" to not use an automatic extension.
                -- A Format to specify the default extension for that format.
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete '%s': current directory not specified" % key)
            return
            
        # vector version
        if not isinstance(key,str):
            if not isinstance(key, Collection): error( "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            for k, e in zip(key,ext):
                self.delete(k, raiseOnError=raiseOnError, ext=e)
            return

        # handle directories in 'key'
        if len(key) == 0: error( "'key' is empty" )
        sub, key_ = os.path.split(key)
        if len(key_) == 0: error("'key' %s indicates a directory, not a file", key)
        if len(sub) > 0: return SubDir(sub,parent=self).delete(key_,raiseOnError=raiseOnError,ext=ext)
        # don't try if directory doesn't existy
        if not self.pathExists():
            if raiseOnError:
                raise KeyError(key)
            return        
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key)
        else:
            os.remove(fullFileName)

    def deleteAllKeys( self, raiseOnError : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys in this sub directory with the correct extension.
        
        Parameters
        ----------
            key :
                filename, or list of filenames
            raiseOnError :
                if False, do not throw KeyError if file does not exist.
            ext :
                File extension to match.
                Use
                -- None for the directory default
                -- "" to match all files regardless of extension.
                -- A Format to specify the default extension for that format.
        """
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete all files: current directory not specified")
            return
        if not self.pathExists():
            return
        self.delete( self.keys(ext=ext), raiseOnError=raiseOnError, ext=ext )

    def deleteAllContent( self, deleteSelf : bool = False, raiseOnError : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys and subdirectories in this sub directory.
        Does not delete files with other extensions.
        Use eraseEverything() if the aim is to delete everything.

        Parameters
        ----------
            deleteSelf:
                whether to delete the directory or only its contents
            raiseOnError:
                False for silent failure
            ext:
                Extension for keys, or None for the directory's default.
                You can also provide a Format for 'ext'.
                Use "" to match all files regardless of extension.
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete all contents: current directory not specified")
            return
        if not self.pathExists():
            return
        # delete sub directories
        subdirs = self.subDirs();
        for subdir in subdirs:
            SubDir(subdir, parent=self).deleteAllContent( deleteSelf=True, raiseOnError=raiseOnError, ext=ext )
        # delete keys
        self.deleteAllKeys( raiseOnError=raiseOnError,ext=ext )
        # delete myself
        if not deleteSelf:
            return
        rest = list( os.scandir(self._path[:-1]) )
        txt = str(rest)
        txt = txt if len(txt) < 50 else (txt[:47] + '...')
        if len(rest) > 0:
            if raiseOnError: error( "Cannot delete my own directory %s: directory not empty: found %ld object(s): %s", self._path,len(rest), txt)
            return
        os.rmdir(self._path[:-1])   ## does not work ????
        self._path = None

    def eraseEverything( self, keepDirectory : bool = True ):
        """
        Deletes the entire sub directory will all contents
        WARNING: deletes ALL files, not just those with the present extension.
        Will keep the subdir itself by default.
        If not, it will invalidate 'self._path'

        If self is None, do nothing. That means you can call this function several times.
        """
        if self._path is None:
            return
        if not self.pathExists():
            return
        shutil.rmtree(self._path[:-1], ignore_errors=True)
        if not keepDirectory and os.path.exists(self._path[:-1]):
            os.rmdir(self._path[:-1])
            self._path = None
        elif keepDirectory and not os.path.exists(self._path[:-1]):
            os.makedirs(self._path[:-1])

    # -- file ops --

    def exists(self, key : str, *, ext : str = None ) -> bool:
        """
        Checks whether 'key' exists. Works with iterables

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            If 'key' is a string, returns True or False, else it will return a list of bools.
        """
        # vector version
        if not isinstance(key,str):
            verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.exists(k,ext=e) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return False
        # handle directories in 'key'
        if len(key) == 0: raise ValueError("'key' missing (the filename)")
        sub, key_ = os.path.split(key)
        if len(key_) == 0: raise IsADirectoryError( key, txtfmt("'key' %s indicates a directory, not a file", key) )
        if len(sub) > 0:
            return self(sub).exists(key=key_,ext=ext)
        # if directory doesn't exit
        if not self.pathExists():
            return False
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return False
        if not os.path.isfile(fullFileName):
            raise IsADirectoryError("Structural error: key %s: exists, but is not a file (full path %s)",key,fullFileName)
        return True
    
    def _getFileProperty( self, *, key : str, ext : str, func ):
        # vector version
        if not isinstance(key,str):
            verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: error("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self._getFileProperty(key=k,ext=e,func=func) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return None
        # handle directories in 'key'
        if len(key) == 0: raise ValueError("'key' missing (the filename)")
        sub, key_ = os.path.split(key)
        if len(key_) == 0: raise IsADirectoryError( key, txtfmt("'key' %s indicates a directory, not a file", key) )
        if len(sub) > 0: return self(sub)._getFileProperty(key=key_,ext=ext,func=func)
        # if directory doesn't exit
        if not self.pathExists():
            return None
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return None
        return func(fullFileName)

    def getCreationTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the creation time of 'key', or None if file was not found.
        See comments on os.path.getctime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            datetime.datetime if 'key' is a string, otherwise a list of datetime's
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getctime(x)) )

    def getLastModificationTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last modification time of 'key', or None if file was not found.
        See comments on os.path.getmtime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            datetime.datetime if 'key' is a string, otherwise a list of datetime's
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getmtime(x)) )

    def getLastAccessTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last access time of 'key', or None if file was not found.
        See comments on os.path.getatime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            datetime.datetime if 'key' is a string, otherwise a list of datetime's
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getatime(x)) )

    def getFileSize( self, key : str, *, ext : str = None ) -> int:
        """
        Returns the file size of 'key', or None if file was not found.
        See comments on os.path.getatime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            File size if 'key' is a string, otherwise a list thereof.
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : os.path.getsize(x) )

    def rename( self, source : str, target : str, *, ext : str = None ):
        """
        Rename "source" key into "target" key.
        Function will raise an exception if not successful

        Parameters
        ----------
            source, target:
                filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extensions.
                -- A Format to specify the default extension for that format.
        """
        # empty directory
        if self._path is None:
            return

        # handle directories in 'source'
        if len(source) == 0: raise ValueError("'source' missing (the filename)")
        sub, source_ = os.path.split(source)
        if len(source_) == 0: raise IsADirectoryError( source, txtfmt("'source' %s indicates a directory, not a file", source ))
        if len(sub) > 0:
            src_full = self(sub).fullKeyName(key=source_,ext=ext)
        else:
            src_full = self.fullKeyName( source, ext=ext )
            
        # handle directories in 'target'
        if len(target) == 0: raise ValueError("'target' missing (the filename)" )
        sub, target_ = os.path.split(target)
        if len(target_) == 0: raise IsADirectoryError( target, txtfmt("'target' %s indicates a directory, not a file", target))
        if len(sub) > 0:
            tar_dir  = self(sub)
            tar_dir.createDirectory()
            tar_full = tar_dir.fullKeyName(key=target_,ext=ext)
        else:
            tar_full = self.fullKeyName( target, ext=ext )
            self.createDirectory()
            
        os.rename(src_full, tar_full)

    # utilities
    
    @staticmethod
    def removeBadKeyCharacters( key:str, by:str=' ' ) -> str:
        """
        Replaces invalid characters in a filename by 'by'.
        See util.fmt_filename() for documentation and further options.
        """
        return fmt_filename( key, by=by )
   
    def unqiueLabelToKey( self, unique_label:str, id_length:int=8, separator:str='-', max_length:int=64 ) -> str:
        """
        Converts a unique label which might contain invalid characters into a unique file name, such that the full file name does not exceed 'max_length' bytes.
        The returned key has the format 
            name + separator + ID
        where ID has length id_length.
        If unique_label is already guaranteed to be a valid filename, use unqiueLongFileNameToKey() instead.
        """
        len_ext      = len(self.ext)
        assert len_ext < max_length, ("'max_length' must exceed the length of the extension", max_length, self.ext)
        uqf          = uniqueLabelExt( max_length=max_length-len_ext, id_length=id_length, separator=separator, filename_by="default" )
        return uqf( unique_label )
   
    def unqiueLongFileNameToKey( self, unique_filename:str, id_length:int=8, separator:str='-', max_length:int=64 ) -> str:
        """
        Converts a unique filename which might be too long to a unique filename such that the total length plus 'ext' does not exceed 'max_length' bytes.
        If the filename is already short enough, no change is made.

        If 'unique_filename' is not guaranteed to be a valid filename, use unqiueLabelToKey() instead.
        """
        len_ext      = len(self.ext)
        assert len_ext < max_length, ("'max_length' must exceed the length of the extension", max_length, self.ext)
        uqf          = uniqueLabelExt( max_length=max_length-len_ext, id_length=id_length, separator=separator )
        return uqf( unique_filename )
   
    # -- dict-like interface --

    def __call__(self, keyOrSub : str,
                       default = RETURN_SUB_DIRECTORY,
                       raiseOnError : bool = False,
                       *,
                       version : str = None,
                       ext : str = None,
                       fmt : Format = None,
                       delete_wrong_version : bool = True,
                       createDirectory : bool = None ):
        """
        Return either the value of a sub-key (file), or return a new sub directory.
        If only one argument is used, then this function returns a new sub directory.
        If two arguments are used, then this function returns read( keyOrSub, default ).

        sd  = SubDir("!/test")

        Member access:
            x   = sd('x', None)                      reads 'x' with default value None
            x   = sd('sd/x', default=1)              reads 'x' from sub directory 'sd' with default value 1
            x   = sd('x', default=1, ext="tmp")      reads 'x.tmp' from sub directory 'sd' with default value 1

        Create sub directory:
            sd2 = sd("subdir")                       creates and returns handle to subdirectory 'subdir'
            sd2 = sd("subdir1/subdir2")              creates and returns handle to subdirectory 'subdir1/subdir2'
            sd2 = sd("subdir1/subdir2", ext=".tmp")  creates and returns handle to subdirectory 'subdir1/subdir2' with extension "tmp"
            sd2 = sd(ext=".tmp")                     returns handle to current subdirectory with extension "tmp"

        Parameters
        ----------
            keyOrSub : str
                identify the object requested. Should be a string or a list of strings.
            default:
                If specified, this function reads 'keyOrSub' with read( keyOrSub, default, *args, **kwargs )
                If not specified, then this function calls SubDir(keyOrSub,parent=self,ext=ext,fmt=fmt)

        The following keywords are only relevant when reading files.
        They echo the parameters of read()

            raiseOnError : bool
                Whether to raise an exception if reading an existing file failed.
                By default this function fails silently and returns the default.
            version : str
                If not None, specifies the version of the current code base.
                Use '*' to read any version (this is distrinct from reading a file without version).
                If version  is not' '*', then this version will be compared to the version of the file being read.
                If they do not match, read fails (either by returning default or throwing an exception).
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.
                
        The following keywords are only relevant when accessing directories
        They echo the parameters of __init__
        
            createDirectory : bool
                Whether or not to create the directory. The default, None, is to inherit the behaviour from self.
            ext : str
                Set to None to inherit the parent's extension.
            fmt : Format
                Set to None to inherit the parent's format.
                
        Returns
        -------
            Either the value in the file, a new sub directory, or lists thereof.
            Returns None if an element was not found.
        """
        if default == SubDir.RETURN_SUB_DIRECTORY:
            if not isinstance(keyOrSub, str):
                if not isinstance(keyOrSub, Collection): 
                    raise ValueError(txtfmt("'keyOrSub' must be a string or an iterable object. Found type '%s;", type(keyOrSub)))
                return [ SubDir( k,parent=self,ext=ext,fmt=fmt,createDirectory=createDirectory) for k in keyOrSub ]
            return SubDir(keyOrSub,parent=self,ext=ext,fmt=fmt,createDirectory=createDirectory)
        return self.read( key=keyOrSub,
                          default=default,
                          raiseOnError=raiseOnError,
                          version=version,
                          delete_wrong_version=delete_wrong_version,
                          ext=ext,
                          fmt=fmt )

    def __getitem__( self, key ):
        """
        Reads self[key]
        If 'key' does not exist, throw a KeyError
        """
        return self.read( key=key, default=None, raiseOnError=True )

    def __setitem__( self, key, value):
        """ Writes 'value' to 'key' """
        self.write(key,value)

    def __delitem__(self,key):
        """ Silently delete self[key] """
        self.delete(key, False )

    def __len__(self) -> int:
        """ Return the number of files (keys) in this directory """
        return len(self.keys())

    def __iter__(self):
        """ Returns an iterator which allows traversing through all keys (files) below this directory """
        return self.keys().__iter__()

    def __contains__(self, key):
        """ Implements 'in' operator """
        return self.exists(key)

    # -- object like interface --

    def __getattr__(self, key):
        """
        Allow using member notation to get data
        This function throws an AttributeError if 'key' is not found.
        """
        if not self.exists(key):
            raise AttributeError(key)
        return self.read( key=key, raiseOnError=True )

    def __setattr__(self, key, value):
        """
        Allow using member notation to write data
        Note: keys starting with '_' are /not/ written to disk
        """
        if key[0] == '_':
            self.__dict__[key] = value
        else:
            self.write(key,value)

    def __delattr__(self, key):
        """ Silently delete a key with member notation. """
        verify( key[:1] != "_", "Deleting protected or private members disabled. Fix __delattr__ to support this")
        return self.delete( key=key, raiseOnError=False )

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
        Wraps a callable or a class into a cachable function.
        Caching is based on the following two simple principles:
            
            1) Unique Call ID:
               When a function is called with some parameters, the wrapper identifies a unique ID based
               on the qualified name of the function and on its runtime functional parameters (ie those
               which alter the outcome of the function).
               When a function is called the first time with a given unique call ID, it will store
               the result of the call to disk. If the function is called with the same call ID again,
               the result is read from disk and returned.

               To compute unique call IDs' cdxbasics.util.namedUniqueHashExt() is used.
               Please read implementation comments there:
               Key default features:
                   * It hashes objects via their __dict__ or __slot__ members.
                     This can be overwritten for a class by implementing __unique_hash__; see cdxbasics.util.namedUniqueHashExt().
                   * Function members of objects or any members starting with '_' are not considered
                     unless this behaviour is changed using CacheController().
                   * Numpy and panda frames are hashed using their byte representation.
                     That is slow and not recommended. It is better to identify numpy/panda inputs
                     via their generating characteristic ID.
                           
            2) Version:
               Each function has a version, which includes dependencies on other functions or classes.
               If the version of a result on disk does not match the current version, it is deleted
               and the function is called again. This way you can use your code to drive updates
               to data generated with cached functions.               
               Behind the scenes this is implemented using cdxbasics.version.version() which means
               that the version of a cached function can also depend on versions of non-cached functions
               or other objects.

        Functions
        ---------
        Example of caching functions:

            Cache a simple function 'f':            

                from cdxbasics.subdir import SubDir
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))
                
                @cache.cache("0.1")
                def f(x,y):
                    return x*y
                
                _ = f(1,2)    # function gets computed and the result cached
                _ = f(1,2)    # restore result from cache
                _ = f(2,2)    # different parameters: compute and store result

            Another function g which calls f, and whose version therefore on f's version:
            
                from cdxbasics.subdir import SubDir
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))

                @cache.cache("0.1", dependencies=[f])
                def g(x,y):
                    return g(x,y)**2

            A function may have non-functional parameters which do not alter the function's outcome.
            An example are 'debug' flags:
                             
                from cdxbasics.subdir import SubDir
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))

                @cache.cache("0.1", dependencies=[f], exclude_args='debug')
                def g(x,y,debug): # <-- debug is a non-functional parameter
                    if debug:
                        print(f"h(x={x},y={y})")  
                    return g(x,y)**2
                             
            You can systematically define certain types as non-functional for *all* functions wrapped
            by this SubDir by specifying the respective parameter for the CacheController() in SubDir.__init__().

            The Unique Call ID of a functions is by default generated by its fully qualified name
            and a unique hash of its functional parameters.            
            This can be made more readable by using id=

                from cdxbasics.subdir import SubDir
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))
                
                @cache.cache("0.1", id="f({x},{y}") # <- using a string to be passed to str.format()
                def f(x,y):
                    return x*y

            You can also use functions:
    
                from cdxbasics.subdir import SubDir
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))
                
                # Using a function 'id'. Note the **_ to catch uninteresting parameters, here 'debug'
                @cache.cache("0.1", id=lambda x,y,**_: f"h({x},{y})", exclude_args='debug') 
                def h(x,y,debug=False):
                    if debug:
                        print(f"h(x={x},y={y})")  
                    return x*y

            Note that by default it is not assumed that the call Id returned by id is unique,
            and a hash generated from all pertinent arguments will be generated.
            That is why in the previous example we still need to exclude_args 'debug' here.

            If the id you generate is guaranteed to be unique for all functional parameter values,
            you can add unique=True. In this case the filename of the function 

                from cdxbasics.subdir import SubDir
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))
                
                # Using a function 'id' with 'unique' to generate a unique ID.
                @cache.cache("0.1", id=lambda x,y,**_: f"h({x},{y})", unique=True) 
                def h(x,y,debug=False):
                    if debug:
                        print(f"h(x={x},y={y})")  
                    return x*y
            
        Numpy/Panda
        -----------
        Numpy/Panda data should not be hashed for identifying unique call IDs.
        Instead, use the defining characteristics for generating the data frames.
        
        For example:
            
            from cdxbasics.subdir import SubDir
            cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))

            from cdxbasics.prettydict import pdct
            
            @cache.cache("0.1")
            def load_src( src_def ):
                result = ... load ...
                return result

            # ignore 'src_result'. It is uniquely identified by 'src_def' -->
            @cache.cache("0.1", dependencies=[load_src], exclude_args=['data'])  
            def statistics( stats_def, src_def, data ):
                stats = ... using data
                return stats
            
            src_def = pdct()
            src_def.start = "2010-01-01"
            src_def.end = "2025-01-01"
            src_def.x = 0.1

            stats_def = pdct()
            stats_def.lambda = 0.1
            stats_def.window = 100

            data  = load_src( src_def )
            stats = statistics( stats_def, src_def, data )

        While instructive, this case is not optimal: we do not really need to load 'data'
        if we can reconstruct 'stats' from 'data' (unless we need 'data' further on).
        
        Consider therefore

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

        Member functions
        ----------------
        You can cache member functions like any other function.
        Note that version information are by default inherited, i.e. member functions will be dependent on the version of their 
        defining class, and class versions will be dependent on their base classes' versions.
            
            from cdxbasics.subdir import SubDir, version
            cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))
            
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
        The hashing function used -- cdxbasics.util.uniqueHashExt() -- does by default *not* process members of objects or dictionaries
        which start with a "_". This behaviour can be changed using CacheController().
        For reasonably complex objects it is recommended to implement:
            __unique_hash__( self, length : int, parse_functions : bool, parse_underscore : str )
        (it is also possible to simply set this value to a string constant).

        Bound Member Functions
        ----------------------
        Note that above is functionally different to decorating a bound member function:
            
            from cdxbasics.subdir import SubDir, version
            cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))

            class A(object):
                def __init__(self,x):
                    self.x = x
                def f(self,y):
                    return self.x*y
            
            a = A(x=1)
            f = cache.cache("0.1", id=lambda self, y : f"a.f({y})")(a.f)  # <- decorate bound 'f'.
            r = c(y=2)

        In this case the function 'f' is bound to 'a'. The object is added as 'self' to the function
        parameter list even though the bound function parameter list does not include 'self'.
        This, together with the comments on hashing objects above, ensures that (hashed) changes to 'a' will
        be reflected in the unique call ID for the member function.

        Classes
        -------
        Classes can also be cached.
        This is done in two steps: first, the class itself is decorated to provide version information at its own level.
        Secondly, decorate __init__ which also helps to define the unique call id. You do not need to specify a version
        for __init__ as its version usually coincides with the version of the class.

            Simple example:            
        
                cache   = SubDir("!/.cache", cacheController : CacheController(debug_verbose=Context("all")))
                
                @cache.cache("0.1")
                class A(object):
                    
                    @cache.cache(exclude_args=['debug'])
                    def __init__(self, x, debug):
                        if debug:
                            print("__init__",x)
                        self.x = x

            __init__ does not actually return a value; for this reason the actual function decorated will be __new__.
            Attempting to cache decorate __new__ will lead to an exception.

            A nuance for __init__ vs ordinary member function is that 'self' is non-functional.
            It is therefore automatically excluded from computing a unique call ID.
            Specifically, 'self' is not part of the arguments passed to 'id':
            
                @cache.cache("0.1")
                class A(object):
                    
                    @cache.cache("0.1", id=lambda x, debug: f"A.__init__(x={x})")  # <-- 'self' is not passed to the lambda function; no need to add **_
                    def __init__(self, x, debug):
                        if debug:
                            print("__init__",x)
                        self.x = x

            Decorating classes with __slots__ does not yet work.
                                    
        Non-functional parameters
        -------------------------
        Often functions have parameters which do not alter the output of the function but control i/o or other aspects of the overall environment.
        An example is a function parameter 'debug':
        
            def f(x,y,debug=False):
                z = x*y
                if not debug:
                    print(f"x={x}, y={y}, z={z}")
                return z

        To specify which parameters are pertinent for identiying a unique id, use:
            
            a) include_args: list of functions arguments to include. If None, use all as input in the next step
            b) exclude_args: list of funciton arguments to exclude, if not None.
            c) exclude_arg_types: a list of types to exclude. This is helpful if control flow is managed with dedicated data types.
               An example of such a type is cdxbasics.verbose.Context which is used to print hierarchical output messages.
               Types can be globally excluded using the CacheController.
                
        See also
        --------                
        For project-wide use it is usually inconvenient to control caching at the level of a 'directory'.
        See VersionedCacheRoot() is a thin wrapper around a SubDir with a CacheController.
        
        Parameters
        ----------
        version : str, optional
            Version of the function.
            * If None then F must be decorated with cdxbasics.version.version().
            * If set, the function F is first decorated with cdxbasics.version.version().
        dependencies : list, optional
            List of version dependencies
        
        id : str, Callable
            Create a call label for the function call and its parameters.
            See above for a description.
            * A plain string without {} formatting: this is the fully qualified id
            * A string with {} formatting: id.str( name=name, **parameters ) will be used to generate the fully qualified id
            * A Callable, in which case id( name=name, **parameters ) will be used to generate the fully qualified id
        
        unique : bool
            Whether the 'id' generated by 'id' is unique for this function call with its parameters.
            If True, then the function will attempt to use 'id' as filename as long as it has no invalid characters and is short
            enough (see 'max_filename_length').
            If False, the function will append to the 'id' a unique hash of the qualified function name and all pertinent parameters
        
        name : str
            The name of the function, or None for using the fully qualified function name.
            
        include_args : list[str]
            List of arguments to include in generating a unqiue id, or None for all.
        
        exclude_args : list[str]:
            List of argumernts to exclude
            
        exclude_arg_types : list[type]
            List of types to exclude.
            
        version_auto_class : bool
        

            
        Returns
        -------
            A callable to execute F if need be.
            This callable has a member 'cache_info' which can be used to access information on caching activity.

                Information available at any time after decoration:
                    F.cache_info.name : qualified name of the function
                    F.cache_info.signature : signature of the function
            
                Additonal information available during a call to a decorated function F, and thereafter:                    
                    F.cache_info.version : unique version string reflecting all dependencies.
                    F.cache_info.uid : unique call ID. 
                    F.cache_info.label : last id generated, or None (if id was a string and unique was True)
                    F.cache_info.arguments : arguments parsed to create a unique call ID, or None (if id was a string and unique was True)

                Additonal information available after a call to F:
                    F.cache_info.last_cached : whether the last function call returned a cached object
                
            The function F has additional function parameters
                override_cache_mode : allows to override caching mode temporarily, in particular "off"
                track_cached_files : pass a CacheTracker object to keep track of all files used (loaded from or saved to).
                      This can be used to delete intermediary files when a large operation was completed.
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
        Short cut for SubDir.cache() for classes
        See  SubDir.cache() for documentation.
        """
        return self.cache( name=name,
                      version=version,
                      dependencies=dependencies,
                      version_auto_class=version_auto_class)        
                      

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
    Utility class for SubDir.cache_callable.
    See documentation for that function.
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
        Utility class for SubDir.cache_callable.
        See documentation for that function.
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
        return self._uid if self._label is None else self._label
    @property
    def unique(self) -> bool:
        return not self._uid is None
        
    @property
    def cacheController(self) -> CacheController:
        """ Returns the cache controller """
        return self._subdir.cacheController
    @property
    def cache_mode(self) -> Context:
        return self.cacheController.cache_mode
    @property
    def debug_verbose(self) -> Context:
        return self.cacheController.debug_verbose
    @property
    def uniqueNamedFileName(self) -> Callable:
        return self.cacheController.uniqueNamedFileName
    @property
    def uniqueLabelledFileName(self) -> Callable:
        return self.cacheController.uniqueLabelledFileName
    @property
    def global_exclude_arg_types(self) -> list[type]:
        return self.cacheController.exclude_arg_types
    
    def __call__(self, F : Callable):
        """
        Decorate 'F' as cachable callable. Can also decorate classes via ClassCallable()
        See SubDir.cache() for documentation.
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
            1) Assigns a cdxbasics.version.version() for the class (if not yet present)
            2) Extracts from __init__ the wrapper to decorate __new__
        """
        debug_verbose = self.cacheController.debug_verbose

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
    
        debug_verbose = self.cacheController.debug_verbose
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
            
            label        = None
            uid          = None 
            uid_or_label = self.uid_or_label
            if isinstance(uid_or_label, str) and self.unique:
                # if 'id' does not contain formatting codes, and the result is 'unique' then do not bother collecting
                # function arguments
                try:
                    uid = uid_or_label.format()   # throws a KeyError if 'id' contains formatting information
                except KeyError:
                    pass

            if not uid is None:
                # generate name with the unique string provided by the user
                label     = uid
                uid       = self.uniqueLabelledFileName( self.id )
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
                                
                # apply logics                
                if uid_or_label is None:
                    label = name
                    
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
                            label = str.format( uid_or_label, **arguments )
                        except KeyError as e:
                            raise KeyError(e, f"Error while generating id for '{name}' using format string '{uid_or_label}': {e}. Available arguments: {list(arguments)}")

                    else:
                        which = 'uid' if not self._uid is None else 'label'
                        try:
                            label = uid_or_label(**arguments)
                        except TypeError as e:
                            raise TypeError(e, f"Error while generating '{which}' for '{name}' using a function: {e}. Available arguments: {list(arguments)}")
                        except Exception as e:
                            raise type(e)(f"Error while generating '{which}' for '{name}': attempt to call '{which}' of type {type(uid_or_label)} failed: {e}")
                        assert isinstance(label, str), ("Error:", which,"callable must return a string. Found",type(label))

                if self.unique:
                    uid = self.uniqueLabelledFileName( label )
                else:
                    uid = self.uniqueNamedFileName( label, **arguments )

            # determine version, cache mode
            # ------------------

            version_   = self._version if not self._version is None else F.version.unique_id64
            cache_mode = CacheMode(override_cache_mode) if not override_cache_mode is None else self.cache_mode
            del override_cache_mode

            # store process information
            # -------------------------

            execute.cache_info.label   = str(label) if not label is None else None
            execute.cache_info.uid     = uid
            execute.cache_info.version = version_
            
            if self.cacheController.keep_last_arguments:
                info_arguments = OrderedDict()
                for argname, argvalue in arguments.items():
                    info_arguments[argname] = str(argvalue)[:100]
                execute.cache_info.arguments = info_arguments
                del argname, argvalue
            
            # execute caching
            # ---------------

            if cache_mode.delete:
                self._subdir.delete( uid )
            elif cache_mode.read:
                class Tag:
                    pass
                tag = Tag()
                if not is_new:
                    r = self._subdir.read( uid, tag, version=version_ )
                else:
                    try:
                        execute.__new_during_read = True
                        r = self._subdir.read( uid, tag, version=version_ )
                    finally:
                        execute.__new_during_read = False
                        
                if not r is tag:
                    if not track_cached_files is None:
                        track_cached_files += self._fullFileName(uid)
                    execute.cache_info.last_cached = True 
                    if not debug_verbose is None:
                        debug_verbose.write(f"cache({name}): read '{label}' version 'version {version_}' from cache '{self._subdir.fullFileName(uid)}'.")
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
                self._subdir.write(uid,r,version=version_)      
                if not track_cached_files is None:
                    track_cached_files += self._subdir.fullFileName(uid)
            execute.cache_info.last_cached = False

            if is_new:
                assert r.__magic_cache_call_init__ is None, ("**** Internal error. __init__ should reset __magic_cache_call_init__")
                r.__magic_cache_call_init__ = False # since we called __new__, __init__ will be called next
                #debug_verbose.write(f"cache({name}): called __init__ after __new__ with: {args[1:]} / {kwargs}")
            
            if not debug_verbose is None:
                if cache_mode.write:
                    debug_verbose.write(f"cache({name}): called '{label}' version 'version {version_}' and wrote result into '{self._subdir.fullFileName(uid)}'.")
                else:
                    debug_verbose.write(f"cache({name}): called '{label}' version 'version {version_}' but did *not* write into '{self._subdir.fullFileName(uid)}'.")
            return r

        update_wrapper( wrapper=execute, wrapped=F )
        execute.cache_info = CacheInfo()
        
        execute.cache_info.name = name                       # decoded name of the function
        execute.cache_info.signature = inspect.signature(F)  # signature of the function

        execute.cache_info.uid = None           # last function call ID
        execute.cache_info.label = None    # last unique file name cached to
        execute.cache_info.version = None      # last version used

        execute.cache_info.last_cached = None       # last function call restored from disk?

        if self.cacheController.keep_last_arguments:
            execute.cache_info.arguments = None    # last function call arguments dictionary of strings
            
        if is_new:
            execute.__new_during_read = False
        
        if not debug_verbose is None:
            debug_verbose.write(f"cache({name}): {'function' if not is_new else 'class constructor function'} registered for caching into '{self._subdir.path}'.")
        self.cacheController.versioned[name] = execute
        return execute          

def VersionedCacheRoot( directory          : str, *,
                        ext                : str = None, 
                        fmt                : Format = None,
                        createDirectory    : bool = None,
                        **controller_kwargs
                        ):
    """
    Create a root directory for versioning caching on disk
    
    Usage:
        In a central file, define a root directory                
            vroot = VersionedCacheRoot("!/cache")

        and a sub-directory
            vtest = vroot("test")
            
        @vtest.cache("1.0")
        def f1( x=1, y=2 ):
            print(x,y)
            
        @vtest.cache("1.0", dps=[f1])
        def f2( x=1, y=2, z=3 ):
            f1( x,y )
            print(z)
    
    Parameters
    ----------
        directory : name of the directory. Using SubDir the following short cuts are supported:
                        "!/dir" creates 'dir' in the temporary directory
                        "~/dir" creates 'dir' in the home directory
                        "./dir" created 'dir' relative to the current directory
        ext : extension, which will automatically be appended to file names (see SubDir). Default depends on format. For Format.PICKLE it is 'pck'
        fmt : format, see SubDir.Format. Default is Format.PICKLE
        createDirectory : whether to create the directory upon creation. Default is no.
        controller_kwargs: parameters passed to VersionController, for example:
            exclude_arg_types : list of types or names of types to exclude when auto-generating function signatures from function arguments.
                             A standard example from cdxbasics is "Context" as it is used to print progress messages.
            max_filename_length : maximum filename length
            hash_length: length used for hashes, see cdxbasics.util.uniqueHash() 
        
    Returns
    -------
        A root cache directory
    """    
    controller = CacheController(**controller_kwargs) if len(controller_kwargs) > 0 else None
    return SubDir( directory=directory, ext=ext, fmt=fmt, createDirectory=createDirectory, controller=controller )

version = version_decorator
                
    