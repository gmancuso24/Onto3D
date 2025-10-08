"""
rdf_utils.py - Utility functions for RDF/TTL operations
Shared helpers for import/export modules
"""

import bpy
from typing import Optional, Tuple, Dict, Any, List


def blender_to_protege_name(name: str) -> str:
    """
    Convert Blender name (with spaces) to Protégé format (with underscores).
    
    Args:
        name: Blender name (e.g., "Man Made Object")
    
    Returns:
        Protégé name (e.g., "Man_Made_Object")
    """
    return name.replace(" ", "_")


def protege_to_blender_name(name: str) -> str:
    """
    Convert Protégé name (with underscores) to Blender format (with spaces).
    
    Args:
        name: Protégé name (e.g., "Man_Made_Object")
    
    Returns:
        Blender name (e.g., "Man Made Object")
    """
    return name.replace("_", " ")

def get_onto_reg() -> Dict[str, Any]:
    """Get ONTO_REG from preferences_ontology module"""
    try:
        from . import preferences_ontology
        return preferences_ontology.ONTO_REG
    except (ImportError, AttributeError):
        return {}


def resolve_class_uri(ontology_slug: str, class_id: str) -> Optional[str]:
    """
    Resolve full URI for a class given ontology slug and class ID.
    
    Args:
        ontology_slug: e.g. 'crm', 'cra'
        class_id: e.g. 'E22_Man-Made_Object'
    
    Returns:
        Full URI or None if not found
    """
    onto_reg = get_onto_reg()
    if ontology_slug not in onto_reg:
        return None
    
    ontology_data = onto_reg[ontology_slug]
    base_uri = ontology_data.get("base", f"http://example.org/{ontology_slug}#")
    
    # Ensure base_uri ends with # or /
    if not base_uri.endswith(('#', '/')):
        base_uri += '#'
    
    return f"{base_uri}{class_id}"


def resolve_property_uri(ontology_slug: str, property_id: str) -> Optional[str]:
    """
    Resolve full URI for a property given ontology slug and property ID.
    
    Args:
        ontology_slug: e.g. 'crm'
        property_id: e.g. 'P46_is_composed_of'
    
    Returns:
        Full URI or None if not found
    """
    onto_reg = get_onto_reg()
    if ontology_slug not in onto_reg:
        return None
    
    ontology_data = onto_reg[ontology_slug]
    base_uri = ontology_data.get("base", f"http://example.org/{ontology_slug}#")
    
    if not base_uri.endswith(('#', '/')):
        base_uri += '#'
    
    return f"{base_uri}{property_id}"


def parse_class_uri(uri: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a class URI to extract ontology slug and class ID.
    
    Args:
        uri: Full URI like 'http://www.cidoc-crm.org/cidoc-crm/E22_Man-Made_Object'
    
    Returns:
        Tuple of (ontology_slug, class_id) or (None, None) if not found
    """
    onto_reg = get_onto_reg()
    
    # Extract fragment/localname
    if '#' in uri:
        class_id = uri.split('#')[-1]
    elif '/' in uri:
        class_id = uri.rstrip('/').split('/')[-1]
    else:
        return None, None
    
    # Find matching ontology by checking if URI starts with base
    for slug, data in onto_reg.items():
        base_uri = data.get("base", "")
        if uri.startswith(base_uri.rstrip('#/')):
            return slug, class_id
        
        # Also check if class_id matches any known entity
        for entity_id, _, _ in data.get("entities", []):
            if entity_id == class_id:
                return slug, class_id
    
    return None, None


def parse_property_uri(uri: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a property URI to extract ontology slug and property ID.
    
    Args:
        uri: Full URI like 'http://www.cidoc-crm.org/cidoc-crm/P46_is_composed_of'
    
    Returns:
        Tuple of (ontology_slug, property_id) or (None, None) if not found
    """
    onto_reg = get_onto_reg()
    
    # Extract fragment/localname
    if '#' in uri:
        property_id = uri.split('#')[-1]
    elif '/' in uri:
        property_id = uri.rstrip('/').split('/')[-1]
    else:
        return None, None
    
    # Find matching ontology
    for slug, data in onto_reg.items():
        base_uri = data.get("base", "")
        if uri.startswith(base_uri.rstrip('#/')):
            return slug, property_id
        
        # Also check if property_id matches any known property
        for prop_id, _, _ in data.get("properties", []):
            if prop_id == property_id:
                return slug, property_id
    
    return None, None


def get_namespace_bindings() -> Dict[str, str]:
    """
    Get all namespace prefix → URI bindings from loaded ontologies.
    
    Returns:
        Dict mapping prefix to URI
    """
    onto_reg = get_onto_reg()
    bindings = {}
    
    for slug, data in onto_reg.items():
        base_uri = data.get("base", f"http://example.org/{slug}#")
        prefix = data.get("prefix", slug).lower()
        bindings[prefix] = base_uri
    
    return bindings


def get_linked_entity_node(socket, visited=None):
    """
    Recursively find the entity node connected to a socket.
    Handles cycles by tracking visited sockets.
    """
    if visited is None:
        visited = set()
    
    if not socket or not socket.is_linked:
        return None
    
    # Use a unique identifier for the socket to prevent infinite loops
    try:
        socket_id = (id(socket.id_data), socket.path_from_id())
    except:
        # Fallback if path_from_id() fails
        socket_id = (id(socket.id_data), id(socket))
    
    if socket_id in visited:
        return None
    visited.add(socket_id)
    
    try:
        for link in socket.links:
            # Determine the connected node based on socket direction
            if socket.is_output:
                # We're on an output socket, follow to the input
                connected_node = link.to_node
                next_socket = link.to_socket
            else:
                # We're on an input socket, follow from the output
                connected_node = link.from_node
                next_socket = link.from_socket
            
            if not connected_node:
                continue
            
            # Check if this is an entity node
            if connected_node.bl_idname in ('Onto3DNodeEntity', 'Onto3DEntityNodeType'):
                return connected_node
            
            # Continue searching through the connected node's sockets
            # Search in the opposite direction
            if socket.is_output:
                # We came from output, search the connected node's outputs
                for out_socket in connected_node.outputs:
                    if out_socket != next_socket:  # Don't go back where we came from
                        result = get_linked_entity_node(out_socket, visited)
                        if result:
                            return result
            else:
                # We came from input, search the connected node's inputs
                for in_socket in connected_node.inputs:
                    if in_socket != next_socket:  # Don't go back where we came from
                        result = get_linked_entity_node(in_socket, visited)
                        if result:
                            return result
    except RecursionError:
        print(f"[Onto3D] RecursionError in get_linked_entity_node - stopping recursion")
        return None
    except Exception as e:
        print(f"[Onto3D] Error in get_linked_entity_node: {e}")
        return None
    
    return None


def sanitize_node_name(name: str) -> str:
    """
    Sanitize a node name for use in URI.
    
    Args:
        name: Blender node name
    
    Returns:
        Sanitized name safe for URI
    """
    import re
    # Replace spaces and special chars with underscore
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    # Remove leading/trailing underscores
    safe = safe.strip('_')
    # Ensure it starts with a letter
    if safe and not safe[0].isalpha():
        safe = 'n_' + safe
    return safe or 'node'


def ensure_rdflib():
    """
    Check if rdflib is available, provide helpful error if not.
    
    Returns:
        True if available, False otherwise
    """
    try:
        import rdflib
        return True
    except ImportError:
        return False


def install_rdflib_instructions() -> str:
    """
    Get user-friendly instructions for installing rdflib.
    
    Returns:
        Instruction string
    """
    import sys
    python_exe = sys.executable
    
    return f"""rdflib is required for RDF import/export.

Install via Blender's Python:
1. Open Blender Console (Window > Toggle System Console)
2. Run this command:
   {python_exe} -m pip install rdflib

Or install manually:
pip install rdflib

Then restart Blender."""


def parse_ontology_file(path_or_url: str, is_url: bool = False) -> Tuple[list, list]:
    """
    Parse RDF/OWL/TTL file and extract entities (classes) and properties.
    
    Args:
        path_or_url: File path or URL to ontology
        is_url: True if path_or_url is a URL, False if local file
    
    Returns:
        Tuple of (entities, properties) where each is a list of (id, label, namespace) tuples
    
    Raises:
        RuntimeError: If rdflib is not available
        FileNotFoundError: If file doesn't exist (when is_url=False)
    """
    try:
        import rdflib
        from rdflib.namespace import RDF, RDFS, OWL, SKOS
    except ImportError as e:
        raise RuntimeError("rdflib is not installed or not available in Blender's environment") from e

    g = rdflib.Graph()
    g.parse(path_or_url)

    def _label_for(node):
        """Extract best label for a node (rdfs:label, skos:prefLabel, or localname)"""
        # Try rdfs:label first
        lbl = g.value(node, RDFS.label)
        if lbl:
            return str(lbl)
        # Try skos:prefLabel
        lbl = g.value(node, SKOS.prefLabel)
        if lbl:
            return str(lbl)
        # Fallback to localname from URI
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

    # Extract classes (rdfs:Class and owl:Class)
    seen_classes = set()
    for s in g.subjects(RDF.type, RDFS.Class):
        sid = str(s)
        if sid in seen_classes:
            continue
        entities.append((sid, _label_for(s), ""))
        seen_classes.add(sid)

    for s in g.subjects(RDF.type, OWL.Class):
        sid = str(s)
        if sid in seen_classes:
            continue
        entities.append((sid, _label_for(s), ""))
        seen_classes.add(sid)

    # Extract properties (rdf:Property, owl:ObjectProperty, owl:DatatypeProperty, owl:AnnotationProperty)
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