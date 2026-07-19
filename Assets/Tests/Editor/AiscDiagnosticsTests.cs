using NUnit.Framework;
using Newtonsoft.Json.Linq;
using UnityEngine;

/// <summary>
/// 验证 AISc 诊断模块在非 PlayMode 环境下仍返回稳定结构。
/// </summary>
public sealed class AiscDiagnosticsTests
{
    /// <summary>
    /// EditMode 健康报告应明确要求进入 PlayMode，而不是抛出异常。
    /// </summary>
    [Test]
    public void HealthReportOutsidePlayModeReturnsStableFailure()
    {
        DiagnosticHealthReport report = AiscDiagnostics.GetHealthReport();

        Assert.AreEqual("failed", report.status);
        Assert.IsTrue(report.issues.Exists(issue => issue.code == "play_mode_required"));
    }

    /// <summary>
    /// 没有运行中 GameManager 时协议轨迹应返回空集合。
    /// </summary>
    [Test]
    public void ProtocolTraceWithoutGameManagerReturnsEmptyCollection()
    {
        Assert.IsEmpty(AiscDiagnostics.GetProtocolTrace());
    }

    /// <summary>
    /// 暂停诊断 DTO 应稳定承载三个时间域及 FX 计数。
    /// </summary>
    [Test]
    public void PauseDiagnosticDtoParsesTimeDomains()
    {
        var snapshot = JsonUtility.FromJson<PauseDiagnosticSnapshot>(
            "{\"gameplay_paused\":true,\"ui_paused\":false,\"fx_paused\":true,\"gameplay_sources\":[\"dialogue\"],\"fx_sources\":[\"dialogue\"],\"unity_time_scale\":0,\"registered_fx_count\":2,\"domain_paused_fx_count\":1}"
        );

        Assert.IsTrue(snapshot.gameplay_paused);
        Assert.IsFalse(snapshot.ui_paused);
        Assert.IsTrue(snapshot.fx_paused);
        Assert.AreEqual("dialogue", snapshot.gameplay_sources[0]);
        Assert.AreEqual(2, snapshot.registered_fx_count);
        Assert.AreEqual(1, snapshot.domain_paused_fx_count);
    }

    /// <summary>
    /// 协议轨迹应支持按 request_id 过滤，且不保存其他请求。
    /// </summary>
    [Test]
    public void ProtocolTraceFiltersByRequestId()
    {
        var protocol = new ProtocolClient();
        protocol.BeginSession();
        protocol.CreateEnvelope("first", "request_a", new JObject());
        protocol.CreateEnvelope("second", "request_b", new JObject());

        var trace = protocol.GetTraceSnapshot("request_b", 10);

        Assert.AreEqual(1, trace.Count);
        Assert.AreEqual("second", trace[0].type);
    }

    /// <summary>
    /// 协议轨迹超过固定容量后应只保留最近记录。
    /// </summary>
    [Test]
    public void ProtocolTraceKeepsFixedCapacity()
    {
        var protocol = new ProtocolClient();
        protocol.BeginSession();
        for (int index = 0; index < 205; index++)
            protocol.CreateEnvelope($"type_{index}", $"request_{index}", new JObject());

        var trace = protocol.GetTraceSnapshot(null, 200);

        Assert.AreEqual(200, trace.Count);
        Assert.AreEqual("type_5", trace[0].type);
        Assert.AreEqual("type_204", trace[199].type);
    }

    /// <summary>
    /// 没有运行中 GameManager 时会话检索诊断应返回空集合。
    /// </summary>
    [Test]
    public void ConversationRetrievalWithoutGameManagerReturnsEmptyCollection()
    {
        Assert.IsEmpty(AiscDiagnostics.GetConversationRetrievalSnapshots("dialogue_1", "kujo"));
    }

    /// <summary>
    /// 会话检索 DTO 应接收近期对白预览，且不再依赖话题实体字段。
    /// </summary>
    [Test]
    public void ConversationRetrievalDtoParsesRecentDialoguePreview()
    {
        var snapshot = JsonUtility.FromJson<ConversationRetrievalDiagnosticSnapshot>(
            "{\"conversation_id\":\"dialogue_1\",\"recent_dialogue_preview\":[\"player: 千早是谁？\"]}"
        );

        Assert.AreEqual("dialogue_1", snapshot.conversation_id);
        Assert.AreEqual(new[] { "player: 千早是谁？" }, snapshot.recent_dialogue_preview);
    }

    /// <summary>
    /// 初始知识投影 DTO 应保留权限、来源和实际边字段。
    /// </summary>
    [Test]
    public void InitialKnowledgeProjectionDtoParsesStructuredSnapshot()
    {
        var snapshot = JsonUtility.FromJson<InitialKnowledgeProjectionDiagnosticSnapshot>(
            "{\"npc_id\":\"sakura\",\"count\":1,\"items\":[{\"fact_id\":\"chihaya_bakery_identity\",\"status\":\"included\",\"projection_id\":\"initial_knowledge__sakura__chihaya_bakery_identity\",\"node_id\":\"node_1\",\"knowledge_scope\":\"public\",\"visibility_rule\":\"public\",\"source_type\":\"public_record\",\"edge_ids\":[\"edge_1\"]}]}"
        );

        Assert.AreEqual("public", snapshot.items[0].knowledge_scope);
        Assert.AreEqual("public", snapshot.items[0].visibility_rule);
        Assert.AreEqual(new[] { "edge_1" }, snapshot.items[0].edge_ids);
    }

    /// <summary>
    /// 非 PlayMode 查询初始知识时应返回稳定失败原因，而不是访问 Unity 运行态。
    /// </summary>
    [Test]
    public void InitialKnowledgeProjectionOutsidePlayModeReturnsStableFailure()
    {
        InitialKnowledgeProjectionDiagnosticSnapshot snapshot =
            AiscDiagnostics.GetInitialKnowledgeProjectionSnapshot("sakura");

        Assert.AreEqual("play_mode_required", snapshot.failure_reason);
        Assert.IsEmpty(snapshot.items);
    }

    /// <summary>
    /// 通用记忆快照 DTO 应接收方向、mention、层统计和路径证据。
    /// </summary>
    [Test]
    public void MemoryRetrievalDtoParsesStructuredTrace()
    {
        var snapshot = JsonUtility.FromJson<MemoryRetrievalDiagnosticSnapshot>(
            "{\"retrieval_trace_id\":\"trace_1\",\"strategy\":\"llm_guided_local\",\"direction_source\":\"local\",\"direction\":{\"recall_intent\":\"locate_person\",\"retrieval_query\":\"千早的位置\",\"query_constraints\":[\"person_location\"]},\"mentions\":[{\"text\":\"千早\",\"entity_id\":\"chihaya\"}],\"layer_stats\":[{\"depth\":1,\"frontier_nodes\":2}],\"path_evidence\":[{\"edge_id\":\"edge_1\",\"score\":0.8}],\"vector_query_count\":1,\"retrieval_query_source\":\"llm_guided\",\"query_constraints\":[\"person_location\"],\"vector_hit_usage\":[{\"node_id\":\"memory_1\",\"rank\":1,\"similarity\":0.9}],\"final_entries\":[{\"node_id\":\"memory_1\",\"type\":\"person\",\"score\":0.8,\"score_components\":[{\"name\":\"importance\",\"value\":0.7}],\"rendered_chars\":12}],\"policy_summary\":{\"max_depth\":8,\"beam_width\":12},\"stop_reason\":\"sufficient_evidence\"}"
        );

        Assert.AreEqual("trace_1", snapshot.retrieval_trace_id);
        Assert.AreEqual("locate_person", snapshot.direction.recall_intent);
        Assert.AreEqual("千早的位置", snapshot.direction.retrieval_query);
        Assert.AreEqual("chihaya", snapshot.mentions[0].entity_id);
        Assert.AreEqual(1, snapshot.layer_stats[0].depth);
        Assert.AreEqual("edge_1", snapshot.path_evidence[0].edge_id);
        Assert.AreEqual(1, snapshot.vector_query_count);
        Assert.AreEqual("llm_guided", snapshot.retrieval_query_source);
        Assert.AreEqual("person_location", snapshot.query_constraints[0]);
        Assert.AreEqual(0.9f, snapshot.vector_hit_usage[0].similarity);
        Assert.AreEqual("person", snapshot.final_entries[0].type);
        Assert.AreEqual("importance", snapshot.final_entries[0].score_components[0].name);
        Assert.AreEqual(8, snapshot.policy_summary.max_depth);
        Assert.AreEqual(12, snapshot.policy_summary.beam_width);
    }

    /// <summary>
    /// 快捷回复 DTO 应保留主体预期、拒绝原因和兜底状态，不要求完整文本。
    /// </summary>
    [Test]
    public void PlayerReplySuggestionDtoParsesSafetySnapshot()
    {
        var snapshot = JsonUtility.FromJson<PlayerReplySuggestionDiagnosticSnapshot>(
            "{\"reply_trace_id\":\"reply_1\",\"npc_id\":\"sakura\",\"speaker_role_expected\":\"player\",\"recipient_role_expected\":\"npc\",\"choice_count\":3,\"rejection_reasons\":[\"npc_name_prefix\"],\"fallback_used\":true}"
        );

        Assert.AreEqual("reply_1", snapshot.reply_trace_id);
        Assert.AreEqual("player", snapshot.speaker_role_expected);
        Assert.AreEqual("npc", snapshot.recipient_role_expected);
        Assert.AreEqual("npc_name_prefix", snapshot.rejection_reasons[0]);
        Assert.IsTrue(snapshot.fallback_used);
    }

    /// <summary>
    /// 非 PlayMode 的记忆检索探针应稳定失败且不访问后端。
    /// </summary>
    [Test]
    public void MemoryRetrievalProbeOutsidePlayModeReturnsStableFailure()
    {
        MemoryRetrievalProbeResult result = AiscDiagnostics.RunMemoryRetrievalProbe(
            "kujo", "player", "千早在哪？", "player_dialogue", "street.crossroad", "第1天 10:00");

        Assert.IsFalse(result.success);
        Assert.AreEqual("play_mode_required", result.failure_reason);
    }

    /// <summary>
    /// 午夜快照 DTO 应保留并发、固定方向与局部失败字段。
    /// </summary>
    [Test]
    public void MidnightSnapshotDtoParsesStructuredState()
    {
        var snapshot = JsonUtility.FromJson<MidnightMaintenanceDiagnosticSnapshot>(
            "{\"operation_id\":\"midnight_1\",\"status\":\"partial_failure\",\"phase\":\"complete\",\"target_count\":5,\"direction_source\":\"nightly_fixed_player\",\"llm_direction_calls\":0,\"impression_success_count\":4,\"impression_fallback_count\":1,\"extraction_invalid_edge_count\":2,\"parallel_wall_sec\":12.5}"
        );

        Assert.AreEqual("midnight_1", snapshot.operation_id);
        Assert.AreEqual("nightly_fixed_player", snapshot.direction_source);
        Assert.AreEqual(0, snapshot.llm_direction_calls);
        Assert.AreEqual(1, snapshot.impression_fallback_count);
        Assert.AreEqual(2, snapshot.extraction_invalid_edge_count);
        Assert.AreEqual(12.5f, snapshot.parallel_wall_sec);
    }

    /// <summary>
    /// 非 PlayMode 查询午夜快照时应返回稳定失败原因。
    /// </summary>
    [Test]
    public void MidnightSnapshotOutsidePlayModeReturnsStableFailure()
    {
        MidnightMaintenanceDiagnosticSnapshot snapshot = AiscDiagnostics.GetMidnightMaintenanceSnapshot();

        Assert.AreEqual("unavailable", snapshot.status);
        Assert.Contains("play_mode_required", snapshot.failure_reasons);
    }

    /// <summary>
    /// 白名单日程探针必须调用正式裁决 seam，并声明只写隔离内存。
    /// </summary>
    [TestCase("jump_to_17", "work", "work_task_continues_after_segment")]
    [TestCase("social_lock_defer", "deferred", "npc_social_dialogue_locked")]
    [TestCase("task_failure_replan", "", "task_terminal_consumed")]
    public void DailyScheduleProbeReturnsStableDecision(string scenario, string decision, string reason)
    {
        DailyScheduleProbeResult result = AiscDiagnostics.RunDailyScheduleProbe(scenario);

        Assert.IsTrue(result.success);
        Assert.AreEqual("isolated_in_memory_only", result.write_scope);
        Assert.AreEqual(decision, result.decision);
        Assert.AreEqual(reason, result.reason);
    }

    /// <summary>
    /// 迟到 revision 探针必须由正式 TryReplace 契约拒绝。
    /// </summary>
    [Test]
    public void DailyScheduleLateRevisionProbeIsRejected()
    {
        DailyScheduleProbeResult result = AiscDiagnostics.RunDailyScheduleProbe("late_revision");

        Assert.IsTrue(result.success);
        Assert.AreEqual("rejected", result.decision);
        Assert.AreEqual("stale_plan_revision", result.reason);
    }

    /// <summary>
    /// 社交探针必须稳定终态化并原子释放双方 reservation。
    /// </summary>
    [TestCase("complete", "completed")]
    [TestCase("player_preempt", "player_dialogue_preempted")]
    [TestCase("rendezvous_failure", "movement_failed")]
    [TestCase("late_content_revision", "player_dialogue_preempted")]
    public void NpcSocialProbeReachesStableTerminalAndReleasesBoth(string scenario, string reason)
    {
        NpcSocialProbeResult result = AiscDiagnostics.RunNpcSocialProbe(scenario);

        Assert.IsTrue(result.success, result.failure_reason);
        Assert.AreEqual("isolated_in_memory_only", result.write_scope);
        Assert.IsTrue(result.both_reserved_initially);
        Assert.IsTrue(result.both_released);
        Assert.AreEqual("terminal", result.terminal_phase);
        Assert.AreEqual(reason, result.terminal_reason);
        if (scenario == "late_content_revision")
            Assert.IsFalse(result.late_content_accepted);
    }

    /// <summary>
    /// 后端稳定 fallback seed 可超过 Int32，诊断 DTO 必须无损接收。
    /// </summary>
    [Test]
    public void ScheduleOwnerTraceParsesUnsignedFallbackSeedAsString()
    {
        var snapshot = JsonUtility.FromJson<ScheduleOwnerDiagnosticSnapshot>(
            "{\"fallback_seed\":\"18446744073709551615\",\"failure_reason\":\"planner_rejected:ValueError\",\"failure_detail\":\"unknown_candidate\"}");

        Assert.AreEqual("18446744073709551615", snapshot.fallback_seed);
        Assert.AreEqual("unknown_candidate", snapshot.failure_detail);
    }

    /// <summary>
    /// 空 replan operation 不得错误关联同 NPC 的其他 owner trace。
    /// </summary>
    [Test]
    public void EmptyOperationDoesNotSelectUnrelatedScheduleTrace()
    {
        var traces = new System.Collections.Generic.List<ScheduleOwnerDiagnosticSnapshot>
        {
            new ScheduleOwnerDiagnosticSnapshot { operation_id = "daily_schedule_2:owner:trace" },
        };

        Assert.IsNull(AiscDiagnostics.SelectScheduleOwnerTrace(string.Empty, traces));
        Assert.AreSame(traces[0], AiscDiagnostics.SelectScheduleOwnerTrace("daily_schedule_2", traces));
    }
}
