from . import preferences_ontology
#------------------------------------------------------------
# ONTO3D
#------------------------------------------------------------

# ---- Onto3D: window-safe helpers to avoid _RestrictContext -----
def __onto3d_iter_areas(type_set={'NODE_EDITOR','VIEW_3D'}):
    try:
        import bpy
        wm = getattr(bpy.context, "window_manager", None)
        if not wm:
            return
        for w in wm.windows:
            scr = getattr(w, "screen", None)
            if not scr:
                continue
            for a in getattr(scr, "areas", []):
                if a.type in type_set:
                    yield w, scr, a
    except Exception:
        return

def __onto3d_tag_node_editors():
    try:
        import bpy
        for _w, _s, a in __onto3d_iter_areas({'NODE_EDITOR'}):
            a.tag_redraw()
    except Exception:
        pass

bl_info = {
    "name": "Onto3D",
    "author": "Giacomo Mancuso & ChatGPT",
    "version": (0, 6, 0),
    "blender": (4, 5, 2),
    "location": "Node Editor > N-Panel (Onto3D)",
    "description": "Manage and create an ontological graph in Blender's node editor and connect it to geometry data. Import/Export RDF/TTL for Protégé integration.",
    "category": "Node",
}

# ------------------------------------------------------------
# Onto3D – Graph nodes with RDF importer + presets
# ------------------------------------------------------------
import bpy
from bpy.types import NodeTree, Node, NodeSocket
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories
import os, json, ast
from collections import defaultdict
import uuid
from importlib import import_module

# Import all modules
from . import nodes
from . import ui_panels
from . import preferences_ontology
from . import rdf_utils
from . import graph_layout
from . import rdf_export
from . import rdf_import
from . import ui_import_export


def register():
    """Register all Onto3D modules"""
    from . import nodes, ui_panels, preferences_ontology
    from . import rdf_export, rdf_import, ui_import_export
    
    if hasattr(nodes, 'register'): 
        nodes.register()
    if hasattr(ui_panels, 'register'): 
        ui_panels.register()
    if hasattr(preferences_ontology, 'register'): 
        preferences_ontology.register()
    if hasattr(rdf_export, 'register'): 
        rdf_export.register()
    if hasattr(rdf_import, 'register'): 
        rdf_import.register()
    if hasattr(ui_import_export, 'register'): 
        ui_import_export.register()


def unregister():
    """Unregister all Onto3D modules in reverse order"""
    # Import modules with error handling
    try:
        from . import preferences_ontology
    except Exception:
        preferences_ontology = None
    try:
        from . import ui_panels
    except Exception:
        ui_panels = None
    try:
        from . import nodes
    except Exception:
        nodes = None
    try:
        from . import ui_import_export
    except Exception:
        ui_import_export = None
    try:
        from . import rdf_import
    except Exception:
        rdf_import = None
    try:
        from . import rdf_export
    except Exception:
        rdf_export = None

    # Unregister in reverse order
    if preferences_ontology is not None and hasattr(preferences_ontology, "unregister"):
        try:
            preferences_ontology.unregister()
        except Exception:
            pass

    if ui_panels is not None and hasattr(ui_panels, "unregister"):
        try:
            ui_panels.unregister()
        except Exception:
            pass

    if nodes is not None and hasattr(nodes, "unregister"):
        try:
            nodes.unregister()
        except Exception:
            pass
    
    if ui_import_export is not None and hasattr(ui_import_export, "unregister"):
        try:
            ui_import_export.unregister()
        except Exception:
            pass
    
    if rdf_import is not None and hasattr(rdf_import, "unregister"):
        try:
            rdf_import.unregister()
        except Exception:
            pass
    
    if rdf_export is not None and hasattr(rdf_export, "unregister"):
        try:
            rdf_export.unregister()
        except Exception:
            pass


# ---- Onto3D: attach safe poll at runtime (avoids panel access during restricted context) ----
def __onto3d_attach_safe_polls():
    try:
        import bpy, builtins
        g = globals()
        targets = [k for k,v in g.items() if isinstance(v, type) and getattr(v, "__mro__", None) and "bpy_types.Panel" in str(v.__mro__)]
        def _poll(cls, context):
            return getattr(context, "area", None) and context.area.type in {'NODE_EDITOR','VIEW_3D'}
        for name in targets:
            cls = g.get(name)
            if cls and not hasattr(cls, "poll"):
                cls.poll = classmethod(_poll)
    except Exception:
        pass
    return None

try:
    import bpy
    bpy.app.timers.register(__onto3d_attach_safe_polls, first_interval=0.2)
except Exception:
    pass


if __name__ == "__main__":
    register()