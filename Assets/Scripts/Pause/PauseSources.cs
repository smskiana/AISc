/// <summary>
/// 维护跨 UI 和流程模块复用的稳定暂停来源 ID。
/// </summary>
public static class PauseSources
{
    public const string Dialogue = "dialogue";
    public const string Inventory = "inventory";
    public const string PauseMenu = "pause_menu";
    public const string BlockingMessage = "blocking_message";
    public const string LoadingOverlay = "loading_overlay";
    public const string SleepFlow = "sleep_flow";
    public const string SaveManagement = "save_management";
    public const string DiagnosticsTest = "diagnostics_test";
}
