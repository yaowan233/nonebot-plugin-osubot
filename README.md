<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-osubot

_✨ 面向 NoneBot2 的 osu! 查询与谱面工具插件 ✨_


<a href="./License">
    <img src="https://img.shields.io/github/license/yaowan233/nonebot-plugin-osubot.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-osubot">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-osubot.svg" alt="pypi">
</a>
<a href="https://codecov.io/gh/yaowan233/nonebot-plugin-osubot">
    <img src="https://codecov.io/gh/yaowan233/nonebot-plugin-osubot/branch/master/graph/badge.svg" alt="codecov">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

</div>


## 📖 介绍

nonebot-plugin-osubot 提供 osu! 四种模式的玩家资料、成绩、BP 分析、群内排名、多人比赛分析、谱面信息与谱面预览等功能。查询结果以适合聊天场景的图片呈现，并通过 `nonebot-plugin-uninfo` 获取跨适配器的用户、群组与频道信息。

项目修改自 [osuv2](https://github.com/Yuri-YuzuChaN/osuv2)，并针对 NoneBot2 的命令交互、绘图和多平台使用进行了持续维护。

> [!NOTE]
> 本部署额外内置 **g0v0（咕哦服）** 服务器查询支持：查询末尾加 `&gu` 即可切换到
> g0v0 服务器（osu!(lazer) 兼容服务器，含 RX/AP 模式），与官方 osu! API 和
> ppysb（`&sb`）查询完全并列，互不影响。详见下方「g0v0 查询」与「⚙️ 配置」。

> [!IMPORTANT]
> 原生谱面预览无需 FFmpeg；仅在原生渲染失败并回退旧完整视频链路时依赖
> [FFmpeg](https://ffmpeg.org/download.html)。可将 FFmpeg 加入 `PATH`，或通过
> `OSU_PREVIEW_FFMPEG_PATH` 指定可执行文件。

## 💿 安装

运行环境：Python 3.10–3.13、NoneBot2 2.3.0 及以上版本。

<details>
<summary>使用 nb-cli 安装（推荐）</summary>

在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

```bash
nb plugin install nonebot-plugin-osubot
```

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

```bash
pip install nonebot-plugin-osubot
```

</details>
<details>
<summary>pdm</summary>

```bash
pdm add nonebot-plugin-osubot
```

</details>
<details>
<summary>poetry</summary>

```bash
poetry add nonebot-plugin-osubot
```

</details>


打开 nonebot2 项目的 `bot.py` 文件, 在其中写入

```python
nonebot.load_plugin("nonebot_plugin_osubot")
```

</details>


## ⚙️ 配置

前往 [osu! 账号设置](https://osu.ppy.sh/home/account/edit) 创建 OAuth 应用，将客户端 ID 和客户端密钥写入 NoneBot 项目的 `.env` 文件：

```dotenv
OSU_CLIENT=你的客户端ID
OSU_KEY=你的客户端密钥
```

若需使用 `/friend` 好友功能，请在同一个 osu! OAuth 应用中将回调地址设置为
`https://mayumi.xyz/api/osubot/oauth/callback`。插件会通过公共中转站完成授权，无需新增配置或自行部署公网回调。

### 基础配置

| 配置项 | 必填 | 默认值 | 说明 |
| --- | :---: | --- | --- |
| `OSU_CLIENT` | 是 | 无 | osu! OAuth 客户端 ID |
| `OSU_KEY` | 是 | 无 | osu! OAuth 客户端密钥 |
| `SQLALCHEMY_DATABASE_URL` | 否 | `sqlite+aiosqlite:///db.sqlite3` | 数据库地址，详见 [NoneBot ORM 配置](https://nonebot.dev/docs/best-practice/database/) |
| `OSU_PROXY` | 否 | 无 | 请求 osu! API 时使用的代理地址或代理配置 |
| `OSUTRACK_ENABLED` | 否 | `true` | 是否启用玩家信息定时追踪 |
| `OSUTRACK_DEFAULT_DAYS` | 否 | `365` | 历史查询的默认追踪天数 |
| `OSU_SCORE_HISTORY_ENABLED` | 否 | `true` | 是否采集官网排行榜无法查询的成绩历史 |
| `OSU_SCORE_HISTORY_SYNC_HOUR` | 否 | `2` | 每日采集小时（服务器本地时间，0–23） |
| `OSU_SCORE_HISTORY_CONCURRENCY` | 否 | `2` | 成绩采集并发数（1–20） |
| `OSU_SCORE_HISTORY_RECENT_LIMIT` | 否 | `200` | 每个活跃用户/模式检查的最近成绩数（1–1000） |
| `OSU_API_MAX_CONCURRENCY` | 否 | `8` | osu! API 总并发；至少为前台和后台各保留一个 worker |
| `OSU_API_FOREGROUND_RATE` | 否 | `8.0` | 交互查询每秒启动的最大请求数 |
| `OSU_API_BACKGROUND_RATE` | 否 | `1.0` | 历史采集每秒启动的最大请求数 |
| `OSU_API_QUEUE_SIZE` | 否 | `512` | 前台、后台各自的最大等待队列长度 |
| `OSU_API_MAX_RETRIES` | 否 | `3` | 网络错误、429 和 5xx 的最大重试次数 |
| `OSU_RENDER_MAX_CONCURRENCY` | 否 | `2` | Playwright 同时执行的最大绘图数（1–16） |
| `OSU_RENDER_QUEUE_SIZE` | 否 | `64` | Playwright 绘图等待队列的最大长度 |
| `OSU_RENDER_QUEUE_TIMEOUT` | 否 | `30.0` | 绘图请求允许排队的最长秒数 |
| `OSU_RENDER_TIMEOUT` | 否 | `180.0` | 单次 Playwright 绘图的最长执行秒数 |
| `G0V0_API_BASE` | 否 | `https://lazer-api.g0v0.top` | g0v0（咕哦服）服务器 API 地址，自建 g0v0-server 时可改为自己的域名 |
| `G0V0_CLIENT` | 否 | 无 | g0v0 服务器 OAuth 客户端 ID（在 g0v0 服务器 OAuth 应用管理页面注册获取） |
| `G0V0_KEY` | 否 | 无 | g0v0 服务器 OAuth 客户端密钥；未配置或获取 token 失败时自动以匿名方式查询公开数据 |

### 完整预览配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `OSU_PREVIEW_FFMPEG_PATH` | `PATH` 中的 FFmpeg | FFmpeg 可执行文件路径 |
| `OSU_PREVIEW_TAIKO_SKIN_PATH` | 无 | Taiko 皮肤目录，支持滚轮素材及其 `@2x` 版本；留空时使用内置样式 |
| `OSU_PREVIEW_FULL_SCALE` | `0.75` | Mania 完整视频缩放倍率，范围 0.5–1.0 |
| `OSU_PREVIEW_FULL_FRAME_INTERVAL` | `30` | Mania 完整视频帧间隔（毫秒），范围 20–50 |
| `OSU_PREVIEW_TAIKO_FULL_SCALE` | `0.5` | Taiko 完整视频缩放倍率 |
| `OSU_PREVIEW_TAIKO_FULL_FRAME_INTERVAL` | `30` | Taiko 完整视频帧间隔（毫秒） |
| `OSU_PREVIEW_STD_CATCH_FULL_SCALE` | `0.5` | osu!/Catch 完整视频缩放倍率 |
| `OSU_PREVIEW_STD_CATCH_FULL_FRAME_INTERVAL` | `30` | osu!/Catch 完整视频帧间隔（毫秒） |


### 原生谱面预览

插件通过 [osu-beatmap-preview-py](https://pypi.org/project/osu-beatmap-preview-py/)
在 Python 进程内调用 Rust 渲染器，支持四种模式以及 GIF、PNG、MP4 输出。
安装插件时会自动安装对应平台的预编译 wheel，无需下载可执行文件或新增配置；
原生渲染失败时会自动回退现有浏览器渲染链路。

## ⚠️ 从 v6 升级到 v7

v7 将底层 ORM 从 tortoise-orm 迁移至 nonebot-plugin-orm，**数据库表名和结构发生了变化**，升级前需手动执行迁移脚本，否则数据将丢失。

**升级步骤：**

1. 停止 bot
2. 在 bot 根目录下运行迁移脚本：

```bash
# 默认 SQLite（自动从 .env 读取数据库地址）
python migrate.py

# 或手动指定数据库地址
python migrate.py sqlite:///db.sqlite3
python migrate.py postgresql://user:pass@localhost/dbname
python migrate.py mysql+pymysql://user:pass@localhost/dbname
```

3. 标记迁移版本：

```bash
nb orm stamp 68a04ea31d05
```

4. 升级插件后重启 bot

## 🎉 使用

首次使用请发送 `/bind <用户名、UID 或主页链接>` 绑定账号。发送 `/osuhelp` 可查看交互式帮助，发送 `/osuhelp 全部` 可查看完整指令说明。

通用格式：

```text
/命令 [玩家] [序号或范围]:[模式] [+Mods] [&sb]
```

模式简称：`o`/`0` = osu!、`t`/`1` = Taiko、`c`/`2` = Catch、`m`/`3` = Mania。未指定玩家或模式时，使用当前用户绑定账号的默认设置。官网成绩查询默认包含 lazer 与 stable 成绩，无需切换；成绩图会逐条标注来源。

### 常用指令

| 分类 | 指令 | 说明 |
| --- | --- | --- |
| 账号 | `/bind`、`/unbind`、`/mode` | 绑定账号与设置默认模式 |
| 资料 | `/info`、`/mu`、`/rank`、`/update` | 玩家资料、主页、群内 PP 排名和资料刷新 |
| 最佳成绩 | `/bp`、`/bl`、`/nb`、`/bpa` | 单条 BP、BP 列表、新增 BP 与 BP 分析 |
| 第一名成绩 | `/first [序号或范围]` | 查询玩家在谱面排行榜上的第一名成绩（仅 osu! 官网） |
| 最近成绩 | `/re`、`/rl`、`/pr`、`/pl` | 最近游玩、最近通过成绩及其列表 |
| 谱面成绩 | `/sc [mapid]`、`/sl [mapid]` | 查询单条成绩，或列出该谱面各 Mod 组合的最佳成绩 |
| 历史 | `/hs [#天数]` | 查询 PP 与排名历史 |
| 谱面 | `/m`、`/bm`、`/bg`、`/dl` | 难度信息、谱面集、背景与谱面下载 |
| 预览 | `/预览`、`/完整预览`、`/vp` | 普通预览、全谱预览和完整预览视频 |
| 多人 | `/mp <matchid>`、`/rt <matchid>` | 多人比赛详情与多人房评分 |
| 其他 | `/推荐`、`/md`、猜歌指令 | 谱面推荐、成就查询与猜歌游戏 |

示例：

```text
/bind peppy
/bp 5:o +HDHR
/bl 31-60:m
/first peppy 1-20:o
/sc 3783810
/sl 3783810
/bpa
/预览 3783810 +gif
/完整预览 3783810
/mp 123456789
```

查询过一张谱面后，`/m`、`/bm`、`/sc`、`/bg`、`/预览`、`/dl` 等指令可以省略 ID，复用最近查询的谱面。

### ppysb 查询

使用 `/sbbind <玩家>` 绑定 ppysb 账号，然后在普通查询末尾添加 `&sb`，例如 `/info &sb`、`/bl:4 &sb`。SB 模式 `0`–`3` 对应四种常规模式，`4`–`6` 对应 Relax，`8` 对应 Autopilot。

### g0v0 查询

使用 `/gubind <玩家>` 绑定 g0v0（咕哦服）账号，然后在普通查询末尾添加 `&gu` 即可切换到 g0v0 服务器，例如：

```text
/gubind Chestnut         绑定 g0v0 账号
/info &gu                查询已绑定 g0v0 玩家资料
/bl:4 &gu                查询 RX std BP 1–30
/rl:5 &gu                查询 RX taiko 最近游玩
/sc <mapid>:6 &gu        查询 RX catch 谱面成绩
/guunbind                解除 g0v0 账号绑定
```

g0v0 模式 `0`–`3` 对应 std/taiko/catch/mania，`4`/`5`/`6`/`8` 对应 RX std / RX taiko / RX catch / AP std。其他成绩查询与分析指令（`/bp`、`/bl`、`/re`、`/rl`、`/pr`、`/pl`、`/sc`、`/sl`、`/first`、`/bpa` 等）均支持 `&gu` 后缀；`/fix`（BP Fix）目前仅支持 osu! 官网成绩。g0v0 API 目前不提供 PP/排名历史快照，因此 `/hs` 仅支持 osu! 官网。g0v0 的 OAuth 配置见上方「⚙️ 配置」的 `G0V0_*` 项。

### AI 自然语言调用（可选）

如果同一个 NoneBot 项目中安装并加载了 `nonebot-plugin-ai-groupmate`，本插件会自动向 ai-groupmate 注册 osu 查询工具。用户可以通过自然语言让 AI 调用 osubot 的查询能力，而不是直接输入固定命令。

没有安装或没有加载 `nonebot-plugin-ai-groupmate` 时，本功能会自动跳过，不影响 osubot 原有指令使用。

示例：

```text
@bot 查我的 bp1
@bot 查我的榜一 1-20
@bot 查我的 info
@bot 查 peppy 的 bp1
@bot 查 WhiteCat 的 bp 1-20
@bot 查 @群友 的 bp1
@bot 查我在 3783810 这张图上的成绩
@bot 查我 Freedom Dive 这张图打了多少
@bot 查我的 pp 历史
@bot 分析我的 bp 构成
@bot 给我推荐谱面
@bot 发一下我的 osu 主页
@bot 查 match 123456789
@bot 查 match 123456789 的 rating
@bot 预览谱面 3783810
@bot 提取谱面 3783810 的背景
@bot 查成就 Non-stop Dancer
```

账号与模式规则：

- 用户说“我/我的/自己”或未指定玩家时，使用当前发言用户通过 `/bind` 绑定的 osu 账号。
- 消息里 `@群友` 时，优先使用被 @ 群友绑定的 osu 账号。
- 查询绑定用户时会使用绑定记录中的默认模式，官网成绩默认包含 lazer 与 stable 成绩。
- 明确指定 osu 用户名时会查询该玩家并优先使用其 osu! 默认游玩模式；也可以在自然语言里明确指定 `std`、`taiko`、`ctb` 或 `mania` 覆盖默认值。
- 只提供歌名、艺术家、谱师或难度名查询成绩时，AI 会优先匹配准确标题和难度名：只有一个难度有成绩时直接发送成绩图，多个难度有成绩时发送与 BP 列表相同风格的图片列表。
- 按名称查询成绩时也支持直接评价发挥：图片照常发送，AI 使用工具返回的结构化成绩分析，不再回读图片。
- AI 查询 BP 范围或筛选列表时也遵循同一规则：筛选结果只有一条就发送单张成绩图，多条才发送列表图。

如果用户只是要求查询，AI 会调用工具发出图片后结束；如果用户同时要求评价，例如：

```text
@bot 查我的 bp1，我打得怎么样
@bot 分析一下 @群友 的 bp1
@bot 看看我 recent 发挥如何
@bot 评价一下我的 bp1-200
```

评价/分析类请求，工具会直接把 osu API 返回的结构化数据（成绩、玩家资料、pp/rank 历史、推荐谱面、比赛评分等）转成文本返回给 AI，AI 基于这些数据给出评价；图片只作为发给用户的展示物，不作为 AI 的分析数据源。因此即使主聊天模型不支持图片输入（非多模态），也能正常完成分析，无需依赖图片回读。

分析整体 BP（如 bp1-200）时，AI 会先发送 BP 列表图，再分页读取各段 BP 的结构化数据（每次最多 20 条）进行整体评价。


## 💡 贡献

如果遇到任何问题，欢迎提各种issue来反馈bug
你也可以加群(228986744)来进行反馈！
![1665504476458_temp_qrcode_share_9993](https://user-images.githubusercontent.com/30517062/195143643-5c212f4e-5ee2-49fd-8e71-4f360eef2d46.png)
