using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 让明确挂载到同一层级的粒子和 Animator 使用独立 FX 时间域。
/// </summary>
public sealed class PauseFxAdapter : MonoBehaviour
{
    public static int RegisteredFxCount { get; private set; }
    public static int DomainPausedFxCount { get; private set; }

    [SerializeField] private ParticleSystem[] _particleSystems = System.Array.Empty<ParticleSystem>();
    [SerializeField] private Animator[] _animators = System.Array.Empty<Animator>();

    private readonly List<ParticleSystem> _pausedParticles = new List<ParticleSystem>();
    private readonly List<Animator> _pausedAnimators = new List<Animator>();
    private PauseController _pauseController;
    private bool _isDomainPaused;

    /// <summary>
    /// 注册明确连线的 FX，并将其更新模式切换为非缩放时间。
    /// </summary>
    private void Awake()
    {
        RegisteredFxCount += _particleSystems.Length + _animators.Length;
        foreach (ParticleSystem particleSystem in _particleSystems)
        {
            if (particleSystem == null)
                continue;
            ParticleSystem.MainModule main = particleSystem.main;
            main.useUnscaledTime = true;
        }

        foreach (Animator animator in _animators)
        {
            if (animator != null)
                animator.updateMode = AnimatorUpdateMode.UnscaledTime;
        }
    }

    /// <summary>
    /// 订阅 FX 域并立即应用当前状态。
    /// </summary>
    private void OnEnable()
    {
        BindController();
    }

    /// <summary>
    /// 在所有 Awake 完成后补绑控制器，避免依赖同场景脚本初始化顺序。
    /// </summary>
    private void Start()
    {
        BindController();
    }

    /// <summary>
    /// 幂等绑定全局暂停控制器并立即应用 FX 域状态。
    /// </summary>
    private void BindController()
    {
        PauseController controller = PauseController.Instance;
        if (controller == null || controller == _pauseController)
            return;
        if (_pauseController != null)
            _pauseController.DomainPauseChanged -= HandleDomainPauseChanged;
        _pauseController = controller;
        _pauseController.DomainPauseChanged += HandleDomainPauseChanged;
        ApplyPausedState(_pauseController.IsDomainPaused(PauseTimeDomain.FX));
    }

    /// <summary>
    /// 只响应包含 FX 的域变化。
    /// </summary>
    private void HandleDomainPauseChanged(PauseTimeDomain changedDomains)
    {
        if ((changedDomains & PauseTimeDomain.FX) != 0)
            ApplyPausedState(_pauseController.IsDomainPaused(PauseTimeDomain.FX));
    }

    /// <summary>
    /// 暂停正在运行的 FX，并只恢复由本适配器暂停的实例。
    /// </summary>
    private void ApplyPausedState(bool paused)
    {
        if (_isDomainPaused == paused)
            return;

        _isDomainPaused = paused;
        if (paused)
        {
            foreach (ParticleSystem particleSystem in _particleSystems)
            {
                if (particleSystem != null && particleSystem.isPlaying)
                {
                    particleSystem.Pause(true);
                    _pausedParticles.Add(particleSystem);
                }
            }
            foreach (Animator animator in _animators)
            {
                if (animator != null && animator.enabled)
                {
                    animator.enabled = false;
                    _pausedAnimators.Add(animator);
                }
            }
            DomainPausedFxCount += _pausedParticles.Count + _pausedAnimators.Count;
            return;
        }

        DomainPausedFxCount -= _pausedParticles.Count + _pausedAnimators.Count;
        foreach (ParticleSystem particleSystem in _pausedParticles)
        {
            if (particleSystem != null)
                particleSystem.Play(true);
        }
        foreach (Animator animator in _pausedAnimators)
        {
            if (animator != null)
                animator.enabled = true;
        }
        _pausedParticles.Clear();
        _pausedAnimators.Clear();
    }

    /// <summary>
    /// 解除订阅并清理静态诊断计数。
    /// </summary>
    private void OnDisable()
    {
        if (_pauseController != null)
            _pauseController.DomainPauseChanged -= HandleDomainPauseChanged;
        ApplyPausedState(false);
    }

    /// <summary>
    /// 从已注册 FX 总数中移除本适配器持有的引用。
    /// </summary>
    private void OnDestroy()
    {
        RegisteredFxCount -= _particleSystems.Length + _animators.Length;
    }
}
