<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-osubot

_✨ NoneBot osubot ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/yaowan233/nonebot-plugin-osubot.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-osubot">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-osubot.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">

</div>


## 📖 介绍

本项目修改自[osuv2](https://github.com/Yuri-YuzuChaN/osuv2)，适配了nonebot2，并且在此之上修改了命令的响应逻辑并修改了一些bug使之更易于使用 

## 💿 安装

<details>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-osubot

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-osubot
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-osubot
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-osubot
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-osubot
</details>

打开 nonebot2 项目的 `bot.py` 文件, 在其中写入

    nonebot.load_plugin('nonebot_plugin_osubot')

</details>

<details>
<summary>从 github 安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 输入以下命令克隆此储存库

    git clone https://github.com/yaowan233/nonebot-plugin-osubot.git

打开 nonebot2 项目的 `bot.py` 文件, 在其中写入

    nonebot.load_plugin('src.plugins.nonebot_plugin_osubot')

</details>

## ⚙️ 配置
你需要至[OSU个人设置](https://osu.ppy.sh/home/account/edit)申请新的OAuth应用，然后将得到的客户端ID与客户端密钥填入nonebot2 项目的`.env`文件中

配置说明
| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| OSU_CLIENT | 是 | 无 | 客户端ID |
| OSU_KEY | 是 | 无 | 客户端密钥 |
| DB_URL | 否 | sqlite://db.sqlite3 | 数据库地址 |

## 🎉 使用
### 指令表
| 指令    | 功能                 | 可选参数                           | 说明                                 |
| :------ | :------------------- | :--------------------------------- | :----------------------------------- |
| osuhelp | 查看指令大全         |                                    |                                      |
| info    | 查询信息             | 无                                 | 查询自己                             |
|         |                      | [user]                             | 查询TA人                             |
|         |                      | :[mode]                            | 查询自己其它模式，`:`为触发词        |
|         |                      | [user] :[mode]                     | 查询TA人其它模式                     |
| bind    | 绑定                 | [user]                             | 绑定用户名                           |
| unbind  | 解绑                 | 无                                 |                                      |
| update  | 更改或更新           | mode [mode]                        | 更改模式                             |
| recent(pr)| 查询最近(不)包含死亡的游玩记录     | 无                     | 查询自己最近(不)包含死亡的游玩记录               |
|         |                      | [user]                             | 查询TA人最近(不)包含死亡的游玩记录               |
|         |                      | :[mode]                            | 查询自己最近游玩其它模式(不)包含死亡记录         |
|         |                      | [user] :[mode]                     | 查询TA人最近游玩其它模式(不)包含死亡记录         |
| score   | 查询成绩             | [mapid]                            | 查询该地图成绩                       |
|         |                      | [mapid] +[mods]                    | 查询该地图附加mods成绩               |
|         |                      | [mapid] :[mode]                    | 查询该地图其它模式成绩               |
|         |                      | [mapid] :[mode] +[mods]            | 查询该地图其它模式加mods的成绩       |
|         |                      | [user] [mapid]                     | 查询TA人该地图成绩                   |
|         |                      | [user] [mapid] :[mode]             | 查询TA人该地图其它模式成绩           |
|         |                      | [user] [mapid] +[mods]             | 查询TA人该地图加mods的成绩           |
|         |                      | [user] [mapid] :[mode] +[mods]     | 查询TA人该地图其它模式加mods的成绩   |
| bp      | 查询bp榜成绩         | [num]                              | 查询bp成绩                           |
|         |                      | [num] +[mods]                      | 查询bp附加mods成绩                   |
|         |                      | [num] :[mode]                      | 查询其他模式的bp成绩                 |
|         |                      | [num] :[mode] +[mods]              | 查询其他模式加mods的bp成绩           |
|         |                      | [user] [num]                       | 查询TA人bp成绩                       |
|         |                      | [user] [num] +[mods]               | 查询TA人bp附加mods成绩               |
|         |                      | [user] [num] :[mode]               | 查询TA人其他模式bp成绩               |
|         |                      | [user] [num] :[mode] +[mods]       | 查询TA人其他模式加mods的bp成绩       |
| pfm     | 查询bp榜指定范围成绩 | [min]-[max]                        | 查询bp范围内成绩，最多10个           |
|         |                      | [min]-[max] :[mode]                | 查询其它模式bp范围内成绩             |
|         |                      | [min]-[max] +[mods]                | 查询bp范围内加mods的成绩             |
|         |                      | [min]-[max] :[mode] +[mods]        | 查询其它模式bp范围内加mods的成绩     |
|         |                      | [user] [min]-[max]                 | 查询TA人bp，最多10个                 |
|         |                      | [user] [min]-[max] :[mode]         | 查询TA人其它模式bp                   |
|         |                      | [user] [min]-[max] +[mods]         | 查询TA人bp                           |
|         |                      | [user] [min]-[max] :[mode] +[mods] | 查询TA人其它模式bp范围内加mods的成绩 |
| tbp     | 查询当天新增bp成绩   | 无                                 | 查询自己当天新增bp成绩               |
|         |                      | [user]                             | 查询TA人当天新增bp成绩               |
|         |                      | :[mode]                            | 查询自己其它模式当天新增bp成绩       |
|         |                      | [user] :[mode]                     | 查询TA人其它模式当天新增bp成绩       |
| map     | 查询地图信息         | [mapid]                            | 查询地图信息                         |
|         |                      | [mapid] +[mods]                    | 查询地图加mod的信息，仅计算PP        |
| getbg   | 提取背景             | [mapid]                            | 提取地图背景                         |
| bmap    | 查询图组信息         | [setid]                            | 查询图组信息                         |
|         |                      | -b [mapid]                         | 使用地图id查询图组信息               |
| osudl   | 下载地图上传到群     | [setid]                            | 下载地图，`setid`为图组id，非单图id  |

*`[]`内为需要填的参数

*`mode`：0-3分别为std，taiko，ctb，mania

## 💡 贡献
由于当前开发缺乏测试，欢迎提各种issue来反馈bug
或者你可以加群(228986744)来直接反馈！
![1665504476458_temp_qrcode_share_9993](https://user-images.githubusercontent.com/30517062/195143643-5c212f4e-5ee2-49fd-8e71-4f360eef2d46.png)
