"""
A simple :class:`cdxcore.pretty.PrettyObject` class which mimics directory access to its members.

Overview
--------

The purpose is a functional-programming style pattern for generating complex objects::

    from cdxbasics.prettydict import PrettyObject
    pdct = PrettyObject(z=1)
    
    pdct.num_samples = 1000
    pdct.num_batches = 100
    pdct.method = "signature"
    
The object allows accessing members via ``[]``:
    
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
    
The :attr:`cdxcore.pretty.PrettyObject.at_pos` attribute allows accessing elements of the ordered dictionary
by positon:
  
* ``cdxcore.pretty.PrettyObject.at_pos[i]`` returns the `i` th element.

* ``cdxcore.pretty.PrettyObject.at_pos.keys[i]`` returns the `i` th key.

* ``cdxcore.pretty.PrettyObject.at_pos.items[i]`` returns the `i` th item.

For example::
    
    print(pdct.at_pos[3])      # -> prints "signature"
    print(pdct.at_pos.keys[3]) # -> prints "method"

You can also assign member functions to a :class:`cdxcore.pretty.PrettyObject`.
The following works as expected::
    
      pdct.f = lambda self, y: return self.y*x
      
(to assign a static function which does not refer to ``self``, use ``pdct['g'] = lambda z : return z``).

Dataclasses
^^^^^^^^^^^

:mod:`dataclasses` rely on default values of any member being "frozen" objects, which most user-defined objects and
:class:`cdxcore.pretty.PrettyObject` objects are not.
This limitation applies as well to `flax <https://flax-linen.readthedocs.io/en/latest/api_reference/flax.linen/module.html>`__ modules.
To use non-frozen default values, use the
:meth:`cdxcore.pretty.PrettyObject.as_field` function::

    from cdxbasics.prettydict import PrettyObject
    from dataclasses import dataclass
    
    @dataclass
    class Data:
    	data : PrettyObject = PrettyObject(x=2).as_field()
    
    	def f(self):
            return self.data.x
    
    d = Data()   # default constructor used.
    d.f()        # -> returns 2

Import
------
.. code-block:: python

    from cdxcore.pretty import PrettyObject as pdct
    
Documentation
-------------
"""

import dataclasses as dataclasses
from dataclasses import Field
import types as types
from collections.abc import Mapping, MutableMapping, Sequence

class __No_Default_dummy():
    pass
no_default = __No_Default_dummy()

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
    
    * The ``a | b`` returns the union of two :class:`cdxcore.pretty.PrettyObject`. Elements of the ``b`` overwrite any elements of ``a``, if they
      are present in both. The order of the new dictionary is determined by the order of appearance of keys in first ``a`` and then ``b``, that 
      means in all but trivial cases ``a|b != b|a``.
      
      The ``|=`` operator is a short-cut for :meth:`cdxcore.pretty.PrettyObject.update`.

    Parameters
    ----------
        copy : Mapping, optional
            If present, assign elements of ``copy`` to ``self``.

        ** kwargs:
            Key/value pairs to be added to ``self``.
    """
    def __init__(self, copy : Mapping = None, **kwargs) -> None:
        """
        :meta private:
        """
        if not copy is None:
            self.update(copy)            
        for k, v in kwargs.items():
            setattr(self, k, v)
            
    def __getitem__(self, key):
        try:
            return getattr( self, key )
        except AttributeError as e:
            raise KeyError(key,*e.args)
            
    def __setitem__(self,key,value):
        """
        Route ``self[key] = value`` to the base class ``__setattr__`` method.
        This way you can assign static functions using ``[]`` which assinging
        functions using ``.`` will assign member functions.
        """
        try:
            super().__setattr__(key, value)
            return self[key]
        except AttributeError as e:
            raise KeyError(key,*e.args)
        
    def __delitem__(self,key):
        try:
            delattr(self, key)
        except AttributeError as e:
            raise KeyError(key,*e.args)
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

    # allow assigning functions with ``self``
    def __setattr__(self, key, value):
        """
        ``__setattr__`` converts function assignments to member functions
        """
        if key[:2] == "__":
            super().__setattr__(key, value)
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

    def get(self, key, default = no_default ):
        """ Equivalent to :meth:`dict.get`. """
        try:
            return getattr(self, key) if default == no_default else getattr(self, key, default)
        except AttributeError as e:
            raise KeyError(key,*e.args)
        
    def pop(self, key, default = no_default ):
        """ Equivalent to :meth:`dict.pop`. """
        try:
            v = getattr(self, key) if default == no_default else getattr(self, key, default)
            delattr(self,key)
            return v
        except AttributeError as e:
            raise KeyError(key,*e.args)
    def setdefault( self, key, default=None ):
        """ Equivalent to :meth:`dict.setdefault`. """
        #return self.__dict__.setdefault(key,default)
        if not hasattr(self, key):
            self.__setattr__(key, default)
        return getattr(self,key)
    
    def update(self, other : Mapping = None, **kwargs):
        """
        Equivalent to :meth:`dict.update`. 
        
        Note that functon assignments are handled in normal dictionary
        fashion - in particular, bound functions will *not* become
        magically unbound.
        """
        if not other is None:
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
        copy = self.copy()
        copy.update(other)
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

    def __neq__(self, other):
        """
        Comparison operator. Unlike dictionary comparison, this comparision operator
        preservers order.
        """
        return not self == other    
    
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
