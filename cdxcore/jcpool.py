"""
Simple multi-processing conv wrapper around (already great)
`joblib.Parallel() <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__.

The minor additions are that parallel processing will be a tad more convenient for dictionaries,
and that it supports routing :class:`cdxcore.verbose.Context` messaging via a
:class:`multiprocessing.Queue` to a single thread.

Import
------
.. code-block:: python

    from cdxcore.jcpool import JCPool
    
Documentation
-------------
"""
from __future__ import annotations

from joblib import Parallel as joblib_Parallel, delayed as _jl_delayed, cpu_count
import multiprocessing as mp
from multiprocessing import Manager, Queue
from threading import Thread, get_ident as get_thread_id
import gc as gc
from collections import OrderedDict
from collections.abc import Mapping, Callable, Sequence, Iterable
import functools as functools
import uuid as uuid
import os as os
import datetime as datetime
import joblib as joblib
import psutil as psutil
import math as math
import logging as logging
from dataclasses import dataclass

from .verbose import Context, Timer
from .subdir import SubDir
from .uniquehash import unique_hash8
from .err import verify_inp
from .util import fmt_digits

class _PromoteMemoryLeakToFatal(logging.Filter):
    """ 
    Utility class to promote a memory leak INFO to a FATAL error.
    By default this will trigger a runtime debug warning (not an exception).
    
    This is somewhat brittle and relies on the code specifics in https://github.com/joblib/joblib/blob/main/joblib/externals/loky/process_executor.py
    """
    def filter(self, record):
        if "Memory leak detected" in record.getMessage():
            record.levelno = logging.FATAL
            record.levelname = "FATAL"
        return True            

def _ProcessF( *, 
               mem_leak_enforce : bool,
               mem_leak_max_memory : int,
               mem_leak_timer : float,
               logging_level : int|None,
               F : Callable,
               F_args : list,
               F_kwargs : dict ):
    """
    Child process wrapper
    """
    import joblib as joblib_
    import multiprocessing as mp_

    # ensure a memory leak becomes a FATAL
    # (the default level is WARNING)
    # ------------------------------------

    logger = mp_.util.log_to_stderr(level=logging_level) if not logging_level is None else mp_.util.getLogger()
    logger.addFilter(_PromoteMemoryLeakToFatal())
    
    # adjust memory leak detection
    # ----------------------------

    joblib_.externals.loky.process_executor._USE_PSUTIL = mem_leak_enforce
    joblib_.externals.loky.process_executor._MAX_MEMORY_LEAK_SIZE = mem_leak_max_memory
    joblib_.externals.loky.process_executor._MEMORY_LEAK_CHECK_DELAY = mem_leak_timer

    return F(*F_args, **F_kwargs)

class ParallelContextChannel( Context ):
    """
    Lightweight :class:`cdxcore.verbose.Context` ``channel`` which is pickle'able.

    This channel sends messages it receives to a :class:`multiprocessing.Queue`.
    """
    def __init__(self, *, cid, maintid, queue, f_verbose) -> None:
        self._queue        = queue
        self._cid          = cid
        self._maintid      = maintid
        self._f_verbose    = f_verbose
    def __call__(self, msg : str, flush : bool ):
        """
        Sends ``msg`` via a :class:`multiprocessing.Queue` to the main thread for
        printing.
        """
        if get_thread_id() == self._maintid:
            self._f_verbose._raw(msg,end='',flush=flush)
        else:
            return self._queue.put( (msg, flush) )

class _ParallelContextOperator( object ):
    """
    Queue-based channel backbone for _ParallelContextChannel
    This object cannot be pickled; use self.mp_context as object to pass to other processes.
    """
    def __init__(self, pool_verbose     : Context,      # context to print Pool progress to (in thread)
                       f_verbose        : Context,      # original function context (in thread)
                       verbose_interval : float|None = None  # throttling for reporting 
            ) -> None:
        cid = id(f_verbose)
        tid = get_thread_id()
        with pool_verbose.write_t(f"Launching messaging queue '{cid}' using thread '{tid}'... ", end='') as tme:
            self._cid          = cid
            self._tid          = tid
            self._pool_verbose = pool_verbose
            self._mgr          = Manager() 
            self._queue        = self._mgr.Queue()
            self._thread       = Thread(target=self.report, kwargs=dict(cid=cid, queue=self._queue, f_verbose=f_verbose, verbose_interval=verbose_interval), daemon=True)
            self._mp_context   = Context( f_verbose, 
                                          channel=ParallelContextChannel(
                                                    cid=self._cid, 
                                                    queue=self._queue, 
                                                    maintid=self._tid,
                                                    f_verbose=f_verbose
                                                    ) )
            self._thread.start()
            pool_verbose.write(f"done; this took {tme}.", head=False)

    def __del__(self):
        """ clean up; should not be necessary """
        self.terminate()
        
    def terminate(self):
        """ stop all multi-thread/processing activity """
        if self._queue is None:
            return
        tme = Timer()
        self._queue.put( None )
        self._thread.join(timeout=2)
        if self._thread.is_alive():
            raise RuntimeError("Failed to terminate thread")
        self._thread = None
        self._queue = None
        self._mgr = None
        gc.collect()
        self._pool_verbose.write(f"Terminated message queue '{self.cid}'. This took {tme}.")

    @property
    def cid(self) -> str:
        """ context ID. Useful for debugging """
        return self._cid

    @property
    def mp_context(self):
        """ Return the actual channel as a pickleable object """
        return self._mp_context
            
    @staticmethod
    def report( cid : str, queue : Queue, f_verbose : Context, verbose_interval : float ):
        """ Thread program to keep reporting messages until None is received """
        tme = f_verbose.timer()
        while True:
            r = queue.get()
            if r is None:
                break
            if isinstance(r, Exception):
                print(f"*** Messaging queue {cid} encountered an exception: {r}. Aborting.")
                raise r
            msg, flush = r
            if tme.interval_test(verbose_interval):
                f_verbose._raw(msg,end='',flush=flush)

    def __enter__(self):
        return self.mp_context

    def __exit__(self, *kargs, **kwargs):
        return False#raise exceptions

class _DIF(object):
    """ _DictIterator 'F' """
    def __init__(self, k : str, f : Callable, merge_tuple : bool ) -> None:
        self._f = f
        self._k = k
        self._merge_tuple = merge_tuple
    def __call__(self, *args, **kwargs):
        r = self._f(*args, **kwargs)
        if not self._merge_tuple or not isinstance(r, tuple):
            return (self._k, r)
        return ((self._k,) + r)

class _DictIterator(object):
    """ Dictionary iterator """
    def __init__(self, jobs : Mapping, merge_tuple : bool) -> None:
        self._jobs = jobs
        self._merge_tuple = merge_tuple
    def __iter__(self):
        for k, v in self._jobs.items():
            f, args, kwargs = v
            yield _DIF(k,f, self._merge_tuple), args, kwargs
    def __len__(self):#don't really need that but good to have
        return len(self._jobs)
           
class _NoPool(object):
    def __init__(self) -> None:
        self._jobs = None
    def __call__(self, jobs):
        for func, args, kargs in jobs:
            yield func(*args,**kargs)
    
def _parallel(pool : joblib_Parallel|_NoPool, jobs : Iterable) -> Iterable:
    """
    Process 'jobs' in parallel using the current multiprocessing pool.
    All (function) values of 'jobs' must be generated using self.delayed.
    See help(JCPool) for usage patterns.
    
    Parameters
    ----------
        jobs:
            can be a sequence, a generator, or a dictionary.
            Each function value must have been generated using JCPool.delayed()
            
    Returns
    -------
        An iterator which yields results as soon as they are available.   
        If 'jobs' is a dictionary, then the resulting iterator will generate tuples with the first
        element equal to the dictionary key of the respective function job.
    """
    jobs = jobs if not isinstance(jobs, Mapping) else _DictIterator(jobs,merge_tuple=True)
    return pool( jobs )

def _parallel_to_dict(pool : joblib_Parallel|_NoPool, jobs : Mapping) -> Mapping:
    """
    Process 'jobs' in parallel using the current multiprocessing pool.
    All values of the dictionary 'jobs' must be generated using self.delayed.
    This function awaits the calculation of all elements of 'jobs' and
    returns a dictionary with the results.
    
    See help(JCPool) for usage patterns.

    Parameters
    ----------
        jobs:
            A dictionary where all (function) values must have been generated using JCPool.delayed.
            
    Returns
    -------
        A dictionary with results.
        If 'jobs' is an OrderedDict, then this function will return an OrderedDict
        with the same order as 'jobs'.
    """
    assert isinstance(jobs, Mapping), ("'jobs' must be a Mapping.", type(jobs))
    r = dict( pool( _DictIterator(jobs,merge_tuple=False) ) )
    if isinstance( jobs, OrderedDict ):
        q = OrderedDict()
        for k in jobs:
            q[k] = r[k]
        r = q
    return r
            
def _parallel_to_list(pool : joblib_Parallel|_NoPool, jobs : Sequence ) -> Sequence:
    """
    Call parallel() and convert the resulting generator into a list.

    Parameters
    ----------
        jobs:
            can be a sequence, a generator, or a dictionary.
            Each function value must have been generated using JCPool.delayed()
            
    Returns
    -------
        An list with the results in order of the input.
    """
    assert not isinstance( jobs, Mapping ), ("'jobs' is a Mapping. Use parallel_to_dict() instead.", type(jobs))
    lst = { i: j for i, j in enumerate(jobs) }
    r   = _parallel_to_dict( pool, lst )
    return list( r[i] for i in lst ) 

class JCPool( object ):
    r"""
    Parallel Job Context Pool.
    
    Simple wrapper around `joblib.Parallel() <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__ 
    which allows worker processes to use :class:`cdxcore.verbose.Context` to report
    progress updates. For this purpose, :class:`cdxcore.verbose.Context` 
    will send output messages via a :class:`multiprocessing.Queue`
    to the main process
    where a separate thread prints these messages out.
    
    Using a fixed central pool object in  your code base
    avoids relaunching processes.

    Functions passed to :meth:`cdxcore.jcpool.JCPool.parallel` and related functions must
    be decorated with :dec:`cdxcore.jcpool.JCPool.delayed`.

    **List/Generator Usage**

    The following code is a standard prototype for using :func:`cdxcore.jcpool.JCPool.parallel`
    following closely the `joblib paradigm <https://joblib.readthedocs.io/en/latest/parallel.html>`__:

    .. code-block:: python

        from cdxcore.verbose import Context
        from cdxcore.jcpool import JCPool
        import time as time 
        import numpy as np

        pool    = JCPool( num_workers=4 )   # global pool. Reuse where possible
        
        def f( ticker, tdata, verbose : Context ):
            # some made up function
            q  = np.quantile( tdata, 0.35, axis=0 )
            tx = q[0]
            ty = q[1]
            time.sleep(0.5)
            verbose.write(f"Result for {ticker}: {tx:.2f}, {ty:.2f}")
            return tx, ty
        
        tickerdata =\
         { 'SPY': np.random.normal(size=(1000,2)),
           'GLD': np.random.normal(size=(1000,2)), 
           'BTC': np.random.normal(size=(1000,2))
         } 
        
        verbose = Context("all")
        with verbose.write_t("Launching analysis") as tme:
            with pool.context( verbose ) as verbose:
                for tx, ty in pool.parallel(
                            pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose(2) )
                            for ticker, tdata in tickerdata.items() ):
                    verbose.report(1,lambda : f"Returned {tx:.2f}, {ty:.2f}")
        verbose.write(lambda : f"Analysis done; this took {tme}.")
    
    The output from this code is asynchronous:

    .. code-block:: python

        00: Launching analysis
        02:     Result for SPY: -0.43, -0.39
        01:   Returned -0.43, -0.39
        02:     Result for BTC: -0.39, -0.45
        01:   Returned -0.39, -0.45
        02:     Result for GLD: -0.41, -0.43
        01:   Returned -0.41, -0.43
        00: Analysis done; this took 0.73s.        

    **Dict**

    Considering the asynchronous nature of the returned data it is often desirable
    to keep track of results by some identifier. In above example ``ticker``
    was not available in the main loop.
    This pattern is automated with the dictionary usage pattern:
    
    .. code-block:: python
       :emphasize-lines: 26,27,28,29

        from cdxcore.verbose import Context
        from cdxcore.jcpool import JCPool
        import time as time 
        import numpy as np

        pool    = JCPool( num_workers=4 )   # global pool. Reuse where possible
        
        def f( ticker, tdata, verbose : Context ):
            # some made up function
            q  = np.quantile( tdata, 0.35, axis=0 )
            tx = q[0]
            ty = q[1]
            time.sleep(0.5)
            verbose.write(f"Result for {ticker}: {tx:.2f}, {ty:.2f}")
            return tx, ty
        
        tickerdata =\
         { 'SPY': np.random.normal(size=(1000,2)),
           'GLD': np.random.normal(size=(1000,2)), 
           'BTC': np.random.normal(size=(1000,2))
         } 
        
        verbose = Context("all")
        with verbose.write_t("Launching analysis") as tme:
            with pool.context( verbose ) as verbose:
                for ticker, tx, ty in pool.parallel(
                        { ticker: pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose(2) )
                          for ticker, tdata in tickerdata.items() } ):
            verbose.report(1,f"Returned {ticker} {tx:.2f}, {ty:.2f}")
        verbose.write(f"Analysis done; this took {tme}.")
    
    This generates the following output::

        00: Launching analysis
        02:     Result for SPY: -0.34, -0.41
        01:   Returned SPY -0.34, -0.41
        02:     Result for GLD: -0.38, -0.41
        01:   Returned GLD -0.38, -0.41
        02:     Result for BTC: -0.34, -0.32
        01:   Returned BTC -0.34, -0.32
        00: Analysis done; this took 5s.
    
    Note that :func:`cdxcore.jcpool.JCPool.parallel` when applied to a dictionary does not return a dictionary,
    but a sequence of tuples.
    As in the example this also works if the function being called returns tuples itself; in this case the returned data
    is extended by the key of the dictionary provided.
    
    In order to retrieve a dictionary use :func:`cdxcore.jcpool.JCPool.parallel_to_dict`::

        verbose = Context("all")
        with pool.context( verbose ) as verbose:
            r = pool.parallel_to_dict( { ticker: pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose )
                                         for ticker, tdata in self.data.items() } )

    Note that in this case the function returns only after all jobs have been processed.
    
    ** Loky Memory Leak Detection **
    
    ``JCPool`` uses the `loky <https://loky.readthedocs.io/en/stable/index.html>'__ backend by default.
    Loky `tries to avoid memory leaks by monitoring the current processes' memory allocation 
    and kills the process if it thinks it accidentally allocates too much memory <https://loky.readthedocs.io/en/stable/API.html#protection-against-memory-leaks>`__.
                                                                                   
    This monitoring consists of two components:
    
    * After a first initial period (the first task, usually), Loky assess the initial memory used by the process using :mod:`psutil`.
    * Before each subsequent task, if a minimum time period has passed (a second by default) it:
      1. Checks whether the process allocated more than this number + 300MB by default.
      2. If that happens, Loky will call :func:`gc.collect` (a very expensive operation)
      3. Then check again perform above test. If this exceeds the initial number + 300MB it will kill the process.
      
    The github code is `here <https://github.com/joblib/loky/blob/master/loky/process_executor.py>`__.
       
    For most intensive machine learning tasks such as data pipeline processing this will lead to killing the process early on.
    By default, Loky is quiet about killing a process which it thinks leaks memory. The default implementation of ``JCPool``
    changes Loky's INFO to FATAL and reports it to ``stderr`` if this happens.
    This can be turned off by setting ``logging_level`` to ``None``.

    To manually check whether a Loky joblib process is killed due to a perceived memory leak, use::
            
        import multiprocessing.util as mp_util
        mp_util.log_to_stderr(level=mp_util.INFO)
        
    Check for ``"Memory leak detected: shutting down worker"`` and then ``"Exit due to memory leak"``.

    You can either modify this behaviour to a more moderate setting, or turn it off:
        
    * **Turn off**: set ``mem_leak_enforce`` to ``False`` to turn off memory checking.
      *However* in this case Loky will still regularly call :func:`gc.collect`, by default if a second or more has passed after the last task.
      You can change that delay by using ``mem_leak_timer``.
    * **Modify**: set the memory threshold to a bigger number than 300MB by using ``mem_leak_max_memory``; this can be a float representing the percentage
      of total physical memory. You can change the delay of checking vs the new threshold by using ``mem_leak_timer``.
    
    Parameters
    ----------
        num_workers : int, default ``1``
            
            The number of workers. If ``num_workers`` is ``1`` then no parallel process or thread is started
            per default `joblib <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__ functionality.
            
            Just as for `joblib <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__ you can
            use a negative ``num_workers`` to set the number of workers to the ``number of CPUs + num_workers + 1``.
            For example, a ``num_workers`` of ``-2`` will use as many jobs as CPUs are present less one.
            If ``num_workers`` is negative, the effective number of workers will be at least ``1``.
            
            For debugging can set the number of workers to zero to bypass ``joblib`` entirely.
            
            Default is ``1``.
        
        threading : bool, default ``False``
        
            If ``False``, the default, then the pool will act as a ``"loky"`` multi-process pool with the associated overhead
            of managing data across processes.
            
            If ``True``, then the pool is a ``"threading"`` pool. This helps for functions whose code releases
            Python's `global interpreter lock <https://wiki.python.org/moin/GlobalInterpreterLock>`__, for example
            when engaged in heavy I/O or compiled code such as :mod:`numpy`., :mod:`pandas`,
            or generated with `numba <https://numba.pydata.org/>`__.
            
        tmp_root_dir : str | SubDir, default ``"!/.cdxmp"``
        
            Temporary directory for memory mapping large arrays. This is a root directory; the function
            will create a temporary sub-directory with a name generated from the current state of the system.
            This sub-directory will be deleted upon destruction of ``JCPool`` or when :meth:`cdxcore.jcpool.JCPool.terminate`
            is called. This function uses :class:`cdxcore.subdir.SubDir` and therefore supports for example
            root directories ``!/`` (local temporary directory), ``?/`` (a temporary directory root), and ``~/`` as
            the home directory.
            
            This parameter can also be ``None`` in which case the `default behaviour <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__
            of :class:`joblib.Parallel` is used.
            
            Default is ``"?/.cdxmp"`` which creates a temporary temp directory using, :func:`tempfile.gettempdir`, and places
            a subdirectory ``".cdxmp"`` inside it.
            
        mem_leak_enforce : bool | None, default is ``None`` which uses :attr:`cdxcore.jcpool.JCPool.DEFAULT_MEM_LEAK_ENFORCE`
        
            This parameter controls whether Loky is allowed to detect memory leaks when multi-processing is used. 
            See the section on "Loky Memory Leak Detection" above for background.

            You can set the static variable :attr:`cdxcore.jcpool.JCPool.DEFAULT_MEM_LEAK_ENFORCE` to change the default value of this parameter
            process-wide.

            This parameter has no effect if ``threading`` is ``True``.
            
        mem_leak_max_memory : int | float | None, default is ``None`` which uses :attr:`cdxcore.jcpool.JCPool.DEFAULT_MEM_LEAK_MAX_MEMORY`
        
            This parameter sets the memory threshold after which Loky assumes a process leaks memory and kills it. 
            See the section on "Loky Memory Leak Detection" above for background.

            * If ``mem_leak_max_memory`` is an ``int`` it specifies the amount of memory in bytes a process may allocate before it is killed. It must be above :attr:`cdxcore.jcpool.JCPool.MIN_MAX_MEMORY`.
            * If ````mem_leak_max_memory`` is a ``float`` it specifies the amount of memory a process may allocate as percentage of total available physical memory.
              This will be floored by attr:`cdxcore.jcpool.JCPool.MIN_MAX_MEMORY`.
            
            The default :attr:`cdxcore.jcpool.JCPool.DEFAULT_MEM_LEAK_MAX_MEMORY` is typically 300MB.

            This parameter has no effect if ``threading`` is ``True``.
            
        mem_leak_timer : float | None, default is ``None`` which uses :attr:`cdxcore.jcpool.JCPool.DEFAULT_MEM_LEAK_TIMER`
        
            This parameter controls how many seconds Loky waits before detecting memory leaks (if ``mem_leak_enforce`` is ``True``) or how
            often it calls :func:`gc.collect` (if ``mem_leak_enforce`` is ``False``). 
            See the section on "Loky Memory Leak Detection" above for background.
            
            The default, :attr:`cdxcore.jcpool.JCPool.DEFAULT_MEM_LEAK_TIMER` is one second.

            This parameter has no effect if ``threading`` is ``True``.
            
        logging_level : int | None, default :attr:logging.ERROR
        
            Sets the global level for :mod:`multiprocessing` upon which to print log messages to ``stderr``.
            Essentially, if not ``None``, then :func:`multiprocessing.util.log_to_stderr` is called.
            
        verbose : :class:`cdxcore.verbose.Context`, default :attr:`cdxcore.verbose.Context.quiet`
            
            A :class:`cdxcore.verbose.Context` object used to print out multi-processing/threading information.
            This is *not* the ``Context`` provided to child processes/threads.
            
            Default is ``quiet``, a context which does not print anything.

        parallel_kwargs : dict, default empty
        
            Additional keywords for :class:`joblib.Parallel`.
    
    """
    
    DEFAULT_MEM_LEAK_ENFORCE    = True  #: Default for whether to enforce memory leak detection in Loky, which is on by default.
    DEFAULT_MEM_LEAK_MAX_MEMORY = joblib.externals.loky.process_executor._MAX_MEMORY_LEAK_SIZE     #: Default Loky memory leak size, usually 300MB
    DEFAULT_MEM_LEAK_TIMER      = joblib.externals.loky.process_executor._MEMORY_LEAK_CHECK_DELAY  #: Default loky memory leak and :func:`gc.collect` timer in seconds, usually 1.#
    MIN_MAX_MEMORY              = 10_000_000  #: lower bound for memory leak detection per process. See discussion on "Loky Memory Leak Detection" above.
        
    def __init__(self, num_workers          : int = 1,
                       threading            : bool = False,
                       tmp_root_dir         : str|SubDir|None = "!/.cdxmp", *,
                       mem_leak_enforce     : bool|None = None,
                       mem_leak_max_memory  : int|float|None = None,
                       mem_leak_timer       : float|None = None,
                       logging_level        : int|None = logging.ERROR,
                       verbose              : Context = Context.quiet,
                       parallel_kwargs      : dict = {} ) -> None:
        """
        Initialize a multi-processing pool. Thin wrapper around joblib.parallel for cdxcore.verbose.Context() output
        """
        mem_leak_enforce       = mem_leak_enforce if not mem_leak_enforce is None else JCPool.DEFAULT_MEM_LEAK_ENFORCE
        mem_leak_max_memory    = mem_leak_max_memory if not mem_leak_max_memory is None else JCPool.DEFAULT_MEM_LEAK_MAX_MEMORY
        mem_leak_timer         = mem_leak_timer if not mem_leak_timer is None else JCPool.DEFAULT_MEM_LEAK_TIMER
    

        self.__state = dict(
            num_workers = num_workers,
            threading = threading,
            tmp_root_dir =tmp_root_dir,
            mem_leak_enforce = mem_leak_enforce,
            mem_leak_max_memory = mem_leak_max_memory,
            mem_leak_timer = mem_leak_timer,
            logging_level = logging_level,
            verbose = verbose,
            parallel_kwargs = dict(parallel_kwargs)
        )

        tmp_dir_ext                = unique_hash8( uuid.getnode(), os.getpid(), get_thread_id(), datetime.datetime.now() )
        self._num_workers          = int(num_workers)
        tmp_root_dir : SubDir|None = SubDir(tmp_root_dir) if not tmp_root_dir is None else None
        self._tmp_dir              = tmp_root_dir(tmp_dir_ext, ext='', create_directory=False) if not tmp_root_dir is None else None
        self._verbose              = verbose if not verbose is None else Context("quiet")
        self._threading            = threading
        self._no_pool              = self._num_workers == 0
        self._pool                 = None # for error message handling
        del num_workers
        
        if isinstance(mem_leak_max_memory, float):
            verify_inp( 0. < mem_leak_max_memory < 1., lambda : f"If 'mem_leak_max_memory' is a float it must be strictly between 0 and 1; found {mem_leak_max_memory:.4g}")
            mem_leak_max_memory = max( self.MIN_MAX_MEMORY, math.ceil( psutil.virtual_memory().total * mem_leak_max_memory ) )
        else:
            verify_inp( isinstance(mem_leak_max_memory, int), lambda : f"'mem_leak_max_memory' must be an integer or a float; found {type(mem_leak_max_memory)}")
            verify_inp( mem_leak_max_memory >= self.MIN_MAX_MEMORY, lambda : f"If 'mem_leak_max_memory' is an integer it must be positive and above {fmt_digits(self.MIN_MAX_MEMORY)}. Found {fmt_digits(mem_leak_max_memory)}")
            
        self._mem_leak_enforce     = mem_leak_enforce
        self._mem_leak_max_memory  = mem_leak_max_memory
        self._mem_leak_timer       = float(mem_leak_timer)
        self._logging_level        = logging_level

        logger = mp.util.log_to_stderr(level=logging_level) if not logging_level is None else mp.util.getLogger()
        logger.addFilter(_PromoteMemoryLeakToFatal())
            
        if self._num_workers < 0:
            self._num_workers = max( self.cpu_count() + self._num_workers + 1, 1 )
        
        path_info = f" with temporary directory '{self.tmp_path}'" if not self.tmp_path is None else ''
        if self._num_workers!=0:
            with self._verbose.write_t(f"Launching {self._num_workers} processes{path_info}... ", end='') as tme:
                self._pool = joblib_Parallel( n_jobs=self._num_workers, 
                                              backend="loky" if not self._threading else "threading", 
                                              return_as="generator_unordered", 
                                              temp_folder=self.tmp_path,
                                              **parallel_kwargs)
                self._verbose.write(f"done; this took {tme}.", head=False)
        else:
            self._pool = _NoPool()
            self._verbose.write("Note: not using any pooling.")

    def __del__(self):
        self.terminate()

    @property
    def tmp_path(self) -> str|None:
        """ Path to the temporary directory for this object. """
        return self._tmp_dir.path if not self._tmp_dir is None else None
    @property
    def is_threading(self) -> bool:
        """ Whether we are threading or multi-processing. """
        return self._threading

    @property
    def threading(self) -> bool:
        """ Whether we are threading or multi-processing. """
        return self._threading
    @property
    def num_workers(self) -> int:
        """ Actual number of worker processes or threads. """
        return self._num_workers
    @property
    def is_no_pool(self) -> bool:
        """ Whether this is an actual pool or not (i.e. the pool was constructed with zero workers) """
        return self._no_pool
    @property
    def mem_leak_max_memory(self) -> int|None:
        """ returns the effective ``mem_leak_max_memory`` used by the pool as integer, or ``None`` if not used. """
        return self._mem_leak_max_memory if self._mem_leak_enforce else None
    
    @staticmethod
    def cpu_count( only_physical_cores : bool = False ) -> int:
        """
        Return the number of physical CPUs.
        
        Parameters
        ----------
            only_physical_cores : boolean, optional
            
                If ``True``, does not take hyperthreading / SMT logical cores into account.
                Default is ``False``.
        
        Returns
        -------
            cpus : int
                Count
        """
        return cpu_count(only_physical_cores=only_physical_cores)

    def terminate(self):
        """
        Stop the current parallel pool, and delete any temporary files (if managed by ``JCPool``).
        """
        if not self._pool is None:
            tme = Timer()
            del self._pool
            self._pool = None
            self._verbose.write(f"Shut down parallel pool. This took {tme}.")
        gc.collect()
        if not self._tmp_dir is None:
            dir_name = self._tmp_dir.path
            self._tmp_dir.delete_everything(keep_directory=False)
            self._verbose.write(f"Deleted temporary directory {dir_name}.")

    def context( self, verbose : Context, verbose_interval : float = None ):
        """
        Parallel processing ``Context`` object.
        
        This function returns a :class:`cdxcore.verbose.Context` object whose ``channel`` is a queue towards a utility thread
        which will output all messages to ``verbose``.
        As a result a worker process is able to use ``verbose`` as if it were in-process
        
        A standard usage pattern is:
            
        .. code-block:: python
            :emphasize-lines: 13, 14

            from cdxcore.verbose import Context
            from cdxcore.jcpool import JCPool
            import time as time 
            import numpy as np
    
            pool    = JCPool( num_workers=4 )   # global pool. Reuse where possible
            
            def f( x, verbose : Context ):
                verbose.write(f"Found {x}")     # <- text "Found 1" etc will be sent
                return x                        #    to main thread via Queue 
             
            verbose = Context("all")
            with pool.context( verbose ) as verbose:
                for x in pool.parallel( pool.delayed(f)( x=x, verbose=verbose(1) ) for x in [1,2,3,4] ):
                    verbose.write(f"Returned {x}")                    
        
        See :class:`cdxcore.jcpool.JCPool` for more usage patterns.
        """
        if self._threading:
            return verbose
        return _ParallelContextOperator( pool_verbose=self._verbose, 
                                         f_verbose=verbose,
                                         verbose_interval=verbose_interval )

    @staticmethod
    def _validate( F : Callable, args : list, kwargs : Mapping ):
        """ Check that ``args`` and ``kwargs`` do not contain ``Context`` objects without channel """
        for k, v in enumerate(args):
            if isinstance(v, Context) and not isinstance(v.channel, ParallelContextChannel):
                raise RuntimeError(f"Argument #{k} for {F.__qualname__} is a Context object, but its channel is not set to 'ParallelContextChannel'. Use JPool.context().")
        for k, v in kwargs.items():
            if isinstance(v, Context) and not isinstance(v.channel, ParallelContextChannel):
                raise RuntimeError(f"Keyword argument '{k}' for {F.__qualname__} is a Context object, but its channel is not set to 'ParallelContextChannel'. Use JPool.context().")

    def delayed(self, F : Callable ):
        """
        Decorate a function for parallel execution.
        
        This decorator adds minor syntactical sugar on top of :func:`joblib.delayed`
        (which in turn is discussed `here <https://joblib.readthedocs.io/en/latest/parallel.html#parallel>`__).

        When called, this decorator checks that no :class:`cdxcore.verbose.Context`
        arguments are passed to the pooled function which have no ``ParallelContextChannel`` present. In other words,
        the function detects if the user forgot to use :meth:`cdxcore.jcpool.JCPool.context`.
        
        Parameters
        ----------
            F : Callable
                Function.
            
        Returns
        -------
            wrapped F : Callable
                Decorated function.
        """
        if self._threading or self._no_pool:
            return _jl_delayed(F)

        def delayed_function( *args, **kwargs ):
            JCPool._validate( F, args, kwargs )
            kwargs_Process = dict( mem_leak_enforce=self._mem_leak_enforce,
                                   mem_leak_max_memory=self._mem_leak_max_memory,
                                   mem_leak_timer=self._mem_leak_timer,
                                   logging_level=self._logging_level,
                                   F=F,
                                   F_args=args, 
                                   F_kwargs=kwargs
                                   )
            return _ProcessF, [], kwargs_Process # mimic joblib.delayed()
        try:
            delayed_function = functools.wraps(F)(delayed_function)
        except AttributeError:
            " functools.wraps fails on some callable objects "
        return delayed_function

    def parallel(self, jobs : Iterable|Sequence|Mapping) -> Iterable:
        """
        Process a number of jobs in parallel using the current multiprocessing pool.
        This is equivalent to :meth:`cdxcore.jcpool.JCpool.__call__`.
        
        All functions used in ``jobs`` must have been decorated using :dec:`cdxcore.jcpool.JCPool.delayed`.
        
        This function returns an iterator which yields results as soon as they 
        are computed.
        
        If ``jobs`` is a ``Sequence`` you can also use
        :meth:`cdxcore.jcpool.JCPool.parallel_to_list` to retrieve
        a :class:`list` of all results upon completion of the last job. Similarly, if ``jobs`` 
        is a ``Mapping``, use :meth:`cdxcore.jcpool.JCPool.parallel_to_dict` to retrieve
        a :class:`dict` of results upon completion of the last job.
        
        Parameters
        ----------
            jobs :  Iterable | Sequence | Mapping
                A sequence, iterator or mapping of ``Callable`` functions.

                Each ``Callable`` used as part of either must
                have been decorated with :dec:`cdxcore.jcpool.JCPool.delayed`.
                
        Returns
        -------
            parallel : Iterator
                An iterator which yields results as soon as they are available.   
                If ``jobs`` is a :class:`Mapping`, then the resulting iterator will generate tuples with the first
                element equal to the mapping key of the respective function job. This function will *not*
                return a dictionary. See the example described in :mod:`cdxcore.jcpool` in section "Dict".
        """
        return _parallel( self._pool, jobs )
    
    def __call__(self, jobs : Iterable|Sequence|Mapping) -> Iterable:
        """
        Process a number of jobs in parallel using the current multiprocessing pool.
        This is equivalent to :meth:`cdxcore.jcpool.JCpool.parallel`.
        
        All functions used in ``jobs`` must have been decorated using :dec:`cdxcore.jcpool.JCPool.delayed`.
        
        This function returns an iterator which yields results as soon as they 
        are computed.
        
        If ``jobs`` is a ``Sequence`` you can also use
        :meth:`cdxcore.jcpool.JCPool.parallel_to_list` to retrieve
        a :class:`list` of all results upon completion of the last job. Similarly, if ``jobs`` 
        is a ``Mapping``, use :meth:`cdxcore.jcpool.JCPool.parallel_to_dict` to retrieve
        a :class:`dict` of results upon completion of the last job.
        
        Parameters
        ----------
            jobs :  Iterable | Sequence | Mapping
                A sequence, iterator or mapping of ``Callable`` functions.

                Each ``Callable`` used as part of either must
                have been decorated with :dec:`cdxcore.jcpool.JCPool.delayed`.
                
        Returns
        -------
            parallel : Iterator
                An iterator which yields results as soon as they are available.   
                If ``jobs`` is a :class:`Mapping`, then the resulting iterator will generate tuples with the first
                element equal to the mapping key of the respective function job. This function will *not*
                return a dictionary. See the example described in :mod:`cdxcore.jcpool` in section "Dict".
        """
        return _parallel( self._pool, jobs )
    
    def parallel_to_dict(self, jobs : Mapping) -> dict:
        """
        Process a number of jobs in parallel using the current multiprocessing pool,
        and return all results in a dictionary upon completion.
        
        This function awaits the calculation of all elements of ``jobs`` and
        returns a :class:`dict` with the results.
        
        Parameters
        ----------
            jobs : Mapping
                A dictionary where all (function) values must have been decorated
                with :dec:`cdxcore.jcpool.JCPool.delayed`.
                
        Returns
        -------
            Results : dict
                A dictionary with results.
                
                If ``jobs`` is an :class:`OrderedDict`, then this function will return an :class:`OrderedDict`
                with the same order as ``jobs``. Otherwise the elements of the ``dict`` returned
                by this function are in completion order.
        """
        return _parallel_to_dict( self._pool, jobs )
                
    def parallel_to_list(self, jobs : Iterable|Sequence ) -> Sequence:
        """
        Process a number of jobs in parallel using the current multiprocessing pool,
        and return all results in a list upon completion.
        
        This function awaits the calculation of all elements of ``jobs`` and
        returns a :class:`list` with the results.
        
        Parameters
        ----------
            jobs : Iterable | Sequence 
                An sequence or iterable of ``Callable`` functions, each of which 
                must have been decorated
                with :dec:`cdxcore.jcpool.JCPool.delayed`.
                
        Returns
        -------
            Results : list
                A list with results, in the order of ``jobs``.
        """
        return _parallel_to_list( self._pool, jobs )

    # ------------------------------------------------------------
    # Serialization - serialize the arguments, do not serialize
    # the pool itself.
    # ------------------------------------------------------------

    @staticmethod
    def _reconstruct_from_state( state : dict ) -> JCPool:
        return JCPool(**state)

    def __reduce__(self) -> tuple:
        return ( JCPool._reconstruct_from_state, (self.__state,) )

class JCPoolConfig(object):
    """
    Pool configuation object.
    
    This object's :meth:`pool` method returns a singleton :class:`JCPool` object for this configuration.
    This allows you to use the same pool across your code base without having to pass around the pool object itself, e.g.::

        def f( x, pool_config : JCPoolConfig ):
            pool = pool_config.pool() # get the pool for this configuration
            for y in pool.parallel( pool.delayed(g)(x=x) for x in [1,2,3] ):
                print(y)

        def g( x, pool_config : JCPoolConfig ):
            ...
            f( x, pool_config=pool_config ) # pass the same pool configuration to f() and g()
            ...
            pool = pool_config.pool() # get the same pool for this configuration

    """
    def __init__(self, num_workers : int = 4, threading : bool = False ):
        self.num_workers: int         = num_workers  # Number of worker processes or threads. If zero, no pool is used.
        self.threading:   bool        = threading    # Whether to use threading or multiprocessing. This is only used if the respective code base is supporting this.
        self._pool:       JCPool|None = None

    def __str__(self):
        """ Minimal string representation of the pool configuration. """
        return f"{self.num_workers}{'t' if self.threading else 'p'}"
    
    @staticmethod
    def off():
        """ Pool configuration for no parallel processing. """
        return JCPoolConfig(num_workers=0, threading=True)
    
    def pool(self, **kwargs) -> JCPool:
        """ Get the pool for this configuration. This is a singleton in a given process. """
        if self._pool is None:
            self._pool = JCPool( num_workers=self.num_workers, threading=self.threading, **kwargs )
        return self._pool



