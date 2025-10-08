"""
rdf_import.py - Import RDF/Turtle files into Blender Onto3D graph
Supports Protégé-generated ontologies with reasoning results
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty, EnumProperty
from .rdf_utils import (
    ensure_rdflib, install_rdflib_instructions,
    parse_class_uri, parse_property_uri, get_linked_entity_node,
    protege_to_blender_name
)
from .graph_layout import auto_layout_nodes, estimate_graph_complexity


def import_graph_from_ttl(node_tree, filepath: str, merge_mode='replace', auto_layout=True) -> dict:
    """
    Import TTL file into node tree.
    
    Args:
        node_tree: Blender NodeTree to populate
        filepath: Input TTL file path
        merge_mode: 'replace' (clear existing), 'merge' (add to existing), 'update' (update matching)
        auto_layout: Apply automatic layout after import
    
    Returns:
        Dictionary with import statistics
    """
    if not ensure_rdflib():
        raise ImportError("rdflib is required. " + install_rdflib_instructions())
    
    from rdflib import Graph, Namespace, URIRef
    from rdflib.namespace import RDF, RDFS, OWL
    
    # Parse RDF graph
    g = Graph()
    g.parse(filepath, format='turtle')
    
    ONTO3D = Namespace("http://onto3d.local/")
    
    stats = {
        'entities_created': 0,
        'properties_created': 0,
        'entities_updated': 0,
        'entities_skipped': 0,
        'errors': []
    }
    
    # Clear existing nodes if replace mode
    if merge_mode == 'replace':
        for node in list(node_tree.nodes):
            node_tree.nodes.remove(node)
    
    # Track created nodes: URI -> Node
    node_map = {}
    existing_node_map = {}
    
    # In update/merge mode, map existing nodes by their stored URI
    if merge_mode in ('merge', 'update'):
        for node in node_tree.nodes:
            if node.bl_idname == "Onto3DNodeEntity":
                # Reconstruct URI from node's ontology properties
                ontology_slug = getattr(node, "onto3d_ontology", "")
                class_id = getattr(node, "onto3d_entity_id", "")
                
                if ontology_slug and class_id:
                    # Try to resolve the actual URI
                    from .rdf_utils import resolve_class_uri
                    uri = resolve_class_uri(ontology_slug, class_id)
                    if uri:
                        existing_node_map[uri] = node
                    else:
                        # Fallback to onto3d namespace
                        from .rdf_utils import sanitize_node_name
                        safe_name = sanitize_node_name(node.name)
                        uri = str(ONTO3D[safe_name])
                        existing_node_map[uri] = node
    
    # Step 1: Import individuals (entity nodes)
    for subject in g.subjects(RDF.type, None):
        subject_str = str(subject)
        
        # Skip ontology declaration and metadata
        if subject_str.endswith('/ontology'):
            continue
        
        # Get all classes this individual belongs to
        classes = list(g.objects(subject, RDF.type))
        
        # Filter out OWL/RDFS meta-classes
        ontology_classes = [c for c in classes if not str(c).startswith(('http://www.w3.org/2002/07/owl#',
                                                                          'http://www.w3.org/2000/01/rdf-schema#'))]
        
        if not ontology_classes:
            continue
        
        # Use first ontology class found
        class_uri = str(ontology_classes[0])
        ontology_slug, class_id = parse_class_uri(class_uri)
        
        if not ontology_slug or not class_id:
            stats['errors'].append(f"Unknown class: {class_uri}")
            stats['entities_skipped'] += 1
            continue
        
        # Check if node exists (update mode)
        if merge_mode == 'update' and subject_str in existing_node_map:
            node = existing_node_map[subject_str]
            stats['entities_updated'] += 1
        else:
            # Check if we already created this node in this import session
            if subject_str in node_map:
                # Skip duplicates
                continue
            
            # Create new entity node
            node = node_tree.nodes.new("Onto3DNodeEntity")
            stats['entities_created'] += 1
        
        # Set node properties
        node.onto3d_ontology = ontology_slug
        node.onto3d_entity_id = class_id
        
        # MAPPING: label (Protégé, with underscores) -> description (Blender, with spaces)
        label = g.value(subject, RDFS.label)
        if label:
            # Convert underscores to spaces for Blender
            blender_label = protege_to_blender_name(str(label))
            node.onto3d_description = blender_label
        
        # MAPPING: comment (Protégé) -> title (Blender)
        comment = g.value(subject, RDFS.comment)
        if comment:
            node.onto3d_title = str(comment)
        
        # If no comment but we have label, use label as fallback for title
        if not comment and label:
            blender_label = protege_to_blender_name(str(label))
            node.onto3d_title = blender_label
        
        # Set IRI reference (from rdfs:seeAlso)
        see_also = g.value(subject, RDFS.seeAlso)
        if see_also:
            node.onto3d_iri = str(see_also)
        
        # Restore Blender metadata if present
        blender_name = g.value(subject, ONTO3D.blenderNodeName)
        if blender_name and merge_mode == 'replace':
            node.name = str(blender_name)
        
        pos_x = g.value(subject, ONTO3D.positionX)
        pos_y = g.value(subject, ONTO3D.positionY)
        if pos_x and pos_y:
            try:
                node.location = (float(pos_x), float(pos_y))
            except (ValueError, TypeError):
                pass
        
        # Store in map
        node_map[subject_str] = node
    
    # Step 2: Import relationships (property nodes)
    # Collect all predicates that aren't metadata
    skip_predicates = {
        str(RDF.type), str(RDFS.label), str(RDFS.comment), str(RDFS.seeAlso),
        str(ONTO3D.blenderNodeName), str(ONTO3D.positionX), str(ONTO3D.positionY),
        str(ONTO3D.inferredRelation)
    }
    
    created_relations = set()  # Track (subject, predicate, object) to avoid duplicates
    
    for subject, predicate, obj in g:
        pred_str = str(predicate)
        
        if pred_str in skip_predicates:
            continue
        
        # Only process object properties (not datatype properties)
        if not isinstance(obj, URIRef):
            continue
        
        subject_str = str(subject)
        object_str = str(obj)
        
        # Check if both nodes exist
        if subject_str not in node_map or object_str not in node_map:
            continue
        
        # Parse property URI
        ontology_slug, property_id = parse_property_uri(pred_str)
        if not ontology_slug or not property_id:
            stats['errors'].append(f"Unknown property: {pred_str}")
            continue
        
        # Avoid duplicate relations
        relation_key = (subject_str, pred_str, object_str)
        if relation_key in created_relations:
            continue
        created_relations.add(relation_key)
        
        # Create property node
        prop_node = node_tree.nodes.new("Onto3DNodeProperty")
        prop_node.onto3d_ontology = ontology_slug
        prop_node.onto3d_property_id = property_id
        
        # Set label if available
        prop_label = g.value(URIRef(pred_str), RDFS.label)
        if prop_label:
            prop_node.prop_label = str(prop_label)
        
        # Check if inferred (mark for visual distinction)
        is_inferred = (subject, ONTO3D.inferredRelation, obj) in g
        if is_inferred:
            prop_node["onto3d_inferred"] = True
        
        # Create links
        subject_node = node_map[subject_str]
        object_node = node_map[object_str]
        
        try:
            # Connect: subject.output -> property.input
            node_tree.links.new(subject_node.outputs[0], prop_node.inputs[0])
            # Connect: property.output -> object.input
            node_tree.links.new(prop_node.outputs[0], object_node.inputs[0])
            stats['properties_created'] += 1
        except Exception as e:
            stats['errors'].append(f"Failed to link {subject_str} -> {object_str}: {e}")
    
    # Step 3: Auto-layout if requested and no positions were saved
    if auto_layout:
        # Check if any node has saved position
        has_positions = any(
            g.value(URIRef(uri), ONTO3D.positionX) is not None
            for uri in node_map.keys()
        )
        
        if not has_positions:
            try:
                suggested_algorithm = estimate_graph_complexity(node_tree)
                auto_layout_nodes(node_tree, algorithm=suggested_algorithm)
            except Exception as e:
                print(f"[Onto3D] Auto-layout failed: {e}")
    
    return stats


class ONTO3D_OT_ImportGraphTTL(Operator):
    """Import RDF/Turtle file into the node graph (from Protégé or other OWL tools)"""
    bl_idname = "onto3d.import_graph_ttl"
    bl_label = "Import Graph (TTL)"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: StringProperty(
        name="File Path",
        description="Input TTL file path",
        subtype='FILE_PATH',
        default="//ontology_export.ttl"
    )
    
    merge_mode: EnumProperty(
        name="Import Mode",
        description="How to handle existing nodes",
        items=[
            ('replace', "Replace", "Clear all existing nodes before import"),
            ('merge', "Merge", "Add imported nodes to existing graph"),
            ('update', "Update", "Update matching nodes, add new ones"),
        ],
        default='replace'
    )
    
    auto_layout: BoolProperty(
        name="Auto Layout",
        description="Automatically arrange nodes after import",
        default=True
    )
    
    def execute(self, context):
        if not ensure_rdflib():
            self.report({'ERROR'}, "rdflib not installed. Check console for instructions.")
            print(install_rdflib_instructions())
            return {'CANCELLED'}
        
        space = getattr(context, "space_data", None)
        if not space or space.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "Open a Node Editor")
            return {'CANCELLED'}
        
        node_tree = space.edit_tree or space.node_tree
        if not node_tree:
            self.report({'ERROR'}, "No node tree active")
            return {'CANCELLED'}
        
        # Expand relative path
        filepath = bpy.path.abspath(self.filepath)
        
        try:
            stats = import_graph_from_ttl(
                node_tree, 
                filepath, 
                merge_mode=self.merge_mode,
                auto_layout=self.auto_layout
            )
            
            msg = (f"Imported: {stats['entities_created']} entities, "
                   f"{stats['properties_created']} properties")
            
            if stats['entities_updated'] > 0:
                msg += f", {stats['entities_updated']} updated"
            
            if stats['entities_skipped'] > 0:
                msg += f" ({stats['entities_skipped']} skipped)"
            
            if stats['errors']:
                msg += f" - {len(stats['errors'])} errors (see console)"
                for err in stats['errors'][:5]:  # Show first 5
                    print(f"[Onto3D Import Error] {err}")
            
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(ONTO3D_OT_ImportGraphTTL)


def unregister():
    bpy.utils.unregister_class(ONTO3D_OT_ImportGraphTTL)