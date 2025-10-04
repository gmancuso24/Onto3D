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
    "version": (0, 4, 4),
    "blender": (4, 5, 2),
    "location": "Node Editor > N-Panel (Onto3D)",
    "description": "Manage and create an ontological graph in Blender's node editor and connect it to geometry data.",
    "category": "Node",
}

# ------------------------------------------------------------
# Onto3D — Graph nodes with RDF importer + presets
# ------------------------------------------------------------
import bpy
from bpy.types import NodeTree, Node, NodeSocket
from nodeitems_utils import NodeCategory, NodeItem, register_node_categories, unregister_node_categories
import os, json, ast
from collections import defaultdict
import uuid


# -------------------------
# Lazy import rdflib (works even if installed after)
# -------------------------
def _import_rdflib():
    import importlib
    rdflib = importlib.import_module('rdflib')
    ns = importlib.import_module('rdflib.namespace')
    RDF, RDFS, OWL, SKOS = ns.RDF, ns.RDFS, ns.OWL, ns.SKOS
    return rdflib, RDF, RDFS, OWL, SKOS

# -------------------------
# Helpers + in-memory store
# -------------------------
def _last_fragment(iri: str) -> str:
    if not iri: return ""
    s = iri.rsplit("#", 1)
    if len(s) == 2 and s[1]: return s[1]
    s = iri.rstrip("/").rsplit("/", 1)
    return s[1] if len(s) == 2 else iri

def _nice_label(g, node):
    # ensure namespaces locally (avoid NameError)
    _rdflib, RDF, RDFS, OWL, SKOS = _import_rdflib()
    for p in (RDFS.label, SKOS.prefLabel):
        for o in g.objects(node, p):
            return str(o)
    return _last_fragment(str(node))

class OntologyStore:
    """data = { ns_key: {base:str, classes:[{iri,code,label}], properties:[{iri,code,label,domain,range}] } }"""
    def __init__(self):
        self.data = {}
        self.default_ns = None

    def clear(self): self.data = {}
    def namespaces(self): return list(self.data.keys())
    def ensure_ns(self, ns_key, base_iri=""):
        if ns_key not in self.data:
            self.data[ns_key] = {"base": base_iri, "classes": [], "properties": []}
    def add_class(self, ns_key, iri, label):
        self.data[ns_key]["classes"].append({"iri": iri, "code": _last_fragment(iri), "label": label})
    def add_property(self, ns_key, iri, label, domain=None, range_=None):
        self.data[ns_key]["properties"].append({
            "iri": iri, "code": _last_fragment(iri), "label": label,
            "domain": domain or [], "range": range_ or []
        })
    def enum_classes(self):
        items = [("__custom__", "<Custom class>", "")]
        for ns_key, blob in self.data.items():
            for c in blob["classes"]:
                items.append((c["code"], f"{c['label']}  [{ns_key}]", c["code"]))
        return items
    def enum_properties(self):
        items = [("__custom__", "<Custom property>", "")]
        for ns_key, blob in self.data.items():
            for p in blob["properties"]:
                items.append((p["code"], f"{p['label']}  [{ns_key}]", p["code"]))
        return items

STORE = OntologyStore()

def import_rdf_to_store(filepath, ns_hint=None):
    rdflib, RDF, RDFS, OWL, SKOS = _import_rdflib()
    g = rdflib.Graph(); g.parse(filepath)

    ns_key = ns_hint or os.path.splitext(os.path.basename(filepath))[0]

    # try to select a meaningful base IRI
    base_iri = ""
    for prefix, ns in g.namespaces():
        if prefix.lower() in ("crm", "cidoc", "cidoc_crm"):
            base_iri = str(ns); break
    if not base_iri:
        for o in g.subjects(RDF.type, OWL.Ontology):
            base_iri = str(o); break
    if not base_iri:
        for prefix, ns in g.namespaces():
            if prefix not in ("owl","rdfs","xml","xsd","rdf"):
                base_iri = str(ns); break

    STORE.ensure_ns(ns_key, base_iri)

    # classes (rdfs:Class + owl:Class)
    seen = set()
    for t in (RDFS.Class, OWL.Class):
        for cls in g.subjects(RDF.type, t):
            iri = str(cls)
            if iri in seen: continue
            seen.add(iri)
            STORE.add_class(ns_key, iri, _nice_label(g, cls))

    # properties
    seenp = set()
    for t in (RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty):
        for p in g.subjects(RDF.type, t):
            iri = str(p)
            if iri in seenp: continue
            seenp.add(iri)
            dom = [str(o) for o in g.objects(p, RDFS.domain)]
            rng = [str(o) for o in g.objects(p, RDFS.range)]
            STORE.add_property(ns_key, iri, _nice_label(g, p), dom, rng)

    return ns_key

def rebuild_dynamic_enums_and_menus():
    for area in __onto3d_tag_node_editors() or []:
        if area.type == 'NODE_EDITOR':
            area.tag_redraw()

# Enum providers (fallback to demo lists if store is empty)
def dynamic_class_items(self, context):
    items = STORE.enum_classes()
    if len(items) == 1:
        items += [(c, l, "") for c,l,_ in CRM_ENTITIES]
        items += [(c, l, "") for c,l,_ in CRA_ENTITIES]
        items += [(c, l, "") for c,l,_ in CRMSCI_ENTITIES]
    return items

def dynamic_property_items(self, context):
    items = STORE.enum_properties()
    if len(items) == 1:
        items += [(c, l, "") for c,l,_ in CRM_PROPERTIES]
    return items

# <-- add this dynamic provider for namespaces
def dynamic_namespace_items(self, context):
    # always include an empty option as the first item so the default "" remains valid
    items = [("", "(none)", "")]
    items += [(k, k, "") for k in STORE.namespaces()]
    if len(items) == 1:
        # fallback to demo namespaces when no ontologies have been imported
        items += [('crm','CIDOC CRM',''),('cra','CRMarchaeo',''),('crmsci','CRMsci','')]
    return items

# -------------------------
# Dynamic Add-Menu Presets (filtered)
# -------------------------
_DYNAMIC_ENTITY_ITEMS = []
_DYNAMIC_PROPERTY_ITEMS = []
# map namespace -> (ents, props) to persist presets per-namespace and avoid overwrite
_PRESET_MAP = {}

def _make_nodeitem_entity(label, class_code, namespace):
    return NodeItem("ONTO3DEntityNodeType", label=label,
                    settings={"class_code": repr(class_code), "namespace": repr(namespace)})

def _make_nodeitem_property(label, prop_code, namespace):
    return NodeItem("ONTO3DPropertyNodeType", label=label,
                    settings={"prop_code": repr(prop_code), "namespace": repr(namespace)})

def build_preset_items(filter_text="", namespaces=None, limit_per_kind=200):
    ft = (filter_text or "").strip().lower()
    nsset = set(namespaces) if namespaces else None
    ents, props = [], []

    # entities
    for ns_key, blob in STORE.data.items():
        if nsset and ns_key not in nsset: continue
        for c in blob["classes"]:
            if ft and (ft not in c["code"].lower() and ft not in c["label"].lower()): continue
            ents.append(_make_nodeitem_entity(f"{c['label']} [{ns_key}]", c["code"], ns_key))
            if len(ents) >= limit_per_kind: break
        if len(ents) >= limit_per_kind: break

    # properties
    for ns_key, blob in STORE.data.items():
        if nsset and ns_key not in nsset: continue
        for p in blob["properties"]:
            if ft and (ft not in p["code"].lower() and ft not in p["label"].lower()): continue
            props.append(_make_nodeitem_property(f"{p['label']} [{ns_key}]", p["code"], ns_key))
            if len(props) >= limit_per_kind: break
        if len(props) >= limit_per_kind: break

    return ents, props

def rebuild_node_categories_with_presets(entity_items, property_items):
    """
    Build one pair of categories per namespace found in the provided NodeItem lists.
    If both lists are empty, register an empty Add menu so the Add menu is blank.
    """
    global _DYNAMIC_ENTITY_ITEMS, _DYNAMIC_PROPERTY_ITEMS, node_categories
    _DYNAMIC_ENTITY_ITEMS = entity_items
    _DYNAMIC_PROPERTY_ITEMS = property_items

    # group items by namespace (namespace is stored in item.settings["namespace"] as repr(ns))
    ents_by_ns = defaultdict(list)
    props_by_ns = defaultdict(list)

    def _ns_from_item(item):
        ns = None
        try:
            if hasattr(item, "settings") and isinstance(item.settings, dict):
                nsval = item.settings.get("namespace")
                if nsval is not None:
                    try:
                        ns = ast.literal_eval(nsval)
                    except Exception:
                        ns = str(nsval).strip("'\"")
        except Exception:
            ns = None
        return ns or ""

    for it in _DYNAMIC_ENTITY_ITEMS:
        ns = _ns_from_item(it)
        ents_by_ns[ns].append(it)
    for it in _DYNAMIC_PROPERTY_ITEMS:
        ns = _ns_from_item(it)
        props_by_ns[ns].append(it)

    # build categories: one "NS - Entities" and one "NS - Properties" for each namespace that has items
    base = []
    # keep namespaces order consistent with STORE if possible
    ns_order = list(STORE.data.keys())
    # ensure namespaces present in items are included
    for ns in list(ents_by_ns.keys()) + list(props_by_ns.keys()):
        if ns and ns not in ns_order: ns_order.append(ns)

    for ns in ns_order:
        eitems = ents_by_ns.get(ns, [])
        pitems = props_by_ns.get(ns, [])
        if eitems:
            base.append(NodeCategory(f"ONTO3D_{ns}_ENT", f"{ns} - Entities", items=eitems))
        if pitems:
            base.append(NodeCategory(f"ONTO3D_{ns}_PROP", f"{ns} - Properties", items=pitems))

    # if still empty, register an empty menu so Add is blank
    try:
        unregister_node_categories("ONTO3D_NODES_CAT")
    except Exception:
        pass
    register_node_categories("ONTO3D_NODES_CAT", base)
    rebuild_dynamic_enums_and_menus()

# ---- helpers to merge NodeItem lists without duplicates ----
def _nodeitem_unique_key(item):
    try:
        lbl = str(getattr(item, "label", ""))
        settings = getattr(item, "settings", {}) or {}
        ns = settings.get("namespace", "")
        cls = settings.get("class_code", settings.get("prop_code", ""))
        return (lbl, str(ns), str(cls))
    except Exception:
        return (str(getattr(item, "label", "")), "", "")

def _merge_nodeitem_lists(existing, new_items):
    seen = set(_nodeitem_unique_key(i) for i in existing)
    out = list(existing)
    for it in new_items:
        k = _nodeitem_unique_key(it)
        if k not in seen:
            out.append(it); seen.add(k)
    return out

# Scene props for UI state (Blocco B1)
def _ensure_scene_props():
    sc = bpy.types.Scene
    if not hasattr(sc, "onto3d_filter_text"):
        sc.onto3d_filter_text = bpy.props.StringProperty(
            name="Filter", description="Filtro testo per codice/label", default="")
    if not hasattr(sc, "onto3d_limit"):
        sc.onto3d_limit = bpy.props.IntProperty(
            name="Max items", description="Limite voci per Entities/Properties",
            default=200, min=10, max=5000)
    if not hasattr(sc, "onto3d_ns_enum"):
        sc.onto3d_ns_enum = bpy.props.EnumProperty(
            name="Namespaces",
            description="Select the namespaces to include",
            items=lambda self, ctx: [("", "(none)", "")] + [(k, k, "") for k in STORE.data.keys()],
            options={'ENUM_FLAG'}
        )
_ensure_scene_props()

# -------------------------
# Sockets
# -------------------------
class ONTO3DInSocket(NodeSocket):
    bl_idname = "ONTO3DInSocket"; bl_label = "In"
    def draw(self, ctx, layout, node, text): layout.label(text=text) if text else None
    def draw_color(self, ctx, node): return (0.20, 0.60, 1.00, 1.0)

class ONTO3DOutSocket(NodeSocket):
    bl_idname = "ONTO3DOutSocket"; bl_label = "Out"
    def draw(self, ctx, layout, node, text): layout.label(text=text) if text else None
    def draw_color(self, ctx, node): return (0.20, 0.60, 1.00, 1.0)

# -------------------------
# NodeTree
# -------------------------
class ONTO3DGraphTree(NodeTree):
    bl_idname = "ONTO3DGraphTreeType"; bl_label = "Onto3D"; bl_icon = 'NODETREE'

# -------------------------
# Entity Node
# -------------------------
class ONTO3DEntityNode(Node):
    bl_idname = "ONTO3DEntityNodeType"; bl_label = "Onto3D Entity"; bl_icon = 'OBJECT_DATA'

    def _dedupe_ports(self):
        def _do(side):
            seen=set(); rm=[]
            for s in side:
                k=(s.bl_idname, s.name)
                if k in seen: rm.append(s)
                else: seen.add(k)
            for s in rm: side.remove(s)
        _do(self.inputs); _do(self.outputs)

    def _on_title(self, ctx): self.label = self.title if self.title.strip() else self.bl_label

    title: bpy.props.StringProperty(name="Title", default="", update=_on_title)
    iri: bpy.props.StringProperty(name="IRI", default="")
    # replace the static EnumProperty with the dynamic provider
    namespace: bpy.props.StringProperty(name="Namespace", default="")
    class_code: bpy.props.EnumProperty(
        name="Class",
        items=dynamic_class_items,
        description="Imported classes (or demo list if none loaded)"
    )
    class_custom: bpy.props.StringProperty(name="Custom Class", default="")
    is_valid: bpy.props.BoolProperty(name="Valid", default=True)

    def init(self, ctx):
        while self.inputs: self.inputs.remove(self.inputs[0])
        while self.outputs: self.outputs.remove(self.outputs[0])
        self.inputs.new("ONTO3DInSocket", "in (property)")
        self.outputs.new("ONTO3DOutSocket", "out (property)")
        self._dedupe_ports(); self.label = self.bl_label

    def draw_buttons(self, ctx, layout):
        self._dedupe_ports()
        # editable metadata (kept as before)
        layout.prop(self, "title", text="Title")
        layout.prop(self, "class_code", text="Class")
        if self.class_code == "__custom__": layout.prop(self, "class_custom", text="Custom")
        row = layout.row(align=True); row.prop(self, "namespace", text="Namespace")
              # IRI + pulsante "open"
        row_iri = layout.row(align=True)
        row_iri.prop(self, "iri", text="IRI")
        op_open = row_iri.operator("onto3d.open_iri", text="", icon='URL')
        op_open.iri = self.iri

        if not self.is_valid:
            col = layout.column(); col.alert = True
            col.label(text="Class not recognized — pick from list.")

        # --- Geometry controls restored on the node ---
        row = layout.row(align=True)
        nid = _ensure_node_uuid(self)
        op = row.operator("onto3d.node_zoom_geometry", text="Zoom to geometry", icon='VIEWZOOM')
        op.node_uuid = nid
        op2 = row.operator("onto3d.node_isolate_geometry", text="Isolate geometry", icon='HIDE_OFF')
        op2.node_uuid = nid

    @property
    def effective_class(self):
        return self.class_custom if self.class_code == "__custom__" else (self.class_code or "")

    def update(self):
        known = {c for c,_,_ in CRM_ENTITIES}|{c for c,_,_ in CRA_ENTITIES}|{c for c,_,_ in CRMSCI_ENTITIES}
        if self.class_code == "__custom__": self.is_valid = bool(self.class_custom.strip())
        else:
            self.is_valid = (self.class_code in known) or any(self.class_code == c["code"]
                             for ns in STORE.data.values() for c in ns["classes"])
        self._dedupe_ports()

# -------------------------
# Property Node
# -------------------------
class ONTO3DPropertyNode(Node):
    bl_idname = "ONTO3DPropertyNodeType"; bl_label = "Onto3D Property"; bl_icon = 'DOT'

    def _dedupe_ports(self):
        def _do(side):
            seen=set(); rm=[]
            for s in side:
                k=(s.bl_idname, s.name)
                if k in seen: rm.append(s)
                else: seen.add(k)
            for s in rm: side.remove(s)
        _do(self.inputs); _do(self.outputs)

    # replace the static EnumProperty with the dynamic provider
    namespace: bpy.props.StringProperty(name="Namespace", default="")

    def _on_prop_change(self, ctx): self.label = self.effective_property or self.bl_label
    prop_code: bpy.props.EnumProperty(name="Property", items=dynamic_property_items,
        description="Imported properties (or demo)", update=_on_prop_change)
    prop_custom: bpy.props.StringProperty(name="Custom Property", default="", update=_on_prop_change)

    def init(self, ctx):
        while self.inputs: self.inputs.remove(self.inputs[0])
        while self.outputs: self.outputs.remove(self.outputs[0])
        self.inputs.new("ONTO3DInSocket", "subject")
        self.outputs.new("ONTO3DOutSocket", "object")
        self._dedupe_ports(); self.label = self.bl_label

    def draw_buttons(self, ctx, layout):
        self._dedupe_ports()
        # editable selections (kept)
        layout.prop(self, "prop_code", text="Property")
        if self.prop_code == "__custom__": layout.prop(self, "prop_custom", text="Custom")
        layout.prop(self, "namespace", text="Namespace")
                # If the node has an IRI property, show it with "open" button
        iri_val = self.get("iri", "")
        if iri_val:
            row_iri = layout.row(align=True)
            row_iri.label(text=f"IRI: {iri_val}")
            op_open = row_iri.operator("onto3d.open_iri", text="", icon='URL')
            op_open.iri = iri_val


        # --- Geometry controls restored on the node ---
        row = layout.row(align=True)
        nid = _ensure_node_uuid(self)
        op = row.operator("onto3d.node_zoom_geometry", text="Zoom to geometry", icon='VIEWZOOM')
        op.node_uuid = nid
        op2 = row.operator("onto3d.node_isolate_geometry", text="Isolate geometry", icon='HIDE_OFF')
        op2.node_uuid = nid

    def _on_prop_change(self, ctx): self.label = self.effective_property or self.bl_label
    prop_code: bpy.props.EnumProperty(name="Property", items=dynamic_property_items,
        description="Proprietà importate (o demo)", update=_on_prop_change)
    prop_custom: bpy.props.StringProperty(name="Custom Property", default="", update=_on_prop_change)

    def init(self, ctx):
        while self.inputs: self.inputs.remove(self.inputs[0])
        while self.outputs: self.outputs.remove(self.outputs[0])
        self.inputs.new("ONTO3DInSocket", "subject")
        self.outputs.new("ONTO3DOutSocket", "object")
        self._dedupe_ports(); self.label = self.bl_label

    def draw_buttons(self, ctx, layout):
        self._dedupe_ports()
        # editable selections (kept)
        layout.prop(self, "prop_code", text="Property")
        if self.prop_code == "__custom__": layout.prop(self, "prop_custom", text="Custom")
        layout.prop(self, "namespace", text="Namespace")

        # --- Geometry controls restored on the node ---
        row = layout.row(align=True)
        nid = _ensure_node_uuid(self)
        op = row.operator("onto3d.node_zoom_geometry", text="Zoom to geometry", icon='VIEWZOOM')
        op.node_uuid = nid
        op2 = row.operator("onto3d.node_isolate_geometry", text="Isolate geometry", icon='HIDE_OFF')
        op2.node_uuid = nid

        # --- Item panel: show non-editable metadata and "Zoom to node" button
        box = layout.box()
        box.label(text="Node metadata", icon='INFO')
        box.label(text=f"Title: {self.label or self.bl_label}")
        box.label(text=f"Property: {self.effective_property or '(none)'}")
        box.label(text=f"Namespace: {self.namespace or '(none)'}")
        # le property node possono non avere IRI; mostro comunque la proprietà iri se presente
        box.label(text=f"IRI: {self.get('iri','(none)')}")
        row = box.row(align=True)
        nid = _ensure_node_uuid(self)
        op = row.operator("onto3d.node_zoom_node", text="Zoom to node", icon='VIEWZOOM')
        op.node_uuid = nid

    @property
    def effective_property(self):
        return self.prop_custom if self.prop_code == "__custom__" else (self.prop_code or "")

# -------------------------
# Menus (base + generic)
# -------------------------
# Remove demo/test preset entries so the Add menu stays empty until user generates presets
ENTITY_MENU_ITEMS = [
]
PROPERTY_MENU_ITEMS = [
    ]

# initial categories — start empty so Add menu is blank until user generates presets/imports
node_categories = [
]

# -------------------------
# UI Panel & Operators
# -------------------------
class ONTO3D_PT_OntologiesPanel(bpy.types.Panel):
    bl_idname = "ONTO3D_PT_OntologiesPanel"
    bl_label = "Import Ontologies"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Onto3D"

    def draw(self, context):
        layout = self.layout
        sc = context.scene

        col = layout.column(align=True)
        col.operator("onto3d.import_ontology", icon='IMPORT')
        # reload button removed

        if not STORE.data:
            col.label(text="No ontologies loaded.")
            return

        col.label(text="Loaded namespaces:")
        for ns_key, blob in STORE.data.items():
            box = col.box()
            box.label(text=f"{ns_key}  (base: {blob.get('base','')})")
            row = box.row(align=True)
            row.label(text=f"Classes: {len(blob['classes'])}")
            row.label(text=f"Properties: {len(blob['properties'])}")
            row2 = box.row(align=True)
            row2.operator("onto3d.export_namespace", text="Export JSON").ns_key = ns_key
            row2.operator("onto3d.remove_namespace", text="Remove").ns_key = ns_key

        layout.separator()
        box = layout.box()
        box.label(text="Select Imported Ontology")
        # removed the filter and max limit: Generate will load all selected entities/properties
        box.prop(sc, "onto3d_ns_enum", text="Namespaces")
        rowb = box.row(align=True)
        rowb.operator("onto3d.generate_presets", icon='PLUS')
        rowb.operator("onto3d.clear_presets", icon='TRASH')

class ONTO3D_OT_ExportNamespace(bpy.types.Operator):
    bl_idname = "onto3d.export_namespace"; bl_label = "Export Namespace JSON"
    ns_key: bpy.props.StringProperty()
    def execute(self, context):
        if self.ns_key not in STORE.data:
            self.report({'ERROR'}, "Namespace not found"); return {'CANCELLED'}
        outdir = bpy.path.abspath("//ontologies_cache"); os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, f"{self.ns_key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(STORE.data[self.ns_key], f, ensure_ascii=False, indent=2)
        self.report({'INFO'}, f"Exported: {path}"); return {'FINISHED'}

class ONTO3D_OT_RemoveNamespace(bpy.types.Operator):
    bl_idname = "onto3d.remove_namespace"; bl_label = "Remove Namespace"
    ns_key: bpy.props.StringProperty()
    def execute(self, context):
        if self.ns_key in STORE.data:
            del STORE.data[self.ns_key]
            # also remove any stored presets for that namespace
            try:
                _PRESET_MAP.pop(self.ns_key, None)
            except Exception:
                pass
            # rebuild presets for the remaining namespaces (keep others)
            # recompute merged lists from _PRESET_MAP (fall back to building from STORE)
            all_ents = []
            all_props = []
            if _PRESET_MAP:
                for e,p in _PRESET_MAP.values():
                    all_ents = _merge_nodeitem_lists(all_ents, e)
                    all_props = _merge_nodeitem_lists(all_props, p)
            else:
                # fallback: build fresh from STORE
                remaining = tuple(STORE.namespaces()) if STORE.namespaces() else None
                total_ents = sum(len(STORE.data[ns]['classes']) for ns in STORE.data) if STORE.data else 0
                total_props = sum(len(STORE.data[ns]['properties']) for ns in STORE.data) if STORE.data else 0
                if total_ents == 0 and total_props == 0:
                    all_ents, all_props = [], []
                else:
                    all_ents, all_props = build_preset_items(filter_text="", namespaces=remaining, limit_per_kind=max(total_ents, total_props, 0))
            rebuild_node_categories_with_presets(all_ents, all_props)
            self.report({'INFO'}, f"Namespace removed:'{self.ns_key}'")
        else:
            self.report({'WARNING'}, "Namespace not found")
        return {'FINISHED'}

class ONTO3D_OT_ImportOntology(bpy.types.Operator):
    bl_idname = "onto3d.import_ontology"; bl_label = "Import RDFS/RDF/OWL"
    bl_description = "Import ontology from local file and populate the store"
    filter_glob: bpy.props.StringProperty(default="*.rdf;*.rdfs;*.owl;*.ttl;*.xml", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    ns_hint: bpy.props.StringProperty(name="Namespace key (opzionale)", default="")
    def execute(self, context):
        try:
            ns = import_rdf_to_store(self.filepath, self.ns_hint or None)
            rebuild_dynamic_enums_and_menus()
            # generate Add-menu presets automatically for the newly imported namespace
            ents, props = build_preset_items(filter_text="", namespaces=(ns,), limit_per_kind=200)
            # store presets per-namespace and rebuild the global merged menu
            global _DYNAMIC_ENTITY_ITEMS, _DYNAMIC_PROPERTY_ITEMS, _PRESET_MAP
            _PRESET_MAP[ns] = (ents, props)
            merged_ents = []
            merged_props = []
            for e,p in _PRESET_MAP.values():
                merged_ents = _merge_nodeitem_lists(merged_ents, e)
                merged_props = _merge_nodeitem_lists(merged_props, p)
            rebuild_node_categories_with_presets(merged_ents, merged_props)
            self.report({'INFO'}, f"Import: '{ns}' "
                                  f"({len(STORE.data[ns]['classes'])} classes, {len(STORE.data[ns]['properties'])} properties)")
        except Exception as e:
            self.report({'ERROR'}, f"Import fallito: {e}"); return {'CANCELLED'}
        return {'FINISHED'}
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self); return {'RUNNING_MODAL'}

class ONTO3D_OT_GeneratePresets(bpy.types.Operator):
    bl_idname = "onto3d.generate_presets"; bl_label = "Add Nodes"
    bl_description = "Generate presets for the selected namespaces"
    def execute(self, context):
        sc = context.scene
        selected_ns = tuple(sc.onto3d_ns_enum) if sc.onto3d_ns_enum else None
        # compute the total number of entities/properties for the selected namespaces (or all)
        if selected_ns:
            total_ents = sum(len(STORE.data[ns]['classes']) for ns in selected_ns if ns in STORE.data)
            total_props = sum(len(STORE.data[ns]['properties']) for ns in selected_ns if ns in STORE.data)
        else:
            total_ents = sum(len(blob['classes']) for blob in STORE.data.values())
            total_props = sum(len(blob['properties']) for blob in STORE.data.values())
        limit = max(total_ents, total_props, 0)
        if limit == 0:
            rebuild_node_categories_with_presets([], [])
            self.report({'INFO'}, "No entities/properties found for the selected namespaces.")
            return {'FINISHED'}
        # generate all items without filtering
        ents, props = build_preset_items(
            filter_text="",
            namespaces=selected_ns,
            limit_per_kind=limit
        )
        # when user explicitly generates presets replace the current menu with the selection
        rebuild_node_categories_with_presets(ents, props)
        self.report({'INFO'}, f"Generated {len(ents)} entities, {len(props)} properties.")
        return {'FINISHED'}

class ONTO3D_OT_ClearPresets(bpy.types.Operator):
    bl_idname = "onto3d.clear_presets"; bl_label = "Clear Nodes"
    bl_description = "Clear all Add-menu presets"
    def execute(self, context):
        rebuild_node_categories_with_presets([], [])
        self.report({'INFO'}, "Cleared ONTO3D Add-menu presets.")
        return {'FINISHED'}

class ONTO3D_OT_ReloadAddon(bpy.types.Operator):
    """Reload the Onto3D addon from disk (for development purposes)."""
    bl_idname = "onto3d.reload_addon"
    bl_label = "Reload Onto3D Addon"

    def execute(self, context):
        import importlib, sys
        addon_name = __name__
        if addon_name in sys.modules:
            importlib.reload(sys.modules[addon_name])
        else:
            importlib.import_module(addon_name)
        self.report({'INFO'}, "Onto3D ricaricato")
        return {'FINISHED'}

# ================================
# Onto3D – Connect Geometry Panel
# ================================
# connect nodes and geometry in the schene
GEOM_TYPES = {
    'MESH','CURVE','SURFACE','META','FONT','VOLUME','GPENCIL','POINTCLOUD','CURVES'
}
def _iter_geom_under(obj):
    out = []
    if obj.type in GEOM_TYPES:
        out.append(obj)
    elif obj.type == 'EMPTY':
        for ch in obj.children_recursive:
            if ch.type in GEOM_TYPES:
                out.append(ch)
    return out

def _gather_selected_geometry(context):
    objs = set()
    for o in context.selected_objects:
        for g in _iter_geom_under(o):
            objs.add(g)
    return sorted(objs, key=lambda x: x.name)

def _find_active_node(context):
    space = getattr(context, "space_data", None)
    if space and getattr(space, "type", "") == 'NODE_EDITOR':
        nt = space.edit_tree or space.node_tree
        if nt and nt.nodes and nt.nodes.active:
            return nt.nodes.active
    for area in context.window.screen.areas:
        if area.type == 'NODE_EDITOR':
            for space in area.spaces:
                if space.type == 'NODE_EDITOR':
                    nt = space.edit_tree or space.node_tree
                    if nt and nt.nodes and nt.nodes.active:
                        return nt.nodes.active
    return None

def _ensure_node_uuid(node):
    if "onto3d_uuid" not in node:
        node["onto3d_uuid"] = str(uuid.uuid4())
    return node["onto3d_uuid"]

def _node_add_link(node, obj):
    node_links = set(node.get("onto3d_linked_objects", []))
    obj_links  = set(obj.get("onto3d_linked_nodes", []))
    nid = _ensure_node_uuid(node)
    node_links.add(obj.name)
    obj_links.add(nid)
    node["onto3d_linked_objects"] = list(sorted(node_links))
    obj["onto3d_linked_nodes"] = list(sorted(obj_links))

def _node_remove_link(node, obj):
    nid = node.get("onto3d_uuid")
    if not nid:
        return
    if "onto3d_linked_objects" in node:
        lst = [n for n in node["onto3d_linked_objects"] if n != obj.name]
        node["onto3d_linked_objects"] = lst
    if "onto3d_linked_nodes" in obj:
        lst = [n for n in obj["onto3d_linked_nodes"] if n != nid]
        obj["onto3d_linked_nodes"] = lst

def _remove_all_links_for_node(node):
    nid = node.get("onto3d_uuid")
    if not nid:
        return 0
    count = 0
    for oname in list(node.get("onto3d_linked_objects", [])):
        o = bpy.data.objects.get(oname)
        if o:
            if "onto3d_linked_nodes" in o:
                o["onto3d_linked_nodes"] = [n for n in o["onto3d_linked_nodes"] if n != nid]
            count += 1
    node["onto3d_linked_objects"] = []
    return count

class ONTO3D_OT_CreateConnection(bpy.types.Operator):
    """Connects the active geometry to the active node."""
    bl_idname = "onto3d.create_connection"
    bl_label = "Create"
    bl_options = {'UNDO'}

    def execute(self, context):
        node = _find_active_node(context)
        if not node:
            self.report({'ERROR'}, "No active node.")
            return {'CANCELLED'}
        geoms = _gather_selected_geometry(context)
        if not geoms:
            self.report({'ERROR'}, "Select one or more geometries (or an Empty with child geometries).")
            return {'CANCELLED'}
        created = 0
        for g in geoms:
            _node_add_link(node, g)
            created += 1
        self.report({'INFO'}, f"{node.name} connected to {created}”.")
        return {'FINISHED'}
    
class ONTO3D_OT_OpenIRI(bpy.types.Operator):
    """Open the IRI in the default browser (new tab)."""
    bl_idname = "onto3d.open_iri"
    bl_label = "Open in Web Browser"

    iri: bpy.props.StringProperty(name="IRI", default="")

    def execute(self, context):
        url = (self.iri or "").strip()
        if not url:
            self.report({'ERROR'}, "IRI mancante.")
            return {'CANCELLED'}
        try:
            import re, webbrowser
            # If the URL scheme is missing, try prepending "https://" for cases like 'www.example.org'
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', url):
                if url.startswith("www."):
                    url = "https://" + url
            webbrowser.open_new_tab(url)
            self.report({'INFO'}, "Opened in default browser.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unable to open IRI: {e}")
            return {'CANCELLED'}


class ONTO3D_OT_BreakConnection(bpy.types.Operator):
    """Disconnect the selected geometry from the active node.
    If no geometry is selected, remove ALL links from the node (with confirmation)."""
    bl_idname = "onto3d.break_connection"
    bl_label = "Break"
    bl_options = {'UNDO'}

    remove_all: bpy.props.BoolProperty(
        name="Remove all from node",
        description="In no geometry has been selected, removes all links from the active node",
        default=False
    )

    def invoke(self, context, event):
        geoms = _gather_selected_geometry(context)
        if not geoms:
            self.remove_all = True
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        node = _find_active_node(context)
        if not node:
            self.report({'ERROR'}, "No active node found.")
            return {'CANCELLED'}
        geoms = _gather_selected_geometry(context)
        if geoms:
            removed = 0
            for g in geoms:
                if "onto3d_uuid" in node and "onto3d_linked_nodes" in g and node["onto3d_uuid"] in g["onto3d_linked_nodes"]:
                    _node_remove_link(node, g)
                    removed += 1
            self.report({'INFO'}, f"Disconnected {removed} geometries from node “{node.name}”.")
            return {'FINISHED'}
        if self.remove_all:
            n = _remove_all_links_for_node(node)
            self.report({'INFO'}, f"Removed {n} connections from node “{node.name}”.")
            return {'FINISHED'}
        self.report({'INFO'}, "No geometry selected. No action taken.")
        return {'CANCELLED'}

class ONTO3D_OT_UpdateConnections(bpy.types.Operator):
    """Update the active node's connections (handles renames and deletions)."""
    bl_idname = "onto3d.update_connections"
    bl_label = "Update"
    bl_options = {'UNDO'}

    def execute(self, context):
        node = _find_active_node(context)
        if not node:
            self.report({'ERROR'}, "No active node found in an open Node Editor.")
            return {'CANCELLED'}
        nid = node.get("onto3d_uuid") or _ensure_node_uuid(node)

        # rebuild the list of objects that actually reference this node_uuid
        objs_with_ref = [o for o in bpy.data.objects if nid in o.get("onto3d_linked_nodes", [])]
        new_links = sorted(o.name for o in objs_with_ref)
        old_links = list(node.get("onto3d_linked_objects", []))

        added = len([n for n in new_links if n not in old_links])
        removed = len([n for n in old_links if n not in new_links])

        node["onto3d_linked_objects"] = new_links

        # sync object side: add/remove nid where needed
        for o in bpy.data.objects:
            lst = list(o.get("onto3d_linked_nodes", []))
            if o.name in new_links:
                if nid not in lst:
                    lst.append(nid); o["onto3d_linked_nodes"] = sorted(lst)
            else:
                if nid in lst:
                    o["onto3d_linked_nodes"] = [x for x in lst if x != nid]

        self.report({'INFO'}, f"Connections updated: +{added} -{removed}")
        return {'FINISHED'}

# ================================
# === SYNC VIEWS + VIEW HELPERS ===
# ================================
def _iter_areas(area_type):
    for area in bpy.context.window.screen.areas:
        if area.type == area_type:
            yield area

def _run_in_area(area, op_callable):
    reg = None
    for r in area.regions:
        if r.type == 'WINDOW':
            reg = r; break
    space = area.spaces.active
    if not reg or not space:
        return False
    with bpy.context.temp_override(area=area, region=reg, space_data=space):
        return op_callable()

def _activate_node_and_view(node):
    ok = False
    for area in _iter_areas('NODE_EDITOR'):
        def op():
            sp = area.spaces.active
            try:
                # Ensure the correct tree is set
                sp.tree_type = "CIDOCGraphTreeType"
                sp.node_tree = node.id_data
            except Exception:
                pass
            nt = sp.edit_tree or sp.node_tree
            if not nt:
                return False
            for n in nt.nodes:
                n.select = False
            try:
                nt.nodes.active = node
            except Exception:
                pass
            node.select = True
            try:
                bpy.ops.node.view_selected()
            except Exception:
                pass
            return True
        ok = _run_in_area(area, op) or ok
    return ok

def _select_objects_in_view(objs, make_active=True):
    names = {o.name for o in objs if o}
    if not names: return False
    # reset selection
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    active_obj = None
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            o.select_set(True)
            if not active_obj:
                active_obj = o
    if make_active and active_obj:
        bpy.context.view_layer.objects.active = active_obj
    # ping alle view 3D (override minimo)
    any_ok = False
    for area in _iter_areas('VIEW_3D'):
        def op(): return True
        any_ok = _run_in_area(area, op) or any_ok
    return any_ok

def _find_node_by_uuid(node_uuid):
    if not node_uuid: return None
    for ng in bpy.data.node_groups:
        if ng.bl_idname != "ONTO3DGraphTreeType":
            continue
        for n in ng.nodes:
            if n.get("onto3d_uuid") == node_uuid:
                return n
    return None

def _activate_node_by_uuid(node_uuid):
    n = _find_node_by_uuid(node_uuid)
    if n:
        _activate_node_and_view(n)
        return n
    return None

_SYNC_HANDLER = None
_last_sel_uuids = set()
_last_active_node_uuid = None

def _objects_to_node_uuid_set(objects):
    uuids = set()
    for o in objects:
        for nid in o.get("onto3d_linked_nodes", []):
            uuids.add(nid)
    return uuids

def _node_to_linked_objects(node):
    out = []
    for name in node.get("onto3d_linked_objects", []):
        o = bpy.data.objects.get(name)
        if o: out.append(o)
    return out

def _handle_view_to_graph_sync(scene):
    global _last_sel_uuids, _last_active_node_uuid
    # 1) Geometry selection → activate linked node
    sel_objs = [o for o in bpy.context.selected_objects]
    current_uuids = _objects_to_node_uuid_set(sel_objs)
    if current_uuids and current_uuids != _last_sel_uuids:
        target_uuid = next(iter(current_uuids))
        node = _activate_node_by_uuid(target_uuid)
        _last_active_node_uuid = target_uuid if node else None
        _last_sel_uuids = current_uuids

    # 2) Active node → select linked geometries
    node = _find_active_node(bpy.context)
    if node:
        nid = node.get("onto3d_uuid")
        if nid and nid != _last_active_node_uuid:
            objs = _node_to_linked_objects(node)
            if objs:
                _select_objects_in_view(objs, make_active=True)
            _last_active_node_uuid = nid

class ONTO3D_OT_ToggleSyncViews(bpy.types.Operator):
    """Toggle synchronization between Viewport and Graph."""
    bl_idname = "onto3d.toggle_sync_views"
    bl_label = "Sync views"

    def execute(self, context):
        global _SYNC_HANDLER, _last_sel_uuids, _last_active_node_uuid
        wm = context.window_manager
        if not hasattr(wm, "onto3d_sync_views"):
            wm["onto3d_sync_views"] = False

        if wm["onto3d_sync_views"]:
            if _SYNC_HANDLER and _SYNC_HANDLER in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(_SYNC_HANDLER)
            _SYNC_HANDLER = None
            wm["onto3d_sync_views"] = False
            _last_sel_uuids = set()
            _last_active_node_uuid = None
            self.report({'INFO'}, "Sync views: OFF")
        else:
            def _handler(scene):
                try:
                    _handle_view_to_graph_sync(scene)
                except Exception:
                    pass
            bpy.app.handlers.depsgraph_update_post.append(_handler)
            _SYNC_HANDLER = _handler
            wm["onto3d_sync_views"] = True
            self.report({'INFO'}, "Sync views: ON")
        return {'FINISHED'}

class ONTO3D_OT_NodeZoomNode(bpy.types.Operator):
    """Select the node in the Node Editor and center the view (node.view_selected)."""
    bl_idname = "onto3d.node_zoom_node"
    bl_label = "Zoom to node"

    node_uuid: bpy.props.StringProperty(name="Node UUID", default="")

    def execute(self, context):
        n = _find_node_by_uuid(self.node_uuid)
        if not n:
            self.report({'WARNING'}, "Node not found.")
            return {'CANCELLED'}
        ok = _activate_node_and_view(n)
        if ok:
            self.report({'INFO'}, "Node selected and centered in the Node Editor.")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Unable to activate the Node Editor or center the node.")
            return {'CANCELLED'}

class ONTO3D_OT_NodeZoomGeometry(bpy.types.Operator):
    """Frame the geometry/ies linked to the node."""
    bl_idname = "onto3d.node_zoom_geometry"
    bl_label = "Zoom to geometry"

    node_uuid: bpy.props.StringProperty(name="Node UUID", default="")

    def execute(self, context):
        node = _find_node_by_uuid(self.node_uuid)
        if not node:
            self.report({'WARNING'}, "Nodo non trovato.")
            return {'CANCELLED'}
        objs = _node_to_linked_objects(node)
        if not objs:
            self.report({'INFO'}, "Nessuna geometria collegata.")
            return {'CANCELLED'}

        _select_objects_in_view(objs, make_active=True)
        did = False
        for area in _iter_areas('VIEW_3D'):
            def op():
                try:
                    bpy.ops.view3d.view_selected(use_all_regions=False)
                except Exception:
                    pass
                return True
            did = _run_in_area(area, op) or did
        if did:
            self.report({'INFO'}, "Inquadrata la geometria collegata.")
        return {'FINISHED'}

class ONTO3D_OT_NodeIsolateGeometry(bpy.types.Operator):
    """Isolate (Local View) the geometry/ies linked to the node (toggle)."""
    bl_idname = "onto3d.node_isolate_geometry"
    bl_label = "Isolate geometry"

    node_uuid: bpy.props.StringProperty(name="Node UUID", default="")

    def execute(self, context):
        node = _find_node_by_uuid(self.node_uuid)
        if not node:
            self.report({'WARNING'}, "Node not found")
            return {'CANCELLED'}
        objs = _node_to_linked_objects(node)
        if not objs:
            self.report({'INFO'}, "No geometry connected.")
            return {'CANCELLED'}

        _select_objects_in_view(objs, make_active=True)

        did = False
        for area in _iter_areas('VIEW_3D'):
            def op():
                try:
                    bpy.ops.view3d.localview(frame_selected=True)
                except Exception:
                    pass
                return True
            did = _run_in_area(area, op) or did

        if did:
            self.report({'INFO'}, "Local View toggled on/off for linked geometries.")
        return {'FINISHED'}

class ONTO3D_PT_ConnectGeometry(bpy.types.Panel):
    """N-panel section for managing node ↔ geometry links."""
    bl_label = "Connect geometry"
    bl_idname = "ONTO3D_PT_ConnectGeometry"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Onto3D"
 
    def draw(self, context):
        layout = self.layout
        node = _find_active_node(context)
        if node:
            box = layout.box()
            box.label(text=f"Active node: {node.name}", icon='NODE')
            linked = node.get("onto3d_linked_objects", [])
            box.label(text=f"Linked geometries: {len(linked)}")
            if linked:
                col = box.column(align=True)
                preview = linked[:5]
                for name in preview:
                    col.label(text=name, icon='MESH_DATA' if bpy.data.objects.get(name, None) else 'ERROR')
                if len(linked) > 5:
                    col.label(text=f"... (+{len(linked)-5})")
        else:
            layout.label(text="No active node found.", icon='INFO')
        row = layout.row(align=True)
        row.operator("onto3d.create_connection", icon='LINKED')
        row.operator("onto3d.break_connection", icon='UNLINKED')
        row.operator("onto3d.update_connections", icon='FILE_REFRESH')

        # removed Sync views UI from Node Editor panel as requested

        col = layout.column(align=True)
        col.label(text="Usage:", icon='QUESTION')
        col.label(text="1) Select geometries in the 3D View (Empties allowed).")
        col.label(text="2) Activate a node in the Node Editor.")
        col.label(text="3) Press Create or Break.")

# --- rimpiazza la classe ONTO3D_PT_ViewportPanel con il nuovo pannello sotto "Item" ---
class ONTO3D_PT_ItemProperties(bpy.types.Panel):
    """Item N-panel: shows metadata of the node linked to the selected object."""
    bl_label = "Onto3D Properties"
    bl_idname = "ONTO3D_PT_ItemProperties"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if not obj:
            layout.label(text="No active object.")
            return

        linked = obj.get("onto3d_linked_nodes", [])
        if not linked:
            layout.label(text="No node linked to the selected object.")
            return

        nid = linked[0]
        node = _find_node_by_uuid(nid)
        if not node:
            layout.label(text="Linked node not found.")
            return

        box = layout.box()
        if len(linked) > 1:
            box.label(text=f"{len(linked)} linked nodes", icon='NODE')

        title = getattr(node, "title", "") or getattr(node, "label", "") or "(none)"
        cls = getattr(node, "effective_class", None) or getattr(node, "effective_property", None) or "(none)"
        ns = getattr(node, "namespace", "") or "(none)"
        iri = node.get("iri", None) or getattr(node, "iri", "") or "(none)"

        box.label(text=f"Title: {title}")
        box.label(text=f"Class/Property: {cls}")
        box.label(text=f"Namespace: {ns}")
        # IRI in the Item panel + "open" button
        if iri and iri != "(none)":
            row_iri = box.row(align=True)
            row_iri.label(text=f"IRI: {iri}")
            op_open = row_iri.operator("onto3d.open_iri", text="", icon='URL')
            op_open.iri = str(iri)
        else:
            box.label(text=f"IRI: {iri}")

        row = box.row(align=True)
        op = row.operator("onto3d.node_zoom_node", text="Zoom to node", icon='VIEWZOOM')
        op.node_uuid = nid

# Registration: make sure all classes are listed here (add/remove names as needed)
classes = (
    ONTO3DInSocket, ONTO3DOutSocket, ONTO3DGraphTree,
    ONTO3DEntityNode, ONTO3DPropertyNode,
    ONTO3D_PT_OntologiesPanel, ONTO3D_OT_ExportNamespace,
    ONTO3D_OT_RemoveNamespace, ONTO3D_OT_ImportOntology,
    ONTO3D_OT_GeneratePresets, ONTO3D_OT_ClearPresets,
    ONTO3D_OT_ReloadAddon,
    ONTO3D_OT_CreateConnection, ONTO3D_OT_BreakConnection, ONTO3D_PT_ConnectGeometry,
    ONTO3D_OT_UpdateConnections,
    ONTO3D_OT_ToggleSyncViews,
    ONTO3D_OT_NodeZoomGeometry,
    ONTO3D_OT_NodeIsolateGeometry,
    ONTO3D_OT_NodeZoomNode,
    ONTO3D_PT_ItemProperties,
    ONTO3D_OT_OpenIRI,
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass
    # ensure Add menu starts empty
    rebuild_node_categories_with_presets([], [])

def unregister():
    # remove sync handler if active
    global _SYNC_HANDLER
    try:
        if _SYNC_HANDLER and _SYNC_HANDLER in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(_SYNC_HANDLER)
    except Exception:
        pass
    try: unregister_node_categories("ONTO3D_NODES_CAT")
    except Exception: pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

if __name__ == "__main__":
    register()
    # create a sample visible in the "New" menu of the Node Editor (only if it doesn't already exist)
    if "Onto3D Graph 1" not in bpy.data.node_groups:
        tree = bpy.data.node_groups.new("Onto3D Graph 1", "ONTO3DGraphTreeType")
        # optional: add the tree to the current Node Editor area (if open)
        for area in __onto3d_tag_node_editors() or []:
            if area.type == "NODE_EDITOR":
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        space.tree_type = "ONTO3DGraphTreeType"
                        space.node_tree = tree
                        break
                break



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
