# YumuBot 可借鉴功能审阅

审阅对象：[`yumu-bot/yumu-bot`](https://github.com/yumu-bot/yumu-bot/tree/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17)，固定到提交 `3be8d659afa121f90ca9c8aa1e5b2bf780d62d17`（2026-08-18）。本文只讨论此前“无排行榜成绩历史库”之外的能力。

## 结论

最值得当前项目学习的不是 Yumu 的大数据库，而是几个有清晰边界的小机制。建议顺序如下：

1. 统一 osu! API 前台/后台调度器。
2. 谱面 PP 情景计算和理论 FC/BP 修复。
3. Qualified 列表与 Nomination 进度卡。
4. 服务级限流、功能开关与轻量指标。
5. 实时比赛监听（建立在 API 调度器之后）。
6. Mania 技能雷达/双人对比（先作为实验功能）。

OAuth 好友、Popular、RecentBest、历史 BP 浏览等功能依赖用户授权或长期保存大量完整成绩，不符合本项目当前的轻量存储边界，不建议近期复制。

## 1. 统一前台/后台 osu! API 调度器（最高优先级）

Yumu 的所有 osu! 请求进入一个优先队列，交互请求与后台任务分别标记优先级；前台、后台有独立的速率配额与熔断状态，同时共享总并发上限。它还按 `Retry-After` 处理 429，并对可恢复错误退避后重新入队：[请求入口与前后台优先级](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/osuApiService/impl/OsuApiBaseService.kt#L79-L124)、[优先队列、80/20 配额和独立熔断器](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/osuApiService/impl/OsuApiBaseService.kt#L204-L248)、[并发控制与 429 处理](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/osuApiService/impl/OsuApiBaseService.kt#L348-L446)。

这对当前项目尤其合适：新加入的成绩采集器会和 `/bp`、`/sc` 等交互查询争用同一套 osu! API 配额。当前网络层已有共享 `httpx` client 和重试装饰器，但没有跨功能的队列优先级，且重试器会捕获所有异常。

建议吸收一个简化版，而不是复制 Yumu 的整类实现：

- `ApiRequestScheduler.submit(call, kind="foreground" | "background")` 作为唯一调度入口。
- 有界优先队列 + 全局 `Semaphore`；永远先保证用户交互。
- 只重试网络错误、429 和 5xx；尊重 `Retry-After`，不重试 400/401/403/404。
- 暴露队列长度、等待时间、429 次数和失败数；后台队列满时丢弃或延后采集，不拖垮前台。

## 2. 谱面 PP 情景计算与理论 FC/BP 修复（高优先级）

### 参数化谱面 PP

Yumu 的 map 查询可接受 `accuracy`、`combo`、`misses`、mods 和 lazer/legacy 条件，然后同时计算用户指定情景以及 100/99/98/96/94/92% 的 PP 表：[参数解析](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MapStatisticsService.kt#L109-L136)、[情景模型和 PP 列表](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MapStatisticsService.kt#L282-L353)。

当前项目已经有 `.osu` 文件下载、mods 解析和 PP 计算，因此这是低存储、用户感知强的增量功能。适合扩展 `/m <bid> 98% 1xmiss +HDHR`，把“这图多少 PP”变成可复现的情景计算。计算请求对象应是独立的 typed model，供命令、AI tool 和绘图共同使用。

### 理论 FC / BP Fix

Yumu 从 BP 中挑出疑似 choke（断连但零 miss，或 miss 占物件数不超过 1%；mania 另有判定），计算 FC PP，再按新 PP 重排并使用 `0.95^index` 重算理论总 PP：[候选筛选](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BPFixService.kt#L123-L175)、[重排和加权](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BPFixService.kt#L177-L228)。

这个功能也无需长期数据库。实现时应明确标为“理论值/估算”，保留原 BP 和原总 PP，不把模拟结果写回成绩对象；判定阈值应可测试、可按模式替换。

## 3. Qualified 与 Nomination 视图（高优先级）

Yumu 提供按模式、状态、排序和分页浏览 Qualified 等谱面的卡片，并补充谱面上架时间与谱师信息：[Qualified 查询与分页](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/QualifiedMapService.kt#L29-L101)。Nomination 卡则聚合谱面讨论区，把 problem、suggestion、未解决项、hype、praise、客串难度和星数范围整理为一张进度卡：[数据获取与难度关联](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/NominationService.kt#L105-L133)、[讨论分类与汇总](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/NominationService.kt#L139-L221)。

两者都主要依赖官方搜索/讨论 API，不要求本地保存全量成绩，和当前项目很匹配。建议先做：

- `/qualified [模式] [页码]`：近期过审谱面列表。
- `/nomination <sid/bid>`：未解决问题、建议、hype 和谱师构成。
- 给短 TTL 缓存，讨论区失败时仍能降级展示基础谱面信息。

## 4. 运维限流、功能开关与指标（高优先级）

Yumu 有按 service 或 service-user 组成 key 的令牌桶：[TokenBucketRateLimiter](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/permission/TokenBucketRateLimiter.kt#L9-L62)；权限层支持针对服务做全局、群和用户范围控制：[PermissionController](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/permission/PermissionController.kt#L10-L69)；服务调用还会记录耗时及涉及的 uid/bid/sid/mode：[调用统计切面](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/aop/CheckAspect.java#L228-L258)、[统计模型](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/entity/ServiceCallStatistic.kt#L13-L35)。

值得借鉴的是“按成本保护功能”，例如预览、批量 BP、比赛监听分别设置每用户并发/频率，而不是所有命令一个阈值。实现应避免照搬其无容量上限的内存 key：使用有界 TTL cache；指标默认只记 command、耗时、结果和匿名化作用域，不长期记录查询过的玩家或谱面明细。

## 5. 实时比赛监听（中优先级，先完成 API 调度器）

Yumu 能在群内注册/停止 match listener；同一个 match 可复用监听实例，并限制每群、每用户最多三个监听：[监听状态、上限和重启清理](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MatchListenerService.kt#L40-L88)、[注册与复用](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MatchListenerService.kt#L179-L224)。每局开始/结束会补齐谱面和玩家信息、计算 rating 并发送局卡：[局事件处理](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MatchListenerService.kt#L228-L285)。

当前项目已有 `/mp` 和 `/rt` 的赛后查询，因此可以复用现有 match schema/绘图。新增的难点是长生命周期任务：轮询间隔、API 配额、同 match 去重、订阅群扇出、取消、机器人退出清理。它应作为独立 `MatchWatchManager`，必须走后台 API 队列，进程重启后默认不自动恢复，避免幽灵监听。

## 6. Mania 技能雷达与 VS（中优先级、实验性）

Yumu 同时拉取一到两名玩家的 BP，下载对应 `.osu` 文件，按谱面提取六维技能；成绩准确率会削弱每张图的技能贡献，再聚合前 100 BP，生成个人或 VS 数据：[单人/双人取数](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/SkillService.kt#L125-L178)、[谱面解析与技能聚合](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/SkillService.kt#L215-L304)、[准确率权重](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/SkillService.kt#L311-L326)。

这个方向很适合 mania 社区，但 Yumu 当前解析处明确以 `OsuMode.MANIA` 构造技能模型，因此不应宣传为四模式通用算法。建议先做 `/skill:mania` 和 `/skillvs:mania` 实验版，标明“启发式画像”，缓存 `(beatmap checksum, rate) -> skill vector`，避免每次重复解析 100 张谱。

## 不建议近期复制

### OAuth 好友/互关

Yumu 的好友功能依赖用户 OAuth token，同步/刷新 token 后才能查询关注关系：[OAuth 绑定和 token 同步](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/controller/BindController.kt#L35-L94)、[好友关系查询](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/FriendService.kt#L180-L327)。这会引入用户授权、token 加密、撤销、刷新失败与隐私治理，收益不足以覆盖安全成本。

### Popular、RecentBest、BP 历史

这些能力建立在“长期保存大量完整成绩”之上。RecentBest 直接从本地 score DAO 按用户和日期读取 ranked scores，并在未绑定/未收录时返回不同错误：[RecentBestService](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/RecentBestService.kt#L121-L144)；BP 历史通过快照中的 score ID 列表回查完整 score：[BestHistoryRecoverService](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BestHistoryRecoverService.kt#L95-L173)；Popular 同样是围绕本地成绩热度统计的服务：[PopularService 源码](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/PopularService.kt)。

当前项目刚建立的边界是“只保存官方排行榜查不到的成绩”。为了上述功能扩大为全量 score warehouse，会重新带来此前担心的硬盘、同步、回填和数据保留问题。若未来确有需求，优先使用官方 recent/BP 实时查询加短 TTL 缓存；不要借功能之名扩大历史库范围。

## 推荐落地路线

第一阶段先做 API 调度器和服务限流，它们是成绩采集、实时比赛和批量计算的共同基础。第二阶段做纯计算型的 `/m` PP 情景与 BP Fix。第三阶段补 Qualified/Nomination。实时比赛和 Mania 技能雷达作为独立可关闭的实验模块，等基础设施和缓存稳定后再上。

总体原则是：借鉴 Yumu 的调度、计算与交互模型，不复制它的全量数据平台。

## 2026-08-20：基于当前实现的重新排序

本节取代上面的初始落地顺序。当前项目已经具备前台/后台 API 调度、严格分类重试、批量用户快照与索引、谱面镜像竞速、Playwright 渲染调度，以及群聊“上一张谱面”上下文。Yumu 的这些基础设施思路已经被吸收，下一阶段应转向直接增加用户价值的功能。

| 当前优先级 | 功能 | 当前状态后的判断 |
| --- | --- | --- |
| P0 / 1 | 任意参数 PP 情景 | 最值得先做；纯计算、无新增长期数据，可复用现有 PP、谱面文件与 mods 基础设施 |
| P0 / 2 | BP Fix | 与 PP 情景共用计算内核；在前者完成后追加理论 FC、BP 重排和理论总 PP |
| P1 / 3 | Qualified / Nomination | 主要依赖官方搜索和讨论 API，存储成本低，能补足面向谱师/摸图用户的产品面 |
| P1 / 4 | 按功能/用户限流 | API 和渲染已有调度，但仍需保护高成本功能免受单用户重复调用影响 |
| P1 / 5 | 实时比赛监听 | 基础设施条件已经成熟，但长生命周期、群订阅和恢复语义仍使它比普通查询复杂 |
| P2 / 6 | Mania 技能雷达 / VS | 有差异化，但算法解释性、谱面解析成本和缓存设计需要先验证 |
| P2 / 7 | 统一成绩筛选 DSL | 当前项目已经有较丰富的 typed 筛选；应渐进补字段和复用范围，不值得重写 |
| P3 / 8 | BP 风格分析 | `/bpa` 已存在；只需按需吸收缺失指标，不再作为独立新功能立项 |

### P0：任意参数 PP 情景

Yumu 把 `accuracy`、`combo`、`misses`、mods、lazer/legacy 和可选 clock rate 组合成一个情景对象，并同时输出指定情景与多档准确率 PP：[参数读取](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MapStatisticsService.kt#L109-L136)、[情景模型与批量 PP](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MapStatisticsService.kt#L282-L353)。

当前 `/m` 已能展示谱面与 mods 后属性，但还没有通用的成绩情景输入。建议新增独立 `PerformanceScenario`，让命令、AI tool、谱面卡和未来 BP Fix 共用：

- 支持 acc、miss、combo、mods、clock rate、lazer/legacy；按模式验证互斥和合法范围。
- 同时返回“用户指定情景”和固定 ACC 梯度，避免每档 PP 分别排队计算。
- 输出必须包含规则版本与输入回显，使结果可复现。

### P0：BP Fix

Yumu 只挑选疑似 choke 的 BP 计算 FC PP，再把模拟成绩与原成绩合并、重排，并按 `0.95^index` 估算新总 PP：[choke 候选与并行计算](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BPFixService.kt#L123-L175)、[重排与权重重算](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BPFixService.kt#L177-L228)。

它应建立在 `PerformanceScenario` 上，而不是另写一套 PP 调用。第一版可只支持“原准确率、0 miss、FC combo”，结果显示原/理论 PP、原/理论 BP 位次和理论总 PP；不要修改或持久化真实成绩。Yumu 的固定 choke 阈值只能作为参考，四模式应有各自策略和测试样例。

### P1：Qualified / Nomination

Qualified 卡提供模式、状态、排序、分页与谱师补全：[QualifiedMapService](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/QualifiedMapService.kt#L29-L101)。Nomination 卡把讨论区内容归类为 problem、suggestion、未解决项、hype 和 praise，并汇总 GD 与难度信息：[讨论获取](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/NominationService.kt#L105-L133)、[分类汇总](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/NominationService.kt#L139-L221)。

镜像竞速与“上一张谱面”上下文已经可复用，新增工作主要是 discussion/search schema、短 TTL 缓存和卡片。建议把两项作为一个 `mapping` 功能域实现，但保持两个查询接口；讨论 API 失败时 Nomination 卡应降级为基础谱面集信息。

### P1：按功能/用户限流

API 调度器解决的是外部配额与前后台公平，Playwright 调度器解决的是渲染并发；它们不能阻止同一用户反复触发 `.osu` 下载、百条 BP 计算或常驻比赛监听。Yumu 的令牌桶支持 service 或 service-user key：[TokenBucketRateLimiter](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/permission/TokenBucketRateLimiter.kt#L9-L62)，权限层支持服务的全局、群和用户范围开关：[PermissionController](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/permission/PermissionController.kt#L10-L69)。

建议先做内存型、有容量上限和 TTL 的 `FeatureGuard`，按功能配置 cooldown、burst、每用户并发与每群并发。优先接入预览、BP Fix、技能分析和比赛监听；持久化的群/用户黑白名单等确有管理需求后再加，不必复制 Yumu 的完整权限数据库。

### P1：实时比赛监听

Yumu 会让多个群订阅复用同一 match listener，并设置每群、每用户上限与退出清理：[监听器状态和生命周期](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MatchListenerService.kt#L40-L88)、[注册、复用与上限](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MatchListenerService.kt#L179-L224)，并在局事件上生成即时卡片与 rating：[局事件处理](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/MatchListenerService.kt#L228-L285)。

当前已有 `/mp`、`/rt`、后台 API 调度和渲染队列，复用条件已齐。实现时仍应先限定为进程内、显式 start/stop、不跨重启恢复；用 `(match_id -> watcher)` 去重拉取，再向订阅群扇出。轮询请求必须标为 background，并受 `FeatureGuard` 的用户/群/全局 watcher 数限制。

### P2：Mania 技能雷达 / VS

Yumu 下载玩家 BP 对应谱面，提取六维 skill vector，以准确率削弱单图贡献并聚合前 100 BP，同时支持双人比较：[取数与 VS](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/SkillService.kt#L125-L178)、[解析和聚合](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/SkillService.kt#L215-L304)、[准确率权重](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/SkillService.kt#L311-L326)。

当前谱面缓存和批量请求能力降低了实现成本，但算法本身仍是最大风险。先做离线原型验证 skill 维度、不同 key 数和 rate mods，再决定是否发布；若上线，只标为 Mania 启发式画像，并缓存 `(checksum, effective_rate, algorithm_version)` 的向量。

### P2：统一成绩筛选 DSL

Yumu 的 `ScoreFilter` 覆盖谱师、标题、SR、PP、BPM、ACC、combo、各模式判定、mods、彩率和时间，并供多个成绩命令共用：[字段定义](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/model/filter/ScoreFilter.kt#L24-L116)、[筛选执行](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/model/filter/ScoreFilter.kt#L116-L145)。

当前项目已支持 pp/acc/SR、时间、FC、mods、标题/谱师和 miss 等条件，因此目标应从“新建 DSL”改为“收口现有 DSL”：统一字段注册表、解析错误、typed predicate 和命令复用，再按需求补 BPM、长度、判定数和彩率。不要移植 Yumu 500 多行正则枚举，也不要为了字段完整度阻塞前三项功能。

### P3：BP 风格分析

Yumu 的 BP 分析会从当前 top scores 计算 mod、rank、mapper、长度、星数、PP 与游玩时间等分布：[基础聚合](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BPAnalysisService.kt#L45-L120)、[分布与面板数据](https://github.com/yumu-bot/yumu-bot/blob/3be8d659afa121f90ca9c8aa1e5b2bf780d62d17/src/main/java/com/now/nowbot/service/messageServiceImpl/BPAnalysisService.kt#L139-L239)。

当前 `/bpa` 已经是同类功能，因此无需再建 Yumu 风格分析模块。只应对照现有卡片补缺失且有解释力的指标，例如谱师 PP 贡献、BP 新旧程度和 lazer/legacy 构成；这些都能在现有 `build_bpa_data` 内完成。

### 更新后的路线

先实现共享的 `PerformanceScenario`，随后用它完成参数化 `/m` 和 BP Fix；并行补一个轻量 `FeatureGuard`。下一批做 Qualified/Nomination。实时比赛监听等这三项稳定后上线；Mania 技能雷达先原型验证。成绩筛选和 `/bpa` 只做渐进式增强。
