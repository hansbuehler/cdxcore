"""
## Overview

A very simple implementation of a tool that tracks the last printed line before a newline was encountered.
Helps with somewhat consistent progress reporting with '\r' and '\n' characters.

**Beta Version**

Used by [Context][cdxcore.verbose.Context]

## Import
```
from cdxcore.crman import CRman
```
"""

from collections.abc import Callable

class CRMan(object):
    r"""
    Carraige Return ('\r') manager.    
    This class is meant to enable efficient per-line updates using '\r' for text output with a focus on making it work with both Jupyter and the command shell.
    In particular, Jupyter does not support the ANSI \33[2K 'clear line' code.
                                                         
    **Beta version**
    
    ```
    crman = CRMan()
    print( crman("\rmessage 111111"), end='' )
    print( crman("\rmessage 2222"), end='' )
    print( crman("\rmessage 33"), end='' )
    print( crman("\rmessage 1\n"), end='' )
    
    --> message 1     
    
    print( crman("\rmessage 111111"), end='' )
    print( crman("\rmessage 2222"), end='' )
    print( crman("\rmessage 33"), end='' )
    print( crman("\rmessage 1"), end='' )
    print( crman("... and more"), end='' )
    
    --> message 1... and more
    ```
    """
    
    def __init__(self):
        """ See [CRMan][cdxcore.crman.CRMan] """
        self._current = ""
        
    def __call__(self, message : str) -> str:
        r"""
        Convert `message` containing '\r' and '\n' into a printable string which ensures that a '\r' string does not lead to printed artifacts.
        Afterwards, the object will retain any text not terminated by '\n'.
        
        The itention of this function is to be part of the printing operation
        
        Parameters
        ----------
        message : str
            message containing '\r' and '\n'.
            
        Returns
        -------
        Message: str
            Printable string.
        """
        if message is None:
            return

        lines  = message.split('\n')
        output = ""
        
        # first line
        line   = lines[0]
        icr    = line.rfind('\r')
        if icr == -1:
            line = self._current + line
        else:
            line = line[icr+1:]
        if len(self._current) > 0:
            output    += '\r' + ' '*len(self._current) + '\r' + '\33[2K' + '\r'
        output        += line
        self._current = line
            
        if len(lines) > 1:
            output       += '\n'
            self._current = ""
            
            # intermediate lines
            for line in lines[1:-1]:
                # support multiple '\r', but in practise only the last one will be printed
                icr    =  line.rfind('\r')
                line   =  line if icr==-1 else line[icr+1:]
                output += line + '\n'
                
            # final line
            line      = lines[-1]
            if len(line) > 0:
                icr           = line.rfind('\r')
                line          = line if icr==-1 else line[icr+1:]
                output        += line
                self._current += line
        
        return output
            
    def reset(self):
        """ Reset object """
        self._current = ""
        
    @property
    def current(self) -> str:
        """ Return current string """
        return self._current
        
    def write(self, text : str, end : str = '', flush : bool = True, channel : Callable = None ):
        r"""
        Write to `channel` taking into account current status and any '\r' and '\n' in `text`.
        The `end` and `flush` parameters mirror those of [print](https://docs.python.org/3/library/functions.html#print)().
                                                                 
        Parameters
        ----------
        text: str
            Text to print, containing '\r' and '\n'.
        channel: Callable
            Callable to output the residual text. If None, the default, [print](https://docs.python.org/3/library/functions.html#print)() to stdout.
        end, flush:
            `end` and `flush` parameters mirror those of [print](https://docs.python.org/3/library/functions.html#print)()
            if `channel` is None.
        """
        text = self(text+end)
        if channel is None:
            print( text, end='', flush=flush )
        else:
            channel( text, flush=flush )
        return self
