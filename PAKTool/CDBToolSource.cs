using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace CDBTool
{
    internal class Separator
    {
        public int id { get; set; }

        public string name { get; private set; }

        public int lineIndex { get; private set; }

        public Separator(int _id, string _name, int _lineIndex)
        {
            this.id = _id;
            this.name = _name;
            this.lineIndex = _lineIndex;
        }

        public void pushLine()
        {
            ++this.lineIndex;
        }
    }

    public class CDBTool
    {
        private class Test
        {
            public int i;
            public JObject obj;
            public string originalFileName;

            public Test(int _i, JObject _obj, string _originalFileName)
            {
                this.i = _i;
                this.obj = _obj;
                this.originalFileName = _originalFileName;
            }
        }

        public const string structureFileName = "__STRUCTURE__.json";
        public const string propertyFileName = "__PROPS__.json";
        public const string columnsNodeName = "__columns";
        public const string tableIndexName = "__table_index";
        public const string separatorGroupIDName = "__separator_group_ID";
        public const string separatorGroupNameName = "__separator_group_Name";
        public const string originalIndexName = "__original_Index";

        public bool bMultiThread = true;

        public void Expand(string _sourceCDBPath, string _output)
        {
            DirectoryInfo directoryInfo = new DirectoryInfo(_output);
            if (!File.Exists(_sourceCDBPath))
                throw new FileNotFoundException("CDB file not found : " + _sourceCDBPath, _sourceCDBPath);

            directoryInfo.Create();
            string[] preferredNameKeys = new string[5] { "id", "item", "name", "room", "animId" };
            JObject root = (JObject)JsonConvert.DeserializeObject(File.ReadAllText(_sourceCDBPath));
            int tableIndex = 0;

            foreach (JObject sheet in (IEnumerable<JToken>)root["sheets"])
            {
                string path = sheet["name"].ToString();
                DirectoryInfo sheetDirectory = directoryInfo.CreateSubdirectory(path);
                JArray columns = sheet.Value<JArray>("columns");

                JObject structure = new JObject();
                structure.Add("__columns", columns);
                structure.Add("__table_index", tableIndex);
                this.WriteContent(Path.Combine(sheetDirectory.FullName, "__STRUCTURE__.json"), structure.ToString());

                List<Separator> separators = new List<Separator>();
                JArray separatorLines = sheet.Value<JArray>("separators");
                JObject propsObject = null;
                JArray separatorTitles = null;
                if (separatorLines != null)
                {
                    propsObject = sheet.Value<JObject>("props");
                    if (propsObject != null)
                        separatorTitles = propsObject.Value<JArray>("separatorTitles");
                }

                if (separatorTitles != null)
                {
                    List<int> indices = new List<int>();
                    foreach (JToken separatorLine in separatorLines)
                        indices.Add((int)separatorLine);

                    List<string> names = new List<string>();
                    foreach (JToken separatorTitle in separatorTitles)
                        names.Add((string)separatorTitle);

                    for (int i = 0; i < indices.Count; ++i)
                        separators.Add(new Separator(i, names[i], indices[i]));
                }

                int separatorCount = separators.Count;
                if (separatorCount > 0)
                    separators.Sort((a, b) => a.lineIndex.CompareTo(b.lineIndex));

                JObject props = (JObject)sheet["props"];
                props.Remove("separatorTitles");
                this.WriteContent(Path.Combine(sheetDirectory.FullName, "__PROPS__.json"), props.ToString());

                int originalIndex = 0;
                string preferredNameKey = "";
                JArray lines = sheet.Value<JArray>("lines");
                int digits = (int)Math.Floor(Math.Log10(lines.Count)) + 1;
                string indexFormat = "D" + digits;
                int currentSeparatorIndex = -1;

                foreach (JObject line in lines)
                {
                    while (separatorCount > 0 && currentSeparatorIndex + 1 < separatorCount && originalIndex >= separators[currentSeparatorIndex + 1].lineIndex)
                        ++currentSeparatorIndex;

                    line.Add("__separator_group_ID", currentSeparatorIndex);
                    string separatorName = "";
                    if (currentSeparatorIndex >= 0 && currentSeparatorIndex < separatorCount)
                        separatorName = separators[currentSeparatorIndex].name;

                    line.Add("__separator_group_Name", separatorName);
                    line.Add("__original_Index", originalIndex);

                    string lineName = null;
                    if (preferredNameKey == "")
                    {
                        for (int i = 0; i < preferredNameKeys.Length && lineName == null; ++i)
                        {
                            try
                            {
                                lineName = line[preferredNameKeys[i]].ToString();
                                preferredNameKey = preferredNameKeys[i];
                            }
                            catch (Exception)
                            {
                            }
                        }
                    }
                    else
                    {
                        try
                        {
                            lineName = line[preferredNameKey].ToString();
                        }
                        catch (Exception)
                        {
                        }
                    }

                    string indexedPrefix = originalIndex.ToString(indexFormat);
                    if (string.IsNullOrEmpty(lineName))
                        lineName = indexedPrefix + "-UnnamedLine";

                    string outputDir = Path.Combine(sheetDirectory.FullName, separatorName);
                    Directory.CreateDirectory(outputDir);
                    this.WriteContent(Path.Combine(outputDir, indexedPrefix + "---" + lineName + ".json"), line.ToString());
                    ++originalIndex;
                }

                ++tableIndex;
            }
        }

        public void Collapse(string _rootInput, string _destCDBPath)
        {
            DirectoryInfo rootInput = new DirectoryInfo(_rootInput);
            if (!rootInput.Exists)
                throw new DirectoryNotFoundException("Input directory not found : " + _rootInput);

            JObject root = new JObject();
            JArray sheets = new JArray();
            root.Add("sheets", sheets);
            List<KeyValuePair<int, JObject>> orderedSheets = new List<KeyValuePair<int, JObject>>();

            foreach (DirectoryInfo sheetDirectory in rootInput.GetDirectories())
            {
                JObject sheet = new JObject();
                JArray lines = new JArray();
                JObject props = null;
                JArray separators = new JArray();

                sheet.Add("name", sheetDirectory.Name);
                List<Separator> separatorInfo = new List<Separator>();

                foreach (FileInfo file in sheetDirectory.GetFiles("*.json", SearchOption.AllDirectories))
                {
                    if (file.Name == "__STRUCTURE__.json" || file.Name == "__PROPS__.json")
                        continue;

                    JObject line = (JObject)JsonConvert.DeserializeObject(File.ReadAllText(file.FullName));
                    int separatorId = line.Value<int>("__separator_group_ID");
                    string separatorName = line.Value<string>("__separator_group_Name");
                    Separator separator = new Separator(separatorId, separatorName, 0);
                    if (separatorId == -1 || separatorInfo.Find(s => s.name == separatorName) != null)
                        continue;

                    bool conflict;
                    do
                    {
                        conflict = false;
                        if (separatorInfo.Count == 0)
                            continue;

                        int existingIndex = 0;
                        while (existingIndex < separatorInfo.Count && separatorInfo[existingIndex].id != separator.id)
                            ++existingIndex;

                        conflict = existingIndex < separatorInfo.Count;
                        if (!conflict)
                            continue;

                        foreach (Separator existing in separatorInfo)
                        {
                            if (existing.id > separator.id)
                                existing.id++;
                        }
                        separator.id++;
                    }
                    while (conflict);

                    separatorInfo.Add(separator);
                }

                List<KeyValuePair<long, int>> lineOrder = new List<KeyValuePair<long, int>>();
                List<JObject> lineObjects = new List<JObject>();
                foreach (FileInfo file in sheetDirectory.GetFiles("*.json", SearchOption.AllDirectories))
                {
                    JObject json = (JObject)JsonConvert.DeserializeObject(File.ReadAllText(file.FullName));
                    if (file.Name == "__STRUCTURE__.json")
                    {
                        sheet.Add("columns", json.Value<JArray>("__columns").DeepClone());
                        orderedSheets.Add(new KeyValuePair<int, JObject>(json.Value<int>("__table_index"), sheet));
                        continue;
                    }

                    if (file.Name == "__PROPS__.json")
                    {
                        props = (JObject)json.DeepClone();
                        continue;
                    }

                    JObject line = (JObject)json.DeepClone();
                    int separatorId = -1;
                    string separatorName = line.Value<string>("__separator_group_Name");
                    if (separatorInfo.Count > 0 && !string.IsNullOrEmpty(separatorName))
                    {
                        int matchIndex = 0;
                        while (matchIndex < separatorInfo.Count && separatorInfo[matchIndex].name != separatorName)
                            ++matchIndex;
                        separatorId = separatorInfo[matchIndex].id;
                    }

                    for (int i = 0; i < separatorInfo.Count; ++i)
                    {
                        if (separatorInfo[i].id > separatorId)
                        {
                            separatorInfo[i].pushLine();
                        }
                        else if (separatorInfo[i].id == separatorId)
                        {
                            string currentName = line.Value<string>("__separator_group_Name");
                            if (separatorInfo[i].name != currentName)
                                separatorInfo[i].pushLine();
                        }
                    }

                    int originalIndex = line.Value<int>("__original_Index");
                    lineOrder.Add(new KeyValuePair<long, int>(((long)originalIndex << 32) | (uint)(separatorId + 1), lineObjects.Count));
                    lineObjects.Add(line);
                    line.Remove("__separator_group_ID");
                    line.Remove("__separator_group_Name");
                    line.Remove("__original_Index");
                }

                lineOrder.Sort((a, b) => a.Key.CompareTo(b.Key));
                for (int i = 0; i < lineOrder.Count; ++i)
                    lines.Add(lineObjects[lineOrder[i].Value]);

                separatorInfo.Sort((a, b) => a.lineIndex.CompareTo(b.lineIndex));
                JArray separatorTitles = new JArray();
                props.AddFirst(new JProperty("separatorTitles", separatorTitles));
                foreach (Separator separator in separatorInfo)
                {
                    if (separator.lineIndex > -1)
                    {
                        separators.Add(separator.lineIndex);
                        separatorTitles.Add(separator.name);
                    }
                }

                sheet.Add("lines", lines);
                sheet.Add("separators", separators);
                sheet.Add("props", props);
            }

            orderedSheets.Sort((a, b) => a.Key.CompareTo(b.Key));
            for (int i = 0; i < orderedSheets.Count; ++i)
                sheets.Add(orderedSheets[i].Value);

            root.Add("compress", false);
            root.Add("customTypes", new JArray());
            Directory.CreateDirectory(new FileInfo(_destCDBPath).Directory.FullName);
            this.WriteContentAsync(_destCDBPath, GetCDBJObjectAsString(root)).Wait();
        }

        public static string GetCDBJObjectAsString(JObject _root)
        {
            StringWriter stringWriter = new StringWriter();
            CastleJsonTextWriter jsonWriter = new CastleJsonTextWriter(stringWriter)
            {
                Formatting = Formatting.Indented,
                Indentation = 1,
                IndentChar = '\t'
            };
            new JsonSerializer().Serialize(jsonWriter, _root);
            string result = stringWriter.ToString().Replace("\r", "");
            jsonWriter.Close();
            stringWriter.Close();
            return result;
        }

        public void BuildDiffCDB(string _referenceCDBPath, string _inputDirPath, string _outputDirPath)
        {
            DirectoryInfo tempDirectory = new DirectoryInfo(Path.Combine(Path.GetTempPath(), Path.GetRandomFileName()));
            string expandedReferencePath = tempDirectory.FullName;
            this.Expand(_referenceCDBPath, expandedReferencePath);

            Dictionary<string, Test> referenceMap = this.BuildCRCFileMap(tempDirectory);
            Dictionary<string, Test> inputMap = this.BuildCRCFileMap(new DirectoryInfo(_inputDirPath));
            List<string> changedFiles = new List<string>();

            foreach (KeyValuePair<string, Test> item in inputMap)
            {
                if (referenceMap.TryGetValue(item.Key, out Test existing))
                {
                    if (existing.i != item.Value.i)
                        changedFiles.Add(item.Value.originalFileName);
                }
                else
                {
                    changedFiles.Add(item.Value.originalFileName);
                }
            }

            if (changedFiles.Count > 0)
            {
                new DirectoryInfo(_outputDirPath).Create();
                foreach (string file in changedFiles)
                {
                    FileInfo destination = new FileInfo(Path.Combine(_outputDirPath, this.GetOriginalName(file)));
                    Directory.CreateDirectory(destination.Directory.FullName);
                    File.Copy(Path.Combine(_inputDirPath, file), destination.FullName, true);
                }
            }

            tempDirectory.Delete(true);
        }

        private Dictionary<string, Test> BuildCRCFileMap(DirectoryInfo _rootDir)
        {
            int prefixLength = _rootDir.FullName.Length;
            Dictionary<string, Test> result = new Dictionary<string, Test>();
            List<DirectoryInfo> directories = new List<DirectoryInfo>();
            directories.Add(_rootDir);
            Adler32 adler32 = new Adler32();

            for (int i = 0; i < directories.Count; ++i)
            {
                foreach (DirectoryInfo directory in directories[i].GetDirectories())
                    directories.Add(directory);

                foreach (FileInfo file in directories[i].GetFiles())
                {
                    string relativePath = file.FullName.Substring(prefixLength + 1);
                    string originalName = this.GetOriginalName(relativePath);
                    try
                    {
                        JObject json = (JObject)JsonConvert.DeserializeObject(File.ReadAllText(file.FullName));
                        int checksum;
                        if (!json.Remove("__original_Index"))
                        {
                            using (Stream stream = File.OpenRead(file.FullName))
                                checksum = adler32.Make(stream);
                        }
                        else
                        {
                            checksum = adler32.Make(Encoding.UTF8.GetBytes(json.ToString()));
                        }

                        result.Add(originalName, new Test(checksum, json, relativePath));
                    }
                    catch (Exception)
                    {
                        Log.Error("Failing to build CRC for file : " + originalName + " from " + file.FullName, "");
                        throw;
                    }
                }
            }

            return result;
        }

        private string GetOriginalName(string _indexedAndCategorizedName)
        {
            string[] parts = _indexedAndCategorizedName.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            List<string> pathParts = new List<string>(parts);
            while (pathParts.Count > 2)
                pathParts.RemoveAt(1);

            string fileName = pathParts[pathParts.Count - 1];
            int index = fileName.IndexOf("---", StringComparison.Ordinal);
            if (index != -1)
                pathParts[pathParts.Count - 1] = fileName.Substring(index + 3);

            return Path.Combine(pathParts.ToArray());
        }

        private void WriteContent(string _fileName, string _content)
        {
            if (this.bMultiThread)
            {
                this.WriteContentAsync(_fileName, _content).ContinueWith(
                    t => Error.Show(t.Exception, false),
                    TaskContinuationOptions.OnlyOnFaulted
                );
            }
            else
            {
                WriteContentSync(_fileName, _content);
            }
        }

        private static void WriteContentSync(string _fileName, string _content)
        {
            using (StreamWriter streamWriter = new FileInfo(_fileName).CreateText())
                streamWriter.Write(_content);
        }

        private async Task WriteContentAsync(string _fileName, string _content)
        {
            using (StreamWriter writer = new FileInfo(_fileName).CreateText())
                await writer.WriteAsync(_content);
        }
    }
}
