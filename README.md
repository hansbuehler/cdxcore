# cdxcore documentation

This module contains a number of lightweight tools, developed for managing data analytics and machine learning projects.

Install using:

```bash
pip install -U cdxcore
```

Documentation can be found here: <https://quantitative-research.de/docs/cdxcore>.

## Highlights

- **Dynamic plotting**: simple live/animated plots built on Matplotlib.
- **Config management**: validated, discoverable configurations with automatic help.
- **Versioning & caching**: code-versioned I/O and reproducible hashing for pipelines.
- **PrettyObject**: dictionary-like objects that allow attribute access.
- **Utilities**: formatting helpers, binary I/O, shared-memory arrays, and more.

## Main Functionality

- [`cdxcore.dynaplot`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.dynaplot.html) is a framework for
  simple **dynamic graphs** with `matplotlib`. It has a simple methodology for
  animated updates for graphs (e.g. during training runs), and allows generation of plot layouts without knowing upfront
  the number of plots (e.g. for plotting a list of features).

  ![Aninmated 3D plot](https://quantitative-research.de/docs/cdxcore/_static/dynaplot3D.gif)
  
- [`cdxcore.config`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.config.html) allows **robust management of configurations**. It automates help, validation checking,
  and detects misspelled configuration arguments.

  ```python
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
  ```

- [`cdxcore.subdir`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.subdir.html) wraps various file and directory functions into convenient objects. Useful if files have
  common extensions.

  ```python
  from cdxcore.subdir import SubDir
  import numpy as np
  root   = SubDir("!")   # current temp directory
  subdir = root("test")  # sub-directory 'test'
  subdir.write("data", np.zeros((10,2)))
  data   = subdir.read("data")
  ```

-  **Caching:** ``SubDir`` supports code-versioned file i/o which is used by [`@cdxcore.subdir.SubDir.cache`](file:///C:/Users/hans/OneDrive/Python3/packages/cdxcore/docs/build/html/api/generated/cdxcore.subdir.html#cdxcore.subdir.SubDir.cache)
  for an efficient code-versioned caching protocol for functions and objects:

  ```python
  from cdxcore.subdir import SubDir
  cache   = SubDir("!/.cache;*.bin")

  @cache.cache("0.1")
  def f(x,y):
     return x*y

  _ = f(1,2)    # function gets computed and the result cached
  _ = f(1,2)    # restore result from cache
  _ = f(2,2)    # different parameters: compute and store result
  ```

- **Code versioning** is implemented in [`cdxcore.version`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.version.html):

  ```python
  from cdxbasics.version import version

  @version("0.0.1")
  def f(x):
      return x

  print( f.version.full )   # -> 0.0.1
  ```

- **Hashing** (which is used for caching above) is implemented in [`cdxcore.uniquehash`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.uniquehash.html):

  ```python
  class A(object):
      def __init__(self, x):
          self.x = x
          self._y = x*2  # protected member will not be hashed by default

  from cdxcore.uniquehash import UniqueHash
  uniqueHash = UniqueHash(length=12)
  a = A(2)
  print( uniqueHash(a) ) # --> "2d1dc3767730"
  ```

- [`cdxcore.pretty`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.pretty.html) provides a ``PrettyObject`` class whose objects operate like dictionaries.
  This is for users who prefer attribute ``.`` notation over item access when building structured output.

  ```python
  from cdxbasics.prettydict import PrettyObject
  pdct = PrettyObject(z=1)

  pdct.num_samples = 1000
  pdct.num_batches = 100
  pdct.method = "signature"
  ```

## General purpose utilities

- [`cdxcore.verbose`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.verbose.html) provides user-controllable context output for providing progress updates to users.

- [`cdxcore.util`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.util.html) offers a number of utility functions such as standard formatting for dates, big numbers, lists,
  dictionaries etc.

- [`cdxcore.npio`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.npio.html) provides a low level binary i/o interface for numpy files.

- [`cdxcore.npshm`](https://quantitative-research.de/docs/cdxcore/api/generated/cdxcore.npshm.html) provides shared memory numpy arrays.
