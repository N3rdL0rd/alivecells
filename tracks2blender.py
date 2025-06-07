"""
Tool to import Dead Cells ModHelperSkin animation tracks into Blender.
"""

import argparse
import json
import os
import sys
import bpy
import mathutils

def clear_animation_data():
    """Clear existing animation data to prevent conflicts"""
    for obj in bpy.data.objects:
        if obj.animation_data:
            obj.animation_data_clear()

def map_z(z):
    """Map Z coordinate from Dead Cells to Blender"""
    return z # TODO

def map_xy(val):
    """Map X and Y coordinates from Dead Cells to Blender"""
    # somehow this is also fucked, so we need to map them from 0 to 100-ish to 0 to 1
    return val / 100.0

def import_tracks(tracks_file, animation_name, output_file):
    """Import tracks from JSON file into Blender"""
    try:
        with open(tracks_file, 'r') as f:
            tracks_data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading tracks file: {e}")
        return False
    
    if animation_name not in tracks_data:
        print(f"Animation '{animation_name}' not found in tracks file")
        available_animations = list(tracks_data.keys())
        print(f"Available animations: {', '.join(available_animations[:10])}")
        if len(available_animations) > 10:
            print(f"... and {len(available_animations) - 10} more")
        return False
    
    animation = tracks_data[animation_name]
    
    # delete default cube
    if "Cube" in bpy.data.objects:
        cube = bpy.data.objects["Cube"]
        bpy.data.objects.remove(cube, do_unlink=True)
    
    if "Armature" not in bpy.data.objects:
        bpy.ops.object.armature_add()
        armature_obj = bpy.data.objects["Armature"]
    else:
        armature_obj = bpy.data.objects["Armature"]
    
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    edit_bones = armature_obj.data.edit_bones
    
    # delete default "Bone" that's created with the armature
    if "Bone" in edit_bones:
        edit_bones.remove(edit_bones["Bone"])
    
    for bone_name in animation.keys():
        if bone_name not in edit_bones:
            bone = edit_bones.new(bone_name)
            bone.head = (0, 0, 0)
            bone.tail = (0, 0.1, 0)
    
    bpy.ops.object.mode_set(mode='POSE')
    
    clear_animation_data()
    
    action = bpy.data.actions.new(animation_name)
    armature_obj.animation_data_create()
    armature_obj.animation_data.action = action
    
    # make sure the z values aren't all 0 or 1, since some versions of the game have a bug where they round to nearest, which causes the animation to be flat
    for track in animation.values():
        all_z = []
        for i in range(2, len(track), 3):
            all_z.append(track[i])
        if all(all_z) or all(not z for z in all_z):
            print(f"Warning: Z values for animation '{animation_name}' are all 0 or 1. Please check the animation data (this is present from >v34 and cannot be fixed, use <=v33).")
            break
    
    fps = 24.0
    for bone_name, track in animation.items():
        if bone_name not in armature_obj.pose.bones:
            print(f"Warning: Bone '{bone_name}' not found in armature")
            continue
        
        bone = armature_obj.pose.bones[bone_name]

        vectors = []
        for i in range(0, len(track), 3):
            if i+2 < len(track):
                x, y, z = track[i], track[i+1], track[i+2]
                z = map_z(z)
                x, y = map_xy(x), map_xy(y)
                # everything is right in terms of scale, but in the tracks, the Y axis is up, whereas in Blender, the Z axis is up
                vectors.append(mathutils.Vector((x, z, -y)))
        
        for frame, position in enumerate(vectors):
            bone.location = position
            bone.keyframe_insert(data_path="location", frame=frame)
    
    max_frames = 0
    for track in animation.values():
        frames = len(track) // 3
        max_frames = max(max_frames, frames)
    
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = max_frames - 1
    
    bpy.ops.wm.save_as_mainfile(filepath=output_file)
    print(f"Animation '{animation_name}' imported and saved to {output_file}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Import Dead Cells ModHelperSkin animation tracks into Blender.")
    parser.add_argument("input", help="Path to the beheadedModHelper_tracks.json file from your game's ModTools.")
    parser.add_argument("animation", help="Name of the animation to import.")
    parser.add_argument("output", help="Path to the output .blend file.")

    args = parser.parse_args()
    
    os.remove(args.output) if os.path.exists(args.output) else None
    
    if bpy is None:
        blender_path = "blender"
        blender_args = ["--background", "--python", __file__, "--", args.input, args.animation, args.output]
        os.execvp(blender_path, [blender_path] + blender_args)
    else:
        import_tracks(args.input, args.animation, args.output)

if __name__ == "__main__":
    try:
        import bpy
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1:]
            if len(argv) == 3:
                import_tracks(argv[0], argv[1], argv[2])
            else:
                print("Usage (inside Blender): blender --background --python tracks2blender.py -- input.json animation_name output.blend")
        else:
            main()
    except ImportError:
        import bpy
        main()