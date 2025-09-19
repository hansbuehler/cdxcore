r"""
Overview
--------

Fast binary disk i/o for numpy.
Usage is fairly straight forward



Illustation
^^^^^^^^^^^


Import
------

.. code-block:: python

    from cdxcore.deferred import Deferred

Documentation
-------------
"""
from .util import fmt_digits, fmt as txtfmt, fmt_list
from .err import verify, error, warn, warn_if
import numpy as np
from collections.abc import Callable
from numba import njit
import warnings as warnings

LINUX_MAX_FILE_BLOCK = 0x7ffff000 
"""
The `maximum block size <https://www.man7.org/linux/man-pages/man2/write.2.html#NOTES>`__ in 64 and 32 bit linux.
"""

DTYPE_TO_CODE = {
        "bool"       : np.int8(0),
        "int8"       : np.int8(1),
        "int16"      : np.int8(2),
        "int32"      : np.int8(3),
        "int64"      : np.int8(4),
        "uint16"     : np.int8(5),
        "uint32"     : np.int8(6),
        "uint64"     : np.int8(7),
        "float16"    : np.int8(8),
        "float32"    : np.int8(9),
        "float64"    : np.int8(10),
        "complex64"  : np.int8(11),
        "complex128" : np.int8(12),
        "datetime64" : np.int8(13),
        "timedelta64": np.int8(14)
    }
"""
Maps numpy dtype names to a numerical ID in int8
"""

CODE_TO_DTYPE = { v:k for k,v in DTYPE_TO_CODE.items() }
"""
Maps a numerical ID to numpy dtype names
"""

# ===============================================
# Write
# ===========0====================================

def _write_int(f : int, x : int, lbytes : int):
    """ Write an integer ``x`` of at most ``lbytes`` to a file ``f`` """
    x = int(x).to_bytes(lbytes,"big")
    w = f.write( x )
    if w != len(x):
        raise IOError(f"could only write {w} bytes, not {len(x)}.")

def _tofile(f : int, array : np.ndarray, DTYPE_TO_CODE : dict ):
    """
    Write a numpy array ``array`` including its associated
    shape and dtype to a file ``f``.
    """
    array    = np.asarray( array )
    dtypec   = DTYPE_TO_CODE.get( str(array.dtype), None )
    verify( not dtypec is None, lambda : f"Cannot handle dtype '{str(array.dtype)}'. Supported dtypes are: {fmt_list(DTYPE_TO_CODE)}.", exception=ValueError ) 
    dtypec   = np.int8(dtypec)
    length   = np.int64( np.prod( array.shape, dtype=np.uint64 ) )
    shape32  = tuple( [np.int32(i) for i in array.shape])
    array    = np.reshape( array, (length,) )  # this operation should not reallocate any memory
    dsize    = int(array.itemsize)   
    max_size = int(LINUX_MAX_FILE_BLOCK//dsize)
    num      = int(length-1)//max_size+1        
    saved    = 0

    # write shape
    verify( len(shape32) < 0x7fff, lambda : f"Cannot write numpy array with shape {array.shape}: maximum number of dimensions is {fmt_digits(0x7fff)}", exception=ValueError )   
    _write_int( f, len(shape32), 2 )  # max 32k dimension
    for i in shape32:
        verify( i < 0x7fffffff, lambda : f"Cannot write numpy array with shape {array.shape}: maximum dimensions is {fmt_digits(0x7fffffff)}", exception=ValueError )
        _write_int(f, i, 4) # max 32 bit resolution
    # write dtype
    _write_int(f, dtypec, 1)
    # write object      
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        bts = array.data[s:e]
        nw  = f.write( bts )
        if nw != (e-s)*dsize:
            raise IOError( f"wrote only {fmt_digits(nw)} bytes of a block of {fmt_digits((e-s)*dsize)} bytes.")
        saved += nw
    if saved != length*dsize:
        raise IOError( f"wrote only {fmt_digits(saved) } bytes of a block of  {fmt_digits(length*dsize)} bytes")

def tofile( file         : str|int,
            array        : np.ndarray, *,
            buffering    : int = -1
            ):
    """
    Write a numpy arrray into a file using binary format.
    
    This function will work for unbuffered files exceeding 2GB which is the usual unbuffered :func:`write` `limitation on Linux <https://www.man7.org/linux/man-pages/man2/write.2.html#NOTES>`__.
    This function will only work with the dtypes contained in :data:`cdxcore.npio.DTYPE_TO_CODE`.
    
    Parameters
    ----------
        file : str | int
            Filename or an open file handle from :func:`open`.
            
        array : :class:`numpy.ndarray`
            The array. Objects of type :class:`cdxcore.sharedarray.ndsharedarray` are identified as :class:`numpy.ndarray` arrays.
            
        buffering : int, default ``-1``
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.
            
    Raises
    ------
        I/O error : :class:`IOError`
            In case the function failed to write the whole file.
        Value error : :class:`ValueError`
            In case an array is passed whose dtype is not contained in :data:`cdxcore.npio.DTYPE_TO_CODE`,
            which has more than 32k dimensions, or which has an indivudual dimension longer than 2bn lines.        
    """
    if isinstance(file, str):
        with open( file, "wb", buffering=buffering ) as f:
            return tofile(f, array, buffering=buffering)
    f = file
    del file
    
    if not array.data.contiguous:
        warn("Array is not 'contiguous'. Is that an issue??")
        array = np.ascontiguousarray( array, dtype=array.dtype ) if not array.data.contiguous else array
        
    try:
        _tofile(f, array=array, DTYPE_TO_CODE=DTYPE_TO_CODE )
    except IOError as e:
        raise IOError(f"Could not write all {fmt_digits(array.nbytes)} bytes to {f.name}: {str(e)}", e) from e

# ===============================================
# Read
# ===============================================

def _read_int(f : int, lbytes : int) -> int:
    """ Read and int from file ``f`` of size ``lbytes`` """
    x = f.read(lbytes)
    if len(x) != lbytes:
        raise EOFError(f"could only read {len(x)} bytes not {lbytes}.")
    x = int.from_bytes(x,"big")
    return int(x)

def _readfromfile( f : int, array : np.ndarray ):
    # split into chunks
    shape    = array.shape
    length   = int( np.prod( array.shape, dtype=np.uint64 ) )
    array    = np.reshape( array, (length,) )
    dsize    = int(array.itemsize)
    max_size = int(LINUX_MAX_FILE_BLOCK//dsize)
    num      = int(length-1)//max_size+1
    read     = 0
    # read        
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        nr  = f.readinto( array.data[s:e] )
        if nr != (e-s)*dsize:
            raise EOFError(f"could only read {fmt_digits(nr)} of a block of {fmt_digits((e-s)*dsize)} bytes.")
        read += nr
    if read != length*dsize:
        raise EOFError(f"could only read {fmt_digits(read)} of a block of  {fmt_digits(length*dsize)} bytes.")
    return np.reshape( array, shape )  # no copy

def _readheader(f : int):
    """
    Read shape, dtype
    """
    shape_len  = _read_int(f,2)
    shape      = tuple( [ int(_read_int(f,4)) for _ in range(shape_len) ] )
    dtype      = CODE_TO_DTYPE[_read_int(f,1)]
    return shape, dtype

def readfromfile( file           : str|int, 
                  target         : np.ndarray|Callable, *, 
                  read_only      : bool = False,
                  buffering      : int  = -1,
                  validate_dtype : type = None,
                  validate_shape : tuple = None
                  ) -> np.ndarray:
    """
    Read a :class:`numpy.ndarray` from disk into an existing array or into a new array.
    
    See :func:`cdxcore.npio.readinto` and :func:`cdxcore.npio.fromfile` for more convenient interfaces
    for each use case.
    
    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        target : np.ndarray | Callable
            Either an :class:`numpy.ndarray` to write into, or a function which returns allocates an array for a given shape and dtype.
            It must have the signature::
                
                def create( shape : tuple, dtype : type ):
                    return np.empty( shape, dtype )
                
        read_only : bool, optional
            Whether to clear the ``writable`` `flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flags.html>`__ of the array
            after reading it from disk.
            
        buffering : int, optional
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.

        validate_dtype: dtype | ``None``, optional
            If not ``None``, check that the returned array has the specified dtype.
            
        validate_shape: tuple | ``None``, optional
            If not ``None``, check that the array has the specified shape.
        
    Returns
    -------
        Array : :class:`numpy.ndarray`
            The array
            
    Raises
    ------
        EOF : :class:`EOFError`
            In case the function failed to read the whole file.
        I/O error : :class:`IOError`
            In case the function failed to match the desired ``validate_dtype`` or ``validate_shape``,
            or if it does not match the geometry of ``target`` if provided as a numpy array.
    """
    if isinstance(file, str):
        with open( file, "rb", buffering=buffering ) as f:
            return readfromfile( f, target, 
                                 read_only=read_only,
                                 buffering=buffering,
                                 validate_dtype=validate_dtype,
                                 validate_shape=validate_shape )
    f = file
    del file
        
    # read shape
    shape, dtype = _readheader(f)

    if not validate_dtype is None and validate_dtype != dtype:
        raise IOError(f"Failed to read {f.name}: found type {dtype} expected {validate_dtype}.")
    if not validate_shape is None and validate_shape != shape:
        raise IOError(f"Failed to read {f.name}: found type {shape} expected {validate_shape}.")

    # handle array
    if isinstance(target, np.ndarray):
        if target.shape != shape or target.dtype.base != dtype:
            raise IOError(f"File {f.name} read error: expected shape {target.shape}/{str(target.dtype)} but found {shape}/{str(dtype)}.")
        array = target
        
    else:
        array = target( shape=shape, dtype=dtype ) 
        assert not array is None, ("'target' function returned None")
        assert array.shape == shape and array.dtype == dtype, ("'target' function returned wrong array; shape:", array.shape, shape, "; dtype:", array.dtype, dtype)
    del target

    try:
        _readfromfile(f, array)
    except EOFError as e:
        raise EOFError(f"Cannot read from {f.name}: {str(e)}", e)
    if read_only:
        array.flags.writeable  = False

    assert array.flags.writeable == (not read_only), ("Internal flag error", array.flags.writeable, read_only, not read_only )
    return array

def read_shape_and_dtype( file : str|int, buffering : int = -1 ) -> tuple:
    """
    Read shape and dtype from a numpy binary file.
    
    Parameters
    ----------
        file : str | int
            file name passed to open(), or a file handle from open()

        buffering : int, optional
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.
        
    Returns
    -------
        shape, dtype : tuple, type
            Shape and dtype.

    Raises
    ------
        EOF : :class:`EOFError`
            In case the function failed to read the whole file.
    """

    if isinstance(file, str):
        with open( file, "rb", buffering=buffering ) as f:
            return read_shape_and_dtype( f, buffering=buffering )
    return _readheader(file)

def readinto( file, array : np.ndarray, *, read_only : bool = False, buffering : int = -1 ):
    """
    Read an array from disk into an existing :class:`numpy.ndarray`.    
    
    The receiving array must have the same shape and dtype as the array on disk. 

    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        target : np.ndarray
            Target array to write into. This array must have the same shape and dtype as the source data.
                
        read_only : bool, optional
            Whether to clear the ``writable`` `flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flags.html>`__ of the array
            after reading it from disk.
            
        buffering : int, optional
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.
        
    Returns
    -------
        Array : :class:`numpy.ndarray`
            Returns ``target`` with the data read from disk.
            
    Raises
    ------
        EOF : :class:`EOFError`
            In case the function failed to read the whole file.
        I/O error : :class:`IOError`
            In case the function failed to match the desired ``validate_dtype`` or ``validate_shape``,
            or if it does not match the geometry of ``target`` if provided as a numpy array.
    """
    return readfromfile( file, target = array, read_only=read_only, buffering=buffering )

def fromfile( file, *, validate_dtype = None, validate_shape = None, read_only : bool = False, buffering : int = -1  ) -> np.ndarray:
    """
    Read array from disk into a new :class:`numpy.ndarray`.
    
    Use :func:`cdxcore.sharedarray.shared_fromfile` to create a shared array 
    instead.

    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        validate_dtype: dtype | ``None``, optional
            If not ``None``, check that the returned array has the specified dtype.
            
        validate_shape: tuple | ``None``, optional
            If not ``None``, check that the array has the specified shape.

        read_only : bool, optional
            Whether to clear the ``writable`` `flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flags.html>`__ of the array
            after reading it from disk.
            
        buffering : int, optional
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.

    Returns
    -------
        Array : :class:`numpy.ndarray`
            Returns newly created numpy array.
            
    Raises
    ------
        EOF : :class:`EOFError`
            In case the function failed to read the whole file.
        I/O error : :class:`IOError`
            In case the function failed to match the desired ``validate_dtype`` or ``validate_shape``,
            or if it does not match the geometry of ``target`` if provided as a numpy array.
    """
    return readfromfile( file,
                         target=lambda shape, dtype : np.empty( shape=shape, dtype=dtype ),
                         read_only = read_only, 
                         validate_dtype=validate_dtype, 
                         validate_shape=validate_shape,
                         buffering=buffering )
        


