.. cdxcore documentation master file, created by
   sphinx-quickstart on Wed Sep  3 19:53:25 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

cdxcore documentation
=====================

This module contains a number of lightweight tools, developped for managing data analytica and machine learning projects.

Install using::

    pip install -U cdxcore

Documentation can be found here: `https://quantitative-research.de/docs/cdxcore <https://quantitative-research.de/docs/cdxcore>`__.

Contents
^^^^^^^^

.. toctree::
   :maxdepth: 2

   api/index

Main Functionality
^^^^^^^^^^^^^^^^^^

* :mod:`cdxcore.dynaplot` is a framework for simple **dynamic graphs** with :mod:`matplotlib`. It has a simple methodology for 
  animated updates for graphs (e.g. during training runs), and allows generation of plot layouts without knowinng upfront
  the number of plots (e.g. for plotting a list of features).

  .. image:: /_static/dynaplot3D.gif

* :mod:`cdxcore.config` allows **robust management of configurations**. It automates help, validation checking,
  and detects misspelled configuration arguments

  .. code-block:: python

    from cdxcore.config import Config, Int, Float
    class Network(object):
        def __init__( self, config ):
            self.depth      = config("depth", 1, Int>0, "Depth of the network")
            self.width      = config("width", 1, Int>0, "Width of the network")
            self.activation = config("activation", "selu", str, "Activation function")
            config.done() # see below
    
    config = Config()
    config.network.depth         = 10
    config.network.width         = 100
    config.network.activation    = 'relu'

    network = Network(config.network)
    config.done()

* :mod:`cdxcore.subdir` wraps various file and directory functions into convenient objects. Useful if files have
  common extensions. 

  .. code-block:: python

    from cdxcore.subdir import SubDir
    import numpy as np
    root   = SubDir("!")   # current temp directory
    subdir = root("test")  # sub-directory 'test'
    subdir.write("data", np.zeros((10,2)))
    data   = subdir.read("data")
  
  **Caching:** ``SubDir`` supports code-versioned file i/o which is used by :dec:`cdxcore.subdir.SubDir.cache`
  for an efficient code-versioned caching protocol for functions and objects:

  .. code-block:: python

    from cdxcore.subdir import SubDir
    cache   = SubDir("!/.cache;*.bin")
      
    @cache.cache("0.1")
    def f(x,y):
       return x*y
      
    _ = f(1,2)    # function gets computed and the result cached
    _ = f(1,2)    # restore result from cache
    _ = f(2,2)    # different parameters: compute and store result


* **Code versioning** is implemented in :mod:`cdxcore.version`.

  .. code-block:: python

    from cdxbasics.version import version

    @version("0.0.1")
    def f(x):
        return x

    print( f.version.full )   # -> 0.0.1

* **Hashing** (which is used for caching above) is implemented in :mod:`cdxcore.uniquehash`:

  .. code-block:: python

    class A(object):
        def __init__(self, x):
            self.x = x
            self._y = x*2  # protected member will not be hashed by default
    
    from cdxcore.uniquehash import UniqueHash
    uniqueHash = UniqueHash(length=12)
    a = A(2)
    print( uniqueHash(a) ) # --> "2d1dc3767730"

* :mod:`cdxcore.pretty` provides a ``PrettyObject`` class whose objects operate like dictionaries. 
  This is for users who prefer attribute ``.`` notation over item access when building structured output.

  .. code-block:: python

    from cdxbasics.prettydict import PrettyObject
    pdct = PrettyObject(z=1)
    
    pdct.num_samples = 1000
    pdct.num_batches = 100
    pdct.method = "signature"

General purpose utilities
^^^^^^^^^^^^^^^^^^^^^^^^^

* :mod:`cdxcore.verbose` provides user-controllable context output for providing progress updates to users.

* :mod:`cdxcore.util` offers a number of utility functions such as standard formatting for dates, big numbers, lists,
  dictionaries etc.

* :mod:`cdxcore.npio` provides a low level binary i/o interface for numpy files.

* :mod:`cdxcore.npshm` provides shared memory numpy arrays.



