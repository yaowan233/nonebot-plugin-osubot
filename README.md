<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-osubot

_✨ NoneBot osubot ✨_


<a href="./License">
    <img src="https://img.shields.io/github/license/yaowan233/nonebot-plugin-osubot.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-osubot">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-osubot.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">

</div>


## 📖 介绍

本项目修改自[osuv2](https://github.com/Yuri-YuzuChaN/osuv2)，适配了nonebot2，并且在此之上修改了命令的响应逻辑并修改了一些bug使之更易于使用

变速功能依赖ffmpeg，需要[自行安装ffmpeg](https://docs.go-cqhttp.org/guide/quick_start.html#%E5%AE%89%E8%A3%85-ffmpeg)才能正常使用

## 💿 安装

<details>
<summary>使用 nb-cli 安装（推荐）</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-osubot

</details>

<details>
<summary>使用包管理器安装（推荐）</summary>
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


打开 nonebot2 项目的 `bot.py` 文件, 在其中写入

    nonebot.load_plugin('nonebot_plugin_osubot')

</details>

<details>
<summary>从 github 安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 输入以下命令克隆此储存库

    git clone https://github.com/yaowan233/nonebot-plugin-osubot.git

修改[nonebot_plugin_osubot的__init__.py](https://github.com/yaowan233/nonebot-plugin-osubot/blob/a7c7098f39d92b8fe74dfe85c262397b81db721c/nonebot_plugin_osubot/__init__.py#L37)为
  
    add_model('src.plugins.database.models')
  
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
| SQLALCHEMY_DATABASE_URL | 否 | sqlite+aiosqlite:///db.sqlite3 | 数据库地址，详见 [NoneBot 数据库配置](https://nonebot.dev/docs/best-practice/database/) |
| INFO_BG | 否 | ['https://example.com'] | 随机背景api地址，需要打开网页后随机获得一张图片 |

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

3. 升级插件后重启 bot

## 🎉 使用
### 指令

![image](https://github.com/yaowan233/nonebot-plugin-osubot/assets/30517062/41fd8326-7b97-4de9-be83-c38b31453ea1)


## 💡 贡献

如果遇到任何问题，欢迎提各种issue来反馈bug
你也可以加群(228986744)来进行反馈！
![1665504476458_temp_qrcode_share_9993](https://user-images.githubusercontent.com/30517062/195143643-5c212f4e-5ee2-49fd-8e71-4f360eef2d46.png)
