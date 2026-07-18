using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 前端 NPC 空闲表现调度器；只占用可抢占的表现槽，不改变后端权威行为。
/// </summary>
public class NpcAmbientBehaviorController
{
    private const int CheckIntervalGameMinutes = 30;
    private const float TriggerChance = 0.45f;
    private const float PoseDurationMinSec = 2.5f;
    private const float PoseDurationMaxSec = 5.5f;

    private readonly Dictionary<string, int> _lastCheckMinuteByNpc = new();
    private readonly AmbientOption[] _options =
    {
        new("ambient_look_around", "四下看看", false),
        new("ambient_adjust_posture", "整理姿势", false),
        new("ambient_pace_nearby", "在附近踱步", true),
    };

    /// <summary>
    /// 在 NPC 生成或刷新后初始化冷却，避免进入场景瞬间集体触发小动作。
    /// </summary>
    public void Prime(IEnumerable<NpcEntity> npcs, GameTime gameTime)
    {
        if (npcs == null || gameTime == null)
            return;

        int now = ToAbsoluteGameMinute(gameTime);
        foreach (var npc in npcs)
        {
            if (npc == null || string.IsNullOrEmpty(npc.NpcId))
                continue;

            if (!_lastCheckMinuteByNpc.ContainsKey(npc.NpcId))
                _lastCheckMinuteByNpc[npc.NpcId] = now;
        }
    }

    /// <summary>
    /// 按游戏内 30 分钟节流尝试触发每个 NPC 的空闲表现。
    /// </summary>
    public void Tick(GameTime gameTime, IEnumerable<NpcEntity> npcs)
    {
        if (gameTime == null || npcs == null)
            return;

        int now = ToAbsoluteGameMinute(gameTime);
        foreach (var npc in npcs)
        {
            if (npc == null || string.IsNullOrEmpty(npc.NpcId))
                continue;

            int last = _lastCheckMinuteByNpc.GetValueOrDefault(npc.NpcId, now);
            if (now - last < CheckIntervalGameMinutes)
                continue;

            _lastCheckMinuteByNpc[npc.NpcId] = now;
            TryStartAmbient(npc);
        }
    }

    /// <summary>
    /// 捕获 NPC 当前视觉上下文，用于玩家搭话时传给后端。
    /// </summary>
    public NpcVisualContext CaptureVisualContext(NpcEntity npc, bool interruptAmbient)
    {
        if (npc == null)
            return null;

        return npc.CaptureVisualContext(interruptAmbient);
    }

    /// <summary>
    /// 取消指定 NPC 的空闲表现，用于后端行为抢占。
    /// </summary>
    public void CancelAmbient(NpcEntity npc)
    {
        npc?.CancelAmbientPresentation();
    }

    /// <summary>
    /// 在空闲槽可用时按概率选择原地表现或同区域踱步。
    /// </summary>
    private void TryStartAmbient(NpcEntity npc)
    {
        if (npc == null || !npc.IsAmbientSlotAvailable)
            return;

        if (Random.value > TriggerChance)
            return;

        var option = _options[Random.Range(0, _options.Length)];
        if (option.UsePace)
        {
            npc.TryPlayAmbientPace(option.ActionId, option.Label);
            return;
        }

        float duration = Random.Range(PoseDurationMinSec, PoseDurationMaxSec);
        npc.TryPlayAmbientPose(option.ActionId, option.Label, duration);
    }

    /// <summary>
    /// 把 GameTime 转成跨天递增的游戏分钟。
    /// </summary>
    private static int ToAbsoluteGameMinute(GameTime gameTime)
    {
        int day = Mathf.Max(1, gameTime.day);
        int hour = Mathf.Max(0, gameTime.hour);
        int minute = Mathf.Clamp(gameTime.minute, 0, 59);
        return (day - 1) * 1440 + hour * 60 + minute;
    }

    private readonly struct AmbientOption
    {
        public readonly string ActionId;
        public readonly string Label;
        public readonly bool UsePace;

        public AmbientOption(string actionId, string label, bool usePace)
        {
            ActionId = actionId;
            Label = label;
            UsePace = usePace;
        }
    }
}
