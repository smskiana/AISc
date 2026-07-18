using System.Reflection;
using NUnit.Framework;
using UnityEngine;

/// <summary>
/// 验证加载阶段更新不会把已播放的假进度重置到起点。
/// </summary>
public sealed class SystemMessageLoadingProgressTests
{
    /// <summary>
    /// 同一次加载的后续阶段必须保留当前视觉进度，只提高目标下限。
    /// </summary>
    [Test]
    public void LaterLoadingStageDoesNotResetVisualProgress()
    {
        var viewObject = new GameObject("SystemMessageViewTest");
        var controllerObject = new GameObject("SystemMessageControllerTest");
        try
        {
            var view = viewObject.AddComponent<SystemMessageView>();
            var controller = controllerObject.AddComponent<SystemMessageController>();
            SetPrivateField(controller, "_view", view);

            controller.SetLoadingProgress("第一阶段", 0.25f);
            SetPrivateField(view, "_visualProgress", 0.42f);
            controller.SetLoadingProgress("第二阶段", 0.55f);

            Assert.AreEqual(0.42f, GetPrivateField<float>(view, "_visualProgress"));
            Assert.AreEqual(0.55f, GetPrivateField<float>(view, "_targetProgress"));
        }
        finally
        {
            Object.DestroyImmediate(viewObject);
            Object.DestroyImmediate(controllerObject);
        }
    }

    /// <summary>
    /// 以反射绑定测试专用字段，避免为测试扩大运行时接口。
    /// </summary>
    private static void SetPrivateField(object target, string fieldName, object value)
    {
        target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic)
            .SetValue(target, value);
    }

    /// <summary>
    /// 读取测试所需私有状态，验证视觉进度没有被阶段消息重置。
    /// </summary>
    private static T GetPrivateField<T>(object target, string fieldName)
    {
        return (T)target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic)
            .GetValue(target);
    }
}
