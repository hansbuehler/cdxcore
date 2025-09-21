"""
Shared memory tools
"""

from .config import Config, Int, Float # NOQA
from .err import verify
from .npio import read_into, read_shape_and_dtype, _DTYPE_TO_CODE, _CODE_TO_DTYPE, _create_header, _decode_header
from .util import fmt_list, fmt_digits
import numpy as np
import weakref
from multiprocessing import shared_memory

try:
    # shared array only works on Linx
    import SharedArray as _sa
except ModuleNotFoundError:
    _sa = None

# ===============================================
# Windows
# ===============================================
    
def _win_finalize(shm):
    """
    try:
        shm = shared_memory.SharedMemory(name=name)
    except FileNotFoundError:
        return
    """
    try:
        shm.close()
    finally:
        #shm.unlink() # no effect on windows, c.f. https://docs.python.org/3/library/multiprocessing.shared_memory.html
        pass

def _win_create( name : str, shape : tuple, dtype : type ):
    """
    Create a shared-memory ndarray.
    """
    dtype = np.dtype( dtype )
    try:    
        header = _create_header( shape, dtype )
    except Exception  as e:
        raise type(e)(f"Could not create shared memory '{name}' of type {str(dtype)} with shape {shape}: {str(e)}")
    
    # allocate enough memory for geometry and data
    print( dtype, type(dtype), int(np.prod(shape)), dtype.itemsize, len(header))
    nbytes                = int(np.prod(shape)) * dtype.itemsize + len(header)
    shm                   = shared_memory.SharedMemory(name=name, create=True, size=nbytes)
    shm.buf[:len(header)] = header
    arr                   = np.ndarray(shape, dtype=dtype, buffer=shm.buf[len(header):], order="C")
    def _win_finalize():
        print("_win_create._win_finalize", name)
        shm.close()
    weakref.finalize(arr, _win_finalize )
    print("_win_create: created", name)

    return arr, shm.name

def _win_attach( name : str, read_only : bool ):
    """
    Attach to an existing shared block and get an ndarray view.
    """
    shm       = shared_memory.SharedMemory(name=name, create=False )
    buf       = shm.buf
    try:    
        dtype,\
        shape,\
        buf       = _decode_header(buf)
    except Exception  as e:
        raise type(e)(f"Could not attach to shared memory '{name}' : {str(e)}")

    arr = np.ndarray( shape, dtype=dtype, buffer=buf, order="C")
    if read_only:
        arr.setflags(write=False)
    def _win_finalize():
        print("_win_attach._win_finalize", name)
        shm.close()
    weakref.finalize(arr, _win_finalize )
    print("_win_attach: attached", name)
    return arr
    
def _sa_create( name, shape, dtype ):
    if name.find("://") != -1:
        raise ValueError("Shared memory name should not contain ''://'; found '{name}'")

    if not _sa is None:
        # linux        
        array = _sa.create("shm://" + name, shape, dtype )
        def _finalize():
            print("_sa_create._finalize", name)
            _sa.delete(name)
        weakref.finalize(array, _finalize )
        print("_sa_create", name)
        return array
    else:
        # windows
        return _win_create(name, shape, dtype)

def _sa_attach( name, read_only ):
    if name.find("://") != -1:
        raise ValueError("Shared memory name should not contain ''://'; found '{name}'")

    # linux        
    if not _sa is None:
        array = _sa.attach("shm://" + name, ro=read_only )
        def _finalize():
            print("_sa_attach._finalize", name)
            _sa.delete(name)
        weakref.finalize(array, _finalize )
        print("_sa_attach", name)
        return array

    # windows
    return _win_attach(name, read_only=read_only )

def _sa_delete( name ):
    if name.find("://") != -1:
        raise ValueError("Shared memory name should not contain ''://'; found '{name}'")

    # linux        
    if not _sa is None:
        name = "shm://" + name
        return _sa.delete(name)
    
    return # NOP

# ===============================================
# Wrapper for Linux and Windows
# ===============================================
    
def create_sharedarray( name : str, shape : tuple, dtype, *, raise_on_error : bool = True, force : bool = False, full = None ) -> np.ndarray:
    """
    Create a shared array.
    
    This function is a simplistic wrapper funcion around `SharedArray.create <https://gitlab.com/tenzing/shared-array>`__
    on Linux/WSL, or aroud :class:`multiprocessing.shared_memory.SharedMemory` on Windows.
    
    **Linux**
    
    Note that the amount of shared memory available on Linux is limited.
    Use "findmnt -o AVAIL,USED /dev/shm" to check available size. Modify /etc/fstab to amend.
    
    Parameters
    ----------
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.
            
        shape : tuple
            Shape of the array.
            
        dtype : dtype
            Numpy dtype of the array.
            
        raise_on_error : bool, default ``True``
            If an array called ``name`` already exists, this function raises an :class:`FileExistsError` exception 
            if ``raise_on_error`` is ``True``; otherwise it will return ``None``.
            
        full  : default ``None``
            Value to fill array with, or ``None`` to not fill the array.
            
        force : bool, default ``False``
            Whether to attempt to delete any existing arrays.
            Note that while the file might be get deleted the actual memory is
            only freed after all references are destroyed.
        
    Returns
    -------
        Array : :class:`numpy.ndarray` like
            Shared numpy array, or ``None`` if the named array exists and if ``raise_on_error`` is ``False``.

    Raises
    ------
        File exists : :class:`FileExistsError`
           If an array ``name`` already exists (and ``raise_on_error`` is ``True``).
    """
    
    shape = tuple(shape)
    dtype = dtype if not isinstance(dtype, type) else dtype() 
    
    try:
        array = _sa_create( name=name, shape=shape, dtype=dtype )

    except FileExistsError as e:
        if force:
            _sa_delete( name )
            return create_sharedarray( name=name, shape=shape, dtype=dtype, raise_on_error=raise_on_error, full=full, force=False )
        if raise_on_error:
            raise e
        return None

    if not full is None:
        array[...] = full            
    assert is_sharedarray(array), ("Internal error - fix is_sharedarray")
    return array

def attach_sharedarray( name : str, *, 
                        validate_shape : tuple|None = None, 
                        validate_dtype : type|None  = None, 
                        raise_on_error : bool  = True,
                        read_only      : bool  = False ) -> np.ndarray:
    """
    Attach a :class:`numpy.ndarray` to am existing shared array.
    
    Simplistic wrapper funcion around `SharedArray.attach <https://gitlab.com/tenzing/shared-array>`__ on Linux
    or :class:`multiprocessing.shared_memory.SharedMemory` on Windows.
            
    Parameters
    ----------
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.

        validate_shape : tuple|None, default ``None``
            Validate that array has this shape, if not ``None``. If the array has a different shape, raise a :class:`ValueError`.

        validate_dtype : dtype|None, default ``None``
            Validate that array has this dtype, if not ``None``. If the array has a different dtype, raise a :class:`ValueError`.

        raise_on_error : bool, default ``True``
            If an array called ``name`` does not exists, this function raises an :class:`FileNotFoundError` exception 
            if ``raise_on_error`` is ``True``; otherwise it will return ``None``.

        read_only : boo, default ``False``
            Whether to set numpy's `writeable flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.setflags.html>`__
            to ``False``.

    Returns
    -------
        Array : :class:`numpy.ndarray` like
            The array, or ``None`` if no array of ``name`` exists and ``raise_on_error`` is ``False``.
        
    Throws
    ------
        File not foujnd : :class:`FileNotFoundError`
            If an array ``name`` does not exist  (and ``raise_on_error`` is ``True``).
        Incorrect geometry : :class:`ValueError`
            Raised if ``validate_shape`` or ``validate_dtype` do not match the array  (and ``raise_on_error`` is ``True``).
    """
    try:
        array = _sa_attach(name, read_only=read_only )

    except NameError as e:
        if raise_on_error:
            raise e
        return None
    except FileNotFoundError as e:
        if raise_on_error:
            raise e
        return None
        
    if not validate_shape is None and tuple(array.shape) != validate_shape: ValueError(f"Shared array {name} has shape {array.shape} not {validate_shape}", tuple(array.shape))
    if not validate_dtype is None and array.dtype != validate_dtype: raise ValueError(f"Shared array {name} has dtype {array.dtype} not {validate_dtype}", array.dtype)
    if read_only:
        array.flags.writeable  = False

    assert is_sharedarray(array), ("Internal error - fix is_sharedarray")
    return array

def read_sharedarray( file : int|str, 
                      name : str, *,
                      validate_shape  : tuple = None, 
                      validate_dtype  : type = None,
                      accept_existing : bool = True, 
                      buffering       : int  = -1,
                      read_only       : bool = False,
                      return_status   : bool = False) -> np.ndarray:
    """
    Read a shared array from disk into a new named shared :class:`numpy.ndarray` in binary format
    using :func:`cdxcore.npio.readinto`.
    
    If ``accept_existing`` is ``True``, allow attaching to an existing shared array ``name``.

    Parameters
    ----------
        file : str | int
            File from :func:`open` or file name.
        
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.

        validate_shape : tuple|None, default ``None``
            Validate that array has this shape, if not ``None``. If the array has a different shape, raise a :class:`ValueError`.

        validate_dtype : dtype|None, default ``None``
            Validate that array has this dtype, if not ``None``. If the array has a different dtype, raise a :class:`ValueError`.

        raise_on_error : bool, default ``True``
            If an array called ``name`` does not exists, this function raises an :class:`FileNotFoundError` exception 
            if ``raise_on_error`` is ``True``; otherwise it will return ``None``.

        read_only : boo, default ``False``
            Whether to set numpy's `writeable flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.setflags.html>`__
            to ``False``.

        accept_existing : bool, default ``True``
            Whether to first try to attach to an existing shared array ``name``.
            If either ``validate_shape`` or ``validate_dtype`` is ``None``, then the function will read
            the array characteristics from the file on disk even if an exsting array exists
            to ensure its characteristics match those on disk.

        buffering : int, default ``-1``
            See :func:`open`. Use -1 for default behaviour.
        
        return_status : bool default ``False``
            Whether to return ``status`` as well. See below.

    Returns
    -------
        Array : :class:`numpy.ndarray` like
            If ``return_status`` is ``False``, return just the array or ``None`` if an error occured and ``raise_on_error`` is False.
    
        ( Array, attached ) : :class:`numpy.ndarray` like, bool
            If ``return_status`` is ``True``, and if no error occured, then the
            function returns a tuple containing of the array and a boolean indicating whether the array
            was attached to an existing shared array (``True``), or whether a new shared array was created (``False``).
            Useful for status messages.
            
    Throws
    ------
        File exists : :class:`FileExistsError`
            If an array ``name`` already exists, and ``accept_existing`` was ``False`` (and ``raise_on_error`` is ``True``).
        Incorrect geometry : :class:`ValueError`
            Raised if ``validate_shape`` or ``validate_dtype` do not match the array  (and ``raise_on_error`` is ``True``).

    """
    shape = None
    dtype = None
    
    if accept_existing:
        if validate_shape is None or validate_dtype is None:
            shape, dtype   = read_shape_and_dtype( file, buffering=buffering )
            validate_shape = validate_shape if not validate_shape is None else shape
            validate_dtype = validate_dtype if not validate_dtype is None else dtype

        r = attach_sharedarray( name, validate_shape=validate_shape, validate_dtype=validate_dtype, raise_on_error=False, read_only=read_only )
        if not r is None:
            if not return_status:
                return r
            return r, True
        
    if shape is None:
        shape, dtype = read_shape_and_dtype( file, buffering=buffering )

    if not validate_shape is None and shape != validate_shape: raise ValueError(f"File array {name} has shape {shape} not {validate_shape}", shape)
    if not validate_dtype is None and dtype != validate_dtype: raise ValueError(f"File array {name} has dtype {dtype} not {validate_dtype}", dtype)

    r = create_sharedarray( name=name, shape=shape, dtype=dtype, raise_on_error=True, full=None ) 
    read_into( file, r, read_only = read_only)
    assert r.flags.writeable == (not read_only), ("Internal flag error", r.flags.writeable, read_only)
    assert is_sharedarray(r), ("Internal error - fix is_sharedarray")
    
    if not return_status:
        return r
    return r, False

def is_sharedarray( x ) -> bool:
    """ Whether an array is "shared" """
    assert isinstance(x,np.ndarray), ("'x' must be a np.ndarray", type(x))
    return not x.base is None and str(type(x.base)) == "<class 'shared_array.map_owner'>"

def del_sharedarray_file( name : str):
    """
    Delete a shared memory file. 
    
    The file will be deleted but the respective memory is only freed after the last reference was destroyed.
    Note that this function is only required under Linux; under Windows releasing the last lock will lead to the
    deletion of the object. Therefore, this is a NOOP under Windows.
    
    Parameters
    ----------
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.
    """
    _sa_delete( name )

    