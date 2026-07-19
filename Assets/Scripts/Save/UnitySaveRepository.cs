using System;
using System.IO;
using System.Security.Cryptography;
using Newtonsoft.Json;
using System.Collections.Generic;

/// <summary>
/// 使用临时目录、SHA-256 和原子替换管理 Unity 主存档。
/// </summary>
public class UnitySaveRepository
{
    private const int CurrentSchemaVersion = 3;
    private readonly string _rootPath;
    private readonly SaveMigrationRegistry _migrations;

    /// <summary>
    /// 绑定 Unity 本地存档根目录和迁移注册表。
    /// </summary>
    public UnitySaveRepository(string rootPath, SaveMigrationRegistry migrations)
    {
        _rootPath = rootPath ?? throw new ArgumentNullException(nameof(rootPath));
        _migrations = migrations ?? throw new ArgumentNullException(nameof(migrations));
        Directory.CreateDirectory(_rootPath);
    }

    /// <summary>
    /// 将主存档写入临时槽位，并返回待提交 manifest。
    /// </summary>
    public SaveManifest Prepare(
        GameSaveData data,
        string memoryManifestSha256,
        int memorySchemaVersion,
        string displayName,
        bool isAuto,
        byte[] screenshotPng)
    {
        ValidateSaveData(data);
        string pendingPath = GetPendingPath(data.slot_id, data.checkpoint_id);
        if (Directory.Exists(pendingPath)) Directory.Delete(pendingPath, true);
        Directory.CreateDirectory(pendingPath);

        string worldPath = Path.Combine(pendingPath, "world.json");
        File.WriteAllText(worldPath, JsonConvert.SerializeObject(data, Formatting.Indented));
        string screenshotFile = string.Empty;
        if (screenshotPng != null && screenshotPng.Length > 0)
        {
            screenshotFile = "screenshot.png";
            File.WriteAllBytes(Path.Combine(pendingPath, screenshotFile), screenshotPng);
        }
        var manifest = new SaveManifest
        {
            save_id = data.save_id,
            slot_id = data.slot_id,
            checkpoint_id = data.checkpoint_id,
            created_at = data.created_at,
            game_build = UnityEngine.Application.version,
            unity_schema_version = data.schema_version,
            memory_schema_version = memorySchemaVersion,
            world_sha256 = ComputeSha256(worldPath),
            memory_manifest_sha256 = memoryManifestSha256 ?? string.Empty,
            display_name = string.IsNullOrWhiteSpace(displayName) ? data.slot_id : displayName.Trim(),
            is_auto = isAuto,
            screenshot_file = screenshotFile,
        };
        File.WriteAllText(Path.Combine(pendingPath, "manifest.json"), JsonConvert.SerializeObject(manifest, Formatting.Indented));
        return manifest;
    }

    /// <summary>
    /// 原子提交临时主存档，并保留失败回滚能力。
    /// </summary>
    public void Commit(string slotId, string checkpointId)
    {
        string pendingPath = GetPendingPath(slotId, checkpointId);
        ValidateDirectory(pendingPath, checkpointId);
        string finalPath = GetFinalPath(slotId);
        string backupPath = finalPath + ".previous";
        if (Directory.Exists(backupPath)) Directory.Delete(backupPath, true);
        if (Directory.Exists(finalPath)) Directory.Move(finalPath, backupPath);
        try
        {
            Directory.Move(pendingPath, finalPath);
        }
        catch
        {
            if (!Directory.Exists(finalPath) && Directory.Exists(backupPath))
                Directory.Move(backupPath, finalPath);
            throw;
        }
    }

    /// <summary>
    /// 在双方 prepare 完成后写入 Python 记忆 manifest 摘要。
    /// </summary>
    public void AttachMemoryManifest(string slotId, string checkpointId, string memoryManifestSha256, int memorySchemaVersion)
    {
        string pendingPath = GetPendingPath(slotId, checkpointId);
        string manifestPath = Path.Combine(pendingPath, "manifest.json");
        var manifest = JsonConvert.DeserializeObject<SaveManifest>(File.ReadAllText(manifestPath));
        if (manifest == null || manifest.checkpoint_id != checkpointId) throw new InvalidDataException("checkpoint_mismatch");
        manifest.memory_manifest_sha256 = memoryManifestSha256 ?? string.Empty;
        manifest.memory_schema_version = memorySchemaVersion;
        File.WriteAllText(manifestPath, JsonConvert.SerializeObject(manifest, Formatting.Indented));
    }

    /// <summary>
    /// 清理未提交主存档，不影响正式槽位。
    /// </summary>
    public void Abort(string slotId, string checkpointId)
    {
        string pendingPath = GetPendingPath(slotId, checkpointId);
        if (Directory.Exists(pendingPath)) Directory.Delete(pendingPath, true);
        string finalPath = GetFinalPath(slotId);
        string backupPath = finalPath + ".previous";
        if (Directory.Exists(finalPath))
        {
            var manifest = JsonConvert.DeserializeObject<SaveManifest>(
                File.ReadAllText(Path.Combine(finalPath, "manifest.json")));
            if (manifest != null && manifest.checkpoint_id == checkpointId)
            {
                Directory.Delete(finalPath, true);
                if (Directory.Exists(backupPath)) Directory.Move(backupPath, finalPath);
            }
        }
    }

    /// <summary>
    /// 确认双端提交成功后删除上一 Unity 主存档备份。
    /// </summary>
    public void FinalizeCommit(string slotId, string checkpointId)
    {
        ValidateDirectory(GetFinalPath(slotId), checkpointId);
        string backupPath = GetFinalPath(slotId) + ".previous";
        if (Directory.Exists(backupPath)) Directory.Delete(backupPath, true);
    }

    /// <summary>
    /// 校验并加载正式主存档，再执行版本迁移。
    /// </summary>
    public GameSaveData Load(string slotId, string checkpointId)
    {
        string finalPath = GetFinalPath(slotId);
        ValidateDirectory(finalPath, checkpointId);
        string json = File.ReadAllText(Path.Combine(finalPath, "world.json"));
        var data = JsonConvert.DeserializeObject<GameSaveData>(json);
        return _migrations.Migrate(data, CurrentSchemaVersion);
    }

    /// <summary>
    /// 返回正式槽位的 manifest，供协调器校验记忆检查点。
    /// </summary>
    public SaveManifest ReadManifest(string slotId)
    {
        string path = Path.Combine(GetFinalPath(slotId), "manifest.json");
        return JsonConvert.DeserializeObject<SaveManifest>(File.ReadAllText(path));
    }

    /// <summary>
    /// 从 Unity 本地 manifest 列出可加载存档，不依赖 Python 完整存档目录。
    /// </summary>
    public List<SaveInfo> ListSaves()
    {
        var result = new List<SaveInfo>();
        foreach (string directory in Directory.GetDirectories(_rootPath, "slot_*"))
        {
            string manifestPath = Path.Combine(directory, "manifest.json");
            string worldPath = Path.Combine(directory, "world.json");
            if (!File.Exists(manifestPath) || !File.Exists(worldPath)) continue;
            try
            {
                var manifest = JsonConvert.DeserializeObject<SaveManifest>(File.ReadAllText(manifestPath));
                var data = JsonConvert.DeserializeObject<GameSaveData>(File.ReadAllText(worldPath));
                if (manifest == null || data == null || manifest.world_sha256 != ComputeSha256(worldPath)) continue;
                result.Add(new SaveInfo
                {
                    slot = manifest.slot_id,
                    game_day = data.game_time?.day ?? 1,
                    saved_at = manifest.created_at,
                    version = manifest.unity_schema_version.ToString(),
                    display_name = string.IsNullOrWhiteSpace(manifest.display_name) ? manifest.slot_id : manifest.display_name,
                    is_auto = manifest.is_auto || manifest.slot_id == "auto",
                    screenshot_path = string.IsNullOrWhiteSpace(manifest.screenshot_file)
                        ? string.Empty
                        : Path.Combine(directory, manifest.screenshot_file),
                });
            }
            catch (Exception)
            {
                // 损坏槽位不进入可加载列表，具体错误在显式加载时返回。
            }
        }
        result.Sort((left, right) =>
        {
            if (left.is_auto != right.is_auto) return left.is_auto ? -1 : 1;
            return string.Compare(right.saved_at, left.saved_at, StringComparison.Ordinal);
        });
        return result;
    }

    /// <summary>
    /// 修改手动存档显示名，不改变内部槽位和世界摘要。
    /// </summary>
    public void Rename(string slotId, string displayName)
    {
        if (slotId == "auto") throw new InvalidOperationException("自动存档不能重命名");
        if (string.IsNullOrWhiteSpace(displayName)) throw new ArgumentException("存档名不能为空", nameof(displayName));
        if (ListSaves().Exists(save => save.slot != slotId
            && string.Equals(save.display_name, displayName.Trim(), StringComparison.Ordinal)))
            throw new InvalidOperationException("手动存档名称不得重复");

        string manifestPath = Path.Combine(GetFinalPath(slotId), "manifest.json");
        var manifest = JsonConvert.DeserializeObject<SaveManifest>(File.ReadAllText(manifestPath));
        if (manifest == null) throw new InvalidDataException("存档 manifest 损坏");
        manifest.display_name = displayName.Trim();
        File.WriteAllText(manifestPath, JsonConvert.SerializeObject(manifest, Formatting.Indented));
    }

    /// <summary>
    /// 删除指定手动槽并返回其 checkpoint ID，供 Python 同步清理。
    /// </summary>
    public string Delete(string slotId)
    {
        if (slotId == "auto") throw new InvalidOperationException("自动存档不能删除");
        var manifest = ReadManifest(slotId) ?? throw new InvalidDataException("存档 manifest 损坏");
        string finalPath = GetFinalPath(slotId);
        if (Directory.Exists(finalPath)) Directory.Delete(finalPath, true);
        string backupPath = finalPath + ".previous";
        if (Directory.Exists(backupPath)) Directory.Delete(backupPath, true);
        return manifest.checkpoint_id;
    }

    /// <summary>
    /// 永久删除全部正式、备份和待提交 Unity 主存档，并重建空仓储目录。
    /// </summary>
    public void PurgeAll()
    {
        if (Directory.Exists(_rootPath)) Directory.Delete(_rootPath, true);
        Directory.CreateDirectory(_rootPath);
    }

    /// <summary>
    /// 生成现实日期加三位序号的唯一默认手动存档名。
    /// </summary>
    public string CreateDefaultManualName(DateTime localDate)
    {
        string prefix = $"手动存档：{localDate:yyyy-MM-dd}-";
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (var save in ListSaves())
            names.Add(save.display_name ?? string.Empty);
        for (int index = 1; index <= 999; index++)
        {
            string candidate = $"{prefix}[{index:000}]";
            if (!names.Contains(candidate)) return candidate;
        }
        throw new InvalidOperationException("当天手动存档编号已用尽");
    }

    /// <summary>
    /// 校验存档必需的稳定标识符和 schema。
    /// </summary>
    private static void ValidateSaveData(GameSaveData data)
    {
        if (data == null) throw new ArgumentNullException(nameof(data));
        if (data.schema_version != CurrentSchemaVersion) throw new InvalidOperationException("只能写入当前 Unity 存档 schema");
        ValidateId(data.slot_id, nameof(data.slot_id));
        ValidateId(data.save_id, nameof(data.save_id));
        ValidateId(data.checkpoint_id, nameof(data.checkpoint_id));
    }

    /// <summary>
    /// 校验目录中的 checkpoint 身份与世界文件摘要。
    /// </summary>
    private static void ValidateDirectory(string path, string checkpointId)
    {
        string manifestPath = Path.Combine(path, "manifest.json");
        string worldPath = Path.Combine(path, "world.json");
        if (!File.Exists(manifestPath) || !File.Exists(worldPath)) throw new FileNotFoundException("主存档不完整");
        var manifest = JsonConvert.DeserializeObject<SaveManifest>(File.ReadAllText(manifestPath));
        if (manifest == null || manifest.checkpoint_id != checkpointId) throw new InvalidDataException("checkpoint_mismatch");
        if (manifest.world_sha256 != ComputeSha256(worldPath)) throw new InvalidDataException("world_save_corrupted");
    }

    /// <summary>
    /// 校验跨端 ID 只使用小写英文、数字和下划线。
    /// </summary>
    private static void ValidateId(string value, string fieldName)
    {
        if (string.IsNullOrWhiteSpace(value)) throw new ArgumentException($"{fieldName} 不能为空");
        foreach (char character in value)
        {
            if (!(character >= 'a' && character <= 'z') && !(character >= '0' && character <= '9') && character != '_')
                throw new ArgumentException($"{fieldName} 格式非法");
        }
    }

    /// <summary>
    /// 计算文件 SHA-256 小写十六进制摘要。
    /// </summary>
    private static string ComputeSha256(string path)
    {
        using var stream = File.OpenRead(path);
        using var sha256 = SHA256.Create();
        return BitConverter.ToString(sha256.ComputeHash(stream)).Replace("-", string.Empty).ToLowerInvariant();
    }

    private string GetPendingPath(string slotId, string checkpointId) => Path.Combine(_rootPath, ".pending", $"slot_{slotId}_{checkpointId}");
    private string GetFinalPath(string slotId) => Path.Combine(_rootPath, $"slot_{slotId}");
}
