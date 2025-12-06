"""
Rank Card Generator for GuildScout.
Creates visual score cards using Pillow (PIL).
"""

import logging
import io
import math
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import discord
import aiohttp

logger = logging.getLogger("guildscout.rank_card")

class RankCardGenerator:
    """Generates a PNG rank card for a user."""

    def __init__(self):
        # Modern Dark Theme Palette
        self.COLOR_BG_START = (20, 20, 24) 
        self.COLOR_BG_END = (35, 37, 45)
        self.COLOR_OVERLAY = (0, 0, 0, 100)
        self.COLOR_TEXT_MAIN = (255, 255, 255)
        self.COLOR_TEXT_SUB = (170, 175, 185)
        
        # Accent Colors
        self.COLOR_ACCENT = (88, 101, 242) # Discord Blurple
        self.COLOR_MSG = (87, 242, 135)    # Green
        self.COLOR_VOICE = (235, 69, 158)  # Pink
        self.COLOR_DAYS = (88, 101, 242)   # Blue
        
        self.COLOR_BAR_BG = (50, 53, 59)

    async def generate_card(
        self, 
        user: discord.User, 
        score_data: dict, 
        rank: int, 
        total_users: int
    ) -> io.BytesIO:
        """
        Generate the rank card image.
        """
        try:
            # Canvas (900x450) - More vertical space for separation
            W, H = 900, 450
            image = Image.new("RGB", (W, H), self.COLOR_BG_START)
            draw = ImageDraw.Draw(image)

            # 1. Background Gradient & Pattern
            self._draw_background(image, W, H)
            
            # 2. Load Fonts
            try:
                font_name = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
                font_rank = ImageFont.truetype("DejaVuSans.ttf", 28)
                font_stat_label = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
                font_stat_val = ImageFont.truetype("DejaVuSans.ttf", 18)
                font_score_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
                font_score_label = ImageFont.truetype("DejaVuSans.ttf", 22)
            except:
                font_name = ImageFont.load_default()
                font_rank = ImageFont.load_default()
                font_stat_label = ImageFont.load_default()
                font_stat_val = ImageFont.load_default()
                font_score_big = ImageFont.load_default()
                font_score_label = ImageFont.load_default()

            # 3. Avatar (Top Left)
            avatar_size = 140
            avatar_x, avatar_y = 50, 50
            
            avatar_bytes = await self._get_avatar_bytes(user)
            if avatar_bytes:
                with Image.open(io.BytesIO(avatar_bytes)) as avatar_img:
                    avatar_img = avatar_img.convert("RGBA").resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (avatar_size, avatar_size), 0)
                    draw_mask = ImageDraw.Draw(mask)
                    draw_mask.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    image.paste(avatar_img, (avatar_x, avatar_y), mask)
                    
                    # Avatar Ring
                    self._draw_ring(draw, avatar_x + avatar_size//2, avatar_y + avatar_size//2, avatar_size//2 + 4, 4, 1.0, self.COLOR_ACCENT)

            # 4. User Info (Right of Avatar)
            info_x = 230
            draw.text((info_x, 70), str(user.name), font=font_name, fill=self.COLOR_TEXT_MAIN)
            
            percentile = (1 - (rank - 1) / total_users) * 100 if total_users > 1 else 100
            rank_text = f"Rank #{rank}  •  Top {percentile:.1f}%"
            draw.text((info_x, 130), rank_text, font=font_rank, fill=self.COLOR_TEXT_SUB)

            # 5. Score Circle (Top Right)
            circle_x, circle_y = 780, 120
            radius = 80
            thickness = 18
            score = score_data.get('final_score', 0)
            
            # Background Ring
            self._draw_ring(draw, circle_x, circle_y, radius, thickness, 1.0, (40, 40, 40))
            # Progress Ring
            self._draw_ring(draw, circle_x, circle_y, radius, thickness, score/100, self.COLOR_MSG if score > 50 else self.COLOR_ACCENT)
            
            # Score Text
            txt = f"{int(score)}"
            try:
                w = font_score_big.getlength(txt)
            except:
                w = 50
            draw.text((circle_x - w/2, circle_y - 40), txt, font=font_score_big, fill=self.COLOR_TEXT_MAIN)
            draw.text((circle_x - 20, circle_y + 20), "PTS", font=font_score_label, fill=self.COLOR_TEXT_SUB)

            # 6. Stats Area (Bottom Section)
            # Draw a semi-transparent container
            overlay = Image.new("RGBA", (W - 60, 180), (0, 0, 0, 60))
            image.paste(overlay, (30, 240), overlay)
            
            # Stats Configuration
            stats_y_start = 265
            bar_height = 16
            bar_width_total = 550
            label_x = 60
            bar_x = 200
            val_x = 780
            
            spacing = 50

            # Messages
            self._draw_stat_line(draw, label_x, bar_x, val_x, stats_y_start, 
                               "MESSAGES", self.COLOR_MSG, 
                               score_data.get('message_score', 0), 
                               font_stat_label, font_stat_val, bar_width_total, bar_height)

            # Voice
            self._draw_stat_line(draw, label_x, bar_x, val_x, stats_y_start + spacing, 
                               "VOICE", self.COLOR_VOICE, 
                               score_data.get('voice_score', 0), 
                               font_stat_label, font_stat_val, bar_width_total, bar_height)

            # Days
            self._draw_stat_line(draw, label_x, bar_x, val_x, stats_y_start + spacing * 2, 
                               "LOYALTY", self.COLOR_DAYS, 
                               score_data.get('days_score', 0), 
                               font_stat_label, font_stat_val, bar_width_total, bar_height)

            # Finalize
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer

        except Exception as e:
            logger.error(f"Failed to generate rank card: {e}", exc_info=True)
            return None

    def _draw_stat_line(self, draw, lx, bx, vx, y, label, color, score, font_l, font_v, bw, bh):
        """Helper to draw one row of stats."""
        # Label
        draw.text((lx, y - 5), label, font=font_l, fill=self.COLOR_TEXT_SUB)
        
        # Bar Background
        draw.rounded_rectangle((bx, y, bx + bw, y + bh), radius=bh//2, fill=self.COLOR_BAR_BG)
        
        # Bar Fill
        fill_w = int(bw * (score / 100))
        if fill_w > 0:
            # Ensure min width for visibility if > 0
            fill_w = max(fill_w, bh)
            draw.rounded_rectangle((bx, y, bx + fill_w, y + bh), radius=bh//2, fill=color)
            
        # Value Text
        draw.text((vx, y - 3), f"{int(score)}%", font=font_v, fill=color)

    def _draw_background(self, image, w, h):
        """Draws a gradient background with a subtle grid pattern."""
        draw = ImageDraw.Draw(image)
        
        # Vertical Gradient
        for y in range(h):
            r = int(self.COLOR_BG_START[0] + (self.COLOR_BG_END[0] - self.COLOR_BG_START[0]) * y / h)
            g = int(self.COLOR_BG_START[1] + (self.COLOR_BG_END[1] - self.COLOR_BG_START[1]) * y / h)
            b = int(self.COLOR_BG_START[2] + (self.COLOR_BG_END[2] - self.COLOR_BG_START[2]) * y / h)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
            
        # Subtle Grid Pattern
        step = 40
        grid_color = (255, 255, 255, 10) # Very faint
        
        overlay = Image.new("RGBA", (w, h), (0,0,0,0))
        d_overlay = ImageDraw.Draw(overlay)
        
        # Draw diagonal lines
        for i in range(0, w + h, step):
            d_overlay.line([(i, 0), (0, i)], fill=grid_color, width=1)
            
        image.paste(overlay, (0,0), overlay)

    def _draw_ring(self, draw, cx, cy, radius, thickness, progress, color):
        """Draw an arc ring with rounded caps."""
        start_angle = -90
        end_angle = -90 + (360 * max(0.001, min(1, progress)))
        
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        draw.arc(bbox, start=start_angle, end=end_angle, fill=color, width=thickness)

    def _draw_rounded_rect(self, draw, x1, y1, x2, y2, r, fill):
        """Draw a rounded rectangle."""
        draw.rounded_rectangle((x1, y1, x2, y2), radius=r, fill=fill)

    async def _get_avatar_bytes(self, user: discord.User) -> Optional[bytes]:
        url = user.display_avatar.url
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
        except:
            return None
