# Alive Cells

A collection of tools for working with and modding Dead Cells.

Join the [Official Dead Cells Discord](https://discord.gg/Ru3vqTg5RH) in #mods or the [Hashlink Modding Community Discord](https://discord.gg/Es8ZpVkPey) for support and more info on mods!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. However, the Dead Cells game and its assets are not included in this repository and are subject to their own licensing agreements, and the following licensing exemptions apply:

- The Dead Cells team, Motion Twin, and Evil Empire are hereby permitted to use this software in any way they see fit, including but not limited to modifying, distributing, and selling it.

## Tools

### PAKTool

A patched version of the game's `.pak` archive tool, used to expand and repack the `res/*.pak` files Dead Cells ships its assets in. Standalone builds are available from the [Releases](https://github.com/N3rdL0rd/alivecells/releases) page, or build it yourself from the [`PAKTool`](PAKTool) directory.

Or, alternately, on Fedora: `sudo dnf copr enable n3rdl0rd/packages && sudo dnf install paktool`

```plaintext
Usage:
  expand        <output directory> <input pak path>                     Expands a PAK of any version into a directory
  collapse      <input directory> <output pak path>                     Creates a v0 PAK from a directory, but is broken past v35
  collapsev1    <input directory> <output pak path>                     Creates a v1 PAK from a directory, bypassing the stamp verification
  creatediffpak <input pak path> <input directory> <output pak path>    Creates a v0 diff PAK, completely unmodified from the base tool
Options:
  -p, --popup-errors     Pop up a message box upon errors occuring, similarly to how the original PakTool did
  -s, --stamp <value>    Specify a custom stamp to use to bypass PAK authenticity verification past v35
  -h, --help             Display this help message
```

For most modding purposes, `expand` followed by `collapsev1` is what you want - `collapse` (v0) is broken on game versions past v35, and `creatediffpak` is unmodified from the original tool.

### savetool

Verifies, inspects, extracts, repacks, and converts Dead Cells save files (`user_0.dat` and similar). Run from the [`savetool`](savetool) directory.

```plaintext
savetool.py verify <save_file>                                Verify the checksum of a save file.
savetool.py info <save_file>                                   Display detailed information and decode primitive chunks from a save file.
savetool.py extract <save_file> <output_dir>                   Extract chunks and editable metadata from a save file.
savetool.py repack <input_dir> <output_file>                   Repack a directory of chunks into a new save file.
savetool.py edit <save_file>                                    Open a GUI editor for all chunks and metadata of a save file.
savetool.py convert <input_file> <shell_file> <output_file>    Convert a save file from one format/platform to another.
```

### stamptool

A small [standalone web app](https://n3rdl0rd.github.io/alivecells/stamptool) for calculating the "stamp" values used to authenticate `.pak` files past v35 - the same values you can pass to `PAKTool collapsev1 --stamp`. Open it directly in a browser.

### mobile/lang.py

Unpacks and repacks the unusual GNU MO files used for translations in Dead Cells mobile builds.

```plaintext
lang.py unpack <input.mo> <output.po>    Convert MO binary to readable PO text
lang.py pack <input.po> <output.mo>      Convert PO text back to binary MO
```

### tracks/

Scripts for working with `ModHelperSkin` animation tracks (as exported by the game's ModTools) in Blender:

```plaintext
tracks2blender.py <tracks.json> <animation> <output.blend>    Import a single animation from a beheadedModHelper_tracks.json file into Blender.
batch_generate.py <tracks.json> [-o output_dir] [-b blender]  Batch-generate .blend files for every animation in a tracks.json file.
```

### AtlasTool

A tool for unpacking (`Expand`) and repacking (`Collapse`) the texture atlases (`.atlas` + image files) used for the game's sprites and animations. This is based on the game's own `AtlasTool` (part of its ModTools), with a number of fixes on top - see [Modifications](#atlastool-modifications) below. Build it yourself from the [`AtlasTool`](AtlasTool) directory.

```plaintext
-? : Display this help
-Expand -outdir <output directory> -Atlas <input atlas path> [-s]: Expands a given Atlas to a file tree
-ExpandAll -indir <input atlases directory> -outdir <output directory> [-s]: Expands every atlas found in indir into outdir
-Collapse -indir <input directory> -Atlas <output atlas path> [-s][-ascii]: Collapse a given file tree to an atlas
-CollapseAll -indir <input directories> -outdir <output atlases path> [-s][-ascii]: Collapse every directory in the input directory into atlases
arguments :
-s/-silent : Do not display message error (deactivated by default)
-ascii : Export atlases as ascii (binary by default)
```

#### AtlasTool Modifications

Compared to the stock AtlasTool that ships with the game, this version:

- Fixes binary atlas packaging (`Collapse` without `-ascii`) producing atlases the game couldn't load
- Fixes a circle of duplicate pixels appearing around textures after packing
- Fixes a normal map packing offset bug, where normal maps were written with an unnecessary 1px offset
- Removes an erroneous `+1` applied to each tile's `x`/`y` position when writing the binary atlas header, which caused animation and packaging offset errors
- Fixes `Tile.atlasIndex` defaulting to `0` instead of `-1`, which caused an extra empty stream to be written into output atlas files
- Wraps bitmap copying in a try/catch to avoid crashing on malformed tiles

### alivecells.py (deprecated)

`alivecells.py` extracted the game's Hashlink bytecode and set up a standalone Hashlink VM to run it on Windows. It is no longer needed and is kept only for historical reference.