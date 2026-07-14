import bpy
import blf
import bmesh
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup
from bpy_extras import view3d_utils

class VEFProperties(PropertyGroup):
    is_enabled: BoolProperty(
        name="Enabled",
        default=False,
        description="Enable index visualization"
    )
    show_verts: BoolProperty(
        name="Vertices",
        default=True,
        description="Show vertex indices"
    )
    show_edges: BoolProperty(
        name="Edges",
        default=False,
        description="Show edge indices"
    )
    show_faces: BoolProperty(
        name="Faces",
        default=False,
        description="Show face/polygon indices"
    )
    show_selected_only: BoolProperty(
        name="Selected Only",
        default=False,
        description="Show indices only for selected elements"
    )
    show_verts_in_all_modes: BoolProperty(
        name="Show Vertices in All Modes",
        default=False,
        description="Show vertex indices in all modes (Object, Sculpt, etc.)"
    )
    enable_limit: BoolProperty(
        name="Limit Display Count",
        default=False,
        description="Limit the number of displayed indices for performance"
    )
    limit_count: IntProperty(
        name="Max Indices",
        default=500,
        min=1,
        max=10000,
        description="Maximum number of indices to display (for heavy meshes)"
    )
    text_size: IntProperty(
        name="Text Size",
        default=14,
        min=8,
        max=30,
        description="Font size for indices"
    )
    color_verts: FloatVectorProperty(
        name="Vertex Color",
        default=(1.0, 0.2, 0.2, 1.0),
        size=4,
        min=0.0,
        max=1.0,
        subtype='COLOR',
        description="Color for vertex indices"
    )
    color_edges: FloatVectorProperty(
        name="Edge Color",
        default=(0.2, 1.0, 0.2, 1.0),
        size=4,
        min=0.0,
        max=1.0,
        subtype='COLOR',
        description="Color for edge indices"
    )
    color_faces: FloatVectorProperty(
        name="Face Color",
        default=(0.2, 0.2, 1.0, 1.0),
        size=4,
        min=0.0,
        max=1.0,
        subtype='COLOR',
        description="Color for face indices"
    )

draw_handle = None

def draw_indices_callback(*args):
    ctx = bpy.context
    scene = ctx.scene
    props = scene.vef_props
    
    if not props.is_enabled:
        return
    
    obj = ctx.active_object
    if not obj or obj.type != 'MESH':
        return
    
    region = ctx.region
    rv3d = ctx.space_data.region_3d
    if not region or not rv3d:
        return
    
    font_id = 0
    blf.size(font_id, props.text_size)
    
    is_edit_mode = ctx.mode in ('EDIT_MESH', 'PAINT_WEIGHT')
    limit = props.limit_count if props.enable_limit else float('inf')
    
    bm = None
    if is_edit_mode and (props.show_verts or props.show_edges or props.show_faces):
        bm = bmesh.from_edit_mesh(obj.data)
    
    # Vertex indices
    if props.show_verts:
        if is_edit_mode and bm:
            blf.color(font_id, *props.color_verts)
            count = 0
            for v in bm.verts:
                if v.hide:
                    continue
                if props.show_selected_only and not v.select:
                    continue
                co_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, obj.matrix_world @ v.co
                )
                if co_2d:
                    if count >= limit:
                        break
                    blf.position(font_id, co_2d.x, co_2d.y, 0)
                    blf.draw(font_id, str(v.index))
                    count += 1
        elif props.show_verts_in_all_modes and not is_edit_mode and obj.data.vertices:
            blf.color(font_id, *props.color_verts)
            count = 0
            for v in obj.data.vertices:
                co_2d = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, obj.matrix_world @ v.co
                )
                if co_2d:
                    if count >= limit:
                        break
                    blf.position(font_id, co_2d.x, co_2d.y, 0)
                    blf.draw(font_id, str(v.index))
                    count += 1
    
    # Edge indices
    if props.show_edges and bm:
        blf.color(font_id, *props.color_edges)
        count = 0
        for e in bm.edges:
            if e.hide:
                continue
            if props.show_selected_only and not e.select:
                continue
            center = (e.verts[0].co + e.verts[1].co) / 2.0
            co_2d = view3d_utils.location_3d_to_region_2d(
                region, rv3d, obj.matrix_world @ center
            )
            if co_2d:
                if count >= limit:
                    break
                blf.position(font_id, co_2d.x, co_2d.y, 0)
                blf.draw(font_id, str(e.index))
                count += 1
    
    # Face indices
    if props.show_faces and bm:
        blf.color(font_id, *props.color_faces)
        count = 0
        for f in bm.faces:
            if f.hide:
                continue
            if props.show_selected_only and not f.select:
                continue
            center = f.calc_center_median()
            co_2d = view3d_utils.location_3d_to_region_2d(
                region, rv3d, obj.matrix_world @ center
            )
            if co_2d:
                if count >= limit:
                    break
                blf.position(font_id, co_2d.x, co_2d.y, 0)
                blf.draw(font_id, str(f.index))
                count += 1

class VEF_OT_toggle_display(Operator):
    bl_idname = "vef.toggle_display"
    bl_label = "Toggle Index Display"
    bl_description = "Enable/disable index visualization"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        props = context.scene.vef_props
        props.is_enabled = not props.is_enabled
        context.area.tag_redraw()
        return {'FINISHED'}

class VEF_PT_main_panel(Panel):
    bl_label = "VEF Index Visualizer"
    bl_idname = "VEF_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "VEF Index Vis"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.vef_props
        
        row = layout.row(align=True)
        if props.is_enabled:
            row.operator("vef.toggle_display", text="Disable", icon='HIDE_ON')
        else:
            row.operator("vef.toggle_display", text="Enable", icon='HIDE_OFF')
        
        layout.separator()
        
        col = layout.column(align=True)
        col.prop(props, "show_verts", text="Vertices", icon='VERTEXSEL')
        col.prop(props, "show_edges", text="Edges", icon='EDGESEL')
        col.prop(props, "show_faces", text="Faces", icon='FACESEL')
        
        layout.separator()
        
        box = layout.box()
        box.label(text="Settings", icon='SETTINGS')
        
        row = box.row()
        row.enabled = context.mode in ('EDIT_MESH', 'PAINT_WEIGHT')
        row.prop(props, "show_selected_only", text="Selected Only")
        
        box.prop(props, "show_verts_in_all_modes", text="Show Vertices in All Modes")
        
        box.separator()
        box.prop(props, "enable_limit", text="Limit Display Count")
        row = box.row()
        row.enabled = props.enable_limit
        row.prop(props, "limit_count", text="Max Indices")
        
        box.separator()
        box.prop(props, "text_size", text="Font Size")
        box.separator()
        box.label(text="Colors:", icon='COLOR')
        box.prop(props, "color_verts", text="Vertices")
        box.prop(props, "color_edges", text="Edges")
        box.prop(props, "color_faces", text="Faces")

classes = (
    VEFProperties,
    VEF_OT_toggle_display,
    VEF_PT_main_panel,
)

def register():
    global draw_handle
    
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.vef_props = PointerProperty(type=VEFProperties)
    
    draw_handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_indices_callback, (), 'WINDOW', 'POST_PIXEL'
    )

def unregister():
    global draw_handle
    
    if draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')
        draw_handle = None
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.vef_props

if __name__ == "__main__":
    register()