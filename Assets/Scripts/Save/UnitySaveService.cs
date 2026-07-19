using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

/// <summary>
/// 协调 Unity 主存档仓储和 Python 记忆检查点协议。
/// </summary>
public sealed class UnitySaveService : IDisposable
{
    public event Action<string, bool, string> SaveFinished;
    public event Action<GameSaveData, string> LoadFinished;
    public event Action<string, bool, string> DeleteFinished;
    public event Action<bool, string> NewGameStorageResetFinished;
    public event Action<string> OperationFailed;
    public SaveTransactionPhase TransactionPhase => _coordinator.Phase;
    public string ActiveCheckpointId => _coordinator.ActiveCheckpointId;
    public bool IsPurgingForNewGame { get; private set; }
    public string LastNewGamePurgeError { get; private set; } = string.Empty;
    public NpcScheduleSnapshotReference AcceptedScheduleSnapshotReference { get; private set; }

    private readonly WebSocketClient _webSocket;
    private readonly GameStateStore _stateStore;
    private readonly Func<GameTime> _getCurrentTime;
    private readonly IInventoryPersistence _inventoryPersistence;
    private readonly UnitySaveRepository _repository;
    private readonly SaveCoordinator _coordinator = new SaveCoordinator();
    private string _slotId;
    private string _requestId;
    private string _currentCheckpointId;
    private byte[] _pendingScreenshot;
    private string _pendingDisplayName;
    private bool _pendingIsAuto;
    private string _pendingDeleteSlot;
    private string _worldSnapshotRequestId;
    private NpcScheduleSnapshotReference _pendingScheduleSnapshotReference;

    /// <summary>
    /// 绑定协议连接、运行状态和 Unity 本地仓储。
    /// </summary>
    public UnitySaveService(
        WebSocketClient webSocket,
        GameStateStore stateStore,
        Func<GameTime> getCurrentTime,
        IInventoryPersistence inventoryPersistence)
    {
        _webSocket = webSocket ?? throw new ArgumentNullException(nameof(webSocket));
        _stateStore = stateStore ?? throw new ArgumentNullException(nameof(stateStore));
        _getCurrentTime = getCurrentTime ?? throw new ArgumentNullException(nameof(getCurrentTime));
        _inventoryPersistence = inventoryPersistence ?? throw new ArgumentNullException(nameof(inventoryPersistence));
        _repository = new UnitySaveRepository(
            Path.Combine(Application.persistentDataPath, "SaveData"),
            new SaveMigrationRegistry());
        _webSocket.Protocol.EnvelopeReceived += HandleEnvelope;
    }

    /// <summary>
    /// 开始双端保存事务，Unity 与 Python 共用新 checkpoint_id。
    /// </summary>
    public void Save(string slotId)
    {
        Save(slotId, slotId == "auto" ? BuildAutoDisplayName() : slotId, slotId == "auto", null);
    }

    /// <summary>
    /// 使用产品元数据和可选世界截图开始双端保存事务。
    /// </summary>
    public void Save(string slotId, string displayName, bool isAuto, byte[] screenshotPng)
    {
        _slotId = NormalizeSlot(slotId);
        if (isAuto && string.IsNullOrWhiteSpace(displayName))
            displayName = BuildAutoDisplayName();
        string checkpointId = $"checkpoint_{Guid.NewGuid():N}";
        string saveId = $"save_{_slotId}";
        _requestId = $"req_{Guid.NewGuid():N}";
        _coordinator.BeginSave(checkpointId);
        _pendingDisplayName = displayName;
        _pendingIsAuto = isAuto;
        _pendingScreenshot = screenshotPng;
        var data = _stateStore.CreateSaveData(
            _slotId,
            saveId,
            checkpointId,
            _getCurrentTime(),
            _inventoryPersistence.CaptureInventory());
        _repository.Prepare(
            data,
            string.Empty,
            1,
            _pendingDisplayName,
            _pendingIsAuto,
            _pendingScreenshot);
        _coordinator.WaitForMemory();
        Send("memory_checkpoint_prepare", new JObject
        {
            ["slot_id"] = _slotId,
            ["checkpoint_id"] = checkpointId,
        });
    }

    /// <summary>
    /// 读取 Unity manifest 后请求 Python 加载同一记忆检查点。
    /// </summary>
    public void Load(string slotId)
    {
        _slotId = NormalizeSlot(slotId);
        var manifest = _repository.ReadManifest(_slotId);
        _requestId = $"req_{Guid.NewGuid():N}";
        _coordinator.BeginLoad(manifest.checkpoint_id);
        Send("memory_checkpoint_load", new JObject
        {
            ["slot_id"] = _slotId,
            ["checkpoint_id"] = manifest.checkpoint_id,
        });
    }

    /// <summary>
    /// 返回 Unity 本地主存档列表。
    /// </summary>
    public System.Collections.Generic.List<SaveInfo> ListSaves()
    {
        return _repository.ListSaves();
    }

    /// <summary>
    /// 返回符合产品命名规则的唯一默认手动存档名。
    /// </summary>
    public string CreateDefaultManualName()
    {
        return _repository.CreateDefaultManualName(DateTime.Now);
    }

    /// <summary>
    /// 生成新的无限手动槽内部 ID，与玩家显示名分离。
    /// </summary>
    public string CreateManualSlotId()
    {
        return $"manual_{Guid.NewGuid():N}";
    }

    /// <summary>
    /// 修改手动存档显示名。
    /// </summary>
    public void Rename(string slotId, string displayName)
    {
        _repository.Rename(NormalizeSlot(slotId), displayName);
    }

    /// <summary>
    /// 请求 Python 删除记忆检查点，确认后再移除 Unity 手动槽。
    /// </summary>
    public void Delete(string slotId)
    {
        _pendingDeleteSlot = NormalizeSlot(slotId);
        var manifest = _repository.ReadManifest(_pendingDeleteSlot);
        _requestId = $"req_{Guid.NewGuid():N}";
        Send("memory_checkpoint_delete", new JObject
        {
            ["slot_id"] = _pendingDeleteSlot,
            ["checkpoint_id"] = manifest.checkpoint_id,
        });
    }

    /// <summary>
    /// 新游戏进入前先请求 Python 永久清空全部记忆检查点，确认后清空 Unity 主存档。
    /// </summary>
    public void PurgeAllForNewGame()
    {
        IsPurgingForNewGame = true;
        LastNewGamePurgeError = string.Empty;
        _requestId = $"req_{Guid.NewGuid():N}";
        Send("new_game_backend_purge", new JObject());
    }

    /// <summary>
    /// 取消事件订阅，避免重建 facade 时重复处理协议消息。
    /// </summary>
    public void Dispose()
    {
        _webSocket.Protocol.EnvelopeReceived -= HandleEnvelope;
    }

    /// <summary>
    /// 根据记忆检查点响应推进保存或加载事务。
    /// </summary>
    private void HandleEnvelope(ProtocolEnvelope envelope)
    {
        if (envelope.type == "hello_ack")
        {
            SendWorldSnapshot();
            return;
        }
        if (envelope.type == "world_snapshot_applied" && envelope.request_id == _worldSnapshotRequestId)
        {
            AcceptedScheduleSnapshotReference = _pendingScheduleSnapshotReference;
            _pendingScheduleSnapshotReference = null;
            _worldSnapshotRequestId = null;
            return;
        }
        if (envelope.request_id != _requestId) return;
        try
        {
            if (envelope.type == "memory_checkpoint_prepared")
            {
                JToken memoryManifest = envelope.payload?["manifest"];
                string manifestJson = memoryManifest?.ToString(Formatting.None) ?? "{}";
                int memorySchemaVersion = memoryManifest?["memory_schema_version"]?.Value<int>() ?? 1;
                _repository.AttachMemoryManifest(
                    _slotId,
                    _coordinator.ActiveCheckpointId,
                    ComputeSha256(manifestJson),
                    memorySchemaVersion);
                _coordinator.BeginCommit();
                Send("memory_checkpoint_commit", new JObject
                {
                    ["slot_id"] = _slotId,
                    ["checkpoint_id"] = _coordinator.ActiveCheckpointId,
                });
                return;
            }
            if (envelope.type == "memory_checkpoint_committed")
            {
                _repository.Commit(_slotId, _coordinator.ActiveCheckpointId);
                Send("memory_checkpoint_finalize", new JObject
                {
                    ["slot_id"] = _slotId,
                    ["checkpoint_id"] = _coordinator.ActiveCheckpointId,
                });
                return;
            }
            if (envelope.type == "memory_checkpoint_finalized")
            {
                string checkpointId = _coordinator.ActiveCheckpointId;
                _repository.FinalizeCommit(_slotId, checkpointId);
                _currentCheckpointId = checkpointId;
                _coordinator.Complete();
                SaveFinished?.Invoke(_slotId, true, checkpointId);
                return;
            }
            if (envelope.type == "memory_checkpoint_loaded")
            {
                var data = _repository.Load(_slotId, _coordinator.ActiveCheckpointId);
                _coordinator.BeginApplyWorld();
                _stateStore.ApplySaveData(data);
                _inventoryPersistence.RestoreInventory(data.player?.inventory);
                string checkpointId = _coordinator.ActiveCheckpointId;
                _currentCheckpointId = checkpointId;
                SendWorldSnapshot();
                _coordinator.Complete();
                LoadFinished?.Invoke(data, checkpointId);
                return;
            }
            if (envelope.type == "memory_checkpoint_deleted")
            {
                string deletedSlot = _pendingDeleteSlot;
                _repository.Delete(deletedSlot);
                _pendingDeleteSlot = null;
                DeleteFinished?.Invoke(deletedSlot, true, string.Empty);
                return;
            }
            if (envelope.type == "new_game_backend_purged" || envelope.type == "memory_checkpoints_purged_all")
            {
                try
                {
                    _repository.PurgeAll();
                    _currentCheckpointId = null;
                    IsPurgingForNewGame = false;
                    NewGameStorageResetFinished?.Invoke(true, string.Empty);
                }
                catch (Exception error)
                {
                    IsPurgingForNewGame = false;
                    LastNewGamePurgeError = error.Message;
                    NewGameStorageResetFinished?.Invoke(false, error.Message);
                }
                return;
            }
            if (envelope.type.EndsWith("_failed", StringComparison.Ordinal))
            {
                string reason = envelope.payload?["reason"]?.ToString() ?? envelope.type;
                if (envelope.type == "memory_checkpoint_delete_failed")
                {
                    string failedSlot = _pendingDeleteSlot;
                    _pendingDeleteSlot = null;
                    DeleteFinished?.Invoke(failedSlot, false, reason);
                }
                else if (envelope.type == "new_game_backend_purge_failed" || envelope.type == "memory_checkpoints_purge_all_failed")
                {
                    IsPurgingForNewGame = false;
                    LastNewGamePurgeError = reason;
                    NewGameStorageResetFinished?.Invoke(false, reason);
                }
                else
                {
                    Abort(reason);
                }
            }
        }
        catch (Exception error)
        {
            Abort(error.Message);
        }
    }

    /// <summary>
    /// 清理本地临时存档并通知 Python 中止对应检查点。
    /// </summary>
    private void Abort(string reason)
    {
        SaveTransactionPhase failedPhase = _coordinator.Phase;
        string checkpointId = _coordinator.ActiveCheckpointId;
        _coordinator.BeginAbort();
        if (!string.IsNullOrEmpty(checkpointId))
        {
            _repository.Abort(_slotId, checkpointId);
            Send("memory_checkpoint_abort", new JObject
            {
                ["slot_id"] = _slotId,
                ["checkpoint_id"] = checkpointId,
            });
        }
        _coordinator.Complete();
        if (failedPhase == SaveTransactionPhase.LoadingMemory || failedPhase == SaveTransactionPhase.ApplyingWorld)
            OperationFailed?.Invoke(reason);
        else
            SaveFinished?.Invoke(_slotId, false, reason);
    }

    /// <summary>
    /// 通过 ProtocolClient 发送版本化存档消息。
    /// </summary>
    private void Send(string type, JObject payload)
    {
        _webSocket.Send(_webSocket.Protocol.CreateEnvelope(type, _requestId, payload));
    }

    /// <summary>
    /// 在握手或读档后向 Python 推送 Unity 权威世界事实。
    /// </summary>
    private void SendWorldSnapshot()
    {
        GameTime currentTime = _getCurrentTime();
        if (currentTime == null) return;
        string checkpointId = _currentCheckpointId ?? string.Empty;
        var data = _stateStore.CreateSaveData(
            "runtime",
            "runtime",
            checkpointId,
            currentTime,
            _inventoryPersistence.CaptureInventory());
        var payload = JObject.FromObject(data);
        payload.Remove("schema_version");
        payload.Remove("save_id");
        payload.Remove("slot_id");
        payload["checkpoint_id"] = checkpointId;
        // 日程物理字段只来自 Unity 当前运行时存档；未知动态事实不伪造可用性。
        string snapshotId = $"world_{currentTime.day}_{currentTime.hour}_{currentTime.minute}_{Guid.NewGuid():N}";
        _pendingScheduleSnapshotReference = new NpcScheduleSnapshotReference
        {
            snapshot_id = snapshotId,
            time_revision = data.world_revision,
            world_revision = data.world_revision,
            game_day = currentTime.day,
        };
        payload["npc_schedule_physical_state"] = new JObject
        {
            ["snapshot_id"] = snapshotId,
            ["time_revision"] = data.world_revision,
            ["world_revision"] = data.world_revision,
            ["game_time"] = JObject.FromObject(currentTime),
            ["weather"] = data.weather ?? "unknown",
            ["locations"] = new JArray(),
            ["spots"] = new JArray(),
            ["npcs"] = payload["npcs"] ?? new JArray()
        };
        _worldSnapshotRequestId = $"req_{Guid.NewGuid():N}";
        _webSocket.Send(_webSocket.Protocol.CreateEnvelope(
            "world_snapshot",
            _worldSnapshotRequestId,
            payload));
    }

    /// <summary>
    /// 将空槽位归一为默认槽，并保持跨端稳定小写格式。
    /// </summary>
    private static string NormalizeSlot(string slotId) => string.IsNullOrWhiteSpace(slotId) ? "1" : slotId.Trim().ToLowerInvariant();

    /// <summary>
    /// 构造自动存档玩家显示名，保留当前游戏日和醒来时间。
    /// </summary>
    private string BuildAutoDisplayName()
    {
        GameTime time = _getCurrentTime();
        string inheritedName = ListSaves().Find(save => !save.is_auto)?.display_name ?? "无存档";
        return $"第{time?.day ?? 1}天 [上午 6:00] [{inheritedName}]";
    }

    /// <summary>
    /// 计算记忆 manifest 规范 JSON 的 SHA-256 摘要。
    /// </summary>
    private static string ComputeSha256(string value)
    {
        using var sha256 = SHA256.Create();
        byte[] digest = sha256.ComputeHash(Encoding.UTF8.GetBytes(value ?? string.Empty));
        return BitConverter.ToString(digest).Replace("-", string.Empty).ToLowerInvariant();
    }
}
