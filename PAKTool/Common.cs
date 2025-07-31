using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Newtonsoft.Json;

public class Adler32
{
	private int m_A1;

	private int m_A2;

	public int value => (m_A2 << 16) | m_A1;

	public Adler32()
	{
		m_A1 = 1;
		m_A2 = 0;
	}

	public void Update(byte[] _bytes, int _position, int _length)
	{
		int num = _position + _length;
		for (int i = _position; i < num; i++)
		{
			m_A1 = (m_A1 + _bytes[i]) % 65521;
			m_A2 = (m_A2 + m_A1) % 65521;
		}
	}

	public int Make(Stream _stream)
	{
		BinaryReader binaryReader = new BinaryReader(_stream);
		return Make(binaryReader.ReadBytes((int)_stream.Length));
	}

	public int Make(byte[] _bytes)
	{
		m_A1 = 1;
		m_A2 = 0;
		Update(_bytes, 0, _bytes.Length);
		return value;
	}
}
public class CastleJsonTextWriter : JsonTextWriter
{
	public CastleJsonTextWriter(TextWriter _writer)
		: base(_writer)
	{
	}

	public override void WriteValue(float _value)
	{
		if (_value == (float)(int)_value)
		{
			((JsonWriter)this).WriteValue((int)_value);
		}
		else
		{
			((JsonTextWriter)this).WriteValue(_value);
		}
	}

	public override void WriteValue(float? _value)
	{
		if (!_value.HasValue || _value != (float)(int)_value.Value)
		{
			((JsonTextWriter)this).WriteValue(_value);
		}
		else
		{
			((JsonWriter)this).WriteValue((int)_value.Value);
		}
	}
}

public class Error
{
	public static void Show(Exception _e, bool _bShowMessage)
	{
		Show(_bShowMessage, _e.Message, _e.StackTrace);
	}

	public static void Show(bool _bShowMsgBox, string _message, string _callstack)
	{
		Log.Error(_message, _callstack);
	}
}
public class Log
{
	public enum Level
	{
		NoMessage,
		Error,
		Warning,
		Message,
		VerboseMessage,
		Full
	}

	public static Level level { get; set; } = Level.Error;

	public static void Error(string _message, string _callstack = "")
	{
		if (level >= Level.Error)
		{
			ConsoleColor foregroundColor = Console.ForegroundColor;
			Console.ForegroundColor = ConsoleColor.DarkRed;
			Console.WriteLine(_message);
			if (_callstack != "")
			{
				Console.Write(_callstack);
			}
			Console.ForegroundColor = foregroundColor;
		}
	}

	public static void Message(string _message)
	{
		if (level >= Level.Message)
		{
			Console.WriteLine(_message);
		}
	}
}
public class Versionning
{
	public static string currentVersion => "1.7.0";
}
