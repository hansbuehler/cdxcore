def import_local():
    """
    In order to be able to run our tests manually from the 'tests' directory
    we force import from the local package.
    """
    me = "cdxcore"
    import os
    import sys
    cwd = os.getcwd()
    if cwd[-len(me):] == me:
        print("import_local: current working directory does not contain",me,":", cwd)
        return
    assert cwd[-5:] == "tests",("Expected current working directory to be in a 'tests' directory", cwd[-5:], "from", cwd)
    assert cwd[-6] in ['/', '\\'],("Expected current working directory 'tests' to be lead by a '\\' or '/'", cwd[-6:], "from", cwd)
    if sys.path[0] != cwd[:-6]:
        sys.path.insert( 0, cwd[:-6] )
        print("import_local: added import directory:", cwd[:-6])
    else:
        print("import_local: import directory already present:", cwd[:-6])
        
# -*- coding: utf-8 -*-

