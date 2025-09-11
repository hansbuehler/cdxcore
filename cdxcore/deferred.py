"""
Overview
--------

Framework for delayed execution of a Python code tree.

Used by :mod:`cdxcore.dnaplot`.

Import
------

.. code-block:: python

    from cdxcore.deferrred import Deferred

"""

from .err import verify
from. util import qualified_name, fmt_list
from .verbose import Context
from collections.abc import Collection, Sequence, Mapping
import gc as gc

class _ParentDeleted:
    pass

class ResolutionDependencyError(RuntimeError):
    """
    Exeception if the resolution of a deferred action failed because one
    of its source items has not been resolved.
    """
    pass        
   
class DeferredAction(object):
    """
    A deferred action keeps track of an action dependency tree
    for an object which has not been created, yet.
    
    This class is returned by :class:`cdxcore.deferred.Deferred`.
    
    The aim is to be able to record a sequence of actions on a placeholder
    for an object which does not yet exist
    such as function calls, item access, or attribute access,
    and store the resulting logical dependency tree. Once the target
    element is available, execute the dependency tree iteratively.

    A basic example is as follows: assume we have a class ``A`` of which
    we will create an object ``a``, but only at a later stage. We
    wish to record a list of deferred actions on ``a`` ahead of its creation.

    Define the class::
        
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

    Use :class:`cdxcore.deferred.Deferred` to create a root ``DeferredAction`` object::
        
        from cdxcore.deferred import Deferred
        da = Deferred("A")
        
    Record a few actions::

        af = da.a_func(1)    # defer function call to a_func(1)
        ai = da[2]           # defer item access
        aa = da.x            # defer attribute access

    :class:`cdxcore.deferred.DeferredAction` works iteratively, e.g. all values returned from a function call, ``__call__``, or ``__getitem__``
    are themselves deferred automatically.`:class:`cdxcore.deferred.DeferredAction` is also able to defer item and attribute assignments.
    
    As an example::

        an = da.another()
        an = an.another()     # call a.another().another() --> an.x = 1*2*2 = 4
        
    Finally, resolve the execution by instantiating ``A`` and calling :meth:`cdxcore.deferred.DeferredAction.deferred_resolve`::

        a = A()
        da.deferred_resolve( a )
        
        print( an.x )         # -> 4

    This functionality is used in :mod:`cdxcore.dynaplot`::

        from cdxcore.dynaplot import figure

        fig = figure()                # the DynanicFig returned by figure() is derived from DeferredAction
        ax  = fig.add_subplot()       # Deferred call for add_subplot()
        lns = ax.plot( x, y )[0]      # This is a deferred call to plot() and then [0].
        fig.render()                  # renders the figure and executes plot() then [0]
        lns.set_ydata( y2 )           # we can now access the resulting Line2D object via the DeferredAction wrapper
        fig.close()                   # update graph
    
    **Constructor**
    
    External applications do not usually need to directly create objects
    of type :class:`cdxcore.deferred.DeferredAction`. Use :class:`cdxcore.deferred.Deferred`
    as top level entry point.
    """

    def __init__(self, *, action         : str,       #: :meta private:
                          info           : str,       #: :meta private:
                          parent         : type,      #: :meta private:
                          src_dependants : list,      #: :meta private:
                          sources        : dict,      #: :meta private:
                          args           : Collection,#: :meta private: 
                          kwargs         : Mapping,   #: :meta private:
                          max_err_len    : int,       #: :meta private:
                          ):
        """
        Initialize a deferred action.
        :meta private:
        """
        self._deferred_max_err_len  = max_err_len
        
        verify( isinstance(info, str), lambda : f"'info' must be a string; found {self._deferred_to_str(info)}.", exception=ValueError)
        verify( parent is None or isinstance(parent, DeferredAction), lambda : f"'parent' must be a DeferredAction; found {type(parent)}.", exception=ValueError)
        verify( isinstance(action, str), lambda : f"'action' must be a string; found {self._deferred_to_str(action)}.", exception=ValueError)
        verify( isinstance(args, (Sequence,Collection)), lambda : f"'args' must be a Collection; found {type(args)}.", exception=ValueError)
        verify( isinstance(kwargs, Mapping), lambda : f"'kwargs' must be a Mapping; found {type(kwargs)}.", exception=ValueError)
        
        if action == "":
            verify( len(info)>0 and
                    len(args) == 0 and
                    parent is None and
                    len(sources) == 0 and
                    len(kwargs) == 0, "Must specify 'info' but cannot specify 'sources', 'parent', 'args', or 'kwargs' for the root action \"\"", exception=ValueError)
        
        self._deferred_action         = action              # action code
        self._deferred_parent         = parent
        self._deferred_depth          = parent._deferred_depth+1 if not parent is None else 0
        self._deferred_args           = args
        self._deferred_kwargs         = kwargs
        self._deferred_live           = None           # once the object exists, it goes here.
        self._deferred_was_resolved   = False          # whether the action was executed.
        self._deferred_dependants     = []             # list of all direct dependent actions
        self._deferred_src_dependants = src_dependants
        
        if action == "":
            info            = "$"+info
            self._deferred_sources  = {id(self):info}
            self._deferred_info     = info
        else:
            self._deferred_sources  = sources
            self._deferred_info     = info
        
        self.__dict__["_ready_for_the_deferred_magic_"] = 1

    @property
    def _deferred_parent_info(self) -> str:
        return self._deferred_parent._deferred_info if not self._deferred_parent is None else ""

    def _deferred_to_str( self, x ):
        """ Limit string 'x' to ``max_err_len`` by adding ``...`` if necessary. """
        x = str(x)
        if len(x) > self._deferred_max_err_len:
            if x[-1] in [')', ']', '}']:
                x = x[:self._deferred_max_err_len-4] + "..." + x[-1]
            else:
                x = x[:self._deferred_max_err_len-3] + "..." 
        return x
    
    def _deferred_to_argstr( self, x ):
        if isinstance(x, DeferredAction):
            if not x.deferred_was_resolved:
                return f"{{{x._deferred_info}}}"    
            x = x._deferred_live
        return str(x)

    def _deferred_fmt_args(self, args, kwargs ):
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
        
        Top level sources are indicated by a ``$``. Curly brackets ``{}`` indicate
        deferred actions themselves. For example:
        
        .. code-block:: python
        
            $a.f({$b.g(1)})
            
        Is generated by:
        
        .. code-block:: python

            from cdxcore.deferred import Deferred

            a = Deferred("a")
            b = Deferred("b")
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
        """ Retrieve list of dependant :class:`cdxcore.deferred.DeferredAction` objects. """
        return self._deferred_dependants
        
    @property
    def deferred_sources(self) -> dict:
        """
        Retrieve a dictionary with information on all top-level sources
        this deferred action depends on.
        
        A top level source is an element which must be created explicitly by the user.
        These are the elements generated by :func:'cdxcore.deferred.Deferred'.

        The list contains a unique ``id`` and the name of the
        source. The ``id`` is used to allow the same name for
        several :func:`Deferred` elements.
        
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
        These are the elements generated by :func:'cdxcore.deferred.Deferred'.

        The list returned by this function contains the ``info`` names
        for each of the sources. 

        Example:
        
        .. code-block:: python

            from cdxcore.deferred import Deferred

            a = Deferred("a")
            b = Deferred("b")
            _ = a.f( b.g(1) )
            print( _.deferred_sources_names )  # -> ['$a', '$b']
            
        The purpose of this function is to allow users to detect dependencies on
        source objects and organize resolution code accordingly.
        """
        return list( self.deferred_sources.values() )
    
    @property
    def deferred_action_result(self):
        """
        Returns the result of the deferred action, if available.
        
        Raises a :class:`RuntimeError` if the action has not been
        executed with :meth:`cdxcore.deferred.Deferred.deferred_resolve` yet.        
        
        Note that this function might return ``None`` if the resolved
        action had returned ``None``.
        """
        verify( self._deferred_was_resolved, lambda : f"Deferred action '{self._deferred_info}' has not been executed yet" )
        return self._deferred_live
    
    def deferred_print_dependency_tree( self, verbose : Context = Context.all, *, with_sources : bool = False ):
        """ 
        Prints the dependency tree recorded by this object and its descendants.
        
        This function must be called *before* :meth:`cdxcore.deferred.Deferred.deferred_resolve` is called
        (``deferred_resolve`` clears the dependency tree to free memory).
        
        You can collect this information manually as follows if required:

        .. code-block:: python

            from cdxcore.deferred import Deferred

            a = Deferred("a")
            b = Deferred("b")
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
            verbose.write( f"{self._deferred_info} <= {s}" )
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
        verify( not isinstance(parent, DeferredAction), lambda : f"Cannot resolve '{self._deferred_info}' using a 'DeferredAction'" )
        
        # what action 
        def morph(x):
            if not isinstance(x, DeferredAction):
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
       
        verbose.write(f"{self._deferred_info} -> '{qualified_name(live)}' : {self._deferred_to_str(live)}")

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
        gc.collect()
        
        # action        
        self._deferred_was_resolved = True
        self._deferred_live         = live

    # Iteration
    # =========
    # The following are deferred function calls on the object subject of the action ``self``.
    
    def _act( self, action     : str, *,
                    args       : Collection = [],
                    kwargs     : Mapping = {},
                    num_args   : int = None,
                    fmt        : str = None
                    ):
        """ Standard action handling """

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
                verify( num_args is None or len(args) == num_args, lambda : f"Error defining action '{action}' for '{self._deferred_info}': expected {num_args} but found {len(args)}" )
                verify( len(kwargs) == 0, lambda : f"Error defining action '{action}' for '{self._deferred_info}': expected {num_args} ... in this case no kwargs are expected, but {len(kwargs)} where found" )
                verify( not fmt is None, lambda : f"Error defining action '{action}' for '{self._deferred_info}': 'fmt' not specified" )
    
                def label(x):
                    return x if not isinstance(x, DeferredAction) else x._deferred_info
                arguments           = { f"arg{i}" : label(arg) for i, arg in enumerate(args) }
                arguments['parent'] = self._deferred_info
                try:
                    info                = fmt.format(**arguments)
                except ValueError as e:
                    raise ValueError( fmt, e, arguments ) from e

            else:
                # __call__
                info = fmt.format(parent=self._deferred_info, args=fmt_args())
        
        # detected dependencies in arguments on other
        sources = dict(self._deferred_sources)
        for x in args:
            if isinstance(x, DeferredAction):
                sources |= x._deferred_sources
        for x in kwargs.values():
            if isinstance(x, DeferredAction):
                sources |= x._deferred_sources
        
        # create new action
        deferred  = DeferredAction( 
                              action=action,
                              parent=self,
                              info=self._deferred_to_str(info),
                              args=list(args),
                              kwargs=dict(kwargs),
                              max_err_len=self._deferred_max_err_len,
                              sources=sources,
                              src_dependants=self._deferred_src_dependants,
                              )
        self._deferred_src_dependants.append( deferred )
        self._deferred_dependants.append( deferred )
        return deferred

    # Routed actions
    # --------------
    # We handle __getattr__ and __setattr__ explicitly

    def __getattr__(self, attr ):
        """ Deferred attribute access """
        private_str = "_deferred_"    
        #print("__getattr__", attr, self.__dict__.get(private_str+"info", "?"))
        #print("  ", self.__dict__)
        if attr in self.__dict__ or\
                   attr[:2] == "__" or\
                   attr[:len(private_str)] == private_str or\
                   not "_ready_for_the_deferred_magic_" in self.__dict__:
            #print("__getattr__: direct", attr)
            try:
                return self.__dict__[attr]
            except KeyError as e:
                raise AttributeError(*e.args, self.__dict__[private_str+"info"]) from e
        if not self._deferred_live is None:
            #print("__getattr__: live", attr)
            return getattr(self._deferred_live, attr)
        #print("__getattr__: act", attr)
        return self._act("__getattr__", args=[attr], num_args=1, fmt="{parent}.{arg0}")
    
    def __setattr__(self, attr, value):
        """ Deferred attribute access """
        private_str = "_deferred_"    
        #print("__getattr__", attr, self.__dict__.get(private_str+"info", "?"))
        if attr in self.__dict__ or\
                   attr[:2] == "__" or\
                   attr[:len(private_str)] == private_str or\
                   not "_ready_for_the_deferred_magic_" in self.__dict__:
            try:
                self.__dict__[attr] = value
            except KeyError as e:
                raise AttributeError(*e.args, self.__dict__[private_str+"info"]) from e
            #print("__setattr__: direct", attr)
            return
        if not self._deferred_live is None:
            #print("__setattr__: live", attr)
            return setattr(self._deferred_live, attr, value)
        #print("__setattr__: act", attr)
        return self._act("__setattr__", args=[attr, value], num_args=2, fmt="{parent}.{arg0}={arg1}")

    def __delattr__(self, attr):
        """ Deferred attribute access """
        private_str = "_deferred_"    
        #print("__delattr__", attr)
        if attr in self.__dict__ or\
                   attr[:2] == "__" or\
                   attr[:len(private_str)] == private_str or\
                   not "_ready_for_the_deferred_magic_" in self.__dict__:
            #print("__delattr__: direct", attr)
            try:
                del self.__dict__[attr]
            except KeyError as e:
                raise AttributeError(*e.args, self.__dict__[private_str+"info"]) from e
            return
        if not self._deferred_live is None:
            #print("__delattr__: live", attr)
            return delattr(self._deferred_live, attr)
        #print("__delattr__: act", attr)
        return self._act("__delattr__", args=[attr], num_args=1, fmt="del {parent}.{arg0}")

    @staticmethod
    def _generate_handle( action : str,
                          return_deferred : bool = True, *,
                          num_args : int = None,
                          fmt : str = None ):
        def act(self, *args, **kwargs):
            r = self._act(action, args=args, kwargs=kwargs, num_args=num_args, fmt=fmt )
            return r if return_deferred else self
        act.__name__ = action
        act.__doc__  = f"Deferred ``{action}`` action"
        return act
    
    # core functionality
    __call__    = _generate_handle("__call__", num_args=None, fmt="{parent}({args})")
    __setitem__ = _generate_handle("__setitem__", num_args=2, fmt="{parent}[{arg0}]={arg1}")
    __getitem__ = _generate_handle("__getitem__", num_args=1, fmt="{parent}[{arg0}]")

    # collections
    __contains__ = _generate_handle("__contains__", num_args=1, fmt="({arg0} in {parent})")
    __iter__     = _generate_handle("__iter__")
    __len__      = _generate_handle("__len__", num_args=0, fmt="len({parent})")
    __hash__     = _generate_handle("__hash__", num_args=0, fmt="hash({parent})")

    # cannot implement __bool__, __str__, or, __repr__ as these
    # have defined return types

    # comparison operators
    __neq__     = _generate_handle("__neq__", num_args=1, fmt="({parent}!={arg0})")
    __eq__      = _generate_handle("__eq__", num_args=1, fmt="({parent}=={arg0})")
    __ge__      = _generate_handle("__ge__", num_args=1, fmt="({parent}>={arg0})")
    __le__      = _generate_handle("__le__", num_args=1, fmt="({parent}<={arg0})")
    __gt__      = _generate_handle("__gt__", num_args=1, fmt="({parent}>{arg0})")
    __lt__      = _generate_handle("__lt__", num_args=1, fmt="({parent}<{arg0})")
    
    # i*
    __ior__      = _generate_handle("__ior__", False, num_args=1, fmt="{parent}|={arg0}")
    __iand__     = _generate_handle("__iand__", False, num_args=1, fmt="{parent}&={arg0}")
    __ixor__     = _generate_handle("__iand__", False, num_args=1, fmt="{parent}^={arg0}")
    __imod__     = _generate_handle("__imod__", False, num_args=1, fmt="{parent}%={arg0}")
    __iadd__     = _generate_handle("__iadd__", False, num_args=1, fmt="{parent}+={arg0}")
    __iconcat__  = _generate_handle("__iconcat__", False, num_args=1, fmt="{parent}+={arg0}")
    __isub__     = _generate_handle("__isub__", False, num_args=1, fmt="{parent}-={arg0}")
    __imul__     = _generate_handle("__imul__", False, num_args=1, fmt="{parent}*={arg0}")
    __imatmul__  = _generate_handle("__imatmul__", False, num_args=1, fmt="{parent}@={arg0}")
    __ipow__     = _generate_handle("__ipow__", False, num_args=1, fmt="{parent}**={arg0}")
    __itruediv__ = _generate_handle("__itruediv__", False, num_args=1, fmt="{parent}/={arg0}")
    __ifloordiv__ = _generate_handle("__ifloordiv__", False, num_args=1, fmt="{parent}//={arg0}")
    # Py2 __idiv__     = _generate_handle("__idiv__", False, num_args=1, fmt="{parent}/={arg0}")
    
    # binary
    __or__       = _generate_handle("__or__", num_args=1, fmt="({parent}|{arg0})")
    __and__      = _generate_handle("__and__", num_args=1, fmt="({parent}&{arg0})")
    __xor__      = _generate_handle("__xor__", num_args=1, fmt="({parent}^{arg0})")
    __mod__      = _generate_handle("__mod__", num_args=1, fmt="({parent}%{arg0})")
    __add__      = _generate_handle("__add__", num_args=1, fmt="({parent}+{arg0})")
    __concat__   = _generate_handle("__concat__", num_args=1, fmt="({parent}+{arg0})")
    __sub__      = _generate_handle("__sub__", num_args=1, fmt="({parent}-{arg0})")
    __mul__      = _generate_handle("__mul__", num_args=1, fmt="({parent}*{arg0})")
    __pow__      = _generate_handle("__pow__", num_args=1, fmt="({parent}**{arg0})")
    __matmul__   = _generate_handle("__matmul__", num_args=1, fmt="({parent}@{arg0})")
    __truediv__  = _generate_handle("__truediv__", num_args=1, fmt="({parent}/{arg0})")
    __floordiv__ = _generate_handle("__floordiv__", num_args=1, fmt="({parent}//{arg0})")
    # Py2__div__      = _generate_handle("__div__", num_args=1, fmt="({parent}/{arg0})")

    # rbinary
    __ror__       = _generate_handle("__ror__", num_args=1,      fmt="({arg0}|{parent})")
    __rand__      = _generate_handle("__rand__", num_args=1,     fmt="({arg0}&{parent})")
    __rxor__      = _generate_handle("__rxor__", num_args=1,     fmt="({arg0}^{parent})")
    __rmod__      = _generate_handle("__rmod__", num_args=1,     fmt="({arg0}%{parent})")
    __radd__      = _generate_handle("__radd__", num_args=1,     fmt="({arg0}+{parent})")
    __rconcat__   = _generate_handle("__rconcat__", num_args=1,  fmt="({arg0}+{parent})")
    __rsub__      = _generate_handle("__rsub__", num_args=1,     fmt="({arg0}-{parent})")
    __rmul__      = _generate_handle("__rmul__", num_args=1,     fmt="({arg0}*{parent})")
    __rpow__      = _generate_handle("__rpow__", num_args=1,     fmt="({arg0}**{parent})")
    __rmatmul__   = _generate_handle("__rmatmul__", num_args=1,  fmt="({arg0}@{parent})")
    __rtruediv__  = _generate_handle("__rtruediv__", num_args=1, fmt="({arg0}/{parent})")
    __rfloordiv__ = _generate_handle("__rfloordiv__", num_args=1,fmt="({arg0}//{parent})")
    # Py2__rdiv__      = _generate_handle("__rdiv__", num_args=1,     fmt="({arg0}/{parent})")
 
class Deferred(DeferredAction):
    """
    Create a :class:`cdxcore.deferred.DeferredAction` object to keep track
    of a dependency tree of a sequence of actions performed an object
    that does not yet exist.
    
    See :class:`cdxcore.deferred.DeferredAction` for a comprehensive discussion.

    Parameters
    ----------
    info : str
        Descriptive name of the usually not-yet-created object deferred actions
        will act upon.
        
    max_err_len : int, optional
        Maximum length of output information. The default is 100.

    Returns
    -------
    :class:`cdxcore.deferred.DeferredAction`
        A deferred action.
    """
    
    def __init__(self,  info         : str,
                        max_err_len  : int = 100 ):
        """ Init """       
        self._deferred_src_dependants = []
        
        DeferredAction.__init__(  
                           self,
                           info=info,
                           action="", 
                           parent=None, 
                           src_dependants=self._deferred_src_dependants,
                           sources={},
                           args=[], 
                           kwargs={},
                           max_err_len=max_err_len )
        
        assert self._deferred_live is None
    

    def deferred_resolve(self, element, verbose : Context = None):
        """
        Resolve the top level deferred element.
        
        The top level itself is "resolved" by assigning it 
        concrete object. It will then iterate through all dependent
        deferred actions and attempt to solve those.
        
        This can fail if those calculations are dependent on
        other :class:`cdxcore.deferred.Deferred` which have not been resolved
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
        
        verify( self._deferred_live is None, lambda : f"Called resolve() twice on '{self._deferred_info}'.")
        verify( not element is None, lambda : f"You cannot resolve '{self._deferred_info}' with an empty 'element'")
        verbose = Context.quiet if verbose is None else verbose
        
        verbose.write(f"{self._deferred_info} -> '{qualified_name(element)}' : {self._deferred_to_str(element)}")
        self._deferred_live         = element
        self._deferred_was_resolved = True

        while len(self._deferred_src_dependants) > 0:
            daction = self._deferred_src_dependants.pop(0)
            dlevel  = daction._deferred_depth
            daction._deferred_resolve( verbose=verbose(dlevel) )
            del daction 
            
        gc.collect()
        return element
    
    