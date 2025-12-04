"""Helper module to generate activity charts for the dashboard."""

import io
import logging
import matplotlib
# Force non-interactive backend before importing pyplot
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from typing import Dict, Optional
import discord

logger = logging.getLogger("guildscout.chart_generator")

def generate_activity_chart(
    daily_data: Dict[str, int],
    hourly_data: Dict[int, int]
) -> Optional[discord.File]:
    """
    Generate a combined chart image for daily and hourly activity.

    Args:
        daily_data: Dictionary mapping date string (YYYY-MM-DD) to message count
        hourly_data: Dictionary mapping hour (0-23) to total message count

    Returns:
        discord.File object containing the chart image, or None if no data.
    """
    if not daily_data and not hourly_data:
        return None

    try:
        # Set style
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        
        # Color palette
        bar_color = '#5865F2'  # Discord Blurple
        highlight_color = '#EB459E'

        # --- Plot 1: Daily Trend (Last 7 Days) ---
        if daily_data:
            # Sort available data
            sorted_dates = sorted(daily_data.keys())
            start_date_str = sorted_dates[0]
            end_date_str = sorted_dates[-1]
            
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            
            # Fill in missing days with 0
            dates = []
            counts = []
            curr = start_date
            while curr <= end_date:
                d_str = curr.strftime("%Y-%m-%d")
                dates.append(curr)
                counts.append(daily_data.get(d_str, 0))
                curr += timedelta(days=1)

            # If we have fewer than 7 days of data total, pad backwards to show context
            while len(dates) < 7:
                prev_date = dates[0] - timedelta(days=1)
                dates.insert(0, prev_date)
                counts.insert(0, 0)

            # Slice to last 7-14 days max to keep chart readable
            if len(dates) > 14:
                dates = dates[-14:]
                counts = counts[-14:]
            
            ax1.plot(dates, counts, marker='o', color=bar_color, linewidth=2, markersize=6)
            ax1.fill_between(dates, counts, color=bar_color, alpha=0.3)
            
            ax1.set_title("Nachrichten (Verlauf)", fontsize=10, color='white')
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax1.grid(True, linestyle='--', alpha=0.2)
            ax1.tick_params(colors='white')
            
            # Rotate date labels slightly
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha='right')
            
            for spine in ax1.spines.values():
                spine.set_color('#444444')
        else:
            ax1.text(0.5, 0.5, "Keine Daten", ha='center', va='center', color='gray')
            ax1.set_title("Täglicher Trend", fontsize=10)

        # --- Plot 2: Hourly Distribution (Prime Time) ---
        if hourly_data:
            hours = list(range(24))
            # Ensure all hours 0-23 exist
            counts = [hourly_data.get(h, 0) for h in hours]
            
            ax2.bar(hours, counts, color=bar_color, alpha=0.8, width=0.8)
            
            # Highlight peak hour
            if max(counts) > 0:
                peak_hour = hours[counts.index(max(counts))]
                ax2.patches[peak_hour].set_facecolor(highlight_color)
            
            ax2.set_title("Aktivität nach Uhrzeit (UTC)", fontsize=10, color='white')
            ax2.set_xlim(-0.5, 23.5)
            ax2.set_xticks([0, 6, 12, 18])
            ax2.set_xticklabels(['00:00', '06:00', '12:00', '18:00'])
            ax2.grid(axis='y', linestyle='--', alpha=0.2)
            ax2.tick_params(colors='white')
            for spine in ax2.spines.values():
                spine.set_color('#444444')
        else:
            ax2.text(0.5, 0.5, "Keine Daten", ha='center', va='center', color='gray')
            ax2.set_title("Stündliche Aktivität", fontsize=10)

        plt.tight_layout()

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, transparent=False, bbox_inches='tight', facecolor='#2f3136')
        buf.seek(0)
        plt.close(fig)

        return discord.File(buf, filename="activity_chart.png")

    except Exception as e:
        logger.error(f"Failed to generate chart: {e}")
        return None
