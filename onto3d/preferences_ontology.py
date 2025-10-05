import bpy
from bpy.types import AddonPreferences, PropertyGroup, Operator, UIList
from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty, IntProperty
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories
import os, json

# Default (fallback) ids – verranno sovrascritti se troviamo le classi registrate
ENTITY_NODE_ID_DEFAULT   = "Onto3DNodeEntity"
PROPERTY_NODE_ID_DEFAULT = "Onto3DNodeProperty"
TREE_TYPE_ID             = "Onto3DNodeTree"  # se serve, adatta al tuo NodeTree

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

def _parse_ttl_or_owl_any(path_or_url: str, is_url: bool = False):
    try:
        import rdflib
        from rdflib.namespace import RDF, RDFS, OWL, SKOS
    except Exception as e:
        raise RuntimeError("rdflib is not installed or not available in Blender's environment") from e

    g = rdflib.Graph()
    # rdflib capisce da solo il formato nella maggior parte dei casi; lasciamo a lui il detection.
    g.parse(path_or_url)

    def _label_for(node):
        # prova rdfs:label, poi skos:prefLabel, se nulla usa localname dell'URI
        lbl = g.value(node, RDFS.label)
        if lbl:
            return str(lbl)
        lbl = g.value(node, SKOS.prefLabel)
        if lbl:
            return str(lbl)
        # localname fallback
        try:
            s = str(node)
            for sep in ['#', '/', ':']:
                if sep in s:
                    s = s.rsplit(sep, 1)[-1]
            return s
        except Exception:
            return str(node)

    entities = []
    properties = []

    # --- Classi ---
    seen_classes = set()
    for s in g.subjects(RDF.type, RDFS.Class):
        sid = str(s)
        if sid in seen_classes: 
            continue
        entities.append((sid, _label_for(s), ""))  # ns vuoto: opzionale
        seen_classes.add(sid)

    for s in g.subjects(RDF.type, OWL.Class):
        sid = str(s)
        if sid in seen_classes:
            continue
        entities.append((sid, _label_for(s), ""))
        seen_classes.add(sid)

    # --- Proprietà ---
    seen_props = set()
    for s in g.subjects(RDF.type, RDF.Property):
        pid = str(s)
        if pid in seen_props:
            continue
        properties.append((pid, _label_for(s), ""))
        seen_props.add(pid)

    for ptype in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty):
        for s in g.subjects(RDF.type, ptype):
            pid = str(s)
            if pid in seen_props:
                continue
            properties.append((pid, _label_for(s), ""))
            seen_props.add(pid)

    return entities, properties

# =========================
# Public API (what your __init__.py will call)
# =========================
def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    _ensure_node_props()
    _load_from_prefs_and_build()

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
ONTO_REG = {}             # { slug: {"name": str, "prefix": str, "entities": [(id,label,ns)], "properties": [...] } }
_NODE_CAT_IDS = set()     # Track registered NodeCategory identifiers

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
        items=[('FILE',"File","Local file"), ('URL',"URL","Remote URL"), ('BUILTIN',"Built-in","Code preset")],
        default='FILE'
    )
    path: StringProperty(name="Path / URL", subtype='FILE_PATH', description="File path (JSON-LD/TTL/OWL) or URL")
    prefix: StringProperty(name="Prefix", description="Shown in Add menu labels, e.g. CRM, CRA", default="")
    enabled: BoolProperty(name="Enabled", default=True)

class ONTO3D_Preferences(AddonPreferences):
    bl_idname = __package__ if __package__ else __name__

    ontologies: CollectionProperty(type=ONTO3D_PG_Ontology)
    active_index: IntProperty(default=0)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Ontologies", icon='BOOKMARKS')
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
    bl_idname = "onto3d.ontology_add"; bl_label = "Add Ontology"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = context.preferences.addons[__package__ if __package__ else __name__].preferences
        item = prefs.ontologies.add()
        item.name = "New ontology"
        context.preferences.addons[__package__ if __package__ else __name__].preferences.active_index = len(prefs.ontologies) - 1
        return {'FINISHED'}

class ONTO3D_OT_OntologyRemove(Operator):
    bl_idname = "onto3d.ontology_remove"; bl_label = "Remove Ontology"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = context.preferences.addons[__package__ if __package__ else __name__].preferences
        idx = prefs.active_index
        if 0 <= idx < len(prefs.ontologies):
            slug = prefs.ontologies[idx].slug.strip() or _slugify(prefs.ontologies[idx].name)
            ONTO_REG.pop(slug, None)
            prefs.ontologies.remove(idx)
            prefs.active_index = min(idx, len(prefs.ontologies)-1)
            _rebuild_node_categories()
            self.report({'INFO'}, "Ontology removed and node menu rebuilt")
        return {'FINISHED'}

class ONTO3D_OT_OntologyReloadOne(Operator):
    bl_idname = "onto3d.ontology_reload_one"; bl_label = "Reload Selected Ontology"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = context.preferences.addons[__package__ if __package__ else __name__].preferences
        if not (0 <= prefs.active_index < len(prefs.ontologies)):
            return {'CANCELLED'}
        _load_enabled_ontologies(prefs, only_index=prefs.active_index)
        _rebuild_node_categories()
        self.report({'INFO'}, "Ontology reloaded")
        return {'FINISHED'}

class ONTO3D_OT_OntologyReloadAll(Operator):
    bl_idname = "onto3d.ontology_reload_all"; bl_label = "Reload All Ontologies"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        prefs = context.preferences.addons[__package__ if __package__ else __name__].preferences
        _load_enabled_ontologies(prefs)
        _rebuild_node_categories()
        self.report({'INFO'}, "All ontologies reloaded")
        return {'FINISHED'}

class ONTO3D_OT_RebuildNodeMenu(Operator):
    bl_idname = "onto3d.ontology_rebuild_categories"; bl_label = "Rebuild Node Menu"
    bl_options = {'REGISTER', 'INTERNAL'}
    def execute(self, context):
        _rebuild_node_categories()
        self.report({'INFO'}, "Node menu rebuilt")
        return {'FINISHED'}

# =========================
# Parse / Load
# =========================
def _parse_ontology_from_source(item: ONTO3D_PG_Ontology):
    slug = (item.slug.strip() or _slugify(item.name))[:32]
    prefix = item.prefix.strip() or slug.upper()
    entities, properties = [], []

    if item.source_type == 'BUILTIN' and not item.path:
        # Simple example builtin
        entities = [("E22_Man-Made_Object", "E22 Man-Made Object", "crm"),
                    ("E39_Actor", "E39 Actor", "crm")]
        properties = [("P46_is_composed_of", "P46 is composed of", "crm")]
    else:
        if item.source_type == 'FILE':
            path = bpy.path.abspath(item.path)
            if not os.path.exists(path):
                raise FileNotFoundError(path)

            lower = path.lower()
            if lower.endswith((".json", ".jsonld")):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entities = [(e.get("id", ""), e.get("label", e.get("id", "")), e.get("ns", "")) for e in data.get("entities", [])]
                properties = [(p.get("id", ""), p.get("label", p.get("id", "")), p.get("ns", "")) for p in data.get("properties", [])]
            else:
                # RDF/XML (.rdf), TTL (.ttl), OWL (.owl), anche JSON-LD complesso: usa rdflib
                entities, properties = _parse_ttl_or_owl_any(path, is_url=False)

        elif item.source_type == 'URL':
            url = (item.path or "").strip()
            if not url:
                raise ValueError("Empty URL")
            lower = url.lower()
            if lower.endswith((".json", ".jsonld")):
                # scarica JSON e parse semplice
                import urllib.request, tempfile
                fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(lower)[1] or ".json")
                os.close(fd)
                try:
                    urllib.request.urlretrieve(url, tmp_path)
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    entities = [(e.get("id", ""), e.get("label", e.get("id", "")), e.get("ns", "")) for e in data.get("entities", [])]
                    properties = [(p.get("id", ""), p.get("label", p.get("id", "")), p.get("ns", "")) for p in data.get("properties", [])]
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
            else:
                # lascia che rdflib faccia il fetch/parsing direttamente dall’URL (supporta http/https/file)
                entities, properties = _parse_ttl_or_owl_any(url, is_url=True)

    return {"name": item.name.strip() or slug, "prefix": prefix, "entities": entities, "properties": properties}

def _load_enabled_ontologies(prefs: ONTO3D_Preferences, only_index=None):
    targets = range(len(prefs.ontologies)) if only_index is None else [only_index]
    for i in targets:
        it = prefs.ontologies[i]
        slug = (it.slug.strip() or _slugify(it.name))[:32]
        if not it.enabled:
            ONTO_REG.pop(slug, None)
            continue
        try:
            model = _parse_ontology_from_source(it)
        except Exception as e:
            print(f"[Onto3D] Error loading ontology '{it.name}': {e}")
            continue
        ONTO_REG[slug] = {
            "name": model["name"],
            "prefix": model["prefix"],
            "entities": list(model.get("entities", [])),
            "properties": list(model.get("properties", [])),
        }

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
            ent_items.append(NodeItem(
                ENTITY_NODE_ID,
                label=f"[{pre}] {elab}",
                settings={
                    "onto3d_ontology": repr(slug),
                    "onto3d_entity_id": repr(eid),
                }
            ))
        for pid, plab, ns in data["properties"]:
            prop_items.append(NodeItem(
                PROPERTY_NODE_ID,
                label=f"[{pre}] {plab}",
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

    # "All"
    all_ent, all_prop = [], []
    for slug, data in ONTO_REG.items():
        pre = data["prefix"]
        for eid, elab, ns in data["entities"]:
            all_ent.append(NodeItem(ENTITY_NODE_ID, label=f"[{pre}] {elab}", settings={
                "onto3d_ontology": repr(slug), "onto3d_entity_id": repr(eid)
            }))
        for pid, plab, ns in data["properties"]:
            all_prop.append(NodeItem(PROPERTY_NODE_ID,
                label=f"[{pre}] {plab}",
                settings={"onto3d_ontology": repr(slug), "onto3d_property_id": repr(pid)}
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
# Ensure node properties exist on your node classes
# =========================
def _ensure_node_props():
    # This does NOT create your nodes. It only ensures the props exist.
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
# Load from prefs on startup
# =========================
def _load_from_prefs_and_build():
    prefs = bpy.context.preferences.addons[__package__ if __package__ else __name__].preferences
    _load_enabled_ontologies(prefs)
    _rebuild_node_categories()

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
)
