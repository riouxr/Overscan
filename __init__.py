import bpy

# Global dictionary to store original sizes of background images
original_bg_image_scales = {}

bl_info = {
    "name": "Overscan Render",
    "author": "Blender Bob ChatGPT",
    "version": (1, 0, 2),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Overscan Tab",
    "description": "Adjust render size with various options, modify camera attributes, and handle safe areas",
    "category": "Render",
}

class OverscanPanel(bpy.types.Panel):
    bl_label = "Overscan"
    bl_idname = "RENDER_PT_overscan"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'output'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        overscan = scene.overscan_settings
        layout.use_property_split = False
        layout.use_property_decorate = True

        col = layout.column_flow(columns=3, align=True)
        col.prop(overscan, "overscan_panel", icon="DOWNARROW_HLT" if overscan.overscan_panel else "RIGHTARROW", text="Overscan", emboss=False)

        if overscan.overscan_panel:
            layout.prop(overscan, "mode")
            if overscan.mode == 'PERCENTAGE':
                layout.prop(overscan, "percentage")
            elif overscan.mode == 'PIXELS':
                layout.prop(overscan, "extra_pixels")
            else:
                layout.prop(overscan, "specific_x_resolution")

            row = layout.row(align=True)
            row.operator("render.apply_overscan")
            row.operator("render.revert_overscan")

class OverscanSettings(bpy.types.PropertyGroup):
    mode_items = [
        ('PERCENTAGE', "Percentage", ""),
        ('PIXELS', "Extra Pixels", ""),
        ('SPECIFIC_X', "Specific X Resolution", "")
    ]
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=mode_items,
        description="Choose the method for overscan",
        default='PERCENTAGE'
    )
    percentage: bpy.props.FloatProperty(
        name="Percentage",
        description="Percentage of overscan to apply to the render",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )
    extra_pixels: bpy.props.IntProperty(
        name="Extra Pixels",
        description="Number of extra pixels to add to the render dimensions",
        default=0,
        min=0
    )
    specific_x_resolution: bpy.props.IntProperty(
        name="Specific X Resolution",
        description="Set a specific X resolution while maintaining aspect ratio",
        default=1920,
        min=1
    )
    original_width: bpy.props.IntProperty(name="Original Width")
    original_height: bpy.props.IntProperty(name="Original Height")
    original_sensor_width: bpy.props.FloatProperty(name="Original Sensor Width")
    overscan_panel: bpy.props.BoolProperty(name="Overscan", default=True)

class ApplyOverscan(bpy.types.Operator):
    bl_idname = "render.apply_overscan"
    bl_label = "Apply"

    def execute(self, context):
        scene = context.scene
        camera = scene.camera.data
        overscan = scene.overscan_settings
        safe_areas = scene.safe_areas
        active_camera = scene.camera

        # Check if overscan has already been applied
        if 'overscan_applied' in camera and camera['overscan_applied']:
            self.report({'WARNING'}, "Overscan already applied. Revert before applying again.")
            return {'CANCELLED'}

        # Store original values
        camera['original_width'] = scene.render.resolution_x
        camera['original_height'] = scene.render.resolution_y
        if camera.type == 'ORTHO':
            camera['original_ortho_scale'] = camera.ortho_scale
        else:
            camera['original_sensor_width'] = camera.sensor_width

        # Apply overscan changes based on the selected mode
        if overscan.mode == 'PERCENTAGE':
            new_safe_area = (((100 / (overscan.percentage + 100)) - 1) * -1)
            safe_areas.action = (new_safe_area, new_safe_area)
            safe_areas.title = (1, 1)

        elif overscan.mode == 'PIXELS':
            extra_pixels_x = overscan.extra_pixels
            extra_pixels_y = overscan.extra_pixels
            new_safe_area_x = (extra_pixels_x / 2) / (extra_pixels_x + camera['original_width']) * 2
            new_safe_area_y = (extra_pixels_y / 2) / (extra_pixels_y + camera['original_height']) * 2
            safe_areas.action = (new_safe_area_x, new_safe_area_y)
            safe_areas.title = (1, 1)

        else:  # SPECIFIC_X
            specific_x_resolution = overscan.specific_x_resolution
            new_safe_area = ((specific_x_resolution - camera['original_width']) / specific_x_resolution)
            safe_areas.action = (new_safe_area, new_safe_area)
            safe_areas.title = (1, 1)

        # Adjust render resolution
        if overscan.mode == 'PERCENTAGE':
            overscan_value = overscan.percentage / 100
            new_width = round(camera['original_width'] * (1 + overscan_value))
            new_height = round(camera['original_height'] * (1 + overscan_value))
        elif overscan.mode == 'PIXELS':
            new_width = camera['original_width'] + overscan.extra_pixels
            new_height = camera['original_height'] + overscan.extra_pixels
        else:  # SPECIFIC_X
            aspect_ratio = camera['original_height'] / camera['original_width']
            new_width = overscan.specific_x_resolution
            new_height = round(new_width * aspect_ratio)

        scene.render.resolution_x = new_width
        scene.render.resolution_y = new_height

        # Adjust scale factor and camera attributes
        scale_factor = new_width / camera['original_width']
        if camera.type == 'ORTHO':
            camera.ortho_scale = camera['original_ortho_scale'] * scale_factor
        else:
            camera.sensor_width = camera['original_sensor_width'] * scale_factor

        # Background image scaling
        if camera.type == 'ORTHO':
            scale = camera['original_ortho_scale'] / camera.ortho_scale
        else:
            scale = camera['original_sensor_width'] / camera.sensor_width

        for index, bg_image in enumerate(camera.background_images):
            if hasattr(bg_image, 'scale'):
                camera[f"bg_image_scale_{index}"] = bg_image.scale
        for bg_image in camera.background_images:
            if hasattr(bg_image, 'scale'):
                bg_image.scale *= scale

        if not active_camera.name.endswith("_o"):
            active_camera.name += "_o"

        active_camera.data.show_safe_areas = True
        camera['overscan_applied'] = True

        return {'FINISHED'}

class RevertOverscan(bpy.types.Operator):
    bl_idname = "render.revert_overscan"
    bl_label = "Revert"

    def execute(self, context):
        scene = context.scene
        camera = scene.camera.data
        safe_areas = scene.safe_areas
        active_camera = scene.camera

        scene.render.resolution_x = camera.get('original_width', scene.overscan_settings.original_width)
        scene.render.resolution_y = camera.get('original_height', scene.overscan_settings.original_height)

        if camera.type == 'ORTHO':
            camera.ortho_scale = camera.get('original_ortho_scale', camera.ortho_scale)
        else:
            camera.sensor_width = camera.get('original_sensor_width', camera.sensor_width)

        for index, bg_image in enumerate(camera.background_images):
            if hasattr(bg_image, 'scale'):
                property_name = f"bg_image_scale_{index}"
                if property_name in camera:
                    bg_image.scale = camera[property_name]

        safe_areas.action = (1, 1)
        safe_areas.title = (1, 1)

        if active_camera.name.endswith("_o"):
            active_camera.name = active_camera.name[:-2]

        camera['overscan_applied'] = False
        return {'FINISHED'}

def register():
    bpy.utils.register_class(OverscanSettings)
    bpy.utils.register_class(ApplyOverscan)
    bpy.utils.register_class(RevertOverscan)
    bpy.utils.register_class(OverscanPanel)
    bpy.types.Scene.overscan_settings = bpy.props.PointerProperty(type=OverscanSettings)

def unregister():
    bpy.utils.unregister_class(OverscanSettings)
    bpy.utils.unregister_class(ApplyOverscan)
    bpy.utils.unregister_class(RevertOverscan)
    bpy.utils.unregister_class(OverscanPanel)
    del bpy.types.Scene.overscan_settings

if __name__ == "__main__":
    register()
