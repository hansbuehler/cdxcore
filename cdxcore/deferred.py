r"""
[Not included in main documentation]

Overview
--------

Framework for delayed execution of a Python code tree.
Used by :mod:`cdxcore.dynaplot`.

*Advanced Users Only*

Illustation
^^^^^^^^^^^

**The Top Dependency Graph**

Assume we have a class ``A`` and a function ``F``
operates on instances ``a`` of ``A``:

.. code-block:: python

    class A(object):
        def __init__(self, x):
            self.x = x
        def func(self, y=1):
            return self.x * y
        def __call__(self, y):
            return self.x + y
        def __eq__(self, z):
            return self.x==z

    def F(a : A):       
        _ = a.f(2)
        _ = _+a(3)  
        return _, _ == 1
    
Create execution means that instead of using an instance of ``A`` to evaluate
``F``, we use a :func:`cdxcore.deferred.Deferred.Create` object:

.. code-block:: python

    from cdxcore.deferred import Create
    
    a      = Create("a")    # <- name "a" is arbitrary but important for error messages
    r1, r2 = F(a)
    
The returned ``r1`` and ``r2`` are of type :class:`cdxcore.deferred.Deferred`. We can print
the overall dependency tree from ``a`` using :meth:`cdxcore.deferred.Deferred.deferred_print_dependency_tree`:

.. code-block:: python
    
    a.deferred_print_dependency_tree( with_sources = True )
    
yields::

    00: $a <= $a
    01:   $a.f <= $a
    02:     $a.f(2) <= $a
    03:       ($a.f(2)+$a(3)) <= $a
    04:         (($a.f(2)+$a(3))==1) <= $a
    01:   $a(3) <= $a

The ``$`` sign indicates top level source elements.
Note that this tree shows the depth of the dependencies, not execution dependencies: the term ``$a(3)``
must be executed before ``$a.f(2)+=$a(3)``.
This order of terms a seen from the top level ``a`` can be retrieved using :meth:`cdxcore.deferred.Deferred.deferred_source_dependants`:
calling ``print( [ _.deferred_info for _ in a.deferred_source_dependants ] )`` prints::

    ['$a.f', '$a.f(2)', '$a(3)', '$a.f(2)+=$a(3)', '($a.f(2)==2)']

**Evaluating the Graph**

To execute the graph, use :meth:`cdxcore.deferred.Create.deferred_resolve` at top level (note that graphs can only
be resolved once):

.. code-block:: python

    a.deferred_resolve(A(x=2))
    print(r1.deferred_result, ",", r2.deferred_result)   # -> 9 , False
    
Validation by directly execution ``F`` with an object of type ``A`` confirms the result:

.. code-block:: python

    t1, t2 = F(A(x=2))
    print(t1, ",", t2)                                 # -> 9 , False

Limitations
^^^^^^^^^^^

The framework relies on replacing any Python element by a :class:`cdxcore.deferred.Deferred` object and then
catche and track all actions applied to it, be that reading an attribute, an item, calling ``__call__`` or accessing
any of the standard Python attributes such as ``__eq__``.

This appraoch has a number of short comings:

* **Gap in Implementation:** please let us know.    

* **Flow controls:** any code flow which depends on the actual value of some computation is not supported.

* **Core Python Operators:** some Python operators
  must return a certain type: ``__bool__``, ``__str__``, ``__repr__`` and ``__index__`` as far as we are aware.
  That means we cannot wrap the result into a 
  :class:`cdxcore.deferred.Deferred`.
  
  Considering ``__str__`` and ``__repr__`` are used throughtout the Python stack 
  a ``Deferred`` will return strings describing itself. Be aware of
  corresponding error messages.
  
  If ``__bool__`` or ``__index__`` is called a :class:`cdxcore.deferred.NotSupportedError`
  is raised.

* **Python atomic types:** Python optimizes various operations for its atomic types such as ``int`` etc. That means if a deferred
  action catches an operation on an element which represents an atomic element, it might not be able to translate the action
  into the atomic's equivalent.
  
  Here is an example for ``int`` with ``+=``: 
      
  .. code-block:: python
  
      a = Create("a")
      a += 1
      a.deferred_resolve(int(1))      

  This produces an error:

  .. code-block:: python
  
      AttributeError: ("Cannot resolve '$a+=1': the concrete element of type 'int' provided by '$a' does not contain the action '__iadd__'", "'int' object has no attribute '__iadd__'")

  The reason here is that the operation ``a += 1`` was caught as an ``__iadd__`` action.
  However, ``getattr`` cannot obtain this operator from an ``int``:
      
  .. code-block:: python

      getattr( int(1), "__iadd__" )    # -> AttributeError: 'int' object has no attribute '__iadd__'

  Interestingly, other operators such as ``__add__`` do work.

**Core Python Elements**

Some Python functionality requires more complexity: catching and tracing core
operatores like ``__bool__``, ``is_`` etc does not add value to the use cases we have in mind, and complicate the framework
considerably.

Deriving your own Classes
^^^^^^^^^^^^^^^^^^^^^^^^^

A common usage pattern is to mix deferred actions with actual actions.
To derive from :func:`cdxcore.deferred.Deferred.Create` it is recommended that you overwrite any operators that your
class relies on, explicitly or implicitly.

For example:
    
* **Equality operator for :class:`list` use:** if you intend to add your objects to a list, then you will need to overwrite
  the `__eq__` operator. The implementation of `Create.__eq__` delegates the result of the equality test to a later point - however
  if you plan to add any objects to a list, then this 

Class Interface
^^^^^^^^^^^^^^^

The class interfaces for both :func:`cdxcore.deferred.Deferred.Create` and :class:`cdxcore.deferred.Deferred`
are pretty clunky in that all member functions and attribues are pre-fixed with ``deferred`` or ``_deferred_``, respectively.
The reason is that the objects will catch and track all member function calls and attribute access meant for objects
of type ``A``.


Import
------

.. code-block:: python

    from cdxcore.deferred import Deferred

Documentation
-------------
"""

from .err import verify
from .util import qualified_name, fmt_list
from .verbose import Context
from collections.abc import Collection, Sequence, Mapping

class _ParentDeleted:
    pass

class ResolutionDependencyError(RuntimeError):
    """
    Exeception if the resolution of a deferred action failed because one
    of its source items has not been resolved.
    """
    pass        
   
class NotSupportedError(RuntimeError):
    """
    Exeception in case of an attempted resolution of unsupported
    operators.
    """
    pass

class Deferred(object):
    r"""
    Create a top level placeholder object to keep track
    of a sequence of actions performed
    on an object that does not yet exist.

    Actions such as function calls, item access, or attribute access,
    feed the resulting logical dependency tree. Once the target
    element is available, execute the dependency tree iteratively.

    A basic example is as follows: assume we have a class ``A`` of which
    we will create an object ``a``, but only at a later stage. We
    wish to record a list of deferred actions on ``a`` ahead of its creation.

    Define the class

    .. code-block:: python
        
        class A(object):
            def __init__(self, x):
                self.x = x
            def a_func(self, y):
                return self.x * y
            @staticmethod
            def a_static(y):
                return y
            @property
            def a_propery(self):
                return self.x
            def __getitem__(self, y):
                return self.x * y
            def __call__(self, y):
                return self.x * y
            def another(self):#
                return A(x=self.x*2)

    Use :func:`cdxcore.deferred.Deferred.Create` to create a root ``Deferred`` object:
        
    .. code-block:: python

        from cdxcore.deferred import Create
        da = Create("A")
        
    Record a few actions:

    .. code-block:: python

        af = da.a_func(1)    # defer function call to a_func(1)
        ai = da[2]           # defer item access
        aa = da.x            # defer attribute access

    :class:`cdxcore.deferred.Deferred` works iteratively, e.g. all values returned from a function call, ``__call__``, or ``__getitem__``
    are themselves deferred automatically. :class:`cdxcore.deferred.Deferred` is also able to defer item and attribute assignments.
    
    As an example:

    .. code-block:: python

        an = da.another()
        an = an.another()     # call a.another().another() --> an.x = 1*2*2 = 4
        
    Finally, resolve the execution by instantiating ``A`` and calling :meth:`cdxcore.deferred.Create.deferred_resolve`:

    .. code-block:: python

        a = A()
        da.deferred_resolve( a )
        
        print( an.x )         # -> 4

    Parameters
    ----------
    info : str
        Descriptive name of the usually not-yet-created object deferred actions
        will act upon.        
    """
    @classmethod
    def Create( cls, info : str ):
        """
        Create top level element.
        """
        info = str(info)
        verify( len(info) > 0, "You must specify an 'info' term")
        return cls( info=info )

    deferred_max_err_len = 100 #: maximum string length for strings

    def __init__(self,     info           : str, *,   
                           action         : str = "",       
                           #     
                           parent         : type|None  = None,
                           base_info      : bool|None = None,
                           # arguments passed to the action  
                           args           : Collection|None  = None,
                           kwargs         : Mapping|None  = None,   
                           ):
        """
        Initialize a deferred action.
        """
        verify( isinstance(action, str), lambda : f"'action' must be a string; found {self._deferred_to_str(action)}.", exception=ValueError)
        verify( isinstance(info, str), lambda : f"'info' must be a string; found {self._deferred_to_str(info)}.", exception=ValueError)
        verify( parent is None or isinstance(parent, Deferred), lambda : f"'parent' must be a Deferred; found {type(parent)}.", exception=ValueError)
        verify( args is None or isinstance(args, (Sequence,Collection)), lambda : f"'args' must be a Collection; found {type(args)}.", exception=ValueError)
        verify( kwargs is None or isinstance(kwargs, Mapping), lambda : f"'kwargs' must be a Mapping; found {type(kwargs)}.", exception=ValueError)
        
        if action == "":
            verify( len(info)>0 and
                    parent is None and
                    args is None and
                    kwargs is None, "Must specify 'info' but cannot specify 'parent', 'args', or 'kwargs' for the root action \"\"", exception=ValueError)
        
        self._deferred_action         = action              # action code
        self._deferred_parent         = parent
        self._deferred_depth          = parent._deferred_depth+1 if not parent is None else 0
        self._deferred_base_info      = parent._deferred_base_info if not parent is None else ( base_info if not base_info is None else False )
        self._deferred_args           = [] if args is None else list(args)
        self._deferred_kwargs         = {} if kwargs is None else dict(kwargs)
        self._deferred_live           = None           # once the object exists, it goes here.
        self._deferred_was_resolved   = False          # whether the action was executed.
        self._deferred_dependants     = []             # list of all direct dependent actions
        
        if action == "":
            # top level element
            info                          = "$"+info
            self._deferred_sources        = {id(self):info}
            self._deferred_info           = info
            self._deferred_src_dependants = []
            
        else:
            sources = dict(parent._deferred_sources)
            if not args is None:
                for x in args:
                    if isinstance(x, Deferred):
                        sources |= x._deferred_sources
            if not kwargs is None:
                for x in kwargs.values():
                    if isinstance(x, Deferred):
                        sources |= x._deferred_sources

            self._deferred_sources        = sources
            self._deferred_info           = info
            self._deferred_src_dependants = parent._deferred_src_dependants 
        
        self.__dict__["_ready_for_the_deferred_magic_"] = 1

    def __str__(self) -> str:
        """
        Return descriptive string.
        
        ``__str__`` cannot be deferred as it must return a string.
        We therefore return some information on ``self``
        """
        if not '_deferred_info' in self.__dict__:
            return type(self).__name__
        return self._deferred_info

    def __repr__(self) -> str:
        """
        Return description.
        
        ``__repr__`` cannot be deferred as it must return a string.
        We therefore return some information on ``self``
        """
        if not '_deferred_info' in self.__dict__:
            return type(self).__name__
        if self._deferred_parent is None:
            return f"{type(self).__name__}({self._deferred_info})"

        sources = list(self._deferred_sources.values())
        s = ""
        for src in sources:
            s += src + ","
        s = s[:-1]
        return f"{type(self).__name__}({self._deferred_info}<-{s})"

    def deferred_create_action( self, **kwargs ):
        """
        Creates a deferred action created during another deferred action.

        This function is called internally if a new action is created. The purpose of this function
        is allowing to implement different deferral overwrite profiles (eg which functions are overwritten).   
        
        The standard implementation is to call the constructor of the desired
        class derived from :class:`cdxcore.deferred.Deferred`.
        """
        return Deferred( **kwargs )
        
    @property
    def _deferred_parent_info(self) -> str:
        return self._deferred_parent._deferred_info if not self._deferred_parent is None else ""

    def _deferred_to_str( self, x ):
        """ Limit string 'x' to ``max_err_len`` by adding ``...`` if necessary. """
        x = str(x)
        if len(x) > self.deferred_max_err_len:
            if x[-1] in [')', ']', '}']:
                x = x[:self.deferred_max_err_len-4] + "..." + x[-1]
            else:
                x = x[:self.deferred_max_err_len-3] + "..." 
        return x
    
    def _deferred_to_argstr( self, x ):
        if isinstance(x, Deferred):
            if not x.deferred_was_resolved:
                return f"{{{x._deferred_info}}}"    
            x = x._deferred_live
        return self._deferred_to_str(x)

    def _deferred_fmt_args(self, args, kwargs ):
        """ format arguments """
        args_   = [ self._deferred_to_argstr(x) for x in args ]
        kwargs_ = { k: self._deferred_to_argstr(x) for k,x in kwargs.items() }
        fmt_args = ""
        for _ in args_:
            fmt_args += str(_) + ","
        for _ in kwargs_.items():
            fmt_args += f"{_[0]}={_[1]},"
        return fmt_args[:-1]

    def _deferred_qualname( self, x ):
        """ Attempt to obtain a human readable name for ``x``/ """
        if x is None:
            return "None"
        name = getattr(x,"_deferred_qualname__", getattr(x, "__name__", None) )
        if not name is None:
            return name       
        try:
            return qualified_name( type(x) )
        except:
            pass                       
        return self._deferred_to_str(x)

    @property
    def deferred_info(self) -> str:
        """
        Text description of the current action.
        
        Create level sources are indicated by a ``$``. Curly brackets ``{}`` indicate
        deferred actions themselves. For example:
        
        .. code-block:: python
        
            $a.f({$b.g(1)})
            
        Is generated by:
        
        .. code-block:: python

            from cdxcore.deferred import Create

            a = Create("a")
            b = Create("b")
            _ = a.f( b.g(1) )
            print( _.deferred_info )  # -> '$a.f({$b.g(1)})'
        """
        return self._deferred_info
        
    @property
    def deferred_was_resolved(self) -> bool:
        """ Whether the underlying operation has already been resolved. """
        return self._deferred_was_resolved
        
    @property
    def deferred_dependants(self) -> list:
        """ Retrieve list of dependant :class:`cdxcore.deferred.Deferred` objects. """
        return self._deferred_dependants
        
    @property
    def deferred_source_dependants(self) -> list:
        """
        Retrieve list of dependant :class:`cdxcore.deferred.Deferred` objects at the level of the original parent source.
        This list is in order.
        """
        return self._deferred_src_dependants
        
    @property
    def deferred_sources(self) -> dict:
        """
        Retrieve a dictionary with information on all top-level sources
        this deferred action depends on.
        
        A top level source is an element which must be created explicitly by the user.
        These are the elements generated by :func:'cdxcore.deferred.Create'.

        The list contains a unique ``id`` and the name of the
        source. The ``id`` is used to allow the same name for
        several :func:`Create` elements.
        
        Most users will prefer a simple list of names of sources.
        In that case, use :meth:`cdxcore.deferred.Deferred.deferred_sources_names`.

        """
        return self._deferred_sources
    
    @property
    def deferred_sources_names(self) -> list:
        """
        Retrieve a list of names of all top-level sources
        this deferred action depends on.
        
        A top level source is an element which must be created explicitly by the user.
        These are the elements generated by :func:'cdxcore.deferred.Create'.

        The list returned by this function contains the ``info`` names
        for each of the sources. 

        Example:
        
        .. code-block:: python

            from cdxcore.deferred import Create

            a = Create("a")
            b = Create("b")
            _ = a.f( b.g(1) )
            print( _.deferred_sources_names )  # -> ['$a', '$b']
            
        The purpose of this function is to allow users to detect dependencies on
        source objects and organize resolution code accordingly.
        """
        return list( self.deferred_sources.values() )
    
    @property
    def deferred_result(self):
        """
        Returns the result of the deferred action, if available.
        
        Raises a :class:`RuntimeError` if the action has not been
        executed with :meth:`cdxcore.deferred.Create.deferred_resolve` yet.        
        
        Note that this function might return ``None`` if the resolved
        action had returned ``None``.
        """
        verify( self._deferred_was_resolved, lambda : f"Create action '{self._deferred_info}' has not been executed yet" )
        return self._deferred_live
    
    @property
    def deferred_result_or_self(self):
        """
        Returns the result of the deferred action, if available, or ``self``.
        """
        return self._deferred_live if self._deferred_was_resolved else self
    
    def deferred_print_dependency_tree( self, verbose : Context = Context.all, *, with_sources : bool = False ):
        """ 
        Prints the dependency tree recorded by this object and its descendants.
        
        This function must be called *before* :meth:`cdxcore.deferred.Create.deferred_resolve` is called
        (``deferred_resolve`` clears the dependency tree to free memory).
        
        You can collect this information manually as follows if required:

        .. code-block:: python

            from cdxcore.deferred import Create

            a = Create("a")
            b = Create("b")
            _ = a.f( b.g(1) )
            
            def collect(x,i=0,data=None):
                data = data if not data is None else list()
                data.append((i,x.deferred_info,x.deferred_sources_names))
                for d in x.deferred_dependants:
                    collect(d,i+1,data)
                return data
            for i, info, sources in collect(a):
                print( f"{' '*i} {info} <- {sources}" )    
                
        prints:
            
        .. code-block:: python

             $a <- ['$a']
              $a.f <- ['$a']
               $a.f({$b.g(1)}) <- ['$a', '$b']            
        """
        if with_sources:
            sources = sorted( self._deferred_sources.values() )
            s = ""
            for _ in sources:
                s += _+","
            s = s[:-1]
            verbose.write( lambda : f"{self._deferred_info} <= {s}" )
        else:
            verbose.write( self._deferred_info )
                      
        for d in self._deferred_dependants:
            d.deferred_print_dependency_tree( with_sources=with_sources, verbose=verbose(1) )

    # Resolve
    # =======

    def _deferred_resolve(self, verbose : Context = None ):
        """
        Executes the deferred action with ``parent`` as the subject of the action to be performed.
        
        For example, if the action is ``__getitem__`` parameter ``key``, then this function
        will execute ``parent[key]``, resolve all dependent functions, and then return the
        value of ``parent[key]``.
        """
        if self._deferred_was_resolved:
            return
        verify( self._deferred_action != "", lambda : f"Cannot resolve to level action '{self._deferred_info}' here. Looks like user error, sorry.")
        
        # obtaining the 'parent' object from 
        parent  = self._deferred_parent._deferred_live
        verbose = Context.quiet if verbose is None else verbose
        
        verify( not parent is None, lambda : f"Cannot resolve '{self._deferred_info}': the parent action '{self._deferred_parent_info}' returned 'None'" )
        verify( not isinstance(parent, Deferred), lambda : f"Cannot resolve '{self._deferred_info}' using a 'Deferred'" )
        
        # what action 
        def morph(x):
            if not isinstance(x, Deferred):
                return x
            if x.deferred_was_resolved:
                return x._deferred_live
            raise ResolutionDependencyError(
                    f"Cannot resolve '{self._deferred_info}' with the concrete element of type '{qualified_name(parent)}': "+\
                    f"execution is dependent on yet-unresolved element '{x._deferred_info}'. "+\
                    "Resolve that element first. "+\
                    f"Note: '{self._deferred_info}' is dependent on the following sources: {fmt_list(self._deferred_sources.values(),sort=True)}."    
                    )  
        args   = [ morph(x) for x in self._deferred_args ]        
        kwargs = { k: morph(x) for k,x in self._deferred_kwargs.items() } 
        
        if self._deferred_action == "__getattr__":
            # __getattr__ is not a standard member and cannot be obtained with getattr()
            try:
                live = getattr(parent,*args,**kwargs)
            except AttributeError as e:
                arguments = self._deferred_fmt_args(args,kwargs)
                ppt    = f"provided by '{self._deferred_parent_info}' " if self._deferred_parent_info!="" else ''
                emsg   = f"Cannot resolve '{self._deferred_info}': the concrete element of type '{qualified_name(parent)}' {ppt}"+\
                         f"does not have the requested attribute '{arguments}'."
                e.args = (emsg,) + e.args
                raise e
        else:
            # all other properties -> standard handling
            try:
                action = getattr(parent, self._deferred_action)
            except AttributeError as e:
                ppt    = f"provided by '{self._deferred_parent_info}' " if self._deferred_parent_info!="" else ''
                emsg   = f"Cannot resolve '{self._deferred_info}': the concrete element of type '{qualified_name(parent)}' {ppt}"+\
                         f"does not contain the action '{self._deferred_action}'"
                e.args = (emsg,) + e.args
                raise e
            
            try:
                live  = action( *args, **kwargs )
            except Exception as e:
                arguments = self._deferred_fmt_args(args,kwargs)
                ppt  = f"provided by '{self._deferred_parent_info}' " if self._deferred_parent_info!="" else ''
                emsg = f"Cannot resolve '{self._deferred_info}': when attempting to execute the action '{self._deferred_action}' "+\
                       f"using the concrete element of type '{qualified_name(parent)}' {ppt}"+\
                       f"with parameters '{arguments}' "+\
                       f"an exception was raised: {e}"
                e.args = (emsg,) + e.args
                raise e
            del action
       
        verbose.write(lambda : f"{self._deferred_info} -> '{qualified_name(live)}' : {self._deferred_to_str(live)}")

        # clear object
        # note that as soon as we write to self._deferred_live we can no longer
        # access any information via getattr()/setattr()/delattr().
        # So make sure the parameter scope is released as
        # 'args' and 'kwargs' may hold substantial amounts of memory,
        # For example when this framework is used for delayed
        # plotting with cdxcore.dynaplot
        
        
        self._deferred_kwargs = None
        self._deferred_args   = None
        self._deferred_parent = _ParentDeleted()  # None is a valid parent --> choose someting bad
        
        # action        
        self._deferred_was_resolved = True
        self._deferred_live         = live

    def deferred_resolve(self, element, verbose : Context = None):
        """
        Resolve the top level deferred element.
        
        The top level itself is "resolved" by assigning it 
        concrete object. It will then iterate through all dependent
        deferred actions and attempt to solve those.
        
        This can fail if those calculations are dependent on
        other :func:`cdxcore.deferred.Deferred.Create` which have not been resolved
        yet. In this case a :class:`cdxcore.deferred.ResolutionDependencyError`
        exception will be raised.
        
        Parameters
        ----------
            element :
                The object to resolve ``self`` with.
                
            verbose : :class:`cdxcore.verbose.Context`
                Can be used to provide runtime information on which
                deferred actions are being resolved. Defaults to ``None``
                which surpresses all output.
                
        Returns
        -------
            element
                The input element, so you can chain ``resolve()``.
        """        
        
        verify( self._deferred_action == "", lambda : f"Cannot only resolve top level actions, not '{self._deferred_info}'. Looks like user error, sorry.")
        verify( self._deferred_live is None, lambda : f"Called resolve() twice on '{self._deferred_info}'.")
        verify( not element is None, lambda : f"You cannot resolve '{self._deferred_info}' with an empty 'element'")
        verbose = Context.quiet if verbose is None else verbose
        
        verbose.write(lambda : f"{self._deferred_info} -> '{qualified_name(element)}' : {self._deferred_to_str(element)}")
        self._deferred_live         = element
        self._deferred_was_resolved = True

        while len(self._deferred_src_dependants) > 0:
            daction = self._deferred_src_dependants.pop(0)
            dlevel  = daction._deferred_depth
            daction._deferred_resolve( verbose=verbose(dlevel) )
            del daction 

        return element
    
    # Iteration
    # =========
    # The following are deferred function calls on the object subject of the action ``self``.
    
    def _deferred_act( self, action     : str, *,
                             args       : Collection = [],
                             kwargs     : Mapping = {},
                             num_args   : int|None = None,
                             fmt        : str|None = None
                    ):
        """
        Standard action handling
        
        Parameters
        ----------
            action : str
                The name of the action, e.g. the function name, __getattr__ etc.
            
            args, kwargs :
                Parameters passed to the call.
                
            num_args, fmt : int, str
                If not None then fmt() is a format string which expects ``num_args`` parameters.
        """

        # we already have a live object --> action directly
        if self._deferred_was_resolved:
            if action == "":
                return self._live
            if action == "__getattr__":
                return getattr(self._live, *args, **kwargs)
            try:
                element = getattr(self._deferred_live, action)
            except AttributeError as e:
                emsg = f"Cannot route '{self._deferred_info}' to the object '{qualified_name(self._deferred_live)}' "+\
                       f"provided by '{self._deferred_parent_info}': the object "+\
                       f"does not contain the action '{action}'"
                e.args = (emsg,) + e.args
                raise e
            
            return element(*args, **kwargs)
        
        # format info string
        fmt_args = lambda : self._deferred_fmt_args(args,kwargs)
        if fmt is None:
            verify( num_args is None, f"Error defining action '{action}' for '{self._deferred_info}': cannot specify 'num_args' if 'fmt' is None")
            info = f"{self._deferred_info}.{action}({fmt_args()})"
        else:
            if not num_args is None:
                # specific list of arguments
                verify( num_args is None or len(args) == num_args, lambda : f"Error defining action '{action}' for '{self._deferred_info}': expected {num_args} arguments but found {len(args)}" )
                verify( len(kwargs) == 0, lambda : f"Error defining action '{action}' for '{self._deferred_info}': expected {num_args} ... in this case no kwargs are expected, but {len(kwargs)} keyword arguments where found" )
                verify( not fmt is None, lambda : f"Error defining action '{action}' for '{self._deferred_info}': 'fmt' not specified" )
    
                def label(x):
                    return self._deferred_to_str(x) if not isinstance(x, Deferred) else x.__dict__.get('_deferred_info',action)
                arguments           = { f"arg{i}" : label(arg) for i, arg in enumerate(args) }
                arguments['parent'] = self._deferred_info
                try:
                    info                = fmt.format(**arguments)
                except ValueError as e:
                    raise ValueError( fmt, e, arguments ) from e

            else:
                # __call__
                info = fmt.format(parent=self._deferred_info, args=fmt_args())
        
        # create new action
        deferred  = self.deferred_create_action(
                              info=self._deferred_to_str(info),
                              action=action,
                              # parent
                              parent=self,
                              # arguments
                              args=list(args),
                              kwargs=dict(kwargs)
                              )
        self._deferred_src_dependants.append( deferred )
        self._deferred_dependants.append( deferred )
        return deferred

    # Routed actions
    # --------------
    # We always handle attributes and __call__. 
    # All other handlers need to be implemented in derived classes.
    # We handle __getattr__ and __setattr__ explicitly

    def __getattr__(self, attr ):
        """ Create attribute access """
        private_str = "deferred_"
        #print("__getattr__", attr, self.__dict__.get(private_str+"info", "?"))
        if attr in self.__dict__ or\
                   attr[:2] == "__" or\
                   attr[:len(private_str)] == private_str or\
                   attr[1:1+len(private_str)] == private_str or\
                   not "_ready_for_the_deferred_magic_" in self.__dict__:
            #print("__getattr__: direct", attr)
            try:
                return self.__dict__[attr]
            except KeyError as e:
                raise AttributeError(*e.args, self.__dict__["_deferred_info"]) from e
            except AttributeError as e:
                raise AttributeError(*e.args, self.__dict__["_deferred_info"]) from e
        if not self._deferred_live is None:
            #print("__getattr__: live", attr)
            return getattr(self._deferred_live, attr)
        #print("__getattr__: act", attr)
        return self._deferred_act("__getattr__", args=[attr], num_args=1, fmt="{parent}.{arg0}")
    
    def __setattr__(self, attr, value):
        """ Create attribute access """
        private_str = "deferred_"    
        #print("__getattr__", attr, self.__dict__.get(private_str+"info", "?"))
        if attr in self.__dict__ or\
                   attr[:2] == "__" or\
                   attr[:len(private_str)] == private_str or\
                   attr[1:1+len(private_str)] == private_str or\
                   not "_ready_for_the_deferred_magic_" in self.__dict__:
            try:
                object.__setattr__(self, attr, value)
            except KeyError as e:
                raise AttributeError(*e.args, self.__dict__["_deferred_info"]) from e
            except AttributeError as e:
                raise AttributeError(*e.args, self.__dict__["_deferred_info"]) from e
            #print("__setattr__: direct", attr)
            return
        if not self._deferred_live is None:
            #print("__setattr__: live", attr)
            return setattr(self._deferred_live, attr, value)
        #print("__setattr__: act", attr)
        return self._deferred_act("__setattr__", args=[attr, value], num_args=2, fmt="{parent}.{arg0}={arg1}")

    def __delattr__(self, attr):
        """ Create attribute access """
        private_str = "_deferred_"    
        #print("__delattr__", attr)
        if attr in self.__dict__ or\
                   attr[:2] == "__" or\
                   attr[:len(private_str)] == private_str or\
                   attr[1:1+len(private_str)] == private_str or\
                   not "_ready_for_the_deferred_magic_" in self.__dict__:
            #print("__delattr__: direct", attr)
            try:
                object.__delattr__(self,attr)
            except KeyError as e:
                raise AttributeError(*e.args, self.__dict__[private_str+"info"]) from e
            except AttributeError as e:
                raise AttributeError(*e.args, self.__dict__[private_str+"info"]) from e
            return
        if not self._deferred_live is None:
            #print("__delattr__: live", attr)
            return delattr(self._deferred_live, attr)
        #print("__delattr__: act", attr)
        return self._deferred_act("__delattr__", args=[attr], num_args=1, fmt="del {parent}.{arg0}")

    @staticmethod
    def _deferred_handle( action : str,
                          return_deferred : bool = True, *,
                          num_args : int = None,
                          fmt : str = None ):
        def act(self, *args, **kwargs):
            if not "_ready_for_the_deferred_magic_" in self.__dict__:
                return getattr( self, action )(*args,**kwargs)
            r = self._deferred_act(action, args=args, kwargs=kwargs, num_args=num_args, fmt=fmt )
            return r if return_deferred else self
        act.__name__ = action
        act.__doc__  = f"Create ``{action}`` action"
        return act
    
    @staticmethod
    def _deferred_unsupported( action : str, reason : str ):
        def act(self, *args, **kwargs):
            if not "_ready_for_the_deferred_magic_" in self.__dict__:
                return getattr( self, action )(*args,**kwargs)
            raise NotSupportedError(action, 
                                    f"Deferring action `{action}` for '{self._deferred_info}' is not possible: {reason}")
        act.__name__ = action
        act.__doc__  = f"Create ``{action}`` action"
        return act

    # core functionality
    __call__    = _deferred_handle("__call__", num_args=None, fmt="{parent}({args})")


class DeferAll(Deferred):
    def deferred_create_action( self, **kwargs ):
        """
        Creates a deferred action created during another deferred action.

        This function is called internally if a new action is created. The purpose of this function
        is allowing to implement different deferral overwrite profiles (eg which functions are overwritten).   
        
        The standard implementation is to call the constructor of the desired
        class derived from :class:`cdxcore.deferred.Deferred`.
        """
        return DeferAll( **kwargs )

    _deferred_handle = Deferred._deferred_handle
    _deferred_unsupported = Deferred._deferred_unsupported
    
    __setitem__ = Deferred._deferred_handle("__setitem__", num_args=2, fmt="{parent}[{arg0}]={arg1}")
    __getitem__ = Deferred._deferred_handle("__getitem__", num_args=1, fmt="{parent}[{arg0}]")

    # catch those - usually bad sign
    __bool__    = _deferred_unsupported("__bool__", "'__bool__' must return a 'bool'.")
    __index__   = _deferred_unsupported("__index__", "'__index__' must return an 'int'.")
    # __str__ : implemented
    # __repr__ : implemented
                
    # collections
    __contains__ = _deferred_handle("__contains__", num_args=1, fmt="({arg0} in {parent})")
    __iter__     = _deferred_handle("__iter__")
    __len__      = _deferred_handle("__len__", num_args=0, fmt="len({parent})")

    # comparison operators
    __eq__      = _deferred_handle("__eq__", num_args=1, fmt="({parent}!={arg0})")   # ** handle with care - interferes with lists **
    __neq__     = _deferred_handle("__neq__", num_args=1, fmt="({parent}!={arg0})")
    __ge__      = _deferred_handle("__ge__", num_args=1, fmt="({parent}>={arg0})")
    __le__      = _deferred_handle("__le__", num_args=1, fmt="({parent}<={arg0})")
    __gt__      = _deferred_handle("__gt__", num_args=1, fmt="({parent}>{arg0})")
    __lt__      = _deferred_handle("__lt__", num_args=1, fmt="({parent}<{arg0})")

    # core functionality
    __call__    = _deferred_handle("__call__", num_args=None, fmt="{parent}({args})")
    __setitem__ = _deferred_handle("__setitem__", num_args=2, fmt="{parent}[{arg0}]={arg1}")
    __getitem__ = _deferred_handle("__getitem__", num_args=1, fmt="{parent}[{arg0}]")

    # unitary
    __abs__      = _deferred_handle("__abs__", True, num_args=0, fmt="|{parent}|")

    # unitary
    __abs__      = _deferred_handle("__abs__", True, num_args=0, fmt="|{parent}|")
    
    # i*
    __ior__      = _deferred_handle("__ior__", False, num_args=1, fmt="{parent}|={arg0}")
    __iand__     = _deferred_handle("__iand__", False, num_args=1, fmt="{parent}&={arg0}")
    __ixor__     = _deferred_handle("__iand__", False, num_args=1, fmt="{parent}^={arg0}")
    __imod__     = _deferred_handle("__imod__", False, num_args=1, fmt="{parent}%={arg0}")
    __iadd__     = _deferred_handle("__iadd__", False, num_args=1, fmt="{parent}+={arg0}")
    __iconcat__  = _deferred_handle("__iconcat__", False, num_args=1, fmt="{parent}+={arg0}")
    __isub__     = _deferred_handle("__isub__", False, num_args=1, fmt="{parent}-={arg0}")
    __imul__     = _deferred_handle("__imul__", False, num_args=1, fmt="{parent}*={arg0}")
    __imatmul__  = _deferred_handle("__imatmul__", False, num_args=1, fmt="{parent}@={arg0}")
    __ipow__     = _deferred_handle("__ipow__", False, num_args=1, fmt="{parent}**={arg0}")
    __itruediv__ = _deferred_handle("__itruediv__", False, num_args=1, fmt="{parent}/={arg0}")
    __ifloordiv__ = _deferred_handle("__ifloordiv__", False, num_args=1, fmt="{parent}//={arg0}")
    
    # binary
    __or__       = _deferred_handle("__or__", num_args=1, fmt="({parent}|{arg0})")
    __and__      = _deferred_handle("__and__", num_args=1, fmt="({parent}&{arg0})")
    __xor__      = _deferred_handle("__xor__", num_args=1, fmt="({parent}^{arg0})")
    __mod__      = _deferred_handle("__mod__", num_args=1, fmt="({parent}%{arg0})")
    __add__      = _deferred_handle("__add__", num_args=1, fmt="({parent}+{arg0})")
    __concat__   = _deferred_handle("__concat__", num_args=1, fmt="({parent}+{arg0})")
    __sub__      = _deferred_handle("__sub__", num_args=1, fmt="({parent}-{arg0})")
    __mul__      = _deferred_handle("__mul__", num_args=1, fmt="({parent}*{arg0})")
    __pow__      = _deferred_handle("__pow__", num_args=1, fmt="({parent}**{arg0})")
    __matmul__   = _deferred_handle("__matmul__", num_args=1, fmt="({parent}@{arg0})")
    __truediv__  = _deferred_handle("__truediv__", num_args=1, fmt="({parent}/{arg0})")
    __floordiv__ = _deferred_handle("__floordiv__", num_args=1, fmt="({parent}//{arg0})")

    # rbinary
    __ror__       = _deferred_handle("__ror__", num_args=1,      fmt="({arg0}|{parent})")
    __rand__      = _deferred_handle("__rand__", num_args=1,     fmt="({arg0}&{parent})")
    __rxor__      = _deferred_handle("__rxor__", num_args=1,     fmt="({arg0}^{parent})")
    __rmod__      = _deferred_handle("__rmod__", num_args=1,     fmt="({arg0}%{parent})")
    __radd__      = _deferred_handle("__radd__", num_args=1,     fmt="({arg0}+{parent})")
    __rconcat__   = _deferred_handle("__rconcat__", num_args=1,  fmt="({arg0}+{parent})")
    __rsub__      = _deferred_handle("__rsub__", num_args=1,     fmt="({arg0}-{parent})")
    __rmul__      = _deferred_handle("__rmul__", num_args=1,     fmt="({arg0}*{parent})")
    __rpow__      = _deferred_handle("__rpow__", num_args=1,     fmt="({arg0}**{parent})")
    __rmatmul__   = _deferred_handle("__rmatmul__", num_args=1,  fmt="({arg0}@{parent})")
    __rtruediv__  = _deferred_handle("__rtruediv__", num_args=1, fmt="({arg0}/{parent})")
    __rfloordiv__ = _deferred_handle("__rfloordiv__", num_args=1,fmt="({arg0}//{parent})")
    
