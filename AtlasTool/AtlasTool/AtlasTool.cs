using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using ModTools;
using Packer;

namespace AtlasTool;

internal class AtlasTool
{
	private static byte[] buffer = new byte[67108864];
	private int c = 0;
	private Dictionary<string, Tile> hashes = new Dictionary<string, Tile>();

	/* The fix of binary collapse method is based on this method. */
	public void Expand(string _atlasPath, string _outDirPath)
	{
		DirectoryInfo directoryInfo = new DirectoryInfo(_outDirPath);
		if (directoryInfo.Exists)
		{
			directoryInfo.Delete(recursive: true);
		}
		directoryInfo.Create();

		FileInfo fileInfo = new FileInfo(_atlasPath);
		fileInfo.Name.Substring(0, fileInfo.Name.Length - 6);
		Stream stream = File.OpenRead(_atlasPath);
		BinaryReader binaryReader = new BinaryReader(stream);

		// read the first four char: BATL
		string BATL =  new string(binaryReader.ReadChars(4));
		//进入第一层循环。
        	while (binaryReader.BaseStream.Position + 18 < stream.Length)
		{
			List<Tile> list = new List<Tile>(); // Tile class contains all position information of each frame animation textures.
			string text = ReadString(binaryReader); // Read the packaged big texture name, like beheaded0.png，beheaded1.png
            		if (text == "")
				break;
			//进入第二层循环
			while (binaryReader.BaseStream.Position + 18 < stream.Length)
			{
				Tile tile = new Tile();
				tile.name = ReadString(binaryReader);// Read current animation frame name, like: atkA_00， atkA_01。
                		if (tile.name == "")
					break;
		                tile.index = binaryReader.ReadUInt16(); // always 0
		                tile.x = binaryReader.ReadUInt16(); // Horizontal position of the top-left pixel of the current frame in the big texture.
		                tile.y = binaryReader.ReadUInt16(); // Vertical position of the top-left pixel of the current frame in the big texture.
		                tile.width = binaryReader.ReadUInt16(); // Width of current frame.
		                tile.height = binaryReader.ReadUInt16(); // Height of current frame.
				// When finishing the Expand action, you can see each frame are splited into single small textures.
		                tile.offsetX = binaryReader.ReadUInt16(); // Horizontal position of the top-left pixel of the current frame in the small texture.
		                tile.offsetY = binaryReader.ReadUInt16(); // Vertical position of the top-left pixel of the current frame in the small texture.
		                tile.originalWidth = binaryReader.ReadUInt16(); // Width of the small texture.
		                tile.originalHeight = binaryReader.ReadUInt16(); // Height of the small texture.
				// The ReadUInt16() method was used for 9 time, each time it read 2 bytes, so the while condition requires + 18.
		                list.Add(tile);
			}
			CreateBitmapTree(list, directoryInfo, fileInfo, text);

			try // Check and expand the normal map.
			{
				CreateBitmapTree(list, directoryInfo, fileInfo, text.Substring(0, text.Length - 4) + "_n.png", "_n");
			}
			catch (Exception)
			{}
		}
		binaryReader.Close();
	}

	public void CreateBitmapTree(List<Tile> _tiles, DirectoryInfo _outDir, FileInfo _atlasInfo, string _atlasName, string _suffix = "")
	{
		Bitmap bitmap = (Bitmap)Image.FromFile(Path.Combine(_atlasInfo.DirectoryName, _atlasName));
		Directory.CreateDirectory(_outDir.FullName);
		foreach (Tile _tile in _tiles)
			CopyBitmapFromAtlas(_tile, _outDir.FullName, bitmap, _suffix);
		
		bitmap.Dispose();
	}

	public void Collapse(string _inputDirPath, string _atlasPath, bool _exportBinaryAtlases)
	{
		DirectoryInfo directoryInfo = new DirectoryInfo(_inputDirPath);
		new DirectoryInfo(new FileInfo(_atlasPath).DirectoryName).Create();
		if (!directoryInfo.Exists)
		{
			throw new DirectoryNotFoundException("Directory not found : " + _inputDirPath);
		}
		List<Tile> list = new List<Tile>();
		new HashSet<Bitmap>();
		foreach (FileInfo item in from file in directoryInfo.GetFiles("*.png", SearchOption.AllDirectories)
			where !file.Name.EndsWith("_n.png")
			select file)
		{
			try
			{
				Bitmap bitmap = (Bitmap)Image.FromFile(item.FullName);
				Tile _tile = new Tile();
				_tile.width = (_tile.originalWidth = bitmap.Width);
				_tile.height = (_tile.originalHeight = bitmap.Height);
				_tile.bitmap = bitmap;
				_tile.hasNormal = File.Exists(Path.Combine(item.DirectoryName, item.Name.Substring(0, item.Name.Length - 4) + "_n.png"));
				_tile.name = item.FullName.Replace(directoryInfo.FullName, "").Substring(1);
				_tile.name = _tile.name.Substring(0, _tile.name.Length - 4).Replace("\\", "/");
				int num = _tile.name.IndexOf("-=-");
				if (num != -1)
				{
					int num2 = _tile.name.IndexOf("-=-", num + 3);
					if (num2 != -1)
					{
						string text = _tile.name.Substring(num + 3);
						text = text.Substring(0, text.IndexOf("-=-"));
						int.TryParse(text, out _tile.index);
						_tile.name = _tile.name.Substring(0, num) + _tile.name.Substring(num2 + 3);
					}
				}
				_tile.originalFilePath = item.FullName;
				TrimTile(ref _tile);
				ExtrudeTile(ref _tile);
				if (_tile.height != 0)
				{
					list.Add(_tile);
					if (_tile.width == 0)
						throw new Exception("?? width should not be at 0, when height != 0");
				}
			}
			catch (Exception ex)
			{
				Log.Error("Error collapsing " + item.Name);
				throw ex;
			}
		}
		list.Sort(delegate(Tile a, Tile b)
		{
			if (a.width > b.width)
				return -1;
			if (a.width == b.width)
			{
				if (a.height > b.height)
					return -1;
				if (a.height == b.height)
					return 0;
				return 1;
			}
			return 1;
		});
		Bin2DPacker bin2DPacker = new Bin2DPacker(new Size(32, 32), new Size(4096, 4096), Bin2DPacker.Algorithm.MaxRects);
		bin2DPacker.margin = new Size(1, 1);
		bin2DPacker.marginType = MarginType.All;
		for (int i = 0; i < list.Count; i++)
		{
			if (list[i].bitmap != null)
			{
				bin2DPacker.InsertElement((uint)i, new Size(list[i].width, list[i].height), out var _);
			}
		}
		int count = bin2DPacker.bins.Count;
		BinaryWriter binaryWriter = null;
		StreamWriter streamWriter = null;
		if (_exportBinaryAtlases)
		{
			/* We only need this title once, so this should be written at first */
			binaryWriter = new BinaryWriter(File.OpenWrite(_atlasPath.Substring(0, _atlasPath.Length - 4) + ".atlas"));
			string text3 = "BATL";
            		binaryWriter.Write(text3.ToCharArray());
        	}
		else
		{
			streamWriter = new StreamWriter(_atlasPath.Substring(0, _atlasPath.Length - 4) + ".atlas");
		}
		for (int j = 0; j < count; j++)
		{
			Bin2D bin2D = bin2DPacker.bins[j];
			Bitmap bitmap2 = new Bitmap(bin2D.size.Width, bin2D.size.Height);
			Bitmap bitmap3 = new Bitmap(bin2D.size.Width, bin2D.size.Height);
			bool flag = false;
			foreach (KeyValuePair<uint, Rectangle> element in bin2D.elements)
			{
				Tile _tile2 = list[(int)element.Key];
				_tile2.x = element.Value.X;
				_tile2.y = element.Value.Y;
				_tile2.atlasIndex = j;
				CopyBitmapToAtlas(_tile2, bitmap2);
				if (_tile2.hasNormal)
				{
					_tile2.bitmap = (Bitmap)Image.FromFile(_tile2.originalFilePath.Substring(0, _tile2.originalFilePath.Length - 4) + "_n.png");
					ExtrudeTile(ref _tile2, _bForceBitmapResizeAndPreventUpdateTileInfo: true);
					CopyBitmapToAtlas(_tile2, bitmap3);
					flag = true;
				}
			}
			string text2 = new FileInfo(_atlasPath).FullName;
			if (count > 1)
			{
				text2 = text2.Substring(0, text2.Length - 4) + j + ".png";
			}
			bitmap2.Save(text2);
			if (flag)
			{
				bitmap3.Save(text2.Substring(0, text2.Length - 4) + "_n.png");
				bitmap3.Dispose();
				bitmap3 = null;
			}
			if (_exportBinaryAtlases)
			{
				/* We only need this title once, so this should be written earlier. */
				/*
				string text3 = "BATL";
				binaryWriter.Write(text3.ToCharArray());
				*/
				WriteString(binaryWriter, text2.Substring(text2.LastIndexOf('\\') + 1));
				foreach (Tile item2 in list)
				{
					if (item2.duplicateOf != null)
					{
						item2.x = item2.duplicateOf.x;
						item2.y = item2.duplicateOf.y;
						item2.atlasIndex = item2.duplicateOf.atlasIndex;
					}
					if (item2.atlasIndex == j)
					{
			                        WriteString(binaryWriter, item2.name);
						binaryWriter.Write((ushort)item2.index);
						/* Delete the + 1 , which causes animation offset error and package error.*/
						binaryWriter.Write((ushort)(item2.x));
			                        binaryWriter.Write((ushort)(item2.y));
						
			                        binaryWriter.Write((ushort)item2.width);
			                        binaryWriter.Write((ushort)item2.height);
			                        binaryWriter.Write((ushort)item2.offsetX);
			                        binaryWriter.Write((ushort)item2.offsetY);
			                        binaryWriter.Write((ushort)item2.originalWidth);
			                        binaryWriter.Write((ushort)item2.originalHeight);
                    			}
                		}
				binaryWriter.Write((byte)0);
			}
			else
			{
				streamWriter.WriteLine("");
				streamWriter.WriteLine(text2.Substring(text2.LastIndexOf('\\') + 1));
				streamWriter.WriteLine("size: {0},{1}", bitmap2.Width, bitmap2.Height);
				streamWriter.WriteLine("format: RGBA8888");
				streamWriter.WriteLine("filter: Linear,Linear");
				streamWriter.WriteLine("repeat: none");
				foreach (Tile item3 in list)
				{
					if (item3.duplicateOf != null)
					{
						item3.x = item3.duplicateOf.x;
						item3.y = item3.duplicateOf.y;
						item3.atlasIndex = item3.duplicateOf.atlasIndex;
					}
					if (item3.atlasIndex == j)
					{
						streamWriter.WriteLine(item3.name);
						streamWriter.WriteLine("  rotate: false");
						streamWriter.WriteLine("  xy: {0}, {1}", item3.x + 1, item3.y + 1);
						streamWriter.WriteLine("  size: {0}, {1}", item3.width - 2, item3.height - 2);
						streamWriter.WriteLine("  orig: {0}, {1}", item3.originalWidth - 2, item3.originalHeight - 2);
						streamWriter.WriteLine("  offset: {0}, {1}", item3.offsetX, item3.originalHeight - 2 - (item3.height - 2 + item3.offsetY));
						streamWriter.WriteLine("  index: {0}", item3.index);
					}
				}
			}
			bitmap2.Dispose();
			bitmap2 = null;
		}
		if (_exportBinaryAtlases)
		{
			binaryWriter.Write((byte)0);
			binaryWriter.Close();
		}
		else
		{
			streamWriter.Close();
		}
	}

	private void CopyBitmapFromAtlas(Tile _tile, string _path, Bitmap _atlas, string _suffix)
	{
		string[] array = _tile.name.Split('/');
		string path = _path;
		for (int i = 0; i < array.Length - 1; i++)
		{
			path = Directory.CreateDirectory(Path.Combine(path, array[i])).FullName;
		}
		string text = array[array.Length - 1];
		if (_tile.index != -1)
			text = text + "-=-" + _tile.index + "-=-";
		BitmapData bitmapData = _atlas.LockBits(new Rectangle(_tile.x, _tile.y, _tile.width, _tile.height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
		Bitmap bitmap = new Bitmap(_tile.originalWidth, _tile.originalHeight);
		BitmapData bitmapData2 = bitmap.LockBits(new Rectangle(_tile.offsetX, _tile.offsetY, _tile.width, _tile.height), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
		for (int j = 0; j < _tile.height; j++)
		{
			Core.CopyMemory(bitmapData2.Scan0 + j * bitmapData2.Stride, bitmapData.Scan0 + j * bitmapData.Stride, (uint)(_tile.width * 4));
		}
		bitmap.UnlockBits(bitmapData2);
		_atlas.UnlockBits(bitmapData);
		string filename = Path.Combine(path, text + _suffix + ".png");
		bitmap.Save(filename);
		bitmap.Dispose();
	}

	private void TrimTile(ref Tile _tile)
	{
		BitmapData bitmapData = _tile.bitmap.LockBits(new Rectangle(0, 0, _tile.width, _tile.height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
		
		string key;
		lock (buffer)
		{
			Marshal.Copy(bitmapData.Scan0, buffer, 0, _tile.originalWidth * _tile.originalHeight * 4);
			key = Convert.ToBase64String(SHA256.Create().ComputeHash(buffer, 0, _tile.originalWidth * _tile.originalHeight * 4));
		}
		if (!hashes.TryGetValue(key, out var value))
		{
			hashes.Add(key, _tile);
			bool flag = false;
			for (int i = 0; i < _tile.originalHeight; i++)
			{
				if (flag)
					break;
				if (_tile.height <= 1)
					break;
				for (int j = 0; j < _tile.originalWidth; j++)
				{
					if (flag)
						break;
					if (_tile.height <= 1)
						break;
					flag = (Marshal.ReadInt32(bitmapData.Scan0 + (i * _tile.originalWidth + j) * 4) & 0xFF000000u) != 0;
				}
				if (!flag)
				{
					_tile.offsetY++;
					_tile.height--;
				}
			}
			flag = false;
			for (int k = 0; k < _tile.originalWidth; k++)
			{
				if (flag)
					break;
				if (_tile.width <= 1)
					break;
				for (int l = _tile.offsetY; l < _tile.originalHeight; l++)
				{
					if (flag)
						break;
					if (_tile.width <= 1)
						break;
					flag = (Marshal.ReadInt32(bitmapData.Scan0 + (l * _tile.originalWidth + k) * 4) & 0xFF000000u) != 0;
				}
				if (!flag)
				{
					_tile.offsetX++;
					_tile.width--;
				}
			}
			flag = false;
			int num = _tile.originalHeight - 1;
			while (num >= _tile.offsetY && !flag && _tile.height > 1)
			{
				for (int m = _tile.offsetX; m < _tile.originalWidth; m++)
				{
					if (flag)
						break;
					if (_tile.height <= 1)
						break;
					flag = (Marshal.ReadInt32(bitmapData.Scan0 + (num * _tile.originalWidth + m) * 4) & 0xFF000000u) != 0;
				}
				if (!flag)
				{
					_tile.height--;
				}
				num--;
			}
			flag = false;
			int num2 = _tile.originalWidth - 1;
			while (num2 >= _tile.offsetX && !flag && _tile.width > 1)
			{
				for (int n = _tile.offsetY; n < _tile.originalHeight; n++)
				{
					if (flag)
						break;
					if (_tile.width <= 1)
						break;
					flag = (Marshal.ReadInt32(bitmapData.Scan0 + (n * _tile.originalWidth + num2) * 4) & 0xFF000000u) != 0;
				}
				if (!flag)
				{
					_tile.width--;
				}
				num2--;
			}
			_tile.bitmap.UnlockBits(bitmapData);

		}
		else
		{
			_tile.duplicateOf = value;
			_tile.x = value.x;
			_tile.y = value.y;
			_tile.offsetX = value.offsetX;
			_tile.offsetY = value.offsetY;
			_tile.originalWidth = value.originalWidth;
			_tile.originalHeight = value.originalHeight;
			_tile.width = value.width;
			_tile.height = value.height;
			_tile.bitmap = null;
		}
	}

	private void ExtrudeTile(ref Tile _tile, bool _bForceBitmapResizeAndPreventUpdateTileInfo = false)
	{
		if (_tile.bitmap == null)
		{
			return;
		}
		string text = "none";
		try
		{
			if (_bForceBitmapResizeAndPreventUpdateTileInfo || _tile.offsetX == 0 || _tile.offsetY == 0 || _tile.originalWidth - _tile.width < _tile.offsetX + 2 || _tile.originalHeight - _tile.height < _tile.offsetY + 2)
			{
				int width = _tile.bitmap.Width;
				int height = _tile.bitmap.Height;
				Bitmap bitmap = new Bitmap(width + 2, height + 2);
				text = "reading old";
				BitmapData bitmapData = _tile.bitmap.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
				text = "reading new";

				// BitmapData bitmapData2 = bitmap.LockBits(new Rectangle(1, 1, width, height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
				// BitmapData bitmapData2 = bitmap.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
				/* for normal map, (1, 1) offset is unnecessary*/
				int normalOffset = _bForceBitmapResizeAndPreventUpdateTileInfo ? 0 : 1;
				BitmapData bitmapData2 = bitmap.LockBits(new Rectangle(normalOffset, normalOffset, width, height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
				
				
				for (int i = 0; i < height; i++)
				{
					Core.CopyMemory(bitmapData2.Scan0 + i * bitmapData2.Stride, bitmapData.Scan0 + i * bitmapData.Stride, (uint)(width * 4));
				}
				_tile.bitmap.UnlockBits(bitmapData);
				bitmap.UnlockBits(bitmapData2);
				_tile.bitmap.Dispose();
				_tile.bitmap = bitmap;
				if (!_bForceBitmapResizeAndPreventUpdateTileInfo)
				{
					_tile.offsetX++;
					_tile.offsetY++;
					_tile.originalHeight += 2;
					_tile.originalWidth += 2;
				}
			}
			if (!_bForceBitmapResizeAndPreventUpdateTileInfo)
			{
				_tile.offsetX--;
				_tile.offsetY--;
				_tile.width += 2;
				_tile.height += 2;
			}
			/* not necessary at all, since the original textures didn't have repeats for the sprites’ pixels at the borders.*/
   			/*	
			text = "writing";
			_ = $"_tile.offsetX = {_tile.offsetX}, _tile.offsetY = {_tile.offsetY}, _tile.width = {_tile.width}, _tile.height = {_tile.height}";
			BitmapData bitmapData3 = _tile.bitmap.LockBits(new Rectangle(_tile.offsetX, _tile.offsetY, _tile.width, _tile.height), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
			for (int j = 0; j < _tile.height; j++)
			{
				Marshal.WriteInt32(bitmapData3.Scan0 + j * bitmapData3.Stride, Marshal.ReadInt32(bitmapData3.Scan0 + j * bitmapData3.Stride + 4));
				Marshal.WriteInt32(bitmapData3.Scan0 + j * bitmapData3.Stride + (_tile.width - 1) * 4, Marshal.ReadInt32(bitmapData3.Scan0 + j * bitmapData3.Stride + (_tile.width - 2) * 4));
			}
			int num = (_tile.height - 1) * bitmapData3.Stride;
			for (int k = 0; k < _tile.width; k++)
			{
				Marshal.WriteInt32(bitmapData3.Scan0 + k * 4, Marshal.ReadInt32(bitmapData3.Scan0 + bitmapData3.Stride + k * 4));
				int val = Marshal.ReadInt32(bitmapData3.Scan0 + num - bitmapData3.Stride + k * 4);
				Marshal.WriteInt32(bitmapData3.Scan0 + num + k * 4, val);
			}
			_tile.bitmap.UnlockBits(bitmapData3);
			*/
		}
		catch (Exception ex)
		{
			Log.Error("Problem " + text + " " + _tile.name + " when extruding");
			throw ex;
		}
	}

	private void CopyBitmapToAtlas(Tile _tile, Bitmap _atlas)/*didn't change any code, just add a try catch*/
	{
		if (_tile.bitmap != null)
		{
			try
			{
				BitmapData bitmapData = _atlas.LockBits(
				    new Rectangle(_tile.x, _tile.y, _tile.width, _tile.height),
				    ImageLockMode.WriteOnly,
				    PixelFormat.Format32bppArgb
				);
				
				BitmapData bitmapData2 = _tile.bitmap.LockBits(
				    new Rectangle(_tile.offsetX, _tile.offsetY, _tile.width, _tile.height),
				    ImageLockMode.ReadOnly,
				    PixelFormat.Format32bppArgb
				);
				
				for (int i = 0; i < _tile.height; i++)
				{
					Core.CopyMemory(
					bitmapData.Scan0 + i * bitmapData.Stride,
					bitmapData2.Scan0 + i * bitmapData2.Stride,
					(uint)(_tile.width * 4)
					);
				}
				_atlas.UnlockBits(bitmapData);
				_tile.bitmap.UnlockBits(bitmapData2);
			}
			catch (Exception ex)
			{
				Console.WriteLine("Error when copy bitmaps: " + ex.Message);
			}
		}
	}

	/*how the binary .atlas file read the string in it*/
	private string ReadString(BinaryReader _reader)
	{
		int num = _reader.ReadByte();
		if (num == 255)
		{
			num = _reader.ReadUInt16();
		}
		if (num != 0)
		{
			return new string(_reader.ReadChars(num));
		}
		return "";
	}

	private void WriteString(BinaryWriter _writer, string _stringToWrite)
	{
	if (_stringToWrite.Length >= 255)
		_writer.Write((ushort)_stringToWrite.Length);
	else
		_writer.Write((byte)_stringToWrite.Length);
		_writer.Write(_stringToWrite.ToCharArray());
	}
}
