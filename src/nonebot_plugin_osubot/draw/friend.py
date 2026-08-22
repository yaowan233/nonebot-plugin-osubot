"""好友列表面板渲染（Jinja2 + Playwright，风格与 rating 一致）。

性能优化：头像优先使用本地磁盘缓存（data/osu/user/{uid}/icon.png），
渲染时内联为 base64 data URI，避免每次 /f 都从 osu! 服务器现场下载全部头像。
"""

import asyncio
import base64
import time
from io import BytesIO
from pathlib import Path

import jinja2
from PIL import Image

from ..api import safe_async_get
from ..file import user_cache_path
from .browser import persistent_page

# 头像并发下载上限（避免打爆网络 / 触发 osu! 限流）
_avatar_sem = asyncio.Semaphore(8)
# 头像缓存有效期：7 天
_AVATAR_TTL = 7 * 24 * 3600
# 头像渲染目标尺寸（模板中显示 60px 圆形，64px 足够）
_AVATAR_SIZE = 64


async def _load_avatar_data_uri(uid: int, url: str) -> str:
    """获取好友头像并返回 data URI；优先本地缓存，缺失时下载并缓存。

    下载失败时回退原始 URL（浏览器自行加载，功能不受影响）。
    """
    cache_dir = user_cache_path / str(uid)
    cache_file = cache_dir / "icon.png"

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
        # 网络异常时回退原 URL，保证图片仍能显示（只是慢一点）
        return url


async def _prepare_avatars(friends: list[dict]) -> list[dict]:
    """并发加载全部好友头像（本地缓存优先），返回替换为 data URI 的副本。"""
    if not friends:
        return friends
    avatars = await asyncio.gather(*[_load_avatar_data_uri(f["uid"], f["avatar"]) for f in friends])
    return [{**f, "avatar": av} for f, av in zip(friends, avatars)]


async def draw_friend_list(data: dict) -> bytes:
    template_path = Path(__file__).parent / "friend_templates"
    template = jinja2.Environment(  # noqa: S701
        loader=jinja2.FileSystemLoader(str(template_path)), enable_async=True
    ).get_template("index.html")

    # 头像本地化：并发加载 + base64 内联，避免浏览器现场下载几十上百张头像
    data = {**data, "friends": await _prepare_avatars(data.get("friends") or [])}

    async with persistent_page(
        "friend", (template_path / "index.html").as_uri(), {"width": 1280, "height": 900}
    ) as page:
        await page.set_content(await template.render_async(**data), wait_until="domcontentloaded")
        await page.evaluate(
            "Promise.race([Promise.all([document.fonts.ready,"
            "...Array.from(document.images,x=>x.decode().catch(()=>{}))]),"
            "new Promise(resolve=>setTimeout(resolve,8000))])"
        )
        element = await page.query_selector(".card")
        assert element
        return await element.screenshot(type="png")
