// Decompiled with JetBrains decompiler
// Type: PAKTool.FileData
// Assembly: PAKTool, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: ECC9A4AB-62C6-4F7C-95CE-FBC3CF0F40A2
// Assembly location: D:\SteamLibrary\steamapps\common\Dead Cells\ModTools\PAKTool.exe

#nullable disable
namespace PAKTool
{
  internal class FileData : EntryData
  {
    public int position { get; private set; }

    public int size { get; private set; }

    public int checksum { get; private set; }

    public override bool isDirectory => false;

    public FileData(DirectoryData _parent, string _name, int _position, int _size, int _crc)
      : base(_parent, _name)
    {
      this.position = _position;
      this.size = _size;
      this.checksum = _crc;
    }
  }
}
