import datetime
import json
import reprlib
import struct
from typing import Any

from hxbit.core import HXSFile, Obj
from core import (
    DLC_MAP,
    FEATURE_FLAG_MAP,
    HXBIT_CHUNK_BITS,
    SAVE_CONTENT_MAP,
    build_save_bytes,
    parse_save_bytes,
    verify_save_checksum_bytes,
)

_TREE_PAGE_SIZE = 500

_state: dict[str, Any] = {
    "raw": None,
    "header": None,
    "chunks": {},
    "hxs": {},
    "dlc_unknown_bits": {},
    "header_edit": None,
}


def _value_kind(value: Any) -> str:
    if isinstance(value, Obj):
        return value.schema.classdef.name.value if value.schema.classdef else "Obj"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if value is None:
        return "None"
    return type(value).__name__


def _value_summary(value: Any) -> str:
    if isinstance(value, Obj):
        return f"{_value_kind(value)} ({len(value.fields)} fields)"
    if isinstance(value, dict):
        return f"{len(value)} entries"
    if isinstance(value, list):
        return f"{len(value)} items"
    if isinstance(value, bytes):
        return f"{len(value)} bytes"
    if isinstance(value, str):
        return value if len(value) <= 200 else value[:200] + "…"
    if value is None:
        return "None"
    return str(value)


def _is_expandable(value: Any) -> bool:
    if isinstance(value, Obj):
        return bool(value.fields)
    if isinstance(value, (dict, list)):
        return bool(value)
    return False


def _iter_children(value: Any) -> list[tuple[str, Any, Any]]:
    """Yields (label, path_element, child) for one level of `value`."""
    if isinstance(value, Obj):
        return [(key, key, child) for key, child in value.fields.items()]
    if isinstance(value, dict):
        return [(repr(key), i, child) for i, (key, child) in enumerate(value.items())]
    if isinstance(value, list):
        return [(f"[{i}]", i, child) for i, child in enumerate(value)]
    return []


def _format_scalar(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return "None"
    return str(value)


def _scalar_type_name(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _parse_scalar(type_name: str, raw: str) -> Any:
    if type_name == "None":
        return None
    if type_name == "bool":
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ValueError("Boolean values must be true/false, yes/no, on/off, or 1/0.")
    if type_name == "int":
        return int(raw, 0)
    if type_name == "float":
        return float(raw)
    return raw


def _hex_preview(data: bytes, limit: int = 4096) -> str:
    preview = data[:limit]
    lines = [
        f"{off:08x}  {preview[off:off + 16].hex(' ')}"
        for off in range(0, len(preview), 16)
    ]
    if len(data) > len(preview):
        lines.append(f"… {len(data) - len(preview)} more bytes")
    return "\n".join(lines)


def _roots(bit: int) -> list[Obj]:
    hxs = _state["hxs"][bit]
    return list(hxs.roots or ([hxs.obj] if hxs.obj is not None else []))


def _walk(bit: int, path: list):
    """Resolves `path` against the chunk's root list.

    Returns (container, key, value, ancestor_ids, labels). `container[key]`
    is `value`; `container` is None only when `path` is empty (`value` is
    then the synthetic list of root objects).
    """
    value: Any = _roots(bit)
    container = None
    key = None
    ancestors: set[int] = set()
    labels: list[str] = []

    for elem in path:
        if isinstance(value, (Obj, dict, list)):
            ancestors.add(id(value))

        if isinstance(value, Obj):
            container = value.fields
            key = elem
            labels.append(str(elem))
        elif isinstance(value, dict):
            items = list(value.items())
            real_key, _ = items[elem]
            container = value
            key = real_key
            labels.append(repr(real_key))
        else:  # list, including the synthetic root list
            container = value
            key = elem
            if not labels and isinstance(value[elem], Obj) and value[elem].schema.classdef:
                labels.append(value[elem].schema.classdef.name.value)
            else:
                labels.append(f"[{elem}]")

        value = container[key]

    return container, key, value, ancestors, labels


def _path_str(labels: list[str]) -> str:
    if not labels:
        return ""
    out = labels[0]
    for lbl in labels[1:]:
        out += lbl if lbl.startswith("[") else f".{lbl}"
    return out


def load(data: bytes) -> str:
    raw = bytes(data)
    header, chunks = parse_save_bytes(raw)
    is_valid, stored, calculated = verify_save_checksum_bytes(raw)

    _state["raw"] = raw
    _state["header"] = header
    _state["chunks"] = chunks
    _state["hxs"] = {}
    _state["dlc_unknown_bits"] = {}
    _state["header_edit"] = None

    chunk_infos = []
    for bit in sorted(chunks):
        name = SAVE_CONTENT_MAP[bit]
        info: dict[str, Any] = {"bit": bit, "name": name, "size": len(chunks[bit])}
        if bit in HXBIT_CHUNK_BITS:
            try:
                hxs = HXSFile.from_bytes(chunks[bit], shims="deadcells")
                _state["hxs"][bit] = hxs
                info["type"] = "hxbit"
                info["root_count"] = len(_roots(bit))
                if hxs.object_parse_error is not None:
                    info["parse_error"] = str(hxs.object_parse_error)
            except Exception as e:
                info["type"] = "hxbit_error"
                info["error"] = str(e)
        elif bit == 3:
            info["type"] = "date"
            timestamp = struct.unpack('<d', chunks[bit])[0]
            info["value"] = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        elif bit == 7:
            info["type"] = "version"
            info["value"] = struct.unpack('<f', chunks[bit])[0]
        elif bit == 8:
            info["type"] = "dlc"
            mask = struct.unpack('<I', chunks[bit])[0]
            known = sum(1 << b for b in DLC_MAP)
            _state["dlc_unknown_bits"][bit] = mask & ~known
            info["mask"] = mask
            info["owned"] = {str(b): bool((mask >> b) & 1) for b in DLC_MAP}
        else:
            info["type"] = "hex"
            info["preview"] = _hex_preview(chunks[bit])

        chunk_infos.append(info)

    return json.dumps({
        "checksum_ok": is_valid,
        "stored_checksum": stored.hex(),
        "calculated_checksum": calculated.hex(),
        "header": {
            "version": header["version"],
            "git_hash": header["git_hash"].hex(),
            "build_date": header["build_date"],
            "feature_flags": {
                str(bit): bool((header["flags"] >> bit) & 1)
                for bit in FEATURE_FLAG_MAP
            },
        },
        "feature_flag_names": {str(bit): name for bit, name in FEATURE_FLAG_MAP.items()},
        "dlc_names": {str(bit): name for bit, name in DLC_MAP.items()},
        "chunks": chunk_infos,
    })


def tree_children(bit: int, path_json: str, offset: int = 0) -> str:
    path = json.loads(path_json)
    _, _, value, ancestors, _ = _walk(bit, path)
    if isinstance(value, (Obj, dict, list)):
        ancestors = ancestors | {id(value)}

    items = _iter_children(value)
    if not path:
        # `value` is the synthetic list of root objects: label each by its
        # class name (as hxbit.gui does) instead of "[i]".
        items = [
            (root.schema.classdef.name.value if root.schema.classdef else label, elem, root)
            for label, elem, root in items
        ]
    total = len(items)
    chunk = items[offset:offset + _TREE_PAGE_SIZE]

    children = []
    for label, elem, child in chunk:
        is_container = isinstance(child, (Obj, dict, list))
        is_cycle = is_container and id(child) in ancestors
        children.append({
            "path": path + [elem],
            "label": label,
            "kind": _value_kind(child),
            "summary": "<circular reference>" if is_cycle else _value_summary(child),
            "expandable": (not is_cycle) and _is_expandable(child),
            "is_cycle": is_cycle,
        })

    next_offset = offset + len(chunk)
    return json.dumps({
        "children": children,
        "total": total,
        "next_offset": next_offset if next_offset < total else None,
    })


def tree_node(bit: int, path_json: str) -> str:
    path = json.loads(path_json)
    container, _, value, ancestors, labels = _walk(bit, path)
    is_cycle = isinstance(value, (Obj, dict, list)) and id(value) in ancestors

    result: dict[str, Any] = {
        "path_str": _path_str(labels),
        "kind": _value_kind(value),
        "summary": _value_summary(value),
        "is_cycle": is_cycle,
        "editable": False,
    }

    if is_cycle:
        return json.dumps(result)

    if isinstance(value, Obj):
        detail = value.pprint()
        if len(detail) > 200_000:
            detail = detail[:200_000] + "\n… (truncated; expand the tree to inspect nested values)"
        result["detail"] = detail
    elif isinstance(value, (dict, list)):
        result["detail"] = reprlib.Repr(maxlevel=3, maxdict=20, maxlist=20, maxstring=120, maxother=120).repr(value)
    else:
        result["editable"] = container is not None
        result["scalar_type"] = _scalar_type_name(value)
        result["value"] = "" if value is None else _format_scalar(value)

    return json.dumps(result)


def set_value(bit: int, path_json: str, type_name: str, raw_value: str) -> str:
    path = json.loads(path_json)
    container, key, _, _, _ = _walk(bit, path)
    if container is None:
        raise ValueError("This node is not editable.")

    new_value = _parse_scalar(type_name, raw_value)
    container[key] = new_value

    hxs = _state["hxs"][bit]
    # Force serialise() to re-encode from the typed object graph instead of
    # falling back to the preserved raw payload.
    hxs.object_parse_error = None
    hxs.raw_object_data = None

    return tree_node(bit, path_json)


def schemas_text(bit: int) -> str:
    hxs = _state["hxs"][bit]
    return hxs.pprint_classdefs() + "\n\n" + hxs.pprint_schemas()


def set_header(version: str, git_hash_hex: str, build_date: str, feature_flags_json: str) -> None:
    git_hash = bytes.fromhex(git_hash_hex.strip())
    if len(git_hash) != 20:
        raise ValueError("Git hash must be exactly 20 bytes (40 hex characters).")
    feature_flags = json.loads(feature_flags_json)
    _state["header_edit"] = {
        "version": int(version),
        "git_hash": git_hash,
        "build_date": build_date.strip(),
        "feature_flags": {int(bit): bool(enabled) for bit, enabled in feature_flags.items()},
    }


def set_date(bit: int, date_str: str) -> None:
    parsed = datetime.datetime.strptime(date_str.strip(), '%Y-%m-%d %H:%M:%S')
    _state["chunks"][bit] = struct.pack('<d', parsed.timestamp())


def set_version(bit: int, value: str) -> None:
    _state["chunks"][bit] = struct.pack('<f', float(value))


def set_dlc(bit: int, owned_json: str) -> None:
    owned = json.loads(owned_json)
    mask = _state["dlc_unknown_bits"].get(bit, 0)
    for dlc_bit, is_owned in owned.items():
        if is_owned:
            mask |= 1 << int(dlc_bit)
    _state["chunks"][bit] = struct.pack('<I', mask)


def serialise() -> bytes:
    chunks = dict(_state["chunks"])
    for bit, hxs in _state["hxs"].items():
        chunks[bit] = hxs.serialise()

    base_header = _state["header"]
    header_edit = _state["header_edit"] or {}

    known = sum(1 << b for b in SAVE_CONTENT_MAP) | sum(1 << b for b in FEATURE_FLAG_MAP)
    flags = base_header["flags"] & ~known
    for bit in chunks:
        flags |= 1 << bit

    feature_flags = header_edit.get("feature_flags")
    if feature_flags is None:
        feature_flags = {bit: bool((base_header["flags"] >> bit) & 1) for bit in FEATURE_FLAG_MAP}
    for bit, enabled in feature_flags.items():
        if enabled:
            flags |= 1 << bit
        else:
            flags &= ~(1 << bit)

    version = header_edit.get("version", base_header["version"])
    git_hash = header_edit.get("git_hash", base_header["git_hash"])
    build_date = header_edit.get("build_date", base_header["build_date"])

    return build_save_bytes(version, git_hash, build_date, flags, chunks)
