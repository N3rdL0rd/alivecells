#!/usr/bin/env python3

"""
Tool for working with Dead Cells save files. Allows verification, extraction, and repacking.
"""

import hashlib
import argparse
import sys
import zlib
from pathlib import Path
import io
import os
import struct
import toml

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

def verify_save_checksum(file_path: Path) -> bool:
    """
    Performs the core logic of verifying the SHA-1 checksum.

    Args:
        file_path: A Path object pointing to the save file.

    Returns:
        True if the checksum is valid, False otherwise.
    """
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
    print(f"  > Stored Checksum:   {stored_checksum.hex()}")

    data_for_hashing = bytearray(save_data)

    checksum_placeholder = b'\x00' * CHECKSUM_SIZE

    data_for_hashing[CHECKSUM_OFFSET : CHECKSUM_OFFSET + CHECKSUM_SIZE] = checksum_placeholder
    
    calculated_checksum = hashlib.sha1(data_for_hashing).digest()
    print(f"  > Calculated Checksum: {calculated_checksum.hex()}")
    
    return stored_checksum == calculated_checksum

def handle_verify(args: argparse.Namespace):
    """Handler for the 'verify' subcommand."""
    save_file_path = Path(args.save_file)

    if not save_file_path.is_file():
        print(f"[!] Error: File not found at '{save_file_path}'", file=sys.stderr)
        sys.exit(1)

    is_valid = verify_save_checksum(save_file_path)
    
    if is_valid:
        print("\n[+] SUCCESS: Checksum is VALID!")
        sys.exit(0)
    else:
        print("\n[!] FAILURE: Checksum is INVALID! The file may be corrupt or modified.")
        sys.exit(1)

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
            'build_date': build_date_bytes.decode('utf-8'),
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


def main():
    """Sets up argument parsing and delegates to subcommand handlers."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    verify_parser = subparsers.add_parser('verify', help='Verify the checksum of a save file.')
    verify_parser.add_argument('save_file', help='Path to the save file to verify.')
    verify_parser.set_defaults(func=handle_verify)
    
    extract_parser = subparsers.add_parser('extract', help='Extract chunks and editable metadata from a save file.')
    extract_parser.add_argument('save_file', help='Path to the save file to extract from.')
    extract_parser.add_argument('output_dir', help='Path to the directory to save files.')
    extract_parser.set_defaults(func=handle_extract)

    repack_parser = subparsers.add_parser('repack', help='Repack a directory of chunks into a new save file.')
    repack_parser.add_argument('input_dir', help='Path to the directory with chunk files and metadata.toml.')
    repack_parser.add_argument('output_file', help='Path for the newly created save file.')
    repack_parser.set_defaults(func=handle_repack)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()