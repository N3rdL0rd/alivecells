using System.Drawing;

namespace AtlasTool;
//图块类用于存放一个图块具有的信息
internal class Tile
{
	public string name;//图块名

	public int index;//索引

	public int x;//图块左上角x像素坐标

	public int y;//图块左上角y像素坐标

	public int width;//图块宽

	public int height;//图块高

	public int offsetX;//图块在新图中的左上角x像素坐标

    	public int offsetY;//图块在新图中的左上角y像素坐标

	public int originalWidth;//新图宽

	public int originalHeight; //新图高

	public string originalFilePath;

	public Bitmap bitmap;

	public bool hasNormal;

	public Tile duplicateOf;

	public int atlasIndex = -1;// 属于第几张大图
}
