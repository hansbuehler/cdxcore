r"""
Shared memory numpy arrays.

Overview
--------

The functions in this module wrap :class:`multiprocessing.shared_memory.SharedMemory` into a numpy array
with garbage collection clean up, depending in the operating system.

**In process 1:**

.. code-block:: python

    from cdxcore.npshm import create_shared_array
    import numpy as np

    test_name = "Test2121"    
    test = create_shared_array( test_name, shape=(10,3), dtype=np.int32, force=True, full=0 )
    test[:,1] = 1

**In process 2:**

.. code-block:: python

    from cdxcore.npshm import create_shared_array
    import numpy as np

    test_name = "Test2121"    
    test = attach_shared_array( test_name, validate_shape=(10,3), validate_dtype=np.int32 )
    assert np.all( test[:,1] == 1)
    test[:,2] = 2

**Back in process 1:**

.. code-block:: python

    assert np.all( test[:,2] == 2)

Loading binary files
^^^^^^^^^^^^^^^^^^^^

This module's' :func:`cdxcore.npshm.read_shared_array` reads numpy arrays stored to disk
with :func:`cdxcore.npio.to_file` directly into shared memory.

Garbage Collection
^^^^^^^^^^^^^^^^^^

The functions here are simplistic wrappers around :class:`multiprocessing.shared_memory.SharedMemory` on
Linux and Windows. The returned object will call :meth:`multiprocessing.shared_memory.SharedMemory.close` 
upon garbage collection, but not :meth:`multiprocessing.shared_memory.SharedMemory.unlink`.
   
**Linux**

Under Linux above settings means that the shared file will reside permanently -- and will remain sharable -- in ``/dev/shm/`` until it 
is manually deleted. Call :func:`cdxcore.npshm.delete_shared_array` to delete a shared file manually.

The amount of shared memory available on Linux is limited by default.
Use ```findmnt -o AVAIL,USED /dev/shm`` to check available size. Modify ``/etc/fstab`` to amend.

**Windows**

Windows keeps track of access to shared memory and will release it automatically upon garbage collection of the last Python object,
or upon destruction of all processes with access to the shared memory block. Therefore the object does not persist between 
independent runs of your software.

Import
------

.. code-block:: python

    from cdxcore.npio import create_shared_array, attach_shared_array, read_shared_array

Documentation
-------------
"""

from .config import Config, Int, Float # NOQA
from .npio import read_into, read_dtype_and_shape, _create_header, _decode_header
from .verbose import Context
import numpy as np
import weakref
from multiprocessing import shared_memory
import platform as platform

ALIGN = 64
"""
Default memory alignment after an internal descriptive header.
A 64 byte alignment ensures that optimized AVX2, AVX512 etc, see
`this discussion <https://stackoverflow.com/questions/77848460/are-64-byte-cpu-cache-line-reads-aligned-on-64-byte-boundaries?utm_source=chatgpt.com>`__
"""

def create_shared_array( name  : str, 
                         shape : tuple, 
                         dtype : type|str, *, 
                         raise_on_error : bool = True, 
                         full  : float|np.ndarray|None = None,
                         force : bool = False, 
                         verbose : Context|None = None ) -> np.ndarray:
    """
    Create a new named shared array.
    
    This function can ``force`` creation of a new array on Linux only.
    
    This function is a simplistic wrapper around creating a :class:`numpy.ndarray` with
    a newly created :class:`multiprocessing.shared_memory.SharedMemory` buffer.
    The returned object will call :meth:`multiprocessing.shared_memory.SharedMemory.close` 
    upon garbage collection, but not :meth:`multiprocessing.shared_memory.SharedMemory.unlink`.
       
    **Linux**

    Under Linux above settings means that the shared file will reside permanently -- and will remain sharable -- in ``/dev/shm/`` until it 
    is manually deleted. Call :func:`cdxcore.npshm.delete_shared_array` to delete a shared file manually.
    
    The amount of shared memory available on Linux is limited by default.
    Use ```findmnt -o AVAIL,USED /dev/shm`` to check available size. Modify ``/etc/fstab`` to amend.
    
    **Windows**
    
    Windows keeps track of access to shared memory and will release it automatically upon garbage collection of the last Python object,
    or upon destruction of all processes with access to the shared memory block. Therefore the object does not persist between 
    independent runs of your software.
    
    Parameters
    ----------
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.
            
        shape : tuple
            Shape of the array.
            
        dtype : dtype | str
            Numpy dtype of the array.
            
        raise_on_error : bool, default ``True``
            If an array called ``name`` already exists: if ``raise_on_error`` is ``True``, then this function raises an :class:`FileExistsError` exception;
            otherwise it will return ``None``.
            
        full : float | :class:`numpy.ndarray` | None, default ``None``
            Value to fill array with, or ``None`` to not fill the array.
            
        force : bool, default ``False``
            Whether to attempt to delete any existing arrays under Linux only.
            Note that while the file might be get deleted the actual memory is
            only freed after all references are destroyed.
            
        verbose : :class:`cdxcore.verbose.Context` | None, default ``None``
            If not ``None`` print out activity information, typically for debugging.
        
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
    dtype = np.dtype( dtype )
    
    try:    
        header = _create_header( shape, dtype )
    except Exception  as e:
        raise type(e)(f"Could not create shared memory '{name}' of type {str(dtype)} with shape {shape}: {str(e)}") from e
    
    # allocate shared memory for geometry and data
    align        = max(ALIGN, dtype.alignment)
    len_header64 = (( len(header) + align - 1) // align ) * align
    nbytes       = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize + len_header64

    try:
        shm  = shared_memory.SharedMemory(name=name, create=True, size=nbytes )
    except FileExistsError as e:
        if force:
            shm  = shared_memory.SharedMemory(name=name, create=False )
            shm.close()
            if not platform.system().startswith("W"):
                shm.unlink()
            return create_shared_array( name=name, shape=shape, dtype=dtype, raise_on_error=raise_on_error, full=full, force=False, verbose=verbose )
        if raise_on_error:
            raise e
        return None
            
    # assign
    shm.buf[:len(header)]             = header
    if len(header)<len_header64:
        shm.buf[len(header):len_header64] = b"\x00" * ( len_header64 - len(header) )
    array                             = np.ndarray(shape, dtype=dtype, buffer=shm.buf[len_header64:], order="C")
    def _finalize():
        if not verbose is None: verbose.report(1,f"create_shared_array: _finalize '{name}'")
        shm.close()
        #shm.unlink() c.f. https://docs.python.org/3/library/multiprocessing.shared_memory.html
    weakref.finalize(array, _finalize )
    if not verbose is None: verbose.write(f"create_shared_array '{name}'")

    if not full is None:
        array[...] = full            
    assert is_shared_array(array), ("Internal error - fix is_sharedarray")
    return array

def attach_shared_array(name : str, *, 
                        validate_shape : tuple|None = None, 
                        validate_dtype : type|None  = None, 
                        raise_on_error : bool  = True,
                        read_only      : bool  = False,
                        verbose        : Context|None = None ) -> np.ndarray:
    """
    Attach to an existing named shared array.
    
    This function is a simplistic wrapper around creating a :class:`numpy.ndarray` with
    an existing :class:`multiprocessing.shared_memory.SharedMemory` buffer.
    The returned object will call :meth:`multiprocessing.shared_memory.SharedMemory.close` 
    upon garbage collection, but not :meth:`multiprocessing.shared_memory.SharedMemory.unlink`.
       
    **Linux**

    Under Linux above settings means that the shared file will reside permanently -- and will remain sharable -- in ``/dev/shm/`` until it 
    is manually deleted. Call :func:`cdxcore.npshm.delete_shared_array` to delete a shared file manually.
    
    The amount of shared memory available on Linux is limited by default.
    Use ```findmnt -o AVAIL,USED /dev/shm`` to check available size. Modify ``/etc/fstab`` to amend.
    
    **Windows**
    
    Windows keeps track of access to shared memory and will release it automatically upon garbage collection of the last Python object,
    or upon destruction of all processes with access to the shared memory block. Therefore the object does not persist between 
    independent runs of your software.
            
    Parameters
    ----------
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.

        validate_shape : tuple | None, default ``None``
            Validate that array has this shape, if not ``None``. If the array has a different shape, raise a :class:`ValueError`.

        validate_dtype : dtype | None, default ``None``
            Validate that array has this dtype, if not ``None``. If the array has a different dtype, raise a :class:`ValueError`.

        raise_on_error : bool, default ``True``
            If an array called ``name`` does not exists: if ``raise_on_error`` is ``True``, this function raises an :class:`FileNotFoundError` exception;
            otherwise it will return ``None``.
            
            This function will always raise a :class:`ValueError`  if the shape or dtype validation fails.

        read_only : bool, default ``False``
            Whether to set numpy's `writeable flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.setflags.html>`__
            to ``False``.

        verbose : :class:`cdxcore.verbose.Context` | None, default ``None``
            If not ``None`` print out activity information, typically for debugging.

    Returns
    -------
        Array : :class:`numpy.ndarray` like
            The array, or ``None`` if no array of ``name`` exists and ``raise_on_error`` is ``False``.
        
    Raises
    ------
        File not found : :class:`FileNotFoundError`
            If an array ``name`` does not exist  (and ``raise_on_error`` is ``True``).
        Incorrect geometry : :class:`ValueError`
            Raised if ``validate_shape`` or ``validate_dtype`` do not match the array  (and ``raise_on_error`` is ``True``).
    """
    
    try:
        shm       = shared_memory.SharedMemory( name=name, create=False )
        buf       = shm.buf
    except NameError as e:
        if raise_on_error:
            raise e
        return None
    except FileNotFoundError as e:
        if raise_on_error:
            raise e
        return None
    except Exception as e:
        raise type(e)(f"Could not attach to shared memory '{name}': {str(e)}") from e
        
    try:    
        dtype,\
        shape,\
        buf       = _decode_header(buf, align=ALIGN)
    except Exception  as e:
        raise type(e)(f"Could not attach to shared memory '{name}' : {str(e)}") from e

    array = np.ndarray( shape, dtype=dtype, buffer=buf, order="C")
    def _finalize():
        if not verbose is None: verbose.report(1,f"attach_shared_array: _finalize '{name}'")
        shm.close()
        #shm.unlink() c.f. https://docs.python.org/3/library/multiprocessing.shared_memory.html
    weakref.finalize(array, _finalize )

    if not validate_shape is None and tuple(array.shape) != validate_shape: raise ValueError(f"Shared array {name} has shape {array.shape} not {validate_shape}", tuple(array.shape))
    if not validate_dtype is None and array.dtype != validate_dtype: raise ValueError(f"Shared array {name} has dtype {array.dtype} not {validate_dtype}", array.dtype)
    if read_only:
        array.flags.writeable  = False

    if not verbose is None: verbose.write(f"attach_shared_array '{name}'")
    assert is_shared_array(array), ("Internal error - fix is_sharedarray")
    return array

def read_shared_array(file : int|str, 
                      name : str, *,
                      validate_shape  : tuple|None = None, 
                      validate_dtype  : type|None = None,
                      accept_existing : bool = True, 
                      buffering       : int  = -1,
                      read_only       : bool = False,
                      return_status   : bool = False,
                      verbose         : Context|None = None ) -> np.ndarray:
    """
    Read a shared array from disk into a new named shared :class:`numpy.ndarray` in binary format
    using :func:`cdxcore.npio.read_into`.
    
    If ``accept_existing`` is ``True``, this function will first attempt to
    attach to an existing shared array ``name``.

    Parameters
    ----------
        file : str | int
            File from :func:`open` or file name.
        
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.

        validate_shape : tuple | None, default ``None``
            Validate that array has this shape, if not ``None``. If the array has a different shape, raise a :class:`ValueError`.

        validate_dtype : dtype | None, default ``None``
            Validate that array has this dtype, if not ``None``. If the array has a different dtype, raise a :class:`ValueError`.

        read_only : bool, default ``False``
            Whether to set numpy's `writeable flag <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.setflags.html>`__
            to ``False``.

        accept_existing : bool, default ``True``
            Whether to first try to attach to an existing shared array ``name``.
            If either ``validate_shape`` or ``validate_dtype`` is ``None``, then the function will read
            the array characteristics from the file on disk even if an existing array exists
            to ensure its characteristics match those on disk.

        buffering : int, default ``-1``
            See :func:`open`. Use -1 for default behaviour.
        
        return_status : bool default ``False``
            Whether to return ``status`` as well. See below.

        verbose : :class:`cdxcore.verbose.Context` | None, default ``None``
            If not ``None`` print out activity information, typically for debugging.

    Returns
    -------
        Array : :class:`numpy.ndarray` like
            If ``return_status`` is ``False``, return just the array or ``None`` if an error occurred and ``raise_on_error`` is False.
    
        ( Array, attached ) : :class:`numpy.ndarray` like, bool
            If ``return_status`` is ``True``, and if no error occurred, then the
            function returns a tuple containing the array and a boolean indicating whether the array
            was attached to an existing shared array (``True``), or whether a new shared array was created (``False``).
            Useful for status messages.
            
    Raises
    ------
        File exists : :class:`FileExistsError`
            If an array ``name`` already exists, and ``accept_existing`` was ``False`` (and ``raise_on_error`` is ``True``).
        Incorrect geometry : :class:`ValueError`
            Raised if ``validate_shape`` or ``validate_dtype`` do not match the array  (and ``raise_on_error`` is ``True``).

    """
    shape = None
    dtype = None
    
    if accept_existing:
        if validate_shape is None or validate_dtype is None:
            dtype, shape   = read_dtype_and_shape( file, buffering=buffering )
            validate_shape = validate_shape if not validate_shape is None else shape
            validate_dtype = validate_dtype if not validate_dtype is None else dtype

        r = attach_shared_array( name, validate_shape=validate_shape, validate_dtype=validate_dtype, raise_on_error=False, read_only=read_only, verbose=verbose )
        if not r is None:
            if not return_status:
                return r
            return r, True
        
    if shape is None:
        dtype, shape = read_dtype_and_shape( file, buffering=buffering )

    if not validate_shape is None and shape != validate_shape: raise ValueError(f"File array {name} has shape {shape} not {validate_shape}", shape)
    if not validate_dtype is None and dtype != validate_dtype: raise ValueError(f"File array {name} has dtype {dtype} not {validate_dtype}", dtype)

    r = create_shared_array( name=name, shape=shape, dtype=dtype, raise_on_error=True, full=None ) 
    read_into( file, r, read_only = read_only)
    assert r.flags.writeable == (not read_only), ("Internal flag error", r.flags.writeable, read_only)
    assert is_shared_array(r), ("Internal error - fix is_sharedarray")
    if not verbose is None: verbose.write(f"read_shared_array '{name}'")
    
    if not return_status:
        return r
    return r, False

def delete_shared_array( name : str, raise_on_error : bool = True, *, verbose : Context|None = None ) -> bool:
    """
    Deletes the shared array associated with ``name``
    by calling :meth:`multiprocessing.shared_memory.SharedMemory.unlink`.
    
    **Linux**
    
    Under Linux, calling ``unlink()`` will prevent further attachments to this file, 
    and allows creating a new file in its place. Existing shares remain operational.
    Note that the file is deleted immediately, not once the last reference was deleted.
    
    **Windows**
    
    This function does nothing under Windows.
    
    Parameters
    ----------
        name : str
            Name of the array. This must be a valid file name.
            In Linux, shared memory is managed via ``/dev/shm/``.

        raise_on_error : bool, default ``True``
            If the file could not be deleted successfully, raise the respective Exception.
            If the file did not exist, this function will return successfully.

        verbose : :class:`cdxcore.verbose.Context` | None, default ``None``
            If not ``None`` print out activity information, typically for debugging.

    Returns
    -------
        Success : bool
            Whether ``name`` can now be used for a new shared memory block.
    """
    if platform.system()[0].upper() == "W":
        return True
    try:
        shm  = shared_memory.SharedMemory(name=name, create=False )
        shm.close()
        shm.unlink()
        if not verbose is None: verbose.write(f"delete_shared_array '{name}'")
    except FileNotFoundError:
        return True
    except Exception as e:
        if raise_on_error:
            raise type(e)(f"Failed to delete shared array '{name}': {str(e)}") from e
        return False
    return True

def is_shared_array( x ) -> bool:
    """ Whether an array is "shared". This function does not currently work and always returns ``True`` """
    return True
    assert isinstance(x,np.ndarray), ("'x' must be a np.ndarray", type(x))
    return not x.base is None and str(type(x.base)) == "<class 'shared_array.map_owner'>"

