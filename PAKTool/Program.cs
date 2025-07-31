using System;
using System.Globalization;
using System.Threading;

namespace PAKTool
{
    internal class Program
    {
        static readonly string DEFAULT_STAMP = "f5601c10de243a6dcc424121ee4bcc2b9b36323a15a0dd00312f61b3e704c71f"; // for game commit f8349ab

        private static void Main(string[] args)
        {
            Console.WriteLine($"----- N3rdL0rd's PakTool v0.2 (based on ModTools v{Versionning.currentVersion}) -----");
            Thread.CurrentThread.CurrentUICulture = CultureInfo.InvariantCulture;

            if (args.Length == 0 || args[0] == "--help" || args[0] == "-h")
            {
                DisplayHelp();
                Environment.Exit(0);
            }

            string action = args[0].ToLowerInvariant();
            string inputDir = string.Empty;
            string outputDir = string.Empty;
            string refPak = string.Empty;
            string outputPak = string.Empty;
            string stamp = Program.DEFAULT_STAMP;
            bool showErrors = false;

            try
            {
                switch (action)
                {
                    case "expand":
                        if (args.Length < 3)
                            throw new ArgumentException("Usage: expand <output directory> <input pak path>");
                        outputDir = args[1];
                        refPak = args[2];
                        break;

                    case "collapse":
                        if (args.Length < 3)
                            throw new ArgumentException("Usage: collapse <input directory> <output pak path>");
                        inputDir = args[1];
                        outputPak = args[2];
                        break;

                    case "collapsev1":
                        if (args.Length < 3)
                            throw new ArgumentException("Usage: collapsev1 <input directory> <output pak path>");
                        inputDir = args[1];
                        outputPak = args[2];
                        ParseOptions(args, ref showErrors, ref stamp);
                        break;

                    case "creatediffpak":
                        if (args.Length < 4)
                            throw new ArgumentException("Usage: creatediffpak <input pak path> <input directory> <output pak path>");
                        refPak = args[1];
                        inputDir = args[2];
                        outputPak = args[3];
                        break;

                    default:
                        Console.WriteLine($"The action \"{action}\" is not recognized. Please refer to the documentation.");
                        DisplayHelp();
                        Environment.Exit(1);
                        break;
                }

                ExecuteAction(action, inputDir, outputDir, refPak, outputPak, stamp, showErrors);
            }
            catch (Exception ex)
            {
                Error.Show(ex, showErrors);
            }
        }

        private static void ParseOptions(string[] args, ref bool showErrors, ref string stamp)
        {
            for (int i = 3; i < args.Length; i++)
            {
                string arg = args[i];

                switch (arg.ToLowerInvariant())
                {
                    case "--popup-errors":
                    case "-p":
                        showErrors = true;
                        break;
                    case "--stamp":
                    case "-s":
                        if (i + 1 < args.Length)
                        {
                            stamp = args[++i];
                        }
                        else
                        {
                            throw new ArgumentException("The --stamp/-s option requires a value.");
                        }
                        break;
                }
            }
        }

        private static void DisplayHelp()
        {
            Console.WriteLine("Usage:");
            Console.WriteLine("  expand        <output directory> <input pak path>                     Expands a PAK of any version into a directory");
            Console.WriteLine("  collapse      <input directory> <output pak path>                     Creates a v0 PAK from a directory, but is broken past v35");
            Console.WriteLine("  collapsev1    <input directory> <output pak path>                     Creates a v1 PAK from a directory, bypassing the stamp verification");
            Console.WriteLine("  creatediffpak <input pak path> <input directory> <output pak path>    Creates a v0 diff PAK, completely unmodified from the base tool");
            Console.WriteLine("Options:");
            Console.WriteLine("  -p, --popup-errors     Pop up a message box upon errors occuring, similarly to how the original PakTool did");
            Console.WriteLine("  -s, --stamp <value>    Specify a custom stamp to use to bypass PAK authenticity verification past v35");
            Console.WriteLine("  -h, --help             Display this help message");
        }

        private static void ExecuteAction(string action, string inputDir, string outputDir, string refPak, string outputPak, string stamp, bool showErrors)
        {
            PAKTool pakTool = new PAKTool();
            switch (action)
            {
                case "expand":
                    Console.WriteLine("Expanding PAK...");
                    pakTool.ExpandPAK(refPak, outputDir);
                    break;
                case "collapse":
                    Console.WriteLine("Collapsing PAK...");
                    pakTool.BuildPAK(inputDir, outputPak);
                    break;
                case "collapsev1":
                    Console.WriteLine($"Repacking PAK... (with stamp {stamp})");
                    pakTool.BuildPAKStamped(inputDir, outputPak, stamp);
                    break;
                case "creatediffpak":
                    Console.WriteLine("Creating Diff PAK...");
                    pakTool.BuildDiffPAK(refPak, inputDir, outputPak);
                    break;
                default:
                    Console.WriteLine($"The action \"{action}\" is not recognized. Please refer to the documentation.");
                    break;
            }
        }
    }
}
