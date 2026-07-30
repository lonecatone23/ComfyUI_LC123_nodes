"""Deprecated shim — use anima_regional_canvas / krea2_regional_canvas."""
from .anima_regional_canvas import NODE_CLASS_MAPPINGS as _A
from .krea2_regional_canvas import NODE_CLASS_MAPPINGS as _K
from .anima_regional_canvas import NODE_DISPLAY_NAME_MAPPINGS as _AD
from .krea2_regional_canvas import NODE_DISPLAY_NAME_MAPPINGS as _KD

NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(_A)
NODE_CLASS_MAPPINGS.update(_K)
NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(_AD)
NODE_DISPLAY_NAME_MAPPINGS.update(_KD)
