using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using ModTools;

namespace AtlasTool;

internal class Program
{
	private static void Main(string[] args)
	{
		Thread.CurrentThread.CurrentUICulture = CultureInfo.InvariantCulture;
		string atlasPath = "";
		string inDir = "";
		string outDir = "";
		string text = "";
		bool bShowMessage = true;
		bool bBinary = true;
		for (int i = 0; i < args.Length; i++)
		{
			string text2 = args[i];
			// Console.WriteLine(text2);
			if (text2[0] == '-' || text2[0] == '/')
			{
				text2 = text2.Substring(1).ToUpper();
				switch (text2)
				{
				case "INDIR":
					text2 = args[++i];
					// Console.WriteLine(text2);
					inDir = text2;
					break;
				case "OUTDIR":
					text2 = args[++i];
					// Console.WriteLine(text2);
					outDir = text2;
                        break;
				case "ATLAS":
				case "A":
					text2 = args[++i];
					// Console.WriteLine(text2);
					atlasPath = text2;
                        break;
				case "SILENT":
				case "S":
					bShowMessage = false;
					break;
				case "ASCII":
					bBinary = false;
					break;
				case "?":
					Console.WriteLine("-? : Display this help");
					Console.WriteLine("-Expand -outdir <output directory> -Atlas <input atlas path> [-s]: Expands a given Atlas to a file tree");
					Console.WriteLine("-ExpandAll -indir <input atlases directory> -outdir <output directory> [-s]: Expands every atlas found in indir into outdir");
					Console.WriteLine("-Collapse -indir <input directory> -Atlas <output atlas path> [-s][-ascii]: Collapse a given file tree to an atlas");
					Console.WriteLine("-CollapseAll -indir <input directories> -outdir <output atlases path> [-s][-ascii]: Collapse every directory in the input directory into atlases");
					Console.WriteLine("arguments :");
					Console.WriteLine("-s/-silent : Do not display message error (deactivated by default)");
					Console.WriteLine("-ascii : Export atlases as ascii (binary by default)");
					return;
				default:
					text = text2.ToUpper();
					break;
				}
			}
		}
		try
		{
			AtlasTool atlasTool = new AtlasTool();
			Console.WriteLine("Launching AtlasTool v" + Versionning.currentVersion + ", action: " + text);
			switch (text)
			{
			case "EXPAND":
				atlasTool.Expand(atlasPath, outDir);
				break;
			case "COLLAPSE":
				atlasTool.Collapse(inDir, atlasPath, bBinary);
				break;
			case "EXPANDALL":
			{
				DirectoryInfo directoryInfo2 = new DirectoryInfo(inDir);
				List<Task> list2 = new List<Task>();
				FileInfo[] files = directoryInfo2.GetFiles("*.atlas");
				foreach (FileInfo atlas in files)
				{
					Task item2 = Task.Factory.StartNew(delegate
					{
						AtlasTool atlasTool2 = new AtlasTool();
						string path = atlas.Name.Substring(0, atlas.Name.Length - 6);
						atlasTool2.Expand(atlas.FullName, Path.Combine(outDir, path));
					});
					list2.Add(item2);
				}
				Task.WaitAll(list2.ToArray());
				break;
			}
			case "COLLAPSEALL":
			{
				DirectoryInfo directoryInfo = new DirectoryInfo(inDir);
				List<Task> list = new List<Task>();
				DirectoryInfo[] directories = directoryInfo.GetDirectories();
				foreach (DirectoryInfo dir in directories)
				{
					Task item = Task.Factory.StartNew(delegate
					{
						AtlasTool atlasTool3 = new AtlasTool();
						string name = dir.Name;
						atlasTool3.Collapse(Path.Combine(inDir, name), Path.Combine(outDir, name) + ".png", bBinary);
					});
					list.Add(item);
				}
				Task.WaitAll(list.ToArray());
				break;
			}
			default:
				throw new ArgumentException($"The action for \"{text}\" argument is not found, please refer to the doc", "strAction");
			}
		}
		catch (Exception e)
		{
			Error.Show(e, bShowMessage);
		}
	}
}
