import hashlib
import io
import struct
import zlib

MAGIC_NUMBER = 0x11CEADDE  # DE AD CE 11
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


def verify_save_checksum_bytes(save_data: bytes) -> tuple[bool, bytes, bytes]:
    """Checks the SHA-1 checksum of a save file's raw bytes.

    Returns (is_valid, stored_checksum, calculated_checksum). Raises
    ValueError if the data is too small to contain a checksum at all.
    """
    if len(save_data) < (CHECKSUM_OFFSET + CHECKSUM_SIZE):
        raise ValueError("File is too small to be a valid save file.")

    stored_checksum = save_data[CHECKSUM_OFFSET:CHECKSUM_OFFSET + CHECKSUM_SIZE]

    data_for_hashing = bytearray(save_data)
    data_for_hashing[CHECKSUM_OFFSET:CHECKSUM_OFFSET + CHECKSUM_SIZE] = b'\x00' * CHECKSUM_SIZE
    calculated_checksum = hashlib.sha1(bytes(data_for_hashing)).digest()

    return stored_checksum == calculated_checksum, stored_checksum, calculated_checksum
