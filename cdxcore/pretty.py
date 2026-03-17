"""
The main feature of this module is the simple :class:`cdxcore.pretty.PrettyObject`
class which mimics directory access to its members.

Overview
--------

The purpose is a functional-programming style pattern for generating complex objects,
while mimicing a dictionary object::

    from cdxcore.pretty import PrettyObject
    pdct = PrettyObject(z=1)
    
    pdct.num_samples = 1000
    pdct.num_batches = 100
    pdct.method = "signature"
    
The object allows accessing members via ``[]``::
    
    print( pdct['num_samples'] )   # -> 1000
    print( pdct['num_batches'] )   # -> 100
    
Features
^^^^^^^^
    
:class:`cdxcore.pretty.PrettyObject` implements all relevant dictionary protocols, so objects of type :class:`cdxcore.pretty.PrettyObject` can
(nearly always) be passed where dictionaries are expected:
                                                                                                             
* A :class:`cdxcore.pretty.PrettyObject` object supports standard dictionary semantics in addition to member attribute
  access.
  That means you can use ``pdct['num_samples']`` as well as ``pdc.num_samples``.
  You can mix standard dictionary notation with member attribute notation::

    print(pdct["num_samples"]) # -> prints "1000"
    pdct["test"] = 1           # sets pdct.test to 1     

* Iterations work just like for dictionaries; for example::
    
    for k,v in pdct.items():
        print( k, v)
        
* Applying ``str`` and ``repr`` to objects of type :class:`cdxcore.pretty.PrettyObject` will return dictionary-type
  results, so for example ``print(pdct)`` of the above will return ``{'z': 1, 'num_samples': 1000, 'num_batches': 100, 'method': 'signature'}``.

Vectorized access
^^^^^^^^^^^^^^^^^

Several member functions of :class:`cdxcore.pretty.PrettyObject` support member access for example::
    
    from cdxcore.pretty import PrettyObject
    r = PrettyObject()

    # assign    
    r['a','b'] = 1,2

    # read, with defaults
    a,b,c = r.get(['a','b','c'],[11,22,33]) # -> 1,2,33
    
    # dictionary notation
    a,b,c = r.get(a=11,b=22,c=33) # -> 1,2,33

    # works with pop, too:
    a,b,c = r.pop(a=11,b=22,c=33) # -> 1,2,33

    r = PrettyObject(a=1,b=2)
    # reading with defaults
    a, b, c = r.setdefault(a=11,b=22,c=33) # -> 1,2,33
    print(r.c) # -> 33

Access by Position
^^^^^^^^^^^^^^^^^^
    
The :attr:`cdxcore.pretty.PrettyObject.at_pos` attribute allows accessing elements of the ordered dictionary
by positon:
  
* ``cdxcore.pretty.PrettyObject.at_pos[i]`` returns the `i` th element.

* ``cdxcore.pretty.PrettyObject.at_pos.keys[i]`` returns the `i` th key.

* ``cdxcore.pretty.PrettyObject.at_pos.items[i]`` returns the `i` th item.

For example::

    from cdxcore.pretty import PrettyObject
    pdct = PrettyObject(z=1)
    
    pdct.num_samples = 1000
    pdct.num_batches = 100
    pdct.method = "signature"
    
    print(pdct.at_pos[3])      # -> prints "signature"
    print(pdct.at_pos.keys[3]) # -> prints "method"

Member Functions
^^^^^^^^^^^^^^^^

You can assign member functions to a :class:`cdxcore.pretty.PrettyObject`.
The following works as expected::
    
      pdct.f = lambda self, y: return self.y*x
      
(to assign a static function which does not refer to ``self``, use ``pdct['g'] = lambda z : return z``).

Dataclasses
^^^^^^^^^^^

:mod:`dataclasses` rely on default values of any member being "frozen" objects, which most user-defined objects and
:class:`cdxcore.pretty.PrettyObject` objects are not.
This limitation also  applies to `flax <https://flax-linen.readthedocs.io/en/latest/api_reference/flax.linen/module.html>`__ modules.
To use non-frozen default values, use the
:meth:`cdxcore.pretty.PrettyObject.as_field` function::

    from cdxcore.pretty import PrettyObject
    from dataclasses import dataclass
    
    @dataclass
    class Data:
    	data : PrettyObject = PrettyObject(x=2).as_field()
    
    	def f(self):
            return self.data.x
    
    d = Data()   # default constructor used.
    d.f()        # -> returns 2

Hierachies
^^^^^^^^^^

This module also provides :class:`cdxcore.pretty.PrettyHierarchy` derived from :class:`cdxcore.pretty.PrettyObject`
which allows, in addition, automatic generation of hierarchies e.g.::
    
    from cdxcore.pretty import PrettyHierarchy
    r = PrettyHierarchy(a=1,b=2)
    r.x.c = 3
    
This is a short cut for::
    
    from cdxcore.pretty import PrettyHierarchy
    r = PrettyHierarchy(a=1,b=2)
    r.x = PrettyHierarchy()
    r.x.c = 3

However, runtime semantics can be confusing as :class:`cdxcore.pretty.PrettyHierarchy` creates objects
on the fly if an attrbute is not known. Hence typos can generate confusing error messages: 
assume we have some code that creates a :class:`cdxcore.pretty.PrettyHierarchy`::
    
    data = PrettyHierarchy()
    data = ...
    data.center = compute_centre()
    
Somewhere else we then access ``data.centre`` instead of ``data.center`` (a typo) using e.g.::
    
    np.sum( data.centre )
    
This raises ``TypeError: 'PrettyHierarchy' object is not callable`` instead of an :class:`AttributeError`.
   
    
Import
------
.. code-block:: python

    from cdxcore.pretty import PrettyObject as pdct
    
Documentation
-------------
"""
from __future__ import annotations

import dataclasses as dataclasses
from dataclasses import Field
import types as types
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any
from .err import verify_inp

class PrettyObject(MutableMapping):
    """
    Class mimicing an ordered dictionary.
    
    Example::    
        
        from cdxcore.pretty import PrettyObject
        pdct = PrettyObject()
        pdct.x = 1
        pdct['y'] = 2
        print( pdct['x'], pdct.y ) # -> prints 1 2

    The object mimics a dictionary::
        
        print(pdct)  # -> '{'x': 1, 'y': 2}'

        u = dict( pdct )
        print(u)     # -> {'x': 1, 'y': 2}
        
        u = { k: 2*v for k,v in pdct.items() }
        print(u)     # -> {'x': 2, 'y': 4}
    
        l = list( pdct ) 
        print(l)     # -> ['x', 'y']
        
    *Important:*
    attributes starting with '__' cannot be accessed with item ``[]`` notation.
    In other words::
               
        pdct = PrettyObject()
        pdct.__x = 1    # fine
        _ = pdct['__x'] # <- throws an exception
        
    **Access by Index Position**
    
    :class:`cdxcore.pretty.PrettyObject` retains order of construction. To access its members
    by index position, use the :attr:`cdxcore.pretty.PrettyObject.at_pos` attribute::

        print(pdct.at_pos[1])             # -> prints "2"
        print(pdct.at_pos.keys[1])        # -> prints "y"
        print(list(pdct.at_pos.items[2])) # -> prints "[('x', 1), ('y', 2)]"

    **Vectorized access**
    
    Several functions support accessing member elements using vectors, for example:

    Setting elements::

        from cdxcore.pretty import PrettyObject
        r = PrettyObject()
        r['a','b'] = 1,2
        print(r.a,r.b)  # -> 1,2
        r['a','b'] = (1,2)
        print(r.a,r.b)  # -> 1,2
        
    Reading elements::

        r = PrettyObject(a=1,b=2)
        a, b = r['a','b']
        print(a,b)      # -> 1,2
        
    Reading elements with defaults, classic method::

        r = PrettyObject(a=1,b=2)
        a, b, c = r.get(['a','b','c'],[1,2,33])
        print(a,b,c)      # -> 1,2,33
        
    Reading elements with defaults, keyword method::
    
        r = PrettyObject(a=1,b=2)
        a, b, c = r.get(a=11,b=22,c=33)
        print(a,b,c)      # -> 1,2,33
        
    Popping elements with defaults, keyword method::
    
        r = PrettyObject(a=1,b=2)
        a, b, c = r.pop(a=11,b=22,c=33)
        print(a,b,c)      # -> 1,2,33
        assert len(r)==0
        
    Same for :meth:`cdxcore.pretty.PrettyObject.setdefault`::

        r = PrettyObject(a=1,b=2)
        a, b, c = r.setdefault(a=1,b=2,c=33)
        print(a,b,c)      # -> 1,2,33
        print(r.c)        # -> 33

    **Assigning Member Functions**
    
    ``PrettyObject`` objects also allow assigning bona fide member functions by a simple semantic of the form::
    
        pdct = PrettyObject(b=2)
        pdct.mult_b = lambda self, x: self.b*x
        pdct.mult_b(3) # -> 6
    
    Calling ``pdct.mult_b(3)`` with above ``pdct`` will return `6` as expected. 
    To assign static member functions, use the ``[]`` operator.
    The reason for this is as follows: consider::
    
        def mult( a, b ):
            return a*b
        pdct = PrettyObject()
        pdct.mult = mult
        pdct.mult(3,4) --> produces am error as three arguments must be passed: self, 3, and 4
     
    In this case, use::
         
        pdct = PrettyObject()
        pdct['mult'] = mult
        pdct.mult(3,4) --> 12
      
    You can also pass member functions to the constructor::

        p = PrettyObject( f=lambda self, x: self.y*x, y=2)
        p.f(3) # -> 6
        
    **Operators**
    
    Objects of type :class:`cdxcore.pretty.PrettyObject` support the following operators:
        
    * Comparison operator ``==`` and ``!=`` test for equality of keys and values. Unlike for dictionaries
      comparisons are performed in *in order*. That means ``PrettyObject(x=1,y=2)`` and ``PrettyObject(y=2,x=1)`` 
      are *not* equal.
    
    * Super/subset operators ``>=`` and ``<=`` test for a super/sup set relationship, respectively.
    
    * ``a | b`` returns the union of two :class:`cdxcore.pretty.PrettyObject`. Elements of the ``b`` overwrite any elements of ``a``, if they
      are present in both. The order of the new dictionary is determined by the order of appearance of keys in first ``a`` and then ``b``, that 
      means in all but trivial cases ``a|b != b|a``.
      
      The ``|=`` operator is a short-cut for :meth:`cdxcore.pretty.PrettyObject.update`.

    Parameters
    ----------
        copy : Mapping, optional
            If present, assign elements of ``copy`` to ``self``. This is a shallow copy.

        ** kwargs:
            Key/value pairs to be added to ``self``.
    """
    class _No_Default_dummy():
        pass
    
    no_default = _No_Default_dummy()
    # Formal value to indicate no default is provided.
        
    def __init__(self, copy : Mapping|PrettyObject|None = None, **kwargs) -> None:
        """
        :meta private:
        """
        if not copy is None:
            self.update(copy)            
        for k, v in kwargs.items():
            setattr(self, k, v)
            
    def _get1item(self, key : str) -> Any:
        try:
            return getattr( self, key )
        except AttributeError as e:
            raise KeyError(key,*e.args)        
            
    def __getitem__(self, key : str|Sequence) -> Any:
        """ Vector version of [] """
        if not isinstance(key, str) and isinstance(key, Sequence):
            return tuple( self._get1item(k) for k in key )
        return self._get1item(key)

    def _set1(self, key: str,value:Any ):        
        try:
            super().__setattr__(key, value)
            return self[key]
        except AttributeError as e:
            raise KeyError(key,*e.args)
            
    def __setitem__(self, key : str|Sequence, value : Any|Sequence[Any]):
        """
        Route ``self[key] = value`` to the base class ``__setattr__`` method.
        This way you can assign static functions using ``[]`` which assinging
        functions using ``.`` will assign member functions.
        
        This function works with vector assignments.
        """        
        if not isinstance(key, str) and isinstance(key, Sequence):
            if not isinstance(value, str) and isinstance(value, Sequence):
                for k,v in zip(key,value):
                    self._set1(k,v)
            else:
                for k in key:
                    self._set1(k,value)
        else:
            self._set1(key, value)
        
    def __delitem__(self,key : str|Sequence):
        def del1(key):
            try:
                delattr(self, key)
            except AttributeError as e:
                raise KeyError(key,*e.args)
        if not isinstance(key, str) and isinstance(key, Sequence):
            for k in key:
                del1(k)
        else:
            del1(key)
            
    def __iter__(self):
        return self.__dict__.__iter__()
    def __reversed__(self):
        return self.__dict__.__reversed__()
    def __sizeof__(self):
        return self.__dict__.__sizeof__()
    def __contains__(self, key):
        return self.__dict__.__contains__(key)
    def __len__(self):
        return self.__dict__.__len__()

    def __setattr__(self, key : str, value : Any):
        """
        ``__setattr__`` does what is expected, and in addition converts function assignments to member functions
        """
        if key[:2] == "__":
            super().__setattr__(key, value)
            return
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        super().__setattr__(key, value)
    
    # dictionary
    def copy(self, **kwargs):
        """ Return a shallow copy; optionally add further key/value pairs. """
        return PrettyObject(self,**kwargs)
    def clear(self):
        """ Delete all elements. """
        self.__dict__.clear()

    def _get1(self, key:str, default : Any = no_default) -> Any:
        try:
            return getattr(self, key) if default == PrettyObject.no_default else getattr(self, key, default)
        except AttributeError as e:
            raise KeyError(key,*e.args)

    def get(self, __key__ : str|Sequence|Any|None = None, default : Any = no_default, **keys ) -> Any|tuple[any]:
        """
        Get element ``key`` with optional default ``default``. Equivalent to :meth:`dict.get`. 
        Alternatively, this function takes a list of keys and their default values in dictionary notation
        in which case the read values are returned in order. You cannot mix using ``key`` and ``keys``.
        
        **Standard usage**
                
        This function supports ``key`` being a sequence in which case this function returns
        a tuple of the same length with the respective results. The ``default`` value
        will be interpreted accordingly.
        
        Hence, the following works::
            
            from cdxcore.pretty import PrettyObject
            
            r = PrettyObject(a=1, b=2)
            a,b,c = r.get( ['a', 'b','c'],[11,22,33] )
            print(a,b,c) # -> 1,2,33        
            
        **Keyword usage**
        
        Provide keys with default values, i.e.::

            from cdxcore.pretty import PrettyObject
            
            r = PrettyObject(a=1, b=2)
            a,b,c = r.get( a=11, b=22, c=33 )
            print(a,b,c) # -> 1,2,33                
        """
            
        if not __key__ is None:
            verify_inp( len(keys) == 0, "Cannot specify both a 'key' and free keyword arguments")
            if not isinstance(__key__, str) and isinstance(__key__, Sequence):
                if not isinstance(default, str) and isinstance(default, Sequence):
                    return tuple( self._get1(k,d) for k,d in zip(__key__, default) )
                return tuple( self._get1(k,default) for k in __key__ )     
            else:
                return self._get1(__key__, default)
        else:
            verify_inp( default == PrettyObject.no_default, "Cannot specify both a 'key' and free keyword arguments")
            return tuple( self._get1(k,d) for k,d in keys.items() )

    def pop(self, __key__ : str|Sequence|None = None, default : Any = no_default, **keys ):
        """
        Get and remove element ``key`` with optional default ``default``. Equivalent to :meth:`dict.pop`.
        Alternatively, this function takes a list of keys and their default values in dictionary notation
        in which case the read values are returned in order. You cannot mix using ``key`` and ``keys``.

        **Standard usage**
        
        This function supports ``key`` being a sequence in which case this function returns
        a tuple of the same length with the respective results. The ``default`` value
        will be interpreted accordingly.
        
        Hence, the following works::
            
            from cdxcore.pretty import PrettyObject
            
            r = PrettyObject(a=1, b=2)
            a,b,c = r.pop( ['a', 'b','c'],[11,22,33] )
            print(a,b,c) # -> 1,2,33

        **Keyword usage**

        Provide keys with default values, i.e.::

            from cdxcore.pretty import PrettyObject
            
            r = PrettyObject(a=1, b=2)
            a,b,c = r.pop( a=11, b=22, c=33 )
            print(a,b,c) # -> 1,2,33
        """
        if not __key__ is None:
            verify_inp( len(keys) == 0, "Cannot specify both a 'key' and free keyword arguments")
            if not isinstance(__key__, str) and isinstance(__key__, Sequence):
                # read first - so an exception does not leave us with a bad object
                if not isinstance(default, str) and isinstance(default, Sequence):
                    r = tuple( self._get1(k,d) for k,d in zip(__key__, default) )
                else:
                    r = tuple( self._get1(k,default) for k in __key__ )
                # delete
                for k in __key__:
                    if k in self:
                        delattr(self,k)
                return r
            else:
                r = self._get1(__key__, default)
                if __key__ in self:
                    delattr(self,__key__)
                return r   
        else:
            verify_inp( default == PrettyObject.no_default, "Cannot specify both a 'key' and free keyword arguments")
            r = tuple( self._get1(k,d) for k,d in keys.items() )
            for k in keys:
                if k in self:
                    delattr(self,k)
            return r

    def _setdefault1(self, key:str, default : Any) -> Any:
        if not hasattr(self, key):
            self.__setattr__(key, default)
        return getattr(self,key)

    def setdefault( self, __key__ : str|Sequence|None = None, default : Any = None, **keys ) -> Any:
        """
        Returns the value for ``key`` or ``default`` if not found. In the latter case it
        adds ``default`` as value for ``key`` to the dictionary.
        Equivalent to :meth:`dict.setdefault`.
        
        Alternatively, this function takes a list of keys and their default values in dictionary notation
        in which case the read values are returned in order. You cannot mix using ``key`` and ``keys``.

        **Standard usage**

        This function supports ``key`` being a sequence in which case this function returns
        a tuple of the same length with the respective results. The ``default`` value
        will be interpreted accordingly.
        
        Hence, the following works::
            
            from cdxcore.pretty import PrettyObject
            
            r = PrettyObject(a=1, b=2)
            a,b,c = r.setdefault( ['a', 'b','c'],[11,22,33] )
            print(a,b,c) # -> 1,2,33        
            print(r.c) # -> 33
        
        **Keyword usage**

        Provide keys with default values, i.e.::

            from cdxcore.pretty import PrettyObject
            
            r = PrettyObject(a=1, b=2)
            a,b,c = r.setdefault( a=11, b=22, c=33 )
            print(a,b,c) # -> 1,2,33
            print(r.c) # -> 33
        """
        
        if not __key__ is None:
            verify_inp( len(keys) == 0, "Cannot specify both a 'key' and free keyword arguments")
            if not isinstance(__key__, str) and isinstance(__key__, Sequence):
                if not isinstance(default, str) and isinstance(default, Sequence):
                    return tuple( self._setdefault1(k,d) for k,d in zip(__key__, default) )
                return tuple( self._setdefault1(k,default) for k in __key__ )   
            else:
                return self._setdefault1(__key__, default)
        else:
            return tuple( self._setdefault1(k,d) for k, d in keys.items() )     

    def update(self, other : Mapping|None = None, **kwargs) -> PrettyObject:
        """
        Equivalent to :meth:`dict.update`. 
        
        Note that functon assignments are handled in normal dictionary
        fashion - in particular, bound functions will *not* become
        magically unbound.
        """
        if not other is None:
            verify_inp( isinstance(other,Mapping), lambda : f"'other' must be a mapping; found type {type(other)}")
            for k, v in other.items():
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v
        return self

    # behave like a dictionary
    def keys(self):
        """ Equivalent to :meth:`dict.keys` """
        return self.__dict__.keys()
    def items(self):
        """ Equivalent to :meth:`dict.items` """
        return self.__dict__.items()
    def values(self):
        """ Equivalent to :meth:`dict.values` """
        return self.__dict__.values()
    
    # update
    def __ior__(self, other):
        return self.update(other)
    def __or__(self, other):
        copy = self.copy()
        copy.update(other)
        return copy
    def __ror__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        copy = PrettyObject(other)
        copy.update(self)
        return copy
        
    # dictionary comparison
    def __eq__(self, other):
        """
        Comparison operator. Unlike dictionary comparison, this comparision operator
        preservers order.
        """
        if len(self) != len(other):
            return False
        for k1, k2 in zip( self, other ):
            if not k1==k2:
                return False
        for v1, v2 in zip( self.values(), other.values() ):
            if not v1==v2:
                return False
        return True
    def __le__(self, other):
        """
        Subset operator i.e. if ``self`` is contained in ``other``, including values.
        """
        for k, v in self.items():
            if not k in other:
                return False
            if not v == other[k]:
                return False
        return True
    def __ge__(self, other):
        """
        Superset operator i.e. if ``self`` is a superset of ``other``, including values.
        """
        return other <= self

    def __ne__(self, other):
        """
        Comparison operator. Unlike dictionary comparison, this comparision operator
        preservers order.
        """
        return not self == other    

    # Backwards compatibility for older code (note: Python uses __ne__ for !=)
    def __neq__(self, other):
        return self.__ne__(other)
    
    # print representation
    def __repr__(self):
        return f"PrettyObject({self.__dict__.__repr__()})"
    def __str__(self):
        return self.__dict__.__str__()

    # data classes
    def as_field(self) -> Field:
        """
        This function provides support for :class:`dataclasses.dataclass` fields
        with ``PrettyObject`` default values.
        
        When adding
        a `field <https://docs.python.org/3/library/dataclasses.html#dataclasses.field>`__
        with a non-frozen default value to a ``@dataclass`` class,
        a ``default_factory`` has to be provided.
        The function ``as_field`` returns the corresponding :class:`dataclasses.Field`
        element by returning simply::
            
            def factory():
                return self
            return dataclasses.field( default_factory=factory )
            
        Usage is as follows::
            
            from dataclasses import dataclass
            @dataclass 
            class A:
                data : PrettyDict = PrettyDict(x=2).as_field()

            a = A() 
            print(a.data.x)  # -> "2"
            a = A(data=PrettyDict(x=3)) 
            print(a.data.x)  # -> "3"
        """
        def factory():
            return self
        return dataclasses.field( default_factory=factory )

    @property
    def at_pos(self):
        """
        Elementary access to the data contained in ``self`` by ordinal position.
        The ordinal
        position of an element is determined by the order of addition to the dictionary.
        
        * ``at_pos[position]`` returns an element or elements at an ordinal position:
            
          * It returns a single element if ``position`` refers to only one field.
          * If ``position`` is a slice then the respecitve list of fields is returned.

        * ``at_pos.keys[position]`` returns the key or keys at ``position``.
        
        * ``at_pos.items[position]`` returns the tuple ``(key, element)`` or a list thereof for ``position``.

        You can also write data using the `attribute` notation:

        * ``at_pos[position] = item`` assigns an item to an ordinal position:
            
          * If ``position`` refers to a single element, ``item`` must be the value to be assigned to this element.
          * If ``position`` is a slice then '``item`` must resolve to a list (or generator) of the required size.
         """

        class Access(Sequence):
            """ 
            Wrapper object to allow index access for at_pos
            """
            def __init__(self) -> None:
                self.__keys = None
                
            def pop(_, position : int = 0):
                key = _.keys[position]
                return self.pop(key)
            
            def __getitem__(_, position):
                key = _.keys[position]
                return self[key] if not isinstance(key,list) else [ self[k] for k in key ]
            def __setitem__(_, position, item ):
                key = _.keys[position]
                if not isinstance(key,list):
                    self[key] = item
                else:
                    for k, i in zip(key, item):
                        self[k] = i
            def __len__(_):
                return len(self)
            def __iter__(_):
                for key in self:
                    yield self[key]
                    
            @property
            def keys(_) -> list:
                """ Returns the list of keys in construction order """
                return list(self.keys())
            @property
            def values(_) -> list:
                """ Returns the list of values in construction order """
                return list(self.values())
            @property
            def items(_) -> Sequence:
                """ Returns the sequence of key, value pairs of the original dictionary """
                class ItemAccess(Sequence):
                    def __init__(_x) -> None:
                        _x.keys = list(self.keys())
                    def __getitem__(_x, position):
                        key = _x.keys[position]
                        return (key, self[key]) if not isinstance(key,(list,types.GeneratorType)) else [ (k,self[k]) for k in key ]                
                    def __len__(_x):
                        return len(_x.keys)
                    def __iter__(_x):
                        for key in _x.keys:
                            yield key, self[key]
                return ItemAccess()
                
        return Access()
    
class PrettyValueObject( PrettyObject ):
    """
    A :class:`cdxcore.pretty.PrettyObject` whose default iteration is over its values, not keys as is the case of dictionaries and :class:`cdxcore.pretty.PrettyObject`.

    Therefore those work::

        from cdxcore.pretty import PrettyValueObject
        r = PrettyValueObject(a=1,b=2,c=3)

        a,b,c = r
        assert (a,b,c) == (1,2,3)

        for i, v in enumerate(r):
            assert v == i+1
    """
    def __iter__(self):
        return iter( self.values() )

class PrettyHierarchy( PrettyObject ):
    """
    A :class:`cdxcore.pretty.PrettyObject` which can easily create hierarchies of :class:`cdxcore.pretty.PrettyObject`'s.
    
    This works::
        
        from cdxcore.pretty import PrettyHierarchy
        
        r = PrettyHierarchy()
        r.a = 1
        r.x.b = 2
        
        assert r.a == 1
        assert isinstance(r.x,PrettyHierarchy)
        assert r.x.b == 2
        
    Some oddities::
        
        from cdxcore.pretty import PrettyHierarchy
        
        r = PrettyHierarchy()
        
        r.A = 1
        print( r.a )   # -> prints an empty PrettyHierarchy
        _ = r.b        # generates an empty PrettyHierarchy
        assert set(r) == {'A','a','b'} # all above created entries.
        
    Runtime semantics can be confusing as :class:`cdxcore.pretty.PrettyHierarchy` creates objects
    on the fly if an attrbute is not known. Hence typos can generate confusing error messages: 
    assume we have some code that creates a :class:`cdxcore.pretty.PrettyHierarchy`::
        
        data = PrettyHierarchy()
        data = ...
        data.center = compute_centre()
        
    Somewhere else we then access ``data.centre`` innstead of ``data.center``, a typo::
        
        np.sum( data.centre )
        
    This raises ``TypeError: 'PrettyHierarchy' object is not callable`` instead of an :class:`AttributeError`.
        
    Note that ``["x"]`` keeps working as expected, i.e. it will fail if 'x' does not exist.
    """
    
    def __getattr__(self, key : str) -> Any:
        if key.startswith("__"):
            raise AttributeError(key)
        r = PrettyHierarchy()
        setattr(self, key, r )
        return r
    
    def _get1item(self, key : str) -> Any:
        # do not call self.__getattr__
        try:
            return super().__getattribute__(key)
        except AttributeError as e:
            raise KeyError(key,*e.args)        
            
    def __getitem__(self, key : str|Sequence) -> Any:
        """ Vector version of [] """
        if not isinstance(key, str) and isinstance(key, Sequence):
            return tuple( self._get1item(k) for k in key )
        return self._get1item(key)

no_default = PrettyObject.no_default
# :meta:private
