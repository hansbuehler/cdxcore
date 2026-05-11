# -*- coding: utf-8 -*-
"""
Created on June 2022
@author: hansb
"""
from __future__ import annotations

__version__ = "0.1.82"  # auto-updated by setup.py

__all__ = [
    "__version__",
    "Config",
    "Int",
    "Float",
    "SubDir",
    "CacheMode",
    "CacheController",
    "VersionedCacheRoot",
    "UniqueHash",
    "NamedUniqueHash",
    "UniqueLabel",
    "unique_hash8",
    "unique_hash16",
    "unique_hash32",
    "unique_hash48",
    "unique_hash64",
    "Context",
    "Timer",
    "JCPool",
    "PrettyObject",
    "PrettyValueObject",
    "PrettyHierarchy",
    "version",
]

_EXPORTS = {
    "Config": ("cdxcore.config", "Config"),
    "Int": ("cdxcore.config", "Int"),
    "Float": ("cdxcore.config", "Float"),
    "SubDir": ("cdxcore.subdir", "SubDir"),
    "CacheMode": ("cdxcore.subdir", "CacheMode"),
    "CacheController": ("cdxcore.subdir", "CacheController"),
    "VersionedCacheRoot": ("cdxcore.subdir", "VersionedCacheRoot"),
    "UniqueHash": ("cdxcore.uniquehash", "UniqueHash"),
    "NamedUniqueHash": ("cdxcore.uniquehash", "NamedUniqueHash"),
    "UniqueLabel": ("cdxcore.uniquehash", "UniqueLabel"),
    "unique_hash8": ("cdxcore.uniquehash", "unique_hash8"),
    "unique_hash16": ("cdxcore.uniquehash", "unique_hash16"),
    "unique_hash32": ("cdxcore.uniquehash", "unique_hash32"),
    "unique_hash48": ("cdxcore.uniquehash", "unique_hash48"),
    "unique_hash64": ("cdxcore.uniquehash", "unique_hash64"),
    "Context": ("cdxcore.verbose", "Context"),
    "Timer": ("cdxcore.util", "Timer"),
    "JCPool": ("cdxcore.jcpool", "JCPool"),
    "PrettyObject": ("cdxcore.pretty", "PrettyObject"),
    "PrettyValueObject": ("cdxcore.pretty", "PrettyValueObject"),
    "PrettyHierarchy": ("cdxcore.pretty", "PrettyHierarchy"),
    "version": ("cdxcore.version", "version"),
}

def __getattr__(name):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'cdxcore' has no attribute '{name}'") from exc
    from importlib import import_module
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
