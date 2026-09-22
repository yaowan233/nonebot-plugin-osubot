# 新版推荐图

Bot 使用 `POST /recommend/personal/jobs` 提交后台任务，再通过同路径加 `/{job_id}` 查询状态，
与推荐网页复用算法，不再要求一次 HTTP 请求等待整个计算，也不走旧版混合推荐接口。
`/推荐`、`/推荐 综合` 映射为 balanced；吃分、进阶、风格仍分别使用 farm、peak、style。
默认 500 个精算候选、20 张图片结果；Mania 不限制键数，CTB 和太鼓允许转谱，其他模式排除转谱。AI 可用 `filters.include_converts=false` 显式排除转谱。

运行 Bot 前，在部署环境设置：

- `OSU_RECOMMEND_API`：新版推荐后端地址；同一局域网可用 `http://192.168.6.136:8000`，公网 Bot 需配置可达地址。
- `OSU_RECOMMEND_API_TOKEN`：与后端 `RECOMMENDER_API_TOKEN` 一致，仅存放于私有环境配置。
- `OSU_RECOMMEND_CANDIDATE_LIMIT=500`、`OSU_RECOMMEND_RESULT_LIMIT=20` 可覆盖默认值。

卡片右侧分别显示谱面 PP、ACC 和 `+xx.xx pp` 总 PP 收益。
CTB/Mania/太鼓使用服务返回的练习目标 PP 与目标 ACC，不把单次预测混成练习目标。
CTB 显示 FC/Miss 目标，Mania 显示键数与 ACC 目标，STD 显示模型 Miss/Combo。
未知收益不伪装成零；封面保留原有缓存和占位图。

504 准备超时不会连续重算三次。空结果不会声称已加入更新队列。
代码更新后需重启实际 Bot 进程；本地修改不等于已部署运行中的 Bot。

## AI 条件推荐

`send_osu_recommend` 增加可选结构化 `filters`：
星数、应用 Mods 后的 BPM/时长（秒）、允许的完整 Mods 组合、Mania 4K-10K 多选、
转谱、排除已记录成绩（设 false 可重刷）、结果数（1-50）以及模式特征范围。
不填的条件保持 Bot 默认值；条件之间为 AND，Mods 和键数列表内部为 OR。

例如：“推荐 4K 或 7K、5-6 星、三分钟内、LN 占比 20%-50%”：

```json
{"mode":"mania","target":"mixed","filters":{"key_counts":[4,7],"min_stars":5,"max_stars":6,"max_length":180,"feature_ranges":{"ln_ratio":{"min":0.2,"max":0.5}}}}
```

- STD：slider_ratio（滑条占比）、jump_p90（跳跃距离）、angle_change_ratio（转角比例）。
- CTB：direction_change_ratio（换向比例）、edge_ratio（边缘物件比例）、x_jump_p90（横向跳跃距离）。
- 太鼓：rim_ratio（蓝键比例）、big_ratio（大音符比例）、color_change_ratio（换色比例）。
- Mania：ln_ratio（长条比例）、chord_ratio（和弦比例）、ln_overlap_ratio（长条重叠比例）。
- 各模式另支持平均/峰值每秒物件密度，准确名称与边界见 `recommendation_filters.py`。

所有 ratio 使用 0..1，不使用百分数整数。范围可只给 min 或 max。
不支持的字段、跨模式特征、反向范围和非法比例会明确报错，不静默忽略。
AI 返回 applied_filters 和各图实际 BPM/时长/键数/feature_values，可用于核对筛选。
AI 不猜测“少一点”等模糊要求的数值阈值；无结果时先询问用户是否放宽，不自动改条件。
目前不提供标签、谱师、指定 PP 区间等后端未支持的条件，也不会用筛选参数人为上调预测 ACC。

## 等待时间优化

- Bot/AI 共用 120 秒的成功结果缓存（最多 64 组），同用户、目标、完整筛选和后端鉴权配置相同时复用。
  `OSU_RECOMMEND_CACHE_TTL=0` 可禁用结果缓存；BP 或模型更新后最多有该 TTL 的旧结果窗口。
- 相同的并发查询合并成一次后端计算；一个调用方取消不会取消其他人的请求。最多同时挂起 8 组不同查询。
- 错误和空结果不保存；修改筛选不命中旧结果，不减少 500 个精算候选或 20 张默认结果。
- 头像和封面并发等待最多 6 秒（`OSU_RECOMMEND_ASSET_TIMEOUT`），慢资源改用占位图；
  HTTP 504 与客户端读取超时不自动连续重算三次。
- 首次、缓存过期或新筛选仍需后端计算。上述改动主要减少重复计算和出图附加等待，
  不意味着将 NAS 首次 42～75 秒的计算缩短为秒级。

后台准备接口已部署在 NAS 的 `jobs-v33-20260918` API 镜像。Bot 每 2 秒查询状态，不重复提交计算；
后端最多准备 600 秒（含排队），Bot 最多轮询约 630 秒。超出上限仍明确报错，不会无限等待。
相同条件重试复用后台任务；服务重启导致任务丢失时需重新提交。
实际 Bot 必须更新并重启这版代码，同时确保反向代理转发新增的任务和查询路径。
旧版 Bot 仍调用同步接口，可能继续看到“推荐准备超时”；网页同步接口暂未改为后台任务。

## AI 工具慢请求（2026-09-22）

`send_osu_recommend` 不再一直等待推荐和绘图完成。查询、绘图、发送合计超过 1 秒时，
工具返回 `status=pending` / `reason_code=recommendation_queued`，AI 只需告知任务已受理并结束；
图会在后台完成后发到原会话，不需要继续调用工具或让用户重新发指令。
这里的 `success=true` 仅指任务提交成功，`image_sent=false` 明确表示图片尚未发送。
快速请求仍直接返回图片发送结果和结构化推荐数据。

后台任务最多同时 8 个，每个任务限时 900 秒，同一 AI 工具上下文中相同参数的调用复用任务，
不会重复发送。空结果、失败和超时在后台通知原会话；正常结束 AI 回合不会取消已受理的推荐。
受理前被取消的工具调用会清理子任务；已过期的 AI 请求不提交新任务。
后台任务仅存于 Bot 进程内，重启会丢失；这不是持久队列。慢请求无法把图片重新返回已经结束的
AI 回合进行图片分析，因此 pending 时禁止编造分析结论。更新 Bot 并重启后生效，无需改模型或
增大 ai-groupmate 的全局工具超时。
