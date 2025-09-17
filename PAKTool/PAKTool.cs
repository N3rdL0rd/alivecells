// Decompiled with JetBrains decompiler
// Type: PAKTool.PAKTool
// Assembly: PAKTool, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: ECC9A4AB-62C6-4F7C-95CE-FBC3CF0F40A2
// Assembly location: D:\SteamLibrary\steamapps\common\Dead Cells\ModTools\PAKTool.exe

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

#nullable disable
namespace PAKTool
{
    internal class PAKTool
    {
        private Dictionary<string, EntryData> headerData = new Dictionary<string, EntryData>();
        private char[] stamp;

        public byte version { get; private set; }
        public DirectoryData root { get; private set; }
        private int headerSize { get; set; }
        private int dataSize { get; set; }

        public void ExpandPAK(string _pakPath, string _destination)
        {
            Console.WriteLine($"Starting to expand PAK: {_pakPath} to {_destination}");
            if (!File.Exists(_pakPath))
            {
                Console.WriteLine($"Error: File not found: {_pakPath}");
                throw new FileNotFoundException("File not found: " + _pakPath, _pakPath);
            }
            DirectoryInfo directory = Directory.CreateDirectory(_destination);
            Console.WriteLine($"Created directory: {_destination}");
            BinaryReader _reader = this.ReadPAKHeader(_pakPath);
            Console.WriteLine("PAK header read successfully");
            this.CreateTree(_reader, directory, this.root);
            Console.WriteLine("File tree created successfully");
            _reader.Close();
            Console.WriteLine("PAK expansion completed");
        }

        public void BuildPAK(string _expandedPakPath, string _destination)
        {
            Console.WriteLine($"Starting to build PAK from {_expandedPakPath} to {_destination}");
            DirectoryInfo directoryInfo = new DirectoryInfo(_expandedPakPath);
            if (!directoryInfo.Exists)
            {
                Console.WriteLine($"Error: Directory not found: {_expandedPakPath}");
                throw new DirectoryNotFoundException("Directory " + _expandedPakPath + " not found");
            }
            FileInfo fileInfo = new FileInfo(_destination);
            fileInfo.Directory.Create();
            Console.WriteLine($"Created directory for destination: {fileInfo.Directory.FullName}");

            this.root = new DirectoryData((DirectoryData)null, "");
            this.dataSize = 0;
            this.headerSize = 0;
            this.version = (byte)0;
            this.CreatePAKDirectory(this.root, directoryInfo);
            Console.WriteLine("PAK directory structure created");

            this.headerSize += 16;
            using (BinaryWriter _writer = new BinaryWriter((Stream)fileInfo.Create()))
            {
                Console.WriteLine("Writing PAK header");
                _writer.Write(new char[3] { 'P', 'A', 'K' });
                _writer.Write(this.version);
                _writer.Write(this.headerSize);
                _writer.Write(this.dataSize);
                this.WritePAKEntry(_writer, (EntryData)this.root);
                _writer.Write(new char[4] { 'D', 'A', 'T', 'A' });
                Console.WriteLine("Writing PAK content");
                this.WritePAKContent(_writer, directoryInfo);
            }
            Console.WriteLine("PAK building completed");
        }

        public void BuildPAKStamped(string _expandedPakPath, string _destination, string stamp)
        {
            Console.WriteLine($"Starting to build stamped PAK from {_expandedPakPath} to {_destination}");
            if (stamp.Length != 64)
            {
                Console.WriteLine("Error: Stamp should be 64 bytes long.");
                throw new FormatException("Stamp should be 64 bytes long.");
            }

            DirectoryInfo directoryInfo = new DirectoryInfo(_expandedPakPath);
            if (!directoryInfo.Exists)
            {
                Console.WriteLine($"Error: Directory not found: {_expandedPakPath}");
                throw new DirectoryNotFoundException("Directory " + _expandedPakPath + " not found");
            }

            FileInfo fileInfo = new FileInfo(_destination);
            fileInfo.Directory.Create();
            Console.WriteLine($"Created directory for destination: {fileInfo.Directory.FullName}");

            this.root = new DirectoryData((DirectoryData)null, "");
            this.dataSize = 0;
            this.headerSize = 0;
            this.version = (byte)1;
            this.CreatePAKDirectory(this.root, directoryInfo);
            Console.WriteLine("PAK directory structure created");

            this.headerSize += 16 + 64; // extra 64 for the stamp

            using (BinaryWriter _writer = new BinaryWriter(fileInfo.Create()))
            {
                Console.WriteLine("Writing PAK header with stamp");
                _writer.Write(new char[3] { 'P', 'A', 'K' });
                _writer.Write(this.version);
                _writer.Write(this.headerSize);
                _writer.Write(this.dataSize);

                byte[] stampBytes = System.Text.Encoding.ASCII.GetBytes(stamp);
                _writer.Write(stampBytes);
                Console.WriteLine("Stamp written to PAK header");

                this.WritePAKEntry(_writer, (EntryData)this.root);
                _writer.Write(new char[4] { 'D', 'A', 'T', 'A' });
                Console.WriteLine("Writing PAK content");
                this.WritePAKContent(_writer, directoryInfo);
            }
            Console.WriteLine("Stamped PAK building completed");
        }

        public void BuildDiffPAK(string _referencePAK, string _inputDir, string _diffPAKPath)
        {
            Console.WriteLine($"Starting to build diff PAK. Reference: {_referencePAK}, Input: {_inputDir}, Output: {_diffPAKPath}");
            DirectoryInfo directoryInfo1 = new DirectoryInfo(_inputDir);
            if (!directoryInfo1.Exists)
            {
                Console.WriteLine($"Error: Directory not found: {_inputDir}");
                throw new DirectoryNotFoundException("Directory " + _inputDir + " not found.");
            }
            BinaryReader binaryReader = this.ReadPAKHeader(_referencePAK);
            Console.WriteLine("Reference PAK header read successfully");

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
            Console.WriteLine("Reference PAK file checksums collected");

            Dictionary<string, int> dictionary2 = new Dictionary<string, int>();
            Adler32 adler32 = new Adler32();
            if (_inputDir.Length > 0 && _inputDir[_inputDir.Length - 1] != '\\')
                _inputDir += "\\";
            foreach (FileInfo file in directoryInfo1.GetFiles("*.*", SearchOption.AllDirectories))
                dictionary2.Add(file.FullName.Replace(_inputDir, ""), adler32.Make((Stream)File.OpenRead(file.FullName)));
            Console.WriteLine("Input directory file checksums collected");

            List<string> stringList = new List<string>();
            DirectoryInfo directoryInfo2 = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
            directoryInfo2.Create();
            Console.WriteLine($"Temporary directory created: {directoryInfo2.FullName}");

            bool flag = false;
            foreach (KeyValuePair<string, int> keyValuePair in dictionary2)
            {
                if (dictionary1.TryGetValue(keyValuePair.Key, out int num))
                {
                    if (num != keyValuePair.Value)
                    {
                        if (keyValuePair.Key.Substring(keyValuePair.Key.Length - 4, 4).ToUpper() == ".CDB")
                        {
                            Console.WriteLine($"Processing CDB file: {keyValuePair.Key}");
                            CDBTool.CDBTool cdbTool = new CDBTool.CDBTool();
                            DirectoryInfo directoryInfo3 = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
                            directoryInfo3.Create();
                            string str = Path.Combine(directoryInfo3.FullName, keyValuePair.Key);
                            if (!this.headerData.TryGetValue(keyValuePair.Key, out EntryData entryData))
                            {
                                Console.WriteLine($"Error: Original CDB key not found: {keyValuePair.Key}");
                                throw new Exception("Original CDB key called " + keyValuePair.Key + " not found.");
                            }
                            FileData fileData = (FileData)entryData;
                            using (FileStream fileStream = new FileStream(str, FileMode.OpenOrCreate))
                            {
                                binaryReader.BaseStream.Seek((long)fileData.position, SeekOrigin.Begin);
                                fileStream.Write(binaryReader.ReadBytes(fileData.size), 0, fileData.size);
                            }
                            DirectoryInfo directoryInfo4 = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
                            cdbTool.Expand(Path.Combine(_inputDir, keyValuePair.Key), directoryInfo4.FullName);
                            DirectoryInfo directoryInfo5 = new DirectoryInfo(Path.Combine(directoryInfo2.FullName, keyValuePair.Key + "_"));
                            directoryInfo5.Create();
                            cdbTool.BuildDiffCDB(str, directoryInfo4.FullName, directoryInfo5.FullName);
                            Console.WriteLine($"Diff CDB built for: {keyValuePair.Key}");
                            flag = true;
                        }
                        else
                        {
                            stringList.Add(Path.Combine(directoryInfo2.FullName, keyValuePair.Key));
                            Console.WriteLine($"File changed: {keyValuePair.Key}");
                        }
                    }
                }
                else
                {
                    stringList.Add(Path.Combine(directoryInfo2.FullName, keyValuePair.Key));
                    Console.WriteLine($"New file added: {keyValuePair.Key}");
                }
            }
            binaryReader.Close();

            if (stringList.Count == 0 && !flag)
            {
                Console.WriteLine("Error: No changed or added files found.");
                throw new Exception("No diff pak created, no changed or added files found.");
            }

            foreach (string fileName in stringList)
            {
                FileInfo fileInfo = new FileInfo(fileName);
                fileInfo.Directory.Create();
                File.Copy(Path.Combine(_inputDir, fileName.Replace(directoryInfo2.FullName, "").Substring(1)), fileInfo.FullName);
                Console.WriteLine($"Copied file to temp directory: {fileInfo.FullName}");
            }

            this.BuildPAK(directoryInfo2.FullName, _diffPAKPath);
            Console.WriteLine($"Diff PAK built: {_diffPAKPath}");
            directoryInfo2.Delete(true);
            Console.WriteLine("Temporary directory deleted");
        }

        private BinaryReader ReadPAKHeader(string _pakPath)
        {
            Console.WriteLine($"Reading PAK header from: {_pakPath}");
            this.headerData.Clear();
            BinaryReader _reader = new BinaryReader((Stream)File.OpenRead(_pakPath));
            string str = new string(_reader.ReadChars(3));
            this.version = _reader.ReadByte();
            this.headerSize = _reader.ReadInt32();
            this.dataSize = _reader.ReadInt32();
            Console.WriteLine($"PAK version: {this.version}, Header size: {this.headerSize}, Data size: {this.dataSize}");

            if (this.version >= (byte)1)
            {
                Console.WriteLine("Reading stamp for version 1+");
                this.stamp = _reader.ReadChars(76);
                _reader.BaseStream.Seek(-12, SeekOrigin.Current);
            }

            this.root = (DirectoryData)this.ReadPAKEntry(_reader, (DirectoryData)null);
            Console.WriteLine("Root entry read successfully");

            if (this.version >= (byte)1)
            {
                Console.WriteLine("Processing stamp file for version 1+");
                string fileName = "STAMP_AUTOGENERATED_DO_NOT_DELETE.txt";

                char[] last64Chars = new char[64];
                Array.Copy(this.stamp, 12, last64Chars, 0, 64);

                string last64String = new string(last64Chars);
                byte[] fileContentBytes = Encoding.UTF8.GetBytes(last64String);

                int fileSize = fileContentBytes.Length;
                Adler32 adler32 = new Adler32();
                int checksum = adler32.Make(new MemoryStream(fileContentBytes));
                FileData fileData = new FileData(this.root, fileName, 0, fileSize, checksum);

                File.WriteAllBytes(fileName, fileContentBytes);
                Console.WriteLine($"Stamp file created: {fileName}");

                this.root.AddEntry(fileData);
                Console.WriteLine("Stamp file added to root entry");
            }

            return _reader;
        }

        private void CreatePAKDirectory(DirectoryData _pakDirectory, DirectoryInfo _physicalDirectory)
        {
            Console.WriteLine($"Creating PAK directory for: {_physicalDirectory.FullName}");
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
                using (Stream _stream = (Stream)file.OpenRead())
                {
                    FileData _entry = new FileData(_pakDirectory, file.Name, this.dataSize, (int)file.Length, adler32.Make(_stream));
                    _pakDirectory.AddEntry((EntryData)_entry);
                    this.dataSize += (int)file.Length;
                }
                Console.WriteLine($"Added file to PAK: {file.Name}");
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

            byte flags = _reader.ReadByte();
            // flags & 1 = isDirectory
            // flags & 2 = isLargeOffset
            bool isDirectory = (flags & 1) != 0;

            if (isDirectory)
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
            {
                long relativePosition;
                bool isLargeOffset = (flags & 2) != 0;

                if (isLargeOffset)
                {
                    relativePosition = (long)_reader.ReadDouble();
                }
                else
                {
                    relativePosition = _reader.ReadInt32();
                }

                int fileSize = _reader.ReadInt32();
                int checksum = _reader.ReadInt32();

                long absolutePosition = this.headerSize + relativePosition;

                entryData = (EntryData)new FileData(_parent, _name, absolutePosition, fileSize, checksum);
            }
            return entryData;
        }

        private void WritePAKEntry(BinaryWriter _writer, EntryData _entry)
        {
            byte length = (byte)_entry.name.Length;
            _writer.Write(length);
            if (length > 0)
                _writer.Write(_entry.name.ToCharArray());

            if (_entry.isDirectory)
            {
                DirectoryData directoryData = (DirectoryData)_entry;
                _writer.Write((byte)1); // &1 = isDirectory
                _writer.Write(directoryData.directories.Count + directoryData.files.Count);
                foreach (DirectoryData directory in directoryData.directories)
                    this.WritePAKEntry(_writer, (EntryData)directory);
                foreach (FileData file in directoryData.files)
                    this.WritePAKEntry(_writer, (EntryData)file);
            }
            else
            {
                FileData fileData = (FileData)_entry;
                byte flags = 0;
                long relativePosition = fileData.position - this.headerSize;

                bool useLargeOffset = relativePosition > Int32.MaxValue;
                if (useLargeOffset)
                {
                    flags |= 2;
                }

                _writer.Write(flags);

                if (useLargeOffset)
                {
                    _writer.Write((double)relativePosition);
                }
                else
                {
                    _writer.Write((int)relativePosition);
                }

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
    }
}
