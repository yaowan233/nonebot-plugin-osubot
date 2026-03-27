from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from nonebot_plugin_orm import Model


class UserData(Model):
    __tablename__ = "User"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, index=True)
    osu_id: Mapped[int] = mapped_column(Integer)
    osu_name: Mapped[str] = mapped_column(Text)
    osu_mode: Mapped[int] = mapped_column(Integer)
    lazer_mode: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)


class InfoData(Model):
    __tablename__ = "Info"

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
    __tablename__ = "SbUser"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, index=True)
    osu_id: Mapped[int] = mapped_column(Integer)
    osu_name: Mapped[str] = mapped_column(Text)
