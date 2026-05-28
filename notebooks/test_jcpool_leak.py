import importlib as imp
import packages.cdxcore.cdxcore as _
imp.reload(_)

from cdxcore.jcpool import JCPool

data = []

def allocate_lots( mem : int, t : float ):
    """
    Allocates a lot of memory in the current process. This is used to prevent memory fragmentation and to ensure that there is enough contiguous memory available for the shared arrays.
    """
    import numpy as np
    import time as time

    allocate_lots.data.append( np.zeros( mem, dtype=np.uint8 ) )
    time.sleep(t)
    return mem, len(allocate_lots.data)
allocate_lots.data = []

def out_of_memory():

    jcpool = JCPool(num_workers=2, threading=False, mem_leak_max_memory=10_000_000 )

    tests = [ 
                ( 100, 2 ),
                ( 100, 2 ),
                ( 20_000_000_000, 2 ),
                ( 20_000_000_000, 2 ),
                ( 100_000_000_000, 2 ),
                ( 100_000_000_000, 2 )
    ]

    for r, ld in jcpool.parallel( jcpool.delayed(allocate_lots)( mem=test[0], t=test[1] ) for test in tests ):
        print("**", r,ld)

out_of_memory()

