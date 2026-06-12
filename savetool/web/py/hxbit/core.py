
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Dict, Optional, Set, Tuple, Union, BinaryIO, Literal, TypeVar, List
import struct
import inspect
from enum import Enum

from . import shims
from .debug import DEBUG

T = TypeVar("T", bound="VarInt")


def hxbit_hash(name: str) -> int:
    """
    Reimplements the hxbit.Serializer.hash method - takes a string (fully qualified class name) and returns a hashed int.
    """
    v = 1
    for char in name:
        char_code = ord(char)
        v = v * 223 + char_code
        v &= 0xFFFFFFFF
        if v >= 0x80000000:
            v -= 0x100000000
    v &= 0x3FFFFFFF
    v = 1 + (v % 65423)
    return v


def tell(message: str | None = None) -> None:
    """
    Prints the current position in the file-like object.
    Useful for debugging deserialisation.
    """
    global DEBUG
    if not DEBUG:
        return
    frame = inspect.currentframe()
    assert frame is not None
    frame = frame.f_back
    assert frame is not None
    code = frame.f_code
    line_number = frame.f_lineno
    frame_locals = frame.f_locals
    if "f" in frame_locals:
        f = frame_locals["f"]
        print(
            f"DEBUG: {message if message else f'{code.co_filename}:{line_number}':<40} {hex(f.tell())}"
        )
    else:
        print("WARNING: tell() called without a file-like object in locals.")


class Serialisable(ABC):
    """
    Base class for all serialisable objects.
    """

    value: Any

    @abstractmethod
    def __init__(self) -> None:
        self.value = None

    @abstractmethod
    def deserialise(
        self, f: BinaryIO | BytesIO, *args: Any, **kwargs: Any
    ) -> "Serialisable":
        pass

    @abstractmethod
    def serialise(self) -> bytes:
        pass

    def __str__(self) -> str:
        try:
            return str(self.value)
        except AttributeError:
            return super().__repr__()

    def __repr__(self) -> str:
        try:
            return str(self.value)
        except AttributeError:
            return super().__repr__()

    def __eq__(self, other: object) -> Any:
        if not isinstance(other, Serialisable):
            return NotImplemented
        return self.value == other.value

    def __ne__(self, other: object) -> Any:
        if not isinstance(other, Serialisable):
            return NotImplemented
        return self.value != other.value

    def __lt__(self, other: object) -> Any:
        if not isinstance(other, Serialisable):
            return NotImplemented
        return self.value < other.value


class RawData(Serialisable):
    """
    A block of raw data.
    """

    value: bytes
    length: int

    def __init__(self, length: int):
        self.value = b""
        self.length = length

    def deserialise(self, f: BinaryIO | BytesIO) -> "RawData":
        self.value = f.read(self.length)
        return self

    def serialise(self) -> bytes:
        return self.value


class SerialisableInt(Serialisable):
    """
    Integer of the specified byte length.
    """

    value: int
    length: int
    byteorder: Literal["little", "big"]
    signed: bool

    def __init__(self) -> None:
        self.value = -1
        self.length = 4
        self.byteorder = "little"
        self.signed = False

    def deserialise(
        self,
        f: BinaryIO | BytesIO,
        length: int = 4,
        byteorder: Literal["little", "big"] = "little",
        signed: bool = False,
    ) -> "SerialisableInt":
        self.length = length
        self.byteorder = byteorder
        self.signed = signed
        bytes_read = f.read(length)
        if not bytes_read:
            self.value = 0
            return self
        self.value = int.from_bytes(bytes_read, byteorder, signed=signed)
        return self

    def serialise(self) -> bytes:
        return self.value.to_bytes(self.length, self.byteorder, signed=self.signed)


class SerialisableF64(Serialisable):
    """
    A standard 64-bit float.
    """

    value: float

    def __init__(self) -> None:
        self.value = 0.0

    def deserialise(self, f: BinaryIO | BytesIO) -> "SerialisableF64":
        self.value = struct.unpack("<d", f.read(8))[0]
        return self

    def serialise(self) -> bytes:
        return struct.pack("<d", self.value)


class VarInt(Serialisable):
    """
    Represents a variable-length integer using the hxbit serialization format.
    """

    value: int

    def __init__(self, value: int = 0):
        self.value = value

    def deserialise(self: T, f: BinaryIO | BytesIO) -> T:
        tag_byte = f.read(1)
        if not tag_byte:
            raise EOFError("Unexpected end of stream while reading VarInt tag.")

        tag = tag_byte[0]

        if tag == 0x80:
            payload_bytes = f.read(4)
            if len(payload_bytes) < 4:
                raise EOFError(
                    "Unexpected end of stream while reading 4-byte VarInt payload."
                )
            self.value = struct.unpack("<i", payload_bytes)[0]
        else:
            self.value = tag

        return self

    def serialise(self) -> bytes:
        if 0 <= self.value < 0x80:
            return bytes([self.value])
        else:
            marker = b"\x80"
            payload = struct.pack("<i", self.value)
            return marker + payload

    def __repr__(self) -> str:
        return f"VarInt({self.value})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, VarInt):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return NotImplemented


class Resolvable(ABC):
    """
    Base class for resolvable references.
    """

    @abstractmethod
    def resolve_schema(self, context: "HXSFile") -> Any:
        """
        Resolve this reference to a specific reference in the file.
        """
        pass


class ResolvableVarInt(VarInt, Resolvable, ABC):
    """
    Base class for resolvable VarInts. Call `resolve` to get a direct reference to the object it points to.
    """


class String(Serialisable):
    """
    Represents a string using the hxbit serialization format.
    """

    value: str | None

    def __init__(self, value: str | None = None):
        self.value = value

    def deserialise(self, f: BinaryIO | BytesIO) -> "String":
        length_prefix_varint = VarInt().deserialise(f)
        length_plus_one = length_prefix_varint.value

        if length_plus_one == 0:
            self.value = None
            return self

        string_byte_length = length_plus_one - 1

        if string_byte_length > 0:
            string_bytes = f.read(string_byte_length)
            if len(string_bytes) < string_byte_length:
                raise EOFError(
                    f"Expected {string_byte_length} string bytes, but got {len(string_bytes)}."
                )
            try:
                self.value = string_bytes.decode("utf-8")
            except UnicodeDecodeError as e:
                tell("UnicodeDecodeError: " + str(e))
                raise ValueError(
                    f"Failed to decode string bytes: {string_bytes!r}"
                ) from e
        else:
            self.value = ""

        return self

    def serialise(self) -> bytes:
        if self.value is None:
            return VarInt(0).serialise()

        string_bytes = self.value.encode("utf-8")
        length_plus_one = len(string_bytes) + 1
        prefix_bytes = VarInt(length_plus_one).serialise()

        return prefix_bytes + string_bytes

    def __repr__(self) -> str:
        return f"String({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, String):
            return self.value == other.value
        if isinstance(other, str) or other is None:
            return self.value == other
        return NotImplemented


class ClassDef(Serialisable):
    """Represents a single class definition in the HXS header."""

    name: String
    clid: "CLID"
    crc32: SerialisableInt

    def __init__(self) -> None:
        self.name = String()
        self.clid = CLID()
        self.crc32 = SerialisableInt()
        self.crc32.length = 4

    def deserialise(self, f: BinaryIO | BytesIO) -> "ClassDef":
        self.clid.deserialise(f)
        self.crc32.deserialise(f, length=4, byteorder="little", signed=False)
        return self

    def serialise(self) -> bytes:
        return self.name.serialise() + self.clid.serialise() + self.crc32.serialise()

    def __repr__(self) -> str:
        return (
            f"ClassDef(name={self.name.value!r}, clid={self.clid.value}, "
            f"crc32=0x{self.crc32.value:08X})"
        )


class UID(ResolvableVarInt):
    """
    Represents a unique identifier (UID) to a specific class type in the data.
    """

    _resolved: "Schema | None"

    def __init__(self, value: int = 0):
        super().__init__(value)
        self._resolved = None

    def resolve_schema(self, context: "HXSFile") -> "Schema | None":
        """Resolve this UID to its corresponding Schema."""
        if hasattr(context, "schemas"):
            for schema in context.schemas:
                if schema.uid.value == self.value:
                    self._resolved = schema
                    return self._resolved
        return None

    def resolve(self, context: "HXSFile") -> "Obj | None":
        """Resolve this UID to its corresponding Obj in the context."""
        if hasattr(context, "objects"):
            return context.objects.get(self.value, None)
        return None

    @property
    def schema(self) -> "Schema | None":
        """Returns the resolved schema if available."""
        return self._resolved

    def __repr__(self) -> str:
        if self._resolved is not None:
            class_name = None
            if hasattr(self._resolved, "clid") and self._resolved.clid._resolved:  # type: ignore
                class_name = self._resolved.clid.class_name  # type: ignore
            if class_name:
                return f"UID({self.value} -> Schema for {class_name})"
            return f"UID({self.value} -> Schema)"
        return f"UID({self.value})"


class CLID(Resolvable):
    """
    Represents a fixed 2-byte unsigned integer in big-endian order.
    """

    value: int
    _resolved: ClassDef | None

    def __init__(self, value: int = 0):
        if not (0 <= value <= 0xFFFF):
            raise ValueError(f"CLID must be in 0..65535, got {value}")
        self.value = value
        self._resolved = None

    def deserialise(self, f: BinaryIO | BytesIO) -> "CLID":
        data = f.read(2)
        if len(data) < 2:
            raise EOFError("Unexpected end of stream while reading CLID.")
        self.value = struct.unpack(">H", data)[0]
        return self

    def serialise(self) -> bytes:
        return struct.pack(">H", self.value)

    def resolve_schema(self, context: "HXSFile") -> ClassDef | None:
        """Resolve this CLID to its corresponding ClassDef."""
        if hasattr(context, "classdefs"):
            for classdef in context.classdefs:
                if classdef.clid.value == self.value:
                    self._resolved = classdef
                    return self._resolved
        return None

    @property
    def class_name(self) -> str | None:
        """Returns the class name if resolved, otherwise None."""
        if self._resolved:
            return self._resolved.name.value
        return None

    def __repr__(self) -> str:
        if self._resolved is not None:
            return f"CLID({self.value} -> {self._resolved.name.value})"
        elif self.class_name:
            return f"CLID({self.value} -> {self.class_name})"
        return f"CLID({self.value})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CLID):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return NotImplemented


class VarCLID(ResolvableVarInt):
    """
    Represents a variable-length CLID that can be resolved to a specific ClassDef.
    """

    _resolved: ClassDef | None

    def __init__(self, value: int = 0):
        super().__init__(value)
        self._resolved = None

    def resolve_schema(self, context: "HXSFile") -> ClassDef | None:
        """Resolve this VarCLID to its corresponding ClassDef."""
        if hasattr(context, "classdefs"):
            for classdef in context.classdefs:
                if classdef.clid.value == self.value:
                    self._resolved = classdef
                    return self._resolved
        return None

    @property
    def class_name(self) -> str | None:
        """Returns the class name if resolved, otherwise None."""
        if self._resolved:
            return self._resolved.name.value
        return None


class Boolean(Serialisable):
    """
    Represents a boolean value in the hxbit serialization format.
    """

    value: bool

    def __init__(self, value: bool = False):
        self.value = value

    def deserialise(self, f: BinaryIO | BytesIO) -> "Boolean":
        byte = f.read(1)
        if not byte:
            raise EOFError("Unexpected end of stream while reading Boolean.")
        self.value = byte[0] != 0
        return self

    def serialise(self) -> bytes:
        return bytes([1 if self.value else 0])

    def __repr__(self) -> str:
        return f"Boolean({self.value})"


class PropTypeDesc(Serialisable):
    class Kind(Enum):
        PInt = 0
        PFloat = 1
        PBool = 2
        PString = 3
        PBytes = 4
        PSerializable = 5
        PEnum = 6
        PMap = 7
        PArray = 8
        PObj = 9
        PAlias = 10
        PVector = 11
        PNull = 12
        PUnknown = 13
        PDynamic = 14
        PInt64 = 15
        PFlags = 16
        PCustom = 17
        PSerInterface = 18
        POldStruct = 19
        PAliasCDB = 20
        PNoSave = 21
        PStruct = 22

    value: int
    kind: Kind

    def __init__(self, value: int = 0):
        super().__init__()
        self.value = value
        self.kind = PropTypeDesc.Kind(value)

    def deserialise(self, f: BinaryIO | BytesIO) -> "PropTypeDesc":
        byte = f.read(1)
        if not byte:
            raise EOFError("Unexpected end of stream while reading PropTypeDesc kind.")

        stream_value = byte[0]

        if stream_value == 0:
            raise ValueError("This should be handled by the PropType deserializer.")

        haxe_index = stream_value - 1
        self.value = haxe_index
        self.kind = PropTypeDesc.Kind(self.value)
        return self

    def serialise(self) -> bytes:
        value_to_serialise = self.value + 1
        return bytes([value_to_serialise])

    def __repr__(self) -> str:
        return f"PropTypeDesc({self.kind.name})"


class PropTypeDef(Serialisable, ABC):
    @abstractmethod
    def __repr__(self) -> str:
        pass


class Empty(PropTypeDef):
    def __init__(self) -> None:
        pass

    def deserialise(self, f: BinaryIO | BytesIO) -> "Empty":
        return self

    def serialise(self) -> bytes:
        return b""

    def __repr__(self) -> str:
        return "None"


class NameDef(PropTypeDef):
    name: String

    def __init__(self) -> None:
        self.name = String()

    def deserialise(self, f: BinaryIO | BytesIO) -> "NameDef":
        self.name.deserialise(f)
        return self

    def serialise(self) -> bytes:
        return self.name.serialise()

    def __repr__(self) -> str:
        return f"NameDef(name={self.name.value!r})"


class MapDef(PropTypeDef):
    key_type: "PropType"
    value_type: "PropType"

    def __init__(self) -> None:
        self.key_type = PropType()
        self.value_type = PropType()

    def deserialise(self, f: BinaryIO | BytesIO) -> "MapDef":
        self.key_type.deserialise(f)
        self.value_type.deserialise(f)
        return self

    def serialise(self) -> bytes:
        return self.key_type.serialise() + self.value_type.serialise()

    def __repr__(self) -> str:
        return f"MapDef(key_type={self.key_type}, value_type={self.value_type})"


class TypeDef(PropTypeDef):
    type: "PropType"

    def __init__(self) -> None:
        self.type = PropType()

    def deserialise(self, f: BinaryIO | BytesIO) -> "TypeDef":
        self.type.deserialise(f)
        return self

    def serialise(self) -> bytes:
        return self.type.serialise()

    def __repr__(self) -> str:
        return f"TypeDef(type={self.type})"

    def __str__(self) -> str:
        return self.__repr__()


class ObjFieldDef(Serialisable):
    name: String | None
    type: "PropType | None"
    opt: Boolean

    def __init__(self) -> None:
        self.name = None
        self.type = None
        self.opt = Boolean()

    def deserialise(self, f: BinaryIO | BytesIO) -> "ObjFieldDef":
        fbits = VarInt().deserialise(f)

        if fbits.value == 0:
            return self

        val = fbits.value - 1

        if val & 1:
            self.name = String().deserialise(f)

        # Haxe serializes anonymous object fields in alphabetical order.
        # For { name, type, opt }, the on-wire order is name, opt, type.
        self.opt.deserialise(f)

        if val & 2:
            prop_type_val = PropType().deserialise(f)
            self.type = None if prop_type_val.kind is None else prop_type_val

        return self

    def serialise(self) -> bytes:
        return b"".join(
            [
                VarInt(
                    (1 if self.name else 0) + (2 if self.type else 0) + 1
                ).serialise(),
                self.name.serialise() if self.name else b"",
                self.opt.serialise() if self.opt else Boolean(False).serialise(),
                self.type.serialise() if self.type else b"",
            ]
        )

    def __repr__(self) -> str:
        return (
            f"ObjFieldDef(name={self.name.value if self.name else 'None'}, "
            f"type={self.type}, opt={self.opt.value})"
        )


class ObjDef(PropTypeDef):
    fields: List[ObjFieldDef]

    def __init__(self) -> None:
        self.fields = []

    def deserialise(self, f: BinaryIO | BytesIO) -> "ObjDef":
        nfields_plus_1 = VarInt().deserialise(f)
        if nfields_plus_1.value > 1:
            num_fields = nfields_plus_1.value - 1
            for _ in range(num_fields):
                field_def = ObjFieldDef().deserialise(f)
                self.fields.append(field_def)
        return self

    def serialise(self) -> bytes:
        return b"".join(
            [
                VarInt(len(self.fields) + 1).serialise(),
                b"".join(
                    field.serialise() for field in self.fields if field is not None
                ),
            ]
        )

    def __repr__(self) -> str:
        return f"ObjDef(fields={self.fields})"


class OldStruct(PropTypeDef):
    name: String
    fields: List[Dict[str, Union[String, "PropType"]]]

    def __init__(self) -> None:
        self.name = String()
        self.fields = []

    def deserialise(self, f: BinaryIO | BytesIO) -> "OldStruct":
        self.name.deserialise(f)
        nfields = VarInt().deserialise(f).value
        tell(f"Struct '{self.name.value}' has {nfields} fields.")
        for _ in range(nfields):
            field_name = String().deserialise(f)
            field_type = PropType().deserialise(f)
            self.fields.append({"name": field_name, "type": field_type})
        return self

    def serialise(self) -> bytes:
        nfields = VarInt(len(self.fields)).serialise()
        fields_data = b"".join(
            field["name"].serialise() + field["type"].serialise()
            for field in self.fields
        )
        return self.name.serialise() + nfields + fields_data

    def __repr__(self) -> str:
        fields_repr = ", ".join(
            f"{field['name'].value!r}: {field['type']}"
            for field in self.fields
        )
        return f"OldStruct(name={self.name.value!r}, fields=[{fields_repr}])"


class PropType(Serialisable):
    MAP: Dict[PropTypeDesc.Kind, type[PropTypeDef]] = {
        PropTypeDesc.Kind.PInt: Empty,
        PropTypeDesc.Kind.PFloat: Empty,
        PropTypeDesc.Kind.PBool: Empty,
        PropTypeDesc.Kind.PString: Empty,
        PropTypeDesc.Kind.PBytes: Empty,
        PropTypeDesc.Kind.PSerializable: NameDef,
        PropTypeDesc.Kind.PEnum: NameDef,
        PropTypeDesc.Kind.PMap: MapDef,
        PropTypeDesc.Kind.PArray: TypeDef,
        PropTypeDesc.Kind.PObj: ObjDef,
        PropTypeDesc.Kind.PAlias: TypeDef,
        PropTypeDesc.Kind.PVector: TypeDef,
        PropTypeDesc.Kind.PNull: TypeDef,
        PropTypeDesc.Kind.PUnknown: Empty,
        PropTypeDesc.Kind.PDynamic: Empty,
        PropTypeDesc.Kind.PInt64: Empty,
        PropTypeDesc.Kind.PFlags: TypeDef,
        PropTypeDesc.Kind.PCustom: Empty,
        PropTypeDesc.Kind.PSerInterface: NameDef,
        PropTypeDesc.Kind.POldStruct: OldStruct,
        PropTypeDesc.Kind.PAliasCDB: TypeDef,
        PropTypeDesc.Kind.PNoSave: TypeDef,
        PropTypeDesc.Kind.PStruct: NameDef,
    }

    kind: PropTypeDesc | None
    defn: PropTypeDef | None

    def __init__(self) -> None:
        self.kind = None
        self.defn = None

    def deserialise(self, f: BinaryIO | BytesIO) -> "PropType":
        kind_byte_val = f.read(1)
        if not kind_byte_val:
            raise EOFError("Unexpected EOF while reading PropType kind byte.")

        kind_byte = kind_byte_val[0]

        if kind_byte == 0:
            return self

        haxe_index = kind_byte - 1
        self.kind = PropTypeDesc(haxe_index)

        if self.kind.kind in self.MAP:
            self.defn = self.MAP[self.kind.kind]()
            self.defn.deserialise(f)
        else:
            raise ValueError(f"Unknown PropTypeDesc kind: {self.kind.value}")
        return self

    def serialise(self) -> bytes:
        if self.kind is None:
            return b"\x00"

        kind_bytes = self.kind.serialise()
        defn_bytes = self.defn.serialise() if self.defn else b""
        return kind_bytes + defn_bytes

    def __repr__(self) -> str:
        if self.kind is None:
            return "PropType(null)"
        return f"PropType(kind={self.kind.kind.name}, defn={self.defn})"

    def pprint(self, indent: int = 0, context: "HXSFile | None" = None) -> str:
        """Returns a pretty-printed representation of the PropType with proper indentation."""
        if self.kind is None:
            return "null"

        kind_name = self.kind.kind.name

        if isinstance(self.defn, Empty):
            return kind_name
        elif isinstance(self.defn, NameDef):
            return f"{kind_name}<{self.defn.name.value}>"
        elif isinstance(self.defn, TypeDef):
            nested = self.defn.type.pprint(indent + 1, context=context)
            return f"{kind_name}<{nested}>"
        elif isinstance(self.defn, MapDef):
            key_type = self.defn.key_type.pprint(indent + 1, context=context)
            value_type = self.defn.value_type.pprint(indent + 1, context=context)
            return f"{kind_name}<{key_type}, {value_type}>"
        elif isinstance(self.defn, ObjDef):
            if not self.defn.fields:
                return f"{kind_name}{{}}"

            spaces = "  " * (indent + 1)
            fields_str = ""
            for field in self.defn.fields:
                field_name = field.name.value if field.name else "<unnamed>"
                field_type = (
                    field.type.pprint(indent + 1, context=context)
                    if field.type
                    else "<untyped>"
                )
                optional = " (optional)" if field.opt.value else ""
                fields_str += f"\n{spaces}{field_name}: {field_type}{optional}"

            return f"{kind_name}{{{fields_str}\n{'  ' * indent}}}"
        elif isinstance(self.defn, OldStruct):
            if not self.defn.fields:
                return f"{kind_name}<{self.defn.name.value}>{{}}"

            spaces = "  " * (indent + 1)
            fields_str = ""
            for f in self.defn.fields:
                field_name = f["name"].value
                field_type = f["type"].pprint(indent + 1, context=context)  # type: ignore
                fields_str += f"\n{spaces}{field_name}: {field_type}"

            return (
                f"{kind_name}<{self.defn.name.value}>{{{fields_str}\n{'  ' * indent}}}"
            )
        else:
            return f"{kind_name}<{self.defn}>"


class Schema(Serialisable):
    uid: UID
    clid: VarInt
    field_names: List[String]
    field_types: List[PropType]
    classdef: ClassDef | None

    def __init__(self) -> None:
        self.uid = UID()
        self.clid = VarInt()
        self.field_names = []
        self.field_types = []
        self.classdef = None

    def deserialise(self, f: BinaryIO | BytesIO) -> "Schema":
        self.uid.deserialise(f)
        self.clid.deserialise(f)

        nfield_names = VarInt().deserialise(f)
        if nfield_names.value > 1:
            tell(f"Schema has {nfield_names.value - 1} field names")
            for _ in range(nfield_names.value - 1):
                tell("Deserialising field name")
                field_name = String().deserialise(f)
                self.field_names.append(field_name)

        nfield_types = VarInt().deserialise(f)
        if nfield_types.value > 1:
            for _ in range(nfield_types.value - 1):
                field_type = PropType().deserialise(f)
                self.field_types.append(field_type)

        return self

    def serialise(self) -> bytes:
        return b"".join(
            [
                self.uid.serialise(),
                self.clid.serialise(),
                VarInt(len(self.field_names) + 1).serialise(),
                b"".join(field_name.serialise() for field_name in self.field_names),
                VarInt(len(self.field_types) + 1).serialise(),
                b"".join(field_type.serialise() for field_type in self.field_types),
            ]
        )

    def __repr__(self) -> str:
        class_name = self.classdef.name.value if self.classdef else "Unknown"
        return (
            f"Schema(for_class='{class_name}', uid={self.uid}, "
            f"field_names={self.field_names}, "
            f"field_types={self.field_types})"
        )

    def pprint(self, context: "HXSFile | None" = None) -> str:
        """Returns a nicely formatted representation of the schema."""
        class_name = "Unknown Class"
        clid_str = "N/A"
        if self.classdef:
            class_name = self.classdef.name.value or "Unnamed Class"
            clid_str = str(self.classdef.clid.value)

        uid_str = str(self.uid.value)
        if context:
            resolved_uid = self.uid.resolve_schema(context)
            if resolved_uid:
                uid_str = f"{self.uid.value} (resolved)"

        lines = [f"Schema for {class_name} (uid={uid_str}, clid={clid_str})"]

        if self.field_names:
            lines.append("  Fields:")
            for name, field_type in zip(self.field_names, self.field_types):
                field_name = name.value
                type_str = field_type.pprint(indent=2, context=context)
                lines.append(f"    {field_name}: {type_str}")
        else:
            lines.append("  No fields")

        return "\n".join(lines)


class Obj:
    """
    Represents an object in the HXS file.
    It holds a reference to its schema and the HXSFile context for deserialization.
    """

    def __init__(self, schema: "Schema", context: "HXSFile") -> None:
        self.schema = schema
        self.context = context
        self.fields: Dict[str, Any] = {}

    def deserialise(self, f: BinaryIO | BytesIO) -> "Obj":
        """Populates the object's fields by reading from the stream according to its schema."""
        if not self.schema:
            return self

        tell(
            f"Class {self.schema.classdef.name.value if self.schema.classdef else 'Unknown'}"
        )
        for i, field_name in enumerate(self.schema.field_names):
            field_type = self.schema.field_types[i]
            assert field_name.value is not None
            self.context._push_read_context(field_name.value)
            try:
                val = self.context._read_value(f, field_type)
                self.fields[field_name.value] = val
            finally:
                self.context._pop_read_context()
        return self
    
    def serialise(self) -> None:
        """Writes the object's fields to the context's buffer according to its schema."""
        if not self.schema:
            return

        for field_name, field_type in zip(self.schema.field_names, self.schema.field_types):
            assert field_name.value is not None
            value = self.fields.get(field_name.value)
            self.context._write_value(field_type, value)

    def __repr__(self) -> str:
        # Deliberately shallow: the object graph is densely cross-linked, so
        # recursing into self.fields here blows up combinatorially (use
        # pprint() for a deep, cycle-safe dump).
        class_name = (
            self.schema.classdef.name.value
            if self.schema and self.schema.classdef
            else "Unknown"
        )
        return f"<Obj class='{class_name}' ({len(self.fields)} fields)>"
    
    def _format_value(self, value: Any, indent: int, seen: Set[Any]) -> str:
        """Helper function to recursively format values for pretty-printing."""
        
        if isinstance(value, Obj):
            return value.pprint(indent, seen)

        if isinstance(value, list):
            if not value: return "[]"
            inner_indent_str = "  " * (indent + 1)
            items = [f"\n{inner_indent_str}{self._format_value(item, indent + 1, seen)}" for item in value]
            outer_indent_str = "  " * indent
            return f"[{','.join(items)}\n{outer_indent_str}]"

        if isinstance(value, dict):
            if not value: return "{}"
            inner_indent_str = "  " * (indent + 1)
            items = [f"\n{inner_indent_str}{repr(k)}: {self._format_value(v, indent + 1, seen)}" for k, v in value.items()]
            outer_indent_str = "  " * indent
            return f"{{{','.join(items)}\n{outer_indent_str}}}"
        
        if isinstance(value, str):
            return repr(value)
        
        return str(value)

    def pprint(self, indent: int = 0, seen: Set[Any] | None = None) -> str:
        """
        Returns a human-readable, indented string representation of the object,
        with cycle detection to prevent infinite recursion.
        """
        obj_id = id(self)

        if seen is None:
            seen = set()

        if obj_id in seen:
            class_name = self.schema.classdef.name.value if self.schema and self.schema.classdef else "Unknown"
            return f"<Circular Reference to Obj class='{class_name}' id={obj_id}>"

        seen.add(obj_id)

        class_name = self.schema.classdef.name.value if self.schema and self.schema.classdef else "Unknown"
        outer_indent_str = "  " * indent
        header = f"{outer_indent_str}<Obj class='{class_name}'>"

        if not self.fields:
            return f"{header} {{}}"

        lines = [f"{header} {{"]
        inner_indent_str = "  " * (indent + 1)
        
        field_items = list(self.fields.items())
        for i, (key, value) in enumerate(field_items):
            formatted_value = self._format_value(value, indent + 1, seen)
            line_end = "," if i < len(field_items) - 1 else ""
            lines.append(f"{inner_indent_str}{key}: {formatted_value}{line_end}")

        lines.append(f"{outer_indent_str}}}")
        return "\n".join(lines)


class HXSFile(Serialisable):
    magic: String
    version: SerialisableInt
    classdefs: List[ClassDef]
    schema_size: VarInt
    schemas: List[Schema]
    objects: Dict[int, Obj]  # uid, obj

    def __init__(self, shims: Optional[str]=None) -> None:
        self.magic = String("HXS")
        self.version = SerialisableInt()
        self.version.value = 1
        self.version.length = 1
        self.classdefs = []
        self.schema_size = VarInt()
        self.schemas = []
        self.objects = {} # Read cache
        self.obj: Obj | None = None
        self.roots: List["Obj"] = []
        self.raw_object_data: bytes | None = None
        self.object_parse_error: Exception | None = None
        self.unresolved_clids: List[Dict[str, Any]] = []
        self.shims = shims
        self.enum_shims: Dict[str, Any] = {}
        self._read_context: List[str] = []

        # Serialization state
        self.buffer = BytesIO()
        self.written_objects: Dict[int, int] = {} # Python object id -> written UID
        self.next_uid = 1

    def deserialise(self, f: BinaryIO | BytesIO) -> "HXSFile":
        self.magic.deserialise(f)
        assert self.magic.value == "HXS"
        self.version.deserialise(f, length=1)
        assert self.version.value == 1
        while True:
            name = String().deserialise(f)
            if name.value is None:
                break
            cdef = ClassDef()
            cdef.name = name
            cdef.deserialise(f)
            self.classdefs.append(cdef)
        self.schema_size.deserialise(f)
        if self.schema_size.value > 0:
            schemas_start_pos = f.tell()
            schemas_end_pos = schemas_start_pos + self.schema_size.value
            while f.tell() < schemas_end_pos:
                self.schemas.append(Schema().deserialise(f))

        self._link_and_resolve_references()
        if self.shims is not None:
            self._apply_type_shims(shims.shims_for(self.shims))
            self.enum_shims = shims.enums_for(self.shims)
        self.raw_object_data = f.read()
        try:
            self.obj = self._read_root_object(BytesIO(self.raw_object_data))
        except Exception as e:
            self.object_parse_error = e
            self.objects = {}
            self.obj = None

        return self

    def _push_read_context(self, segment: str) -> None:
        self._read_context.append(segment)

    def _pop_read_context(self) -> None:
        if self._read_context:
            self._read_context.pop()

    def _current_read_path(self) -> str:
        if not self._read_context:
            return "<root>"
        return ".".join(self._read_context)

    def _peek_stream_bytes(self, f: BinaryIO | BytesIO, radius: int = 16) -> str | None:
        if not isinstance(f, BytesIO):
            return None
        pos = f.tell()
        data = f.getbuffer()
        start = max(0, pos - radius)
        end = min(len(data), pos + radius)
        return bytes(data[start:end]).hex(" ")

    def _record_unresolved_clid(
        self,
        clid: int,
        declared_schema: "Schema | None",
        f: BinaryIO | BytesIO,
    ) -> None:
        declared_name = None
        if declared_schema is not None and declared_schema.classdef is not None:
            declared_name = declared_schema.classdef.name.value
        self.unresolved_clids.append(
            {
                "clid": clid,
                "path": self._current_read_path(),
                "declared_schema": declared_name,
                "offset": f.tell(),
                "nearby_bytes": self._peek_stream_bytes(f),
            }
        )

    def pprint_unresolved_clids(self) -> str:
        if not self.unresolved_clids:
            return "No unresolved runtime CLIDs recorded."
        lines = ["Unresolved runtime CLIDs:"]
        for item in self.unresolved_clids:
            declared = item["declared_schema"] or "<unknown>"
            lines.append(
                f"  CLID {item['clid']} at {item['path']} "
                f"(declared schema: {declared}, offset: 0x{item['offset']:x})"
            )
            if item["nearby_bytes"]:
                lines.append(f"    bytes: {item['nearby_bytes']}")
        return "\n".join(lines)

    def _create_proptype_from_shim(self, shim: Dict[str, Any]) -> PropType:
        """Creates a PropType object from a shim dictionary definition."""
        prop_type = PropType()
        shim_type_str = shim.get("type")

        if shim_type_str == "Int":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PInt.value)
            prop_type.defn = Empty()
        elif shim_type_str == "Float":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PFloat.value)
            prop_type.defn = Empty()
        elif shim_type_str == "Bool":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PBool.value)
            prop_type.defn = Empty()
        elif shim_type_str == "String":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PString.value)
            prop_type.defn = Empty()
        elif shim_type_str == "Array":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PArray.value)
            type_def = TypeDef()
            type_def.type = self._create_proptype_from_shim(shim["payload"])
            prop_type.defn = type_def
        elif shim_type_str == "Enum":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PEnum.value)
            name_def = NameDef()
            name_def.name = String(shim["name"])
            prop_type.defn = name_def
        elif shim_type_str == "Serializable":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PSerializable.value)
            name_def = NameDef()
            name_def.name = String(shim["name"])
            prop_type.defn = name_def
        elif shim_type_str == "Null":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PNull.value)
            type_def = TypeDef()
            type_def.type = self._create_proptype_from_shim(shim["payload"])
            prop_type.defn = type_def
        elif shim_type_str == "Obj":
            prop_type.kind = PropTypeDesc(PropTypeDesc.Kind.PObj.value)
            obj_def = ObjDef()
            shim_fields = shim.get("fields", {})
            for field_name, field_shim in shim_fields.items():
                obj_field_def = ObjFieldDef()
                obj_field_def.name = String(field_name)
                obj_field_def.type = self._create_proptype_from_shim(field_shim)
                obj_field_def.opt = Boolean(True)  # Shims are for optional fields
                obj_def.fields.append(obj_field_def)
            prop_type.defn = obj_def
        else:
            raise ValueError(f"Unsupported shim type: '{shim_type_str}'")

        return prop_type

    def _apply_type_shims(self, shims: Dict[str, Any]) -> None:
        """
        Patches the parsed schemas with externally provided type definitions (shims)
        to fill in gaps where the original schema is incomplete.
        """
        for schema in self.schemas:
            if not schema.classdef or not schema.classdef.name.value:
                continue
            class_name = schema.classdef.name.value

            for i, field_name_obj in enumerate(schema.field_names):
                field_name = field_name_obj.value
                shim_key = f"{class_name}.{field_name}"

                if shim_key in shims:
                    current_prop_type = schema.field_types[i]
                    # Check if the type is PArray<PObj>
                    is_array_of_obj = (
                        current_prop_type.kind
                        and current_prop_type.kind.kind == PropTypeDesc.Kind.PArray
                        and isinstance(current_prop_type.defn, TypeDef)
                        and current_prop_type.defn.type
                        and current_prop_type.defn.type.kind
                        and current_prop_type.defn.type.kind.kind
                        == PropTypeDesc.Kind.PObj
                        and isinstance(current_prop_type.defn.type.defn, ObjDef)
                    )

                    if not is_array_of_obj:
                        continue

                    # Check if the inner PObj has untyped fields, which is the problem we're solving.
                    assert isinstance(current_prop_type.defn, TypeDef)
                    obj_def = current_prop_type.defn.type.defn
                    assert isinstance(obj_def, ObjDef)
                    has_untyped_fields = any(f.type is None for f in obj_def.fields)

                    if has_untyped_fields:
                        # This schema is a candidate for patching.
                        # Replace the entire PropType with a new one generated from the shim.
                        shim_data = shims[shim_key]
                        new_prop_type = self._create_proptype_from_shim(shim_data)
                        
                        # Replace the old, incomplete PropType with the new one
                        schema.field_types[i] = new_prop_type

    def _is_field_nullable(self, prop_type: PropType | None) -> bool:
        """Determines if a field type is nullable according to hxbit rules."""
        if not prop_type or not prop_type.kind:
            return True

        kind = prop_type.kind.kind

        if kind in [
            PropTypeDesc.Kind.PInt,
            PropTypeDesc.Kind.PFloat,
            PropTypeDesc.Kind.PBool,
            PropTypeDesc.Kind.PInt64,
            PropTypeDesc.Kind.PFlags,
        ]:
            return False

        if kind in [
            PropTypeDesc.Kind.PAlias,
            PropTypeDesc.Kind.PAliasCDB,
            PropTypeDesc.Kind.PNoSave,
        ] and isinstance(prop_type.defn, TypeDef):
            return self._is_field_nullable(prop_type.defn.type)

        return True

    def _read_dynamic_value(self, f: BinaryIO | BytesIO) -> Any:
        prefix = f.read(1)[0]
        if prefix == 0: return None
        if prefix == 1: return False
        if prefix == 2: return True
        if prefix == 3: return VarInt().deserialise(f).value
        if prefix == 4: return struct.unpack("<f", f.read(4))[0]
        if prefix == 5:
            d = {}
            count = VarInt().deserialise(f).value
            for _ in range(count):
                key = String().deserialise(f).value
                value = self._read_dynamic_value(f)
                if key is not None:
                    d[key] = value
            return d
        if prefix == 6: return String().deserialise(f).value
        if prefix == 7:
            count = VarInt().deserialise(f).value
            return [self._read_dynamic_value(f) for _ in range(count)]
        if prefix == 8: return String().deserialise(f).value
        if prefix == 9:
             uid = VarInt().deserialise(f).value
             return f"<Dynamic Object UID:{uid}>"
        if prefix == 10:
            enum_name = String().deserialise(f).value
            constructor_index = VarInt().deserialise(f).value
            return f"DynamicEnum<{enum_name}>({constructor_index})"
        raise ValueError(f"Invalid dynamic type prefix: {prefix}")

    def _read_value(self, f: BinaryIO | BytesIO, prop_type: PropType | None) -> Any:
        if prop_type is None: return None
        if prop_type.kind is None: return None
        kind, defn = prop_type.kind.kind, prop_type.defn

        if kind in [PropTypeDesc.Kind.PInt, PropTypeDesc.Kind.PFlags]: return VarInt().deserialise(f).value
        if kind == PropTypeDesc.Kind.PFloat: return struct.unpack("<f", f.read(4))[0]
        if kind == PropTypeDesc.Kind.PBool: return f.read(1)[0] != 0
        if kind == PropTypeDesc.Kind.PInt64: return struct.unpack("<q", f.read(8))[0]
        if kind == PropTypeDesc.Kind.PString: return String().deserialise(f).value
        if kind == PropTypeDesc.Kind.PBytes:
            length = VarInt().deserialise(f).value
            if length == 0: return None
            return f.read(length - 1)
        if kind in [PropTypeDesc.Kind.PArray, PropTypeDesc.Kind.PVector] and isinstance(defn, TypeDef):
            count = VarInt().deserialise(f).value
            if count == 0: return None
            values = []
            for i in range(count - 1):
                self._push_read_context(f"[{i}]")
                try:
                    values.append(self._read_value(f, defn.type))
                finally:
                    self._pop_read_context()
            return values
        if kind == PropTypeDesc.Kind.PMap and isinstance(defn, MapDef):
            count = VarInt().deserialise(f).value
            if count == 0: return None
            values = {}
            for i in range(count - 1):
                self._push_read_context(f"<key:{i}>")
                try:
                    key = self._read_value(f, defn.key_type)
                finally:
                    self._pop_read_context()
                self._push_read_context(f"[{key!r}]")
                try:
                    values[key] = self._read_value(f, defn.value_type)
                finally:
                    self._pop_read_context()
            return values
        if kind == PropTypeDesc.Kind.PSerializable and isinstance(defn, NameDef):
            schema = self._get_schema_by_name(defn.name.value)
            return self._read_ref(f, schema)
        if kind == PropTypeDesc.Kind.PSerInterface:
            return self._read_ref(f, None)
        if kind == PropTypeDesc.Kind.PEnum and isinstance(defn, NameDef):
            constructor = f.read(1)[0]
            if constructor == 0:
                return None
            index = constructor - 1
            enum_name = defn.name.value
            ctors = self.enum_shims.get(enum_name) if enum_name else None
            if ctors and index < len(ctors) and ctors[index]["args"]:
                ctor = ctors[index]
                args = []
                for j, arg_shim in enumerate(ctor["args"]):
                    self._push_read_context(f"{enum_name}.{ctor['name']}<arg{j}>")
                    try:
                        args.append(
                            self._read_value(f, self._create_proptype_from_shim(arg_shim))
                        )
                    finally:
                        self._pop_read_context()
                return {
                    "__enum__": enum_name,
                    "constructor": index,
                    "name": ctor["name"],
                    "args": args,
                }
            return f"Enum<{enum_name}>({index})"
        if kind == PropTypeDesc.Kind.PNull and isinstance(defn, TypeDef):
            return self._read_value(f, defn.type) if f.read(1)[0] != 0 else None
        if kind == PropTypeDesc.Kind.PAlias and isinstance(defn, TypeDef):
            return self._read_value(f, defn.type)
        if kind == PropTypeDesc.Kind.PAliasCDB and isinstance(defn, TypeDef):
            return self._read_value(f, defn.type)
        if kind == PropTypeDesc.Kind.PNoSave and isinstance(defn, TypeDef):
            return self._read_value(f, defn.type)
        if kind == PropTypeDesc.Kind.PObj and isinstance(defn, ObjDef):
            bits = VarInt().deserialise(f).value
            if bits == 0: return None
            bits -= 1
            obj_data, bit_idx = {}, 0
            for field_def in defn.fields:
                field_name = field_def.name.value if field_def.name else f"<unnamed_{bit_idx}>"
                is_present = True
                if self._is_field_nullable(field_def.type):
                    is_present = (bits & (1 << bit_idx)) != 0
                    bit_idx += 1
                if is_present:
                    if field_def.type:
                        tell(f"_read_value field {field_name}: {field_def.type.kind.kind} ") # type: ignore
                        obj_data[field_name] = self._read_value(f, field_def.type)
                        tell(f"value: {obj_data[field_name]}")
                    else:
                        tell(f"string hack {field_name}")
                        obj_data[field_name] = String().deserialise(f).value
            return obj_data
        
        raise NotImplementedError(f"Deserialization for {kind.name} is not implemented.")

    def _read_root_object(self, f: BinaryIO | BytesIO) -> "Obj | None":
        # The root class is not stored in the file: the game passes it to
        # hxbit's unserializer. A file may also contain several root objects
        # back to back (e.g. Dead Cells' "UserAndGameData"). For each root,
        # try every schema and keep the one that consumes the most data,
        # preferring one that reaches the end of the buffer.
        total = len(f.getbuffer()) if isinstance(f, BytesIO) else None
        roots: List[Obj] = []
        saved_objects: Dict[int, Obj] = {}

        while True:
            uid_val = VarInt().deserialise(f).value
            if uid_val == 0:
                break
            start = f.tell()

            def attempt(schema: "Schema") -> "Obj":
                f.seek(start)
                self.objects = dict(saved_objects)
                self._read_context = []
                self.unresolved_clids = []
                resolved = self._resolve_runtime_schema(f, schema)
                obj = Obj(resolved, self)
                self.objects[uid_val] = obj
                obj.deserialise(f)
                return obj

            chosen: Obj | None = None
            best_schema: "Schema | None" = None
            best_pos = -1
            best_err: Exception | None = None
            best_err_pos = -1
            for schema in self.schemas:
                try:
                    obj = attempt(schema)
                except Exception as e:
                    if f.tell() > best_err_pos:
                        best_err_pos = f.tell()
                        best_err = e
                    continue
                if total is None or f.tell() == total:
                    chosen = obj
                    break
                if f.tell() > best_pos:
                    best_pos = f.tell()
                    best_schema = schema
            if chosen is None:
                if best_schema is not None:
                    chosen = attempt(best_schema)
                elif best_err is not None:
                    raise best_err
                else:
                    raise ValueError("No schema produced a valid root object parse.")
            if f.tell() == start:
                raise ValueError(
                    f"Root object parse made no progress at offset 0x{start:x}."
                )
            roots.append(chosen)
            saved_objects = self.objects
            if total is None or f.tell() >= total:
                break

        self.roots = roots
        return roots[0] if roots else None

    def _read_ref(self, f: BinaryIO | BytesIO, schema: "Schema | None") -> "Obj | None":
        uid_val = VarInt().deserialise(f).value
        if uid_val == 0: return None
        if uid_val in self.objects: return self.objects[uid_val]
        schema = self._resolve_runtime_schema(f, schema)
        obj = Obj(schema, self)
        self.objects[uid_val] = obj
        obj.deserialise(f)
        return obj

    def _write_value(self, prop_type: PropType, value: Any) -> None:
        """Writes a single typed Python value to the buffer."""
        if prop_type.kind is None: return
        kind, defn = prop_type.kind.kind, prop_type.defn
        
        if kind in [PropTypeDesc.Kind.PInt, PropTypeDesc.Kind.PFlags]:
            self.buffer.write(VarInt(value).serialise())
        elif kind == PropTypeDesc.Kind.PFloat:
            self.buffer.write(struct.pack("<f", value))
        elif kind == PropTypeDesc.Kind.PBool:
            self.buffer.write(bytes([1 if value else 0]))
        elif kind == PropTypeDesc.Kind.PInt64:
            self.buffer.write(struct.pack("<q", value))
        elif kind == PropTypeDesc.Kind.PString:
            self.buffer.write(String(value).serialise())
        elif kind == PropTypeDesc.Kind.PBytes:
            if value is None:
                self.buffer.write(VarInt(0).serialise())
            else:
                self.buffer.write(VarInt(len(value) + 1).serialise())
                self.buffer.write(value)
        
        elif kind in [PropTypeDesc.Kind.PArray, PropTypeDesc.Kind.PVector] and isinstance(defn, TypeDef):
            if value is None:
                self.buffer.write(VarInt(0).serialise())
            else:
                self.buffer.write(VarInt(len(value) + 1).serialise())
                for item in value:
                    self._write_value(defn.type, item)
        
        elif kind == PropTypeDesc.Kind.PMap and isinstance(defn, MapDef):
            if value is None:
                self.buffer.write(VarInt(0).serialise())
            else:
                self.buffer.write(VarInt(len(value) + 1).serialise())
                for k, v in value.items():
                    self._write_value(defn.key_type, k)
                    self._write_value(defn.value_type, v)
        
        elif kind == PropTypeDesc.Kind.PSerializable and isinstance(defn, NameDef):
            self._write_ref(value, self._get_schema_by_name(defn.name.value))

        elif kind == PropTypeDesc.Kind.PSerInterface:
            self._write_ref(value, None)

        elif kind == PropTypeDesc.Kind.PObj and isinstance(defn, ObjDef):
            if value is None:
                self.buffer.write(VarInt(0).serialise())
            else:
                bits, bit_idx = 0, 0
                for field_def in defn.fields:
                    if self._is_field_nullable(field_def.type):
                        field_name = field_def.name.value if field_def.name else f"<unnamed_{bit_idx}>"
                        if value.get(field_name) is not None:
                            bits |= (1 << bit_idx)
                        bit_idx += 1
                self.buffer.write(VarInt(bits + 1).serialise())
                
                bit_idx = 0
                for field_def in defn.fields:
                    field_name = field_def.name.value if field_def.name else f"<unnamed_{bit_idx}>"
                    field_value = value.get(field_name)
                    
                    is_present = True
                    if self._is_field_nullable(field_def.type):
                        is_present = (bits & (1 << bit_idx)) != 0
                        bit_idx += 1
                    
                    if is_present:
                        if field_def.type:
                            self._write_value(field_def.type, field_value)
                        else: # The untyped string hack
                            self.buffer.write(String(field_value).serialise())

        elif kind == PropTypeDesc.Kind.PEnum:
            if value is None:
                self.buffer.write(b'\x00')
            elif isinstance(value, dict) and "__enum__" in value:
                self.buffer.write(bytes([value["constructor"] + 1]))
                ctors = self.enum_shims.get(value["__enum__"]) or []
                ctor = ctors[value["constructor"]]
                for arg_shim, arg_value in zip(ctor["args"], value["args"]):
                    self._write_value(self._create_proptype_from_shim(arg_shim), arg_value)
            elif isinstance(value, str) and value.endswith(')'):
                # "Enum<Name>(123)" — stored index is constructor + 1
                num_str = value.split('(')[-1][:-1]
                self.buffer.write(bytes([int(num_str) + 1]))
            else: # Fallback for unknown enum format
                print("WARNING: enum fallback format")
                self.buffer.write(VarInt(0).serialise())
                
        elif kind == PropTypeDesc.Kind.PNull and isinstance(defn, TypeDef):
            if value is None:
                self.buffer.write(b'\x00')
            else:
                self.buffer.write(b'\x01')
                self._write_value(defn.type, value)

        else:
            raise NotImplementedError(f"Serialization for {kind.name} is not implemented.")

    def _write_ref(self, obj: Obj | None, declared_schema: "Schema | None" = None) -> None:
        """Writes an object reference.
        """
        if obj is None:
            self.buffer.write(VarInt(0).serialise())
            return

        obj_id = id(obj)
        if obj_id in self.written_objects:
            uid = self.written_objects[obj_id]
            self.buffer.write(VarInt(uid).serialise())
            return

        new_uid = self.next_uid
        self.next_uid += 1

        self.written_objects[obj_id] = new_uid
        self.buffer.write(VarInt(new_uid).serialise())

        if declared_schema is None or declared_schema.clid.value == 0:
            class_name = (
                obj.schema.classdef.name.value
                if obj.schema and obj.schema.classdef
                else None
            )
            if class_name is None:
                raise ValueError(
                    "Cannot write a polymorphic reference to an object with no class name."
                )
            self.buffer.write(struct.pack(">H", self.clid_hash(class_name)))

        obj.serialise()

    def serialise(self) -> bytes:
        # Re-initialize serialization state
        self.buffer = BytesIO()
        self.written_objects = {}
        self.next_uid = 1

        # Write the object data first to a temporary buffer, unless we had to
        # preserve an opaque payload because typed deserialization failed.
        if self.raw_object_data is not None:
            object_data = self.raw_object_data
        else:
            for root in (self.roots or ([self.obj] if self.obj else [])):
                self._write_ref(root, root.schema)
            object_data = self.buffer.getvalue()
        
        # Now, build the final file with the header and object data
        final_buffer = BytesIO()
        final_buffer.write(self.magic.serialise())
        final_buffer.write(self.version.serialise())
        
        # Write class definitions
        for cdef in self.classdefs:
            final_buffer.write(cdef.serialise())
        final_buffer.write(String(None).serialise()) # End of class defs marker

        # Write schema definitions
        schema_bytes = b"".join(s.serialise() for s in self.schemas)
        self.schema_size.value = len(schema_bytes)
        final_buffer.write(self.schema_size.serialise())
        final_buffer.write(schema_bytes)
        
        # Write the main object data
        final_buffer.write(object_data)

        return final_buffer.getvalue()

    @classmethod
    def from_path(cls, path: str, shims: str | None = None) -> "HXSFile":
        with open(path, "rb") as f:
            instance = cls(shims=shims).deserialise(f)
        return instance

    @classmethod
    def from_bytes(cls, data: bytes, shims: str | None = None) -> "HXSFile":
        with BytesIO(data) as f:
            instance = cls(shims=shims).deserialise(f)
        return instance

    def pprint_schemas(self) -> str:
        """Returns a nicely formatted representation of all schemas."""
        if not self.schemas:
            return "No schemas found"
        self._link_and_resolve_references()
        lines = [f"Found {len(self.schemas)} schemas:", ""]
        for schema in self.schemas:
            lines.append(schema.pprint(context=self))
            lines.append("")
        return "\n".join(lines)

    def _link_and_resolve_references(self) -> None:
        if len(self.classdefs) == len(self.schemas):
            for i, schema in enumerate(self.schemas):
                schema.classdef = self.classdefs[i]
        for classdef in self.classdefs:
            if isinstance(classdef.clid, Resolvable):
                classdef.clid.resolve_schema(self)
        for schema in self.schemas:
            if isinstance(schema.uid, Resolvable):
                schema.uid.resolve_schema(self)
            for field_type in schema.field_types:
                self._resolve_prop_type(field_type)

    def _resolve_prop_type(self, prop_type: PropType) -> None:
        if prop_type.defn is None: return
        if isinstance(prop_type.defn, TypeDef): self._resolve_prop_type(prop_type.defn.type)
        elif isinstance(prop_type.defn, MapDef):
            self._resolve_prop_type(prop_type.defn.key_type)
            self._resolve_prop_type(prop_type.defn.value_type)
        elif isinstance(prop_type.defn, ObjDef):
            for field in prop_type.defn.fields:
                if field.type: self._resolve_prop_type(field.type)
        elif isinstance(prop_type.defn, OldStruct):
            for f in prop_type.defn.fields:
                if isinstance(f.get("type"), PropType):
                    self._resolve_prop_type(f["type"])  # type: ignore[index]

    def pprint_classdefs(self) -> str:
        if not self.classdefs: return "No class definitions found"
        lines = [f"Found {len(self.classdefs)} class definitions:", ""]
        for classdef in self.classdefs:
            lines.append( f"  {classdef.name.value} (CLID: {classdef.clid.value}, CRC32: 0x{classdef.crc32.value:08X})")
        return "\n".join(lines)

    def get_class_by_name(self, name: str) -> Tuple[ClassDef, Schema]:
        for i, class_def in enumerate(self.classdefs):
            if class_def.name.value == name:
                if i < len(self.schemas):
                    return (class_def, self.schemas[i])
                else:
                    raise IndexError( f"Found ClassDef for '{name}' at index {i}, but no corresponding Schema exists.")
        raise ValueError(f"Class with name '{name}' not found.")

    def _get_schema_by_name(self, name: str | None) -> "Schema | None":
        if name is None:
            return None
        try:
            _, schema = self.get_class_by_name(name)
            return schema
        except ValueError:
            return None

    # hxbit's runtime class id: a hash of the class name. Runtime refs to
    # polymorphic classes store this hash, NOT the 2-byte value in the
    # ClassDef header (which is the class's index in the game's
    # hxbit.Serializer.CLASSES list).
    clid_hash = staticmethod(hxbit_hash)

    def _get_schema_by_clid(self, clid: int) -> "Schema":
        for i, class_def in enumerate(self.classdefs):
            name = class_def.name.value
            if name is not None and self.clid_hash(name) == clid:
                return self.schemas[i]
        raise ValueError(f"Schema with CLID '{clid}' not found.")

    def _resolve_runtime_schema(
        self, f: BinaryIO | BytesIO, declared_schema: "Schema | None"
    ) -> "Schema":
        if declared_schema is not None and declared_schema.clid.value != 0:
            return declared_schema

        runtime_clid = CLID().deserialise(f)
        try:
            return self._get_schema_by_clid(runtime_clid.value)
        except ValueError as e:
            self._record_unresolved_clid(runtime_clid.value, declared_schema, f)
            declared_name = None
            if declared_schema is not None and declared_schema.classdef is not None:
                declared_name = declared_schema.classdef.name.value
            path = self._current_read_path()
            detail = (
                f"Schema with CLID '{runtime_clid.value}' not found "
                f"at {path} (declared schema: {declared_name or '<unknown>'}, "
                f"offset: 0x{f.tell():x})"
            )
            raise ValueError(detail) from e
