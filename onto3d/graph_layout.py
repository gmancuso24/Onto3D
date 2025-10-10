"""
graph_layout.py - Auto-layout algorithms for node positioning
Supports hierarchical (LR/TB), and grid layouts
"""

import bpy
from typing import Dict, Tuple, List, Set
from .rdf_utils import get_linked_entity_node


def auto_layout_nodes(node_tree, algorithm='hierarchical', orientation='LR', spacing=400):
    """
    Auto-layout nodes in the node tree using specified algorithm.
    
    Args:
        node_tree: Blender NodeTree
        algorithm: 'hierarchical' or 'grid'
        orientation: 'LR' (Left-Right) or 'TB' (Top-Bottom) - only for hierarchical
        spacing: Base spacing between nodes
    """
    if algorithm == 'grid':
        _simple_grid_layout(node_tree, spacing)
        return
    
    if algorithm == 'hierarchical':
        _hierarchical_layout(node_tree, orientation, spacing)
        return
    
    # Fallback
    _simple_grid_layout(node_tree, spacing)


def _hierarchical_layout(node_tree, orientation='LR', spacing=400):
    """
    Hierarchical layout with Left-Right or Top-Bottom orientation.
    
    Args:
        node_tree: Blender NodeTree
        orientation: 'LR' (default, follows socket direction) or 'TB'
        spacing: Distance between layers
    """
    # Build graph structure
    entities = [n for n in node_tree.nodes if n.bl_idname == "Onto3DNodeEntity"]
    
    if not entities:
        return
    
    # Build adjacency info: node -> list of children
    children_map = {}  # entity.name -> [child entity names]
    parent_count = {}  # entity.name -> number of parents
    
    for entity in entities:
        children_map[entity.name] = []
        parent_count[entity.name] = 0
    
    # Analyze connections through property nodes
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeProperty":
            subject = get_linked_entity_node(node.inputs[0])
            obj = get_linked_entity_node(node.outputs[0])
            
            if subject and obj and subject.name in children_map:
                children_map[subject.name].append(obj.name)
                if obj.name in parent_count:
                    parent_count[obj.name] += 1
    
    # Find root nodes (no parents or minimal parents)
    roots = [name for name, count in parent_count.items() if count == 0]
    
    if not roots:
        # No clear roots: use nodes with minimum parent count
        min_parents = min(parent_count.values()) if parent_count else 0
        roots = [name for name, count in parent_count.items() if count == min_parents]
    
    if not roots:
        # Still no roots: just use first node
        roots = [entities[0].name]
    
    # Assign layers using BFS
    layers = {}  # layer_num -> [node_names]
    visited = set()
    node_layer = {}  # node_name -> layer_num
    
    def assign_layers_bfs(start_nodes):
        queue = [(name, 0) for name in start_nodes]
        
        while queue:
            node_name, layer = queue.pop(0)
            
            if node_name in visited:
                # If already visited, update to deeper layer if needed
                if node_name in node_layer and layer > node_layer[node_name]:
                    # Remove from old layer
                    old_layer = node_layer[node_name]
                    if node_name in layers.get(old_layer, []):
                        layers[old_layer].remove(node_name)
                    # Add to new layer
                    node_layer[node_name] = layer
                    if layer not in layers:
                        layers[layer] = []
                    layers[layer].append(node_name)
                continue
            
            visited.add(node_name)
            node_layer[node_name] = layer
            
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(node_name)
            
            # Add children to queue
            for child_name in children_map.get(node_name, []):
                queue.append((child_name, layer + 1))
    
    # Assign layers starting from roots
    assign_layers_bfs(roots)
    
    # Handle disconnected nodes
    for entity in entities:
        if entity.name not in visited:
            assign_layers_bfs([entity.name])
    
    # Calculate positions in logical coordinates
    # logical: (layer_index, cross_position)
    logical_positions = {}
    
    max_layer = max(layers.keys()) if layers else 0
    
    for layer_num in sorted(layers.keys()):
        nodes_in_layer = layers[layer_num]
        num_nodes = len(nodes_in_layer)
        
        # Sort nodes by average parent position for better layout
        if layer_num > 0:
            def avg_parent_pos(node_name):
                parents = [n for n, children in children_map.items() if node_name in children]
                if not parents:
                    return 0
                parent_positions = [logical_positions.get(p, (0, 0))[1] for p in parents if p in logical_positions]
                return sum(parent_positions) / len(parent_positions) if parent_positions else 0
            
            nodes_in_layer.sort(key=avg_parent_pos)
        
        # Calculate vertical spacing dynamically
        # More nodes = tighter spacing
        import math
        vertical_spacing = max(1.0, 3.0 / math.sqrt(max(1, num_nodes)))
        
        # Center nodes vertically
        start_cross = -(num_nodes - 1) * vertical_spacing / 2
        
        for i, node_name in enumerate(nodes_in_layer):
            cross_pos = start_cross + i * vertical_spacing
            logical_positions[node_name] = (layer_num, cross_pos)
    
    # Convert logical to physical coordinates based on orientation
    entity_map = {e.name: e for e in entities}
    
    for node_name, (layer, cross_pos) in logical_positions.items():
        entity = entity_map.get(node_name)
        if not entity:
            continue
        
        if orientation == 'LR':
            # Left to Right: layer -> X, cross -> Y
            entity.location = (layer * spacing, cross_pos * spacing)
        elif orientation == 'TB':
            # Top to Bottom: cross -> X, -layer -> Y (negative because Y+ is up)
            entity.location = (cross_pos * spacing, -layer * spacing)
    
    # Position property nodes between their connected entities
    for node in node_tree.nodes:
        if node.bl_idname == "Onto3DNodeProperty":
            subject = get_linked_entity_node(node.inputs[0])
            obj = get_linked_entity_node(node.outputs[0])
            
            if subject and obj:
                # Place property node between subject and object
                mid_x = (subject.location.x + obj.location.x) / 2
                mid_y = (subject.location.y + obj.location.y) / 2
                
                # Small offset perpendicular to connection
                if orientation == 'LR':
                    # Offset slightly upward
                    node.location = (mid_x, mid_y + spacing * 0.15)
                elif orientation == 'TB':
                    # Offset slightly to the right
                    node.location = (mid_x + spacing * 0.15, mid_y)


def _simple_grid_layout(node_tree, spacing: float):
    """
    Fallback grid layout (no external dependencies required).
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
    elif num_entities < 50:
        return 'hierarchical'  # Still works well for medium graphs
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
    
    return len(roots) in (1, 2, 3) and abs(num_edges - (num_nodes - len(roots))) < 5