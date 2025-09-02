"""
## Overview

This module provides a framework to track versions of functions, classes, and their members via a simple decorating mechanism.
A main application is the use in caching results of computational intensive tasks such as data pipelines in machine learning. The 'version'
framework allows updating dynamically only those parts of the data dependency graph whose code generation logic has changed.
Accordingly, [SubDir][cdxcore.subdir.SubDir]'s file read/write function support fast light-weight file based versioning control
which does not require loading an entire file to determine its version.

A full caching logic is implemented using @[SubDir.cache][cdxcore.subdir.SubDir.cache].

For versioning, basic use is straight forward and self-explanatory:

```
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
print("version", g.version.input)  -- version 0.0.1
print("full version", g.version.full )  -- full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
print("full version ID",g.version.unique_id48 )  -- full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
```

See @[version][cdxcore.version.version] for full details.

## Import
```
from cdxcore.version import version
```
"""
import inspect as inspect
from .util import fmt_list
from .uniquehash import uniqueLabelExt

uniqueLabel64 = uniqueLabelExt(max_length=64,id_length=8)
uniqueLabel60 = uniqueLabelExt(max_length=60,id_length=8)
uniqueLabel48 = uniqueLabelExt(max_length=48,id_length=8)

class VersionError(RuntimeError):
    """
    Error thrown if a version was incorrect.
    """
    def __init__(self, context, message):
        RuntimeError.__init__(self, context, message)

class Version(object):
    """
    Class to track version dependencies for a given function or class `f`.
    This class is used by the @[version][cdxcore.version.version] decorator. Developers will not typically directly use it, but access
    it via a decorated function's `version` property.

    **Key Properties**
    
    * [input][cdxcore.version.Version.input]: input version string as provided by the user.
    
    * [full][cdxcore.version.Version.full]: qualified full version including versions of dependent functions or classes, as a string

    * [unique_id48][cdxcore.version.Version.unique_id48]: 48 character unique ID. Versions for 60 and 64 characters are also pre-defined.
    
    * [dependencies][cdxcore.version.Version.dependencies]: hierarchy of version dependencies as a list.
    
    **Dependency Resolution**
    
    Dependency resolution is lazy to allow creating dependencies on Python elements which are defined later / elsewhere.
    If an error occurs during dependency resoution an exception of type [VersionError][cdxcore.version.VersionError] is thrown.    
    """

    def __init__(self, original, version : str, dependencies : list[type], auto_class : bool ):
        """
        Version information for `original`.
        Usually this function not directly is called but invoked by @[version][cdxcore.version.version].
        
        Parameters
        ----------
        original:
            Orignal Python element: a function, class, or member function.
        version: str
            user version string
        dependencies: list[type]
            List of dependencies as types (preferably) or string names.
        auto_class : bool
            Whether to automatically make classes dependent on their (versioned) base classes, and member functions on their (versioned)
            containing classes.    
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
        """ Returns qualified version string """
        return self.full

    def __repr__(self) -> str:
        """ Returns qualified version string """
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
        """ Returns the input version of this function """
        return self._input_version

    @property
    def unique_id64(self) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 64 characters.
        """
        return uniqueLabel64(self.full)

    @property
    def unique_id60(self) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 60 characters.
        The 60 character version is to support filenames with a three letter extension, so total file name size is at most 64.
        """
        return uniqueLabel60(self.full)

    @property
    def unique_id48(self) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 48 characters.
        """
        return uniqueLabel48(self.full)

    def unique_id(self, max_len : int = 64) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds `max_len` characters.
        """
        assert max_len >= 4,("'max_len' must be at least 4", max_len)
        id_len = 8 if max_len > 16 else 4
        uniqueHashVersion = uniqueLabelExt(max_length=max_len, id_length=id_len)
        return uniqueHashVersion(self.full)

    @property
    def full(self) -> str:
        """
        Returns information on the version of `self` and all dependent functions
        in human readable form. Elements are sorted by name, hence this representation
        can be used to test equality between two versions.
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
        Returns information on the version of `self` and all dependent functions.

        For a given function the format is:
            
        * If the function has no dependents:
                ```function_version```
            
        * If the function has dependencies, return recursively:
                ```( version, { dependency: dependency.version_full() } )```
        """
        self._resolve_dependencies()
        return self._dependencies

    def is_dependent( self, other) -> str:
        """
        Determines whether the current function is dependent on `other`.
        The parameter `other` can be qualified name, a function, or a class.
        
        Returns
        -------
        Version, str
            This function returns `None` if there is no dependency on `other`, 
            or the direct user-specified version of the `other`
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
                    raise VersionError( err_context(), f"Cannot resolve dependency for string reference '{dep}': object of type '{type(self._original).__name__}' has no __globals__ to look up in" )
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
                        raise VersionError( err_context(), f"Cannot find '{part}' in '{src_name}' as part of resolving dependency on '{str_dep}'; known names: {fmt_list(sorted(list(source.keys())))}" )
                    if not isinstance(source, type):
                        raise VersionError( err_context(), f"'{part}' in '{src_name}' is not a class/type, but '{type(source).__name__}'. This was part of resolving dependency on '{str_dep}'" )
                    source   = source.__dict__
                    src_name = part

                # get function
                dep  = source.get(hierarchy[-1], None)
                ext  = "" if hierarchy[-1]==str_dep else ". (This is part of resoling dependency on '%s')" % str_dep
                if dep is None:
                    raise VersionError( err_context(), f"Cannot find '{hierarchy[-1]}' in '{src_name}'; known names: {fmt_list((source.keys()))}{ext}" )

            if not isinstance( dep, Version ):
                dep_v = getattr(dep, "version", None)
                dep_qn = self._qual_name( dep )
                if dep_v is None: raise VersionError( err_context(), f"Cannot determine version of '{dep_qn}': this is not a versioned function or class as it does not have a 'version' member",  )
                if type(dep_v).__name__ != "Version":  raise VersionError( err_context(), f"Cannot determine version of '{dep_qn}': 'version' member is of type '{type(dep_v).__name__}' not of type 'Version'" )
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

    def __unique_hash__( self, uniqueHash, debug_trace ) -> str:
        """
        Compute non-hash for use with [uniqueHashExt][cdxcore.uniquehash.uniqueHashExt]().
        """
        return self.unique_id(max_len=uniqueHash.length)
    
# =======================================================
# @version
# =======================================================

def version( version              : str = "0.0.1" ,
             dependencies         : list[type] = [], *, 
             auto_class           : bool = True,
             raise_if_has_version : bool = True ):
    """
    Decorator to 'version' a function or class, which may depend on other versioned functions or classes.
    The point of this decorator is being able to find out the code version of a sequence of function calls,
    and be able to update cached or otherwise stored results accordingly.
    
    You can 'version' functions, classes, and their member functions.
    
    When a class is 'versioned' it will automatically be dependent on the versions of any 'versioned' base classes. 
    The same is true for 'versioned' member functions: by default they will be dependent on the version of the defining class (but not
    of derived classes). Sometimes this behaviour is not helpful. In this case set `auto_class` to False
    when setting the 'version' for a member function using @[version][cdxcore.version.version].

    Simple function example:
    ```
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
    print("version", g.version.input)  -- version 0.0.1
    print("full version", g.version.full )  -- full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    print("full version ID",g.version.unique_id48 )  -- full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    ```
    
    Example for classes:
    ```    
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
    ```
    
    @[SubDir.cache][cdxcore.subdir.SubDir.cache] implements a caching mechanism which uses versions to decide
    whether a cached result can still be used.

    Parameters
    ----------
    version : str
        Version of this function
    dependencies : list
        List of elements this function depends on. Usually the list contains the actual other element by Python reference.
        If this is not suitable (for example if the name cannot be resolved in order), a string can be used to identify the
        dependency.
        If strings are used, then the function's global context and, if appliable, `self` will be searched
        for the respective element.
    auto_class : bool
        If True, the default, then the version of member function or an inherited class is automatically dependent
        on the version of the defining/base class. Set to False to turn off.
    raise_if_has_version : bool
        Whether to throw an exception of version are already present.
        This is usually the desired behaviour except if used in another wrapper, see for example
        @[SubDir.cache][cdxcore.subdir.SubDir.cache].        

    Returns
    -------
    Function : Callable
        The returned decorated function or class will have a `version` property of type [Version][cdxcore.version.Version] with
        the following key properties:
            
        * [version.input][cdxcore.version.Version.input]: returns the input 'version' above
                
        * [version.full][cdxcore.version.Version.full]: a human readable version string with all dependencies.

        * [version.unique_id48][cdxcore.version.Version.unique_id48]: a unique ID of version_full which can be used to identify changes in the total versioning
                accross the dependency structure, of at most 48 characters. Use [unique_id][cdxcore.version.Version.unique_id]() for other lengths.

        * [version.dependencies][cdxcore.version.Version.dependencies]: returns a hierarchical description of the version of this function and all its dependcies.
            The recursive definition is:  
            * If the function has no dependencies, return:
                    ```version```
            
            * If the function has dependencies, return recursively:
                    ```( version, { dependency: dependency.version_full() } )```
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

