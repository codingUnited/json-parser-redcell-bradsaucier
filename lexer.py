"""
lexer.py - Compatibility shim that exposes both lex() and parse().

//viper1//
"""

from importlib import import_module
import sys

# Pull in the core JSON engine
_json = import_module("json_parser")

# Public API expected by earlier steps
lex = _json.lex

# New export for Step 5
parse = _json.parse  # <- added

__all__ = ["lex", "parse"]

# Keep the legacy alias so `from parser import parse` works
sys.modules.setdefault("parser", sys.modules[__name__])
