"""好友列表面板渲染（原生 SVG + resvg，视觉基准为 friend_templates/index.html）。

头像优先使用专用本地磁盘缓存（data/osu/user/{uid}/friend-avatar-64.png），
渲染时内联为 base64 data URI，避免每次 /f 都从 osu! 服务器现场下载全部头像；
离线好友头像按设计稿做降饱和/降亮度处理。下载失败时使用本地占位图，
保证没有网络等待也能出图。
"""

import asyncio
import base64
import time
from io import BytesIO
from functools import lru_cache

from PIL import Image, ImageEnhance

from ..api import safe_async_get
from ..file import user_cache_path
from .friend_svg import render_friend_svg

# 头像并发下载上限（避免打爆网络 / 触发 osu! 限流）
_avatar_sem = asyncio.Semaphore(8)
# 头像缓存有效期：7 天
_AVATAR_TTL = 7 * 24 * 3600
# 头像渲染目标尺寸（模板中显示 62px 圆形，64px 足够）
_AVATAR_SIZE = 64
_AVATAR_CACHE_NAME = "friend-avatar-64.png"


@lru_cache(maxsize=1)
def _placeholder_avatar_data_uri() -> str:
    """头像下载失败时的本地占位图（纯色，圆形裁切由 SVG 负责）。"""
    img = Image.new("RGBA", (_AVATAR_SIZE, _AVATAR_SIZE), "#26323d")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


async def _load_avatar_data_uri(uid: int, url: str) -> str:
    """获取好友头像并返回 data URI；优先本地缓存，缺失时下载并缓存。

    下载失败时回退本地占位图：resvg 不会抓取远程 URL，
    不能像浏览器那样把原 URL 留给渲染端兜底。
    """
    cache_dir = user_cache_path / str(uid)
    cache_file = cache_dir / _AVATAR_CACHE_NAME

    # ── 命中缓存且在有效期内 → 直接读文件 ──
    if cache_file.exists():
        try:
            if time.time() - cache_file.stat().st_mtime < _AVATAR_TTL:
                data = cache_file.read_bytes()
                return f"data:image/png;base64,{base64.b64encode(data).decode()}"
        except Exception:
            pass

    # ── 缓存缺失/过期 → 下载 → 统一转 PNG 缩放 → 写缓存 ──
    try:
        async with _avatar_sem:
            req = await safe_async_get(url)
        if not req or req.status_code >= 400:
            raise RuntimeError(f"头像下载失败: HTTP {req.status_code if req else 'None'}")
        img = Image.open(BytesIO(req.content)).convert("RGBA")
        img.thumbnail((_AVATAR_SIZE, _AVATAR_SIZE))
        buf = BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(data)
        except Exception:
            pass
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    except Exception:
        return _placeholder_avatar_data_uri()


def _dim_avatar(data_uri: str) -> str:
    """离线好友头像降饱和/降亮度（设计稿 saturate(.55) brightness(.8) 的 Pillow 等价）。"""
    try:
        encoded = data_uri.split(",", 1)[1]
        with Image.open(BytesIO(base64.b64decode(encoded))) as source:
            img = source.convert("RGBA")
        img = ImageEnhance.Color(img).enhance(0.55)
        img = ImageEnhance.Brightness(img).enhance(0.8)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return data_uri


async def _prepare_avatars(friends: list[dict]) -> list[dict]:
    """并发加载全部好友头像（本地缓存优先），离线好友头像做降饱和处理。"""
    if not friends:
        return friends
    avatars = await asyncio.gather(*[_load_avatar_data_uri(f["uid"], f["avatar"]) for f in friends])
    return [{**f, "avatar": avatar if f.get("online") else _dim_avatar(avatar)} for f, avatar in zip(friends, avatars)]


async def draw_friend_list(data: dict) -> bytes:
    friends = await _prepare_avatars(data.get("friends") or [])
    me_avatar = data.get("me_avatar") or ""
    if data.get("me_uid") and me_avatar:
        me_avatar = await _load_avatar_data_uri(int(data["me_uid"]), me_avatar)
    return await render_friend_svg({**data, "me_avatar": me_avatar, "friends": friends})
