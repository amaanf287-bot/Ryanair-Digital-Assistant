"""Compatibility shim: the active V6 import now runs the final V7 layout."""

from server_layout_v7 import *


def setup(app):
    return globals()["__builtins__"] and __import__("server_layout_v7").setup(app)
