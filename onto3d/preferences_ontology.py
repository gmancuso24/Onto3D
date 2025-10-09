import bpy
from bpy.types import AddonPreferences, PropertyGroup, Operator, UIList
from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty, IntProperty
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories
import os, json

# Import RDF parsing from rdf_utils
from .rdf_utils import parse_ontology_file

# Default (fallback) ids
ENTITY_NODE_ID_DEFAULT   = "Onto3DNodeEntity"
PROPERTY_NODE_ID_DEFAULT = "Onto3DNodeProperty"
TREE_TYPE_ID             = "Onto3DNodeTree"

def _resolve_node_ids():
    import bpy
    ent_id = getattr(getattr(bpy.types, "Onto3DNodeEntity", None), "bl_idname", None) or ENTITY_NODE_ID_DEFAULT
    prop_id = getattr(getattr(bpy.types, "Onto3DNodeProperty", None), "bl_idname", None) or PROPERTY_NODE_ID_DEFAULT
    return ent_id, prop_id

def _poll_onto3d(context):
    space = getattr(context, "space_data", None)
    if not space or space.type != 'NODE_EDITOR':
        return False
    return getattr(space, "tree_type", "") == TREE_TYPE_ID

# =========================
# Public API
# =========================
def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    _ensure_node_props()
    # Use app handler to load after Blender is fully initialized
    bpy.app.timers.register(_delayed_load, first_interval=0.1)

def unregister():
    _unregister_all_categories()
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

# =========================
# Internal state
# =========================
ONTO_REG = {}
_NODE_CAT_IDS = set()

def _slugify(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")

# =========================
# Preferences model
# =========================
class ONTO3D_PG_Ontology(PropertyGroup):
    name: StringProperty(name="Label", default="New ontology")
    slug: StringProperty(name="Slug", description="Unique id (e.g. crm, cra, crmsci)", default="")
    source_type: EnumProperty(
        name="Source",
        items=[
            ('FILE', "File", "Local ontology file (.ttl, .owl, .rdf, .json)"),
            ('URL', "URL", "Remote ontology file URL")
        ],
        default='FILE'
    )
    path: StringProperty(name="Path / URL", subtype='FILE_PATH', description="File path (JSON-LD/TTL/OWL) or URL")
    prefix: StringProperty(name="Prefix", description="Shown in Add menu labels, e.g. CRM, CRA", default="")
    enabled: BoolProperty(name="Enabled", default=True)

    cached_data: StringProperty(
        name="Cached Data",
        description="Parsed ontology data (JSON)",
        default=""
    )

class ONTO3D_Preferences(AddonPreferences):
    bl_idname = __package__.split('.')[0] if '.' in __package__ else __package__

    ontologies: CollectionProperty(type=ONTO3D_PG_Ontology)
    active_index: IntProperty(default=0)

    def draw(self, context):
        layout = self.layout
        
        # Header
        col = layout.column()
        header = col.box()
        header.label(text="Import Ontologies", icon='IMPORT')
        
        # Instructions
        instructions = col.box()
        instructions.label(text="How to import ontologies:", icon='INFO')
        instr_col = instructions.column(align=True)
        instr_col.scale_y = 0.8
        instr_col.label(text="1. Click 'Add' to create a new ontology entry")
        instr_col.label(text="2. Set a name, slug (unique ID), and prefix for the menu")
        instr_col.label(text="3. Choose source type: File (local .ttl/.owl/.rdf) or URL")
        instr_col.label(text="4. Select the file path or enter the URL")
        instr_col.label(text="5. Click 'Reload Selected' to load the ontology")
        instr_col.label(text="6. Enable/disable ontologies using the checkbox")
        instr_col.label(text="7. Preferences are saved automatically with Blender")
        instr_col.label(text="Tip: Use 'Reload All' to refresh all enabled ontologies")
        
        layout.separator()
        
        # Ontology list
        col = layout.column()
        col.label(text="Loaded Ontologies:", icon='BOOKMARKS')
        row = col.row()
        row.template_list("ONTO3D_UL_Ontologies", "", self, "ontologies", self, "active_index", rows=4)

        buttons = col.column(align=True)
        r = buttons.row(align=True)
        r.operator("onto3d.ontology_add", text="Add", icon="ADD")
        r.operator("onto3d.ontology_remove", text="Remove", icon="REMOVE")
        r = buttons.row(align=True)
        r.operator("onto3d.ontology_reload_one", text="Reload Selected", icon="FILE_REFRESH")
        r.operator("onto3d.ontology_reload_all", text="Reload All", icon="FILE_REFRESH")
        buttons.operator("onto3d.ontology_rebuild_categories", text="Rebuild Node Menu", icon="NODETREE")

        if 0 <= self.active_index < len(self.ontologies):
            item = self.ontologies[self.active_index]
            box = col.box()
            box.prop(item, "name")
            box.prop(item, "slug")
            box.prop(item, "prefix")
            box.prop(item, "source_type")
            if item.source_type == 'FILE':
                box.prop(item, "path", text="File")
            elif item.source_type == 'URL':
                box.prop(item, "path", text="URL")
            
            if item.cached_data:
                box.label(text="✓ Cached", icon='CHECKMARK')
                box.operator("onto3d.ontology_clear_cache", icon='TRASH')
            else:
                box.label(text="Cache: Not present", icon='ERROR')
                
            row = box.row(align=True)
            row.prop(item, "enabled", toggle=True)
            row.operator("onto3d.ontology_reload_one", text="Apply", icon="CHECKMARK")

class ONTO3D_UL_Ontologies(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.7)
        split.row().label(text=item.name or "(unnamed)")
        r = split.row(align=True)
        r.prop(item, "enabled", text="", icon='CHECKBOX_HLT' if item.enabled else 'CHECKBOX_DEHLT')

# =========================
# Operators
# =========================
class ONTO3D_OT_OntologyAdd(Operator):
    """Add a new ontology to the list"""
    bl_idname = "onto3d.ontology_add"
    bl_label = "Add Ontology"
    bl_description = "Add a new ontology entry to import"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = _get_prefs()
        item = prefs.ontologies.add()
        item.name = "New ontology"
        prefs.active_index = len(prefs.ontologies) - 1
        # Save preferences
        _save_preferences()
        return {'FINISHED'}

class ONTO3D_OT_OntologyRemove(Operator):
    """Remove the selected ontology from the list"""
    bl_idname = "onto3d.ontology_remove"
    bl_label = "Remove Ontology"
    bl_description = "Remove the selected ontology and rebuild the node menu"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = _get_prefs()
        idx = prefs.active_index
        if 0 <= idx < len(prefs.ontologies):
            slug = prefs.ontologies[idx].slug.strip() or _slugify(prefs.ontologies[idx].name)
            ONTO_REG.pop(slug, None)
            prefs.ontologies.remove(idx)
            prefs.active_index = min(idx, len(prefs.ontologies)-1)
            _rebuild_node_categories()
            # Save preferences
            _save_preferences()
            self.report({'INFO'}, "Ontology removed and node menu rebuilt")
        return {'FINISHED'}

class ONTO3D_OT_OntologyReloadOne(Operator):
    """Reload the selected ontology from its source file/URL"""
    bl_idname = "onto3d.ontology_reload_one"
    bl_label = "Reload Selected"
    bl_description = "Reload the selected ontology from source and rebuild the node menu"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = _get_prefs()
        if not (0 <= prefs.active_index < len(prefs.ontologies)):
            return {'CANCELLED'}
        _load_enabled_ontologies(prefs, only_index=prefs.active_index)
        _rebuild_node_categories()
        # Save preferences
        _save_preferences()
        self.report({'INFO'}, "Ontology reloaded")
        return {'FINISHED'}

class ONTO3D_OT_OntologyReloadAll(Operator):
    """Reload all enabled ontologies from their source files/URLs"""
    bl_idname = "onto3d.ontology_reload_all"
    bl_label = "Reload All"
    bl_description = "Reload all enabled ontologies from source and rebuild the node menu"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = _get_prefs()
        _load_enabled_ontologies(prefs)
        _rebuild_node_categories()
        # Save preferences
        _save_preferences()
        self.report({'INFO'}, "All ontologies reloaded")
        return {'FINISHED'}

class ONTO3D_OT_RebuildNodeMenu(Operator):
    """Rebuild the Add menu without reloading ontology files"""
    bl_idname = "onto3d.ontology_rebuild_categories"
    bl_label = "Rebuild Node Menu"
    bl_description = "Rebuild the node Add menu using cached ontology data (faster than reload)"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        _rebuild_node_categories()
        self.report({'INFO'}, "Node menu rebuilt")
        return {'FINISHED'}

class ONTO3D_OT_OntologyClearCache(Operator):
    """Clear the cached data for this ontology and force reload from source"""
    bl_idname = "onto3d.ontology_clear_cache"
    bl_label = "Clear Cache"
    bl_description = "Clear cached ontology data and force reload from source file/URL on next reload"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    def execute(self, context):
        prefs = _get_prefs()
        if 0 <= prefs.active_index < len(prefs.ontologies):
            prefs.ontologies[prefs.active_index].cached_data = ""
            # Save preferences
            _save_preferences()
            self.report({'INFO'}, "Cache cleared. Click 'Reload Selected' to re-parse from source.")
        return {'FINISHED'}
    
# =========================
# Utility functions
# =========================
def _get_prefs():
    """Get addon preferences safely"""
    try:
        addon_name = __package__.split('.')[0] if '.' in __package__ else __package__
        return bpy.context.preferences.addons[addon_name].preferences
    except Exception as e:
        print(f"[Onto3D] Error getting preferences: {e}")
        return None

def _save_preferences():
    """Force save user preferences to disk"""
    try:
        bpy.ops.wm.save_userpref()
    except Exception as e:
        print(f"[Onto3D] Warning: Could not save preferences: {e}")

# =========================
# Parse / Load
# =========================
def _parse_ontology_from_source(item: ONTO3D_PG_Ontology):
    """Parse ontology from source (file or URL)"""
    slug = (item.slug.strip() or _slugify(item.name))[:32]
    prefix = item.prefix.strip() or slug.upper()
    entities, properties = [], []

    if item.source_type == 'FILE':
        path = bpy.path.abspath(item.path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        lower = path.lower()
        if lower.endswith((".json", ".jsonld")):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entities = [(e.get("id", ""), e.get("label", e.get("id", "")), e.get("ns", "")) 
                       for e in data.get("entities", [])]
            properties = [(p.get("id", ""), p.get("label", p.get("id", "")), p.get("ns", "")) 
                         for p in data.get("properties", [])]
        else:
            entities, properties = parse_ontology_file(path, is_url=False)

    elif item.source_type == 'URL':
        url = (item.path or "").strip()
        if not url:
            raise ValueError("URL cannot be empty")
        lower = url.lower()
        if lower.endswith((".json", ".jsonld")):
            import urllib.request, tempfile
            fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(lower)[1] or ".json")
            os.close(fd)
            try:
                urllib.request.urlretrieve(url, tmp_path)
                with open(tmp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entities = [(e.get("id", ""), e.get("label", e.get("id", "")), e.get("ns", "")) 
                           for e in data.get("entities", [])]
                properties = [(p.get("id", ""), p.get("label", p.get("id", "")), p.get("ns", "")) 
                             for p in data.get("properties", [])]
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        else:
            entities, properties = parse_ontology_file(url, is_url=True)

    return {"name": item.name.strip() or slug, "prefix": prefix, "entities": entities, "properties": properties}


def _load_enabled_ontologies(prefs, only_index=None):
    """Load ontologies from preferences, using cache when available"""
    if not prefs:
        return
        
    targets = range(len(prefs.ontologies)) if only_index is None else [only_index]
    for i in targets:
        it = prefs.ontologies[i]
        slug = (it.slug.strip() or _slugify(it.name))[:32]
        if not it.enabled:
            ONTO_REG.pop(slug, None)
            continue

        if it.cached_data:
            try:
                cached = json.loads(it.cached_data)
                ONTO_REG[slug] = cached
                continue
            except Exception as e:
                print(f"[Onto3D] Cache corrupted for '{it.name}', reloading: {e}")

        try:
            model = _parse_ontology_from_source(it)
            it.cached_data = json.dumps({
                "name": model["name"],
                "prefix": model["prefix"],
                "entities": model.get("entities", []),
                "properties": model.get("properties", []),
            })
            ONTO_REG[slug] = {
                "name": model["name"],
                "prefix": model["prefix"],
                "entities": list(model.get("entities", [])),
                "properties": list(model.get("properties", [])),
            }
        except Exception as e:
            print(f"[Onto3D] Error loading ontology '{it.name}': {e}")
            continue

# =========================
# Node menus (Add)
# =========================
def _unregister_all_categories():
    global _NODE_CAT_IDS
    for cat_id in list(_NODE_CAT_IDS):
        try:
            unregister_node_categories(cat_id)
        except Exception:
            pass
    _NODE_CAT_IDS.clear()

def _rebuild_node_categories():
    _unregister_all_categories()
    
    ENTITY_NODE_ID, PROPERTY_NODE_ID = _resolve_node_ids()
    
    cat_defs = []
    # per-ontology
    for slug, data in ONTO_REG.items():
        pre = data["prefix"]
        ent_items, prop_items = [], []
        
        for eid, elab, ns in data["entities"]:
            # Estrai solo l'ultima parte dell'ID dopo l'ultimo /
            short_id = eid.split('/')[-1] if '/' in eid else eid
            
            # Converti underscores in spazi
            try:
                from .rdf_utils import protege_to_blender_name
                display_label = protege_to_blender_name(short_id)
            except:
                display_label = short_id.replace('_', ' ')
            
            ent_items.append(NodeItem(
                ENTITY_NODE_ID,
                label=f"[{pre}] {display_label}",
                settings={
                    "onto3d_ontology": repr(slug),
                    "onto3d_entity_id": repr(eid),
                }
            ))
        
        for pid, plab, ns in data["properties"]:
            # Estrai solo l'ultima parte dell'ID dopo l'ultimo /
            short_id = pid.split('/')[-1] if '/' in pid else pid
            
            # Converti underscores in spazi
            try:
                from .rdf_utils import protege_to_blender_name
                display_label = protege_to_blender_name(short_id)
            except:
                display_label = short_id.replace('_', ' ')
            
            prop_items.append(NodeItem(
                PROPERTY_NODE_ID,
                label=f"[{pre}] {display_label}",
                settings={
                    "onto3d_ontology": repr(slug),
                    "onto3d_property_id": repr(pid),
                }
            ))
        
        if ent_items:
            cid = f"ONTO3D_ENT_{slug}"
            cat_defs.append(NodeCategory(cid, f"Onto3D • {data['name']} • Entities", items=ent_items))
            _NODE_CAT_IDS.add(cid)
        if prop_items:
            cid = f"ONTO3D_PROP_{slug}"
            cat_defs.append(NodeCategory(cid, f"Onto3D • {data['name']} • Properties", items=prop_items))
            _NODE_CAT_IDS.add(cid)

    # "All" categories
    all_ent, all_prop = [], []
    for slug, data in ONTO_REG.items():
        pre = data["prefix"]
        
        for eid, elab, ns in data["entities"]:
            # Estrai solo l'ultima parte dell'ID dopo l'ultimo /
            short_id = eid.split('/')[-1] if '/' in eid else eid
            
            # Converti underscores in spazi
            try:
                from .rdf_utils import protege_to_blender_name
                display_label = protege_to_blender_name(short_id)
            except:
                display_label = short_id.replace('_', ' ')
            
            all_ent.append(NodeItem(
                ENTITY_NODE_ID, 
                label=f"[{pre}] {display_label}", 
                settings={
                    "onto3d_ontology": repr(slug), 
                    "onto3d_entity_id": repr(eid)
                }
            ))
        
        for pid, plab, ns in data["properties"]:
            # Estrai solo l'ultima parte dell'ID dopo l'ultimo /
            short_id = pid.split('/')[-1] if '/' in pid else pid
            
            # Converti underscores in spazi
            try:
                from .rdf_utils import protege_to_blender_name
                display_label = protege_to_blender_name(short_id)
            except:
                display_label = short_id.replace('_', ' ')
            
            all_prop.append(NodeItem(
                PROPERTY_NODE_ID,
                label=f"[{pre}] {display_label}",
                settings={
                    "onto3d_ontology": repr(slug), 
                    "onto3d_property_id": repr(pid)
                }
            ))
    
    if all_ent:
        cid = "ONTO3D_ENT_ALL"
        cat_defs.insert(0, NodeCategory(cid, "Onto3D • All • Entities", items=all_ent))
        _NODE_CAT_IDS.add(cid)
    if all_prop:
        cid = "ONTO3D_PROP_ALL"
        cat_defs.insert(1, NodeCategory(cid, "Onto3D • All • Properties", items=all_prop))
        _NODE_CAT_IDS.add(cid)

    for cat in cat_defs:
        register_node_categories(cat.identifier, [cat])

# =========================
# Ensure node properties exist
# =========================
def _ensure_node_props():
    try:
        ncls = bpy.types.Onto3DNodeEntity
        if not hasattr(ncls, "onto3d_ontology"):
            ncls.onto3d_ontology = StringProperty(name="Ontology", default="")
        if not hasattr(ncls, "onto3d_entity_id"):
            ncls.onto3d_entity_id = StringProperty(name="Entity ID", default="")
    except Exception:
        pass
    try:
        ncls = bpy.types.Onto3DNodeProperty
        if not hasattr(ncls, "onto3d_ontology"):
            ncls.onto3d_ontology = StringProperty(name="Ontology", default="")
        if not hasattr(ncls, "onto3d_property_id"):
            ncls.onto3d_property_id = StringProperty(name="Property ID", default="")
    except Exception:
        pass

# =========================
# Load from prefs on startup (delayed)
# =========================
def _delayed_load():
    """Load ontologies from preferences after Blender is initialized"""
    try:
        prefs = _get_prefs()
        if prefs:
            print("[Onto3D] Loading ontologies from preferences...")
            _load_enabled_ontologies(prefs)
            _rebuild_node_categories()
            print(f"[Onto3D] Loaded {len(ONTO_REG)} ontologies")
    except Exception as e:
        print(f"[Onto3D] Error during delayed load: {e}")
        import traceback
        traceback.print_exc()
    return None  # Don't repeat

# =========================
# Class registry
# =========================
_classes = (
    ONTO3D_PG_Ontology,
    ONTO3D_Preferences,
    ONTO3D_UL_Ontologies,
    ONTO3D_OT_OntologyAdd,
    ONTO3D_OT_OntologyRemove,
    ONTO3D_OT_OntologyReloadOne,
    ONTO3D_OT_OntologyReloadAll,
    ONTO3D_OT_RebuildNodeMenu,
    ONTO3D_OT_OntologyClearCache
)