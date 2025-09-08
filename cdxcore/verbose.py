"""
## Overview

This module contains the [Context][cdxcore.verbose.Context] manager which supports printing hierarchical verbose progress reports.
The key point of this class is to implement an easy-to-use method to print progress which can also be turned off easily without
untidy code constructs such as excessive `if` blocks.

Moreover, message formatting is only applied if the message will also be printed (i.e. in `quiet` mode the functions are very fast).

**Example**

```
def f(x, y, *, verbose = Context.quiet):
    verbose.write(f"Processing {x:.2f} and {y:.2f}", x=x, y=y)   # <- will only format the string if verbosity requires this
    return x*y

def loop(num, *, verbose = Context.quiet):
    import numpy as np
    xs = np.random.normal( size=(num,)).tolist()  
    ys = np.random.normal( size=(num,)).tolist()  
    z = 0.
    with verbose.write_t("Starting to process {numsq} elements:", numsq=num**2) as tme:
        for ix, x in enumerate(xs):
            verbose.report(1,"Processing #{ix} {x:.2f}", ix=ix, x=x)
            for y in ys:
                z += f(x=x,y=y,verbose=verbose(2))
        verbose.write("Processed {numsq} elements; this took {tme}", numsq=num**2, tme=tme)
    return z
```

then `loop(2, verbose=Context.all)` gives

```
00: Starting to process 4 elements:
01:   Processing #0 -0.76
02:     Processing -0.76 and -0.36
02:     Processing -0.76 and -0.23
01:   Processing #1 -0.51
02:     Processing -0.51 and -0.36
02:     Processing -0.51 and -0.23
00: Processed 4 elements; this took 2.08ms
```

## Import
```
from cdxcore.verbose import Context
```
"""

from .util import fmt, Timer
from .err import verify
from .crman import CRMan, Callable

class Context(object):
    """
    Class for printing indented messages, filtered by overall level of visibility.

    ```
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
    ```
    prints
    ```
    00: Starting:
    01:   Running 'f_1'
    02:     Running 'f_2'
    03:       Sub-task 0
    03:       Sub-task 1
    03:       Sub-task 2
    03:       Sub-task 3
    03:       Sub-task 4
    00: Done.
    ```
    
    If, though, we set visibility only 2:
    ```
    verbose = Context(2)
    verbose.write("Starting:")
    f_1(verbose(1))   # <-- make it a level higher
    verbose.write("Done.")
    ```
    we get the reduced
    ```
    00: Starting:
    01:   Running 'f_1'
    02:     Running 'f_2'
    00: Done.
    ```
    
    The [write][cdxcore.verbose.Context.write]() and [report][cdxcore.verbose.Context.report]() functions provide
    string formatting capabilities. If used, then a message will only be formatted if the current level grants
    it visibility. This avoids unnecessary string operations when no output is required.
    
    In the second example above, the format string `verbose.report(1, "Sub-task {i}", i=i)` in `f_2`
    will not be evaluated as that reporting level is turned off.
    """

    QUIET   = "quiet"
    ALL     = "all"

    def __init__(self,   init      = None, *,
                         indent    : int = 2,
                         fmt_level : str = "%02ld: ",
                         level     : int = None,
                         channel   : Callable = None
                         ):
        """
        Create a Context object.

        * Construction with keywords:
            `Context( "all" )` or
            `Context( "quiet" )`

        * Display everything:
            `Context( None )`

        * Display only up to level 2 (the root context is level 0) e.g.:
            `Context( 2 )`

        * Copy constructor: `Context( context )`.

        Parameters
        ----------
        init : str, int, or Context
        
            * if a string: one of 'all' or 'quiet'
            
            * if an integer: the visibility level up to which to print.
                Set to 0 to print only top level messages.
                Any negative number will turn off any messages and is equivalent to "quiet".
            
            * if None: equivalent to displaying everything ("all")
            
            * if a Context: copy constructor.
            
        indent : int
            How much to indent strings per level
            
        fmt_level : str
            How to format output given `level`*`indent` using %ld for the current level.
                
        level : int
            _Advanced parameter_.
            Initial level. This can also be set if `init` is another context.
            
            If `level` is None:
                
            * If `init` is another Context object, use that object's level
            
            * If `init` is an integer or one of the keywords above, use 0
            
        channel : Callable
            _Advanced parameter_.
            A callable which is called to print text. The call signature is
            `channel( msg : str, flush : bool )`
            which is meant to mirror
            `print( msg, end='', flush )` for the provided `channel`.
            
            In particular do not terminate `msg` automatically with a new line.
            A `channel` can also be set if `init` is another context, i.e.
 
            ```
                verbose = Context()
                ...
                cverbose = Context( verbose, channel=lambda msg, flush : pass )                
            ```            
            will return a silenced `cverbose`.
                    
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

    def write( self, message : str, *args, end : str = "\n", head : bool = True, **kwargs ):
        r"""
        Report message at current level.
        The message will be formatted as [fmt][cdxcore.err.fmt](message, *args, **kwargs).
        The message will only be formatted and displayed if the current level is visible.

        The parameter `end` matches `end` in [print](https://docs.python.org/3/library/functions.html#print)(), e.g. `end=''`
        avoids a newline at the end of the message.
        
        * If `head` is True, then the first line of the text will be preceeded by proper indentation.
        
        * If `head` is False, the first line will be printed without preamble.

        This means the following is a valid pattern
        ```
            verbose = Context()
            verbose.write("Doing something... ", end='')
            # do something
            verbose.write("done.", head=False)
        ```
        which prints
        ```
            00: Doing something... done.
        ```
        
        Another use case is updates per line, for example:
        ```
            verbose = Context()
            N  = 1000
            for i in range(N):                
                verbose.write(f"\rDoing something {int(float(i+1)/float(N)*100)}%... ", end='')
                # do something
            verbose.write("done.", head=False)
        ```
        which will provide progress information in a given line.
        
        <u>Implementation notice</u>: The use of `\r` is managed using [CRMan][cdxcore.crman.CRMan].
        
        Parameters
        ----------
        message : str
            Text potentially containing format characters. 
            
            * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
            
            * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
            
            * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
            
            * lambda functions: if `text` is not a string but a callable this is called.

        end : str
            Terminating string akin to [print](https://docs.python.org/3/library/functions.html#print)().
            Use `` to not print a newline.
            
        head : bool
            Whether this message needs a header (i.e. the `01` and the speacing).
            Typically false if the previous write() was called with `end=''`. See examples above.

        *args, **kwargs:
            See above
        """
        self.report( 0, message, *args, end=end, head=head, **kwargs )

    def write_t( self, message : str, *args, end : str = "\n", head : bool = True, **kwargs ) -> Timer:
        """
        Reports `message` subject to string formatting at current level if visible and returns a [Timer][cdxcore.util.Timer] object
        which can be used to measure time elapsed since write_t() was called.

        ```
        verbose = Context()
        with verbose.write_t("Doing something... ", end='') as tme:
            # do something
            verbose.write("done; this took {tme}.", head=False)
        ```
        produces
        ```
        00: Doing something... done; this took 1s.
        ```

        Equivalent to using [write][cdxcore.verbose.Context.write]() first followed by [timer][cdxcore.verbose.Context.timer]().        
        """
        self.report( 0, message, *args, end=end, head=head, **kwargs )
        return self.Timer()

    def report( self, level : int, message : str, *args, end : str = "\n", head : bool = True, **kwargs ):
        r"""
        Report message at current level plus `level`.
        The message will be formatted as [fmt][cdxcore.err.fmt]( message, *args, **kwargs ).
        The message will only be formatted and displayed if current level plus `level` is visible.

        The parameter `end` matches `end` in [print](https://docs.python.org/3/library/functions.html#print)(), e.g. `end=''`
        avoids a newline at the end of the message.
        
        * If `head` is True, then the first line of the text will be preceeded by proper indentation.
        
        * If `head` is False, the first line will be printed without preamble.

        This means the following is a valid pattern
        ```
            verbose = Context()
            verbose.report(1, "Doing something... ", end='')
            # do something
            verbose.report(1, "done.", head=False)
        ```
        which prints
        ```
            01: Doing something... done.
        ```
        
        Another use case is updates per line, for example:
        ```
            verbose = Context()
            N  = 1000
            for i in range(N):                
                verbose.report(1,f"\rStatus {int(float(i+1)/float(N)*100)}%... ", end='')
                # do something
            verbose.report(1,"done.", head=False)
        ```
        will provide progress information in the current line as the loop is processed.
        
        <u>Implementation notice</u>: The use of `\r` is managed using [CRMan][cdxcore.crman.CRMan].

        Parameters
        ----------
        level : int
            Level to add to current level.
            
        message : str
            Text potentially containing format characters. 
            
            * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
            
            * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
            
            * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
            
            * lambda functions: if `text` is not a string but a callable this is called.

        end : str
            Terminating string akin to [print](https://docs.python.org/3/library/functions.html#print)().
            Use `` to not print a newline.
            
        head : bool
            Whether this message needs a header (i.e. the `01` and the speacing).
            Typically false if the previous write() was called with `end=''`. See examples above.

        *args, **kwargs:
            See above
        """
        message = self.fmt( level, message, *args, head=head, **kwargs )
        if not message is None:
            self.crman.write(message,end=end,flush=True, channel=self.channel )

    def fmt( self, level : int, message : str, *args, head : bool = True, **kwargs ) -> str:
        """
        Formats message with the formattting arguments at curent context level plus 'level'
        The message will be formatted with [fmt][cdxcore.err.fmt]( message, *args, **kwargs )
        and then indented appropriately.
        
        The function returns None if current level plus `level` is not visible.
        In that case no string formatting takes place.

        Parameters
        ----------
        level : int
            Level to add to current level.
            
        message : str
            Text potentially containing format characters. 
            
            * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
            
            * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
            
            * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
            
            * lambda functions: if `text` is not a string but a callable this is called.

        head : bool
            Whether this message needs a header (i.e. the `01` and the speacing).

        *args, **kwargs:
            See above

        Returns
        -------
        String : str
            Formatted string, or `None` if current level plus `level` are not visible.
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

    def sub( self, add_level : int = 1, message : str = None, *args, **kwargs ):
        """
        Create a sub Context at current level plus `add_level`.

        Parameters
        ----------
        add_level : int
            Level to add to the current level. Set to 0 for the same level.

        message : str
            Text potentially containing format characters, or None for no message.
            `message` supports string formatting:
            
            * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
            
            * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
            
            * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
            
            * lambda functions: if `text` is not a string but a callable this is called.

        *args, **kwargs:
            See above

        Returns
        -------
        verbose : Context
            Sub context with new level equal to current level plus `add_level`.
        """
        add_level = int(add_level)
        verify( add_level >= 0, "'add_level' cannot be negative. Found {add_level}", add_level=add_level, exception=ValueError)

        if not message is None:
            self.write( message=message, *args, **kwargs )

        sub             = Context(self)
        assert sub.visibility == self.visibility, "Internal error"
        sub.level       = self.level + add_level
        return sub

    def __call__(self, add_level : int, message : str = None, *args, **kwargs ):
        """
        Create a sub context at current level plus `add_level`.
        Optionally write message at the new level.

        Parameters
        ----------
        add_level : int
            Level to add to the current level. Set to 0 for the same level.
            
            `add_level` can also be a string if `message` is None.
            In this case the `add_level` parameter is interpreted as `message`, 
            and the function acts as a short-cut to [write][cdxcore.verbose.Context.write]().

        message : str
            Text potentially containing format characters, or None for no message.
            `message` supports string formatting:
            
            * Classic C-stype ```%d, %s, %f```: in this case the positional `args` of the function are used.
            
            * Python 2 ```%(parameter)d```: in this case `kwargs` are used.
            
            * Python 3 ```{parameter:d}``` [str.format](https://docs.python.org/3/library/stdtypes.html#str.format)() format: in this case `kwargs` are used.
            
            * lambda functions: if `text` is not a string but a callable this is called.

        *args, **kwargs:
            See above

        Returns
        -------
        verbose : Context
            Sub context with new level equal to current level plus `add_level`.
        """
        if message is None:
            assert len(args) == 0 and len(kwargs) == 0, "Internal error: no 'message' is provided."
            return self.sub(add_level)
        if isinstance(add_level, str):
            verify( message is None, "Cannot specify 'add_level' as string and also specify 'message'", exception=ValueError)
            self.write( add_level, *args, **kwargs )
            return self
        else:
            assert isinstance(add_level, int), "'add_level' should be an int or a string"
            self.report( add_level, message, *args, **kwargs )
            return self.sub(add_level)

    @property
    def as_verbose(self):
        """ Return a Context at the same current reporting level as `self` with full visibility """
        copy = Context(self)
        copy.visibility = None
        return copy

    @property
    def as_quiet(self):
        """ Return a Context at the same current reporting level as `self` with zero visibility """
        copy = Context(self)
        copy.visibility = 0
        return copy

    @property
    def is_quiet(self) -> bool:
        """ Whether the current context is quiet """
        return not self.visibility is None and self.visibility < 0

    def shall_report(self, add_level : int = 0 ) -> bool:
        """ Returns whether to print something at `add_level` relative to current level """
        add_level  = int(add_level)
        verify( add_level >= 0, "'add_level' cannot be negative. Found {add_level}", add_level=add_level, exception=ValueError)
        return self.visibility is None or self.visibility >= self.level + add_level

    def str_indent(self, add_level : int = 0) -> str:
        """ Returns the string identation for a given `add_level` plus current level """
        add_level  = int(add_level)
        verify( add_level >= 0, "'add_level' cannot be negative. Found {add_level}", add_level=add_level, exception=ValueError)
        s1 = ' ' * (self.indent * (self.level + add_level))
        s2 = self.fmt_level if self.fmt_level.find("%") == -1 else self.fmt_level % (self.level + add_level)
        return s2+s1
    
    # Misc
    # ----
    
    def timer(self) -> Timer:
        """
        Returns a new [Timer][cdxcore.util.Timer] object to measure time spent in a block of code.
        ```
        import time as time
        verbose = Context("all")
        with verbose.Timer() as tme:
            verbose.write("Starting... ", end='')
            time.sleep(1)
            verbose.write(f"this took {tme}.", head=False)
        ```
        produces
        ```
        00: Starting... this took 1s.
        ```
        """
        return Timer()
     
    # uniqueHash
    # ----------

    def __unique_hash__( self, unique_hash, debug_trace ) -> str:
        """
        Do not compute a hash for Context objects when [UniqueHash][cdxcore.uniquehash.UniqueHash]() is called.
        This function always returns an empty string, which means that the object is never hashed.
        """
        return ""
    
    # Channels
    # --------

    def apply_channel( self, channel : Callable ):
        """
        Returns a new Context object with the same currrent state as `self`, but pointing to `channel`.
        """
        return Context( self, channel=channel ) if channel != self.channel else self
    
    
quiet         = Context(Context.QUIET)
Context.quiet = quiet

all_ = Context(Context.ALL)
Context.all = all_

Context.Timer = Timer

    


