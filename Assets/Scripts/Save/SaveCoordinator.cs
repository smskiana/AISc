using System;

/// <summary>
/// 描述跨端保存或加载事务的当前阶段。
/// </summary>
public enum SaveTransactionPhase
{
    Idle,
    PreparingUnity,
    WaitingForMemory,
    Committing,
    LoadingMemory,
    ApplyingWorld,
    Aborting,
}

/// <summary>
/// 管理 Unity 主存档与 Python 记忆检查点的事务阶段。
/// </summary>
public class SaveCoordinator
{
    public SaveTransactionPhase Phase { get; private set; } = SaveTransactionPhase.Idle;
    public string ActiveCheckpointId { get; private set; }

    /// <summary>
    /// 开始新的保存事务，拒绝覆盖进行中的事务。
    /// </summary>
    public void BeginSave(string checkpointId)
    {
        EnsureIdle();
        ActiveCheckpointId = checkpointId;
        Phase = SaveTransactionPhase.PreparingUnity;
    }

    /// <summary>
    /// 标记 Unity 临时存档完成，等待 Python 记忆检查点。
    /// </summary>
    public void WaitForMemory()
    {
        RequirePhase(SaveTransactionPhase.PreparingUnity);
        Phase = SaveTransactionPhase.WaitingForMemory;
    }

    /// <summary>
    /// 标记双方均已准备，可进入提交阶段。
    /// </summary>
    public void BeginCommit()
    {
        RequirePhase(SaveTransactionPhase.WaitingForMemory);
        Phase = SaveTransactionPhase.Committing;
    }

    /// <summary>
    /// 完成当前事务并清理临时身份。
    /// </summary>
    public void Complete()
    {
        Phase = SaveTransactionPhase.Idle;
        ActiveCheckpointId = null;
    }

    /// <summary>
    /// 进入失败清理阶段。
    /// </summary>
    public void BeginAbort()
    {
        if (Phase == SaveTransactionPhase.Idle) return;
        Phase = SaveTransactionPhase.Aborting;
    }

    /// <summary>
    /// 开始加载对应检查点的记忆数据。
    /// </summary>
    public void BeginLoad(string checkpointId)
    {
        EnsureIdle();
        ActiveCheckpointId = checkpointId;
        Phase = SaveTransactionPhase.LoadingMemory;
    }

    /// <summary>
    /// 标记记忆检查点已加载，可以应用 Unity 世界。
    /// </summary>
    public void BeginApplyWorld()
    {
        RequirePhase(SaveTransactionPhase.LoadingMemory);
        Phase = SaveTransactionPhase.ApplyingWorld;
    }

    /// <summary>
    /// 确保没有其他保存或加载事务正在执行。
    /// </summary>
    private void EnsureIdle()
    {
        if (Phase != SaveTransactionPhase.Idle) throw new InvalidOperationException("已有存档事务正在进行");
    }

    /// <summary>
    /// 校验事务只能按声明的阶段顺序推进。
    /// </summary>
    private void RequirePhase(SaveTransactionPhase expected)
    {
        if (Phase != expected) throw new InvalidOperationException($"存档事务阶段错误: expected={expected}, actual={Phase}");
    }
}
