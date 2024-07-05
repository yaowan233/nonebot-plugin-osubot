from typing import Optional

from tortoise import Model, fields


class UserData(Model):
    id: int = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增主键"""
    user_id: int = fields.BigIntField()
    """用户id"""
    osu_id: int = fields.IntField()
    """osu id"""
    osu_name: str = fields.TextField()
    """osu 用户名"""
    osu_mode: int = fields.IntField()
    """osu 模式"""
    lazer_mode: bool = fields.BooleanField(default=False, null=True)
    """是否启用lazer模式"""

    class Meta:
        table = "User"
        indexes = ("user_id",)


class InfoData(Model):
    id: int = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增主键"""
    osu_id: int = fields.IntField()
    """osu id"""
    c_rank: Optional[int] = fields.IntField(null=True)
    """国家排名"""
    g_rank: Optional[int] = fields.IntField(null=True)
    """世界排名"""
    pp: float = fields.FloatField()
    """pp"""
    acc: float = fields.FloatField()
    """acc"""
    pc: int = fields.IntField()
    """游戏次数"""
    count: int = fields.IntField()
    """打击note数"""
    osu_mode: int = fields.IntField()
    """osu 模式"""
    date = fields.DateField()

    class Meta:
        table = "Info"
        indexes = ("id",)
