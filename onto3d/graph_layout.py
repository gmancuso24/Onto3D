"""
graph_layout.py - Auto-layout algorithms for node positioning
Supports hierarchical, spring, circular, and grid layouts
"""

import bpy
from typing import Dict, Tuple, List, Set
from .rdf_utils import get_linked_entity_node


def auto_layout_nodes(node_tree, algorithm='hierarchical', spacing=400):
    """
    Auto-layout nodes in the node tree using specified algorithm.
    
    Args:
        node_tree: Blender NodeTree
        algorithm: 'hierarchical', 'spring', 'circular', 'grid'
        spacing: Base spacing between nodes
    """
    try:
        import networkx as nx
        use_networkx = True
    except ImportError:
        print("[Onto3D] NetworkX not found, using fallback grid layout")
        use_networkx = False
    
    if not use_networkx or algorithm == 'grid':
        _simple_grid_layout(node_tree, spacing)
        return
    
    # Build NetworkX graph
    G = _build_networkx_graph(node_tree)
    
    if not G.nodes():
        return
    
    # Calculate positions based on algorithm
    if algorithm == 'hierarchical':
        pos = _hierarchical_layout(G)
    elif algorithm == 'spring':
        import networkx as nx
        pos = nx.spring_layout(G, k=2, iterations=50)
    elif algorithm == 'circular':
        import networkx as nx
        pos = nx.circular_layout(G)
    else:
        import networkx as nx
        pos = nx.kamada_kawai_layout(G)
    
    # Apply positions to Blender nodes
    _apply_positions(node_tree, pos, spacing)


def _build_networkx_graph(node_tree):
    """Build NetworkX directed graph from Blender node tree"""
    import networkx as nx
    G = nx.DiGraph()
    
    # Add entity nodes
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeEntity":
            G.add_node(node.name, node_obj=node, node_type='entity')
    
    # Add edges from property connections
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeProperty":
            subject = get_linked_entity_node(node.inputs[0])
            obj = get_linked_entity_node(node.outputs[0])
            
            if subject and obj:
                G.add_edge(subject.name, obj.name, via=node.name, property_node=node)
    
    return G


def _hierarchical_layout(G) -> Dict[str, Tuple[float, float]]:
    """
    Hierarchical top-down layout (Sugiyama-style).
    Root nodes at top, children below in layers.
    """
    import networkx as nx
    
    # Find root nodes (no predecessors)
    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    
    if not roots:
        # No clear roots: try to find minimal set
        try:
            # Find nodes with minimal in-degree
            min_in = min(G.in_degree(n) for n in G.nodes())
            roots = [n for n in G.nodes() if G.in_degree(n) == min_in]
        except ValueError:
            roots = [list(G.nodes())[0]] if G.nodes() else []
    
    pos = {}
    visited = set()
    layer_nodes = {}  # layer -> list of nodes
    
    def assign_layers(node, layer):
        """Recursively assign layer numbers to nodes"""
        if node in visited:
            return
        visited.add(node)
        
        if layer not in layer_nodes:
            layer_nodes[layer] = []
        layer_nodes[layer].append(node)
        
        # Process children
        for child in G.successors(node):
            assign_layers(child, layer + 1)
    
    # Assign all nodes to layers
    for root in roots:
        assign_layers(root, 0)
    
    # Handle unreached nodes (disconnected components)
    for node in G.nodes():
        if node not in visited:
            assign_layers(node, 0)
    
    # Position nodes within each layer
    max_layer = max(layer_nodes.keys()) if layer_nodes else 0
    
    for layer, nodes in layer_nodes.items():
        y = -layer  # Negative Y goes down
        num_nodes = len(nodes)
        
        # Center the layer horizontally
        start_x = -(num_nodes - 1) / 2
        
        for i, node in enumerate(nodes):
            x = start_x + i
            pos[node] = (x, y)
    
    # Optional: adjust X positions to minimize edge crossings
    # (simplified version - could be improved with proper Sugiyama algorithm)
    for layer in range(1, max_layer + 1):
        if layer not in layer_nodes:
            continue
        
        nodes = layer_nodes[layer]
        # Sort by average parent X position
        def avg_parent_x(n):
            parents = list(G.predecessors(n))
            if not parents:
                return pos[n][0]
            return sum(pos[p][0] for p in parents) / len(parents)
        
        nodes.sort(key=avg_parent_x)
        
        # Re-assign X positions
        start_x = -(len(nodes) - 1) / 2
        for i, node in enumerate(nodes):
            pos[node] = (start_x + i, pos[node][1])
    
    return pos


def _apply_positions(node_tree, pos: Dict[str, Tuple[float, float]], spacing: float):
    """Apply calculated positions to Blender nodes"""
    # Apply to entity nodes
    for node_name, (x, y) in pos.items():
        node = node_tree.nodes.get(node_name)
        if node:
            node.location = (x * spacing, y * spacing)
    
    # Position property nodes between connected entities
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeProperty":
            subject = get_linked_entity_node(node.inputs[0])
            obj = get_linked_entity_node(node.outputs[0])
            
            if subject and obj:
                # Place halfway between subject and object, slightly offset
                mid_x = (subject.location.x + obj.location.x) / 2
                mid_y = (subject.location.y + obj.location.y) / 2 + spacing * 0.25
                node.location = (mid_x, mid_y)


def _simple_grid_layout(node_tree, spacing: float):
    """
    Fallback grid layout (no NetworkX required).
    Places entity nodes in a grid, property nodes near their subjects.
    """
    entities = [n for n in node_tree.nodes if n.bl_idname == "Onto3DNodeEntity"]
    
    if not entities:
        return
    
    # Calculate grid dimensions
    import math
    num_entities = len(entities)
    cols = max(1, int(math.sqrt(num_entities) * 1.5))  # Wider than tall
    
    # Place entities in grid
    for i, node in enumerate(entities):
        row = i // cols
        col = i % cols
        node.location = (col * spacing, -row * spacing)
    
    # Place property nodes near their subject entities
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeProperty":
            subject = get_linked_entity_node(node.inputs[0])
            obj = get_linked_entity_node(node.outputs[0])
            
            if subject and obj:
                # Place between subject and object
                mid_x = (subject.location.x + obj.location.x) / 2
                mid_y = (subject.location.y + obj.location.y) / 2 + spacing * 0.2
                node.location = (mid_x, mid_y)
            elif subject:
                # Place to the right of subject
                node.location = (subject.location.x + spacing * 0.5, subject.location.y - spacing * 0.3)


def estimate_graph_complexity(node_tree) -> str:
    """
    Estimate graph complexity and suggest best layout algorithm.
    
    Returns:
        Suggested algorithm name
    """
    entities = [n for n in node_tree.nodes if n.bl_idname == "Onto3DNodeEntity"]
    properties = [n for n in node_tree.nodes if n.bl_idname == "Onto3DNodeProperty"]
    
    num_entities = len(entities)
    num_properties = len(properties)
    
    if num_entities == 0:
        return 'grid'
    
    # Build simple graph to check connectivity
    connections = {}
    for prop_node in properties:
        subject = get_linked_entity_node(prop_node.inputs[0])
        obj = get_linked_entity_node(prop_node.outputs[0])
        if subject and obj:
            if subject.name not in connections:
                connections[subject.name] = []
            connections[subject.name].append(obj.name)
    
    # Check if graph is tree-like (hierarchical)
    is_hierarchical = _is_tree_like(connections, entities)
    
    if is_hierarchical:
        return 'hierarchical'
    elif num_entities < 20:
        return 'spring'
    elif num_entities < 50:
        return 'circular'
    else:
        return 'grid'


def _is_tree_like(connections: Dict[str, List[str]], entities) -> bool:
    """Check if graph resembles a tree (suitable for hierarchical layout)"""
    if not connections:
        return False
    
    # Count nodes with no incoming edges (potential roots)
    all_nodes = {e.name for e in entities}
    children = set()
    for targets in connections.values():
        children.update(targets)
    
    roots = all_nodes - children
    
    # Tree-like if: 1-3 roots and edges ≈ nodes - 1
    num_edges = sum(len(targets) for targets in connections.values())
    num_nodes = len(all_nodes)
    
    return len(roots) in (1, 2, 3) and abs(num_edges - (num_nodes - len(roots))) < 3
