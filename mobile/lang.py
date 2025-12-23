import struct
import argparse
import sys

MAGIC_LE = b'\xde\x12\x04\x95'
MAGIC_BE = b'\x95\x04\x12\xde'
ENCODING = 'utf-8'

def escape_po(s):
    """Escapes strings for PO format."""
    return s.replace('\\', '\\\\') \
            .replace('"', '\\"') \
            .replace('\n', '\\n') \
            .replace('\r', '\\r') \
            .replace('\t', '\\t')

def unescape_po(s):
    """Unescapes strings from PO format."""
    return s.replace('\\n', '\n') \
            .replace('\\r', '\r') \
            .replace('\\t', '\t') \
            .replace('\\"', '"') \
            .replace('\\\\', '\\')

def unpack(args):
    input_file = args.input
    output_file = args.output
    
    print(f"Reading {input_file}...")

    with open(input_file, 'rb') as f:
        magic = f.read(4)
        if magic == MAGIC_LE:
            endian = '<'
        elif magic == MAGIC_BE:
            endian = '>'
        else:
            print(f"Error: Unknown file format. Magic bytes: {magic.hex()}")
            sys.exit(1)

        # Magic (4), Revision (4), Count (4), OrigOffset (4), TransOffset (4), HashSz (4), HashOff (4)
        f.seek(4)
        header_data = f.read(24)
        revision, num_strings, o_table_off, t_table_off, _, _ = struct.unpack(f'{endian}6I', header_data)

        print(f"Found {num_strings} messages. Extracting...")
        
        entries = []

        for i in range(num_strings):
            # Original String (msgid)
            f.seek(o_table_off + (i * 8))
            o_len, o_off = struct.unpack(f'{endian}II', f.read(8))
            
            # Translated String (msgstr)
            f.seek(t_table_off + (i * 8))
            t_len, t_off = struct.unpack(f'{endian}II', f.read(8))

            # Read the actual bytes
            f.seek(o_off)
            msgid_raw = f.read(o_len)
            
            f.seek(t_off)
            msgstr_raw = f.read(t_len)

            # Decode
            try:
                msgid = msgid_raw.decode(ENCODING)
                msgstr = msgstr_raw.decode(ENCODING)
            except UnicodeDecodeError:
                # Fallback if bytes are weird
                msgid = msgid_raw.decode(ENCODING, errors='replace')
                msgstr = msgstr_raw.decode(ENCODING, errors='replace')

            entries.append((msgid, msgstr))

    with open(output_file, 'w', encoding=ENCODING) as out:
        out.write(f'# Unpacked from {input_file}\n')
        
        for msgid, msgstr in entries:
            out.write(f'msgid "{escape_po(msgid)}"\n')
            out.write(f'msgstr "{escape_po(msgstr)}"\n\n')

    print(f"Success! Unpacked to {output_file}")



def pack(args):
    input_file = args.input
    output_file = args.output

    print(f"Parsing {input_file}...")
    
    entries = []
    current_msgid = None
    current_msgstr = None
    
    with open(input_file, 'r', encoding=ENCODING) as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if line.startswith('msgid "'):
            current_msgid = unescape_po(line[7:-1])
        elif line.startswith('msgstr "'):
            if current_msgid is not None:
                current_msgstr = unescape_po(line[8:-1])
                entries.append((current_msgid, current_msgstr))
                current_msgid = None
                current_msgstr = None

    num_strings = len(entries)
    print(f"Packing {num_strings} messages...")
    
    header_size = 28
    table_item_size = 8
    
    o_table_offset = header_size
    t_table_offset = header_size + (num_strings * table_item_size)
    text_start_offset = t_table_offset + (num_strings * table_item_size)
    
    o_table_blob = bytearray()
    t_table_blob = bytearray()
    text_blob = bytearray()
    
    current_text_offset = text_start_offset
    
    for msgid, msgstr in entries:
        id_bytes = msgid.encode(ENCODING) + b'\x00'
        str_bytes = msgstr.encode(ENCODING) + b'\x00'
        
        o_table_blob.extend(struct.pack('<II', len(id_bytes)-1, current_text_offset))
        text_blob.extend(id_bytes)
        current_text_offset += len(id_bytes)
        
        t_table_blob.extend(struct.pack('<II', len(str_bytes)-1, current_text_offset))
        text_blob.extend(str_bytes)
        current_text_offset += len(str_bytes)

    with open(output_file, 'wb') as f:
        # Header
        # Magic (LE), Revision (0), Count, O_Off, T_Off, HashSz (0), HashOff (0)
        # Hash Size is 0 because we are keeping the file unsorted.
        f.write(struct.pack('<IIIIIII', 
                            0x950412de, 
                            0, 
                            num_strings, 
                            o_table_offset, 
                            t_table_offset, 
                            0, 0))
        
        # Tables
        f.write(o_table_blob)
        f.write(t_table_blob)
        
        # Data
        f.write(text_blob)

    print(f"Success! Packed to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Tool for unpacking/packing weird unsorted GNU MO files such as those appearing in Dead Cells mobile builds.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    p_unpack = subparsers.add_parser('unpack', help='Convert MO binary to readable PO text')
    p_unpack.add_argument('input', help='Input binary file (e.g., main.en.mo)')
    p_unpack.add_argument('output', help='Output text file (e.g., main.en.po)')
    p_unpack.set_defaults(func=unpack)

    p_pack = subparsers.add_parser('pack', help='Convert PO text back to binary MO')
    p_pack.add_argument('input', help='Input text file (e.g., main.en.po)')
    p_pack.add_argument('output', help='Output binary file (e.g., main.en.mo)')
    p_pack.set_defaults(func=pack)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()