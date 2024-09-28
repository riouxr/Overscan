# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy

# Global dictionary to store original sizes of background images
original_bg_image_scales = {}   

bl_info = {
    "name": "Overscan Render",
    "author": "Blender Bob, Chat GPT",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Overscan Tab",
    "description": "Adjust render size with various options and modify camera attributes",
    "support": "COMMUNITY"
    "category": "Render",
}

class OverscanPanel(bpy.types.Panel):
    bl_label = "Overscan"
    bl_idname = "RENDER_PT_overscan"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        overscan = scene.overscan_settings

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
        name = "Percentage",
        description = "Percentage of overscan to apply to the render",
        default = 0.0,
        min = 0.0,
        max = 100.0,
        subtype = 'PERCENTAGE'
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
    settings_stored: bpy.props.BoolProperty(name="Settings Stored", default=False)
     

class ApplyOverscan(bpy.types.Operator):
    bl_idname = "render.apply_overscan"
    bl_label = "Apply"

    def execute(self, context):
        scene = context.scene
        camera = scene.camera.data
        overscan = scene.overscan_settings

        # Check if overscan has already been applied
        if 'overscan_applied' in camera and camera['overscan_applied']:
            self.report({'WARNING'}, "Overscan already applied. Revert before applying again.")
            return {'CANCELLED'}

        # Store original values
        camera['original_width'] = scene.render.resolution_x
        camera['original_height'] = scene.render.resolution_y
        camera['original_sensor_width'] = camera.sensor_width

        # Apply overscan changes based on the selected mode
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

        # Adjust render resolution
        scene.render.resolution_x = new_width
        scene.render.resolution_y = new_height

        # Adjust sensor width proportionally
        sensor_scale = new_width / camera['original_width']
        camera.sensor_width = camera['original_sensor_width'] * sensor_scale

        # Append '_o' to camera name if not already done
        if not scene.camera.name.endswith('_o'):
            scene.camera.name += '_o'

        # Store original scales of background images as separate properties
        for index, bg_image in enumerate(camera.background_images):
            if hasattr(bg_image, 'scale'):
                camera[f"bg_image_scale_{index}"] = bg_image.scale


        # Calculate and apply scale factor for background images
        scale_factor = camera['original_sensor_width'] / camera.sensor_width
        for bg_image in camera.background_images:
            if hasattr(bg_image, 'scale'):
                bg_image.scale *= scale_factor

        # Set flag indicating that overscan has been applied
        camera['overscan_applied'] = True

        return {'FINISHED'}


class RevertOverscan(bpy.types.Operator):
    bl_idname = "render.revert_overscan"
    bl_label = "Revert"

    def execute(self, context):
        scene = context.scene
        camera = scene.camera.data

        # Revert render resolution and sensor width
        camera.sensor_width = camera.get('original_sensor_width', scene.overscan_settings.original_sensor_width)
        scene.render.resolution_x = camera.get('original_width', scene.overscan_settings.original_width)
        scene.render.resolution_y = camera.get('original_height', scene.overscan_settings.original_height)

        # Remove '_o' from camera name if present
        if scene.camera.name.endswith('_o'):
            scene.camera.name = scene.camera.name[:-2]

        # Revert the scale of background images from custom properties
        for index, bg_image in enumerate(camera.background_images):
            if hasattr(bg_image, 'scale'):
                property_name = f"bg_image_scale_{index}"
                if property_name in camera:
                    bg_image.scale = camera[property_name]

        # Reset the overscan applied flag
        camera['overscan_applied'] = False

        return {'FINISHED'}




def register():
    bpy.utils.register_class(OverscanPanel)
    bpy.utils.register_class(OverscanSettings)
    bpy.utils.register_class(ApplyOverscan)
    bpy.utils.register_class(RevertOverscan)
    bpy.types.Scene.overscan_settings = bpy.props.PointerProperty(type=OverscanSettings)

def unregister():
    bpy.utils.unregister_class(OverscanPanel)
    bpy.utils.unregister_class(OverscanSettings)
    bpy.utils.unregister_class(ApplyOverscan)
    bpy.utils.unregister_class(RevertOverscan)
    del bpy.types.Scene.overscan_settings

if __name__ == "__main__":
    register()

