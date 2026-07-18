using UnityEngine;

/// <summary>
/// 在玩家进入床位触发区时发起一次主动睡眠确认。
/// </summary>
public sealed class SleepBedTrigger : MonoBehaviour
{
    [SerializeField] private SleepController _sleepController;

    private bool _promptedDuringCurrentEntry;

    /// <summary>
    /// 玩家首次进入当前触发范围时请求主动睡眠。
    /// </summary>
    private void OnTriggerEnter2D(Collider2D other)
    {
        if (_promptedDuringCurrentEntry || other.GetComponent<PlayerController>() == null)
            return;
        _promptedDuringCurrentEntry = true;
        _sleepController?.RequestVoluntarySleep();
    }

    /// <summary>
    /// 玩家离开后重新允许下一次进入触发确认。
    /// </summary>
    private void OnTriggerExit2D(Collider2D other)
    {
        if (other.GetComponent<PlayerController>() != null)
            _promptedDuringCurrentEntry = false;
    }
}
