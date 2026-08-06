# 交接文档：osubot agent 工具提速（图片回读 → 结构化文本直喂主模型）

> 场景：本会话在 nonebot-plugin-osubot 仓库，接手方在**此仓库**继续完善。
> 工作目录：`/home/soloopooo/gitworkdir/nonebot-plugin-osubot`

## 当前进度（已完成，2026-08-06 会话续作）

已在分支 `feat/agent-structured-tool-results` 完成两批改造，244 个测试全绿、ruff 通过：

**第一批：单条成绩/资料工具结构化**
- 新增 `_info_to_summary(info)`；泛化 `_score_to_bp_summary(score, bp_index=None)`。
- `draw_info` 加 `return_info=True`、`get_score_data` 加 `return_score=True` 关键字参数（既有调用点不受影响）。
- `send_osu_user_info` / `send_osu_recent_or_pr` / `send_osu_score` / `send_osu_bp_list` 单条路径改为结构化 JSON 返回（`status/player/mode/info|scores`），`include_image_for_analysis=false` 默认不带 image block。
- instructions 更新：分析类请求直接用 JSON 结构化数据，图片仅作展示。

**第二批：BP 全量分析两段式（先发图 → 分段读数据 → 分析）**
- 新增数据型分页工具 **`get_osu_bp_range`**：按 `range_text`（宽度 ≤20）分页读 BP 紧凑数据，不发图。
  - 返回 `{status, player, mode, range, total, has_more, next_start, scores:[≤20 条紧凑]}`；`_compact_score_summary` 单条约 163 字符，20 条=3260 < 6000 上限（完整 summary 20 条=9500 会被截断）。
  - 请求级 `bp_list_cache`（key=`(uid, source, mode, is_lazer, tuple(mods))`）：分页多次调用只拉一次 `get_user_scores`。
  - 错误分支统一 `_bp_tool_result("failed", ...)`，与 `get_osu_bp_data` 一致。
- `send_osu_bp_list` 多条路径接入 `deliver_bp_once` 去重（key 含 uid/source/mode/lazer/mods/low/high/filters），同请求同参数只发一张图。**去重是请求级**：`build_osu_agent_tools(ctx)` 每条消息重建一次（on_message → handle_reply_logic → choice_response_strategy → create_chat_graph → build_registered_agent_extensions），跨对话不会误去重。
- instructions 加"两段式"recipe：评价 bp 范围/整体 → ① `send_osu_bp_list` 发图（range 对齐用户范围，未给则 1-200）→ ② `get_osu_bp_range` 从 1-20 分段续读（一般前 40-60 条足够）→ ③ 基于数据评价；并明确 `get_osu_bp_range` 与 `send_osu_bp_list`/`get_osu_bp_data` 的分工。
- 测试：新增 8 个用例（range 分页/宽范围拒绝/末页/mod 过滤/缓存不发图/去重/指令 recipe/紧凑字段），共 23 个 agent 用例。
- 本地开发环境：ai-groupmate 已从 PyPI 安装最新版 2.1.1（服务器线上仍装 2.0.19）。本地测试需 `.env.test`（含 `ALEMBIC_STARTUP_CHECK=false`，已被 .gitignore 忽略）。

### 尚未做（下一步候选）

- `send_osu_history` / `send_osu_bp_analysis` / `send_osu_recommend` / match 系列等仍依赖图片回读，未结构化；history 有 `points` 数据、bpa 有 `build_bpa_data(score_ls)` 数据可考虑文本化。
- `get_osu_bp_data`（指定序号完整详情）完整 summary 单条 475 字符，20 条=9500 会超 6000 截断；已通过**指令约束**缓解——docstring + instructions 明确"每次最多传 10 个 BP 序号（≈4800 字符），需要更多分多次调用"，不改工具逻辑。
- `get_osu_bp_range` v2 可考虑支持 BP 筛选（500pp+ 等，目前只支持 range + mods）。
- `send_osu_map_info` / `send_osu_beatmapset_info` 属展示型工具，暂不结构化。

## 现状与要解决的问题

ai-groupmate 的 agent 里，osubot 注册了 18 个工具（见下方清单）。目前"锐评/分析某张成绩图"的链路是：

1. 工具把成绩/info **图片发到群里**（`_send_image`），并当 `include_image_for_analysis=true` 时把 base64 图片随工具结果一起返回（`_image_tool_result` 拼 `ContentBlock`）。
2. ai-groupmate 侧主模型若**不支持图片输入**（`AI_GROUPMATE__CHAT_MULTIMODAL=false`），`_build_extra_content_message` 会调用辅助视觉模型（`AI_GROUPMATE__VISION_MODEL=qwen-vl-max`）对图片做一次"图片回读"总结，再把总结文本喂给主模型。

**问题**：多一次辅助视觉模型的 LLM 往返 → 速度慢、额外成本、还可能读图有损/有提示注入面。

**目标**：分析/锐评类请求，直接用 osu API 返回的**结构化数据转文本**喂给主模型，不依赖发图后再回读。图片只作为"发给用户的展示物"，不作为分析数据源。

## 涉及的两侧代码

### osubot 侧（本次主要改动面）
`src/nonebot_plugin_osubot/agent_tools.py`

- `build_osu_agent_tools(ctx)`：`@register_agent_tool` 注册点，返回 `AgentToolBundle(tools=[...], instructions=[...])`。工具：`get_osubot_command_help / send_osu_user_info / send_osu_bp / get_osu_bp_data / get_osu_bp_range / send_osu_bp_list / send_osu_recent_or_pr / send_osu_score / search_osu_beatmaps / get_osu_scores_by_map_name / send_osu_history / send_osu_bp_analysis / send_osu_recommend / send_osu_profile_url / send_osu_match_history / send_osu_match_rating / send_osu_preview / send_osu_background / send_osu_medal / send_osu_map_info / send_osu_beatmapset_info`。
- `ContentBlock = str | dict[str, Any]`。图片结果格式：`[{"type":"text","text":...},{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}]`。
- `_image_tool_result(text, raw, include_image)`：`include_image` 为真才把 base64 图片塞进返回块。
- **结构化文本工具族（改造完成）**：
  - `_score_to_bp_summary(score, bp_index=None)`：完整 summary（beatmap 元信息 + rank/pp/acc/combo/miss/mods/statistics/played_at），单条约 475 字符。
  - `_compact_score_summary(score, bp_index)`：紧凑 summary（index/title/version/rank/pp/accuracy/combo/miss/mods/stars/date），单条约 163 字符，供 `get_osu_bp_range` 分页用。
  - `_info_to_summary(info)`：`UnifiedUser.statistics` 转结构化 dict。
  - `_bp_tool_result(...)`：JSON 串（status/player/mode/purpose/scores）。`purpose=analyze` 带 `next_action="reply_with_analysis"`。
  - `get_osu_bp_data`（指定序号完整详情，不发图）、`get_osu_bp_range`（范围分页紧凑数据，不发图，≤20 条/次，`has_more/next_start` 提示，请求级 `bp_list_cache`）。
- 约束参数：`include_image_for_analysis`（仅用户明确要求看渲染图本身时传 true）；`BpPurposeArg`（view / analyze）。
- `_query_bp_scores`（312 行）批量读 BP；`_normalize_bp_indices`（234 行）限制 ≤20 个。
- 工具错误统一返回中文错误串；`_resolve_osu_user`（171 行）处理"当前发言用户 / 被 @ 群友 / target_user_id / username"四种身份解析。

### ai-groupmate 侧（只读参考，一般不改）
`/home/soloopooo/gitworkdir/nonebot-plugin-ai-groupmate/src/nonebot_plugin_ai_groupmate/`

- `agent/graph.py`：`_normalize_tool_result`（219）区分 `str` 与 `list[ContentBlock]`；`_build_extra_content_message`（240）——`supports_images=false` 且有 image_url 时走 `image_summarizer`（图片回读），无图/纯文本直接作为 HumanMessage 喂主模型；`_estimate_content_tokens`（320）把单张图片按 1024 token 计。
- `agent/__init__.py`：`_chat_supports_images()`（142）、`_summarize_image_content`（623，调辅助视觉模型）、`build_chat_graph` 装配（1027-1041，`image_summarizer = summarize_image_content if not supports_images else None`）。
- 工具结果过长会被截断（`agent_tool_result_max_chars`，默认 6000，graph.py `_truncate_tool_content`）。**结构化文本别超限**：完整 summary 单条 475 字符 → 20 条 9500 会截断；紧凑 summary 单条 163 字符 → 20 条 3260 安全（`get_osu_bp_range` 用它）。
- 视觉调用有 `VisionRunMetrics` 计数（usage webui 有 Agent 指标面板），改文本化后该计数会下降，属预期。

## 实现方向建议（下一步）

> 本批已完成实现方向 1-3 与 5（见上方"当前进度"）；4 采用"直接附 summary"而非新增 purpose 参数。以下保留供后续续作参考：

1. 给 `send_osu_user_info` / `send_osu_recent_or_pr` / `send_osu_score` 等补结构化文本返回：拿 API 的 `UnifiedScore` / info 数据转 summary（复用 `_score_to_bp_summary` 的思路，info 需新增 `_info_to_summary` 之类）。 ✅ 已完成
2. 返回结构沿用 `_bp_tool_result` 风格：JSON 串，带 `status/player/mode/scores`，让主模型直接能分析；图片照常发群，但不再把 base64 塞给模型（`include_image_for_analysis` 默认 false，指令里引导模型"分析类请求走结构化数据"）。 ✅ 已完成
3. 更新 `AgentToolBundle.instructions`：明确"锐评/分析成绩 → 工具返回结构化数据文本，勿依赖图片回读；发图仅为展示"。 ✅ 已完成
4. 可加 `purpose=analyze` 类似参数给 recent/score 工具，或在返回文本里直接附上 summary。 ✅ 已选后者（不加参数）
5. 回归：注意 `_tool_result_status`（graph.py 269）只认 JSON 里的 `status ∈ {sent,skipped,failed}`，结构化返回别破坏既有去重/状态语义。 ✅ 单条成绩工具成功用 `status:"sent"`、数据型工具（get_osu_bp_data/get_osu_bp_range）用 `"ok"`、错误统一 `"failed"`；`send_osu_bp_list` 多条路径接入 `deliver_bp_once` 请求级去重

## 测试与校验

- osubot 测试：`tests/`（可用 `uv run pytest`）。本批新增/更新的 agent 用例在 `tests/test_agent_tools.py`。本地跑 agent 用例需先 `uv pip install nonebot-plugin-ai-groupmate`（本地装 2.1.1，from PyPI）并存在 `.env.test`（`ALEMBIC_STARTUP_CHECK=false`，被 .gitignore 忽略）。
- ai-groupmate 测试：`tests/test_non_multimodal_vision.py` 覆盖图片回读链路，若只改 osubot 侧不受影响。
- CI 约束（ai-groupmate 上游）：ruff + basedpyright（`reportRedeclaration` 会 fail）+ Coverage(3.10-3.13) + typos。osubot 自身 CI 以仓库为准。
- 服务器验证：装的是 2.0.19（site-packages 直改），字体重启后需留意；改 osubot 代码后需重建/重装 osubot 侧包再测试。真实群测时可用 `/词频` 等验证 bot 在线。本地 dev venv 装的是 ai-groupmate 2.1.1，若上线前需对旧版做兼容验证，可临时用 `uv pip install nonebot-plugin-ai-groupmate==2.0.20`。

## 已知遗留（本次已处理/已放弃）

- **字体豆腐块（已本地修复，不进 PR）**：群词频韩文显示豆腐，根因是内置 `SourceHanSans.otf` 为 "Source Han Sans CN" 子集（Hangul 音节 0 覆盖）。已用官方 `NotoSansCJKsc-Regular.otf`（含全部 Hangul 11172 音节）覆盖本地 `nonebot-plugin-ai-groupmate/src/nonebot_plugin_ai_groupmate/SourceHanSans.otf` 并 scp 到服务器 `.../site-packages/nonebot_plugin_ai_groupmate/SourceHanSans.otf`（wordcloud 每次现读字体，无需重启）。**本地改动未提交**（git 显示 ` M`），不要带入任何 PR；wheel 重装会覆盖服务器字体，需重推。
- **表情包反击错对象（已放弃排查）**：根因是用户5 的表情包消息在 bot 重启期间发出，ChatHistory 无记录 → `load_replied_message_histories` 按 `reply_to_id` 查不到 → 无 replied_images → 视觉总结不触发。属偶发，先放掉。
- **ai-groupmate 非多模态视觉支持（已完成并上游合并）**：PR #3 `feat/non-multimodal-vision` 已合入 upstream main（merge `13a7df3`），本地 main 已同步 `ba4174f`（v2.0.20）并 push fork。本仓库基于旧版本（服务器装 2.0.19），改动涉及工具侧 API 的 `AgentToolContext`/`register_agent_tool`/`AgentToolBundle`，这些接口在当前版本可用。

## 建议下一步使用的 skill

- 本交接文档已生成；续作时建议先读本项目 AGENTS.md（若有）。
- 写结构化文本改造时用 **tdd**（red-green-refactor，补各工具 analyze 路径用例）。
- 若后续排查线上慢/读图问题用 **diagnose**。
