"""
ui_import_export.py - UI Panel and operators for RDF Import/Export
Separate panels for Import and Export in the Onto3D N-Panel
"""

import bpy
from bpy.types import Panel, Operator
from bpy.props import StringProperty


class ONTO3D_PT_Import(Panel):
    """Panel for importing RDF graphs"""
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Onto3D'
    bl_label = 'Import'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'NODE_EDITOR'
    
    def draw(self, context):
        layout = self.layout
        
        # Import section
        box = layout.box()
        box.label(text="Import TTL Graph", icon='IMPORT')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text="Import RDF/Turtle file")
        col.label(text="Includes reasoning results")
        
        box.separator()
        box.operator("onto3d.import_graph_ttl", text="Import Graph (TTL)", icon='APPEND_BLEND')


class ONTO3D_PT_Export(Panel):
    """Panel for exporting RDF graphs"""
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Onto3D'
    bl_label = 'Export'
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
        col.scale_y = 0.8
        col.label(text="Export current graph as RDF/Turtle")
        col.label(text="Compatible with Protégé OWL editor")
        
        box.separator()
        box.operator("onto3d.export_graph_ttl", text="Export Graph (TTL)", icon='FILE_TICK')

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
    ONTO3D_PT_Import,
    ONTO3D_PT_Export,
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