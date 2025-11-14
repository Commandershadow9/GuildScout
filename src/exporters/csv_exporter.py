"""CSV exporter for ranking data."""

import logging
import pandas as pd
from pathlib import Path
from typing import List
from datetime import datetime


logger = logging.getLogger("guildscout.csv_exporter")


class CSVExporter:
    """Exports ranking data to CSV files."""

    def __init__(
        self,
        export_dir: str = "exports",
        delimiter: str = ",",
        encoding: str = "utf-8-sig"
    ):
        """
        Initialize the CSV exporter.

        Args:
            export_dir: Directory to save CSV files
            delimiter: CSV delimiter character
            encoding: File encoding
        """
        self.export_dir = Path(export_dir)
        self.delimiter = delimiter
        self.encoding = encoding

        # Create export directory if it doesn't exist
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_ranking(
        self,
        ranked_users: List[tuple],
        role_name: str,
        filename: str = None
    ) -> str:
        """
        Export ranking to CSV file.

        Args:
            ranked_users: List of (rank, UserScore) tuples
            role_name: Name of the role analyzed
            filename: Optional custom filename (without extension)

        Returns:
            Path to the created CSV file
        """
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"guildscout_{role_name}_{timestamp}"

        # Ensure .csv extension
        if not filename.endswith(".csv"):
            filename += ".csv"

        filepath = self.export_dir / filename

        # Prepare data for DataFrame
        data = []
        for rank, score in ranked_users:
            data.append({
                "Rank": rank,
                "Username": score.display_name,
                "User_ID": score.user_id,
                "Final_Score": score.final_score,
                "Days_Score": score.days_score,
                "Activity_Score": score.activity_score,
                "Days_in_Server": score.days_in_server,
                "Message_Count": score.message_count,
                "Join_Date": score.join_date.strftime("%Y-%m-%d %H:%M:%S")
            })

        # Create DataFrame
        df = pd.DataFrame(data)

        # Export to CSV
        df.to_csv(
            filepath,
            index=False,
            sep=self.delimiter,
            encoding=self.encoding
        )

        logger.info(f"Exported {len(data)} users to {filepath}")
        return str(filepath)

    def export_with_stats(
        self,
        ranked_users: List[tuple],
        role_name: str,
        stats: dict,
        scoring_info: dict,
        filename: str = None
    ) -> str:
        """
        Export ranking with additional statistics sheet.

        Args:
            ranked_users: List of (rank, UserScore) tuples
            role_name: Name of the role analyzed
            stats: Statistics dictionary
            scoring_info: Scoring configuration
            filename: Optional custom filename

        Returns:
            Path to the created file
        """
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"guildscout_{role_name}_{timestamp}"

        # For Excel files with multiple sheets
        if filename.endswith(".xlsx"):
            filepath = self.export_dir / filename
        else:
            # For CSV, just use regular export
            return self.export_ranking(ranked_users, role_name, filename)

        # Prepare ranking data
        ranking_data = []
        for rank, score in ranked_users:
            ranking_data.append({
                "Rank": rank,
                "Username": score.display_name,
                "User_ID": score.user_id,
                "Final_Score": score.final_score,
                "Days_Score": score.days_score,
                "Activity_Score": score.activity_score,
                "Days_in_Server": score.days_in_server,
                "Message_Count": score.message_count,
                "Join_Date": score.join_date.strftime("%Y-%m-%d %H:%M:%S")
            })

        # Prepare stats data
        stats_data = [{
            "Metric": "Total Users",
            "Value": stats["total_users"]
        }, {
            "Metric": "Average Score",
            "Value": stats["avg_score"]
        }, {
            "Metric": "Average Days",
            "Value": stats["avg_days"]
        }, {
            "Metric": "Average Messages",
            "Value": stats["avg_messages"]
        }, {
            "Metric": "Max Score",
            "Value": stats["max_score"]
        }, {
            "Metric": "Min Score",
            "Value": stats["min_score"]
        }, {
            "Metric": "Days Weight",
            "Value": f"{scoring_info['weight_days']:.1%}"
        }, {
            "Metric": "Messages Weight",
            "Value": f"{scoring_info['weight_messages']:.1%}"
        }]

        # Create DataFrames
        df_ranking = pd.DataFrame(ranking_data)
        df_stats = pd.DataFrame(stats_data)

        # Export to Excel with multiple sheets
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df_ranking.to_excel(writer, sheet_name="Rankings", index=False)
            df_stats.to_excel(writer, sheet_name="Statistics", index=False)

        logger.info(f"Exported {len(ranking_data)} users to {filepath}")
        return str(filepath)
