// Decompiled with JetBrains decompiler
// Type: PAKTool.PAKTool
// Assembly: PAKTool, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: ECC9A4AB-62C6-4F7C-95CE-FBC3CF0F40A2
// Assembly location: D:\SteamLibrary\steamapps\common\Dead Cells\ModTools\PAKTool.exe

using ModTools;
using System;
using System.Collections.Generic;
using System.IO;

#nullable disable
namespace PAKTool
{
    internal class PAKTool
    {
        private Dictionary<string, EntryData> headerData = new Dictionary<string, EntryData>();

        public byte version { get; private set; }

        public DirectoryData root { get; private set; }

        public void ExpandPAK(string _pakPath, string _destination)
        {
            if (!File.Exists(_pakPath))
                throw new FileNotFoundException("File not found: " + _pakPath, _pakPath);
            DirectoryInfo directory = Directory.CreateDirectory(_destination);
            BinaryReader _reader = this.ReadPAKHeader(_pakPath);
            this.CreateTree(_reader, directory, this.root);
            _reader.Close();
        }

        public void BuildPAK(string _expandedPakPath, string _destination)
        {
            DirectoryInfo directoryInfo = new DirectoryInfo(_expandedPakPath);
            if (!directoryInfo.Exists)
                throw new DirectoryNotFoundException("Directory " + _expandedPakPath + " not found");
            FileInfo fileInfo = new FileInfo(_destination);
            fileInfo.Directory.Create();
            this.root = new DirectoryData((DirectoryData)null, "");
            this.dataSize = 0;
            this.headerSize = 0;
            this.version = (byte)0;
            this.CreatePAKDirectory(this.root, directoryInfo);
            this.headerSize += 16;
            BinaryWriter _writer = new BinaryWriter((Stream)fileInfo.Create());
            _writer.Write(new char[3] { 'P', 'A', 'K' });
            _writer.Write(this.version);
            _writer.Write(this.headerSize);
            _writer.Write(this.dataSize);
            this.WritePAKEntry(_writer, (EntryData)this.root);
            _writer.Write(new char[4] { 'D', 'A', 'T', 'A' });
            this.WritePAKContent(_writer, directoryInfo);
            _writer.Close();
        }

        public void BuildPAKStamped(string _expandedPakPath, string _destination, string stamp)
        {
            if (stamp.Length != 64)
            {
                throw new FormatException("Stamp should be 64 bytes long.");
            }

            DirectoryInfo directoryInfo = new DirectoryInfo(_expandedPakPath);
            if (!directoryInfo.Exists)
                throw new DirectoryNotFoundException("Directory " + _expandedPakPath + " not found");

            FileInfo fileInfo = new FileInfo(_destination);
            fileInfo.Directory.Create();

            this.root = new DirectoryData((DirectoryData)null, "");
            this.dataSize = 0;
            this.headerSize = 0;
            this.version = (byte)1;
            this.CreatePAKDirectory(this.root, directoryInfo);

            this.headerSize += 16 + 64; // extra 64 for the stamp

            using (BinaryWriter _writer = new BinaryWriter(fileInfo.Create()))
            {
                _writer.Write(new char[3] { 'P', 'A', 'K' });
                _writer.Write(this.version);
                _writer.Write(this.headerSize);
                _writer.Write(this.dataSize);

                // HACK: writing without conversion breaks things, somehow
                byte[] stampBytes = System.Text.Encoding.ASCII.GetBytes(stamp);
                _writer.Write(stampBytes);

                this.WritePAKEntry(_writer, (EntryData)this.root);
                _writer.Write(new char[4] { 'D', 'A', 'T', 'A' });
                this.WritePAKContent(_writer, directoryInfo);
            }
        }

        public void BuildDiffPAK(string _referencePAK, string _inputDir, string _diffPAKPath)
        {
            DirectoryInfo directoryInfo1 = new DirectoryInfo(_inputDir);
            if (!directoryInfo1.Exists)
                throw new DirectoryNotFoundException("Directory " + _inputDir + " not found.");
            BinaryReader binaryReader = this.ReadPAKHeader(_referencePAK);
            Dictionary<string, int> dictionary1 = new Dictionary<string, int>();
            List<DirectoryData> directoryDataList = new List<DirectoryData>();
            directoryDataList.Add(this.root);
            for (int index = 0; index < directoryDataList.Count; ++index)
            {
                foreach (FileData file in directoryDataList[index].files)
                    dictionary1.Add(file.fullName, file.checksum);
                foreach (DirectoryData directory in directoryDataList[index].directories)
                    directoryDataList.Add(directory);
            }
            Dictionary<string, int> dictionary2 = new Dictionary<string, int>();
            Adler32 adler32 = new Adler32();
            if (_inputDir.Length > 0 && _inputDir[_inputDir.Length - 1] != '\\')
                _inputDir += "\\";
            foreach (FileInfo file in directoryInfo1.GetFiles("*.*", SearchOption.AllDirectories))
                dictionary2.Add(file.FullName.Replace(_inputDir, ""), adler32.Make((Stream)File.OpenRead(file.FullName)));
            List<string> stringList = new List<string>();
            DirectoryInfo directoryInfo2 = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
            directoryInfo2.Create();
            bool flag = false;
            foreach (KeyValuePair<string, int> keyValuePair in dictionary2)
            {
                int num;
                if (dictionary1.TryGetValue(keyValuePair.Key, out num))
                {
                    if (num != keyValuePair.Value)
                    {
                        if (keyValuePair.Key.Substring(keyValuePair.Key.Length - 4, 4).ToUpper() == ".CDB")
                        {
                            CDBTool.CDBTool cdbTool = new CDBTool.CDBTool();
                            DirectoryInfo directoryInfo3 = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
                            directoryInfo3.Create();
                            string str = Path.Combine(directoryInfo3.FullName, keyValuePair.Key);
                            EntryData entryData;
                            if (!this.headerData.TryGetValue(keyValuePair.Key, out entryData))
                                throw new Exception("original CDB called " + keyValuePair.Key + " not found.");
                            FileData fileData = (FileData)entryData;
                            FileStream fileStream = new FileStream(str, FileMode.OpenOrCreate);
                            binaryReader.BaseStream.Seek((long)fileData.position, SeekOrigin.Begin);
                            fileStream.Write(binaryReader.ReadBytes(fileData.size), 0, fileData.size);
                            fileStream.Close();
                            DirectoryInfo directoryInfo4 = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
                            cdbTool.Expand(Path.Combine(_inputDir, keyValuePair.Key), directoryInfo4.FullName);
                            DirectoryInfo directoryInfo5 = new DirectoryInfo(Path.Combine(directoryInfo2.FullName, keyValuePair.Key + "_"));
                            directoryInfo5.Create();
                            cdbTool.BuildDiffCDB(str, directoryInfo4.FullName, directoryInfo5.FullName);
                            flag = true;
                        }
                        else
                            stringList.Add(Path.Combine(directoryInfo2.FullName, keyValuePair.Key));
                    }
                }
                else
                    stringList.Add(Path.Combine(directoryInfo2.FullName, keyValuePair.Key));
            }
            binaryReader.Close();
            if (stringList.Count == 0 && !flag)
                throw new Exception("No diff pak created, no changed or added files found.");
            foreach (string fileName in stringList)
            {
                FileInfo fileInfo = new FileInfo(fileName);
                fileInfo.Directory.Create();
                File.Copy(Path.Combine(_inputDir, fileName.Replace(directoryInfo2.FullName, "").Substring(1)), fileInfo.FullName);
            }
            this.BuildPAK(directoryInfo2.FullName, _diffPAKPath);
            directoryInfo2.Delete(true);
        }

        private BinaryReader ReadPAKHeader(string _pakPath)
        {
            this.headerData.Clear();
            BinaryReader _reader = new BinaryReader((Stream)File.OpenRead(_pakPath));
            string str = new string(_reader.ReadChars(3));
            this.version = _reader.ReadByte();
            this.headerSize = _reader.ReadInt32();
            this.dataSize = _reader.ReadInt32();
            if (this.version >= (byte)1)
                _reader.ReadChars(64);
            this.root = (DirectoryData)this.ReadPAKEntry(_reader, (DirectoryData)null);
            return _reader;
        }

        private void CreatePAKDirectory(DirectoryData _pakDirectory, DirectoryInfo _physicalDirectory)
        {
            ++this.headerSize;
            this.headerSize += _pakDirectory.parent == null ? 0 : _physicalDirectory.Name.Length;
            ++this.headerSize;
            this.headerSize += 4;
            foreach (DirectoryInfo directory in _physicalDirectory.GetDirectories())
            {
                DirectoryData directoryData = new DirectoryData(_pakDirectory, directory.Name);
                _pakDirectory.AddEntry((EntryData)directoryData);
                this.CreatePAKDirectory(directoryData, directory);
            }
            Adler32 adler32 = new Adler32();
            foreach (FileInfo file in _physicalDirectory.GetFiles())
            {
                ++this.headerSize;
                this.headerSize += file.Name.Length;
                ++this.headerSize;
                this.headerSize += 12;
                Stream _stream = (Stream)file.OpenRead();
                FileData _entry = new FileData(_pakDirectory, file.Name, this.dataSize, (int)file.Length, adler32.Make(_stream));
                _pakDirectory.AddEntry((EntryData)_entry);
                this.dataSize += (int)file.Length;
                _stream.Close();
            }
        }

        private void CreateTree(
          BinaryReader _reader,
          DirectoryInfo _rootDir,
          DirectoryData _currentDir)
        {
            if (_currentDir.name != "")
                _rootDir.CreateSubdirectory(_currentDir.fullName);
            foreach (DirectoryData directory in _currentDir.directories)
                this.CreateTree(_reader, _rootDir, directory);
            foreach (FileData file in _currentDir.files)
            {
                FileStream fileStream = new FileStream(Path.Combine(_rootDir.FullName, file.fullName), FileMode.Create);
                _reader.BaseStream.Seek((long)file.position, SeekOrigin.Begin);
                fileStream.Write(_reader.ReadBytes(file.size), 0, file.size);
                fileStream.Close();
            }
        }

        private EntryData ReadPAKEntry(BinaryReader _reader, DirectoryData _parent)
        {
            string _name = new string(_reader.ReadChars((int)_reader.ReadByte()));
            EntryData entryData;
            if (((int)_reader.ReadByte() & 1) != 0)
            {
                DirectoryData _parent1 = new DirectoryData(_parent, _name);
                int num = _reader.ReadInt32();
                for (int index = 0; index < num; ++index)
                {
                    EntryData _entry = this.ReadPAKEntry(_reader, _parent1);
                    _parent1.AddEntry(_entry);
                    this.headerData.Add(_entry.fullName, _entry);
                }
                entryData = (EntryData)_parent1;
            }
            else
                entryData = (EntryData)new FileData(_parent, _name, this.headerSize + _reader.ReadInt32(), _reader.ReadInt32(), _reader.ReadInt32());
            return entryData;
        }

        private void WritePAKEntry(BinaryWriter _writer, EntryData _entry)
        {
            byte length = (byte)_entry.name.Length;
            _writer.Write(length);
            if (length > (byte)0)
                _writer.Write(_entry.name.ToCharArray());
            if (_entry.isDirectory)
            {
                DirectoryData directoryData = (DirectoryData)_entry;
                _writer.Write((byte)1);
                _writer.Write(directoryData.directories.Count + directoryData.files.Count);
                foreach (DirectoryData directory in directoryData.directories)
                    this.WritePAKEntry(_writer, (EntryData)directory);
                foreach (FileData file in directoryData.files)
                    this.WritePAKEntry(_writer, (EntryData)file);
            }
            else
            {
                FileData fileData = (FileData)_entry;
                _writer.Write((byte)0);
                _writer.Write(fileData.position);
                _writer.Write(fileData.size);
                _writer.Write(fileData.checksum);
            }
        }

        private void WritePAKContent(BinaryWriter _writer, DirectoryInfo _dir)
        {
            foreach (DirectoryInfo directory in _dir.GetDirectories())
                this.WritePAKContent(_writer, directory);
            foreach (FileInfo file in _dir.GetFiles())
            {
                BinaryReader binaryReader = new BinaryReader((Stream)file.OpenRead());
                _writer.Write(binaryReader.ReadBytes((int)file.Length));
                binaryReader.Close();
            }
        }

        private int headerSize { get; set; }

        private int dataSize { get; set; }
    }
}
