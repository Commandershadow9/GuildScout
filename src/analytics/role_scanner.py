"""Role scanner for finding members with specific roles."""

import logging
from typing import List
import discord


logger = logging.getLogger("guildscout.role_scanner")


class RoleScanner:
    """Scans guild members based on role criteria."""

    def __init__(self, guild: discord.Guild):
        """
        Initialize the role scanner.

        Args:
            guild: Discord guild to scan
        """
        self.guild = guild

    async def get_members_with_role(
        self,
        role: discord.Role,
        exclude_bots: bool = True
    ) -> List[discord.Member]:
        """
        Get all members with a specific role.

        Args:
            role: Discord role to filter by
            exclude_bots: Whether to exclude bot accounts

        Returns:
            List of members with the specified role
        """
        logger.info(f"Scanning members with role: {role.name} (ID: {role.id})")

        members = []
        for member in self.guild.members:
            # Skip bots if requested
            if exclude_bots and member.bot:
                continue

            # Check if member has the role
            if role in member.roles:
                members.append(member)

        logger.info(f"Found {len(members)} members with role {role.name}")
        return members

    async def get_members_by_role_name(
        self,
        role_name: str,
        exclude_bots: bool = True
    ) -> List[discord.Member]:
        """
        Get all members with a role by name.

        Args:
            role_name: Name of the role to filter by
            exclude_bots: Whether to exclude bot accounts

        Returns:
            List of members with the specified role

        Raises:
            ValueError: If role not found
        """
        # Find role by name
        role = discord.utils.get(self.guild.roles, name=role_name)

        if role is None:
            raise ValueError(f"Role '{role_name}' not found in guild")

        return await self.get_members_with_role(role, exclude_bots)

    async def get_members_by_role_id(
        self,
        role_id: int,
        exclude_bots: bool = True
    ) -> List[discord.Member]:
        """
        Get all members with a role by ID.

        Args:
            role_id: ID of the role to filter by
            exclude_bots: Whether to exclude bot accounts

        Returns:
            List of members with the specified role

        Raises:
            ValueError: If role not found
        """
        # Find role by ID
        role = self.guild.get_role(role_id)

        if role is None:
            raise ValueError(f"Role with ID {role_id} not found in guild")

        return await self.get_members_with_role(role, exclude_bots)
