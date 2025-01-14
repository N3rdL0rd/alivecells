using System;
using System.Collections.Generic;
using System.Drawing;

namespace Packer;

internal class Bin2DPacker
{
	public enum Algorithm
	{
		Guillotine,
		MaxRects
	}

	private Size m_StartingSize;

	private List<Bin2D> m_Bins = new List<Bin2D>();

	private Bin2D m_CurrentBin;

	private bool m_bCanIncreaseSize;

	public bool isEmpty
	{
		get
		{
			if (m_Bins.Count == 0)
			{
				return m_CurrentBin == null;
			}
			return false;
		}
	}

	public List<Bin2D> bins => m_Bins;

	public Size maximumSize { get; set; }

	public uint maximumBinCount { get; set; }

	public Size margin { get; set; }

	public MarginType marginType { get; set; }

	public Algorithm algorithm { get; set; }

	public Bin2DPacker(Size _startingSize, Size _maximumSize, Algorithm _algorithm)
	{
		m_StartingSize = _startingSize;
		maximumSize = _maximumSize;
		m_bCanIncreaseSize = true;
		marginType = MarginType.None;
		margin = new Size(0, 0);
		m_CurrentBin = null;
		maximumBinCount = uint.MaxValue;
		algorithm = _algorithm;
	}

	public void Clear()
	{
		m_Bins.Clear();
		m_CurrentBin = null;
	}

	public bool InsertElement(uint _id, Size _size, out bool _newBinCreated)
	{
		_newBinCreated = false;
		if (m_CurrentBin == null)
		{
			m_CurrentBin = CreateBin();
			m_Bins.Add(m_CurrentBin);
			_newBinCreated = true;
		}
		if (!m_CurrentBin.size.CanFit(_size + margin) && ((m_bCanIncreaseSize && !maximumSize.CanFit(_size + margin)) || !m_bCanIncreaseSize))
		{
			throw new Exception("This element will never fit in an atlas with the given parameters");
		}
		bool flag = false;
		for (int i = 0; i < m_Bins.Count; i++)
		{
			if (flag)
			{
				break;
			}
			flag = m_Bins[i].InsertElement(_id, _size);
		}
		while (!flag && maximumBinCount > m_Bins.Count)
		{
			if (m_bCanIncreaseSize && maximumSize.CanFit(m_CurrentBin.nextSize))
			{
				m_CurrentBin.IncreaseSize();
				m_CurrentBin.RearrangeBin();
			}
			else if (maximumBinCount > m_Bins.Count)
			{
				m_CurrentBin = CreateBin();
				m_Bins.Add(m_CurrentBin);
				_newBinCreated = true;
			}
			flag = m_CurrentBin.InsertElement(_id, _size);
		}
		return flag;
	}

	private Bin2D CreateBin()
	{
		if (algorithm == Algorithm.Guillotine)
		{
			return new Bin2DGuillotine(m_StartingSize, margin, marginType);
		}
		if (algorithm == Algorithm.MaxRects)
		{
			return new Bin2DMaxRects(m_StartingSize, margin, marginType);
		}
		throw new NotImplementedException();
	}
}
