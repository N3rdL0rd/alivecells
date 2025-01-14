using System.Collections.Generic;
using System.Drawing;

namespace Packer;

internal class Bin2DNodeGuillotine
{
	private enum BorderType
	{
		None = 0,
		Left = 1,
		Top = 2,
		Right = 4,
		Bottom = 8
	}

	private const uint invalidID = uint.MaxValue;

	private Bin2DNodeGuillotine m_LeftChild;

	private Bin2DNodeGuillotine m_RightChild;

	private Bin2DGuillotine m_Bin;

	public Rectangle area { get; set; }

	public bool isLeaf
	{
		get
		{
			if (m_LeftChild == null)
			{
				return m_RightChild == null;
			}
			return false;
		}
	}

	private uint id { get; set; }

	private BorderType m_Border { get; set; }

	public Bin2DNodeGuillotine(Bin2DGuillotine _bin)
	{
		id = uint.MaxValue;
		m_Bin = _bin;
	}

	public Bin2DNodeGuillotine Insert(uint _id, Size _size, Size _margins, MarginType _marginType)
	{
		if (!isLeaf)
		{
			Bin2DNodeGuillotine bin2DNodeGuillotine = m_LeftChild.Insert(_id, _size, _margins, _marginType);
			if (bin2DNodeGuillotine != null)
			{
				return bin2DNodeGuillotine;
			}
			return m_RightChild.Insert(_id, _size, _margins, _marginType);
		}
		if (id != uint.MaxValue)
		{
			return null;
		}
		Size sizeWithMargin = GetSizeWithMargin(_size, _margins, _marginType);
		if (sizeWithMargin.Width > area.Width || sizeWithMargin.Height > area.Height)
		{
			return null;
		}
		if (sizeWithMargin.Width == area.Width && sizeWithMargin.Height == area.Height)
		{
			id = _id;
			return this;
		}
		m_LeftChild = new Bin2DNodeGuillotine(m_Bin);
		m_RightChild = new Bin2DNodeGuillotine(m_Bin);
		m_LeftChild.m_Border = BorderType.None;
		m_RightChild.m_Border = BorderType.None;
		int num = area.Width - sizeWithMargin.Width;
		int num2 = area.Height - sizeWithMargin.Height;
		if (num > num2)
		{
			m_LeftChild.m_Border = (m_Border & BorderType.Left) | (m_Border & BorderType.Top) | (m_Border & BorderType.Bottom);
			sizeWithMargin = GetSizeWithMargin(_size, _margins, _marginType);
			m_LeftChild.area = new Rectangle(area.Location, new Size(sizeWithMargin.Width, area.Height));
			m_RightChild.m_Border = (m_Border & BorderType.Right) | (m_Border & BorderType.Top) | (m_Border & BorderType.Bottom);
			m_RightChild.area = new Rectangle(area.Left + sizeWithMargin.Width, area.Top, area.Width - sizeWithMargin.Width, area.Height);
		}
		else
		{
			m_LeftChild.m_Border = (m_Border & BorderType.Left) | (m_Border & BorderType.Top) | (m_Border & BorderType.Right);
			sizeWithMargin = GetSizeWithMargin(_size, _margins, _marginType);
			m_LeftChild.area = new Rectangle(area.Location, new Size(area.Width, sizeWithMargin.Height));
			m_RightChild.m_Border = (m_Border & BorderType.Left) | (m_Border & BorderType.Bottom) | (m_Border & BorderType.Right);
			m_RightChild.area = new Rectangle(area.Left, area.Top + sizeWithMargin.Height, area.Width, area.Height - sizeWithMargin.Height);
		}
		return m_LeftChild.Insert(_id, _size, _margins, _marginType);
	}

	public void RetrieveSizes(ref List<Size> _sizeList)
	{
		if (isLeaf)
		{
			if (id != uint.MaxValue)
			{
				_sizeList.Add(GetAreaWithoutMargin(m_Bin.margin, m_Bin.marginType).Size);
			}
		}
		else
		{
			m_LeftChild.RetrieveSizes(ref _sizeList);
			m_RightChild.RetrieveSizes(ref _sizeList);
		}
	}

	private Size GetSizeWithMargin(Size _sizeWithoutMargins, Size _margin, MarginType _marginType)
	{
		Size result = new Size(_sizeWithoutMargins.Width, _sizeWithoutMargins.Height);
		if ((_marginType == MarginType.OnlyBorder || _marginType == MarginType.All) && (m_Border & BorderType.Left) != 0)
		{
			result.Width += _margin.Width;
		}
		if (_marginType == MarginType.All || (_marginType == MarginType.OnlyBorder && (m_Border & BorderType.Right) != 0) || (_marginType == MarginType.NoBorder && (m_Border & BorderType.Right) == 0))
		{
			result.Width += _margin.Width;
		}
		if ((_marginType == MarginType.OnlyBorder || _marginType == MarginType.All) && (m_Border & BorderType.Top) != 0)
		{
			result.Height += _margin.Height;
		}
		if (_marginType == MarginType.All || (_marginType == MarginType.OnlyBorder && (m_Border & BorderType.Bottom) != 0) || (_marginType == MarginType.NoBorder && (m_Border & BorderType.Bottom) == 0))
		{
			result.Height += _margin.Height;
		}
		return result;
	}

	public Rectangle GetAreaWithoutMargin(Size _margin, MarginType _marginType)
	{
		Rectangle result = new Rectangle(area.Location, area.Size);
		if ((_marginType == MarginType.OnlyBorder || _marginType == MarginType.All) && (m_Border & BorderType.Left) != 0)
		{
			result.X += _margin.Width;
			result.Width -= _margin.Width;
		}
		if (_marginType == MarginType.All || (_marginType == MarginType.OnlyBorder && (m_Border & BorderType.Right) != 0) || (_marginType == MarginType.NoBorder && (m_Border & BorderType.Right) == 0))
		{
			result.Width -= _margin.Width;
		}
		if ((_marginType == MarginType.OnlyBorder || _marginType == MarginType.All) && (m_Border & BorderType.Top) != 0)
		{
			result.Y += _margin.Height;
			result.Height -= _margin.Height;
		}
		if (_marginType == MarginType.All || (_marginType == MarginType.OnlyBorder && (m_Border & BorderType.Bottom) != 0) || (_marginType == MarginType.NoBorder && (m_Border & BorderType.Bottom) == 0))
		{
			result.Height -= _margin.Height;
		}
		return result;
	}

	public void RetrieveIDs(ref List<uint> _idList)
	{
		if (isLeaf)
		{
			if (id != uint.MaxValue)
			{
				_idList.Add(id);
			}
		}
		else
		{
			m_LeftChild.RetrieveIDs(ref _idList);
			m_RightChild.RetrieveIDs(ref _idList);
		}
	}
}
