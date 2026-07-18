using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// NPC 移动请求的最终结果。
/// </summary>
public enum MovementResult
{
    Succeeded,
    Failed,
    Cancelled,
}

/// <summary>
/// NPC 移动接口 — 方便以后替换为 NavMesh / A* 等寻路方案。
/// 默认实现: LerpMovementProvider（Transform 匀速移动）。
/// </summary>
public interface IMovementProvider
{
    /// <summary>开始移动到目标位置</summary>
    /// <param name="transform">NPC 的 Transform</param>
    /// <param name="target">目标世界坐标</param>
    /// <param name="speed">移动速度 (unit/s)</param>
    /// <param name="onComplete">移动结果回调</param>
    void MoveTo(Transform transform, Vector2 target, float speed, Action<MovementResult> onComplete);

    /// <summary>开始移动到指定 location_id</summary>
    /// <param name="transform">NPC 的 Transform</param>
    /// <param name="locationId">目标位置 ID</param>
    /// <param name="speed">移动速度 (unit/s)</param>
    /// <param name="onComplete">移动结果回调</param>
    void MoveToLocation(Transform transform, string locationId, float speed, Action<MovementResult> onComplete);

    /// <summary>停止移动</summary>
    void Stop(Transform transform);
}

/// <summary>
/// 默认移动实现 — Transform Lerp 匀速移动。
/// </summary>
public class LerpMovementProvider : IMovementProvider
{
    private readonly Dictionary<Transform, Coroutine> _runningMoves = new();
    private readonly Dictionary<Transform, Action<MovementResult>> _runningCallbacks = new();

    /// <summary>
    /// 开始一次直线移动，并在结束时返回成功、失败或取消。
    /// </summary>
    public void MoveTo(Transform transform, Vector2 target, float speed, Action<MovementResult> onComplete)
    {
        if (transform == null)
        {
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        var runner = transform.GetComponent<MonoBehaviour>();
        if (runner == null)
        {
            Debug.LogWarning("[LerpMove] 需要 MonoBehaviour 来运行 Coroutine");
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        Stop(transform);
        _runningCallbacks[transform] = onComplete;
        _runningMoves[transform] = runner.StartCoroutine(MoveRoutine(transform, target, speed));
    }

    /// <summary>
    /// 按 location_id 获取目标点后开始直线移动。
    /// </summary>
    public void MoveToLocation(Transform transform, string locationId, float speed, Action<MovementResult> onComplete)
    {
        if (transform == null)
        {
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        if (!LocationDatabase.HasPosition(locationId))
        {
            Debug.LogWarning($"[LerpMove] 无坐标: {locationId}");
            onComplete?.Invoke(MovementResult.Failed);
            return;
        }

        var target = LocationDatabase.GetPositionWithOffset(locationId);
        MoveTo(transform, target, speed, onComplete);
    }

    /// <summary>
    /// 取消当前 Transform 上正在执行的直线移动。
    /// </summary>
    public void Stop(Transform transform)
    {
        if (transform == null)
            return;

        var runner = transform.GetComponent<MonoBehaviour>();
        if (runner != null && _runningMoves.TryGetValue(transform, out var coroutine) && coroutine != null)
            runner.StopCoroutine(coroutine);

        CompleteMove(transform, MovementResult.Cancelled);
    }

    private System.Collections.IEnumerator MoveRoutine(Transform transform, Vector2 target,
                                                         float speed)
    {
        Vector3 start = transform.position;
        Vector3 end = new Vector3(target.x, target.y, start.z);
        float distance = Vector3.Distance(start, end);
        if (distance < 0.01f)
        {
            CompleteMove(transform, MovementResult.Succeeded);
            yield break;
        }

        speed = Mathf.Max(0.01f, speed);
        float duration = distance / speed;
        float elapsed = 0f;

        while (elapsed < duration)
        {
            // 玩家正式对话或 NPC 世界气泡对话期间冻结移动，形成稳定站位。
            var gm = GameManager.Instance;
            var npc = transform.GetComponent<NpcEntity>();
            if ((gm != null && gm.IsDialogueActive) || (npc != null && npc.IsMotionLocked))
            {
                yield return null;
                continue;
            }

            elapsed += Time.deltaTime;
            float t = Mathf.Clamp01(elapsed / duration);
            // Smooth step for natural feel
            transform.position = Vector3.Lerp(start, end, Mathf.SmoothStep(0f, 1f, t));
            yield return null;
        }

        transform.position = end;
        CompleteMove(transform, MovementResult.Succeeded);
    }

    /// <summary>
    /// 移除运行记录并发送一次移动结果回调。
    /// </summary>
    private void CompleteMove(Transform transform, MovementResult result)
    {
        _runningMoves.Remove(transform);

        if (!_runningCallbacks.TryGetValue(transform, out var callback))
            return;

        _runningCallbacks.Remove(transform);
        callback?.Invoke(result);
    }
}
