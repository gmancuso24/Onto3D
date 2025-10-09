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

    # User metadata - solo Title e URL
    def _on_title_update(self, context):
        try:
            if self.onto3d_title.strip():
                self.label = self.onto3d_title
            else:
                # Se il titolo è vuoto, mostra l'entity type
                entity_id = getattr(self, "onto3d_entity_id", "")
                if entity_id:
                    short_id = entity_id.split('/')[-1]
                    from .rdf_utils import protege_to_blender_name
                    self.label = protege_to_blender_name(short_id)
                else:
                    self.label = self.bl_label
        except Exception:
            self.label = self.bl_label

    onto3d_title: StringProperty(name="Title", default="", update=_on_title_update)
    onto3d_url: StringProperty(name="URL", default="")

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "Onto3DNodeTree"

    def init(self, context):
        # Clear any existing sockets
        while self.inputs: 
            self.inputs.remove(self.inputs[0])
        while self.outputs: 
            self.outputs.remove(self.outputs[0])
        
        # Create sockets: output first, then input
        self.outputs.new("Onto3DSocketProperty", "out property")
        
        # Create input socket with unlimited connections (link_limit=0)
        input_socket = self.inputs.new("Onto3DSocketProperty", "in property")
        input_socket.link_limit = 0  # Allow unlimited incoming connections
        
        # Init label
        self.label = self.bl_label

    def draw_label(self):
        """Mostra il titolo se presente, altrimenti l'entity type"""
        try:
            # Priorità 1: Title (se presente)
            if self.onto3d_title.strip():
                return self.onto3d_title
            
            # Priorità 2: Entity type (solo ultima parte)
            entity_id = getattr(self, "onto3d_entity_id", "")
            if entity_id:
                short_id = entity_id.split('/')[-1]
                from .rdf_utils import protege_to_blender_name
                return protege_to_blender_name(short_id)
            
            # Priorità 3: Label di default
            return self.bl_label
        except:
            return self.bl_label

    def draw_buttons(self, context, layout):
        # --- 1. TIPO DI ENTITÀ (in alto) - solo ultima parte ---
        box = layout.box()
        try:
            from .rdf_utils import protege_to_blender_name
            entity_id = getattr(self, "onto3d_entity_id", "") or ""
            
            if entity_id:
                # Prendi solo l'ultima parte dopo l'ultimo /
                short_id = entity_id.split('/')[-1]
                # Converti underscores in spazi per visualizzazione
                entity_label = protege_to_blender_name(short_id)
                box.label(text=entity_label, icon='NODE')
            else:
                box.label(text="No entity type", icon='INFO')
        except:
            box.label(text="Entity", icon='NODE')
        
        layout.separator()
        
        # --- 2. TITLE ---
        layout.prop(self, "onto3d_title")
        
        # --- 3. URL con bottone "Open in External Browser" ---
        row = layout.row(align=True)
        row.prop(self, "onto3d_url", text="URL")
        if self.onto3d_url.strip():
            op = row.operator("onto3d.open_iri", text="", icon='URL')
            op.iri = self.onto3d_url
        
        # --- 4. LINKED GEOMETRY ACTIONS (in fondo, solo se ci sono link) ---
        try:
            _names = json.loads(self.get("onto3d_links", "[]"))
        except Exception:
            _names = []
        
        if _names:
            layout.separator()
            row = layout.row(align=True)
            row.operator("onto3d.frame_linked_geometry", text="Frame", icon='VIEWZOOM')
            row.operator("onto3d.toggle_localview_linked", text="Isolate", icon='HIDE_OFF')

    
class Onto3DNodeProperty(Node):
    bl_idname = "Onto3DNodeProperty"
    bl_label = "Property"
    bl_icon = "LINKED"

    onto3d_ontology: StringProperty(name="Ontology", default="")
    
    def _on_property_id_update(self, context):
        """Aggiorna il label quando property_id viene impostato"""
        try:
            from .rdf_utils import protege_to_blender_name
            pid = self.onto3d_property_id or ""
            
            if pid:
                short_id = pid.split('/')[-1] if '/' in pid else pid
                self.label = protege_to_blender_name(short_id)
        except:
            pass
    
    onto3d_property_id: StringProperty(
        name="Property ID", 
        default="",
        update=_on_property_id_update
    )
    
    def _get_auto_label(self):
        """Generate automatic label from property ID (solo ultima parte, con spazi)"""
        try:
            from .rdf_utils import protege_to_blender_name
            pid = getattr(self, "onto3d_property_id", "") or ""
            
            if pid:
                # Estrai solo l'ultima parte dopo l'ultimo / (se presente)
                short_id = pid.split('/')[-1] if '/' in pid else pid
                # Converti underscores in spazi
                return protege_to_blender_name(short_id)
            else:
                return "Property"
        except:
            pid = getattr(self, "onto3d_property_id", "") or "Property"
            # Fallback: estrai ultima parte
            short_id = pid.split('/')[-1] if '/' in pid else pid
            return short_id.replace('_', ' ')

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "Onto3DNodeTree"

    def init(self, context):
        # Clear any existing sockets
        while self.inputs: 
            self.inputs.remove(self.inputs[0])
        while self.outputs: 
            self.outputs.remove(self.outputs[0])
        
        # Property nodes: single input and single output (link_limit=1 is default)
        self.inputs.new("Onto3DSocketProperty", "in")
        self.outputs.new("Onto3DSocketProperty", "out")

    def draw_label(self):
        """Mostra nell'header il nome della property (solo ultima parte, con spazi)"""
        return self._get_auto_label()

    def draw_buttons(self, context, layout):
        # --- NOME DELLA PROPERTY (stesso stile del nodo entity) ---
        box = layout.box()
        box.label(text=self._get_auto_label(), icon='LINKED')

    
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