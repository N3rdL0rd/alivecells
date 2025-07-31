import json
import os
import subprocess
import argparse

def main(tracks_file, output_dir, blender_executable):
    """
    Reads a beheadedModHelper_tracks.json file and runs tracks2blender script
    for every animation found within it.
    """

    importer_script = "tracks2blender.py"

    if not os.path.exists(tracks_file):
        print(f"Error: Tracks file not found at '{tracks_file}'")
        return

    if not os.path.exists(importer_script):
        print(f"Error: Importer script '{importer_script}' not found.")
        return

    os.makedirs(output_dir, exist_ok=True)
    print(f"Created output directory: {output_dir}")

    try:
        with open(tracks_file, 'r') as f:
            data = json.load(f)
        animation_names = list(data.keys())
    except Exception as e:
        print(f"Error reading or parsing JSON file: {e}")
        return

    print(f"Found {len(animation_names)} animations to process.")

    for i, anim_name in enumerate(animation_names):
        safe_anim_name = "".join(c for c in anim_name if c.isalnum() or c in ('_', '-')).rstrip()
        output_blend_file = os.path.join(output_dir, f"{safe_anim_name}.blend")

        print(f"Processing [{i+1}/{len(animation_names)}]: {anim_name}")

        command = [
            blender_executable,
            "--background",
            "--python", importer_script,
            "--",
            tracks_file,
            anim_name,
            output_blend_file
        ]

        # Run the command
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"  -> Successfully created {output_blend_file}")
        except subprocess.CalledProcessError as e:
            print(f"  -> ERROR processing '{anim_name}'.")
            print(f"     Blender stdout: {e.stdout}")
            print(f"     Blender stderr: {e.stderr}")

    print("\nBatch generation complete.")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("tracks", help="Path to your beheadedModHelper_tracks.json")
    parser.add_argument("-o", "--output", help="Output directory", default="source_anims")
    parser.add_argument("-b", "--blender", help="Path to blender", default="blender")
    args = parser.parse_args()
    main(
        args.tracks,
        args.output,
        args.blender
    )