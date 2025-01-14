using System;
using System.Collections.Generic;
using System.Drawing;

namespace Packer;

internal class Bin2DMaxRects : Bin2D
{
	private class Element
	{
		public Rectangle area;

		public uint id;

		public Element()
		{
			area = default(Rectangle);
			id = uint.MaxValue;
		}

		public Element(Rectangle _rectangle)
		{
			area = _rectangle;
			id = uint.MaxValue;
		}
	}

	private List<Element> m_FreeAreas;

	private List<Element> m_UsedAreas;

	public Bin2DMaxRects(Size _startSize, Size _margin, MarginType _marginType)
		: base(_startSize, _margin, _marginType)
	{
		Reset();
	}

	protected override bool InsertElement(uint _id, Size _elementSize, out Rectangle _area)
	{
		_area = default(Rectangle);
		Size elementSize = _elementSize + new Size(1, 1);
		int bestIndexForElement = GetBestIndexForElement(elementSize);
		if (bestIndexForElement == -1)
		{
			return false;
		}
		_area.Size = elementSize;
		_area.Location = m_FreeAreas[bestIndexForElement].area.Location;
		Element element = new Element();
		element.area = _area;
		element.id = _id;
		m_UsedAreas.Add(element);
		Rectangle area = m_FreeAreas[bestIndexForElement].area;
		Rectangle rectangle = new Rectangle(_area.X + _area.Width, _area.Y, area.Width - _area.Width, area.Height);
		if (rectangle.GetArea() > 0)
		{
			m_FreeAreas.Add(new Element(rectangle));
		}
		rectangle = new Rectangle(_area.X, _area.Y + _area.Height, area.Width, area.Height - _area.Height);
		if (rectangle.GetArea() > 0)
		{
			m_FreeAreas.Add(new Element(rectangle));
		}
		m_FreeAreas.RemoveAt(bestIndexForElement);
		List<Rectangle> list = new List<Rectangle>();
		int num = 0;
		while (num < m_FreeAreas.Count)
		{
			Rectangle @this = Rectangle.Intersect(m_FreeAreas[num].area, _area);
			if (@this.GetArea() > 0)
			{
				Rectangle area2 = m_FreeAreas[num].area;
				Rectangle rectangle2 = new Rectangle(area2.X, area2.Y, @this.X - area2.X, area2.Height);
				if (rectangle2.GetArea() > 0)
				{
					list.Add(rectangle2);
				}
				rectangle2 = new Rectangle(area2.X, @this.Y + @this.Height, area2.Width, area2.Height - (@this.Y - area2.Y + @this.Height));
				if (rectangle2.GetArea() > 0)
				{
					list.Add(rectangle2);
				}
				rectangle2 = new Rectangle(area2.X, area2.Y, area2.Width, @this.Y - area2.Y);
				if (rectangle2.GetArea() > 0)
				{
					list.Add(rectangle2);
				}
				rectangle2 = new Rectangle(@this.X + @this.Width, area2.Y, area2.Width - (@this.X - area2.X + @this.Width), area2.Height);
				if (rectangle2.GetArea() > 0)
				{
					list.Add(rectangle2);
				}
				m_FreeAreas.RemoveAt(num);
			}
			else
			{
				num++;
			}
		}
		for (int i = 0; i < list.Count; i++)
		{
			m_FreeAreas.Add(new Element(list[i]));
		}
		int num2 = 0;
		while (num2 < m_FreeAreas.Count - 1)
		{
			bool flag = false;
			int num3 = 1;
			while (num3 < m_FreeAreas.Count && num2 < m_FreeAreas.Count - 1)
			{
				if (num2 == num3)
				{
					num3++;
					continue;
				}
				if (m_FreeAreas[num2].area.Contains(m_FreeAreas[num3].area))
				{
					m_FreeAreas.RemoveAt(num3);
					continue;
				}
				if (m_FreeAreas[num3].area.Contains(m_FreeAreas[num2].area))
				{
					m_FreeAreas.RemoveAt(num2);
					flag = true;
					break;
				}
				num3++;
			}
			if (!flag)
			{
				num2++;
			}
		}
		return true;
	}

	protected override void RetrieveSizes(ref List<Size> _sizeList)
	{
		foreach (Element usedArea in m_UsedAreas)
		{
			_sizeList.Add(usedArea.area.Size - base.margin);
		}
	}

	protected override void RetrieveIDs(ref List<uint> _idList)
	{
		foreach (Element usedArea in m_UsedAreas)
		{
			_idList.Add(usedArea.id);
		}
	}

	protected override void Reset()
	{
		m_FreeAreas = new List<Element>();
		m_UsedAreas = new List<Element>();
		m_FreeAreas.Add(new Element(new Rectangle(0, 0, base.size.Width, base.size.Height)));
	}

	private int GetBestIndexForElement(Size _elementSize)
	{
		int num = int.MaxValue;
		int result = -1;
		for (int i = 0; i < m_FreeAreas.Count; i++)
		{
			Rectangle area = m_FreeAreas[i].area;
			if (area.Size.CanFit(_elementSize))
			{
				int num2 = Math.Min(area.Size.Width - _elementSize.Width, area.Size.Height - _elementSize.Height);
				if (num2 < num)
				{
					result = i;
					num = num2;
				}
			}
		}
		return result;
	}
}
