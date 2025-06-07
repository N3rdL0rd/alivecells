import type.magic;

bitfield DCFlags {
    bool S_User            : 1; // User progress chunk exists
    bool S_Game            : 1; // In-progress run chunk exists
    bool S_UserAndGameData : 1; // Game metadata chunk exists
    bool S_Date            : 1; // Timestamp chunk exists
    bool S_Experimental    : 1; // Experimental features were enabled
    bool S_UsesMods        : 1; // Mods were active
    bool S_HaveLore        : 1; // Lore rooms are supported (always on)
    bool S_VersionNumber   : 1; // Game version chunk exists
    bool S_DLCMask         : 1; // DLC bitmask chunk exists
};

struct DCSaveHeader {
    type::Magic<"\xDE\xAD\xCE\x11"> magic;
    u8  version;
    u8  sha1[20];
    u8  githash[20];
    char built[10];
    DCFlags flags;
    padding[2]; // unused bytes for the foreseeable future

};

// The main file structure.
struct DCSave {
    DCSaveHeader header;
    u8 payload[while(!std::mem::eof())]; // Rest of file as raw bytes
};

// Apply the pattern starting at the beginning of the file.
DCSave save @ 0x0;