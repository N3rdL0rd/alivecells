using System.Drawing;

namespace Packer;

internal static class Extensions
{
	public static bool CanFit(this Size _this, Size _sizeToFit)
	{
		if (_this.Width >= _sizeToFit.Width)
		{
			return _this.Height >= _sizeToFit.Height;
		}
		return false;
	}

	public static bool DoesIntersect(this Rectangle _this, Rectangle _rectangle)
	{
		return Rectangle.Intersect(_this, _rectangle).GetArea() > 0;
	}

	public static int GetArea(this Rectangle _this)
	{
		return _this.Width * _this.Height;
	}
}
