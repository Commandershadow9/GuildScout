"""Command modules for GuildScout Bot."""

from .analyze import AnalyzeCommand
from .my_score import MyScoreCommand
from .admin import AdminCommands
from .ranking_channel import RankingChannelCommands
from .assign_guild_role import AssignGuildRoleCommand

__all__ = [
    "AnalyzeCommand",
    "MyScoreCommand",
    "AdminCommands",
    "RankingChannelCommands",
    "AssignGuildRoleCommand"
]
