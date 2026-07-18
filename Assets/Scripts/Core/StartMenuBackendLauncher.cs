using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;
using Debug = UnityEngine.Debug;

/// <summary>
/// 开始界面后端辅助：负责健康检查和本机 Python 进程拉起。
/// </summary>
public static class StartMenuBackendLauncher
{
    private const string OwnedBackendPidKey = "start_menu_owned_backend_pid";
    private const string OwnedBackendStartTicksKey = "start_menu_owned_backend_start_ticks";

    private static Process _ownedBackendProcess;

    /// <summary>
    /// 使用 REST health 检查判断后端是否在线。
    /// </summary>
    public static IEnumerator CheckHealth(string healthUrl, Action<bool> onDone)
    {
        using var request = UnityWebRequest.Get(healthUrl);
        yield return request.SendWebRequest();
        onDone?.Invoke(request.result == UnityWebRequest.Result.Success);
    }

    /// <summary>
    /// 在超时窗口内轮询 health，等待后端真正就绪。
    /// </summary>
    public static IEnumerator WaitForHealth(string healthUrl, float timeoutSeconds, Action<bool> onDone)
    {
        float deadline = Time.realtimeSinceStartup + timeoutSeconds;
        while (Time.realtimeSinceStartup < deadline)
        {
            bool isHealthy = false;
            yield return CheckHealth(healthUrl, result => isHealthy = result);
            if (isHealthy)
            {
                onDone?.Invoke(true);
                yield break;
            }

            yield return new WaitForSecondsRealtime(0.8f);
        }

        onDone?.Invoke(false);
    }

    /// <summary>
    /// 尝试在本机启动 Python 后端。
    /// </summary>
    public static bool TryLaunchBackend()
    {
        if (IsOwnedBackendRunning())
        {
            Debug.Log($"[StartMenu] 已有前端托管的后端进程在运行: PID={_ownedBackendProcess.Id}");
            return true;
        }

        string projectRoot = Directory.GetParent(Application.dataPath)?.FullName;
        if (string.IsNullOrEmpty(projectRoot))
            return false;

        string backendDir = Path.Combine(projectRoot, "backend");
        string runScript = Path.Combine(backendDir, "run.py");
        if (!File.Exists(runScript))
            return false;

        foreach (var candidate in GetPythonLaunchCandidates(runScript))
        {
            try
            {
                var process = Process.Start(candidate);
                if (process != null)
                {
                    TrackOwnedBackendProcess(process);
                    Debug.Log($"[StartMenu] 已尝试启动后端: {candidate.FileName} {candidate.Arguments} PID={process.Id}");
                    return true;
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[StartMenu] 启动后端失败: {candidate.FileName} {candidate.Arguments} => {e.Message}");
            }
        }

        return false;
    }

    /// <summary>
    /// 关闭由本次 Unity 前端拉起的后端进程；外部已有后端不会被接管或关闭。
    /// </summary>
    public static void ShutdownOwnedBackend()
    {
        var process = ResolveOwnedBackendProcess();
        _ownedBackendProcess = null;
        if (process == null)
        {
            ClearPersistedOwnedBackendProcess();
            return;
        }

        try
        {
            if (!process.HasExited)
            {
                Debug.Log($"[StartMenu] 正在关闭前端托管的后端进程: PID={process.Id}");
                process.Kill();
                process.WaitForExit(2000);
            }
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[StartMenu] 关闭后端进程失败: {e.Message}");
        }
        finally
        {
            ClearPersistedOwnedBackendProcess();
            process.Dispose();
        }
    }

    /// <summary>
    /// 判断当前记录的 owned 后端进程是否仍在运行。
    /// </summary>
    private static bool IsOwnedBackendRunning()
    {
        if (_ownedBackendProcess == null && !TryLoadPersistedOwnedBackendProcess(out _ownedBackendProcess))
            return false;

        try
        {
            return !_ownedBackendProcess.HasExited;
        }
        catch
        {
            _ownedBackendProcess = null;
            return false;
        }
    }

    /// <summary>
    /// 保存前端启动的后端进程引用，并在自然退出后释放对象。
    /// </summary>
    private static void TrackOwnedBackendProcess(Process process)
    {
        _ownedBackendProcess = process;
        PersistOwnedBackendProcess(process);
        try
        {
            process.EnableRaisingEvents = true;
            process.Exited += (_, _) =>
            {
                if (_ownedBackendProcess == process)
                    _ownedBackendProcess = null;

                ClearPersistedOwnedBackendProcess();
                process.Dispose();
            };
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[StartMenu] 无法监听后端进程退出: {e.Message}");
        }
    }

    /// <summary>
    /// 从静态引用或持久化 PID 找回本轮前端拥有的后端进程。
    /// </summary>
    private static Process ResolveOwnedBackendProcess()
    {
        if (_ownedBackendProcess != null)
            return _ownedBackendProcess;

        return TryLoadPersistedOwnedBackendProcess(out var process) ? process : null;
    }

    /// <summary>
    /// 持久化 owned 后端 PID 和启动时间，覆盖 Unity 域重载导致的静态引用丢失。
    /// </summary>
    private static void PersistOwnedBackendProcess(Process process)
    {
        try
        {
            PlayerPrefs.SetInt(OwnedBackendPidKey, process.Id);
            PlayerPrefs.SetString(OwnedBackendStartTicksKey, process.StartTime.Ticks.ToString());
            PlayerPrefs.Save();
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[StartMenu] 无法记录后端进程信息: {e.Message}");
        }
    }

    /// <summary>
    /// 读取并校验持久化进程，只有 PID 与启动时间都匹配时才视为 owned 后端。
    /// </summary>
    private static bool TryLoadPersistedOwnedBackendProcess(out Process process)
    {
        process = null;
        int pid = PlayerPrefs.GetInt(OwnedBackendPidKey, 0);
        string ticksText = PlayerPrefs.GetString(OwnedBackendStartTicksKey, string.Empty);
        if (pid <= 0 || !long.TryParse(ticksText, out long expectedTicks))
            return false;

        try
        {
            var candidate = Process.GetProcessById(pid);
            if (candidate.HasExited || candidate.StartTime.Ticks != expectedTicks)
            {
                candidate.Dispose();
                ClearPersistedOwnedBackendProcess();
                return false;
            }

            process = candidate;
            return true;
        }
        catch
        {
            ClearPersistedOwnedBackendProcess();
            return false;
        }
    }

    /// <summary>
    /// 清除 owned 后端进程记录，避免后续误判旧 PID。
    /// </summary>
    private static void ClearPersistedOwnedBackendProcess()
    {
        PlayerPrefs.DeleteKey(OwnedBackendPidKey);
        PlayerPrefs.DeleteKey(OwnedBackendStartTicksKey);
        PlayerPrefs.Save();
    }

    /// <summary>
    /// 生成一组 Python 启动候选命令，依次尝试。
    /// </summary>
    private static IEnumerable<ProcessStartInfo> GetPythonLaunchCandidates(string runScriptPath)
    {
        string backendDir = Path.GetDirectoryName(runScriptPath) ?? string.Empty;
        string quotedScript = $"\"{runScriptPath}\"";

        yield return new ProcessStartInfo
        {
            FileName = "python",
            Arguments = quotedScript,
            WorkingDirectory = backendDir,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
        };

        yield return new ProcessStartInfo
        {
            FileName = "py",
            Arguments = $"-3 {quotedScript}",
            WorkingDirectory = backendDir,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
        };
    }
}
