// Decompiled with JetBrains decompiler
// Type: PAKTool.DirectoryData
// Assembly: PAKTool, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: ECC9A4AB-62C6-4F7C-95CE-FBC3CF0F40A2
// Assembly location: D:\SteamLibrary\steamapps\common\Dead Cells\ModTools\PAKTool.exe

using System.Collections.Generic;

#nullable disable
namespace PAKTool
{
  internal class DirectoryData : EntryData
  {
    public override bool isDirectory => true;

    public DirectoryData(DirectoryData _parent, string _name)
      : base(_parent, _name)
    {
    }

    public void AddEntry(EntryData _entry)
    {
      if (_entry.isDirectory)
        this.directories.Add((DirectoryData) _entry);
      else
        this.files.Add((FileData) _entry);
    }

    public List<FileData> files { get; private set; } = new List<FileData>();

    public List<DirectoryData> directories { get; private set; } = new List<DirectoryData>();
  }
}
