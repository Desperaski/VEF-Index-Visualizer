import bpy
import blf
import bmesh
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup
from bpy_extras import view3d_utils


def _is_point_visible(world_co, depsgraph):
    """True если точка не перекрыта геометрией (ray_cast из камеры в точку)."""
    ctx = bpy.context
    region = ctx.region
    rv3d = ctx.space_data.region_3d
    if not region or not rv3d:
        return True

    cam_loc = rv3d.view_matrix.inverted().translation
    direction = world_co - cam_loc
    dist = direction.length
    if dist < 1e-6:
        return True
    direction.normalize()

    origin = cam_loc + direction * 1e-4

    hit, loc, norm, idx, hit_obj, matrix = ctx.scene.ray_cast(
        depsgraph, origin, direction
    )
    if not hit:
        return True
    hit_dist = (loc - cam_loc).length
    return hit_dist >= dist - 1e-3


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
    use_occlusion: BoolProperty(
        name="Occlusion (Hide Behind Geometry)",
        default=True,
        description="Hide indices that are behind geometry. "
                    "Independent from Blender's X-Ray toggle"
    )
    enable_limit: BoolProperty(
        name="Limit Display Count",
        default=True,
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
    use_occlusion = props.use_occlusion

    depsgraph = ctx.evaluated_depsgraph_get() if use_occlusion else None

    # Кэш видимости вершин: {vert_index: bool}
    # Заполняется лениво — только когда нужен (вершины/рёбра/грани).
    visible_verts = {}

    def vert_visible(v_index, world_co):
        """Видимость вершины с кэшем. world_co передаётся, чтобы не считать дважды."""
        if not use_occlusion:
            return True
        cached = visible_verts.get(v_index)
        if cached is not None:
            return cached
        result = _is_point_visible(world_co, depsgraph)
        visible_verts[v_index] = result
        return result

    def any_vert_visible(vert_indices_world):
        """True если видима хотя бы одна вершина из списка [(idx, world_co), ...]."""
        if not use_occlusion:
            return True
        for vi, wc in vert_indices_world:
            if vert_visible(vi, wc):
                return True
        return False

    bm = None
    if is_edit_mode and (props.show_verts or props.show_edges or props.show_faces):
        bm = bmesh.from_edit_mesh(obj.data)

    try:
        # --- Vertices ---
        if props.show_verts:
            if is_edit_mode and bm:
                blf.color(font_id, *props.color_verts)
                count = 0
                for v in bm.verts:
                    if v.hide:
                        continue
                    if props.show_selected_only and not v.select:
                        continue
                    world_co = obj.matrix_world @ v.co
                    co_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, world_co)
                    if not co_2d:
                        continue
                    if count >= limit:
                        break
                    if not vert_visible(v.index, world_co):
                        continue
                    blf.position(font_id, co_2d.x, co_2d.y, 0)
                    blf.draw(font_id, str(v.index))
                    count += 1
            elif props.show_verts_in_all_modes and not is_edit_mode and obj.data.vertices:
                blf.color(font_id, *props.color_verts)
                count = 0
                for v in obj.data.vertices:
                    world_co = obj.matrix_world @ v.co
                    co_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, world_co)
                    if not co_2d:
                        continue
                    if count >= limit:
                        break
                    if not vert_visible(v.index, world_co):
                        continue
                    blf.position(font_id, co_2d.x, co_2d.y, 0)
                    blf.draw(font_id, str(v.index))
                    count += 1

        # --- Edges ---
        # Видимо, если видима хотя бы одна из двух вершин.
        if props.show_edges and bm:
            blf.color(font_id, *props.color_edges)
            count = 0
            for e in bm.edges:
                if e.hide:
                    continue
                if props.show_selected_only and not e.select:
                    continue
                v0, v1 = e.verts[0], e.verts[1]
                wc0 = obj.matrix_world @ v0.co
                wc1 = obj.matrix_world @ v1.co
                center = (wc0 + wc1) / 2.0
                co_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, center)
                if not co_2d:
                    continue
                if count >= limit:
                    break
                if not any_vert_visible([(v0.index, wc0), (v1.index, wc1)]):
                    continue
                blf.position(font_id, co_2d.x, co_2d.y, 0)
                blf.draw(font_id, str(e.index))
                count += 1

        # --- Faces ---
        # Видимо, если видима хотя бы одна из его вершин.
        if props.show_faces and bm:
            blf.color(font_id, *props.color_faces)
            count = 0
            for f in bm.faces:
                if f.hide:
                    continue
                if props.show_selected_only and not f.select:
                    continue
                verts_world = [
                    (v.index, obj.matrix_world @ v.co) for v in f.verts
                ]
                center_world = f.calc_center_median()
                center = obj.matrix_world @ center_world
                co_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, center)
                if not co_2d:
                    continue
                if count >= limit:
                    break
                if not any_vert_visible(verts_world):
                    continue
                blf.position(font_id, co_2d.x, co_2d.y, 0)
                blf.draw(font_id, str(f.index))
                count += 1
    finally:
        if bm is not None:
            bm.free()


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
            # Индексы видны -> глаз открытый, надпись "Enabled"
            row.operator("vef.toggle_display", text="Enabled", icon='HIDE_OFF')
        else:
            # Индексы скрыты -> глаз закрытый, надпись "Disabled"
            row.operator("vef.toggle_display", text="Disabled", icon='HIDE_ON')

        layout.separator()

        col = layout.column(align=True)
        col.prop(props, "show_verts", text="Vertices", icon='VERTEXSEL')
        col.prop(props, "show_edges", text="Edges", icon='EDGESEL')
        col.prop(props, "show_faces", text="Faces", icon='FACESEL')

        layout.separator()

        box = layout.box()
        box.label(text="Settings", icon='SETTINGS')

        box.prop(props, "use_occlusion", text="Hide Behind Geometry")

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

    # POST_PIXEL: blf стабильно работает в этом контексте.
    # Окклюзия — вручную через ray_cast (см. _is_point_visible).
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
