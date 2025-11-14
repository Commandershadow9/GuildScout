"""Test script to verify all imports work correctly."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    try:
        # Test utils
        from src.utils import Config, setup_logger
        print("✓ Utils imported successfully")

        # Test analytics
        from src.analytics import RoleScanner, ActivityTracker, Scorer, Ranker, UserScore
        print("✓ Analytics imported successfully")

        # Test exporters
        from src.exporters import DiscordExporter, CSVExporter
        print("✓ Exporters imported successfully")

        # Test commands
        from src.commands import AnalyzeCommand
        print("✓ Commands imported successfully")

        print("\n✅ All imports successful!")
        return True

    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        return False


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
