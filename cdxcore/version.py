r"""
Overview
--------

This module provides a framework to track versions of functions, classes, and their members via a simple decorating mechanism
implemented with :dec:`cdxcore.verson.version`.

A main application is the use in caching results of computational intensive tasks such as data pipelines in machine learning. The version
framework allows updating dynamically only those parts of the data dependency graph whose code generation logic has changed.
Correspondingly, :class:`cdxcore.subdir.SubDir` supports fast light-weight file based read/write support for versioned files.

A full caching logic is implemented using :dec:`cdxcore.subdir.SubDir.cache`.

Versioned Functions
^^^^^^^^^^^^^^^^^^^

For versioning, basic use is straight forward and self-explanatory::

    from cdxbasics.version import version

    @version("0.0.1")
    def f(x):
        return x

    print( f.version.full )   # -> 0.0.1

Dependencies are declared with the ``dependencies`` keyword::

    @version("0.0.2", dependencies=[f])
    def g(x):
        return f(x)

    print( g.version.input )  # -> 0.0.2
    print( g.version.full )   # -> 0.0.2 { f: 0.0.01 }

You have access to ``version`` from within the function::

    @version("0.0.2", dependencies=[f])
    def g(x):
        print(g.version.full) # -> 0.0.2 { f: 0.0.01 }
        return f(x)
    g(1)
    
You can also use strings to refer to dependencies.
This functionality depends on visibility of the referred dependencies by the function in the
function's ``__global__`` scope::

    @version("0.0.4", dependencies=['f'])
    def r(x):
        return x

    print( r.version.full )    # -> 0.0.4 { f: 0.0.01 }

Versioned Classes
^^^^^^^^^^^^^^^^^
    
This works with classes, too::

    @version("0.0.3", dependencies=[f] )
    class A(object):
        def h(self, x):
            return f(x)

    print( A.version.input )  # -> 0.0.3
    print( A.version.full )   # -> 0.0.3 { f: 0.0.01 }

    a = A()
    print( a.version.input )  # -> 0.0.3
    print( a.version.full )   # -> 0.0.3 { f: 0.0.01 }

Dependencies on base classes are automatic::

    @version("0.0.1")
    class A(object):
        pass

    @version("0.0.2")
    class B(A):
        pass

    print( B.version.full )   # -> 0.0.2 { A: 0.0.1 }
    
Member functions are automatically dependent on their defining class::

    from cdxcore.version import version
    
    class A(object):
        def __init__(self, x=2):
            self.x = x
        @version(version="0.4.1")
        def h(self, y):
            return self.x*y
    
    @version(version="0.3.0")
    def h(x,y):
        return x+y
    
    @version(version="0.0.2", dependencies=[h])
    def f(x,y):
        return h(y,x)
    
    @version(version="0.0.1", dependencies=["f", A.h])
    def g(x,z):
        a = A()
        return f(x*2,z)+a.h(z)
    
    g(1,2)
    print("version", g.version.input)                # -> version 0.0.1
    print("full version", g.version.full )           # -> full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    print("full version ID",g.version.unique_id48 )  # -> full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    print("full version ID",g.version.unique_id32 )  # -> full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    print("depedencies",g.version.dependencies )     # -> depedencies ('0.0.1', {'f': ('0.0.2', {'h': '0.3.0'}), 'A.h': '0.4.1'})

Decorated Function Information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A decorated function or class has a member ``version`` of type :class:`cdxcore.version.Version` which has the following
key properties:

* :attr:`cdxcore.version.Version.input`: the input version as defined with :dec:`cdxcore.version.version`.
* :attr:`cdxcore.version.Version.full`: a fully qualified version with all dependent functions and classes in human readable form.
* :attr:`cdxcore.version.Version.unique_id48`,
  :attr:`cdxcore.version.Version.unique_id64`:
  unique hashes of :attr:`cdxcore.version.Version.full` of 48 or 64 characters,
  respectively. You can use the function :meth:`cdxcore.version.Version.unique_id`
  to compute hash IDs of any length.
* :attr:`cdxcore.version.Version.dependencies`: a hierarchical list of dependencies for systematic inspection.

Import
------
.. code-block:: python

    from cdxcore.version import version

Documentation
-------------
"""
import inspect as inspect
from .util import fmt_list
from .uniquehash import UniqueLabel
from collections.abc import Callable

uniqueLabel64 = UniqueLabel(max_length=64,id_length=8)
uniqueLabel60 = UniqueLabel(max_length=60,id_length=8)
uniqueLabel48 = UniqueLabel(max_length=48,id_length=8)

class VersionDefinitionError(RuntimeError):
    """
    Error rasied if an error occured during version definition.
    """
    def __init__(self, context, message):
        RuntimeError.__init__(self, context, message)

class VersionError(RuntimeError):
    """
    Standardized error type to be raised by applications if a version found did not match an expected
    version. 
    """
    def __init__(self, *args, version_found : str, version_expected : str ):
        self.version_found = version_found        #: The version found.
        self.version_expected = version_expected  #: The version expected. 
        RuntimeError.__init__(self, *args)

class Version(object):
    """
    Class to track version dependencies for a given function or class.
    
    This class is used by :dec:`cdxcore.subdir.version`. Developers will typically access
    it via a decorated function's ``version`` property.

    **Key Properties**
    
    * :attr:`cdxcore.version.Version.input`: input version string as provided by the user.
    
    * :attr:`cdxcore.version.Version.full`: qualified full version including versions of dependent
      functions or classes, as a string.

    * :attr:`cdxcore.version.Version.unique_id48`:
      48 character unique ID. Versions for 60 and 64 characters are also 
      pre-defined.
    
    * :attr:`cdxcore.version.Version.dependencies`: hierarchy of version dependencies as a list.
    
    **Dependency Resolution**
    
    Dependency resolution is lazy to allow creating dependencies on Python elements which are defined later / elsewhere.
    If an error occurs during dependency resoution an exception of type :class:`cdxcore.version.VersionDefinitionError` is raised.    
    
    Parameters
    ----------
    original : Callable
        Orignal Python element: a function, class, or member function.

    version : str, optional
        User version string for ``original``.
        
    dependencies : list[type], optional
        List of dependencies as types (preferably) or string names.
        
    auto_class : bool, optional
        Whether to automatically make classes dependent on their (versioned) base classes,
        and member functions on their (versioned) containing classes.    
    """

    def __init__(self, original : Callable, version : str, dependencies : list[type], auto_class : bool ):
        """
        :meta private:
        """
        if version is None:
            raise ValueError("'version' cannot be None")
        self._original           = original
        self._input_version      = str(version)
        self._input_dependencies = list(dependencies) if not dependencies is None else list()
        self._dependencies       = None
        self._class              = None  # class defining this function
        self._auto_class         = auto_class

    def __str__(self) -> str:
        """ Returns qualified version string. """
        return self.full

    def __repr__(self) -> str:
        """ Returns qualified version string. """
        return self.full

    def __eq__(self, other) -> bool:
        """ Tests equality of two versions """
        other = other.full if isinstance(other, Version) else str(other)
        return self.full == other

    def __neq__(self, other) -> bool:
        """ Tests inequality of two versions """
        other = other.full if isinstance(other, Version) else str(other)
        return self.full != other
    
    @property
    def input(self) -> str:
        """ Returns the input version of this function. """
        return self._input_version

    @property
    def unique_id64(self) -> str:
        """
        Returns a unique version string for this version of at most 64 characters.
        
        Returns either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 64 characters.
        """
        return uniqueLabel64(self.full)

    @property
    def unique_id60(self) -> str:
        """
        Returns a unique version string for this version of at most 60 characters.
        
        Returns either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 60 characters.
        """
        return uniqueLabel60(self.full)

    @property
    def unique_id48(self) -> str:
        """
        Returns a unique version string for this version of at most 48 characters.
        
        Returns either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 48 characters.
        """
        return uniqueLabel48(self.full)

    def unique_id(self, max_len : int = 64) -> str:
        """
        Returns a unique version string for this version of at most the specified number of characters.
        
        Returns either the simple readable version or the current version plus a unique hash if the
        simple version exceeds ``max_len`` characters.
        """
        assert max_len >= 4,("'max_len' must be at least 4", max_len)
        id_len = 8 if max_len > 16 else 4
        uniqueHashVersion = UniqueLabel(max_length=max_len, id_length=id_len)
        return uniqueHashVersion(self.full)

    @property
    def full(self) -> str:
        """
        Returns information on the version of ``self`` and all dependent elements
        in human readable form.
        
        Elements are sorted by name, hence this representation
        can be used to test equality between two versions (:class:`cdxcore.version.Version`
        implements ``==`` and ``!=`` based on ``full``).
        """
        self._resolve_dependencies()
        def respond( deps ):
            if isinstance(deps,str):
                return deps
            s = ""
            d = deps[1]
            keys = sorted(list(d.keys()))
            for k in keys:
                v = d[k]
                r = k + ": " + respond(v)
                s = r if s=="" else s + ", " + r
            s += " }"
            s = deps[0] + " { " + s
            return s
        return respond(self._dependencies)

    @property
    def dependencies(self):
        """
        Returns information on the version of ``self`` and all dependent elements.

        For a given function the format is as follows:
            
        * If the element has no dependents::
            
            "version"
            
        * If the function has dependencies, return recursively::
            
            ( "version", { dependency: dependency.version_full() } )
            
        **Example**::
            
            from cdxcore.version import version
            
            class A(object):
                def __init__(self, x=2):
                    self.x = x
                @version(version="0.4.1")
                def h(self, y):
                    return self.x*y
            
            @version(version="0.3.0")
            def h(x,y):
                return x+y
            
            @version(version="0.0.2", dependencies=[h])
            def f(x,y):
                return h(y,x)
            
            @version(version="0.0.1", dependencies=["f", A.h])
            def g(x,z):
                a = A()
                return f(x*2,z)+a.h(z)
            
            g(1,2)
            print("version", g.version.input)                # -> version 0.0.1
            print("full version", g.version.full )           # -> full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
            print("depedencies",g.version.dependencies )     # -> depedencies ('0.0.1', {'f': ('0.0.2', {'h': '0.3.0'}), 'A.h': '0.4.1'})
        """
        self._resolve_dependencies()
        return self._dependencies

    def is_dependent( self, other) -> str:
        """
        Determines whether the current element is dependent on another element.
        
        The parameter ``other`` can be qualified name, a function, or a class.
        
        Returns
        -------
        Version : str
            This function returns ``None`` if there is no dependency on ``other``, 
            or the direct user-specified version of the ``other``
            it is dependent on.
        """
        other        = self._qual_name( other ) if not isinstance(other, str) else other
        dependencies = self.dependencies
        
        def is_dependent( ddict ):
            for k, d in ddict.items():
                if k == other:
                    return d if isinstance(d, str) else d[0]
                if isinstance(d, str):
                    continue
                ver = is_dependent( d[1] )
                if not ver is None:
                    return ver
            return None
        return is_dependent( { self._qual_name( self._original ): dependencies } )

    def _resolve_dependencies(     self,
                                   top_context  : str = None, # top level context for error messages
                                   recursive    : set = None  # set of visited functions
                                   ):
        """
        Function to be called to compute dependencies for `original`.

        Parameters
        ----------
        top_context:
            Name of the top level recursive context for error messages
        recursive:
            A set to catch recursive dependencies.
        """
        # quick check whether 'wrapper' has already been resolved
        if not self._dependencies is None:
            return

        # setup
        local_context = self._qual_name( self._original )
        top_context   = top_context if not top_context is None else local_context

        def err_context():
            if local_context != top_context:
                return "Error while resolving dependencies for '%s' (as part of resolving dependencies for '%s')" % ( local_context, top_context )
            else:
                return "Error while resolving dependencies for '%s'" % top_context

        # ensure we do not have a recursive loop
        if not recursive is None:
            if local_context in recursive: raise RecursionError( err_context() + f": recursive dependency on function '{local_context}'" )
        else:
            recursive = set()
        recursive.add(local_context)

        # collect full qualified dependencies resursively
        version_dependencies = dict()
        
        if self._auto_class and not self._class is None:
            version_dependencies[ self._qual_name( self._class )] = self._class.version.dependencies

        for dep in self._input_dependencies:
            # 'dep' can be a string or simply another decorated function
            # if it is a string, it is of the form A.B.C.f where A,B,C are types and f is a method.

            if isinstance(dep, str):
                # handle A.B.C.f
                hierarchy = dep.split(".")
                str_dep   = dep

                # expand global lookup with 'self' if present
                source    = getattr(self._original,"__globals__", None)      
                if source is None:
                    raise VersionDefinitionError( err_context(), f"Cannot resolve dependency for string reference '{dep}': object of type '{type(self._original).__name__}' has no __globals__ to look up in" )
                src_name  = "global name space"
                self_     = getattr(self._original,"__self__" if not isinstance(self._original,type) else "__dict__", None)
                if not self_ is None:
                    source = dict(source)
                    source.update(self_.__dict__)
                    src_name  = "global name space or members of " + type(self_).__name__

                # resolve types iteratively
                for part in hierarchy[:-1]:
                    source   = source.get(part, None)
                    if source is None:
                        raise VersionDefinitionError( err_context(), f"Cannot find '{part}' in '{src_name}' as part of resolving dependency on '{str_dep}'; known names: {fmt_list(sorted(list(source.keys())))}" )
                    if not isinstance(source, type):
                        raise VersionDefinitionError( err_context(), f"'{part}' in '{src_name}' is not a class/type, but '{type(source).__name__}'. This was part of resolving dependency on '{str_dep}'" )
                    source   = source.__dict__
                    src_name = part

                # get function
                dep  = source.get(hierarchy[-1], None)
                ext  = "" if hierarchy[-1]==str_dep else ". (This is part of resoling dependency on '%s')" % str_dep
                if dep is None:
                    raise VersionDefinitionError( err_context(), f"Cannot find '{hierarchy[-1]}' in '{src_name}'; known names: {fmt_list((source.keys()))}{ext}" )

            if not isinstance( dep, Version ):
                dep_v = getattr(dep, "version", None)
                dep_qn = self._qual_name( dep )
                if dep_v is None: raise VersionDefinitionError( err_context(), f"Cannot determine version of '{dep_qn}': this is not a versioned function or class as it does not have a 'version' member",  )
                if type(dep_v).__name__ != "Version":  raise VersionDefinitionError( err_context(), f"Cannot determine version of '{dep_qn}': 'version' member is of type '{type(dep_v).__name__}' not of type 'Version'" )
                qualname = dep_qn
            else:
                dep_v    = dep
                qualname = self._qual_name( dep._original )

            # dynamically retrieve dependencies
            dep_v._resolve_dependencies( top_context=top_context, recursive=recursive )
            assert not dep_v._dependencies is None, ("Internal error", qualname, ":", dep, "//", dep_v)
            version_dependencies[qualname] = dep_v._dependencies

        # add our own to 'resolved dependencies'
        self._dependencies = ( self._input_version, version_dependencies ) if len(version_dependencies) > 0 else self._input_version

    @staticmethod
    def _qual_name( x ) -> str:
        if isinstance(x, str):
            return x
        try:
            return x.__qualname__
        except:
            pass
        try:
            return type(x).__qualname__
        except:
            pass
        raise TypeError(f"Cannot determine qualified name for type {type(x)}, '{str(x)[:100]}'")


    # uniqueHash
    # ----------

    def __unique_hash__( self, unique_hash, debug_trace ) -> str:
        """
        Compute hash for use with :class:`cdxcore.uniquehash.UniqueHash`.
        """
        return self.unique_id(max_len=unique_hash.length)
    
# =======================================================
# @version
# =======================================================

def version( version              : str = "0.0.1" ,
             dependencies         : list[type] = [], *, 
             auto_class           : bool = True,
             raise_if_has_version : bool = True ):
    """
    Decorator to "version" a function or class, which may depend on other versioned functions or classes.
    The point of this decorator is being able to find out the code version of a sequence of function calls,
    and be able to update cached or otherwise stored results accordingly.
    
    You can :dec:`cdxcore.version.version` functions, classes, and their member functions.
    
    When a class is versioned it will automatically be dependent on the versions of any versioned base classes. 
    The same is true for versioned member functions: by default they will be dependent on the version of the defining class.
    Sometimes this behaviour is not helpful. In this case set ``auto_class`` to ``False``
    when defining the :dec:`cdxcore.version.version` for a member function or derived class.

    Simple function example::
        
        from cdxcore.version import version
        
        class A(object):
            def __init__(self, x=2):
                self.x = x
            @version(version="0.4.1")
            def h(self, y):
                return self.x*y
        
        @version(version="0.3.0")
        def h(x,y):
            return x+y
        
        @version(version="0.0.2", dependencies=[h])
        def f(x,y):
            return h(y,x)
        
        @version(version="0.0.1", dependencies=["f", A.h])
        def g(x,z):
            a = A()
            return f(x*2,z)+a.h(z)
        
        g(1,2)
        print("version", g.version.input)                # -> version 0.0.1
        print("full version", g.version.full )           # -> full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
        print("full version ID",g.version.unique_id48 )  # -> full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
        print("depedencies",g.version.dependencies )     # -> depedencies ('0.0.1', {'f': ('0.0.2', {'h': '0.3.0'}), 'A.h': '0.4.1'})    

    Example for classes::
        
        @version("0.1")
        class A(object):
            @version("0.2") # automatically depends on A
            def f(self, x):
                return x
            @version("0.3", auto_class=False ) # does not depend on A
            def g(self, x):
                return x
            
        @version("0.4") # automatically depends on A
        class B(A):
            pass
        
        @version("0.4", auto_class=False ) # does not depend on A
        class C(A):
            pass


        b = B()
        c = C()
        print( "B", b.version.full )   # -> B 0.4 { A: 0.1 }
        print( "C", c.version.full )   # -> C 0.4

    **See Also**

    :dec:`cdxcore.subdir.SubDir.cache` implements a caching mechanism which uses versions to decide
    whether a cached result can still be used.

    Parameters
    ----------
    version : str
        Version string for this function or class.
        
    dependencies : list[type], optional
        List of elements this function depends on. Usually the list contains the actual other element by Python reference.
        If this is not suitable (for example if the name cannot be resolved in order), a string can be used to identify the
        dependency.
        If strings are used, then the function's global context and, if appliable, the associated
        ``self`` will be searched for the respective element.
        
    auto_class : bool, optional
        If ``True``, the default, then the version of member function or an inherited class is automatically dependent
        on the version of the defining/base class. Set to ``False`` to turn off. The default is ``True``.
        
    raise_if_has_version : bool, optional
        Whether to throw an exception of version are already present.
        This is usually the desired behaviour except if used in another wrapper, see for example
        :dec:`cdxcore.subdir.SubDir.cache`. The default is ``True``.

    Returns
    -------
    Wrapper : Callable
        The returned decorated function or class will have a `version` property of type :class:`cdxcore.version.Version` with
        the following key properties:
            
        * :attr:`cdxcore.version.Version.input`: input version string as provided by the user.
        
        * :attr:`cdxcore.version.Version.full`: qualified full version including versions of dependent functions or classes, as a string
    
        * :attr:`cdxcore.version.Version.unique_id48`: a 48 character unique ID. Versions for 60 and 64 characters are also pre-defined.
        
        * :attr:`cdxcore.version.Version.dependencies`: hierarchy of version dependencies as a list.
          The recursive definition is as follows: if the function has no dependencies, return::
             
            "version"
            
          If the function has dependencies, return recursively::
              
            ( "version", { dependency: dependency.version_full() } )
    """
    def wrap(f):
        dep = dependencies
        existing = getattr(f, "version", None)
        if not existing is None:
            # is 'version' a Version
            if type(existing).__name__ != Version.__name__:
                tmsg = "type" if isinstance(f,type) else "function"
                raise ValueError(f"@version: {tmsg} '{Version._qual_name( f )}' already has a member 'version' but it has type {type(existing).__name__} not {Version}")
            # make sure we were not called twice
            if existing._original == f:
                if not raise_if_has_version:
                    return f
                tmsg = "type" if isinstance(f,type) else "function"
                raise ValueError(f"@version: {tmsg} '{Version._qual_name( f )}' already has a member 'version'. It has initial value {existing._input_version}.")
            # auto-create dependencies to base classes:
            # in this case 'existing' is a member of the base class.
            if not existing._original in dependencies and not Version._qual_name( existing._original ) in dependencies and auto_class:
                dep = list(dep)
                dep.append( existing._original )
        if isinstance( f, type ):
            # set '_class' for all Version objects
            # of all members of a type
            funcs = list( inspect.getmembers(f, predicate=inspect.isfunction) )\
                  + [ c for c in inspect.getmembers(f, predicate=inspect.isclass) if c[0] != "__class__" ]
            for gname, gf in funcs:
                gversion = getattr(gf, "version", None)
                if gversion is None:
                    #print(f"{gname} is not versioned")
                    continue
                if not gversion._class is None:
                    continue
                gversion._class = f
        f.version = Version(f, version, dep, auto_class=auto_class )
        assert type(f.version).__name__ == Version.__name__
        return f
    return wrap

