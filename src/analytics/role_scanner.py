"""Role scanner for finding members with specific roles."""

import logging
from typing import List, Optional, Tuple
import discord


logger = logging.getLogger("guildscout.role_scanner")


class RoleScanner:
    """Scans guild members based on role criteria."""

    def __init__(
        self,
        guild: discord.Guild,
        exclusion_role_ids: Optional[List[int]] = None,
        exclusion_user_ids: Optional[List[int]] = None
    ):
        """
        Initialize the role scanner.

        Args:
            guild: Discord guild to scan
            exclusion_role_ids: Role IDs to exclude (users with these have reserved spots)
            exclusion_user_ids: Specific user IDs to exclude
        """
        self.guild = guild
        self.exclusion_role_ids = exclusion_role_ids or []
        self.exclusion_user_ids = exclusion_user_ids or []

    def _is_excluded(self, member: discord.Member) -> Tuple[bool, Optional[str]]:
        """
        Check if a member should be excluded from ranking.

        Args:
            member: Member to check

        Returns:
            Tuple of (is_excluded, reason)
        """
        # Check if user ID is in exclusion list
        if member.id in self.exclusion_user_ids:
            return True, "Manual reservation (User ID)"

        # Check if user has any exclusion roles
        member_role_ids = [role.id for role in member.roles]
        for exclusion_role_id in self.exclusion_role_ids:
            if exclusion_role_id in member_role_ids:
                # Find role name for logging
                role = self.guild.get_role(exclusion_role_id)
                role_name = role.name if role else f"Role ID {exclusion_role_id}"
                return True, f"Has reserved spot role (@{role_name})"

        return False, None

    async def get_members_with_role(
        self,
        role: discord.Role,
        exclude_bots: bool = True,
        apply_exclusions: bool = True
    ) -> Tuple[List[discord.Member], List[dict]]:
        """
        Get all members with a specific role.

        Args:
            role: Discord role to filter by
            exclude_bots: Whether to exclude bot accounts
            apply_exclusions: Whether to apply exclusion filtering

        Returns:
            Tuple of (members_list, excluded_members_list)
            - members_list: Members to rank
            - excluded_members_list: List of dicts with excluded member info
        """
        logger.info(f"Scanning members with role: {role.name} (ID: {role.id})")

        members = []
        excluded = []

        for member in self.guild.members:
            # Skip bots if requested
            if exclude_bots and member.bot:
                continue

            # Check if member has the role
            if role in member.roles:
                # Check if member should be excluded
                if apply_exclusions:
                    is_excluded, reason = self._is_excluded(member)
                    if is_excluded:
                        excluded.append({
                            "member": member,
                            "name": member.display_name,
                            "id": member.id,
                            "reason": reason
                        })
                        logger.info(
                            f"Excluding {member.name} from ranking: {reason}"
                        )
                        continue

                members.append(member)

        logger.info(
            f"Found {len(members)} members with role {role.name} "
            f"({len(excluded)} excluded - already have spots)"
        )
        return members, excluded

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
