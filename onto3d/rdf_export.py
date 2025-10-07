"""
rdf_export.py - Export Blender Onto3D graph to RDF/Turtle format
Compatible with Protégé and other OWL tools
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from .rdf_utils import (
    ensure_rdflib, install_rdflib_instructions,
    get_namespace_bindings, resolve_class_uri, resolve_property_uri,
    get_linked_entity_node, sanitize_node_name
)


def export_graph_to_ttl(node_tree, filepath: str, include_metadata=True) -> dict:
    """
    Export node tree to Turtle (TTL) format.
    
    Args:
        node_tree: Blender NodeTree to export
        filepath: Output file path
        include_metadata: Include Blender-specific metadata (positions, etc.)
    
    Returns:
        Dictionary with export statistics
    """
    if not ensure_rdflib():
        raise ImportError("rdflib is required. " + install_rdflib_instructions())
    
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, OWL, XSD
    
    # Create graph
    g = Graph()
    
    # Define namespaces
    ONTO3D = Namespace("http://onto3d.local/")
    g.bind("onto3d", ONTO3D)
    g.bind("owl", OWL)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)
    
    # Bind loaded ontology namespaces
    ns_bindings = get_namespace_bindings()
    for prefix, uri in ns_bindings.items():
        g.bind(prefix, Namespace(uri))
    
    # Add ontology declaration
    ontology_uri = ONTO3D["ontology"]
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.label, Literal(f"Onto3D Graph: {node_tree.name}")))
    
    stats = {
        'entities': 0,
        'properties': 0,
        'triples': 0
    }
    
    # Export entity nodes as individuals
    node_uri_map = {}  # node.name -> URI
    
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeEntity":
            stats['entities'] += 1
            
            # Generate URI for individual
            safe_name = sanitize_node_name(node.name)
            individual_uri = ONTO3D[safe_name]
            node_uri_map[node.name] = individual_uri
            
            # Get ontology class
            ontology_slug = getattr(node, "onto3d_ontology", "")
            class_id = getattr(node, "onto3d_entity_id", "")
            
            if ontology_slug and class_id:
                class_uri_str = resolve_class_uri(ontology_slug, class_id)
                if class_uri_str:
                    class_uri = URIRef(class_uri_str)
                    g.add((individual_uri, RDF.type, class_uri))
                    stats['triples'] += 1
            
            # Add label
            title = getattr(node, "onto3d_title", "") or node.name
            if title:
                g.add((individual_uri, RDFS.label, Literal(title)))
                stats['triples'] += 1
            
            # Add description if present
            description = getattr(node, "onto3d_description", "")
            if description:
                g.add((individual_uri, RDFS.comment, Literal(description)))
                stats['triples'] += 1
            
            # Add IRI reference if present
            iri_value = getattr(node, "onto3d_iri", "")
            if iri_value:
                g.add((individual_uri, RDFS.seeAlso, URIRef(iri_value)))
                stats['triples'] += 1
            
            # Add Blender metadata (optional)
            if include_metadata:
                g.add((individual_uri, ONTO3D.blenderNodeName, Literal(node.name)))
                g.add((individual_uri, ONTO3D.positionX, Literal(node.location.x, datatype=XSD.float)))
                g.add((individual_uri, ONTO3D.positionY, Literal(node.location.y, datatype=XSD.float)))
                stats['triples'] += 3
    
    # Export property nodes as relationships
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeProperty":
            stats['properties'] += 1
            
            # Get connected entities
            subject_node = get_linked_entity_node(node.inputs[0])
            object_node = get_linked_entity_node(node.outputs[0])
            
            if not subject_node or not object_node:
                continue
            
            subject_uri = node_uri_map.get(subject_node.name)
            object_uri = node_uri_map.get(object_node.name)
            
            if not subject_uri or not object_uri:
                continue
            
            # Get property URI
            ontology_slug = getattr(node, "onto3d_ontology", "")
            property_id = getattr(node, "onto3d_property_id", "")
            
            if ontology_slug and property_id:
                property_uri_str = resolve_property_uri(ontology_slug, property_id)
                if property_uri_str:
                    property_uri = URIRef(property_uri_str)
                    g.add((subject_uri, property_uri, object_uri))
                    stats['triples'] += 1
                    
                    # Mark if this is an inferred relationship (for re-import)
                    if node.get("onto3d_inferred", False):
                        g.add((subject_uri, ONTO3D.inferredRelation, object_uri))
    
    # Serialize to file
    g.serialize(destination=filepath, format='turtle')
    
    return stats


class ONTO3D_OT_ExportGraphTTL(Operator):
    """Export the current node graph to RDF/Turtle format (compatible with Protégé)"""
    bl_idname = "onto3d.export_graph_ttl"
    bl_label = "Export Graph (TTL)"
    bl_options = {'REGISTER'}
    
    filepath: StringProperty(
        name="File Path",
        description="Output TTL file path",
        subtype='FILE_PATH',
        default="//ontology_export.ttl"
    )
    
    include_metadata: bpy.props.BoolProperty(
        name="Include Blender Metadata",
        description="Include node positions and Blender-specific data",
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
            stats = export_graph_to_ttl(node_tree, filepath, self.include_metadata)
            self.report({'INFO'}, 
                f"Exported: {stats['entities']} entities, {stats['properties']} properties, "
                f"{stats['triples']} triples → {filepath}")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(ONTO3D_OT_ExportGraphTTL)


def unregister():
    bpy.utils.unregister_class(ONTO3D_OT_ExportGraphTTL)
