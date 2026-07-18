using System;
using UnityEngine;

/// <summary>
/// 从世界相机同步抓取不包含 Screen Space Overlay UI 的存档截图。
/// </summary>
public sealed class SaveScreenshotCapture : MonoBehaviour
{
    [SerializeField] private Camera _worldCamera;
    [SerializeField] private int _width = 640;
    [SerializeField] private int _height = 360;

    /// <summary>
    /// 渲染世界相机并编码 PNG；失败时返回空数组且不阻止保存。
    /// </summary>
    public byte[] CapturePng()
    {
        try
        {
            Camera camera = _worldCamera != null ? _worldCamera : Camera.main;
            if (camera == null)
                return Array.Empty<byte>();

            var renderTexture = new RenderTexture(Mathf.Max(64, _width), Mathf.Max(64, _height), 24);
            var texture = new Texture2D(renderTexture.width, renderTexture.height, TextureFormat.RGB24, false);
            RenderTexture previousActive = RenderTexture.active;
            RenderTexture previousTarget = camera.targetTexture;
            try
            {
                camera.targetTexture = renderTexture;
                RenderTexture.active = renderTexture;
                camera.Render();
                texture.ReadPixels(new Rect(0, 0, renderTexture.width, renderTexture.height), 0, 0);
                texture.Apply();
                return texture.EncodeToPNG();
            }
            finally
            {
                camera.targetTexture = previousTarget;
                RenderTexture.active = previousActive;
                Destroy(renderTexture);
                Destroy(texture);
            }
        }
        catch (Exception error)
        {
            Debug.LogWarning($"[SaveScreenshot] 截图失败，保存继续: {error.Message}");
            return Array.Empty<byte>();
        }
    }
}
