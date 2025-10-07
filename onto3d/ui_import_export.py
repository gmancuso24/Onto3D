"""
ui_import_export.py - UI Panel and operators for RDF Import/Export
Add this panel to the Onto3D N-Panel in Node Editor
"""

import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty


class ONTO3D_PT_ImportExport(Panel):
    """Panel for importing/exporting RDF graphs"""
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Onto3D'
    bl_label = 'Import / Export Graph'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'NODE_EDITOR'
    
    def draw(self, context):
        layout = self.layout
        
        # Export section
        box = layout.box()
        box.label(text="Export to Protégé", icon='EXPORT')
        col = box.column(align=True)
        col.label(text="Export current graph as RDF/Turtle")
        col.label(text="Compatible with Protégé OWL editor")
        col.operator("onto3d.export_graph_ttl", text="Export Graph (TTL)", icon='FILE_TICK')
        
        # Import section
        layout.separator()
        box = layout.box()
        box.label(text="Import from Protégé", icon='IMPORT')
        col = box.column(align=True)
        col.label(text="Import RDF/Turtle file")
        col.label(text="Includes reasoning results")
        col.operator("onto3d.import_graph_ttl", text="Import Graph (TTL)", icon='APPEND_BLEND')
        
        # Auto-layout section
        layout.separator()
        box = layout.box()
        box.label(text="Auto-Layout", icon='STICKY_UVS_LOC')
        
        # Get node tree to check if layout is needed
        space = getattr(context, "space_data", None)
        node_tree = None
        if space and space.type == 'NODE_EDITOR':
            node_tree = space.edit_tree or space.node_tree
        
        if node_tree and node_tree.nodes:
            from .graph_layout import estimate_graph_complexity
            suggested = estimate_graph_complexity(node_tree)
            
            col = box.column(align=True)
            col.label(text=f"Suggested: {suggested.title()}", icon='INFO')
            
            row = col.row(align=True)
            op = row.operator("onto3d.auto_layout", text="Hierarchical")
            op.algorithm = 'hierarchical'
            op = row.operator("onto3d.auto_layout", text="Spring")
            op.algorithm = 'spring'
            
            row = col.row(align=True)
            op = row.operator("onto3d.auto_layout", text="Circular")
            op.algorithm = 'circular'
            op = row.operator("onto3d.auto_layout", text="Grid")
            op.algorithm = 'grid'
        else:
            box.label(text="No nodes to layout", icon='INFO')
        
        # Info section
        layout.separator()
        box = layout.box()
        box.label(text="Workflow", icon='QUESTION')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="1. Export graph from Blender")
        col.label(text="2. Open TTL in Protégé")
        col.label(text="3. Run reasoner (e.g., Pellet, HermiT)")
        col.label(text="4. Save inferred ontology")
        col.label(text="5. Import back to Blender")


class ONTO3D_OT_AutoLayout(Operator):
    """Automatically arrange nodes using graph layout algorithm"""
    bl_idname = "onto3d.auto_layout"
    bl_label = "Auto Layout Nodes"
    bl_options = {'REGISTER', 'UNDO'}
    
    algorithm: StringProperty(
        name="Algorithm",
        description="Layout algorithm to use",
        default='hierarchical'
    )
    
    spacing: bpy.props.IntProperty(
        name="Spacing",
        description="Distance between nodes",
        default=400,
        min=100,
        max=2000
    )
    
    def execute(self, context):
        space = getattr(context, "space_data", None)
        if not space or space.type != 'NODE_EDITOR':
            self.report({'ERROR'}, "Open a Node Editor")
            return {'CANCELLED'}
        
        node_tree = space.edit_tree or space.node_tree
        if not node_tree:
            self.report({'ERROR'}, "No node tree active")
            return {'CANCELLED'}
        
        if not node_tree.nodes:
            self.report({'WARNING'}, "No nodes to layout")
            return {'CANCELLED'}
        
        try:
            from .graph_layout import auto_layout_nodes
            auto_layout_nodes(node_tree, algorithm=self.algorithm, spacing=self.spacing)
            self.report({'INFO'}, f"Applied {self.algorithm} layout")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Layout failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}


class ONTO3D_OT_CheckRDFLib(Operator):
    """Check if rdflib is installed and show installation instructions"""
    bl_idname = "onto3d.check_rdflib"
    bl_label = "Check rdflib Installation"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        from .rdf_utils import ensure_rdflib, install_rdflib_instructions
        
        if ensure_rdflib():
            self.report({'INFO'}, "rdflib is installed and ready")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "rdflib not found. See console for installation instructions.")
            print("\n" + "="*60)
            print(install_rdflib_instructions())
            print("="*60 + "\n")
            return {'CANCELLED'}


# Registration
_CLASSES = (
    ONTO3D_PT_ImportExport,
    ONTO3D_OT_AutoLayout,
    ONTO3D_OT_CheckRDFLib,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
