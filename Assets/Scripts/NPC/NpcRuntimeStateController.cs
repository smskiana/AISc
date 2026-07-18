using System;
using System.Collections.Generic;

/// <summary>
/// Unity 权威维护单名 NPC 的运行时状态、P0/need 推进和迟到 effect 拒绝。
/// </summary>
public sealed class NpcRuntimeStateController
{
    public string NpcId { get; private set; }
    public string Emotion { get; private set; } = "平静";
    public float Energy { get; private set; } = 80f;
    public float Sociability { get; private set; } = 50f;
    public string CurrentNeed { get; private set; } = string.Empty;
    public bool IsAsleep { get; private set; }
    public string LingeringConcern { get; private set; } = string.Empty;
    public string LastEffectOperationId { get; private set; } = string.Empty;
    public string LastEffectStatus { get; private set; } = string.Empty;
    public string LastEffectReason { get; private set; } = string.Empty;

    /// <summary>
    /// 从后端初始状态或 Unity 主存档建立权威运行时状态。
    /// </summary>
    public void Restore(NpcState state)
    {
        if (state == null)
            return;
        NpcId = state.npc_id;
        Emotion = string.IsNullOrWhiteSpace(state.emotion) ? "平静" : state.emotion;
        Energy = Clamp(state.energy, 0f, 100f);
        Sociability = Clamp(state.sociability, 0f, 100f);
        CurrentNeed = state.current_need ?? string.Empty;
    }

    /// <summary>
    /// 每个 Unity 权威分钟推进 P0 和 need，不依赖 Python 物理 tick。
    /// </summary>
    public void Tick(GameTime gameTime, string currentAction)
    {
        if (gameTime == null || IsAsleep)
            return;
        if (gameTime.hour >= 23)
        {
            IsAsleep = true;
            CurrentNeed = "sleep";
            return;
        }
        Energy = Clamp(Energy + EnergyDeltaForAction(currentAction), 0f, 100f);
        if (Energy < 18f && string.IsNullOrEmpty(CurrentNeed))
            CurrentNeed = "tired";
        else if (CurrentNeed == "tired" && Energy > 55f && IsRecoveryAction(currentAction))
            CurrentNeed = string.Empty;
    }

    /// <summary>
    /// 校验 base revision 后应用 Python 计算的状态 effect。
    /// </summary>
    public bool TryApplyEffect(NpcStateEffectMsg effect, long currentWorldRevision)
    {
        if (effect == null || effect.npc_id != NpcId)
            return Reject(effect, "effect_npc_mismatch");
        LastEffectOperationId = effect.operation_id ?? string.Empty;
        if (effect.base_world_revision != 0 && effect.base_world_revision != currentWorldRevision)
            return Reject(effect, "stale_base_world_revision");

        if (effect.field_deltas != null)
        {
            Energy = Clamp(Energy + effect.field_deltas.energy, 0f, 100f);
            Sociability = Clamp(Sociability + effect.field_deltas.sociability, 0f, 100f);
        }
        if (effect.field_values != null)
        {
            if (!string.IsNullOrWhiteSpace(effect.field_values.emotion))
                Emotion = effect.field_values.emotion;
            if (effect.field_values.current_need != null)
                CurrentNeed = effect.field_values.current_need;
            if (effect.field_values.lingering_concern != null)
                LingeringConcern = effect.field_values.lingering_concern;
            IsAsleep = effect.field_values.is_asleep;
        }
        LastEffectStatus = "applied";
        LastEffectReason = effect.reason ?? string.Empty;
        return true;
    }

    /// <summary>
    /// 把运行时权威状态写回共享 NpcState 缓存，供存档、对话和诊断读取。
    /// </summary>
    public void CopyTo(NpcState state)
    {
        if (state == null)
            return;
        state.emotion = Emotion;
        state.energy = Energy;
        state.sociability = Sociability;
        state.current_need = CurrentNeed;
    }

    private bool Reject(NpcStateEffectMsg effect, string reason)
    {
        LastEffectOperationId = effect?.operation_id ?? string.Empty;
        LastEffectStatus = "rejected";
        LastEffectReason = reason;
        return false;
    }

    private static bool IsRecoveryAction(string action)
    {
        return action == "rest" || action == "eat" || action == "sleep" || action == "drink";
    }

    private static float EnergyDeltaForAction(string action)
    {
        if (action == "sleep") return 8f;
        if (action == "rest") return 2f;
        if (action == "eat" || action == "drink") return 1f;
        if (action == "patrol" || action == "work_open" || action == "work_close") return -1.5f;
        return -0.2f;
    }

    private static float Clamp(float value, float min, float max)
    {
        return Math.Max(min, Math.Min(max, value));
    }
}

/// <summary>
/// 暴露 Unity 权威 NPC 运行时状态的诊断快照。
/// </summary>
[Serializable]
public sealed class NpcRuntimeStateDiagnosticSnapshot
{
    public string npc_id;
    public string emotion;
    public float energy;
    public float sociability;
    public string current_need;
    public bool is_asleep;
    public string lingering_concern;
    public string last_effect_operation_id;
    public string last_effect_status;
    public string last_effect_reason;
}
