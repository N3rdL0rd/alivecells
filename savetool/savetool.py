#!/usr/bin/env python3

"""
Tool for working with Dead Cells save files. Allows verification, extraction, repacking, and basic conversion.
"""

import hashlib
import argparse
import sys
import zlib
from pathlib import Path
import tempfile
import shutil
import io
import os
import struct
import toml
import datetime

# --- Constants and Maps ---
MAGIC_NUMBER = 0x11CEADDE # DE AD CE 11
CHECKSUM_OFFSET = 5
CHECKSUM_SIZE = 20
HEADER_FORMAT = "<I B 20s 20s 10s I"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

SAVE_CONTENT_MAP = {
    0: "S_User", 1: "S_Game", 2: "S_UserAndGameData", 3: "S_Date",
    7: "S_VersionNumber", 8: "S_DLCMask",
}

FEATURE_FLAG_MAP = {
    4: "S_Experimental", 5: "S_UsesMods", 6: "S_HaveLore",
}

DLC_MAP = {
    0: "Rise of the Giant",
    1: "The Bad Seed",
    2: "Fatal Falls",
    3: "The Queen and the Sea",
    4: "Return to Castlevania",
}

HXBIT_CHUNK_BITS = {0, 1, 2}


def parse_save_bytes(save_data: bytes):
    if len(save_data) < HEADER_SIZE:
        raise ValueError("File is too small to be a valid save file.")
    magic, version, stored_checksum, git_hash, build_date_bytes, flags_int = struct.unpack(
        HEADER_FORMAT, save_data[:HEADER_SIZE]
    )
    if magic != MAGIC_NUMBER:
        raise ValueError(f"Bad magic number {magic:#010x} (expected {MAGIC_NUMBER:#010x}).")
    payload = zlib.decompress(save_data[HEADER_SIZE:])
    reader = io.BytesIO(payload)
    chunks = {}
    for bit in range(32):
        if (flags_int >> bit) & 1 and bit in SAVE_CONTENT_MAP:
            chunk_len = struct.unpack('<I', reader.read(4))[0]
            chunks[bit] = reader.read(chunk_len)
    header = {
        'version': version,
        'git_hash': git_hash,
        'build_date': build_date_bytes.decode('utf-8').strip(),
        'flags': flags_int,
        'stored_checksum': stored_checksum,
    }
    return header, chunks


def build_save_bytes(version: int, git_hash: bytes, build_date: str, flags_int: int,
                     chunks: dict) -> bytes:
    payload = io.BytesIO()
    for bit in sorted(chunks):
        payload.write(struct.pack('<I', len(chunks[bit])))
        payload.write(chunks[bit])
    compressed = zlib.compress(payload.getvalue(), level=9)
    header = struct.pack(
        HEADER_FORMAT, MAGIC_NUMBER, version, b'\x00' * CHECKSUM_SIZE,
        git_hash, build_date.encode('utf-8'), flags_int,
    )
    final = bytearray(header + compressed)
    final[CHECKSUM_OFFSET:CHECKSUM_OFFSET + CHECKSUM_SIZE] = hashlib.sha1(final).digest()
    return bytes(final)

def verify_save_checksum(file_path: Path, verbose=True) -> bool:
    """
    Performs the core logic of verifying the SHA-1 checksum.

    Args:
        file_path: A Path object pointing to the save file.
        verbose: If True, prints detailed steps.

    Returns:
        True if the checksum is valid, False otherwise.
    """
    if verbose:
        print(f"[*] Verifying checksum for: {file_path.name}")
    
    try:
        with open(file_path, 'rb') as f:
            save_data = f.read()
    except Exception as e:
        print(f"[!] An error occurred while reading the file: {e}", file=sys.stderr)
        return False

    if len(save_data) < (CHECKSUM_OFFSET + CHECKSUM_SIZE):
        print("[!] Error: File is too small to be a valid save file.", file=sys.stderr)
        return False

    stored_checksum = save_data[CHECKSUM_OFFSET : CHECKSUM_OFFSET + CHECKSUM_SIZE]
    if verbose:
        print(f"  > Stored Checksum:   {stored_checksum.hex()}")

    data_for_hashing = bytearray(save_data)
    checksum_placeholder = b'\x00' * CHECKSUM_SIZE
    data_for_hashing[CHECKSUM_OFFSET : CHECKSUM_OFFSET + CHECKSUM_SIZE] = checksum_placeholder
    
    calculated_checksum = hashlib.sha1(data_for_hashing).digest()
    if verbose:
        print(f"  > Calculated Checksum: {calculated_checksum.hex()}")
    
    return stored_checksum == calculated_checksum

def handle_verify(args: argparse.Namespace):
    """Handler for the 'verify' subcommand."""
    save_file_path = Path(args.save_file)

    if not save_file_path.is_file():
        print(f"[!] Error: File not found at '{save_file_path}'", file=sys.stderr)
        sys.exit(1)

    is_valid = verify_save_checksum(save_file_path, verbose=True)
    
    if is_valid:
        print("\n[+] SUCCESS: Checksum is VALID!")
        sys.exit(0)
    else:
        print("\n[!] FAILURE: Checksum is INVALID! The file may be corrupt or modified.")
        sys.exit(1)

def handle_info(args: argparse.Namespace):
    """Handler for the 'info' subcommand to print details about a save file."""
    save_file_path = Path(args.save_file)

    if not save_file_path.is_file():
        print(f"[!] Error: File not found at '{save_file_path}'", file=sys.stderr)
        sys.exit(1)

    print(f"--- Save File: {save_file_path.name} ---")

    # 1. Verify checksum first
    is_valid = verify_save_checksum(save_file_path, verbose=False)
    status = "VALID" if is_valid else "INVALID (file may be corrupt!)"
    
    with open(save_file_path, 'rb') as f:
        save_data = f.read()

    # 2. Unpack and print header info
    magic, version, stored_checksum, git_hash, build_date_bytes, flags_int = struct.unpack(HEADER_FORMAT, save_data[:HEADER_SIZE])
    
    print("\n[ Header Information ]")
    print(f"  - Checksum Status:   {status}")
    print(f"  - Magic Number:      {magic:#010x}")
    print(f"  - Format Version:    {version}")
    print(f"  - Git Commit Hash:   {git_hash.hex()}")
    print(f"  - Build Date:        {build_date_bytes.decode('utf-8').strip()}")
    
    # 3. Analyze and print flags
    print("\n[ Flags Analysis ]")
    print(f"  - Raw Flags Value:   {flags_int:#010x}")
    all_flags_map = SAVE_CONTENT_MAP | FEATURE_FLAG_MAP
    for bit in range(32):
        if (flags_int >> bit) & 1:
            flag_name = all_flags_map.get(bit, f"Unknown_Bit_{bit}")
            flag_type = "[Data Chunk]" if bit in SAVE_CONTENT_MAP else "[Feature Flag]"
            print(f"    - Bit {bit:<2} {flag_type:<13} {flag_name}")

    # 4. Analyze payload
    print("\n[ Payload Information ]")
    compressed_payload = save_data[HEADER_SIZE:]
    print(f"  - Compressed Size:     {len(compressed_payload)} bytes")
    try:
        decompressed_payload = zlib.decompress(compressed_payload)
        print(f"  - Decompressed Size:   {len(decompressed_payload)} bytes")
        
        print("  - Data Chunks Present:")
        payload_reader = io.BytesIO(decompressed_payload)
        for bit in range(32):
            if (flags_int >> bit) & 1 and bit in SAVE_CONTENT_MAP:
                chunk_name = SAVE_CONTENT_MAP[bit]
                try:
                    chunk_len = struct.unpack('<I', payload_reader.read(4))[0]
                    chunk_data = payload_reader.read(chunk_len)
                    
                    print(f"    - {chunk_name:<18} {chunk_len:>6} bytes", end="")
                    
                    # --- Primitive Chunk Decoding Logic ---
                    if bit == 3 and chunk_len == 8: # S_Date (double)
                        timestamp = struct.unpack('<d', chunk_data)[0]
                        date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        print(f" -> {date_str}")
                    elif bit == 7 and chunk_len == 4: # S_VersionNumber (float)
                        version_float = struct.unpack('<f', chunk_data)[0]
                        print(f" -> Version: {version_float:.1f}")
                    elif bit == 8 and chunk_len == 4: # S_DLCMask (int)
                        dlc_mask = struct.unpack('<I', chunk_data)[0]
                        print(f" -> Mask: {dlc_mask} ({dlc_mask:#010x})")
                        for dlc_bit, dlc_name in DLC_MAP.items():
                            is_owned = (dlc_mask & (1 << dlc_bit)) != 0
                            status_str = "Owned" if is_owned else "Not Owned"
                            print(f"        - {dlc_name:<25}: {status_str}")
                    else: # hxbit or other complex data
                        print(" (hxbit data)")

                except (struct.error, IndexError):
                    print(f"\n    - {chunk_name:<18} ERROR: Could not read full chunk.")
                    break

    except zlib.error as e:
        print(f"  - Decompression failed: {e}")

    sys.exit(0)

def handle_extract(args: argparse.Namespace):
    """
    Extracts save file chunks and creates an editable metadata.toml.
    """
    save_file_path = Path(args.save_file)
    output_dir_path = Path(args.output_dir)

    if not save_file_path.is_file():
        print(f"[!] Error: File not found at '{save_file_path}'", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Reading save file: {save_file_path.name}")
    with open(save_file_path, 'rb') as f:
        save_data = f.read()

    if len(save_data) < HEADER_SIZE:
        print("[!] Error: File is too small to be a valid save file.", file=sys.stderr)
        sys.exit(1)

    # 1. Parse header and decompress payload
    _, version, _, git_hash, build_date_bytes, flags_int = struct.unpack(HEADER_FORMAT, save_data[:HEADER_SIZE])
    print(f"[*] Found flags: {flags_int:#010x}")
    decompressed_payload = zlib.decompress(save_data[HEADER_SIZE:])
    print(f"[+] Payload decompressed successfully ({len(decompressed_payload)} bytes).")

    # 2. Create output directory and extract chunks
    os.makedirs(output_dir_path, exist_ok=True)
    print(f"[*] Extracting chunks into directory: {output_dir_path}")
    payload_reader = io.BytesIO(decompressed_payload)
    for bit in range(32):
        if (flags_int >> bit) & 1 and bit in SAVE_CONTENT_MAP:
            chunk_name = SAVE_CONTENT_MAP[bit]
            chunk_len = struct.unpack('<I', payload_reader.read(4))[0]
            chunk_data = payload_reader.read(chunk_len)
            chunk_filepath = output_dir_path / f"Bit_{bit:02d}_{chunk_name}.bin"
            with open(chunk_filepath, 'wb') as out_f:
                out_f.write(chunk_data)
            print(f"    -> Extracted {chunk_name} ({len(chunk_data)} bytes)")

    # 3. Save detailed, editable metadata
    flag_details = {}
    all_flags_map = SAVE_CONTENT_MAP | FEATURE_FLAG_MAP
    for bit in range(32):
        flag_name = all_flags_map.get(bit, f"Unknown_Bit_{bit}")
        is_set = (flags_int >> bit) & 1
        flag_details[flag_name] = is_set

    metadata = {
        'header': {
            'version': version,
            'git_hash_hex': git_hash.hex(),
            'build_date': build_date_bytes.decode('utf-8').strip(),
        },
        'flags': flag_details
    }
    metadata_path = output_dir_path / "metadata.toml"
    with open(metadata_path, 'w') as f:
        toml.dump(metadata, f)
    print(f"[*] Saved editable header metadata to {metadata_path}")
    print("\n[+] Extraction complete.")

def handle_repack(args: argparse.Namespace):
    """
    Repacks extracted chunks and edited metadata into a new save file.
    """
    input_dir_path = Path(args.input_dir)
    output_file_path = Path(args.output_file)

    print(f"[*] Repacking from directory: {input_dir_path}")
    
    # 1. Read metadata and reconstruct flags
    metadata_path = input_dir_path / "metadata.toml"
    if not metadata_path.is_file():
        print(f"[!] Error: 'metadata.toml' not found in '{input_dir_path}'.", file=sys.stderr)
        sys.exit(1)
    
    metadata = toml.load(metadata_path)
    header_meta = metadata['header']
    flags_meta = metadata['flags']
    
    # Rebuild the integer flags value from the TOML file
    flags_int = 0
    all_flags_map_inv = {v: k for k, v in (SAVE_CONTENT_MAP | FEATURE_FLAG_MAP).items()}
    for name, is_set in flags_meta.items():
        if is_set:
            bit = all_flags_map_inv.get(name)
            if bit is None and name.startswith("Unknown_Bit_"):
                bit = int(name.split("_")[-1])
            
            if bit is not None:
                flags_int |= (1 << bit)
    
    print(f"[*] Reconstructed flags from metadata: {flags_int:#010x}")

    # 2. Assemble the new decompressed payload
    payload_builder = io.BytesIO()
    for bit in range(32):
        if (flags_int >> bit) & 1 and bit in SAVE_CONTENT_MAP:
            chunk_name = SAVE_CONTENT_MAP[bit]
            chunk_filepath = input_dir_path / f"Bit_{bit:02d}_{chunk_name}.bin"

            if not chunk_filepath.is_file():
                print(f"[!] Error: Flag for '{chunk_name}' is set, but file '{chunk_filepath.name}' not found.", file=sys.stderr)
                sys.exit(1)
            
            with open(chunk_filepath, 'rb') as f_in:
                chunk_data = f_in.read()
            
            payload_builder.write(struct.pack('<I', len(chunk_data)))
            payload_builder.write(chunk_data)
            print(f"    -> Repacked {chunk_name} ({len(chunk_data)} bytes)")
    
    new_decompressed_payload = payload_builder.getvalue()
    
    # 3. Compress, build header, calculate checksum
    new_compressed_payload = zlib.compress(new_decompressed_payload, level=9)
    header_data = struct.pack(
        HEADER_FORMAT, MAGIC_NUMBER, header_meta['version'],
        b'\x00' * 20, bytes.fromhex(header_meta['git_hash_hex']),
        header_meta['build_date'].encode('utf-8'), flags_int
    )
    final_data = bytearray(header_data + new_compressed_payload)
    new_checksum = hashlib.sha1(final_data).digest()
    final_data[CHECKSUM_OFFSET : CHECKSUM_OFFSET + CHECKSUM_SIZE] = new_checksum
    print(f"[*] Calculated new checksum: {new_checksum.hex()}")
    
    # 4. Write to output file
    with open(output_file_path, 'wb') as f_out:
        f_out.write(final_data)
    
    print(f"\n[+] Repacking complete. New save file created at: {output_file_path}")

def handle_convert(args: argparse.Namespace):
    """
    Converts a save file from one format into another.
    In this version, only the S_User chunk (permanent unlocks) is copied; converting the current run is not supported at the moment.
    The S_Game and S_UserAndGameData chunks are deleted to force a new run.
    """
    
    if not Path(args.input_file).is_file():
        print(f"[!] Error: File not found at '{args.input_file}'", file=sys.stderr)
        sys.exit(1)
    if not Path(args.shell_file).is_file():
        print(f"[!] Error: File not found at '{args.shell_file}'", file=sys.stderr)
        sys.exit(1)
    
    with tempfile.TemporaryDirectory() as tmpdir_shell:
        tmpdir_shell_path = Path(tmpdir_shell)
        with tempfile.TemporaryDirectory() as tmpdir_input:
            # 1. Create args objects
            extract_input_args = argparse.Namespace()
            extract_input_args.save_file = args.input_file
            extract_input_args.output_dir = tmpdir_input
            
            extract_shell_args = argparse.Namespace()
            extract_shell_args.save_file = args.shell_file
            extract_shell_args.output_dir = tmpdir_shell

            repack_args = argparse.Namespace()
            repack_args.input_dir = tmpdir_shell
            repack_args.output_file = args.output_file

            # 2. Extract save files
            print(f"[*] Extracting input save file: '{args.input_file}'")
            handle_extract(extract_input_args)
            
            print(f"\n[*] Extracting shell save file: '{args.shell_file}'")
            handle_extract(extract_shell_args)

            # 3. Copy the source S_User chunk
            shutil.copy(f'{tmpdir_input}/Bit_00_S_User.bin', f'{tmpdir_shell}/Bit_00_S_User.bin')
            
            # 4. Delete the destination S_Game and S_UserAndGameData chunks to force a new run
            metadata_path = tmpdir_shell_path / "metadata.toml"
            if not metadata_path.is_file():
                print(f"[!] Error: 'metadata.toml' not found in '{tmpdir_shell_path}'.", file=sys.stderr)
                sys.exit(1)
            
            metadata = toml.load(metadata_path)
            metadata['flags']['S_Game'] = 0
            metadata['flags']['S_UserAndGameData'] = 0
            with open(metadata_path, 'w') as f:
                toml.dump(metadata, f)
            
            if (tmpdir_shell_path / 'Bit_01_S_Game.bin').is_file():
                os.remove(tmpdir_shell_path / 'Bit_01_S_Game.bin')
            if (tmpdir_shell_path / 'Bit_02_S_UserAndGameData.bin').is_file():
                os.remove(tmpdir_shell_path / 'Bit_02_S_UserAndGameData.bin')

            # 5. Repack
            print(f"\n[*] Packing into output save file: '{args.output_file}'")
            handle_repack(repack_args)

def handle_edit(args: argparse.Namespace):
    import datetime as _dt
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    from hxbit.core import HXSFile
    from hxbit.gui import DPIAwareTk, HXSTreeFrame, apply_platform_scaling

    save_file_path = Path(args.save_file)
    if not save_file_path.is_file():
        print(f"[!] Error: File not found at '{save_file_path}'", file=sys.stderr)
        sys.exit(1)

    class SaveEditorApp(DPIAwareTk):
        def __init__(self, path: Path):
            super().__init__()
            scaling = apply_platform_scaling(self)
            self.title(f"savetools - {path.name}")
            self.geometry(f"{round(1280 * scaling)}x{round(860 * scaling)}")

            self.path = path
            self.status_var = tk.StringVar(value="Ready")

            raw = path.read_bytes()
            self.checksum_ok = verify_save_checksum(path, verbose=False)
            self.header, self.chunks = parse_save_bytes(raw)
            self.hxs_files = {}

            self._build_ui()

        def _build_ui(self) -> None:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)

            toolbar = ttk.Frame(self, padding=8)
            toolbar.grid(row=0, column=0, sticky="ew")
            toolbar.columnconfigure(2, weight=1)
            ttk.Button(toolbar, text="Save", command=self.save).grid(row=0, column=0, padx=(0, 6))
            ttk.Button(toolbar, text="Save As", command=self.save_as).grid(row=0, column=1, padx=6)
            checksum_note = "" if self.checksum_ok else "   [checksum INVALID on load]"
            ttk.Label(toolbar, text=f"{self.path}{checksum_note}").grid(row=0, column=2, sticky="e")

            notebook = ttk.Notebook(self)
            notebook.grid(row=1, column=0, sticky="nsew")

            self._build_header_tab(notebook)
            for bit in sorted(self.chunks):
                name = SAVE_CONTENT_MAP[bit]
                if bit in HXBIT_CHUNK_BITS:
                    self._build_hxbit_tab(notebook, bit, name)
                elif bit == 3:
                    self._build_date_tab(notebook, bit, name)
                elif bit == 7:
                    self._build_version_tab(notebook, bit, name)
                elif bit == 8:
                    self._build_dlc_tab(notebook, bit, name)
                else:
                    self._build_hex_tab(notebook, bit, name)

            status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=8)
            status.grid(row=2, column=0, sticky="ew")

        def _build_header_tab(self, notebook: ttk.Notebook) -> None:
            tab = ttk.Frame(notebook, padding=12)
            notebook.add(tab, text="Header")
            tab.columnconfigure(1, weight=1)

            ttk.Label(tab, text="Format version").grid(row=0, column=0, sticky="w", pady=4)
            self.version_var = tk.StringVar(value=str(self.header['version']))
            ttk.Entry(tab, textvariable=self.version_var, width=12).grid(row=0, column=1, sticky="w", pady=4)

            ttk.Label(tab, text="Git commit hash").grid(row=1, column=0, sticky="w", pady=4)
            self.git_hash_var = tk.StringVar(value=self.header['git_hash'].hex())
            ttk.Entry(tab, textvariable=self.git_hash_var, width=48).grid(row=1, column=1, sticky="w", pady=4)

            ttk.Label(tab, text="Build date").grid(row=2, column=0, sticky="w", pady=4)
            self.build_date_var = tk.StringVar(value=self.header['build_date'])
            ttk.Entry(tab, textvariable=self.build_date_var, width=16).grid(row=2, column=1, sticky="w", pady=4)

            ttk.Label(tab, text="Feature flags").grid(row=3, column=0, sticky="nw", pady=(16, 4))
            flags_frame = ttk.Frame(tab)
            flags_frame.grid(row=3, column=1, sticky="w", pady=(16, 4))
            self.feature_flag_vars = {}
            for row, (bit, name) in enumerate(sorted(FEATURE_FLAG_MAP.items())):
                var = tk.BooleanVar(value=bool((self.header['flags'] >> bit) & 1))
                self.feature_flag_vars[bit] = var
                ttk.Checkbutton(flags_frame, text=f"{name} (bit {bit})", variable=var).grid(
                    row=row, column=0, sticky="w"
                )

        def _build_hxbit_tab(self, notebook: ttk.Notebook, bit: int, name: str) -> None:
            tab = ttk.Frame(notebook, padding=8)
            notebook.add(tab, text=name)
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)
            try:
                hxs = HXSFile.from_bytes(self.chunks[bit], shims="deadcells")
            except Exception as e:
                ttk.Label(tab, text=f"Failed to parse {name} as hxbit data:\n{e}").grid(
                    row=0, column=0, sticky="nw"
                )
                return
            self.hxs_files[bit] = hxs
            tree = HXSTreeFrame(tab, on_status=self.status_var.set)
            tree.grid(row=0, column=0, sticky="nsew")
            tree.load(hxs)
            if hxs.object_parse_error is not None:
                ttk.Label(
                    tab,
                    text=f"Warning: typed parse incomplete ({hxs.object_parse_error}); "
                         "the chunk will be saved from its preserved raw payload.",
                ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        def _build_date_tab(self, notebook: ttk.Notebook, bit: int, name: str) -> None:
            tab = ttk.Frame(notebook, padding=12)
            notebook.add(tab, text=name)
            timestamp = struct.unpack('<d', self.chunks[bit])[0]
            date_str = _dt.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            ttk.Label(tab, text="Save date (YYYY-MM-DD HH:MM:SS, local time)").grid(row=0, column=0, sticky="w", pady=4)
            self.date_var = tk.StringVar(value=date_str)
            ttk.Entry(tab, textvariable=self.date_var, width=24).grid(row=1, column=0, sticky="w", pady=4)

        def _build_version_tab(self, notebook: ttk.Notebook, bit: int, name: str) -> None:
            tab = ttk.Frame(notebook, padding=12)
            notebook.add(tab, text=name)
            version_float = struct.unpack('<f', self.chunks[bit])[0]
            ttk.Label(tab, text="Game version number").grid(row=0, column=0, sticky="w", pady=4)
            self.game_version_var = tk.StringVar(value=f"{version_float:g}")
            ttk.Entry(tab, textvariable=self.game_version_var, width=12).grid(row=1, column=0, sticky="w", pady=4)

        def _build_dlc_tab(self, notebook: ttk.Notebook, bit: int, name: str) -> None:
            tab = ttk.Frame(notebook, padding=12)
            notebook.add(tab, text=name)
            dlc_mask = struct.unpack('<I', self.chunks[bit])[0]
            self.dlc_unknown_bits = dlc_mask & ~sum(1 << b for b in DLC_MAP)
            ttk.Label(tab, text="Owned DLC").grid(row=0, column=0, sticky="w", pady=(0, 8))
            self.dlc_vars = {}
            for row, (dlc_bit, dlc_name) in enumerate(DLC_MAP.items(), start=1):
                var = tk.BooleanVar(value=bool((dlc_mask >> dlc_bit) & 1))
                self.dlc_vars[dlc_bit] = var
                ttk.Checkbutton(tab, text=dlc_name, variable=var).grid(row=row, column=0, sticky="w")

        def _build_hex_tab(self, notebook: ttk.Notebook, bit: int, name: str) -> None:
            tab = ttk.Frame(notebook, padding=8)
            notebook.add(tab, text=name)
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)
            text = tk.Text(tab, wrap="none")
            text.grid(row=0, column=0, sticky="nsew")
            data = self.chunks[bit]
            preview = data[:4096]
            lines = [
                f"{off:08x}  {preview[off:off + 16].hex(' ')}"
                for off in range(0, len(preview), 16)
            ]
            if len(data) > len(preview):
                lines.append(f"… {len(data) - len(preview)} more bytes")
            text.insert("1.0", "\n".join(lines))
            text.configure(state="disabled")

        def _collect(self) -> bytes:
            chunks = dict(self.chunks)
            for bit, hxs in self.hxs_files.items():
                chunks[bit] = hxs.serialise()
            if hasattr(self, "date_var"):
                parsed = _dt.datetime.strptime(self.date_var.get().strip(), '%Y-%m-%d %H:%M:%S')
                chunks[3] = struct.pack('<d', parsed.timestamp())
            if hasattr(self, "game_version_var"):
                chunks[7] = struct.pack('<f', float(self.game_version_var.get()))
            if hasattr(self, "dlc_vars"):
                mask = self.dlc_unknown_bits
                for dlc_bit, var in self.dlc_vars.items():
                    if var.get():
                        mask |= 1 << dlc_bit
                chunks[8] = struct.pack('<I', mask)

            flags = 0
            for bit in chunks:
                flags |= 1 << bit
            for bit, var in self.feature_flag_vars.items():
                if var.get():
                    flags |= 1 << bit
            known = sum(1 << b for b in SAVE_CONTENT_MAP) | sum(1 << b for b in FEATURE_FLAG_MAP)
            flags |= self.header['flags'] & ~known

            git_hash = bytes.fromhex(self.git_hash_var.get().strip())
            if len(git_hash) != 20:
                raise ValueError("Git hash must be exactly 20 bytes (40 hex characters).")
            return build_save_bytes(
                int(self.version_var.get()), git_hash,
                self.build_date_var.get().strip(), flags, chunks,
            )

        def save(self) -> None:
            try:
                data = self._collect()
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
                return
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            if not backup.exists():
                backup.write_bytes(self.path.read_bytes())
            self.path.write_bytes(data)
            self.status_var.set(f"Saved {self.path.name} (backup at {backup.name})")

        def save_as(self) -> None:
            target = filedialog.asksaveasfilename(
                title="Save Dead Cells save file",
                defaultextension=".dat",
                filetypes=[("Dead Cells saves", "*.dat"), ("All files", "*.*")],
            )
            if not target:
                return
            try:
                data = self._collect()
            except Exception as e:
                messagebox.showerror("Save failed", str(e))
                return
            Path(target).write_bytes(data)
            self.status_var.set(f"Saved {Path(target).name}")

    SaveEditorApp(save_file_path).mainloop()


def main():
    """Sets up argument parsing and delegates to subcommand handlers."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    verify_parser = subparsers.add_parser('verify', help='Verify the checksum of a save file.')
    verify_parser.add_argument('save_file', help='Path to the save file to verify.')
    verify_parser.set_defaults(func=handle_verify)
    
    info_parser = subparsers.add_parser('info', help='Display detailed information and decode primitive chunks from a save file.')
    info_parser.add_argument('save_file', help='Path to the save file to inspect.')
    info_parser.set_defaults(func=handle_info)

    extract_parser = subparsers.add_parser('extract', help='Extract chunks and editable metadata from a save file.')
    extract_parser.add_argument('save_file', help='Path to the save file to extract from.')
    extract_parser.add_argument('output_dir', help='Path to the directory to save files.')
    extract_parser.set_defaults(func=handle_extract)

    repack_parser = subparsers.add_parser('repack', help='Repack a directory of chunks into a new save file.')
    repack_parser.add_argument('input_dir', help='Path to the directory with chunk files and metadata.toml.')
    repack_parser.add_argument('output_file', help='Path for the newly created save file.')
    repack_parser.set_defaults(func=handle_repack)
    
    edit_parser = subparsers.add_parser('edit', help='Open a GUI editor for all chunks and metadata of a save file.')
    edit_parser.add_argument('save_file', help='Path to the save file to edit.')
    edit_parser.set_defaults(func=handle_edit)

    convert_parser = subparsers.add_parser('convert', help='Convert a save file from one format to another.')
    convert_parser.add_argument('input_file', help='Path to the save file to convert.')
    convert_parser.add_argument('shell_file', help='Path to a save file from the destination platform.')
    convert_parser.add_argument('output_file', help='Path for the converted save file.')
    convert_parser.set_defaults(func=handle_convert)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
