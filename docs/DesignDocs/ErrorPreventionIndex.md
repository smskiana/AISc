# 低级错误预防索引

## 作用

本索引用来汇总项目中已经发生过、且后续高度可能重复出现的可复用错误。

目标：

1. 让 `AGENTS.md` / `CLAUDE.md` 保持简洁
2. 让单个错误保留完整上下文，不因规则文件控长而失真
3. 在新会话或高风险修改前，能快速先看索引，再决定是否深入具体错误明细

## 使用规则

1. 当出现可复用错误并已修正后，先创建独立错误明细文档
2. 再把该文档回写到本索引
3. 本索引只保留：
   - 标题
   - 一句话摘要
   - 影响范围
   - 何时优先回看
   - 明细链接

## 错误列表

### 2026-07-19：存档 schema 版本源分叉

- 一句话摘要：提升存档 schema 时必须同步 DTO 默认值、仓储当前版本和迁移链终点，并用默认新档 prepare 回归锁定三者一致。
- 影响范围：Unity 主存档、manifest、迁移链和双端保存事务。
- 何时优先回看：新增或调整任何 Unity 存档 schema、持久字段或 migration 前。
- 明细：[2026-07-19_save_schema_version_sources_diverged.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-19_save_schema_version_sources_diverged.md:1)

### 2026-07-19：重复字段名导致补丁命中错误类型

- 一句话摘要：补丁上下文若只包含重复字段名，可能语法成功却写入错误 DTO，必须包含目标类名或唯一邻接字段。
- 影响范围：相似 DTO、重复序列化字段和长文件局部补丁。
- 何时优先回看：在同一文件多个类型中新增常见字段名前。
- 明细：[2026-07-19_ambiguous_repeated_field_patch_target.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-19_ambiguous_repeated_field_patch_target.md:1)

### 2026-07-19：跨语言诊断整数宽度不一致

- 一句话摘要：稳定 hash/seed 可能超过有符号 Int64 且受 JSON number 精度影响，应按十进制字符串跨端传输。
- 影响范围：诊断 DTO、revision、sequence、稳定 hash/seed 和跨端持久化整数。
- 何时优先回看：新增或修改 Python/Unity 共用数值字段前。
- 明细：[2026-07-19_cross_language_integer_width.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-19_cross_language_integer_width.md:1)

### 2026-07-19：日程探针夹具未命中目标契约层

- 一句话摘要：探针输入必须先满足前置合法性，并从正式 adapter 获取稳定 ID，否则会命中更早拒绝层或产生 fallback 假象。
- 影响范围：日程 revision、planner provider、候选 ID 和白名单诊断探针。
- 何时优先回看：新增需要验证特定稳定拒绝原因或固定 planner 输出的探针前。
- 明细：[2026-07-19_schedule_probe_fixture_contract.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-19_schedule_probe_fixture_contract.md:1)

### 2026-07-17：Prompt 迁移丢失发言主体契约

- 一句话摘要：把业务 Prompt 迁入数据层时，若未逐项迁移发言者、接收者和上下文方向，格式正确的输出仍可能改由 NPC 代玩家说话。
- 影响范围：玩家快捷回复、PromptAssembler task 迁移、LLM 输出收口和诊断 trace。
- 何时优先回看：新增或迁移任何带角色身份的 Prompt contract、修改回复解析或快捷回复测试前。
- 明细：[2026-07-17_prompt_migration_speaker_contract_loss.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-17_prompt_migration_speaker_contract_loss.md:1)

### 2026-07-17：LLM 方向合法误判与最终重排丢失实体记忆

- 一句话摘要：结构合法的 LLM 检索方向仍可能语义错误；最终重排不能让事件类型先验挤掉已命中的人物 / 身份记忆。
- 影响范围：玩家对话记忆方向、图检索最终上下文、记忆诊断和防编造测试。
- 何时优先回看：修改 `memory_direction` 收口、最终节点重排、`final_memory_limit` 或新增实体记忆回归测试前。
- 明细：[2026-07-17_llm_direction_and_final_rerank_memory_loss.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-17_llm_direction_and_final_rerank_memory_loss.md:1)

### 2026-07-17: 稳定投影 ID 路由与 scope 角色越权

- 一句话摘要：稳定 projection ID 不应被字符串拆分推断 owner，scope 也必须先于角色优先级约束可见性。
- 影响范围：冷启动初始知识、LanceDB 批量写入、SQLite 图投影和权限诊断。
- 何时优先回看：新增稳定记忆 ID、观察者投影规则或多 NPC 批量向量写入前。
- 明细：[2026-07-17_initial_knowledge_projection_seams.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-17_initial_knowledge_projection_seams.md:1)

### 2026-07-16: Windows CLI 中文参数进入 Python 后乱码

- 一句话摘要：PowerShell 向 Python 脚本传递中文命令行参数时可能发生编码转换，导致 LLM prompt 的时间等上下文变成乱码。
- 影响范围：Windows 下通过 CLI 传入中文时间、地点、标签或 prompt 片段的跑测与维护脚本。
- 何时优先回看：准备把中文字符串作为 Python 命令行参数传入真实 LLM 测试前。
- 明细：[2026-07-16_windows_cli_chinese_argument_mojibake.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-16_windows_cli_chinese_argument_mojibake.md:1)

### 2026-07-16: 并行 Python 命令争写同一 pycache

- 一句话摘要：并行执行 `py_compile` 与测试时可能同时替换同一个 `.pyc`，在 Windows 上触发拒绝访问。
- 影响范围：针对相同 Python 模块并行运行编译、导入、单测或其他会写 `__pycache__` 的命令。
- 何时优先回看：准备并行运行 Python 编译与测试验证前。
- 明细：[2026-07-16_parallel_python_pycache_collision.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-16_parallel_python_pycache_collision.md:1)

### 2026-07-16: 共享地点新增后缺少 Unity fallback

- 一句话摘要：新增共享 `location_id` 时只更新语义或场景 Anchor，会导致 Unity fallback 与跨端约定不完整。
- 影响范围：地点、床位、传送出口、任务目标点等稳定位置 ID。
- 何时优先回看：修改 `shared/locations.json` 或新建 `SceneAnchor` 前。
- 明细：[2026-07-16_shared_location_requires_fallback.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-16_shared_location_requires_fallback.md:1)

### 2026-07-14: Unity MCP 外部新增脚本未显式导入

- 一句话摘要：外部新增 C# 后仅刷新可能未生成 `.meta`，必须先用 `manage_asset import` 纳入 AssetDatabase，再编译和挂载组件。
- 影响范围：通过 `apply_patch` 新增 Unity 脚本后立即使用 Unity MCP 挂载、查询或连线。
- 何时优先回看：Unity Console 无编译错误但 `manage_components` 报告找不到新组件类型时。
- 明细：[2026-07-14_unity_mcp_new_script_requires_import.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-14_unity_mcp_new_script_requires_import.md:1)

### 2026-07-14: 兼容标记误改原有注释

- 一句话摘要：为旧类增加兼容定位时误改模块说明和类 docstring，应保留原文并另加补充注释。
- 影响范围：带历史注释、docstring、XML summary 的兼容改造和职责迁移。
- 何时优先回看：准备给旧类标记 deprecated、legacy 或 compatibility 定位前。
- 明细：[2026-07-14_original_comment_accidental_edit.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-14_original_comment_accidental_edit.md:1)

### 2026-07-13: 测试方法因补丁插入点落入错误类

- 一句话摘要：在测试类中间插入新类时未检查完整类边界，导致后续原测试方法被 Python 归入新类。
- 影响范围：Python 测试文件新增测试类、长文件局部补丁、依赖 `setUp` 夹具的测试。
- 何时优先回看：在已有测试类之间插入新类或批量移动测试方法前。
- 明细：[2026-07-13_test_method_wrong_class.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-13_test_method_wrong_class.md:1)

### 2026-07-11: Day 0 被 `or 1` 误覆盖

- 一句话摘要：允许为 `0` 的数值字段被 `or 默认值` 误覆盖，导致合法 `0` 丢失。
- 影响范围：Python 中读取 `created_day`、计数器、索引、偏移量、状态值等允许为 `0` 的字段时。
- 何时优先回看：修改记忆时间语义、节点元数据读取、任何“数值字段带默认值”的代码前。
- 明细： [2026-07-11_day0_or1_override.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-11_day0_or1_override.md:1)

### 2026-07-11: 旧表索引早于迁移导致启动失败

- 一句话摘要：旧 SQLite 表不会被 `CREATE TABLE IF NOT EXISTS` 自动补列，随后创建依赖新列的索引会在迁移前失败。
- 影响范围：后端启动、旧存档热升级、SQLite schema/index 演进。
- 何时优先回看：新增表列、索引或兼容旧 `game.db` / 存档数据库前。
- 明细： [2026-07-11_schema_index_before_migration.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-11_schema_index_before_migration.md:1)

### 2026-07-12: OdinUpgrader.cs 缺失但 csproj 仍引用

- 一句话摘要：安装或刷新 Odin 后，`.csproj` 可能残留对不存在 Sirenix 源文件的 `Compile Include`，导致命令行编译失败。
- 影响范围：Unity / Odin 插件安装、项目文件刷新、命令行 `dotnet build` 验证。
- 何时优先回看：安装 / 升级 Odin 后遇到 `CS2001` 缺失 Sirenix 源文件错误时。
- 明细： [2026-07-12_odin_missing_upgrader_csproj.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-12_odin_missing_upgrader_csproj.md:1)

### 2026-07-20：Transformers 5 chat template 返回 BatchEncoding

- 一句话摘要：`apply_chat_template(..., return_tensors="pt")` 的返回值可能是批次映射，必须用 `model.generate(**inputs)`，不能沿用单 tensor 调用。
- 影响范围：Transformers 5、Qwen chat template、关闭 thinking 推理、训练与评估脚本。
- 何时优先回看：新增或升级本地生成模型的 tokenizer / generate smoke 前。
- 明细：[2026-07-20_transformers_chat_template_batch_encoding.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-20_transformers_chat_template_batch_encoding.md:1)

### 2026-07-20：TorchVersion 不能直接写入 PyYAML safe_dump

- 一句话摘要：第三方库版本对象即使表现为字符串，也应先归一化为基础类型再写 JSON/YAML manifest。
- 影响范围：训练锁定、运行 manifest、PyTorch/Transformers 版本记录和可复现性门禁。
- 何时优先回看：把运行库版本或设备属性写入 YAML/JSON 产物前。
- 明细：[2026-07-20_torch_version_yaml_serialization.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-20_torch_version_yaml_serialization.md:1)

### 2026-07-20：Hugging Face 分析命令漏传 HF_HOME

- 一句话摘要：临时 tokenizer / 模型分析命令也会按进程环境选择缓存，漏传 `HF_HOME` 会回退到 C 盘并可能访问 Hub。
- 影响范围：Transformers、huggingface_hub、本地模型评估、token 统计和项目外模型缓存。
- 何时优先回看：运行任何 `from_pretrained()` 训练、测试或只读分析命令前。
- 明细：[2026-07-20_huggingface_analysis_missing_hf_home.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-20_huggingface_analysis_missing_hf_home.md:1)

### 2026-07-20：PowerShell Error 自动变量不可覆盖

- 一句话摘要：PowerShell 变量名不区分大小写，`$error` 会命中只读自动变量 `$Error` 并使多步骤校验进入无效状态。
- 影响范围：PowerShell 临时脚本、路径变量、测试收口和多步骤文档校验。
- 何时优先回看：编写包含多个临时变量的 PowerShell 验证命令前。
- 明细：[2026-07-20_powershell_error_automatic_variable.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-20_powershell_error_automatic_variable.md:1)

### 2026-07-21：SHA-256 抄录缺位但未在冻结时拦截

- 一句话摘要：冻结哈希不能只目视复制，必须同时校验 64 位小写十六进制格式并对目标实物重新计算后逐值比较。
- 影响范围：模型 Adapter、训练 corpus、报告、配置、发布清单和任何以 SHA-256 固定身份的资产。
- 何时优先回看：把外部资产 SHA-256 写入 plan、execution、test、配置或 manifest 前。
- 明细：[2026-07-21_sha256_transcription_length_gate.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-21_sha256_transcription_length_gate.md:1)

### 2026-07-21：Windows 子进程 JSONL 标准流代码页错配

- 一句话摘要：父进程的 `Popen(encoding="utf-8")` 不会替子进程配置标准流，中文 JSONL worker 必须在入口显式把 stdin/stdout/stderr 重配为 UTF-8。
- 影响范围：Windows 本地模型 worker、JSONL 子进程协议、中文 Prompt、tokenizer 和结构化输出。
- 何时优先回看：新增或修改通过 Windows pipe 传递中文 JSONL 的 Python 子进程前。
- 明细：[2026-07-21_windows_subprocess_jsonl_stdio_encoding.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-21_windows_subprocess_jsonl_stdio_encoding.md:1)

### 2026-07-21：Windows 下空 CUDA_VISIBLE_DEVICES 未禁用 GPU

- 一句话摘要：空字符串不能证明 CUDA 已屏蔽，应使用 `CUDA_VISIBLE_DEVICES=-1` 并在目标 venv 直接断言 `torch.cuda.is_available() is False`。
- 影响范围：Windows、PyTorch/CUDA、本地模型 worker 和 GPU 故障注入测试。
- 何时优先回看：准备验证 CUDA 不可用、CPU fallback 或 GPU 隔离行为前。
- 明细：[2026-07-21_windows_cuda_visible_devices_empty.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-21_windows_cuda_visible_devices_empty.md:1)

### 2026-07-21：后端脚本按文件路径启动时缺少项目根

- 一句话摘要：`python backend/scripts/tool.py` 不会自动把仓库根加入 `sys.path`，新 CLI 必须复用项目根初始化并测试真实文件入口。
- 影响范围：后端诊断脚本、维护 CLI、文档命令和模块导入。
- 何时优先回看：新增直接导入 `backend.*` 的 `backend/scripts/*.py` 前。
- 明细：[2026-07-21_backend_script_missing_project_root.md](/F:/GameProject/unity/AISc/docs/DesignDocs/errors/2026-07-21_backend_script_missing_project_root.md:1)
