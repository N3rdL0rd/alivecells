# PAK files

PAK files are checksum-verified packages that contain a full filesystem structure inside them - they store all assets for the game. PAK files can be layered on top of each other - the game will first search for `res.pak`, then `res1.pak`, then `res2.pak` (etc.) while loading PAKs - PAKs are incrementally stacked on top of each other during the loading process - conflicts are ignored, and the PAK with the highest priority is used.

## Format

> If you're a REHex user, you can download a fully commented out example PAK file from [here](https://github.com/N3rdL0rd/alivecells/blob/main/docs/data/example.pak.zip)

### File

| Size (bytes) | Name           | Description                                        | Struct            |
|--------------|----------------|----------------------------------------------------|-------------------|
| Variable     | Header         | File magic, version, data sizes, stamp             | [Header](#header) |
| Variable     | Root directory | Main directory entry, contains all data in the PAK | [Entry](#entry)   |
| 4            | DATA marker    | Marks the start of file content data               | [DATA marker](#data-marker) |
| Variable     | File contents  | Actual file data for all files in the PAK          | Raw binary data   |

### Header

| Size (bytes) | Name        | Description                                                                   | Struct             | Condition            |
|--------------|-------------|-------------------------------------------------------------------------------|--------------------|----------------------|
| 3            | Magic       | "PAK"                                                                         | ASCII-encoded text | None                 |
| 1            | Version     | 0x00 or 0x01 - v0 doesn't support stamping, v1 does                           | Unsigned byte      | None                 |
| 4            | Header size | Size of the header - at v0, guaranteed to be >16, at v1, guaranteed to be >80 | Signed 32-bit int  | None                 |
| 4            | Data size   | Size of the data                                                              | Signed 32-bit int  | None                 |
| 64           | Stamp       | Signature based on git commit - see [here](#stamps)                           | ASCII-encoded text | Game >=v35, PAK >=v1 |

### Entry

| Size (bytes) | Name           | Description                                                   | Struct                 | Condition                |
|--------------|----------------|---------------------------------------------------------------|------------------------|--------------------------|
| 1            | Name length    | Length of the entry name                                      | Unsigned byte          | None                     |
| Variable     | Name           | Name of the entry                                             | ASCII-encoded text     | Name length > 0          |
| 1            | Type           | 0x00 for file, 0x01 for directory                             | Unsigned byte          | None                     |
| 4            | Entry count    | Number of entries in the directory                            | Signed 32-bit int      | Type == 0x01 (Directory) |
| Variable     | Entries        | Recursive Entry structures for directory contents             | [Entry](#entry)        | Type == 0x01 (Directory) |
| 4            | Position       | Offset of the file data from the start of the data section    | Signed 32-bit int      | Type == 0x00 (File)      |
| 4            | Size           | Size of the file data in bytes                                | Signed 32-bit int      | Type == 0x00 (File)      |
| 4            | Checksum       | Adler32 checksum of the file data                             | Signed 32-bit int      | Type == 0x00 (File)      |

### DATA marker

| Size (bytes) | Name   | Description                           | Struct              |
|--------------|--------|---------------------------------------|---------------------|
| 4            | Marker | ASCII "DATA" to mark start of content | ASCII-encoded text  |

The DATA marker serves as a separator between the header/directory information and the actual file contents. It helps in clearly delineating the structure of the PAK file and can be used as a reference point when reading or writing PAK files.

## Stamps

In v35+ of the game (v1 of the PAK format), PAK files now include "stamps". A stamp is a 64-character (ASCII) digest of a SHA256 hash, generated with this formula (written in pseudocode):

```txt
ASCII digest(
    SHA256(
        UTF-8 encode("Dc02&0hQC#G0:"),
        UTF-8 encode(Current git commit - short hash)
    )
)
```

Due to the deterministic nature of SHA256 and the short length of the commit hash, it is possible to easily brute-force the short hash from a given stamp - an implementation of this exists in Alive Cells' [main script](https://github.com/N3rdL0rd/alivecells/blob/main/alivecells.py), as the `commitbrute` subcommand.