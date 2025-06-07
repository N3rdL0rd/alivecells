"""
Tool for working with Dead Cells save files.
"""

import hashlib
import argparse
import sys
import zlib
from pathlib import Path

CHECKSUM_OFFSET = 5  # HSIGN (4 bytes) + FORMAT_VER (1 byte)
CHECKSUM_SIZE = 20   # SHA-1 produces a 20-byte hash

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
    """Handler for the 'extract' subcommand."""
    save_file_path = Path(args.save_file)
    output_file_path = Path(args.output_file)

    if not save_file_path.is_file():
        print(f"[!] Error: File not found at '{save_file_path}'", file=sys.stderr)
        sys.exit(1)

    try:
        with open(save_file_path, 'rb') as f:
            save_data = f.read()
        
        save_data = save_data[59:]
        save_data = zlib.decompress(save_data)
        
        with open(output_file_path, 'wb') as out_f:
            out_f.write(save_data)
        
        print(f"[+] Successfully extracted data to: {output_file_path}")
    except Exception as e:
        print(f"[!] An error occurred while extracting data: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """Sets up argument parsing and delegates to subcommand handlers."""
    parser = argparse.ArgumentParser(
        description="A command-line tool for working with Dead Cells save files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', required=True, help="Available commands")

    verify_parser = subparsers.add_parser(
        'verify', 
        help='Verify the checksum of a Dead Cells save file.',
        description='Reads a save file, recalculates its SHA-1 checksum, and compares it to the one stored in the file.'
    )
    verify_parser.add_argument(
        'save_file', 
        help='Path to the save file to verify (e.g., user_0.dat).'
    )
    verify_parser.set_defaults(func=handle_verify)
    
    extract_parser = subparsers.add_parser(
        'extract', 
        help='Extract compressed data from a Dead Cells save file.',
        description='Extracts the compressed data from a Dead Cells save file and saves it to a specified output file.'
    )
    extract_parser.add_argument(
        'save_file', 
        help='Path to the save file to extract data from (e.g., user_0.dat).'
    )
    extract_parser.add_argument(
        'output_file', 
        help='Path to the output file where the extracted data will be saved.'
    )
    extract_parser.set_defaults(func=handle_extract)


    args = parser.parse_args()
    
    args.func(args)


if __name__ == "__main__":
    main()