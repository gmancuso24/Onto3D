import bpy
import json
from bpy.types import NodeTree, Node, NodeSocket
from bpy.props import StringProperty

# ------------------------------------------------------------
# NodeTree
# ------------------------------------------------------------
class Onto3DNodeTree(NodeTree):
    bl_idname = "Onto3DNodeTree"
    bl_label = "Onto3D Graph"
    bl_icon = "NODETREE"


# ------------------------------------------------------------
# Sockets
# ------------------------------------------------------------
class Onto3DSocketProperty(NodeSocket):
    bl_idname = "Onto3DSocketProperty"
    bl_label = "Property link"

    def draw(self, context, layout, node, text):
        layout.label(text=text or "link")

    def draw_color(self, context, node):
        return (0.55, 0.55, 0.55, 1.0)


class Onto3DSocketEntity(NodeSocket):
    """Kept for compatibility if some menus reference it."""
    bl_idname = "Onto3DSocketEntity"
    bl_label = "Entity"

    def draw(self, context, layout, node, text):
        layout.label(text=text or "Entity")

    def draw_color(self, context, node):
        return (0.25, 0.6, 0.9, 1.0)


# ------------------------------------------------------------
# Entity Node
# ------------------------------------------------------------
class Onto3DNodeEntity(Node):
    bl_idname = "Onto3DNodeEntity"
    bl_label = "Entity"
    bl_icon = "OUTLINER_OB_EMPTY"

    # Metadata / IDs
    onto3d_ontology: StringProperty(name="Ontology", default="")
    onto3d_entity_id: StringProperty(name="Entity ID", default="")

    # User metadata
    def _on_title_update(self, context):
        try:
            self.label = self.onto3d_title if self.onto3d_title.strip() else self.bl_label
        except Exception:
            self.label = self.bl_label

    onto3d_title: StringProperty(name="Title", default="", update=_on_title_update)
    onto3d_description: StringProperty(name="Description", default="")
    onto3d_iri: StringProperty(name="IRI", default="")

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "Onto3DNodeTree"

    def init(self, context):
        # exact order as requested
        while self.inputs: self.inputs.remove(self.inputs[0])
        while self.outputs: self.outputs.remove(self.outputs[0])
        self.outputs.new("Onto3DSocketProperty", "out property")
        self.inputs.new("Onto3DSocketProperty", "in property")
        # init label
        self.label = self.bl_label

    def draw_label(self):
        return getattr(self, "onto3d_title", "") or self.bl_label

    def draw_buttons(self, context, layout):
        
        
        # --- Onto3D: Linked geometry actions (shown only if there are links) ---
        try:
            _names = json.loads(self.get("onto3d_links", "[]"))
        except Exception:
            _names = []
        if _names:
            row = layout.row(align=True)
            row.operator("onto3d.frame_linked_geometry", text="Frame", icon='VIEWZOOM')
            row.operator("onto3d.toggle_localview_linked", text="Isolate", icon='HIDE_OFF')
            layout.separator()

        # --- Properties (generic) ---
        # Show common fields if present, then any other annotated properties
        for fname in ("onto3d_title","onto3d_description","prop_label","iri","IRI","iri_value","iri_url","url"):
            if hasattr(self, fname):
                try:
                    layout.prop(self, fname)
                except Exception:
                    pass

        ann = getattr(self.__class__, "__annotations__", {})
        _skip = {"onto3d_links","onto3d_ontology","onto3d_entity_id","onto3d_property_id"}
        for pname in ann.keys():
            if pname in ("onto3d_title","onto3d_description","prop_label","iri","IRI","iri_value","iri_url","url","onto3d_iri"):
                continue
            if pname in _skip:
                continue
            try:
                layout.prop(self, pname)
            except Exception:
                pass
        # Custom ID properties (excluding link storage)
        
            except Exception:
                val = self.get(k)
                layout.label(text=f"{k}: {val}")
    
class Onto3DNodeProperty(Node):
    bl_idname = "Onto3DNodeProperty"
    bl_label = "Property"
    bl_icon = "LINKED"

    onto3d_ontology: StringProperty(name="Ontology", default="")
    onto3d_property_id: StringProperty(name="Property ID", default="")

    def _on_prop_label_update(self, context):
        try:
            self.label = self.prop_label or ""
        except Exception:
            pass

    # "Label" field that synchronizes the text shown at the top of the node
    prop_label: StringProperty(
        name="Label",
        description="Text shown as node title (overrides automatic label)",
        default="",
        update=_on_prop_label_update
    )

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "Onto3DNodeTree"

    def init(self, context):
        while self.inputs: self.inputs.remove(self.inputs[0])
        while self.outputs: self.outputs.remove(self.outputs[0])
        self.inputs.new("Onto3DSocketProperty", "in")
        self.outputs.new("Onto3DSocketProperty", "out")
        self.label = self.bl_label

    def draw_label(self):
        if getattr(self, "prop_label", ""):
            return self.prop_label
        ont = getattr(self, "onto3d_ontology", "") or "—"
        pid = getattr(self, "onto3d_property_id", "") or "—"
        return f"{ont}:{pid}"

    def draw_buttons(self, context, layout):
        
        
        # --- Onto3D: Linked geometry actions (shown only if there are links) ---
        try:
            _names = json.loads(self.get("onto3d_links", "[]"))
        except Exception:
            _names = []
        if _names:
            row = layout.row(align=True)
            row.operator("onto3d.frame_linked_geometry", text="Frame", icon='VIEWZOOM')
            row.operator("onto3d.toggle_localview_linked", text="Isolate", icon='HIDE_OFF')
            layout.separator()

        # --- Properties (generic) ---
        # Show common fields if present, then any other annotated properties
        for fname in ("onto3d_title","onto3d_description","prop_label","iri","IRI","iri_value","iri_url","url"):
            if hasattr(self, fname):
                try:
                    layout.prop(self, fname)
                except Exception:
                    pass

        ann = getattr(self.__class__, "__annotations__", {})
        _skip = {"onto3d_links","onto3d_ontology","onto3d_entity_id","onto3d_property_id"}
        for pname in ann.keys():
            if pname in ("onto3d_title","onto3d_description","prop_label","iri","IRI","iri_value","iri_url","url","onto3d_iri"):
                continue
            if pname in _skip:
                continue
            try:
                layout.prop(self, pname)
            except Exception:
                pass
        # Custom ID properties (excluding link storage)
        
            except Exception:
                val = self.get(k)
                layout.label(text=f"{k}: {val}")
    
# ----------------------------
# Class registry for this module
# ----------------------------
_CLASSES = (
    Onto3DNodeTree,
    Onto3DSocketProperty,
    Onto3DSocketEntity,
    Onto3DNodeEntity,
    Onto3DNodeProperty,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)

def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)
