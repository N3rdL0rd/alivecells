using System.Drawing;

namespace AtlasTool;
//ͼ�������ڴ��һ��ͼ����е���Ϣ
internal class Tile
{
	public string name;//ͼ����

	public int index;//����

	public int x;//ͼ�����Ͻ�x��������

	public int y;//ͼ�����Ͻ�y��������

    public int width;//ͼ���

	public int height;//ͼ���

	public int offsetX;//ͼ������ͼ�е����Ͻ�x��������

    public int offsetY;//ͼ������ͼ�е����Ͻ�y��������

    public int originalWidth;//��ͼ��

    public int originalHeight; //��ͼ��

    public string originalFilePath;

	public Bitmap bitmap;

	public bool hasNormal;

	public Tile duplicateOf;

	public int atlasIndex;// ���ڵڼ��Ŵ�ͼ
}
