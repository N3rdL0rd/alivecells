// Decompiled with JetBrains decompiler
// Type: PAKTool.EntryData
// Assembly: PAKTool, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: ECC9A4AB-62C6-4F7C-95CE-FBC3CF0F40A2
// Assembly location: D:\SteamLibrary\steamapps\common\Dead Cells\ModTools\PAKTool.exe

using System.IO;

#nullable disable
namespace PAKTool
{
  internal abstract class EntryData
  {
    public abstract bool isDirectory { get; }

    public string name { get; private set; }

    public string fullName
    {
      get
      {
        DirectoryData parent = this.parent;
        return parent != null ? Path.Combine(parent.fullName, this.name) : this.name;
      }
    }

    public DirectoryData parent { get; private set; }

    public EntryData(DirectoryData _parent, string _name)
    {
      this.name = _name;
      this.parent = _parent;
    }
  }
}
