# ui_panels.py – Onto3D N‑Panel & geometry helpers
# ------------------------------------------------------------
# Implements:
#   - Info panel (shows active node's properties + buttons: Open IRI, Frame Selected, Isolate Selected)
#   - Connect Geometry panel (English instructions; simple non-interactive list of linked objects)
#   - Operators to link/unlink objects to the active node, frame & isolate linked geometry in 3D View
#
# Storage conventions:
#   - On Node:   node["onto3d_links"] = JSON list of object names
#   - On Object: obj["onto3d_node"] = node.name
#
# Safe to drop-in. No assumptions on specific node classes.
# ------------------------------------------------------------

import bpy
import json
from bpy.types import Operator, Panel
from bpy.props import BoolProperty, StringProperty

# -----------------------
# Helpers
# -----------------------

def _is_node_editor(context):
    return context.area and context.area.type == 'NODE_EDITOR'

def _active_node(context):
    space = getattr(context, "space_data", None)
    if not space or not getattr(space, "node_tree", None):
        return None
    return space.node_tree.nodes.active

def _selected_objects(context):
    return list(context.selected_objects or [])

def _ensure_node_links_container(node):
    if "onto3d_links" not in node:
        node["onto3d_links"] = json.dumps([])

def _read_links(node):
    try:
        return set(json.loads(node.get("onto3d_links", "[]")))
    except Exception:
        return set()

def _write_links(node, names_set):
    node["onto3d_links"] = json.dumps(sorted(names_set))

def _report(self, level, msg):
    self.report({level}, msg)

def _find_3d_view_area_region_window(screen):
    # Return the first available (area, region) for VIEW_3D/WINDOW
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    return area, region
    return None, None

def _objects_from_names(names):
    obs = []
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob:
            obs.append(ob)
    return obs

# Try to extract an IRI/URL from the node by common attribute or custom prop names,
# or from sockets named 'IRI' (string).
_POSSIBLE_IRI_ATTRS = ["iri", "IRI", "iri_value", "iri_url", "url", "iri_str", "onto3d_iri", "onto3d_url"]

def _guess_iri_from_node(node):
    # 1) Python/RNA attributes
    for attr in _POSSIBLE_IRI_ATTRS:
        if hasattr(node, attr):
            v = getattr(node, attr, "")
            if isinstance(v, str) and v.strip():
                return v.strip()
    # 2) ID custom properties
    for attr in _POSSIBLE_IRI_ATTRS:
        if attr in node.keys():
            v = node.get(attr, "")
            if isinstance(v, str) and v.strip():
                return v.strip()
    # 3) Sockets named "IRI" (or containing "iri")
    try:
        for sock in getattr(node, "inputs", []):
            if "iri" in sock.name.lower():
                v = getattr(sock, "default_value", "")
                if isinstance(v, str) and v.strip():
                    return v.strip()
    except Exception:
        pass
    return ""

def _get_node_graph_name(node):
    """Get the name of the node tree containing this node"""
    try:
        if hasattr(node, "id_data") and node.id_data:
            return node.id_data.name
    except Exception:
        pass
    return "Unknown Graph"

def _get_entity_type_display(node):
    """Get entity type for display (solo ultima parte, con spazi)"""
    try:
        entity_id = getattr(node, "onto3d_entity_id", "") or ""
        if entity_id:
            # Prendi solo l'ultima parte dopo l'ultimo /
            short_id = entity_id.split('/')[-1]
            # Converti underscores in spazi
            try:
                from .rdf_utils import protege_to_blender_name
                return protege_to_blender_name(short_id)
            except:
                return short_id.replace('_', ' ')
    except:
        pass
    return "Entity"

# -----------------------
# Operators
# -----------------------

class ONTO3D_OT_OpenIRI(Operator):
    """Open the node IRI/URL in the default browser"""
    bl_idname = "onto3d.open_iri"
    bl_label = "Open IRI"
    bl_options = {'REGISTER'}

    iri: StringProperty(name="IRI/URL", default="")

    def execute(self, context):
        iri = self.iri.strip()
        if not iri:
            node = _active_node(context)
            if node:
                iri = _guess_iri_from_node(node).strip()
        if not iri:
            _report(self, 'WARNING', "No IRI/URL found on the active node.")
            return {'CANCELLED'}
        try:
            import webbrowser
            # normalize scheme if missing
            try:
                from urllib.parse import urlparse
                pr = urlparse(iri)
                if not pr.scheme and not iri.lower().startswith(('mailto:', 'doi:')):
                    iri = 'https://' + iri
            except Exception:
                if not (iri.startswith('http://') or iri.startswith('https://') or iri.startswith('mailto:') or iri.startswith('doi:')):
                    iri = 'https://' + iri
            webbrowser.open_new_tab(iri)
            _report(self, 'INFO', f"Opening: {iri}")
        except Exception as ex:
            _report(self, 'ERROR', f"Cannot open IRI: {ex}")
            return {'CANCELLED'}
        return {'FINISHED'}


class ONTO3D_OT_CreateConnection(Operator):
    """Link the active node to selected geometry (multiple allowed)"""
    bl_idname = "onto3d.create_connection"
    bl_label = "Create Connection"
    bl_options = {'REGISTER', 'UNDO'}

    include_children: BoolProperty(
        name="Include Children of Empties",
        description="If an Empty is selected, also link all its children",
        default=True,
    )

    def execute(self, context):
        if not _is_node_editor(context):
            _report(self, 'WARNING', "Open the Node Editor to link a node.")
            return {'CANCELLED'}
        node = _active_node(context)
        if not node:
            _report(self, 'WARNING', "No active node selected.")
            return {'CANCELLED'}
        objs = _selected_objects(context)
        if not objs:
            _report(self, 'WARNING', "Select one or more objects in the 3D Viewport.")
            return {'CANCELLED'}

        expanded = []
        for ob in objs:
            expanded.append(ob)
            if self.include_children and ob.type == 'EMPTY':
                expanded.extend(list(ob.children_recursive))

        _ensure_node_links_container(node)
        names = _read_links(node)
        added = 0
        for ob in expanded:
            if ob.name not in names:
                names.add(ob.name)
                added += 1
            ob["onto3d_node"] = node.name

        _write_links(node, names)
        _report(self, 'INFO', f"Linked {added} objects to node '{node.name}'.")
        return {'FINISHED'}


class ONTO3D_OT_BreakConnection(Operator):
    """Unlink the active node from selected geometry (or all)"""
    bl_idname = "onto3d.break_connection"
    bl_label = "Break Connection"
    bl_options = {'REGISTER', 'UNDO'}

    clear_all_for_node: BoolProperty(
        name="Clear ALL for Active Node",
        description="Ignore selection and remove ALL links of the active node",
        default=False,
    )

    def execute(self, context):
        if not _is_node_editor(context):
            _report(self, 'WARNING', "Open the Node Editor to unlink a node.")
            return {'CANCELLED'}
        node = _active_node(context)
        if not node:
            _report(self, 'WARNING', "No active node selected.")
            return {'CANCELLED'}

        _ensure_node_links_container(node)
        names = _read_links(node)

        if self.clear_all_for_node:
            for name in list(names):
                ob = bpy.data.objects.get(name)
                if ob and ob.get("onto3d_node") == node.name:
                    try:
                        del ob["onto3d_node"]
                    except Exception:
                        pass
            names.clear()
            _write_links(node, names)
            _report(self, 'INFO', f"Removed all links for '{node.name}'.")
            return {'FINISHED'}

        objs = _selected_objects(context)
        if not objs:
            _report(self, 'WARNING', "Select one or more objects to unlink.")
            return {'CANCELLED'}

        removed = 0
        for ob in objs:
            if ob.name in names:
                names.remove(ob.name)
                removed += 1
            if ob.get("onto3d_node") == node.name:
                try:
                    del ob["onto3d_node"]
                except Exception:
                    pass

        _write_links(node, names)
        _report(self, 'INFO', f"Unlinked {removed} objects from '{node.name}'.")
        return {'FINISHED'}


class ONTO3D_OT_UpdateConnections(Operator):
    """Clean stale links (deleted/renamed objects)"""
    bl_idname = "onto3d.update_connections"
    bl_label = "Update Connections"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not _is_node_editor(context):
            _report(self, 'WARNING', "Open the Node Editor to update links.")
            return {'CANCELLED'}
        node = _active_node(context)
        if not node:
            _report(self, 'WARNING', "No active node selected.")
            return {'CANCELLED'}
        _ensure_node_links_container(node)
        names = _read_links(node)
        valid = set(n for n in names if n in bpy.data.objects)
        removed = len(names) - len(valid)
        _write_links(node, valid)
        _report(self, 'INFO', f"Cleanup done. Removed {removed} stale links.")
        return {'FINISHED'}


class ONTO3D_OT_FrameLinkedGeometry(Operator):
    """Frame the geometry linked to the active node in the 3D Viewport"""
    bl_idname = "onto3d.frame_linked_geometry"
    bl_label = "Frame Selected"
    bl_options = {'REGISTER'}

    def execute(self, context):
        node = _active_node(context)
        if not node:
            _report(self, 'WARNING', "No active node selected.")
            return {'CANCELLED'}
        names = _read_links(node)
        if not names:
            _report(self, 'WARNING', "Active node has no linked geometry.")
            return {'CANCELLED'}
        obs = _objects_from_names(names)

        # Ensure selection
        for ob in bpy.data.objects:
            ob.select_set(False)
        for ob in obs:
            ob.hide_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob

        area, region = _find_3d_view_area_region_window(context.window.screen)
        if not area or not region:
            _report(self, 'ERROR', "No 3D View found to frame selection.")
            return {'CANCELLED'}
        try:
            with context.temp_override(window=context.window, screen=context.screen, area=area, region=region, view_layer=context.view_layer, scene=context.scene):
                bpy.ops.view3d.view_selected()
            _report(self, 'INFO', "Framed linked geometry in 3D Viewport.")
            return {'FINISHED'}
        except Exception as ex:
            _report(self, 'ERROR', f"Frame failed: {ex}")
            return {'CANCELLED'}


class ONTO3D_OT_ToggleLocalViewLinked(Operator):
    """Toggle Local View around geometry linked to the active node"""
    bl_idname = "onto3d.toggle_localview_linked"
    bl_label = "Isolate Selected"
    bl_options = {'REGISTER'}

    def execute(self, context):
        node = _active_node(context)
        if not node:
            _report(self, 'WARNING', "No active node selected.")
            return {'CANCELLED'}
        names = _read_links(node)
        if not names:
            _report(self, 'WARNING', "Active node has no linked geometry.")
            return {'CANCELLED'}
        obs = _objects_from_names(names)
        if not obs:
            _report(self, 'WARNING', "Linked geometry not found. Run Update Links.")
            return {'CANCELLED'}

        # Select linked and ensure visible
        for ob in bpy.data.objects:
            ob.select_set(False)
        for ob in obs:
            ob.hide_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob

        area, region = _find_3d_view_area_region_window(context.window.screen)
        if not area or not region:
            _report(self, 'ERROR', "No 3D View found to toggle Local View.")
            return {'CANCELLED'}

        try:
            with context.temp_override(window=context.window, screen=context.screen, area=area, region=region, view_layer=context.view_layer, scene=context.scene):
                # Toggle local view
                bpy.ops.view3d.localview()
                # Optionally frame after toggling
                try:
                    bpy.ops.view3d.view_selected()
                except Exception:
                    pass
            _report(self, 'INFO', "Toggled Local View for linked geometry.")
            return {'FINISHED'}
        except Exception as ex:
            _report(self, 'ERROR', f"Local View toggle failed: {ex}")
            return {'CANCELLED'}


# -----------------------
# VIEW_3D Helpers
# -----------------------

def _node_by_object_link(ob):
    """Return (node, node_tree) for object linked via ob['onto3d_node'] searching all Onto3DNodeTree."""
    node_name = ob.get("onto3d_node") if ob else None
    if not node_name:
        return None, None
    # Search across all node groups of our type
    for nt in bpy.data.node_groups:
        if getattr(nt, "bl_idname", "") == "Onto3DNodeTree":
            nd = nt.nodes.get(node_name)
            if nd:
                return nd, nt
    # Fallback: try any node tree
    for nt in bpy.data.node_groups:
        nd = nt.nodes.get(node_name) if hasattr(nt, "nodes") else None
        if nd:
            return nd, nt
    return None, None

# -----------------------
# Panels
# -----------------------

class ONTO3D_PT_Main(Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Onto3D'
    bl_label = 'Info'

    @classmethod
    def poll(cls, context):
        return _is_node_editor(context)

    def draw(self, context):
        layout = self.layout
        node = _active_node(context)

        if not node:
            layout.label(text="No active node.", icon='INFO')
            return

        # Header
        header = layout.box()
        header.label(text=f"Active Node: {node.name}", icon='NODE')
        header.label(text=f"Type: {getattr(node, 'bl_idname', node.__class__.__name__)}")

        # Open IRI
        row = header.row(align=True)
        row.operator("onto3d.open_iri", text="Open IRI", icon='URL')

        # spacer + actions
        header.separator()
        row = header.row(align=True)
        row.operator("onto3d.frame_linked_geometry", text="Frame Selected", icon='VIEW_ZOOM')
        row.operator("onto3d.toggle_localview_linked", text="Isolate Selected", icon='HIDE_OFF')
        

        # Properties
        box = layout.box()
        box.label(text="Properties")
        # 1) Python-defined annotations (typical for custom nodes)
        annotations = getattr(node.__class__, "__annotations__", {})
        _skip = {"onto3d_links","onto3d_ontology","onto3d_entity_id","onto3d_property_id"}
        for prop_name in annotations.keys():
            if prop_name in _skip:
                continue
            try:
                box.prop(node, prop_name)
            except Exception:
                pass


class ONTO3D_PT_ConnectGeometry(Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Onto3D'
    bl_label = 'Connect Geometry'

    @classmethod
    def poll(cls, context):
        return _is_node_editor(context)

    def draw(self, context):
        layout = self.layout
        node = _active_node(context)

        col = layout.column(align=True)
        col.label(text="Link the active node to selected objects in 3D.", icon='LINKED')
        col.label(text="You can link multiple objects (including children of Empties).")

        row = col.row(align=True)
        op = row.operator("onto3d.create_connection", text="Create Connection", icon='PLUS')
        op.include_children = True
        row = col.row(align=True)
        row.operator("onto3d.break_connection", text="Break (Selected)", icon='X').clear_all_for_node = False
        row.operator("onto3d.break_connection", text="Break ALL", icon='TRASH').clear_all_for_node = True
        col.operator("onto3d.update_connections", text="Update Links", icon='FILE_REFRESH')

        layout.separator()

        # Simple list of linked geometry (non-interactive)
        if node:
            names = sorted(list(_read_links(node)))
            box = layout.box()
            # Warn if some links are missing
            missing = [n for n in names if n not in bpy.data.objects]
            if missing:
                box.label(text=f"{len(missing)} missing – run Update Links", icon='ERROR')
            box.label(text=f"Linked Geometry ({len(names)})")
            for n in names:
                prefix = "• "
                box.label(text=f"{prefix}{n}")
        else:
            layout.label(text="No active node.", icon='INFO')


class ONTO3D_OT_FrameLinkedNode(Operator):
    """Frame the Node linked to the active selected object"""
    bl_idname = "onto3d.frame_linked_node"
    bl_label = "Frame Linked Node"
    bl_options = {'REGISTER'}

    def execute(self, context):
        ob = context.active_object
        if not ob:
            _report(self, 'WARNING', "No active object selected.")
            return {'CANCELLED'}
        node, ntree = _node_by_object_link(ob)
        if not node:
            _report(self, 'WARNING', "No linked node found on active object.")
            return {'CANCELLED'}

        # Find a Node Editor and set context
        area = region = None
        for a in context.window.screen.areas:
            if a.type == 'NODE_EDITOR':
                area = a
                break
        if not area:
            _report(self, 'ERROR', "No Node Editor found.")
            return {'CANCELLED'}
        for r in area.regions:
            if r.type == 'WINDOW':
                region = r
                break
        if not region:
            _report(self, 'ERROR', "No Node Editor region found.")
            return {'CANCELLED'}

        # Ensure the node tree is visible and node is active/selected
        with context.temp_override(window=context.window, screen=context.screen, area=area, region=region, scene=context.scene):
            space = area.spaces.active
            try:
                space.node_tree = ntree
            except Exception:
                pass
            # Activate node
            for n in space.node_tree.nodes:
                n.select = False
            node.select = True
            space.node_tree.nodes.active = node
            try:
                bpy.ops.node.view_selected()
            except Exception:
                pass
        _report(self, 'INFO', f"Framed node: {node.name}")
        return {'FINISHED'}


class ONTO3D_PT_View3D_Info(Panel):
    """Pannello 3D Viewport che mostra info del nodo linkato all'oggetto attivo"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Onto3D'
    bl_label = 'Linked Node Info'

    @classmethod
    def poll(cls, context):
        return getattr(context, "area", None) and context.area.type == 'VIEW_3D'

    def draw(self, context):
        layout = self.layout
        ob = context.active_object
        
        if not ob:
            layout.label(text="No active object.", icon='INFO')
            return
            
        node, ntree = _node_by_object_link(ob)
        if not node:
            layout.label(text="No linked node for active object.", icon='INFO')
            return

        # --- PRIMO BOX: Graph Info ---
        box = layout.box()
        
        # Node Graph: nome del grafo (icona NODETREE come nel Node Editor)
        graph_name = _get_node_graph_name(node)
        box.label(text=f"Node Graph: {graph_name}", icon='NODETREE')
        
        # Entity type (solo ultima parte, con spazi) - icona NODE come sul nodo
        entity_display = _get_entity_type_display(node)
        box.label(text=entity_display, icon='NODE')
        
        box.separator()
        
        # Proprietà Title (non Label)
        if hasattr(node, "onto3d_title"):
            box.prop(node, "onto3d_title", text="Title")
        
        # Proprietà URL (non IRI)
        iri_val = _guess_iri_from_node(node)
        if hasattr(node, "onto3d_url"):
            row = box.row(align=True)
            row.prop(node, "onto3d_url", text="URL")
            if node.onto3d_url.strip():
                op = row.operator("onto3d.open_iri", text="", icon='URL')
                op.iri = node.onto3d_url
        elif iri_val:
            # Fallback: mostra URL trovato con guess e bottone
            row = box.row(align=True)
            row.label(text=f"URL: {iri_val[:30]}...")
            op = row.operator("onto3d.open_iri", text="", icon='URL')
            op.iri = iri_val

        # --- SECONDO BOX: Actions ---
        box = layout.box()
        
        # Pulsante Zoom to Graph
        box.operator("onto3d.frame_linked_node", text="Zoom to Graph", icon='VIEWZOOM')


# -----------------------
# Registration
# -----------------------

_CLASSES = (
    ONTO3D_OT_OpenIRI,
    ONTO3D_OT_CreateConnection,
    ONTO3D_OT_BreakConnection,
    ONTO3D_OT_UpdateConnections,
    ONTO3D_OT_FrameLinkedGeometry,
    ONTO3D_OT_ToggleLocalViewLinked,
    ONTO3D_OT_FrameLinkedNode,
    ONTO3D_PT_Main,
    ONTO3D_PT_ConnectGeometry,
    ONTO3D_PT_View3D_Info,
)

def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()