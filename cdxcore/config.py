"""
Tooling for setting up program-wide configuration hierachies.
Aimed at machine learning programs to ensure consistency of code across experimentation.

Overview
--------

**Basic config construction**::

    from cdxbasics.config import Config, Int
    config = Config()
    config.num_batches = 1000    # object-like assigment of config values
    config.network.depth = 3     # on-the-fly hierarchy generation: here `network` becomes a sub-config
    config.network.width = 100    
    ...
    
    def train(config):
        num_batches = config("num_batches", 10, Int>=2, "Number of batches. Must be at least 2")
        ...
    
Key features
^^^^^^^^^^^^

* Detect misspelled parameters by checking that all parameters provided via a  `config` by a user have been read.

* Provide summary of all parameters used, including summary help for what they were for.

* Nicer object attribute synthax than dictionary notation, in particular for nested configurations.

* Automatic conversion including simple value validation to ensure user-provided values are within
  a given range or from a list of options.

Creating Configs
^^^^^^^^^^^^^^^^

Set data with both dictionary and member notation::
        
    config = Config()
    config['features']           = [ 'time', 'spot' ]   # examplearray-type assignment
    config.scaling               = [ 1., 1000. ]        # example object-type assignment

Reading a Config
^^^^^^^^^^^^^^^^^

When reading the value for a ``key`` from a config, :meth:`cdxcore.config.Config.__call__`
expects a ``key``, a ``default`` value, a ``cast`` type, and a brief ``help`` text.
The function first attempts to find ``key`` in the provided `Config`:

* If ``key`` is found, it casts the value provided for ``key`` using the ``cast`` type and returns.

* If ``key`` is not found, then the default value will be returned (after also being cast using ``cast``).

Example::
    
    from cdxcore.config import Config
    import numpy as np
    
    class Model(object):
        def __init__( self, config ):
            # read top level parameters
            self.features = config("features", [], list, "Features for the agent" )
            self.scaling  = config("scaling", [], np.asarray, "Scaling for the features", help_default="no scaling")
        
    model = Model( config )

Most of the example is self-explanatory, but note that
the :class:'numpy.asarray` provided as ``cast`` parameter for
``weights`` means that any values passed by the user will be automatically
converted to :class:`numpy.ndarray` objects.

The ``help`` text parameter allows providing information on what variables
are read from the config. The latter can be displayed using the function
:meth:`cdxcore.config.Config.usage_report`. (There a number of further parameters to
:meth:`cdxcore.config.Config.__call__` to fine-tune this report such as the ``help_defaults``
parameter used above).

In the above example, ``print( config.usage_report() )`` will return::

    config['features'] = ['time', 'spot'] # Features for the agent; default: []
    config['scaling'] = [   1. 1000.] # Weigths for the agent; default: no initial weights
    
Sub-Configs
^^^^^^^^^^^

You can write and read sub-configurations directly with member notation, without having
to explicitly create an entry for the sub-config:

Assume as before::
    
    config = Config()
    config['features']           = [ 'time', 'spot' ]   
    config.scaling               = [ 1., 1000. ]        

Then create a ``network`` sub configuration with member notation on the fly::
        
    config.network.depth         = 10
    config.network.width         = 100
    config.network.activation    = 'relu'

This is equivalent to::

    config.network               = Config()
    config.network.depth         = 10
    config.network.width         = 100
    config.network.activation    = 'relu'

Now use naturally as follows::

    from cdxcore.config import Config
    import numpy as np
    
    class Network(object):
        def __init__( self, config ):
            self.depth      = config("depth", 1, Int>0, "Depth of the network")
            self.width      = config("width", 1, Int>0, "Width of the network")
            self.activation = config("activation", "selu", str, "Activation function")
            config.done() # see below
    
    class Model(object):
        def __init__( self, config ):
            # read top level parameters
            self.features = config("features", [], list, "Features for the agent" )
            self.weights  = config("weights", [], np.asarray, "Weigths for the agent", help_default="no initial weights")
            self.networks = Network( config.network )
            config.done() # see below
            
    model = Model( config )
  
Imposing Simple Restrictions on Values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``cast`` parameter to :meth:`cdxcore.config.Config.__call__` is a callable; this allows imposing
simple restrictions to any values read from a config.
To this end, import the respective type operators::

    from cdxcore.config import Int, Float

Implement a one-sided restriction::

    # example enforcing simple conditions
    self.width = network('width', 100, Int>3, "Width for the network")

Restrictions on both sides of a scalar::

    # example encorcing two-sided conditions
    self.percentage = network('percentage', 0.5, ( Float >= 0. ) & ( Float <= 1.), "A percentage")

Enforce the value being a member of a list::

    # example ensuring a returned type is from a list
    self.ntype = network('ntype', 'fastforward', ['fastforward','recurrent','lstm'], "Type of network")

We can allow a returned value to be one of several casting types by using tuples.
The most common use case is that ``None`` is a valid value, too.
For example, assume that the ``name`` of the network model should be a string or ``None``.
This is implemented as::

    # example allowing either None or a string
    self.keras_name = network('name', None, (None, str), "Keras name of the network model")

We can combine conditional expressions with the tuple notation::

    # example allowing either None or a positive int
    self.batch_size = network('batch_size', None, (None, Int>0), "Batch size or None for TensorFlow's default 32", help_cast="Positive integer, or None")

Ensuring that we had no Typos & that all provided Data is meaningful
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A common issue when using dictionary-based code configuration is that we might misspell one of the parameters.
Unless this is a mandatory parameter we might not notice that we have not actually
changed its value.

To check that all values of a `config` were read use :meth:`cdxcore.config.Config.done`.
It will alert you if there are keywords or children which have not been read.
Most likely, those will be typos. Consider the following example where ``width`` is misspelled in our config::

    class Network(object):
        def __init__( self, config ):
            # read top level parameters
            self.depth     = config("depth", 1, Int>=1, "Depth of the network")
            self.width     = config("width", 3, Int>=1, "Width of the network")
            self.activaton = config("activation", "relu", help="Activation function", help_cast="String with the function name, or function")
            config.done() # <-- test that all members of config where read

    config                       = Config()
    config.features              = ['time', 'spot']
    config.network.depth         = 10
    config.network.activation    = 'relu'
    config.network.widht         = 100   # (intentional typo)

    n = Network(config.network)

Since ``width`` was misspelled in setting up the config,
a :class:`cdxcore.config.NotDoneError` exception is raised::

    NotDoneError: Error closing Config 'config.network': the following config arguments were not read: widht
    
    Summary of all variables read from this object:
    config.network['activation'] = relu # Activation function; default: relu
    config.network['depth'] = 10 # Depth of the network; default: 1
    config.network['width'] = 3 # Width of the network; default: 3

Note that you can also call :meth:`cdxcore.config.Config.done` at top level::

    class Network(object):
        def __init__( self, config ):
            # read top level parameters
            self.depth     = config("depth", 1, Int>=1, "Depth of the network")
            self.width     = config("width", 3, Int>=1, "Width of the network")
            self.activaton = config("activation", "relu", help="Activation function", help_cast="String with the function name, or function")

    config                       = Config()
    config.features              = ['time', 'spot']
    config.network.depth         = 10
    config.network.activation    = 'relu'
    config.network.widht         = 100   # (intentional typo)

    n = Network(config.network)
    test_features = config("features", [], list, "Features for my network")
    config.done()

produces::

    NotDoneError: Error closing Config 'config.network': the following config arguments were not read: widht

    Summary of all variables read from this object:
    config.network['activation'] = relu # Activation function; default: relu
    config.network['depth'] = 10 # Depth of the network; default: 1
    config.network['width'] = 3 # Width of the network; default: 3
    # 
    config['features'] = ['time', 'spot'] # Features for my network; default: []

You can check the status of the use of the config by using the :attr:`cdxcore.config.Config.not_done` property.

Detaching Child Configs
^^^^^^^^^^^^^^^^^^^^^^^

You can also detach a child config,
which allows you to store it for later use without triggering :meth:`cdxcore.config.Config.done` errors::
    
        def read_config(  self, confg ):
            ...
            self.config_training = config.training.detach()
            config.done()

The function  :meth:`cdxcore.config.Config.detach` will mark he original child but not the detached
child itself as 'done'.
Therefore, we will need to call :meth:`cdxcore.config.Config.done` for the detached child
when we finished processing it::

        def training(self):
            epochs     = self.config_training("epochs", 100, int, "Epochs for training")
            batch_size = self.config_training("batch_size", None, help="Batch size. Use None for default of 32" )

            self.config_training.done()
            
Various Copy Operations
^^^^^^^^^^^^^^^^^^^^^^^

When making a copy of a `config` we will need to decide about the semantics of the operation.
A :class:`cdxcore.config.Config` object contains

* **Inputs**: the user's input hierarchy. This is accessible via :attr:`cdxcore.config.Config.children` and
  :meth:`cdxcore.config.Config.keys`.
  
  All copy operations share (and do not modify) the user's input.
  See also :meth:`cdxcore.config.Config.input_report`.
  
* **Done Status**: to check whether all parameters provided by the users are read by some code `config` keeps
  track of which parameters were read with :meth:`cdxcore.config.Config.__call__`. This list is
  checked against when :meth:`cdxcore.config.Config.done` is called.
  
  This list of elements
  not yet read can be obtained using :meth:`cdxcore.config.Config.input_dict`.
  
* **Consistency**: a :class:`cdxcore.config.Config` object makes sure that if a parameter is requested
  twice with :meth:`cdxcore.config.Config.__call__` then the respective ``default`` and ``help`` values
  are consistency between function calls. This avoids typically divergence of code where one
  part of code assumes a different default value than another.
  
  Recorded consistency information are accessible via 
  :attr:`cdxcore.config.Config.recorder`.
  
  Note that you can read a parameter "quietly" without recording any usage by using the ``[]`` operator.
  
Accordingly, when making a copy of ``self`` we need to determine the relationship of the copy with
above.
  
* :meth:`cdxcore.config.Config.detach`: use case is deferring usage of a config to a later point.

  * *Done status*: ``self`` is marked as "done"; the copy is used keep track of usage of the remaining parameters.
  
  * *Consistency*: both ``self`` and the copy share the same consistency recorder.
  
* :meth:`cdxcore.config.Config.copy`: make an indepedent copy of the current status of ``self``.

  * *Done status*: the copy has an inpendent copy of the "done" status of ``self``.
  
  * *Consistency*: the copy has an inpendent copy of the consistency recorder of ``self``.
  
* :meth:`cdxcore.config.Config.clean_copy`: make an indepedent copy of ``self``, and 
  reset all usage information.

  * *Done status*: the copy has an empty "done" status.
  
  * *Consistency*: the copy has an empty consistency recorder.
  
* :meth:`cdxcore.config.Config.shallow_copy`: make a shallow copy which shares all
  future usage tracking with ``self``. 
  
  The copy acts as a view on ``self``. This is the semantic of the copy constructor.

  * *Done status*: the copy and ``self`` share all "done" status; if a parameter is read with one, it is considered
    "done" by both.
  
  * *Consistency*: the copy and ``self`` share all consistency handling. If a parameter is read with one with a given
    ``default`` and ``help``, the other must use the same values when accessing the same parameter.


Self-Recording All Available Configuration Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once your program ran, you can read the summary of all values read, their defaults, and their help texts::

        print( config.usage_report( with_cast=True ) )
        
Prints::

        config.network['activation'] = relu # (str) Activation function for the network; default: relu
        config.network['depth'] = 10 # (int) Depth for the network; default: 10000
        config.network['width'] = 100 # (int>3) Width for the network; default: 100
        config.network['percentage'] = 0.5 # (float>=0. and float<=1.) Width for the network; default: 0.5
        config.network['ntype'] = 'fastforward' # (['fastforward','recurrent','lstm']) Type of network; default 'fastforward'
        config.training['batch_size'] = None # () Batch size. Use None for default of 32; default: None
        config.training['epochs'] = 100 # (int) Epochs for training; default: 100
        config['features'] = ['time', 'spot'] # (list) Features for the agent; default: []
        config['weights'] = [1 2 3] # (asarray) Weigths for the agent; default: no initial weights

Unique Hash
^^^^^^^^^^^

Another common use case is that we wish to cache the result of some complex operation. 
Assuming that the `config` describes all relevant parameters, and is therefore a valid `ID` for
the data we wish to cache, we can use :meth:`cdxcore.config.Config.unique_hash`
to obtain a unique hash ID for the given config.

:class:`cdxcore.config.Config` also implements
the custom hashing protocol ``__unique_hash__`` defined by :class:`cdxcore.uniquehash.UniqueHash`,
which means that if a ``Config`` is used during a hashing function from :mod:`cdxcore.uniquehash`
the config will be hashed correctly.

A fully transparent caching framework which supports code versioning and transparent
hashing of function parameters is implemented with :meth:`cdxcore.subdir.SubDir.cache`.

Consistent ** kwargs Handling
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `Config` class can be used to improve ``** kwargs`` handling.
Assume we have::

        def f(** kwargs):
            a = kwargs.get("difficult_name", 10)
            b = kwargs.get("b", 20)

We run the usual risk of a user mispronouncing a parameter name which we would never know.
Therefore we may improve upon the above with::

        def f(**kwargs):
            kwargs = Config(kwargs)
            a = kwargs("difficult_name", 10)
            b = kwargs("b", 20)
            kwargs.done()

If now a user calls ``f`` with, say, ``config(difficlt_name=5)`` an error will be raised.

A more advanced pattern is to allow both ``config`` and ``kwargs`` function parameters. In this case, the user
can both provide a ``config`` or specify its parameters directory::

        def f( config=None, **kwargs):
            config = Config.config_kwargs(config,kwargs)
            a = config("difficult_name", 10, int)
            b = config("b", 20, int)
            config.done()
            
Any of the following function calls are now valid::
    
        f( Config(difficult_name=11, b=21) )        # use a Config
        f( difficult_name=12, b=22 )                # use a kwargs
        f( Config(difficult_name=11, b=21), b=22 )  # use both; kwargs overwrite config values
            
Dataclasses
^^^^^^^^^^^

:mod:`dataclasses` rely on default values of any member being "frozen" objects, which most user-defined objects and
:class:`cdxcore.config.Config` objects are not.
This limitation applies as well to `flax <https://flax-linen.readthedocs.io/en/latest/api_reference/flax.linen/module.html>`__ modules.
To use non-frozen default values, use the
:meth:`cdxcore.config.Config.as_field` function::

    from cdxcore.config import Config
    from dataclasses import dataclass
    
    @dataclass
    class Data:
    	data : Config = Config().as_field()
    
        def f(self):
            return self.data("x", 1, Int>0, "A positive integer")
    
    d = Data()   # default constructor used.
    d.f()

Import
------
.. code-block:: python

    from cdxcore.config import Config
    
Documentation
-------------
"""

from collections import OrderedDict
from collections.abc import Mapping, Callable
from sortedcontainers import SortedDict
import dataclasses as dataclasses
from dataclasses import Field
from .err import verify, warn_if
from .uniquehash import UniqueHash, DebugTrace
from .pretty import PrettyObject as pdct
from .util import fmt_list

class _ID(object):
    pass

#: Value indicating no default is available for a given parameter.
no_default = _ID()    

# ==============================================================================
#
# Actual Config class
#
# ==============================================================================

class Config(OrderedDict):
    """
    A simple `Config` class for hierarchical dictionary-like configurations but with type checking, detecting
    missspelled parameters, and simple built-in help.

    See :mod:`cdxcore.config` for an extensive discussion of features.

    Parameters
    ----------
        *args : list
            List of ``Mapping`` to iteratively create a new config with.
            
            If the first element is a ``Config``, and no other parameters are passed,
            then this object will be a shallow copy of that ``Config``.
            It then shares all usage recording. See :meth:`cdxcore.config.Config.shallow_copy`.
            
        config_name : str, optional
            Name of the configuration for report_usage. Default is ``"config"``.
            
        ** kwargs : dict
            Additional key/value pairs to initialize the config with, e.g.``Config(a=1, b=2)``.

    """

    def __init__(self, *args, config_name : str = None, **kwargs) -> None:
        """
        Create a :class:`cdxcore.config.Config`.
        """
        if len(args) == 1 and isinstance(args[0], Config) and config_name is None and len(kwargs) == 0:
            source               = args[0]
            self._done           = source._done
            self._name           = source._name
            self._recorder       = source._recorder
            self._children       = source._children
            self.update(source)
            return

        OrderedDict.__init__(self)
        self._done           = set()
        self._name           = config_name if not config_name is None else "config"
        self._children       = OrderedDict()
        self._recorder       = SortedDict()
        self._recorder._name = self._name
        for k in args:
            if not k is None:
                self.update(k)
        self.update(kwargs)

    # Information
    # -----------

    @property
    def config_name(self) -> str:
        """ Qualified name of this config. """
        return self._name

    @property
    def children(self) -> OrderedDict:
        """ Dictionary of the child configs of ``self``. """
        return self._children

    def __str__(self) -> str:
        """ Print myself as dictionary. """
        s = self.config_name + str(self.as_dict(mark_done=False))
        return s

    def __repr__(self) -> str:
        """ Print myself as reconstructable object. """
        s = repr(self.as_dict(mark_done=False))
        s = "Config( **" + s + ", config_name='" + self.config_name + "' )"
        return s

    @property
    def is_empty(self) -> bool:
        """ Whether any parameters have been set, at parent level or at any child level. """
        if len(self) > 0:
            return False
        for c in self._children.values():
            if not c.is_empty:
                return False
        return True
    
    # conversion
    # ----------

    def as_dict(self, mark_done : bool = True ) -> dict:
        """
        Convert ``self`` into a dictionary of dictionaries.

        Parameters
        ----------
            mark_done : bool
                If True, then all members of this config will be considered "done" 
                upon return of this function.

        Returns
        -------
            Dict : dict
                Dictionary of dictionaries.
        """
        d = { key : self.get(key) if mark_done else self.get_raw(key) for key in self }
        for n, c in self._children.items():
            if n == '_ipython_canary_method_should_not_exist_':
                continue
            c = c.as_dict(mark_done)
            verify( not n in d, "Cannot convert Config to dictionary: found both a regular value, and a child with name '{n}'", n)
            d[n] = c
        return d
    
    def as_field(self) -> Field:
        """
        This function provides support for :class:`dataclasses.dataclass` fields
        with ``Config`` default values.
        
        When adding a field with a non-frozen default value to a ``@dataclass`` class,
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
                data : Config = Config(x=2).as_field()

            a = A() 
            print(a.data['x'])  # -> "2"
            a = A(data=Config(x=3)) 
            print(a.data['x'])  # -> "3"
        """
        def factory():
            return self
        return dataclasses.field( default_factory=factory )

    # handle finishing config use
    # ---------------------------

    def done(self, include_children : bool = True, mark_done : bool = True ):
        """
        Closes the config and checks that no unread parameters remain. This is used
        to detect typos in configuration files.
        
        Raises a
        :class:`cdxcore.config.NotDoneError` if there are unused parameters in ``self``.
        
        Consider this example::

            config = Config()
            config.a = 1
            config.child.b = 2

            _ = config.a # read a
            child = config.child
            config.done()     # error because config.child.b has not been read yet
            
            print( child.b )

        This example raises an error because ``config.child.b`` was not read. If you wish to process
        the sub-config ``config.child`` later, use :meth:`cdxcore.config.Config.detach`::

            config = Config()
            config.a = 1
            config.child.b = 2

            _ = config.a # read a
            child = config.child.detach()
            config.done()   # no error, even though confg.child.b has not been read yet

            print( child.b )
            child.done()    # need to call done() for the child

        By default this function also validates that all child configs were "done".

        **See Also**

        * :meth:`cdxcore.config.Config.mark_done` marks all parameters as "done" (used).
        
        * :meth:`cdxcore.config.Config.reset_done` marks all parameters as "not done".
        
        * :meth:`cdxcore.config.Config.clean_copy` makes a copy of ``self`` without any usage information.
        
        * Introduction to the various copy operations in :mod:`cdxcore.config`.

        Parameters
        ----------
            include_children: bool
                Validate child configs, too. Stronly recommended default.
            mark_done:
                Upon completion mark this config as 'done'.
                This stops it being modified; that also means subsequent calls to done() will be successful.
                
        Raises
        ------
            :class:`cdxcore.config.NotDoneError`
                If not all elements were read.
        """
        inputs = set(self)
        rest   = inputs - self._done
        if len(rest) > 0:
            raise NotDoneError( rest, self.config_name,
                                      f"Error closing Config '{self._name}': the following config arguments were not read: {fmt_list(rest)}\n\n"\
                                      f"Summary of all variables read from this object:\n{self.usage_report(filter_path=self.config_name)}" )
        if include_children:
            for _, c in self._children.items():
                c.done(include_children=include_children,mark_done=False)
        if mark_done:
            self.mark_done(include_children=include_children)
        return

    def reset(self):
        """
        Reset all usage information.

        Use :meth:`cdxcore.config.Config.reset_done` to only reset the information whether a key was used,
        but to keep consistency information on previously used default and/or help values.
        """
        self._done.clear()
        self._recorder.clear()

    def reset_done(self):
        """
        Reset the internal list of which are "done" (used).
        
        Typically "done" means that a parameter
        has been read using :meth:`cdxcore.config.Config.call`.
        
        This function does not reset the consistency recording of previous uses of each key.
        This ensures consistency of default values between uses of keys.
        Use :meth:`cdxcore.config.Config.reset` to reset all "done" and reset all usage records.
        
        See also the summary on various copy operations in :mod:`cdxcore.config`.
        """
        self._done.clear()

    def mark_done(self, include_children : bool = True ):
        """
        Mark all members as "done" (having been used).
        """
        self._done.update( self )
        if include_children:
            for _, c in self._children.items():
                c.mark_done(include_children=include_children)

    # making copies
    # -------------

    def _detach( self,  *, mark_self_done : bool, copy_done : bool, new_recorder ):
        """
        Creates a copy of the current config, with a number of options how to share usage information.
        
        Use the functions
            detach()
            copy()
            clean_copy()
        instead.

        Parameters
        ----------
            mark_self_done : bool
                If True mark 'self' as 'read', otherwise not.
            copy_done : bool
                If True, create a copy of self._done, else remove all 'done' information
            new_recorder :
                <recorder> if a recorder is specified, use it.
                "clean": use a new, empty recorder
                "copy": use a new recorder which is a copy of self.recorder
                "share": share the same recorder

        Returns
        -------
            A new config
        """
        config = Config()
        config.update(self)
        config._done             = set( self._done ) if copy_done else config._done
        config._name             = self._name
        if isinstance( new_recorder, SortedDict ):
            config._recorder     = new_recorder
        elif new_recorder == "clean":
            new_recorder         = config._recorder
        elif new_recorder == "share":
            config._recorder     = self._recorder
        else:
            assert new_recorder == "copy", "Invalid value for 'new_recorder': %s" % new_recorder
            config._recorder.update( self._recorder )

        config._children         = { k: c._detach(mark_self_done=mark_self_done, copy_done=copy_done, new_recorder=new_recorder) for k, c in self._children.items() }
        config._children         = OrderedDict( config._children )

        if mark_self_done:
            self.mark_done()
        return config

    def detach( self ):
        """
        Returns a copy of ``self``, and sets ``self`` to "done".
        
        The purpose of this function is to defer using a config (often a sub-config) to a later point,
        while maintaining consistency of usage.

        * The copy has the same "done" status as ``self`` at the time of calling ``detach()``.

        * The copy shares usage consistency checks with ``self``, i.e. if the same parameter is
          read with different ``default`` or ``help`` values an error is raised.

        * The function flags ``self`` as "done" using :meth:`cdxcore.config.Config.mark_done`.

        For example::

            class Example(object):
            
                def __init__( config ):
                    self.a      = config('a', 1, Int>=0, "'a' value")
                    self.later  = config.later.detach()  # detach sub-config
                    self._cache = None
                    config.done()
                
                def function(self):
                    if self._cache is None:
                        self._cache = Cache(self.later)  # deferred use of the self.later config. Cache() calls done() on self.later
                    return self._cache
 
        See also the summary on various copy operations in :mod:`cdxcore.config`.

        Returns
        -------
            copy : Config
                A copy of ``self``.
        """
        return self._detach(mark_self_done=True, copy_done=True, new_recorder="share")

    def copy( self ):
        """
        Return a fully independent copy of ``self``.
        
        * The copy has an independent "done" status of ``self``.
        
        * The copy has an independent usage consistency status.
        
        * ``self`` will remain untouched. In particular, in contrast to :meth:`cdxcore.config.Config.detach`
          it will not be set to "done".

        As an example, the following allows using different default values for
        config members of the same name::

            base = Config()
            _ = base('a', 1)   # read a with default 1

            copy = base.copy() # copy will know 'a' as used with default 1
                               # 'b' was not used yet

            _ = base('b', 111) # read 'b' with default 111
            _ = copy('b', 222) # read 'b' with default 222 -> ok
        
            _ = copy('a', 2)   # use 'a' with default 2 -> will fail
            
        Use :meth:`cdxcore.config.Config.clean_copy` for making a copy which discards any prior
        usage information.

        See also the summary on various copy operations in :mod:`cdxcore.config`.
        """
        return self._detach( mark_self_done=False, copy_done=True, new_recorder="copy" )

    def clean_copy( self ):
        """
        Make a copy of ``self``, and reset it to the original input state from the user.

        As an example, the following allows using different default values for
        config members of the same name::

            base = Config()
            _ = base('a', 1)   # read a with default 1

            copy = base.copy() # copy will know 'a' as used with default 1
                               # 'b' was not used yet

            _ = base('b', 111) # read 'b' with default 111
            _ = copy('b', 222) # read 'b' with default 222 -> ok
        
            _ = copy('a', 2)   # use 'a' with default 2 -> ok

        Use :meth:`cdxcore.config.Config.copy` for a making a copy which
        tracks prior usage information.

        See also the summary on various copy operations in :mod:`cdxcore.config`.

        """
        return self._detach( mark_self_done=False, copy_done=False, new_recorder="clean" )

    def shallow_copy( self ):
        """
        Return a shallow copy of ``self`` which shares all usage tracking with ``self``
        going forward.
        
        * The copy shares the "done" status of ``self``.
        
        * The copy shares all consistency usage status of ``self``.
        
        * ``self`` will not be flagged as 'done'
        """
        return Config(self)

    # Read
    # -----

    def __call__(self, key          : str,
                       default      = no_default,
                       cast         : Callable = None,
                       help         : str = None,
                       help_default : str = None,
                       help_cast    : str = None,
                       mark_done    : bool = True,
                       record       : bool = True ):
        """
        Reads a parameter ``key`` from the `config` subject to casting with ``cast``.
        If not found, return ``default``

        Examples::

            config("key")                      # returns the value for 'key' or if not found raises an exception
            config("key", 1)                   # returns the value for 'key' or if not found returns 1
            config("key", 1, int)              # if 'key' is not found, return 1. If it is found cast the result with int().
            config("key", 1, int, "A number"   # also stores an optional help text.
                                               # Call usage_report() after the config has been read to a get a full
                                               # summary of all data requested from this config.
                                                 
        Use :attr:`cdxcore.config.Int` and :attr:`cdxcore.config.Float` to ensure a number
        is within a given range::
              
            config("positive_int", 1, Int>=1, "A positive integer")
            config("ranged_int", 1, (Int>=0)&(Int<=10), "An integer between 0 and 10, inclusive")
            config("positive_float", 1, Float>0., "A positive integerg"

        Choices are implemented with lists::
            
            config("difficulty", 'easy', ['easy','medium','hard'], "Choose one")
                
        Alternative types are implemented with tuples::

            config("difficulty", None, (None, ['easy','medium','hard']), "None or a level of difficulty")
            config("level", None, (None, Int>=0), "None or a non-negative level")

        Parameters
        ----------
            key : string
                Keyword to read.
                
            default : optional
                Default value.
                Set to :attr:`cdxcore.config.Config.no_default` for mandatory parameters without default.
                If then 'key' cannot be found a :class:`KeyError` is raised.
                
            cast : Callable, optional

                If ``None``, any value provided by the user will be acceptable.
                
                If not ``None``, the function will attempt to cast the value provided by the user
                with ``cast()``.
                For example, if ``cast = int``, then the function will apply ``int(x)`` to the user's input ``x``.
                
                This function also allows passing the following complex arguments:
                    
                * A list, in which case it is assumed that the ``key`` must be from this list. The type of the first element of the list will be
                  used to ``cast()`` values to the target type.
                
                * :attr:`cdxcore.config.Int` and :attr:`cdxcore.config.Float` allow defining constrained integers and floating point numbers, respectively.
                
                * A tuple of types, in which case any of the types is acceptable.
                  A ``None`` here means that the value ``None`` is acceptabl
                  (it does not mean that any value is acceptable).
                
                * Any callable to validate a parameter.
                                
            help : str, optional
                If provied adds a help text when self documentation is used.
            help_default : str, optional
                If provided, specifies the default value in plain text.
                If not provided, ``help_default`` is equal to the string representation of the ``default`` value, if any.
                Use this for complex default values which are hard to read.
            help_cast : str, optional
                If provided, specifies a description of the cast type.
                If not provided, ``help_cast`` is set to the string representation of ``cast``, or
                ``None`` if ``cast` is ``None``. Complex casts are supported.
                Use this for cast types which are hard to read.
            mark_done : bool, optional
                If true, marks the respective element as read once the function returned successfully.
            record : bool, optional
                If True, records consistency usage of the key and validates that previous usage of the key is consistent with
                the current usage, e.g. that the default values are consistent and that if help was provided it is the same.

        Returns
        -------
            Parameter value.
            
        Raises
        ------
            :class:`KeyError`:
                If ``key`` could not be found.
                
            :class:`ValueError`:
                For input errors.

            :class:`cdxcore.config.InconsistencyError`:
                If ``key`` was previously accessed with different ``default``, ``help``, ``help_default`` or 
                ``help_cast`` values.
                For all the help texts empty strings are not compared, i.e.
                ``__call__("x", default=1)`` will succeed even if a previous call was
                ``__call__("x", default=1, help="value for x")``.
                
                Note that ``cast`` is not validated.

            :class:`cdxcore.config.CastError`:
                If an error occcurs casting a provided value.

        """
        verify( isinstance(key, str), "'key' must be a string but is of type '{typ}'. Key value was '{key}'", typ=type(key), key=key, exception=ValueError )
        verify( key.find('.') == -1 , "Error using Config '{name}': key name cannot contain '.'; found '{key}'", name=self.config_name, key=key, exception=ValueError  )

        # determine raw value
        if not key in self:
            if default == no_default:
                raise KeyError(key, "Error using config '%s': key '%s' not found " % (self.config_name, key))
            value = default
        else:
            value = OrderedDict.get(self,key)

        # has user only specified 'help' but not 'cast' ?
        if isinstance(cast, str) and help is None:
            help = cast
            cast = None
            
        # castdef
        caster = _create_caster( cast=cast, config_name=self._name, key_name=key, none_is_any = True )
        try:
            value  = caster( value, config_name=self._name, key_name=key )
        except CastError as e:
            assert False, "Casters should not throw CastError's"
            raise e
        except Exception as e:
            raise CastError( key=key, config_name=self._name, exception=e )

        # mark key as read
        if mark_done:
            self._done.add(key)

        # avoid recording
        if not record:
            return value
        # record?
        record_key    = self.record_key( key ) # using a fully qualified keys allows 'recorders' to be shared across copy()'d configs.
        help          = str(help) if not help is None and len(help) > 0 else ""
        help          = help[:-1] if help[-1:] == "." else help  # remove trailing '.'
        help_default  = str(help_default) if not help_default is None else ""
        help_default  = str(default) if default != no_default and len(help_default) == 0 else help_default
        help_cast     = str(help_cast) if not help_cast is None else str(caster)
        verify( default != no_default or help_default == "", "Config %s setup error for key %s: cannot specify 'help_default' if no default is given", self.config_name, key, exception=ValueError  )

        raw_use       = help == "" and help_cast == "" and help_default == "" # raw_use, e.g. simply get() or []. Including internal use

        exst_value    = self._recorder.get(record_key, None)

        if exst_value is None:
            # no previous recorded use --> record this one, even if 'raw'
            record = SortedDict(value=value,
                                raw_use=raw_use,
                                help=help,
                                help_default=help_default,
                                help_cast=help_cast )
            if default != no_default:
                record['default'] = default
            self._recorder[record_key] = record
            return value

        if raw_use:
            # do not compare raw_use with any other use
            return value

        if exst_value['raw_use']:
            # previous usesage was 'raw'. Record this new use.
            record = SortedDict(value=value,
                                raw_use=raw_use,
                                help=help,
                                help_default=help_default,
                                help_cast=help_cast )
            if default != no_default:
                record['default'] = default
            self._recorder[record_key] = record
            return value

        # Both current and past were bona fide recorded uses.
        # Ensure that their usage is consistent.
        # Note that we do *not* check consistency of the cast operator.
        if default != no_default:
            if 'default' in exst_value:
                if exst_value['default'] != default:
                    raise InconsistencyError(key, self.config_name, "Key '%s' of config '%s' (%s) was read twice with different default values '%s' and '%s'" % ( key, self.config_name, record_key, exst_value['default'], default ))
            else:
                exst_value['default'] = default

        if help != "":
            if exst_value['help'] != "":
                if exst_value['help'] != help:
                    raise InconsistencyError(key, self.config_name, "Key '%s' of config '%s' (%s) was read twice with different 'help' texts '%s' and '%s'" % ( key, self.config_name, record_key, exst_value['help'], help ) )
            else:
                exst_value['help'] = help

        if help_default != "":
            if exst_value['help_default'] != "":
                # we do not insist on the same 'help_default'
                if exst_value['help_default'] != help_default:
                    raise InconsistencyError(key, self.config_name, "Key '%s' of config '%s' (%s) was read twice with different 'help_default' texts '%s' and '%s'" % ( key, self.config_name, record_key, exst_value['help_default'], help_default ) )
            else:
                exst_value['help_default'] = help_default

        if help_cast != "" and help_cast != _Simple.STR_NONE_CAST:
            if exst_value['help_cast'] != "" and exst_value['help_cast'] != _Simple.STR_NONE_CAST:
                if exst_value['help_cast'] != help_cast:
                    raise InconsistencyError(key, self.config_name, "Key '%s' of config '%s' (%s) was read twice with different 'help_cast' texts '%s' and '%s'" % ( key, self.config_name, record_key, exst_value['help_cast'], help_cast ))
            else:
                exst_value['help_cast'] = help_cast
        # done
        return value

    def __getitem__(self, key : str):
        """
        Returns the item for 'key' *without* recording its usage which for example means that done() will assume it hasn't been read.
        Equivalent to get_raw(key).
        
        __getitem__ does not record usage as many Python functions will use to iterate through objects (recall that Config is derived from OrderedDict)
        """
        return self.get_raw(key)

    def __getattr__(self, key : str):
        """
        Returns either the value for 'key', if it exists, or creates on-the-fly a child config with the name 'key' and returns it.
        If an existing child value is returned, its usage is *not* recorded which for example means that done() will assume it hasn't been read.
        
        Because __getattr__ will generte child configs on the fly it means the following is a legitmate use:            
            config = Config()
            config.sub.x = 1  # <-- create 'sub' on the fly
        """
        verify( key.find('.') == -1 , "Error using Config '{name}': key name cannot contain '.'; found '{key}", name=self.config_name, key=key, exception=ValueError )
        if key in self._children:
            return self._children[key]
        verify( key.find(" ") == -1, "Error using Config '{name}': sub-config names cannot contain spaces. Found '{key}'", name=self.config_name, key=key, exception=ValueError )
        config = Config()
        config._name              = self._name + "." + key
        config._recorder          = self._recorder
        self._children[key]       = config
        return config

    def get(self, *kargs, **kwargs ):
        """
        Returns :meth:`cdxcore.config.Config.__call__` ``(*kargs, **kwargs)``.
        """
        return self(*kargs, **kwargs)

    def get_default(self, *kargs, **kwargs ):
        """
        Returns :meth:`cdxcore.config.Config.__call__` ``(*kargs, **kwargs)``.
        """
        return self(*kargs, **kwargs)

    def get_raw(self, key : str, default = no_default ):
        """
        Reads the raw value for ``key`` without any casting,
        nor marking the element as read, nor recording access to the element.        
        
        Equivalent to using 
        :meth:`cdxcore.config.Config.__call__` ``(key, default, mark_done=False, record=False )``
        which, without ``default``, is turn itself equivalent to ``self[key]``
        """
        return self(key, default, mark_done=False, record=False)

    def get_recorded(self, key : str ):
        """
        Returns the casted value returned for ``key`` previously.
        
        If the parameter ``key`` was provided as part of the input data, this value is returned, subject
        to casting.
        
        If ``key`` was not part of the input data, and a ``default`` was provided when the
        parameter was read with :meth:`cdxcore.config.Config.__call__`, then return this default value, subject
        to casting.

        Raises
        ------
            :class:`KeyError`:
                If the key was not previously read successfully.
        """
        verify( key.find('.') == -1 , "Error using Config '{name}': key name cannot contain '.'; found '{key}", name=self.config_name, key=key, exception=ValueError )
        record_key    = self._name + "['" + key + "']"    # using a fully qualified keys allows 'recorders' to be shared across copy()'d configs.
        record        = self._recorder.get(record_key, None)
        if record is None:
            raise KeyError(key)
        return record['value']

    def keys(self) -> list:
        """
        Returns the keys for the immediate parameters of this config.
        This call will *not* return the names of child config; use :attr:`cdxcore.config.Config.children`.
        
        Use :meth:`cdxcore.config.Config.input_dict` to obtain the full hierarchy of input parameters.
        """
        return OrderedDict.keys(self)

    # Write
    # -----

    def __setattr__(self, key : str, value):
        """
        Assign value using member notation: ``self.key = value``.
        
        Identical to ``self[key] = value``.
        Do not use leading underscores for `config` variables, see below

        Parameters
        ----------
            key : str
                ``key`` to store ``value`` for.

                Key to store. Note that keys starting with underscores are *not* stored as standard
                parameter values,
                but become classic members of the object (in ``self.__dict__``).
                
            value :
                The value for ``key``.
            
                If ``value`` is a ``Config`` object, then a child config is created::

                    config     = Config()
                    config.sub = Config(a=1)
                    a          = config.sub("a", 0, int, "Test")
                    config.done() # <- no error is reported, usage_report() is correct
                    
                *Expert Usage Comment:*
                this function assumes that if ``value`` is a config it is not used elsewhere.
                In particular its usage will be reset, and its consistency recorder aligned
                with ``self``. To avoid side effects for `config`s you wish to re-use elsewhere,
                call :meth:`cdxcore.config.Config.clean_copy` first.                    
        """
        self.__setitem__(key,value)

    def __setitem__(self, key : str, value):
        """
        Assign a ``value`` to ``key`` using array notation ``self[key] = value``.
                
        Identical to ``self.key = value``.

        Parameters
        ----------
            key : str
                ``key`` to store ``value`` for.
                
                Key to store. Note that keys starting with underscores are *not* stored as standard
                parameter values,
                but become classic members of the object (in ``self.__dict__``).

                ``key`` may contain '.' for hierarchical access.

            value :
                If ``value`` is a ``Config`` object, then a child config is created::

                    config     = Config()
                    config.sub = Config(a=1)
                    a          = config.sub("a", 0, int, "Test")
                    config.done() # <- no error is reported, usage_report() is correct
                    
                *Expert Usage Comment:*
                this function assumes that if ``value`` is a config it is not used elsewhere.
                In particular its usage will be reset, and its consistency recorder aligned
                with ``self``. To avoid side effects for `config`s you wish to re-use elsewhere,
                call :meth:`cdxcore.config.Config.clean_copy` first.
        """
        if key[0] == "_" or key in self.__dict__:
            OrderedDict.__setattr__(self, key, value )
        elif isinstance( value, Config ):
            warn_if( len(value._recorder) > 0, "Warning: when assigning a used Config to another Config, all existing usage will be reset. "
                                               "The 'recorder' of the assignee will be set ot the recorder of the receiving Config. "
                                               "Make a 'clean_copy()' to avoid this warning.")
            value._name  = self._name + "." + key
            def update_recorder( config ):
                config._recorder = self._recorder
                config._done.clear()
                for k, c in config._children.items():
                    c._name     = config._name + "." + k
                    update_recorder(c)
            update_recorder(value)
            self._children[key]      = value
        else:
            keys = key.split(".")
            if len(keys) == 1:
                OrderedDict.__setitem__(self, key, value)
            else:
                c = self
                for key in keys[:1]:
                    c = c.__getattr__(key)
                OrderedDict.__setitem__(c, key, value)

    def update( self, other  = None, **kwargs ):
        """
        Overwrite values of 'self' new values.
        Accepts the two main formats::

            update( dictionary )
            update( config )
            update( a=1, b=2 )
            update( {'x.a':1 } )  # hierarchical assignment self.x.a = 1

        Parameters
        ----------
            other : dict, Config
            
                Copy all content of ``other`` into``self``.

                If ``other`` is a config: elements will be clean_copy()ed; ``other`` will not be marked as "read".

                If ``other`` is a dictionary, then '.' notation can be used for hierarchical assignments 

            **kwargs
                Allows assigning specific values.
                
        Returns
        -------
            self : Config
        """
        if not other is None:
            if isinstance( other, Config ):
                # copy() children
                # and reset recorder to ours.
                def set_recorder(config, recorder):
                    config._recorder = recorder
                    for _,c in config._children.items():
                        set_recorder( c, recorder )
                for sub, child in other._children.items():
                    assert isinstance(child,Config)
                    if sub in self._children:
                        self._children[sub].update( child )
                    else:
                        self[sub] = child.clean_copy() # see above for assigning config
                    assert sub in self._children
                    assert not sub in self
                # copy elements from other.
                # we do not mark elements from another config as 'used'
                for key in other:
                    if key in self._children:
                        del self._children[key]
                    self[key] = other.get_raw(key)
                    assert key in self
                    assert not key in self._children
            else:
                verify( isinstance(other, Mapping), "Cannot update a Config with an object of type '{typ}'. Expected 'Mapping' type.", typ=type(other).__name__, exception=ValueError )
                for key in other:
                    if key[:1] == "_" or key in self.__dict__:
                        continue
                    if isinstance(other[key], Mapping):
                        if key in self:
                            del self[key]
                        elif not key in self._children:
                            self.__getattr__(key)  # creates child
                        self._children[key].update( other[key] )
                    else:
                        if key in self._children:
                            del self._children[key]
                        self[key] = other[key]

        if len(kwargs) > 0:
            self.update( other=kwargs )
        return self

    # delete
    # ------

    def delete_children( self, names : list ):
        """
        Delete one or several children from ``self``.
        
        This function does not delete recorded consistency information (``defaults`` and ``help``
        recorded from prior uses of :meth:`cdxcore.config.Config.__call__`).
        """
        if isinstance(names, str):
            names = [ names ]

        for name in names:
            del self._children[name]

    # Usage information & reports
    # ---------------------------

    def usage_report(self,    with_values  : bool = True,
                              with_help    : bool = True,
                              with_defaults: bool = True,
                              with_cast    : bool = False,
                              filter_path  : str  = None ) -> str:
        """
        Generate a human readable report of all variables read from this config.

        Parameters
        ----------
            with_values : bool, optional
                Whether to also print values. This can be hard to read
                if values are complex objects

            with_help: bool, optional
                Whether to print help

            with_defaults: bool, optional
                Whether to print default values

            with_cast: bool, optional
                Whether to print types

            filter_path : str, optional
                If provided, will match the beginning of the fully qualified path of all children vs this string.
                Most useful with ``filter_path = self.config_name`` which ensures only children of this (child) config
                are shown.

        Returns
        -------
            Report : str
        """
        with_values   = bool(with_values)
        with_help     = bool(with_help)
        with_defaults = bool(with_defaults)
        with_cast     = bool(with_cast)
        l             = len(filter_path) if not filter_path is None else 0
        rep_here      = ""
        reported      = ""

        for key, record in self._recorder.items():
            value        =  record['value']
            help         =  record['help']
            help_default =  record['help_default']
            help_cast    =  record['help_cast']
            report       =  key + " = " + str(value) if with_values else key

            do_help      =  with_help and help != ""
            do_cast      =  with_cast and help_cast != ""
            do_defaults  =  with_defaults and help_default != ""

            if do_help or do_cast or do_defaults:
                report += " # "
                if do_cast:
                    report += "(" + help_cast + ") "
                if do_help:
                    report += help
                    if do_defaults:
                        report += "; default: " + help_default
                elif do_defaults:
                    report += "Default: " + help_default

            if l > 0 and key[:l] == filter_path:
                rep_here += report + "\n"
            else:
                reported += report + "\n"

        if len(reported) == 0:
            return rep_here
        if len(rep_here) == 0:
            return reported
        return rep_here + "# \n" + reported

    def usage_reproducer(self) -> str:
        """
        Returns a string representation of current usage, calling :func:`repr`
        for each value.
        """
        report = ""
        for key, record in self._recorder.items():
            value        =  record['value']
            report       += key + " = " + repr(value) + "\n"
        return report

    def input_report(self, max_value_len : int = 100) -> str:
        """
        Returns a report of all inputs in a readable format. Assumes
        that :func:`str` converts all values into some readable format.
        
        Parameters
        ----------
            max_value_len : int
                Limits the length of :func:`str` for each value to ``max_value_len`` characters.
                Set to ``None`` to not limit the length.
                
        Returns
        -------
            Report : str
        """
        inputs = []
        def max_value( s ):
            return s if max_value_len is None or len(s) < max_value_len else ( s[:max_value_len-3] + "..." )
        def ireport(self, inputs):
            for key in self:
                value      = self.get_raw(key)
                report_key = f"{self._name}[{key}] = {max_value(str(value))}"
                inputs.append( report_key )
            for c in self._children.values():
                ireport(c, inputs)
        ireport(self, inputs)

        inputs = sorted(inputs)
        report = ""
        for i in inputs:
            report += i + "\n"
        return report

    @property
    def not_done(self) -> dict:
        """
        Returns a dictionary of keys which were not read yet.
        
        Returns
        -------
            not_done: dict
                Dictionary of dictionaries: for value parameters, the respective entry is their ``key`` and ``False``;
                for children the ``key`` is followed by their ``not_done`` dictionary.
        """
        h = { key : False for key in self if not key in self._done }
        for k,c in self._children.items():
            ch = c.not_done
            if len(ch) > 0:
                h[k] = ch
        return h

    @property
    def recorder(self) -> SortedDict:
        """ Returns the "recorder", a :class:`sortedcontainers.SortedDict` which contains
        ``key``, ``default``, ``cast``, ``help``, and all other function parameters for
        all calls of :meth:`cdxcore.config.Config.__call__`. It is used to ensure consistency
        of parameter calls.
        
        *Use for debugging only.*
        """
        return self._recorder

    def input_dict(self, ignore_underscore = True ) -> pdct:
        """ Returns a :class:`cdxcore.pretty.PrettyObject` of all inputs into this config. """
        inputs = pdct()
        for key in self:
            if ignore_underscore and key[:1] == "_":
                continue
            inputs[key] = self.get_raw(key)
        for k,c in self._children.items():
            if ignore_underscore and k[:1] == "_":
                continue
            inputs[k] = c.input_dict()
        return inputs
    
    def usage_value_dict( self ) -> SortedDict:
        """
        Return a flat sorted dictionary of both "used" and, where not used, "input" values.
        
        A "used" value has either been read from user input or was provided as a default. In both cases,
        it will have been subject to casting. 

        This function will raise a :class:`RuntimeError` in either of the following two cases:
            
        * A key was marked as "done" (read), but no "value" was recorded at that time. A simple example is when :meth:`cdxcore.config.Config.detach` 
          was called to create a child config, but that config has not yet been read.
        * A key has not been read yet, but there is a record of a value being returned. An example of this happening is if :meth:`cdxcore.config.Config.reset_done`
          is called.
        """
        uvd = SortedDict()
        for key, record in self._recorder.items():
            uvd[key] = record['value']

        def add_inputs( config ):
            for key in config:
                full_key = config.record_key( key )
                if key in config._done:
                    verify( full_key in uvd, lambda : f"Error collecting 'usage_value_dict': key '{key}' with full name '{full_key}' is marked as `done` but has no recorder entry. "+\
                                                       "This typically happens when a sub-config is detached(), and has not been used yet." )
                else:
                    verify( not full_key in uvd, lambda : f"Error collecting 'usage_value_dict': key '{key}' with full name '{full_key}' is not yet marked as `done` but has a recorder entry" )
                    uvd[full_key] = config[key]
            for c in config._children.values():
                add_inputs(c)
                
        add_inputs(self)
        return uvd
            
    # hashing
    # -------

    def unique_hash(self, *, unique_hash : Callable = None, debug_trace : DebugTrace = None, input_only : bool = True, **unique_hash_parameters ) -> str:
        r"""
        Returns a unique hash key for this object - based on its provided inputs and
        *not* based on its usage.

        This function allows both provision of an existing ``unique_hash`` function or
        to specify one on the fly using ``unique_hash_parameters``. 
        That means instead of::
                
            from cdxcore.uniquehash import UniqueHash
            self.unique_hash( unique_hash=UniqueHash(**p) )
                
        we can directly call::
            
            self.unique_hash( **p )            
        
        The purpose of this function is to allow indexing results of heavy computations which were
        configured with ``Config`` with a simple hash key. A typical application is caching of results
        based on the relevant user-configuration.

        An example for a simplistic cache::
            
            from cdxcore.config import Config
            import tempfile as tempfile
            import pickle as pickle

            def big_function( cache_dir : str, config : Config = None, **kwargs ):
                assert not cache_dir[-1] in ["/","\\"], cache_dir
                config = Config.config_kwargs( config, kwargs )
                uid    = config.unique_hash(length=8)
                cfile  = f"{cache_dir}/{uid}.pck"
            
                # attempt to read cache
                try:
                    with open(cfile, "rb") as f:
                        return pickle.load(f)
                except FileNotFoundError:
                    pass
            
                # do something big...
                result = config("a", 0, int, "Value 'a'") * 1000
            
                # write cache
                with open(cfile, "wb") as f:
                    pickle.dump(result,f)
            
                return result                
            
            cache_dir  = tempfile.mkdtemp()   # for real applications, use a permanent cache_dir.
             _ = big_function( cache_dir = cache_dir, a=1 )
            print(_)  

        A more sophisticated framework which includes code versioning via :func:`cdxcore.version.version`
        is implemented with :meth:`cdxcore.subdir.SubDir.cache`.

        **Unique Hash Default Semantics**
        
        Please consult the documentation for :class:`cdxcore.uniquehash.UniqueHash` before using this functionality;
        in particular note that by default this function ignores
        config keys or children with leading underscores; set ``parse_underscore`` to ``"protected"`` or ``"private"`` to change this behaviour.

        **Why is "Usage" not Considered when Computing the Hash (by Default)**

        When using ``Config`` to configure our environment, then we have not only the user's input values
        but also the realized values in the form of defaults for those values the user has not provided.
        In most cases, these are the majority of values.
        
        By only considering actual input values when computing a hash, we stipulate that
        defaults are not part of the current unique characteristic of the environment.
        
        That seems inconsistent: consider a program which reads a parameter ``activation`` with default ``relu``.
        The hash key will be different for the case where the user does not provide a value for ``activation``,
        and the case where its value is set to ``relu`` by the user. The effective ``activation`` value
        in both cases is ``relu`` -- why would we not want this to be identified as the same
        environment configuration.

        The following illustrates this dilemma::

            def big_function( config ):
                _ = config("activation", "relu", str, "Activation function")
                config.done()
            
            config = Config()
            big_function( config )
            print( config.unique_hash(length=8) )   # -> 36e9d246
            
            config = Config(activation="relu")
            big_function( config )
            print( config.unique_hash(length=8) )   # -> d715e29c
        
        *Robustness*
        
        The key driver of using only input values for hashing is the prevalence of reading (child) configs
        close to the use of their parameters. That means that often config parameters are only read
        (and therefore their usage registered) if the respective computation is actually executed:
        even the ``big_function`` example above shows this issue: the call 
        ``config("a", 0, int, "Value 'a'")`` will only be executed if the cache could not be found.
        
        This can be rectified if it is ensured that all config parameters are read regardless of
        actual executed code. In this case, set the parameter ``input_only``
        for ``unique_hash()``
        to ``False``. Note that when using :meth:`cdxcore.config.Config.detach` 
        you must make sure to have processed all detached configurations
        before calling ``unique_hash()``.
        
        Parameters
        ----------
        unique_hash_parameters : dict
        
            If ``unique_hash`` is ``None`` these parameters are passed to
            :meth:`cdxcore.uniquehash.UniqueHash.__call__` to obtain
            the corrsponding hashing function.
            
        unique_hash : Callable

            A function to return unique hashes, usally generated using :class:`cdxcore.uniquehash.UniqueHash`.

        debug_trace : :class:`cdxcore.uniquehash.DebugTrace`
            Allows tracing of hashing activity for debugging purposes.
            Two implementations of ``DebugTrace`` are currently available:
                
            * :class:`cdxcore.uniquehash.DebugTraceVerbose` simply prints out hashing activity to stdout.
            
            * :class:`cdxcore.uniquehash.DebugTraceCollect` collects an array of tracing information.
              The object itself is an iterable which contains the respective tracing information
              once the hash function has returned.
                    
        input_only : bool
            *Expert use only.*
            
            If True (the default) only user-provided inputs are used to compute the unique hash.
            If False, then the result of :meth:`cdxcore.config.Config.usage_value_dict` is used
            to generate the hash. Make sure you read and understand
            the discussion above on the topic.
        

        Returns
        -------
            Unique hash, str
                A unique hash of at most the length specified via either ``unique_hash`` or ``unique_hash_parameters``.
                
        """
        if unique_hash is None:
            unique_hash = UniqueHash( **unique_hash_parameters )
        else:
            if len(unique_hash_parameters) != 0: raise ValueError("Cannot provide 'unique_hash_parameters' if 'unique_hash' is provided")
        
        if not input_only:
            uid = unique_hash( self.usage_value_dict() )
            
        else:
            def rec(config):
                """ Recursive version which returns an empty string for empty sub configs """
                inputs = {}
                for key in config:
                    if key[:1] == "_":
                        continue
                    inputs[key] = config.get_raw(key)
                for c, child in config._children.items():
                    if c[:1] == "_":
                        continue
                    # collect ID for the child
                    child_data = rec(child)
                    # we only register children if they have keys.
                    # this way we do not trigger a change in ID simply due to a failed read access.
                    if child_data != "":
                        inputs[c]  = child_data
                if len(inputs) == 0:
                    return ""
                return unique_hash(inputs,debug_trace=debug_trace)
            uid = rec(self)
        return uid if uid!="" else unique_hash("",debug_trace=debug_trace)

    def used_info(self, key : str) -> tuple:
        """
        Returns the usage stats for a given key in the form of a tuple ``(done, record)``.
        
        Here ``done`` is a boolean and ``record`` is a dictionary of consistency
        information on the key. """
        done   = key in self._done
        record = self._recorder.get( self.record_key(key), None )
        return (done, record)

    def record_key(self, key) -> str:
        """
        Returns the fully qualified string key for ``key``.

        It has the form ``config1.config['entry']``.
        """
        return self._name + "['" + key + "']"    # using a fully qualified keys allows 'recorders' to be shared across copy()'d configs.

    # magic
    # -----

    def __iter__(self):
        """
        Iterator.
        """
        return OrderedDict.__iter__(self)

    # pickling
    # --------
    
    def __reduce__(self):
        """
        Pickling this object explicitly
        See https://docs.python.org/3/library/pickle.html#object.__reduce__
        """
        keys = [ k for k in self ]
        data = [ self.get_raw(k) for k in keys ]
        state = dict(done = self._done,
                     name = self._name,
                     children = self._children,
                     recorder = self._recorder,
                     keys = keys,
                     data = data )
        return (Config, (), state)

    def __setstate__(self, state):
        """ Supports unpickling """
        self._name = state['name']
        self._done = state['done']
        self._children = state['children']
        self._recorder = state['recorder']
        data = state['data']
        keys = state['keys']
        for (k,d) in zip(keys,data):
            self[k] = d
    
    # casting
    # -------

    @staticmethod
    def config_kwargs( config, kwargs : Mapping, config_name : str = "kwargs"):
        """
        Default implementation for a usage pattern where the user can provide both a :class:`cdxcore.config.Config` parameter and ``** kwargs``.
        
        Example::

            def f(config, **kwargs):
                config = Config.config_kwargs( config, kwargs )
                ...
                x = config("x", 1, ...)
                config.done() # <-- important to do this here. Remembert that config_kwargs() calls 'detach'

        and then one can use either of the following::

            f(Config(x=1))
            f(x=1)

        *Important*: ``config_kwargs`` calls :meth:`cdxcore.config.Config.detach` to obtain a copy of ``config``.
        This means :meth:`cdxcore.config.Config.done`
        must be called explicitly for the returned object even if ``done()``
        will be called elsewhere for the source ``config``.
            
        Parameters
        ----------
            config : Config
                A ``Config`` object or ``None``.
                
            kwargs : Mapping
                If ``config`` is provided, the function will call :meth:`cdxcore.config.Config.update` with ``kwargs``.

            config_name : str
                A declarative name for the config if ``config`` is not proivded.
            
        Returns
        -------
            config : Config
                A new config object. Please note that if ``config`` was provided, then this a copy
                obtained from calling :meth:`cdxcore.config.Config.detach`, which means that 
                :meth:`cdxcore.config.Config.done` must be called explicitly for this object to
                ensure no parameters were misspelled (it is not sufficient
                if :meth:`cdxcore.config.Config.done` is called
                for ``config``.)
        """
        assert isinstance( config_name, str ), "'config_name' must be a string"
        if type(config).__name__ == Config.__name__: # we allow for import inconsistencies
            config = config.detach()
            config.update(kwargs)
        else:
            if not config is None: raise TypeError("'config' must be of type 'Config'")
            config = Config.to_config( kwargs=kwargs, config_name=config_name )
        return config

    @staticmethod
    def to_config( kwargs : Mapping, config_name : str = "kwargs"):
        """
        Assess whether a parameters is a :class:`cdxcore.config.Config`, and otherwise tries to convert it into one.
        Classic use case is to transform ``** kwargs`` to a :class:`cdxcore.config.Config` to allow
        type checking and prevent spelling errors.
        
        Returns
        -------
            config : Config
                If ``kwargs`` is already a :class:`cdxcore.config.Config` it is returned. Otherwise,
                create a new :class:`cdxcore.config.Config` from ``kwargs`` named using ``config_name``.
        """
        return kwargs if isinstance(kwargs,Config) else Config( kwargs,config_name=config_name )

    # for uniqueHash
    # --------------

    def __unique_hash__(self, unique_hash : UniqueHash, debug_trace : DebugTrace  ) -> str:
        """
        Returns a unique hash for this object.

        This function is required because by default uniqueHash() ignores members starting with '_', which
        in the case of Config means that no children are hashed.
        """
        return self.unique_hash( unique_hash=unique_hash, debug_trace=debug_trace )

    # Comparison
    # -----------
    
    def __eq__(self, other):
        """ Equality operator comparing 'name' and standard dictionary content """        
        if type(self).__name__ != type(other).__name__:  # allow comparison betweenn different imports
            return False
        if self._name != other._name:
            return False
        return OrderedDict.__eq__(self, other)

    def __ne__(self, other):
        """ Inequality operator comparing 'name' and standard dictionary content """
        return not self.__eq__(other)

    __hash__ = None
        
to_config = Config.to_config
config_kwargs = Config.config_kwargs
Config.no_default = no_default

# ==============================================================================
#
# Exceptions
#
# ==============================================================================

class NotDoneError( RuntimeError ):
    """
    Raised when :meth:`cdxcore.config.Config.done` finds that some config parameters have not been read.
    
    The set of those arguments is accessible via
    :attr:`cdxcore.config.NotDoneError.not_done`.
    """
    def __init__(self, not_done : set[str], config_name : str, message : str) -> None:
        #: The parameter keys which were not read when :meth:`cdxcore.config.Config.done` was called.
        self.not_done = not_done
        #: Hierarchical name of the config.
        self.config_name = config_name
        RuntimeError.__init__(self, message)

class InconsistencyError( RuntimeError ):
    """
    Raised when :meth:`cdxcore.config.Config.__call__`
    used inconsistently between function calls for a given parameter.
    
    The ``Config`` semantics require that parameters are accessed used with consistent
    `default` and `help` values between :meth:`cdxcore.config.Config.__call__` calls.

    For *raw* access to any parameters, use ``[]``.
    """
    def __init__(self, key : str, config_name : str, message : str) -> None:
        #: The offending parameter key.
        self.key = key
        #: Hierarchical name of the config.
        self.config_name = config_name
        RuntimeError.__init__(self, message)
        
class CastError( RuntimeError ):
    """
    Raised when :meth:`cdxcore.config.Config.__call__` could not cast a
    value provided by the user to the specified type.

    Parameters
    ----------
        key : str
            Key name of the parameter which failed to cast.
        config_name : str
            Name of the ``Config``.
            
        exception : :class:`Exception`
            Orginal exception raised by the cast.
    """
    def __init__(self, key : str, config_name : str, exception : Exception) -> None:
        """
        :meta private:
        """        
        #: Key of the parameter which failed to cast.
        self.key         = key
        #: Hierarchical name of the config.
        self.config_name = config_name
        header = f"Error in cast definition for key '{key}' in config '{config_name}': " if len(config_name) > 0 else f"Error in cast definition for key '{key}': "
        RuntimeError.__init__(self, header+str(exception))


# ==============================================================================
# New in version 0.1.45
# Support for conditional types, e.g. we can write
#
#  x = config(x, 0.1, Float >= 0., "An 'x' which cannot be negative")
# ==============================================================================

class _Cast(object):
    
    def __call__( self, value, *, config_name : str, key_name : str ):
        """ cast 'value' to the proper type """
        raise NotImplementedError("Internal error")

    def __str__(self) -> str:
        """ Returns readable string description of 'self' """
        raise NotImplementedError("Internal error")

def _cast_name( cast : type ) -> str:
    """ Returns the class name of 'cast' """
    if cast is None:
        return ""
    return getattr(cast,"__name__", str(cast))

def _cast_err_header(*, config_name : str, key_name : str):
    if len(config_name) > 0:
        return f"Error using config '{config_name}' for key '{key_name}': "
    else:
        return f"Config error for key '{key_name}': "

# ================================
# Simple wrapper
# ================================

class _Simple(_Cast):# NOQA
    """
    Default case where the 'cast' argument for a config call() is simply a type, a Callable, or None.
    Cast to an actual underlying type.
    """

    STR_NONE_CAST = "any"

    def __init__(self, *, cast : type, config_name : str, key_name : str, none_is_any : bool ) -> None:
        """ Simple atomic caster """
        if not cast is None:
            if isinstance(cast, str):
                raise ValueError(_cast_err_header(config_name=config_name,key_name=key_name)+\
                                 "'cast' must be a type. Found a string. Most likely this happened because a help string was defined as positional argument, but no 'cast' type was specified. "+\
                                 "In this case, use 'help=' to specify the help text.")
            assert not isinstance(cast, _Cast), lambda : "Internal error in definition for key '%s' in config '%s': 'cast' should not be derived from _Cast. Object is %s" % ( key_name, config_name, str(cast) )
        self.cast        = cast
        self.none_is_any = none_is_any
        assert not none_is_any is None or not cast is None, "Must set 'none_is_any' to bool value if cast is 'None'."

    def __call__(self, value, *, config_name : str, key_name : str ):
        """ Cast 'value' to the proper type """
        if self.cast is None:
            if value is None or self.none_is_any:
                return value
            if not value is None:
                raise ValueError(f"'None' value expected, found value of type {type(value).__name__}")
        return self.cast(value)

    def __str__(self) -> str:
        """ Returns readable string """
        if self.cast is None:
            return self.STR_NONE_CAST if self.none_is_any else "None"
        return _cast_name(self.cast)

# ================================
# Conditional types such as Int>0
# ================================

class _Condition(_Cast):
    """ Represents a simple operator condition such as 'Float >= 0.' """

    def __init__(self, cast, op, other) -> None:
        """ Initialize the condition for a base type 'cast' and an 'op' with an 'other'  """
        self.cast    = cast
        self.op      = op
        self.other   = other
        self.l_and   = None

    def __and__(self, cond):
        """
        Combines to conditions with logical AND .
        Requires the left hand 'self' to be a > or >=; the right hand must be < or <=
        This means you can write

            x = config("x", 0.5, (Float >= 0.) & (Float < 1.), "Variable x")

        """
        if not self.l_and is None:
            raise NotImplementedError("Cannot combine more than two conditions")
        if not self.op[0] == 'g':
            raise NotImplementedError("The left hand condition when using '&' must be > or >=. Found %s" % self._op_str)
        if not cond.op[0] == 'l':
            raise NotImplementedError("The right hand condition when using '&' must be < or <=. Found %s" % cond._op_str)
        if self.cast != cond.cast:
            raise NotImplementedError("Cannot '&' conditions for types %s and %s" % (self.cast.__name__, cond.cast.__name__))
        op_new = _Condition(self.cast, self.op, self.other)
        op_new.l_and = cond
        return op_new

    def __call__(self, value, *, config_name : str, key_name : str ):
        """ Test whether 'value' satisfies the condition """
        value = self.cast(value)

        if self.op == "ge":
            ok = value >= self.other
        elif self.op == "gt":
            ok = value > self.other
        elif self.op == "le":
            ok = value <= self.other
        elif self.op == "lt":
            ok = value < self.other
        else:
            raise RuntimeError("Internal error: unknown operator %s" % str(self.op))
        if not ok:
            raise ValueError( f"value for key '{key_name}' {self.err_str}: found {str(value)[:100]}" )
        return self.l_and( value, config_name=config_name, key_name=key_name) if not self.l_and is None else value

    def __str__(self) -> str:
        """ Returns readable string """
        s = _cast_name(self.cast) + self._op_str + str(self.other)
        if not self.l_and is None:
            s += " and " + str(self.l_and)
        return s

    @property
    def _op_str(self) -> str:
        """ Returns a string for the operator of this conditon """
        if self.op == "ge":
            return ">="
        elif self.op == "gt":
            return ">"
        elif self.op == "le":
            return "<="
        elif self.op == "lt":
            return "<"
        raise RuntimeError("Internal error: unknown operator %s" % str(self.op))

    @property
    def err_str(self) -> str:
        """ Nice error string """
        zero = self.cast(0)
        def mk_txt(cond):
            if cond.op == "ge":
                s = ("not be lower than %s" % cond.other) if cond.other != zero else ("not be negative")
            elif cond.op == "gt":
                s = ("be bigger than %s" % cond.other) if cond.other != zero else ("be positive")
            elif cond.op == "le":
                s = ("not exceed %s" % cond.other) if cond.other != zero else ("not be positive")
            elif cond.op == "lt":
                s = ("be lower than %s" % cond.other) if cond.other != zero else ("be negative")
            else:
                raise RuntimeError("Internal error: unknown operator %s" % str(cond.op))
            return s

        s    = "must " + mk_txt(self)
        if not self.l_and is None:
            s += ", and " + mk_txt(self.l_and)
        return s

class _CastCond(_Cast): # NOQA
    """
    Generates compound _Condition's
    See the two members Float and Int
    """

    def __init__(self, cast) -> None:# NOQA
        self.cast = cast
    def __ge__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'ge', self.cast(other) )
    def __gt__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'gt', self.cast(other) )
    def __le__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'le', self.cast(other) )
    def __lt__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'lt', self.cast(other) )
    def __call__(self, value, *, config_name : str, key_name : str ):
        """ This gets called if the type was used without operators """
        cast = _Simple(cast=self.cast, config_name=config_name, key_name=key_name, none_is_any=None )
        return cast( value, config_name=config_name, key_name=key_name )
    def __str__(self) -> str:
        """ This gets called if the type was used without operators """
        return _cast_name(self.cast)

Float = _CastCond(float)
"""
Allows to apply basic range conditions to ``float`` parameters.

For example::

    timeout = config("timeout", 0.5, Float>=0., "Timeout")

In combination with ``&`` we can limit a float to a range::

    probability = config("probability", 0.5, (Float>=0.) & (Float <= 1.), "Probability")
"""


Int   = _CastCond(int)
"""
Allows to apply basic range conditions to ``int`` parameters.

For example::

    num_steps = config("num_steps", 1, Int>0., "Number of steps")

In combination with ``&`` we can limit an int to a range:

    bus_days_per_year = config("bus_days_per_year", 255, (Int > 0) & (Int < 365), "Business days per year")

"""

# ================================
# Enum type for list 'cast's
# ================================

class _Enum(_Cast):
    """
    Utility class to support enumerator types.
    No need to use this classs directly. It will be automatically instantiated if a list is passed as type, e.g.

        code = config("code", "Python", ['C++', 'Python'], "Which language do we love")

    Note that all list members must be of the same type.
    """

    def __init__(self, enum : list, *, config_name : str, key_name : str ) -> None:
        """ Initializes an enumerator casting type. """
        self.enum = list(enum)
        if len(self.enum) == 0:
            raise ValueError(_cast_err_header(config_name=config_name,key_name=key_name) +\
                             f"'cast' for key '{key_name}' is an empty list. Lists are used for enumerator types, hence passing empty list is not defined")
        if self.enum[0] is None:
            raise ValueError(_cast_err_header(config_name=config_name,key_name=key_name) +\
                             f"'cast' for key '{key_name}' is an list, with first element 'None'. Lists are used for enumerator types, and the first element defines their underlying type. Hence you cannot use 'None'. (Did you want to use alternative notation with tuples?)")
        self.cast = _Simple( cast=type(self.enum[0]), config_name=config_name, key_name=key_name, none_is_any=None )
        for i in range(1,len(self.enum)):
            try:
                self.enum[i] = self.cast( self.enum[i], config_name=config_name, key_name=key_name )
            except:
                other_name = _cast_name(type(self.enum[i]))
                raise ValueError( _cast_err_header(config_name=config_name,key_name=key_name) +\
                                  f"'cast' for key {key_name}: members of the 'cast' list are not of consistent type. Found {self.cast} for the first element which does match the type {other_name} of the {i}th element" )

    def __call__( self, value, *, config_name, key_name ):
        """
        Cast 'value' to the proper type and check is one of the list members
        Raises a KeyError if the value was not found in our enum
        """
        value = self.cast(value, config_name=config_name, key_name=key_name)
        if not value in self.enum:
            raise ValueError( f"Value for key '{key_name}' {self.err_str}; found '{str(value)[:100]}'" )
        return value

    @property
    def err_str(self) -> str:
        """ Nice error string """
        if len(self.enum) == 1:
            return f"must be '{str(self.enum[0])}'"
        
        s = "must be one of: '" + str(self.enum[0]) + "'"
        for i in range(1,len(self.enum)-1):
            s += ", '" + str(self.enum[i]) + "'"
        s += " or '" + str(self.enum[-1]) + "'"
        return s

    def __str__(self) -> str:
        """ Returns readable string """
        s     = "[ "
        for i in range(len(self.enum)):
            s += ( ", " + self.enum[i] ) if i > 0 else self.enum[i]
        s += " ]"
        return s

# ================================
# Multiple types
# ================================

class _Alt(_Cast):
    """
    Initialize a casting compund "alternative" type, e.g. it the variable may contain several types, each of which is acceptable.
    None here means that 'None' is an accepted value.
    This is invokved when a tuple is passed, e.g

        config("spread", None, ( None, float ), "Float or None")
        config("spread", 1, ( Int<=-1, Int>=1. ), "A variable which has to be outside (-1,+1)")
    """

    def __init__(self, casts : list, *, config_name : str, key_name : str ) -> None:
        """ Initialize a compound cast """
        if len(casts) == 0:
            raise ValueError(_cast_err_header(config_name=config_name,key_name=key_name) +\
                             f"'cast' for key '{key_name}' is an empty tuple. Tuples are used for alternative types, hence passing empty tuple is not defined")
#        print("casts####",casts)
#        if casts==(0,0):
#            raise RuntimeError()
        self.casts = [ _create_caster(cast=cast, config_name=config_name, key_name=key_name, none_is_any=False) for cast in casts ]

    def __call__( self, value, *, config_name : str, key_name : str ):
        """ Cast 'value' to the proper type """
        e0   = None
        for cast in self.casts:
            # None means that value == None is acceptable
            try:
                return cast(value, config_name=config_name, key_name=key_name )
            except Exception as e:
                e0 = e if e0 is None else e0
        raise ValueError(f"Error using config '{config_name}': value for key '{key_name}' {self.err_str}. Found '{str(value)}' of type '{type(value).__name__}'")

    def test(self, value):
        """ Test whether 'value' satisfies the condition """
        raise self.test

    @property
    def err_str(self):
        """ Returns readable string """
        return "must be one of the following types: " + self.__str__()

    def __str__(self):
        """ Returns readable string """
        s = ""
        for cast in self.casts[:-1]:
            s += str(cast) + " or "
        s += str(self.casts[-1])
        return s

# ================================
# Manage casting
# ================================

def _create_caster( *, cast : type, config_name : str, key_name : str, none_is_any : bool ):
    """
    Implements casting.

    Parameters
    ----------
        value: value, either from the user or the default value if provided
        cast : cast input to call() from the user, or None.
        key_name : name of the config
        key  : name of the key being access
        none_is_any :If True, then None means that any type is accepted. If False, the None means that only None is accepted.

    Returns
    -------
        value : casted value
        __str__ : casting help text. Empty if 'cast' is None
    """
    if isinstance( cast, str ):
        raise ValueError(_cast_err_header(config_name=config_name,key_name=key_name) +\
                         f"string '{cast}' provided as 'cast'. Strings are not supported. To pass sets of characters, use a list of strings of those single characters.")
    if isinstance(cast, list):
        #print("--- create_caster enun", cast)
        return _Enum( enum=cast, config_name=config_name, key_name=key_name )
    elif isinstance(cast, tuple):
        #print("--- create_caster alt", cast)
        return _Alt( casts=cast, config_name=config_name, key_name=key_name )
    elif isinstance(cast,_Cast):
        #print("--- create_caster-cash", cast)
        return cast
    #print("--- create_caster simple", cast)
    return _Simple( cast=cast, config_name=config_name, key_name=key_name, none_is_any=none_is_any )

