"""
Overview
--------

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

from joblib import Parallel as joblib_Parallel, delayed as _jl_delayed, cpu_count
from multiprocessing import Manager, Queue
from threading import Thread, get_ident as get_thread_id
import gc as gc
from collections import OrderedDict
from collections.abc import Mapping, Callable, Sequence, Iterable
import functools as functools
import uuid as uuid
import os as os
import datetime as datetime

from .verbose import Context, Timer
from .subdir import SubDir
from .uniquehash import unique_hash8

class ParallelContextChannel( Context ):
    """
    Lightweight :class:`cdxcore.verbose.Context` ``channel`` which is pickle'able.

    This channel sends messages it receives to a :class:`multiprocessing.Queue`.
    """
    def __init__(self, *, cid, maintid, queue, f_verbose):
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
            self._f_verbose.write(msg, end='', flush=flush)
        else:
            return self._queue.put( (msg, flush) )

class _ParallelContextOperator( object ):
    """
    Queue-based channel backbone for _ParallelContextChannel
    This object cannot be pickled; use self.mp_context as object to pass to other processes.
    """
    def __init__(self, pool_verbose     : Context,      # context to print Pool progress to (in thread)
                       f_verbose        : Context,      # original function context (in thread)
                       verbose_interval : float = None  # throttling for reporting 
                ):
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
                f_verbose.write(msg, end='', flush=flush)

    def __enter__(self):
        return self.mp_context

    def __exit__(self, *kargs, **kwargs):
        #self.terminate()
        return False#raise exceptions

class _DIF(object):
    """ _DictIterator 'F' """
    def __init__(self, k : str, f : Callable, merge_tuple : bool ):
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
    def __init__(self, jobs : Mapping, merge_tuple : bool):
        self._jobs = jobs
        self._merge_tuple = merge_tuple
    def __iter__(self):
        for k, v in self._jobs.items():
            f, args, kwargs = v
            yield _DIF(k,f, self._merge_tuple), args, kwargs
    def __len__(self):#don't really need that but good to have
        return len(self._jobs)
            
def _parallel(pool, jobs : Iterable) -> Iterable:
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
        If 'jobs' is a dictionary, then the resutling iterator will generate tuples with the first
        element equal to the dictionary key of the respective function job.
    """
    if not isinstance(jobs, Mapping):
        return pool( jobs )
    return pool( _DictIterator(jobs,merge_tuple=True) )

def _parallel_to_dict(pool, jobs : Mapping) -> Mapping:
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
            
def _parallel_to_list(pool, jobs : Sequence ) -> Sequence:
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
    where a sepeate thread prints these messages out.
    
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
                    verbose.report(1,f"Returned {tx:.2f}, {ty:.2f}")
        verbose.write(f"Analysis done; this took {tme}.")
    
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
    
    Parameters
    ----------
        num_workers : int, optional
            
            The number of workers. If ``num_workers`` is ``1`` then no parallel process or thread is started.
            Just as for `joblib <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__ you can
            use a negative ``num_workers`` to set the number of workers to the ``number of CPUs + num_workers + 1``.
            For example, a ``num_workers`` of ``-2`` will use as many jobs as CPUs are present less one.
            If ``num_workers`` is negative, the effective number of workers will be at least ``1``.
            
            Default is ``1``.
        
        threading : bool, optional
        
            If ``False``, the default, then the pool will act as a ``"loky"`` multi-process pool with the associated overhead
            of managing data accross processes.
            
            If ``True``, then the pool is a ``"threading"`` pool. This helps for functions whose code releases
            Python's `global interpreter lock <https://wiki.python.org/moin/GlobalInterpreterLock>`__, for example
            when engaged in heavy I/O or compiled code such as :mod:`numpy`., :mod:`pandas`,
            or generated with `numba <https://numba.pydata.org/>`__.
            
        tmp_root_dir : str | SubDir, optional
        
            Temporary directory for memory mapping large arrays. This is a root directory; the function
            will create a temporary sub-directory with a name generated from the current state of the system.
            This sub-directory will be deleted upon destruction of ``JCPool`` or when :meth:`cdxcore.jcpool.JCPool.terminate`
            is called.
            
            This parameter can also be ``None`` in which case the `default behaviour <https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html>`__
            of :class:`joblib.Parallel` is used.
            
            Default is ``"!/.cdxmp"``.
            
        verbose : Context, optional
            
            A :class:`cdxcore.verbose.Context` object used to print out multi-processing/threading information.
            This is *not* the ``Context`` provided to child processes/threads.
            
            Default is ``quiet``.

        parallel_kwargs : dict, optional
        
            Additional keywords for :class:`joblib.Parallel`.
    
    """
    def __init__(self, num_workers      : int = 1,
                       threading        : bool = False,
                       tmp_root_dir     : str|SubDir= "!/.cdxmp",  *,
                       verbose          : Context = Context.quiet,
                       parallel_kwargs  : dict = {} ):
        """
        Initialize a multi-processing pool. Thin wrapper aroud joblib.parallel for cdxcore.verbose.Context() output
        """
        tmp_dir_ext            = unique_hash8( uuid.getnode(), os.getpid(), get_thread_id(), datetime.datetime.now() )
        num_workers            = int(num_workers)
        tmp_root_dir           = SubDir(tmp_root_dir) if not tmp_root_dir is None else None
        self._tmp_dir          = tmp_root_dir(tmp_dir_ext, ext='') if not tmp_root_dir is None else None
        self._verbose          = verbose if not verbose is None else Context("quiet")
        self._threading        = threading

        if num_workers < 0:
            num_workers = max( self.cpu_count() + num_workers + 1, 1 )
        
        path_info = f" with temporary directory '{self.tmp_path}'" if not self.tmp_path is None else ''
        with self._verbose.write_t(f"Launching {num_workers} processes{path_info}... ", end='') as tme:
            self._pool = joblib_Parallel( n_jobs=num_workers, 
                                          backend="loky" if not threading else "threading", 
                                          return_as="generator_unordered", 
                                          temp_folder=self.tmp_path,
                                          **parallel_kwargs)
            self._verbose.write(f"done; this took {tme}.", head=False)

    def __del__(self):
        self.terminate()

    @property
    def tmp_path(self) -> str|None:
        """ Path to the temporary directory for this object. """
        return self._tmp_dir.path if not self._tmp_dir is None else None
    @property
    def is_threading(self) -> bool:
        """ Whether we are threading or mulit-processing. """
        return self._threading
    
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
            self._verbose.write(f"Deleted temporary directoru {dir_name}.")

    def context( self, verbose : Context, verbose_interval : float = None ):
        """
        Parallel processing ``Context`` object.
        
        This function returns a :class:`cdxcore.verbose.Context` object whose ``channel`` is a queue towards a utility thread
        which will outout all messages to ``verbose``.
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

    def delayed(self, F : Callable):
        """
        Decorate a function for parallel execution.
        
        This decorate adds minor synthatical sugar on top of :func:`joblib.delayed`
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
        if self._threading:
            return _jl_delayed(F)
        def delayed_function( *args, **kwargs ):
            JCPool._validate( F, args, kwargs )
            return F, args, kwargs # mimic joblin.delayed()
        try:
            delayed_function = functools.wraps(F)(delayed_function)
        except AttributeError:
            " functools.wraps fails on some callable objects "
        return delayed_function

    def parallel(self, jobs : Sequence|Mapping) -> Iterable:
        """
        Process a number of jobs in parallel using the current multiprocessing pool.
        
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
            jobs :  Sequence | Mapping
                Can be a :class:`Sequence` containing ``Callable`` functions,
                or a :class:`Mapping` whose values are ``Callable`` functions.

                Each ``Callable`` used as part of either must
                have been decorated with :dec:`cdxcore.jcpool.JCPool.delayed`.
                
        Returns
        -------
            parallel : Iterator
                An iterator which yields results as soon as they are available.   
                If ``jobs`` is a :class:`Mapping`, then the resutling iterator will generate tuples with the first
                element equal to the mapping key of the respective function job. This function will *not*
                return a dictionary.
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
                
    def parallel_to_list(self, jobs : Sequence ) -> Sequence:
        """
        Process a number of jobs in parallel using the current multiprocessing pool,
        and return all results in a list upon completion.
        
        This function awaits the calculation of all elements of ``jobs`` and
        returns a :class:`list` with the results.
        
        Parameters
        ----------
            jobs : Sequence 
                An sequence of ``Callable`` functions, each of which 
                must have been decorated
                with :dec:`cdxcore.jcpool.JCPool.delayed`.
                
        Returns
        -------
            Results : list
                A list with results, in the order of ``jobs``.
        """
        return _parallel_to_list( self._pool, jobs )

