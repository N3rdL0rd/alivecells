import warnings
import os
from urllib.request import urlretrieve
import zipfile
import argparse
import shutil
from tqdm import tqdm
import win32api # type: ignore
import win32con # type: ignore
from pathlib import Path
import vdf

# region Constants
OUTPUT = "hlboot.dat" # Default output filename
MAGIC_HEADER = b"\x48\x4C\x42" # "HLB" for hashlink bytecode
END_PADDING = b"\x58\x50\x41\x44\x44\x49\x4e\x47\x50\x41\x44\x44\x49\x4e\x47\x58" # "XPADDINGPADDINGX" repeating until the nearest 64-byte boundary
HLVM_URL = "https://github.com/HaxeFoundation/hashlink/releases/download/1.10/hl-1.10.0-win.zip"
GOLDBERG_URL = "https://gitlab.com/Mr_Goldberg/goldberg_emulator/-/jobs/4247811310/artifacts/download" # sometimes the game will complain about the steam api not working - we can bypass this with goldberg
GOLDBERG_DLL = "steam_api.dll"
# endregion

# region Utility functions
def copy_file_with_progress(src, dst, buffer_size=1024*1024, msg="Copying"):
    file_size = os.path.getsize(src)
    with tqdm(total=file_size, unit='B', unit_scale=True, desc=msg) as pbar:
        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            while True:
                buf = fsrc.read(buffer_size)
                if not buf:
                    break
                fdst.write(buf)
                pbar.update(len(buf))

def extract_bytecode(exe_path):
    with open(exe_path, "rb") as f:
        exe_data = f.read()
    hlb_start = exe_data.find(MAGIC_HEADER)
    if hlb_start == -1:
        raise ValueError("Hashlink bytecode not found in executable.")
    hlb_data = exe_data[hlb_start:]
    hlb_end = hlb_data.find(END_PADDING)
    if hlb_end == -1:
        warnings.warn("End padding not found in hashlink bytecode.")
        hlb_end = len(hlb_data)
    hlb_data = hlb_data[:hlb_end]
    return hlb_data

def change_ico(exe, ico):
    try:
        hExe = win32api.BeginUpdateResource(exe, False)
        with open(ico, 'rb') as icon_file:
            icon_data = icon_file.read()
        win32api.UpdateResource(hExe, win32con.RT_GROUP_ICON, 1, icon_data)
        win32api.EndUpdateResource(hExe, False)
    except Exception as e:
        print(f"Error: {e}")

def add_steam_shortcut(app_name, exe_path, steam_path="C:/Program Files (x86)/Steam", launch_options="", icon_path="", logo_path="", hero_path="", grid_path="", p_path=""):
    steam_path = Path(steam_path)
    userdata_path = steam_path / "userdata"
    user_id = next(os.walk(userdata_path))[1][0]
    shortcuts_path = userdata_path / user_id / "config" / "shortcuts.vdf"
    with open(shortcuts_path, 'rb') as f:
        shortcuts = vdf.binary_load(f)
    new_app_id = str(max(int(k) for k in shortcuts['shortcuts'].keys()) + 1)
    shortcuts['shortcuts'][new_app_id] = {
        "appname": app_name,
        "exe": f'"{exe_path}"',
        "StartDir": str(Path(exe_path).parent),
        "icon": icon_path,
        "ShortcutPath": "",
        "LaunchOptions": launch_options,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "LastPlayTime": 0
    }
    with open(shortcuts_path, 'wb') as f:
        vdf.binary_dump(shortcuts, f)
    artwork_path = userdata_path / user_id / "config" / "grid"
    app_id = str(int(new_app_id) | 0x80000000)  # Convert to uint32
    if logo_path:
        shutil.copy(logo_path, artwork_path / f"{app_id}_logo.png")
    if hero_path:
        shutil.copy(hero_path, artwork_path / f"{app_id}_hero.png")
    if grid_path:
        shutil.copy(grid_path, artwork_path / f"{app_id}.png")
    if p_path:
        shutil.copy(p_path, artwork_path / f"{app_id}p.png")
# endregion

# region Main functions
def add_vm(dir, game_path, output="hlboot.dat", extract=True, goldberg=False):
    shutil.rmtree(dir, ignore_errors=True)
    os.makedirs(dir, exist_ok=True)
    print("Downloading Hashlink VM...")
    urlretrieve(HLVM_URL, "hlvm.zip")
    with zipfile.ZipFile("hlvm.zip", "r") as zip_ref:
        zip_ref.extractall(dir)
    os.remove("hlvm.zip")
    for f in os.listdir(os.path.join(dir, "hl-1.10.0-win")):
        os.rename(os.path.join(dir, "hl-1.10.0-win", f), os.path.join(dir, f))
    os.rmdir(os.path.join(dir, "hl-1.10.0-win"))
    print("Hashlink VM downloaded and extracted to \"{}\".".format(dir))
    if extract:
        print("Extracting bytecode from executable...")
        hlb_data = extract_bytecode(os.path.join(game_path, "deadcells.exe"))
        with open(os.path.join(dir, output), "wb") as f:
            f.write(hlb_data)
        print("Hashlink bytecode extracted and saved to \"{}\".".format(os.path.join(dir, output)))
    print("Copying game dependencies...")
    ignore_end = [".pak", ".exe", ".idb"]
    ignore_dir = ["ModTools", "UnpackedFiles", "UnpackedCDB"] # just in case someone was poking around
    for root, dirs, files in os.walk(game_path):
        for d in ignore_dir:
            if d in dirs:
                dirs.remove(d)
        for f in files:
            if any(f.endswith(end) for end in ignore_end):
                continue
            src = os.path.join(root, f)
            rel_path = os.path.relpath(root, game_path)
            dst = os.path.join(dir, rel_path, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    print("Game dependencies copied to \"{}\".".format(dir))
    copy_file_with_progress(os.path.join(game_path, "res.pak"), os.path.join(dir, "res.pak"), msg="Copying res.pak")
    if goldberg:
        print("Downloading Goldberg Emulator... (this may take a while)")
        os.makedirs(os.path.join(dir, "Goldberg"), exist_ok=True)
        urlretrieve(GOLDBERG_URL, "goldberg.zip")
        with zipfile.ZipFile("goldberg.zip", "r") as zip_ref:
            zip_ref.extractall(os.path.join(dir, "Goldberg"))
        os.remove("goldberg.zip")
        print("Copying Goldberg DLL...")
        shutil.move(os.path.join(dir, GOLDBERG_DLL), os.path.join(dir, GOLDBERG_DLL + ".bak"))
        shutil.copy2(os.path.join(dir, "Goldberg", GOLDBERG_DLL), os.path.join(dir, GOLDBERG_DLL))
    with open(os.path.join(dir, "steam_appid.txt"), "w") as f:
        f.write("588650")
    print("Cleaning up...")
    cleanup = [".lib"]
    cleanup_specific = ["your game content lives here.txt", "ThirdPartyLicenses.txt"]
    for root, dirs, files in os.walk(dir):
        for f in files:
            if any(f.endswith(end) for end in cleanup):
                os.remove(os.path.join(root, f))
    for f in cleanup_specific:
        try:
            os.remove(os.path.join(dir, f))
        except FileNotFoundError:
            pass
    if goldberg:
        shutil.rmtree(os.path.join(dir, "Goldberg"), ignore_errors=True)
    print("Changing icon...")
    ico = os.path.join(os.path.dirname(__file__), "assets", "icon-16.ico")
    print("Using icon from \"{}\".".format(ico))
    change_ico(os.path.join(dir, "hl.exe"), ico)
    print("Dead Cells is now ready to be run unpacked under the Hashlink VM. Have fun!")
    
def repair(dir, game_path, output="hlboot.dat", restore_respak=False):
    if not os.path.exists(dir):
        raise FileNotFoundError("Hashlink VM install directory not found.")
    print("Restoring Hashlink bytecode...")
    hlb_data = extract_bytecode(os.path.join(game_path, "deadcells.exe"))
    with open(os.path.join(dir, output), "wb") as f:
        f.write(hlb_data)
    if restore_respak:
        copy_file_with_progress(os.path.join(game_path, "res.pak"), os.path.join(dir, "res.pak"), msg="Restoring res.pak")
    print("Hashlink bytecode restored and saved to \"{}\".".format(os.path.join(dir, output)))
    print("Repair complete.")
# endregion

# region Main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Hashlink bytecode from Dead Cells executable and prepare it for execution.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_vm_parser = subparsers.add_parser("install", help="Install the Hashlink VM in a given folder and copy over game bytecode and dependencies.")
    add_vm_parser.add_argument("dir", help="The directory to install the Hashlink VM in.")
    add_vm_parser.add_argument("game_path", help="The path to the Dead Cells game directory.")
    add_vm_parser.add_argument("--output", default="hlboot.dat", help="The output filename for the Hashlink bytecode.")
    add_vm_parser.add_argument("--no-extract", action="store_true", help="Do not extract Hashlink bytecode from the executable - will require you to provide your own hlboot.dat.")
    add_vm_parser.add_argument("--goldberg", action="store_true", help="Use Goldberg Emulator to bypass Steam API issues - generally not required.")
    
    extract_parser = subparsers.add_parser("extract", help="Extract Hashlink bytecode from the Dead Cells executable.")
    extract_parser.add_argument("exe_path", help="The path to the Dead Cells executable (deadcells.exe, not deadcells_gl.exe).")
    extract_parser.add_argument("--output", default="hlboot.dat", help="The output filename for the Hashlink bytecode.")
    extract_parser.add_argument("--in-game-dir", action="store_true", help="Save the Hashlink bytecode in the Dead Cells game directory as well as the current directory.")

    repair_parser = subparsers.add_parser("repair", help="Repair a Hashlink VM installation of Dead Cells with the original bytecode and assets.")
    repair_parser.add_argument("dir", help="The directory containing the Hashlink VM installation.")
    repair_parser.add_argument("game_path", help="The path to the Dead Cells game directory.")
    repair_parser.add_argument("--output", default="hlboot.dat", help="The output filename for the Hashlink bytecode.")
    repair_parser.add_argument("-r", "--restore-respak", action="store_true", help="Restore the res.pak file from the game directory.")

    steam_parser = subparsers.add_parser("steam", help="Add a shortcut to your Steam Library for the Hashlink VM installation.")
    steam_parser.add_argument("dir", help="The directory containing the Hashlink VM installation.")

    args = parser.parse_args()

    if args.command == "install":
        add_vm(args.dir, args.game_path, output=args.output, extract=not args.no_extract, goldberg=args.goldberg)
    elif args.command == "extract":
        hlb_data = extract_bytecode(args.exe_path)
        with open(args.output, "wb") as f:
            f.write(hlb_data)
        print("Hashlink bytecode extracted and saved to \"{}\".".format(args.output))
        if args.in_game_dir:
            with open(os.path.join(os.path.dirname(args.exe_path), args.output), "wb") as f:
                f.write(hlb_data)
            print("Hashlink bytecode also saved to \"{}\".".format(os.path.join(os.path.dirname(args.exe_path), args.output)))
    elif args.command == "repair":
        repair(args.dir, args.game_path, output=args.output, restore_respak=args.restore_respak)
    elif args.command == "steam":
        add_steam_shortcut("Alive Cells", os.path.abspath(os.path.join(args.dir, "hl.exe")), \
                           icon_path=os.path.join(os.path.dirname(__file__), "assets", "bluecells.png"), \
                           launch_options="hlboot.dat", \
                           logo_path=os.path.join(os.path.dirname(__file__), "assets", "alivecells.png"), \
                           hero_path=os.path.join(os.path.dirname(__file__), "assets", "hero.png"), \
                           grid_path=os.path.join(os.path.dirname(__file__), "assets", "grid.png"), \
                           p_path=os.path.join(os.path.dirname(__file__), "assets", "grid2.png"))
    else:
        raise ValueError("Invalid command.")
# endregion
