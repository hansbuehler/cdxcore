r"""
This module contains the :class:`cdxcore.verbose.Context` manager class
which supports printing hierarchical verbose progress reports.

Overview
--------

The key point of this class is to implement an easy-to-use method to print indented progress which
can also be turned off easily without
untidy code constructs such as excessive ``if`` blocks. In this case, we also avoid formatting
any strings.

Here is an example::

    from cdxcore.verbose import Context

    def f_sub( num=3, context = Context.quiet ):
            context.write("Entering loop")
            for i in range(num):
                context.report(1, "Number %ld", i)
    
    def f_main( context = Context.quiet ):
        context.write( "First step" )
        # ... do something
        context.report( 1, "Intermediate step 1" )
        context.report( 1, "Intermediate step 2\\n with newlines" )
        # ... do something
        f_sub( context=context(2) ) # call function f_sub with a sub-context
        # ... do something
        context.write( "Final step" )
        
    print("Verbose=1")
    context = Context(1)
    f_main(context)

    print("\\nVerbose=2")
    context = Context(2)
    f_main(context)

    print("\\nVerbose='all'")
    context = Context('all')
    f_main(context)

    print("\\nVerbose='quiet'")
    context = Context('quiet')
    f_main(context)
    
    print("\\ndone")

Returns::

    Verbose=1
    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:    with newlines
    00: Final step
    
    Verbose=2
    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:    with newlines
    02:     Entering loop
    00: Final step
    
    Verbose='all'
    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:    with newlines
    02:     Entering loop
    03:       Number 0
    03:       Number 1
    03:       Number 2
    00: Final step
    
    Verbose='quiet'
    
    done

Workflow
^^^^^^^^

The basic idea is that the root context has level 0, with increasing levels for sub-contexts.
When printing information, we can limit printing up to a given level and
automatically indent the output to reflect the current level of detail.

Workflow:

* Create a :class:`cdxcore.verbose.Context` model, and define its verbosity in its constructor, e.g.
  by specifying ``"all"``, ``"quiet"``, or a number.
* To write a text at current level to ``stdout`` use :meth:`cdxcore.verbose.Context.write`.
* To write a text at an indented sub-level use :meth:`cdxcore.verbose.Context.report`.
* To create a sub-context (indentation), use :meth:`cdxcore.verbose.Context.__call__`.

Lazy Formatting
^^^^^^^^^^^^^^^

:class:`cdxcore.verbose.Context` message formattting is meant to be lazy and only executed
if a message is actually written. This means that if the ``Contex`` is ``"quiet"`` no string
formatting takes place.

Consider a naive example::
    
    from cdxcore.verbose import Context
    import numpy as np
    
    def f( data : np.ndarray, verbose : Context = Context.quiet ):
        verbose.write(f"'f' called; data has mean {np.mean(data)} and variance {np.var(data)}")
        # ...
    f( verbose = Context.quiet )

In this case ``f`` will compute ``np.mean(data)`` and ``np.var(data)`` even though the use of the ``quiet``
``Context`` means that the formatted
string will not be printed. 

To alleviate this, :meth:`cdxcore.verbose.Context.write` supports a number of alternatives
which are leveraging :func:`cdxcore.err.fmt`. In above example, the most efficient use case
is the use of a ``lambda`` function::

    def f( data : np.ndarray,  verbose : Context ):
        verbose.write(lambda : f"'f' called; data has mean {np.mean(data)} and variance {np.var(data)}")
    
The ``lambda`` function is only called when the message is about to be printed.
    
Providing Updates
^^^^^^^^^^^^^^^^^

In many applications we wish to provide progress updates in a single line, and not clutter the output.
In the example from the beginng, the long lists of output are not informative.

:class:`cdxcore.verbose.Context` supports the use of "\\r" and "\\n for simple output formatting.
Under the hood it uses :class:`cdxcore.crman.CRMan`.

Consider the following change to ``f_sub`` in above code example:

.. code-block:: python
   :emphasize-lines: 4,5

    def f_sub( num=3, context = Context.quiet ):
        context.write("Entering loop")
        for i in range(num):
            context.report(1, ":emphasis:`\\r`Number %ld", i, end='')   # Notice use of \\r and end=''
        context.write("\\rLoop done")                       # Notice use of \\r `

    context = Context('all')
    f_main(context)

During execution this prints, for example at step ``i==1``::

    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:    with newlines
    02:     Entering loop
    03:       Number 1

But once the loop finished the update per ``i`` is overwitten::

    00: First step
    01:   Intermediate step 1
    01:    with newlines
    02:     Entering loop
    02:     Loop done 
    00: Final step
    
Composing Line Output and Timing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For lengthy operations it is often considerate to provide the user with an update on
how long an operation takes. :class:`cdxcore.verbose.Context` provides some simple tooling::
    
    from cdxcore.verbose import Context
    import time as time
    
    def takes_long( n : int, verbose : context = Context.quiet ):    
        with verbose.write_t("About to start... ", end='') as tme:  
            for t in range(n):
                verbose.write(lambda : f"\\rTakes long {int(100.*(t+1)/n)}%... ", end='') 
                time.sleep(0.22)
            verbose.write(lambda : f"done; this took {tme}.", head=False)
    
    takes_long(5, Context.all)
    
During execution prints
    
.. code-block:: python

    00: Takes long 80%... 
    
The example finishes with

.. code-block:: python

    00: Takes long 100%... done; this took 1.1s.

Import
------
.. code-block:: python

    from cdxcore.verbose import Context
    
Documentation
-------------
"""

from .util import fmt, Timer, CRMan, Callable
from .err import verify

class Context(object):
    r"""
    Class for printing indented messages, filtered by overall level of visibility.

    * Construction with keywords::
        
        Context( "all" )` or
        Context( "quiet" )

    * Display everything::
        
        Context( None )

    * Display only up to level 2 (top level is 0) e.g.::

        Context( 2 )

    * Copy constructor::
        
        Context( context )
        
    **Example:**

    .. code-block:: python
    
        from cdxcore.verbose import Context
        
        def f_2( verbose : Context = Context.quiet ):
            verbose.write( "Running 'f_2'")
            for i in range(5):
                verbose.report(1, "Sub-task {i}", i=i)
                # do something
    
        def f_1( verbose : Context = Context.quiet ):
            verbose.write( "Running 'f_1'")
            f_2( verbose(1) )
            # do something
    
        verbose = Context("all")
        verbose.write("Starting:")
        f_1(verbose(1))   
        verbose.write("Done.")

    prints
    
    .. code-block:: python
    
        00: Starting:
        01:   Running 'f_1'
        02:     Running 'f_2'
        03:       Sub-task 0
        03:       Sub-task 1
        03:       Sub-task 2
        03:       Sub-task 3
        03:       Sub-task 4
        00: Done.
    
    If we set visibility to 2

    .. code-block:: python

        verbose = Context(2)
        verbose.write("Starting:")
        f_1(verbose(1))   # <-- make it a level higher
        verbose.write("Done.")
 
    we get the reduced
    
    .. code-block:: python

        00: Starting:
        01:   Running 'f_1'
        02:     Running 'f_2'
        00: Done.
    
    **Lazy Formatting**
    
    The :meth:`cdxcore.verbose.Context.write` and :meth:`cdxcore.verbose.Context.report` functions provide
    string formatting capabilities. If used, then a message will only be formatted if the current level grants
    it visibility. This avoids unnecessary string operations when no output is required.
    
    In the second example above, the format string ``verbose.report(1, "Sub-task {i}", i=i)`` in ``f_2``
    will not be evaluated as that reporting level is turned off.

    Parameters
    ----------
    init : str | int | :class:`cdxcore.verbose.Context`
    
        * If a string is provided: must be ``"all"`` or ``"quiet"``.
        
        * If an integer is privided it represents the visibility level up to which to print.
          Set to 0 to print only top level messages.
          Any negative number will turn off any messages and is equivalent to ``"quiet"``.
        
        * If set to ``None`` display everything.
        
        * A ``Context`` is copied.
        
    indent : int, optional
        How much to indent strings per level. Default 2.
        
    fmt_level : str, optional
        A format string containing ``%d`` for the current indentation.
        Default is ``"%02ld: "``.
            
    level : int, optional
        Current level. If ``init`` is another context, and ``level`` is specified,
        it overwrites the ``level`` from the other context.
        
        If ``level`` is ``None``:
            
        * If ``init`` is another ``Context`` object, use that object's level.
        
        * If ``init`` is an integer or one of the keywords above, use the default, 0.
        
    channel : Callable, optional    
        *Advanced parameter.*
        
        A callable which is called to print text. The call signature is::
        
            channel( msg : str, flush : bool )`
            
        which is meant to mirror
        ``print( msg, end='', flush )`` for the provided ``channel``.        
        In particular do not terminate ``msg`` automatically with a new line.

        Illustration:: 

            class Collector:
                def __init__(self):
                    self.messages = []
                def __call__(self, msg, flush ):
                    self.messages.append( msg )

            collect  = Collector()
            verbose  = Context( channel = collect )
            
            verbose.write("Write at 0")
            verbose.report(1,"Report at 1")
            
            print(collect.messages)
            
        prints

        .. code-block:: python
            
            ['00: Write at 0\\n', '01:   Report at 1\\n']
    """

    QUIET   = "quiet"
    """ Constant for the keyword ``"quiet"`` """
    
    ALL     = "all"
    """ Constant for the keyword ``"all"`` """

    def __init__(self,   init      : str|int|type = None, *,
                         indent    : int = 2,
                         fmt_level : str = "%02ld: ",
                         level     : int = None,
                         channel   : Callable = None
                         ):
        """
        Create a Context object.
        """
        if not level is None: verify( level>=0, "'level' must not be negative; found {level}", level=level, exception=ValueError)
        if isinstance( init, Context ) or type(init).__name__ == "Context":
            # copy constructor
            self.visibility  = init.visibility
            self.level       = init.level if level is None else level
            self.indent      = init.indent
            self.fmt_level   = init.fmt_level
            self.crman       = CRMan()
            self.channel     = init.channel if channel is None else channel
            return

        if isinstance( init, str ):
            # construct with key word
            if init == self.QUIET:
                init = -1
            else:
                verify( init == self.ALL,
                        lambda : f"'init': if provided as a string, has to be '{self.QUIET}' or"+\
                                 f"'{self.ALL}'. Found '{init}'", exception=ValueError)
                init = None
        elif not init is None:
            init = int(init)

        indent           = int(indent)
        verify( indent >=0, "'indent' cannot be negative. Found {indent}", indent=indent, exception=ValueError)

        self.visibility  = init               # print up to this level
        self.level       = 0 if level is None else level
        self.indent      = indent             # indentation level
        self.fmt_level   = str(fmt_level)     # output format
        self.crman       = CRMan()
        self.channel     = channel

    def write( self, message : str|Callable, *args, end : str = "\n", head : bool = True, **kwargs ):
        r"""
        Report message at current level.
        
        The message will be formatted using :func:`cdxcore.err.fmt`
        if the current level is visible. If the current level is not visible no message formatting
        will take place.

        The parameter ``end`` matches ``end`` in :func:`print`
        e.g. ``end=''``
        avoids a newline at the end of the message.
        
        * If ``head`` is ``True``, then the first line of the text will be preceeded by proper indentation.
        
        * If ``head`` is ``False``, the first line will be printed without preamble.

        This means the following is a valid pattern::

            from cdxcore.verbose import Context
            verbose = Context()
            verbose.write("Doing something... ", end='')
            # ... do something
            verbose.write("done.", head=False)

        which prints

        .. code-block:: python

            00: Doing something... done.
        
        Another use case is updates per line, for example::

            from cdxcore.verbose import Context
            verbose = Context()
            N  = 1000
            for i in range(N):                
                verbose.write(f"\\rDoing something {int(float(i+1)/float(N)*100)}%... ", end='')
                # do something
            verbose.write("done.", head=False)

        which will provide progress information in a given line.
        
        *Implementation notice*: the use of ``\r`` is managed using :class:`cdxcore.crman.CRMan`.
        
        Parameters
        ----------
        message : str|Callable
        
            Text containing format characters. 
            
            The following alternatives are suppoted:
            
            * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
              to obtain the output message.
            
            * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
            
            * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
            
            * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( *args, **kwargs )``
              is called to obtain the output message.
              
              Note that a common use case is using an f-string wrapped in a ``lambda`` function. In this case
              you do not need ``args`` or ``kwargs``::
                  
                  x = 1
                  verbose.write(lambda : f"Delayed f-string formatting {x}")

        end : str, optional
            Terminating string akin to ``end`` in :func:`print`.
            Use ``''`` to not print a newline. See example above for a use case.
            
        head : bool, optional;
            Whether this message needs a header (i.e. the ``01`` and spacing).
            Typically ``False`` if the previous call to ``write()`` used `end=''`. See examples above.

        *args, **kwargs:
            See above
        """
        self.report( 0, message, *args, end=end, head=head, **kwargs )

    def write_t( self, message : str|Callable, *args, end : str = "\n", head : bool = True, **kwargs ) -> Timer:
        """
        Reports ``message`` subject to string formatting at current level if visible and returns a
        :class:`cdxcore.util.Timer` object
        which can be used to measure time elapsed since ``write_t()`` was called::

            from cdxcore.verbose import Context
            verbose = Context()
            with verbose.write_t("Doing something... ", end='') as tme:
                # do something
                verbose.write("done; this took {tme}.", head=False)

        produces

        .. code-block:: python
        
            00: Doing something... done; this took 1s.

        Equivalent to using :meth:`cdxcore.verbose.Context.write` first followed by        
        :meth:`cdxcore.verbose.Context.timer`.        
        """
        self.report( 0, message, *args, end=end, head=head, **kwargs )
        return self.timer()

    def report( self, level : int, message : str|Callable, *args, end : str = "\n", head : bool = True, **kwargs ):
        r"""
        Report message at current level plus ``level``.

        The message will be formatted using :func:`cdxcore.err.fmt` is the current level
        plus `level` is visible.

        The parameter ``end`` matches ``end`` in :func:`print`
        e.g. ``end=''``
        avoids a newline at the end of the message.
        
        * If ``head`` is ``True``, then the first line of the text will be preceeded by proper indentation.
        
        * If ``head`` is ``False``, the first line will be printed without preamble.

        This means the following is a valid pattern::
            
            from cdxcore.verbose import Context
            verbose = Context()
            verbose.report(1, "Doing something... ", end='')
            # ... do something
            verbose.report(1, "done.", head=False)

        which prints

        .. code-block:: python

            01: Doing something... done.
        
        Another use case is updates per line, for example:::

            from cdxcore.verbose import Context
            verbose = Context()
            N  = 1000
            for i in range(N):                
                verbose.report(1,f"\\rStatus {int(float(i+1)/float(N)*100)}%... ", end='')
                # do something
            verbose.report(1,"done.", head=False)

        will provide progress information in the current line as the loop is processed.
        
        *Implementation notice:* The use of ``\\r`` is managed using :class:`cdxcore.crman.CRMan`.

        Parameters
        ----------
        level : int
            Level to add to current level.
            
        message : str|Callable
        
            Text containing format characters. 
            
            The following alternatives are suppoted:
            
            * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
              to obtain the output message.
            
            * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
            
            * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
            
            * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( *args, **kwargs )``
              is called to obtain the output message.
              
              Note that a common use case is using an f-string wrapped in a ``lambda`` function. In this case
              you do not need ``args`` or ``kwargs``::
                  
                  x = 1
                  verbose.write(lambda : f"Delayed f-string formatting {x}")

        end : str, optional
            Terminating string akin to ``end`` in :func:`print`.
            Use ``''`` to not print a newline. See example above for a use case.
            
        head : bool, optional;
            Whether this message needs a header (i.e. the ``01`` and spacing).
            Typically ``False`` if the previous call to ``write()`` used `end=''`. See examples above.

        *args, **kwargs:
            See above 
        """
        message = self.fmt( level, message, *args, head=head, **kwargs )
        self._raw(message,end=end,flush=True)
            
    def _raw( self, message : str, end : str, flush : bool ):
        """ :meta private: used in JCPool """
        if not message is None:
            self.crman.write(message,end=end,flush=flush,channel=self.channel )

    def fmt( self, level : int, message : str|Callable, *args, head : bool = True, **kwargs ) -> str:
        """
        Formats message with the formattting arguments at curent context level plus ``level``.
        
        This function returns ```` if current level plus ``level`` is not visible.
        In that case no string formatting takes place.

        Parameters
        ----------
        level : int
            Level to add to current level.
            
        message : str|Callable
        
            Text containing format characters. 
            
            The following alternatives are suppoted:
            
            * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
              to obtain the output message.
            
            * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
            
            * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
            
            * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( *args, **kwargs )``
              is called to obtain the output message.
              
              Note that a common use case is using an f-string wrapped in a ``lambda`` function. In this case
              you do not need ``args`` or ``kwargs``::
                  
                  x = 1
                  verbose.write(lambda : f"Delayed f-string formatting {x}")

        head : bool, optional;
            Whether this message needs a header (i.e. the ``01`` and spacing).
            Typically ``False`` if the previous call to ``write()`` used `end=''`. See examples above.

        *args, **kwargs:
            See above 

        Returns
        -------
        String : str
            Formatted string, or ``None` `if the current level plus ``level`` is not visible.
        """
        if not self.shall_report(level):
            return None
        if isinstance(message, str) and message == "":
            return ""
        str_level = self.str_indent( level )
        text      = fmt( message, *args, **kwargs )
        text      = text[:-1].replace("\r", "\r" + str_level ) + text[-1]
        text      = text[:-1].replace("\n", "\n" + str_level ) + text[-1]
        text      = str_level + text if head and text[:1] != "\r" else text
        return text

    def __call__(self, add_level : int = 1, message : str|Callable = None, end : str = "\n", head : bool = True, *args, **kwargs ):
        """
        Create and return a sub ``Context`` at current level plus ``add_level``.
        
        If a ``message`` is provided, :meth:`cdxcore.verbose.Context.write()` is called
        before the new ``Context`` is created.
        
        Example::
            
            from cdxcore.verbose import Context
            def f( verbose : Context = Context.quiet ):
                # ...
                verbose.write("'f'' usuing a sub-context.")
            verbose = Context.all
            verbose.write("Main")
            f( verbose=verbose(1) )   # create sub-context

        prints

        .. code-block:: python
        
            00: Main
            01:   'f'' usuing a sub-context.

        Parameters
        ----------
        add_level : int
            Level to add to the current level. Set to 0 for the same level.

        message : str|Callable, optional.
        
            Text containing format characters, or ``None`` to not print a message.
            
            The following alternatives are suppoted:
            
            * Python 3 ```{parameter:d}```, in which case ``message.fmt(kwargs)`` for :meth:`str.format` is used
              to obtain the output message.
            
            * Python 2 ```%(parameter)d``` in which case ``message % kwargs`` is used to obtain the output message.
            
            * Classic C-stype ```%d, %s, %f``` in which case ``message % args`` is used to obtain the output message.
            
            * If ``message`` is a ``Callable`` such as a ``lambda`` function, then ``message( *args, **kwargs )``
              is called to obtain the output message.
              
              Note that a common use case is using an f-string wrapped in a ``lambda`` function. In this case
              you do not need ``args`` or ``kwargs``::
                  
                  x = 1
                  verbose.write(lambda : f"Delayed f-string formatting {x}")

        head : bool, optional;
            Whether this message needs a header (i.e. the ``01`` and spacing).
            Typically ``False`` if the previous call to ``write()`` used `end=''`. See examples above.

        *args, **kwargs:
            See above 

        Returns
        -------
        verbose : ``Context``
            Sub context with new level equal to current level plus ``add_level``.
        """
        add_level = int(add_level)
        verify( add_level >= 0, "'add_level' cannot be negative. Found {add_level}", add_level=add_level, exception=ValueError)

        if not message is None:
            self.write( message=message, end=end, head=head, *args, **kwargs )

        sub             = Context(self)
        assert sub.visibility == self.visibility, "Internal error"
        sub.level       = self.level + add_level
        return sub

    @property
    def as_verbose(self):
        """ Return a Context at the same current reporting level as ``self`` with full visibility """
        copy = Context(self)
        copy.visibility = None
        return copy

    @property
    def as_quiet(self):
        """ Return a Context at the same current reporting level as ``self`` with zero visibility """
        copy = Context(self)
        copy.visibility = 0
        return copy

    @property
    def is_quiet(self) -> bool:
        """ Whether the current context is ``"quiet"`` """
        return not self.visibility is None and self.visibility < 0

    def shall_report(self, add_level : int = 0 ) -> bool:
        """ Returns whether to print something at current level plus ``add_level``. """
        add_level  = int(add_level)
        verify( add_level >= 0, "'add_level' cannot be negative. Found {add_level}", add_level=add_level, exception=ValueError)
        return self.visibility is None or self.visibility >= self.level + add_level

    def str_indent(self, add_level : int = 0) -> str:
        """ Returns the string identation for the current level plus ``add_level`` """
        add_level  = int(add_level)
        verify( add_level >= 0, "'add_level' cannot be negative. Found {add_level}", add_level=add_level, exception=ValueError)
        s1 = ' ' * (self.indent * (self.level + add_level))
        s2 = self.fmt_level if self.fmt_level.find("%") == -1 else self.fmt_level % (self.level + add_level)
        return s2+s1
    
    # Misc
    # ----
    
    def timer(self) -> Timer:
        """
        Returns a new :class:`cdxcore.util.Timer` object to measure time spent in a block of code.
        
        Example::

            import time as time
            from cdxcore.verbose import Context

            verbose = Context("all")
            with verbose.Timer() as tme:
                verbose.write("Starting job... ", end='')
                time.sleep(1)
                verbose.write(f"done; this took {tme}.", head=False)

        produces

        .. code-block:: python

            00: Starting job... done; this took 1s.

        """
        return Timer()
     
    # uniqueHash
    # ----------

    def __unique_hash__( self, unique_hash, debug_trace ) -> str:
        """
        Hash function for :class:`cdxcore.uniquehash.UniqueHash`.
        This function always returns an empty string, which means that the object is never hashed.
        :meta private:
        """
        return ""
    
    # Channels
    # --------

    def apply_channel( self, channel : Callable ):
        """
        *Advanced Use*
        
        Returns a new ```Context`` object with the same currrent state as ``self``,
        but pointing to ``channel``.
        """
        return Context( self, channel=channel ) if channel != self.channel else self
    
    # Dummy context
    # -------------
    
    def __enter__(self):
        return self

    def __exit__(self, *kargs, **kwargs):
        return False#raise exceptions
    
quiet         = Context(Context.QUIET)
all_          = Context(Context.ALL)
Context.quiet = quiet
"""
A default ``Context`` with zero visibility.
"""

Context.all   = all_
"""
A default ``Context`` with full visibility.
"""

Context.quiet.__doc__ = \
"""
A default ``Context`` with zero visibility.
"""



    


