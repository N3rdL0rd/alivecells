using System;
using System.Collections.Generic;
using System.Drawing;

namespace Packer;

internal abstract class Bin2D
{
	private enum GrowthState
	{
		GrowWidth,
		SwapWidthHeight,
		Count
	}

	private Dictionary<uint, Rectangle> m_Elements = new Dictionary<uint, Rectangle>();

	public Size size { get; private set; }

	public Dictionary<uint, Rectangle> elements => m_Elements;

	public Size margin { get; private set; }

	public MarginType marginType { get; private set; }

	public Size nextSize
	{
		get
		{
			if (currentGrowthState == GrowthState.GrowWidth)
			{
				return new Size(size.Width * 2, size.Height);
			}
			if (currentGrowthState == GrowthState.SwapWidthHeight)
			{
				return new Size(size.Height, size.Width);
			}
			throw new NotImplementedException();
		}
	}

	protected Size startSize { get; private set; }

	private GrowthState currentGrowthState { get; set; }

	public Bin2D(Size _startSize, Size _margin, MarginType _marginType)
	{
		size = _startSize;
		margin = _margin;
		marginType = _marginType;
		currentGrowthState = GrowthState.GrowWidth;
		startSize = _startSize;
	}

	public void IncreaseSize()
	{
		size = nextSize;
		currentGrowthState = (GrowthState)((int)(currentGrowthState + 1) % 2);
	}

	public bool InsertElement(uint _id, Size _elementSize)
	{
		if (InsertElement(_id, _elementSize, out var _area))
		{
			m_Elements.Add(_id, _area);
			return true;
		}
		return false;
	}

	protected abstract bool InsertElement(uint _id, Size _elementSize, out Rectangle _area);

	protected abstract void RetrieveSizes(ref List<Size> _areaList);

	protected abstract void RetrieveIDs(ref List<uint> _idList);

	protected abstract void Reset();

	public void RearrangeBin()
	{
		List<Size> _areaList = new List<Size>();
		List<uint> _idList = new List<uint>();
		RetrieveSizes(ref _areaList);
		RetrieveIDs(ref _idList);
		bool flag = true;
		do
		{
			flag = true;
			m_Elements.Clear();
			Reset();
			int count = _areaList.Count;
			for (int i = 0; i < count && flag; i++)
			{
				if (!InsertElement(_idList[i], _areaList[i]))
				{
					flag = false;
					IncreaseSize();
				}
			}
		}
		while (!flag);
	}
}
