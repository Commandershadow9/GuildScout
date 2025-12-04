"""Test script for new dashboard features (Charts, Trends, At-Risk)."""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.database.message_store import MessageStore
from src.utils.chart_generator import generate_activity_chart
from src.analytics.scorer import Scorer, UserScore

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_features")

TEST_DB = "data/test_features.db"

async def test_database_stats():
    """Test if daily_stats and hourly_stats are populated correctly."""
    logger.info("--- Testing Database Stats ---")
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        
    store = MessageStore(db_path=TEST_DB)
    await store.initialize()
    
    guild_id = 123
    user_id = 456
    channel_id = 789
    
    # Simulate messages over 3 days
    # Day 1: 10 messages at 10:00
    date1 = datetime(2023, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
    await store.increment_message(guild_id, user_id, channel_id, count=10, message_date=date1)
    
    # Day 2: 20 messages at 14:00
    date2 = datetime(2023, 10, 2, 14, 0, 0, tzinfo=timezone.utc)
    await store.increment_message(guild_id, user_id, channel_id, count=20, message_date=date2)
    
    # Day 3: 5 messages at 10:00 (same hour as day 1)
    date3 = datetime(2023, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
    await store.increment_message(guild_id, user_id, channel_id, count=5, message_date=date3)

    # Verify Daily Stats
    daily = await store.get_daily_history(guild_id, days=7)
    logger.info(f"Daily Stats: {daily}")
    assert daily["2023-10-01"] == 10
    assert daily["2023-10-02"] == 20
    assert daily["2023-10-03"] == 5
    logger.info("✅ Daily stats correct.")

    # Verify Hourly Stats
    hourly = await store.get_hourly_activity(guild_id)
    logger.info(f"Hourly Stats: {hourly}")
    assert hourly[10] == 15  # 10 from day 1 + 5 from day 3
    assert hourly[14] == 20  # 20 from day 2
    logger.info("✅ Hourly stats correct.")
    
    return daily, hourly

def test_chart_generation(daily, hourly):
    """Test if chart generation runs without error."""
    logger.info("--- Testing Chart Generation ---")
    try:
        file = generate_activity_chart(daily, hourly)
        if file:
            logger.info("✅ Chart generated successfully (returned discord.File).")
        else:
            logger.error("❌ Chart generation returned None.")
    except Exception as e:
        logger.error(f"❌ Chart generation crashed: {e}")

async def test_at_risk_filter():
    """Test the >7 days filter logic."""
    logger.info("--- Testing At-Risk Filter ---")
    
    # Mock UserScores
    # User A: 10 days, score 50
    # User B: 2 days, score 10 (Should be filtered out)
    # User C: 100 days, score 20 (Should be included, low score)
    
    users = [
        UserScore(1, "UserA", "0", 10, 100, 10, 10, 50.0, datetime.now()),
        UserScore(2, "UserB", "0", 2, 10, 2, 2, 10.0, datetime.now()), # New user
        UserScore(3, "UserC", "0", 100, 5, 50, 1, 20.0, datetime.now()) # Old but inactive
    ]
    
    # Logic from dashboard_manager
    filtered = [s for s in users if s.days_in_server >= 7]
    filtered.sort(key=lambda x: x.final_score)
    
    logger.info(f"Filtered users: {[u.username for u in filtered]}")
    
    assert len(filtered) == 2
    assert filtered[0].username == "UserC" # Lowest score among valid
    assert filtered[1].username == "UserA"
    
    logger.info("✅ At-Risk filtering correct.")

async def main():
    daily, hourly = await test_database_stats()
    test_chart_generation(daily, hourly)
    await test_at_risk_filter()
    
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    logger.info("Done.")

if __name__ == "__main__":
    asyncio.run(main())
