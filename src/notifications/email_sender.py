"""
Email notification sender using Gmail SMTP.

Sends detailed HTML-formatted bet recommendations via email.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends email notifications via Gmail SMTP."""

    def __init__(self, smtp_user: str, smtp_password: str, recipient: str):
        """
        Initialize email sender.

        Args:
            smtp_user: Gmail address (e.g., yourname@gmail.com)
            smtp_password: Gmail app password (NOT regular password!)
            recipient: Email address to send notifications to

        Note:
            Gmail app passwords: https://support.google.com/accounts/answer/185833
        """
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.recipient = recipient
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 465  # SSL port

    def send_bet_alert(self, analysis: Dict, parlays: Dict) -> bool:
        """
        Send bet alert email with recommendations.

        Args:
            analysis: Pre-game analysis results (from PROD-001)
            parlays: Parlay recommendations (from PROD-002)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = self._create_subject(analysis, parlays)
            msg["From"] = self.smtp_user
            msg["To"] = self.recipient

            # Create HTML body
            html_body = self._create_html_body(analysis, parlays)

            # Attach HTML
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # Send via Gmail SMTP
            with smtplib.SMTP_SSL(
                self.smtp_server, self.smtp_port, timeout=10
            ) as server:
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {self.recipient}")
            return True

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def _create_subject(self, analysis: Dict, parlays: Dict) -> str:
        """Create email subject line."""
        num_bets = len(analysis.get("recommendations", []))
        num_parlays = len(parlays.get("2_leg", [])) + len(parlays.get("3_leg", []))

        if num_bets == 0 and num_parlays == 0:
            return "🏈 NFL Bets: No Recommendations Today"

        subject = f"🏈 NFL Bets: {num_bets} Singles"
        if num_parlays > 0:
            subject += f", {num_parlays} Parlays"

        return subject

    def _create_html_body(self, analysis: Dict, parlays: Dict) -> str:
        """
        Create HTML email body.

        Returns:
            HTML string with styled bet recommendations
        """
        # Get game info
        game_info = analysis["game_info"]
        recommendations = analysis.get("recommendations", [])
        matching_edges = analysis.get("matching_edges", [])

        html = f"""
        <html>
          <head>
            <style>
              body {{
                font-family: Arial, sans-serif;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
              }}
              .header {{
                background: #1a1a2e;
                color: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
              }}
              .game-title {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
              }}
              .game-time {{
                font-size: 14px;
                opacity: 0.8;
              }}
              .section {{
                background: #f5f5f5;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
              }}
              .section-title {{
                font-size: 18px;
                font-weight: bold;
                color: #1a1a2e;
                margin-bottom: 10px;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 5px;
              }}
              .bet-card {{
                background: white;
                padding: 15px;
                border-left: 4px solid #4CAF50;
                margin-bottom: 10px;
                border-radius: 4px;
              }}
              .bet-title {{
                font-size: 16px;
                font-weight: bold;
                color: #4CAF50;
                margin-bottom: 8px;
              }}
              .bet-detail {{
                font-size: 14px;
                margin: 4px 0;
              }}
              .edge-badge {{
                display: inline-block;
                background: #2196F3;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-top: 8px;
              }}
              .tier-s {{
                background: #FFD700;
                color: #333;
                padding: 2px 6px;
                border-radius: 3px;
                font-weight: bold;
                font-size: 11px;
              }}
              .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
                text-align: center;
              }}
            </style>
          </head>
          <body>
            <div class="header">
              <div class="game-title">
                🏈 {game_info['away_team']} @ {game_info['home_team']}
              </div>
              <div class="game-time">
                Week {game_info.get('week', 'N/A')} • {game_info.get('kickoff_str', 'TBD')}
              </div>
            </div>
        """

        # Single bets section
        if recommendations:
            html += """
            <div class="section">
              <div class="section-title">💰 Single Bet Recommendations</div>
            """

            for rec in recommendations:
                odds_str = f"{rec['odds']:+.0f}" if rec["odds"] else "N/A"
                ev_str = (
                    f"{rec['expected_value']:+.1%}" if rec["expected_value"] else "N/A"
                )
                html += f"""
              <div class="bet-card">
                <div class="bet-title">
                  {rec['team']} {rec['bet_type'].upper()}
                  <span class="tier-s">TIER {rec['confidence_tier']}</span>
                </div>
                <div class="bet-detail"><strong>Odds:</strong> {odds_str} ({rec['sportsbook']})</div>
                <div class="bet-detail"><strong>Win Probability:</strong> {rec['win_probability']:.1%}</div>
                <div class="bet-detail"><strong>Expected Value:</strong> {ev_str}</div>
                <div class="bet-detail"><strong>Kelly Fraction:</strong> {rec['kelly_fraction']:.2%} of bankroll</div>
                <span class="edge-badge">{rec['edge_name']}</span>
              </div>
                """

            html += "</div>"

        # Parlays section
        if parlays.get("2_leg") or parlays.get("3_leg"):
            html += """
            <div class="section">
              <div class="section-title">🎲 Parlay Recommendations</div>
            """

            # 2-leg parlays
            for i, parlay in enumerate(parlays.get("2_leg", [])[:3], 1):
                html += f"""
              <div class="bet-card">
                <div class="bet-title">2-Leg Parlay #{i}</div>
                """

                for j, leg in enumerate(parlay["legs"], 1):
                    odds_str = f"{leg['odds']:+.0f}" if leg["odds"] else "N/A"
                    html += f"""
                <div class="bet-detail">
                  <strong>Leg {j}:</strong> {leg['team']} {leg['bet_type']} ({odds_str})
                  <br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{leg['game']}
                </div>
                    """

                html += f"""
                <div class="bet-detail"><strong>Combined Odds:</strong> {parlay['parlay_odds']:+.0f}</div>
                <div class="bet-detail"><strong>Win Probability:</strong> {parlay['combined_probability']:.1%}</div>
                <div class="bet-detail"><strong>Expected ROI:</strong> {parlay['expected_roi']:+.1%}</div>
              </div>
                """

            # 3-leg parlays
            for i, parlay in enumerate(parlays.get("3_leg", [])[:2], 1):
                html += f"""
              <div class="bet-card">
                <div class="bet-title">3-Leg Parlay #{i}</div>
                """

                for j, leg in enumerate(parlay["legs"], 1):
                    odds_str = f"{leg['odds']:+.0f}" if leg["odds"] else "N/A"
                    html += f"""
                <div class="bet-detail">
                  <strong>Leg {j}:</strong> {leg['team']} {leg['bet_type']} ({odds_str})
                  <br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{leg['game']}
                </div>
                    """

                html += f"""
                <div class="bet-detail"><strong>Combined Odds:</strong> {parlay['parlay_odds']:+.0f}</div>
                <div class="bet-detail"><strong>Win Probability:</strong> {parlay['combined_probability']:.1%}</div>
                <div class="bet-detail"><strong>Expected ROI:</strong> {parlay['expected_roi']:+.1%}</div>
              </div>
                """

            html += "</div>"

        # Matching edges section
        if matching_edges:
            html += """
            <div class="section">
              <div class="section-title">✅ Discovered Edges</div>
            """

            for edge in matching_edges:
                html += f"""
              <div class="bet-detail">
                <strong>{edge['edge_name']}</strong>: 
                {edge['win_rate']:.1%} WR, {edge['edge']:+.1%} Edge 
                ({edge['sample_size']} games)
              </div>
                """

            html += "</div>"

        # Footer
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        html += f"""
            <div class="footer">
              ⚠️ This is a research tool. Bet responsibly.<br>
              Generated by NFL Betting System • {timestamp}
            </div>
          </body>
        </html>
        """

        return html
