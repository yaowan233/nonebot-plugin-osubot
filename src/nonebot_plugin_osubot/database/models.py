from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Index, Integer, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from nonebot_plugin_orm import Model


class UserData(Model):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, index=True)
    osu_id: Mapped[int] = mapped_column(Integer)
    osu_name: Mapped[str] = mapped_column(Text)
    osu_mode: Mapped[int] = mapped_column(Integer)
    # 已弃用：仅保留该列以兼容现有数据库，查询逻辑不再读取它。
    lazer_mode: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)


class InfoData(Model):
    __table_args__ = (
        Index(
            "ix_nonebot_plugin_osubot_infodata_lookup",
            "osu_id",
            "osu_mode",
            "date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    osu_id: Mapped[int] = mapped_column(Integer)
    c_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    g_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pp: Mapped[float] = mapped_column(Float)
    acc: Mapped[float] = mapped_column(Float)
    pc: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)
    osu_mode: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date)
    ranked_score: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_score: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    max_combo: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    count_xh: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    count_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    count_sh: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    count_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    count_a: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    replays: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    play_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    badge_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class SbUserData(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, index=True)
    osu_id: Mapped[int] = mapped_column(Integer)
    osu_name: Mapped[str] = mapped_column(Text)


class G0v0UserData(Model):
    """g0v0（咕哦服）服务器绑定表：/gubind 绑定，查询末尾 &gu 后缀使用。"""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, index=True)
    osu_id: Mapped[int] = mapped_column(Integer)
    osu_name: Mapped[str] = mapped_column(Text)
    # g0v0 独立默认模式（0-8，SB 风格：4=RX std 5=RX taiko 6=RX catch 8=AP std），
    # 与官方绑定的默认模式互不影响；/mode:4 &gu 修改。
    osu_mode: Mapped[int] = mapped_column(Integer, default=0)


class ScoreHistoryData(Model):
    """A compact, selective archive of scores unavailable from beatmap leaderboards."""

    __table_args__ = (
        Index(
            "ix_nonebot_plugin_osubot_scorehistory_lookup",
            "user_id",
            "beatmap_id",
            "ruleset_id",
            "ended_at",
        ),
    )

    score_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    beatmap_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ruleset_id: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class UserOAuthData(Model):
    """每个绑定用户的 osu! OAuth 用户级令牌（/friend 好友功能使用）。"""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, unique=True, index=True)  # 平台用户 ID
    osu_id: Mapped[int] = mapped_column(Integer)
    osu_name: Mapped[str] = mapped_column(Text)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
