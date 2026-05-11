r"""
Fast binary disk i/o for numpy arrays.

.. code-block:: python

    from cdxcore.npio import to_file, from_file, read_into
    from cdxcore.subdir import SubSir
    import numpy as np
    
    array = (np.random.normal(size=(1000,3))*100.).astype(np.int32)
    file  = SubDir("!/test", create_directory=True).full_file_name("test")
    
    to_file( file, array )    # write
    test = from_file( file )  # read back
    read_into( file, test )   # read into an existing array

When reading :func:`cdxcore.npio.from_file` you can automatically validate the shape and dtype of
the data being read::
    
    test = from_file( file, validate_dtype=np.int32, validate_shape=(1000,3) )
    
**Continguous Arrays**

By default functions in this module assume that data is laid out linearly in memory, also called "C-contiguous".
This allows writing a continuous block of data to disk, or reading it back. If an array is not "contiguous"
by default, an exception will be raised unless an intermediary copy buffer size is set with ``cont_block_size_mb``::

    array = np.zeros((4,4), dtype=np.int8)
    x = array[:,1]
    assert not x.data.contiguous  # not contiguous
    to_file( file, x, cont_block_size_mb=100 )

**Shared Memory**

The binary format is compatible with :func:`cdxcore.npshm.read_shared_array` which reads
a binary array into shared memory.

Import
------

.. code-block:: python

    from cdxcore.npio import to_file, from_file, intofile

Documentation
-------------
"""
from .util import fmt_digits, fmt_list
from .err import verify
import numpy as np
from collections.abc import Callable

LINUX_MAX_FILE_BLOCK = 0x7ffff000 
"""
The `maximum block size <https://www.man7.org/linux/man-pages/man2/write.2.html#NOTES>`__ in 64 and 32 bit linux.
"""

_DTYPE_TO_CODE = {
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

_CODE_TO_DTYPE = { v:getattr(np, k) for k,v in _DTYPE_TO_CODE.items() }
"""
Maps a numerical ID to numpy dtype names
"""

# ===============================================
# Header
# ===============================================

def _create_header( shape : tuple, dtype : type ):
    """
    Binary header:
        Bytes
            [0:4]          : total byte length of the current block
            [4]            : dtype code for _DTYPE_TO_CODE
            [5:8]          : length of the shape tuple
            [8+i*8:16+i*8] : the actual tuple values
    """
 
    # get type code (byte)
    total    = 4+1+3+len(shape)*8
    verify( total < 0x100*4, lambda : f"Cannot handle numpy array with shape {shape}: total header information has length {total} and exceeds {fmt_digits(0x100**4)}.", exception=ValueError )   
    header   = int(total).to_bytes(4,"big",signed=False)  # write long total size

    #print("_create_header", shape, dtype, total )

    dtype    = np.dtype(dtype)
    dtypec   = _DTYPE_TO_CODE.get( str(dtype), None )
    verify( not dtypec is None, lambda : f"Cannot handle dtype '{str(dtype)}'. Supported dtypes are: {fmt_list(_DTYPE_TO_CODE)}.", exception=ValueError ) 
    dtypec   = np.int8(dtypec)
    header   += int(dtypec).to_bytes(1,"big",signed=False)  # write a word anyway
    
    # get shape size (3 bytes)
    verify( len(shape) < 0x100**3, lambda : f"Cannot handle numpy array with shape {shape}: dimension cannot exceed {fmt_digits(0x100**3)}", exception=ValueError )   
    header   += int(len(shape)).to_bytes(3,"big",signed=False)
    
    # get shapes (wlong)
    for dim in shape:
        header += int(dim).to_bytes(8,"big",signed=False)

    assert len(header) == total, ("Internal consistency error", len(header), total )
    return header

def _decode_header( buffer : bytes|memoryview, align : int = None ):
    """
    Binary header:
        Bytes
            [0:4]          : total byte length of the current block
            [4]            : dtype code for _DTYPE_TO_CODE
            [5:8]          : length of the shape tuple
            [8+i*8:16+i*8] : the actual tuple values
            
    This function returns dtype, shape, body from the binary 'buffer'
    input. If the data is not padded, then body starts at the first byte
    past the header; if the data is padded to 'align' (eg 64 bytes for optimal cache behaviour),
    then the corresponding rounding will be applied.
    """
    # total size
    total = int.from_bytes( buffer[0:4], "big", signed=False )
    verify( total <= len(buffer), lambda : f"Internal file header consistency error: header length is given as {fmt_digits(total)} but byte stream only has {fmt_digits(len(buffer))} bytes.", exception=ValueError )   
    header = buffer[4:]
    
    # dtype
    dtypec = int.from_bytes( header[:1], "big", signed=False )
    dtype  = _CODE_TO_DTYPE.get( dtypec, None )
    verify( not dtype is None, lambda : f"Internal file header consistency error: unknown dtype code '{dtypec}'.", exception=ValueError )   
    dtype  = np.dtype(dtype)

    # shape
    len_shape = int.from_bytes( header[1:4], "big", signed=False )
    verify( total == 4+1+3+len_shape*8, lambda : f"Internal file header consistency error: total header size reported {fmt_digits(total)} does not match a shape of length {len_shape}.", exception=ValueError )   
    header    = header[4:]
    shape     = []
    for i in range(len_shape):
        shape.append( int.from_bytes( header[:8], "big", signed=False ) )
        header = header[8:]
    shape     = tuple(shape)
    #print("_decode_header", shape, dtype, total )

    if align is None:
        body = header
    else:
        align = int(max( align,  dtype.alignment ))
        body  = buffer[ ((total + align - 1)//align  ) * align: ]
    return dtype, shape, body

# ===============================================
# Write
# ===============================================

def _tofile(f : int, array : np.ndarray, cont_block_size_mb : int ):
    """
    Write a numpy array ``array`` including its associated
    shape and dtype to a file ``f``.
    """
    # prepare shape
    header   = _create_header(array.shape, array.dtype) 
    nw       = f.write( header )
    if nw != len(header):
        raise IOError( f"wrote only {fmt_digits(nw)} bytes of a block of {fmt_digits(len(header))} bytes.")
    del header
    
    # prepare array
    array    = np.asarray( array )
    length   = np.int64( np.prod( array.shape, dtype=np.uint64 ) )
    array    = np.reshape( array, (length,) )  # this operation should not reallocate any memory
    dsize    = int(array.itemsize)   
    max_size = int(LINUX_MAX_FILE_BLOCK//dsize)

    if not array.flags.c_contiguous:
        verify( not cont_block_size_mb is None, "Array is not c_contiguous. Use 'cont_block_size_mb' to auto-transform into contiguous chunks of memory.")
        verify( cont_block_size_mb > 0, "'cont_block_size_mb' must be positive.")
        max_size = min( max_size, max(1,cont_block_size_mb*1024*1024//dsize) )
        buffer   = np.empty( (max_size,), dtype=array.dtype )
    else:
        buffer   = None
    num      = int(length-1)//max_size+1        
    saved    = 0

    # write array
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        if array.flags.c_contiguous:
            nw  = f.write( array.data[s:e] )
        else:
            buffer[:e-s] = array[s:e]
            nw  = f.write( buffer.data[:e-s] )
        if nw != (e-s)*dsize:
            raise IOError( f"wrote only {fmt_digits(nw)} bytes of a block of {fmt_digits((e-s)*dsize)} bytes.")
        saved += nw
    if saved != length*dsize:
        raise IOError( f"wrote only {fmt_digits(saved) } bytes of a block of {fmt_digits(length*dsize)} bytes")

def to_file(file               : str|int,
            array              : np.ndarray, *,
            buffering          : int = -1,
            cont_block_size_mb : int|None = None
            ):
    """
    Write a numpy arrray into a file using binary format.
    
    This function will work for unbuffered files exceeding 2GB which is the usual unbuffered :func:`write` `limitation on Linux <https://www.man7.org/linux/man-pages/man2/write.2.html#NOTES>`__.
    This function will only work with the dtypes contained in :data:`cdxcore.npio._DTYPE_TO_CODE`.
    
    By default this function does not write non-contiguous arrays (those not laid out linearly in memory). Use ``cont_block_size_mb``
    to enable an intermediary buffer to do so.

    **Shared Memory**
    
    Use :func:`cdxcore.npshm.read_shared_array` to read numpy arrays stored to disk
    with ``to_file`` into shared memory.
    
    Parameters
    ----------
        file : str | int
            Filename or an open file handle from :func:`open`.
            
        array : :class:`numpy.ndarray`
            The array. Objects of type :class:`cdxcore.sharedarray.ndsharedarray` are identified as :class:`numpy.ndarray` arrays.
            
        buffering : int, default ``-1``
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.
            
        cont_block_size_mb : int | None, default ``None``
            By default this function does not write non-contiguous arrays (those not laid out linearly in memory).
            Use ``cont_block_size_mb``
            to enable an intermediary buffer of size ``cont_block_size_mb`` to do so.
            
    Raises
    ------
        I/O error : :class:`IOError`
            In case the function failed to write the whole file.
        Value error : :class:`ValueError`
            In case an array is passed whose dtype is not contained in :data:`cdxcore.npio._DTYPE_TO_CODE`,
            which has more than 32k dimensions, or which has an indivudual dimension longer than 2bn lines. 
        Not contiguous : :class:`RuntimeError`
            Raised if ``array`` is not contiguous and ``cont_block_size_mb`` is ``None``, its default.
    """
    if isinstance(file, str):
        with open( file, "wb", buffering=buffering ) as f:
            return to_file(f, array, buffering=buffering, cont_block_size_mb=cont_block_size_mb)
    f = file
    del file
    
    try:
        _tofile(f, array=array, cont_block_size_mb=cont_block_size_mb )
    except IOError as e:
        raise IOError(f"Could not write all {fmt_digits(array.nbytes)} bytes to {f.name}: {str(e)}") from e
    except Exception as e:
        raise type(e)(f"Failed to write {f.name}: {str(e)}") from e

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

def _readfromfile( f : int, array : np.ndarray, cont_block_size_mb : int ):
    # split into chunks
    shape    = array.shape
    length   = int( np.prod( array.shape, dtype=np.uint64 ) )
    array    = np.reshape( array, (length,) )
    dsize    = int(array.itemsize)
    max_size = int(LINUX_MAX_FILE_BLOCK//dsize)

    if not array.flags.c_contiguous:
        verify( not cont_block_size_mb is None, "Array is not c_contiguous. Use 'cont_block_size_mb' to auto-transform into contiguous chunks of memory.")
        verify( cont_block_size_mb > 0, "'cont_block_size_mb' must be positive.")
        max_size = min( max_size, max(1,cont_block_size_mb*1024*1024//dsize) )
        buffer   = np.empty( (max_size,), dtype=array.dtype )
    else:
        buffer   = None

    num      = int(length-1)//max_size+1
    read     = 0

    # read        
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        if array.flags.c_contiguous:
            nr  = f.readinto( array.data[s:e] )
        else:
            nr  = f.readinto( buffer.data[:e-s] )
            array[s:e] = buffer[:e-s]            
            
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
    """
    Binary header:
        Bytes
            [0:4]          : total byte length of the current block
            [4]            : dtype code for _DTYPE_TO_CODE
            [5:8]          : length of the shape tuple
            [8+i*8:16+i*8] : the actual tuple values
    """
    header  = f.read(4)
    if len(header) != 4:
        raise EOFError(f"could only read {len(header)} bytes not {4}.")

    total  =  int.from_bytes(header,"big",signed=False)
    header += f.read(total-4)
    if len(header) != total:
        raise EOFError(f"could only read {len(header)} bytes not {total}.")
    
    dtype, shape, _ = _decode_header( header )
    return dtype, shape

def read_from_file( file               : str|int, 
                    target             : np.ndarray|Callable, *, 
                    read_only          : bool = False,
                    buffering          : int  = -1,
                    validate_dtype     : type|None = None,
                    validate_shape     : tuple|None = None,
                    cont_block_size_mb : int|None = None
                  ) -> np.ndarray:
    """
    Read a :class:`numpy.ndarray` from disk into an existing array or into a new array.
    
    See :func:`cdxcore.npio.read_into` and :func:`cdxcore.npio.from_file` for more convenient interfaces
    for each use case.
    
    By default this function does not read into non-contiguous arrays. Use ``cont_block_size_mb``
    to enable an intermediary buffer to do so.
    
    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        target : np.ndarray | Callable
            Either an :class:`numpy.ndarray` to write into, or a function which returns allocates an array for a given shape and dtype.
            It must have the signature::
                
                def create( shape : tuple, dtype : type ):
                    return np.empty( shape, dtype )
                
        read_only : bool, default ``False``
            Whether to clear the ``writable`` `flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flags.html>`__ of the array
            after reading it from disk.
            
        buffering : int, default ``-1``
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.

        validate_dtype: dtype | None, default ``None``
            If not ``None``, check that the returned array has the specified dtype.
            
        validate_shape: tuple | None, default ``None``
            If not ``None``, check that the array has the specified shape.
            
        cont_block_size_mb : int | None, default ``None``
            By default this function does not read into arrays which are not C-contiguous (linear in memory). Use this
            parameter to allocate an intermediary buffer of ``cont_block_size_mb`` mega bytes to read into 
            non-contiguous arrays.
        
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
        Not contiguous : :class:`RuntimeError`
            Raised if ``array`` is not contiguous and ``cont_block_size_mb`` is ``None``, its default.
    """
    if isinstance(file, str):
        with open( file, "rb", buffering=buffering ) as f:
            return read_from_file( f, target, 
                                 read_only=read_only,
                                 buffering=buffering,
                                 validate_dtype=validate_dtype,
                                 validate_shape=validate_shape,
                                 cont_block_size_mb=cont_block_size_mb)
    f = file
    del file
        
    # read shape
    dtype, shape = _readheader(f)
    assert isinstance(shape, tuple), ("Internal error", shape, dtype, type(dtype))

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
        _readfromfile(f, array, cont_block_size_mb=cont_block_size_mb )
    except EOFError as e:
        raise EOFError(f"Cannot read from {f.name}: {str(e)}", e)
    if read_only:
        array.flags.writeable  = False

    assert array.flags.writeable == (not read_only), ("Internal flag error", array.flags.writeable, read_only, not read_only )
    return array

def read_dtype_and_shape( file : str|int, buffering : int = -1 ) -> tuple:
    """
    Read shape and dtype from a numpy binary file by only reading the file header.
    
    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        buffering : int, default ``-1``
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.
        
    Returns
    -------
        dtype, shape : tuple, type
            Shape and dtype.

    Raises
    ------
        EOF : :class:`EOFError`
            In case the function failed to read the whole header block.
    """

    if isinstance(file, str):
        with open( file, "rb", buffering=buffering ) as f:
            return read_dtype_and_shape( f, buffering=buffering )
    return _readheader(file)

def read_into( file, array : np.ndarray, *, read_only : bool = False, buffering : int = -1,cont_block_size_mb : int|None = None ):
    """
    Read an array from disk into an existing :class:`numpy.ndarray`.    
    
    The receiving array must have the same shape and dtype as the array on disk. 

    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        target : np.ndarray
            Target array to write into. This array must have the same shape and dtype as the source data.
                
        read_only : bool, default ``False``
            Whether to clear the ``writable`` `flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flags.html>`__ of the array
            after reading it from disk.
            
        buffering : int, default ``-1``
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.

        cont_block_size_mb : int | None, default ``None``
            By default this function does not read into arrays which are not C-contiguous (linear in memory). Use this
            parameter to allocate an intermediary buffer of ``cont_block_size_mb`` mega bytes to read into 
            non-contiguous arrays.
        
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
            or if it does not match the geometry of ``target``.
        Not contiguous : :class:`RuntimeError`
            Raised if ``array`` is not contiguous and ``cont_block_size_mb`` is ``None`` (its default).
    """
    return read_from_file( file, target = array, read_only=read_only, buffering=buffering, cont_block_size_mb=cont_block_size_mb )

def from_file( file, *, validate_dtype = None, validate_shape = None, read_only : bool = False, buffering : int = -1, cont_block_size_mb : int|None = None  ) -> np.ndarray:
    """
    Read array from disk into a new :class:`numpy.ndarray`.
    
    Use :func:`cdxcore.npshm.read_shared_array` to create a shared array 
    instead.

    Parameters
    ----------
        file : str | int
            A file name to be passed to :func:`open`, or a file handle from :func:`open`.

        validate_dtype : dtype | None, default ``None``
            If not ``None``, check that the returned array has the specified dtype.
            
        validate_shape : tuple | None, default ``None``
            If not ``None``, check that the array has the specified shape.

        read_only : bool, default ``False``
            Whether to clear the ``writable`` `flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flags.html>`__ of the array
            after reading it from disk.
            
        buffering : int, default ``-1``
            Buffering strategy. Only used if ``file`` is a string and :func:`open` is called. Use ``0`` to turn off
            buffering. The default, ``-1``, is the default.

        cont_block_size_mb : int | None, default ``None``
            By default this function does not read into arrays which are not C-contiguous (linear in memory). Use this
            parameter to allocate an intermediary buffer of ``cont_block_size_mb`` mega bytes to read into 
            non-contiguous arrays.

    Returns
    -------
        Array : :class:`numpy.ndarray`
            Returns newly created numpy array.
            
    Raises
    ------
        EOF : :class:`EOFError`
            In case the function failed to read the whole file.
        I/O error : :class:`IOError`
            In case the function failed to match the desired ``validate_dtype`` or ``validate_shape``.
        Not contiguous : :class:`RuntimeError`
            Raised if ``array`` is not contiguous and ``cont_block_size_mb`` is ``None`` (its default).
    """
    return read_from_file(
                         file,
                         target=lambda shape, dtype : np.empty( shape=shape, dtype=dtype ),
                         read_only = read_only, 
                         validate_dtype=validate_dtype, 
                         validate_shape=validate_shape,
                         buffering=buffering,
                         cont_block_size_mb=cont_block_size_mb )
        


