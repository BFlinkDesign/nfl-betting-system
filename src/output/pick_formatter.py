"""Pick Formatter - Clean Visual Output

Takes inspiration from effective sports betting UI/UX patterns:
- Color-coded indicators (green/red)
- Scannable in <5 seconds
- Data-dense but clean tables
- Mobile-friendly formatting

WITHOUT the problematic parts:
- No hype language ("LOCK", "BANG")
- No cherry-picked results
- Transparent methodology shown
- Realistic confidence levels

Outputs: Terminal (ANSI colors), HTML, Markdown, Plain text
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ANSI color codes for terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


@dataclass
class FormattedPick:
    """Structured pick for formatting."""
    game: str
    pick_team: str
    line: float
    confidence: str  # high, medium, low
    model_prob: float
    edge: float
    edge_types: List[str]
    units: float
    notes: str = ""


def format_terminal(picks_df: pd.DataFrame) -> str:
    """
    Format picks for terminal with ANSI colors.

    Clean, scannable, color-coded output.
    """
    lines = []

    # Header
    lines.append("")
    lines.append(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}NFL PICKS - {datetime.now().strftime('%Y-%m-%d')}{Colors.RESET}")
    lines.append(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
    lines.append("")

    # Sort by confidence
    if 'confidence_score' in picks_df.columns:
        picks = picks_df.sort_values('confidence_score', ascending=False)
    else:
        picks = picks_df

    # Summary line
    high_conf = len(picks[picks.get('confidence_score', 0) >= 70]) if 'confidence_score' in picks.columns else 0
    lines.append(f"  {Colors.GREEN}{high_conf} strong plays{Colors.RESET} | {len(picks)} total games")
    lines.append("")

    # Table header
    header = f"  {'GAME':<14} {'SPREAD':>7} {'PROB':>6} {'EDGE':>6} {'CONF':>5} {'PICK':<25}"
    lines.append(f"{Colors.DIM}{header}{Colors.RESET}")
    lines.append(f"  {'-'*66}")

    for _, row in picks.iterrows():
        game = f"{row['away_team']}@{row['home_team']}"
        spread = f"{row.get('spread_line', 0):+.1f}"
        prob = f"{row.get('model_home_prob', 0.5):.0%}"
        edge = row.get('total_edge', row.get('edge_vs_market', 0))
        conf_score = row.get('confidence_score', 50)

        # Color code based on confidence
        if conf_score >= 70:
            color = Colors.GREEN
            conf_str = "HIGH"
        elif conf_score >= 55:
            color = Colors.YELLOW
            conf_str = "MED"
        else:
            color = Colors.DIM
            conf_str = "LOW"

        # Format pick
        final_pick = row.get('final_pick', 'PASS')
        if 'STRONG' in str(final_pick):
            pick_display = final_pick.replace('STRONG:', '').strip()[:23]
        elif 'LEAN' in str(final_pick):
            pick_display = final_pick.replace('LEAN:', '').strip()[:23]
        else:
            pick_display = str(final_pick)[:23]

        # Edge indicator
        edge_indicator = f"{Colors.GREEN}+{edge:.0%}{Colors.RESET}" if edge > 0.03 else f"{edge:+.0%}"

        line = f"  {color}{game:<14}{Colors.RESET} {spread:>7} {prob:>6} {edge_indicator:>12} {conf_str:>5} {pick_display:<25}"
        lines.append(line)

        # Show edge types for high confidence
        if conf_score >= 65 and row.get('edge_types'):
            edge_types = str(row['edge_types'])[:40]
            lines.append(f"  {Colors.DIM}    ^ {edge_types}{Colors.RESET}")

    lines.append("")
    lines.append(f"  {Colors.DIM}Confidence: HIGH (70+) = 2u | MED (55-69) = 1u | LOW = pass{Colors.RESET}")
    lines.append(f"  {Colors.DIM}Track CLV to validate edge over time{Colors.RESET}")
    lines.append("")

    return "\n".join(lines)


def format_markdown(picks_df: pd.DataFrame) -> str:
    """
    Format picks as Markdown table.

    Clean, shareable format without ANSI codes.
    """
    lines = []

    lines.append(f"# NFL Picks - {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    # Sort
    if 'confidence_score' in picks_df.columns:
        picks = picks_df.sort_values('confidence_score', ascending=False)
    else:
        picks = picks_df

    # High confidence section
    high_conf = picks[picks.get('confidence_score', 0) >= 65] if 'confidence_score' in picks.columns else picks.head(3)

    if len(high_conf) > 0:
        lines.append("## Top Plays")
        lines.append("")
        lines.append("| Game | Spread | Model | Edge | Pick |")
        lines.append("|------|--------|-------|------|------|")

        for _, row in high_conf.iterrows():
            game = f"{row['away_team']} @ {row['home_team']}"
            spread = f"{row.get('spread_line', 0):+.1f}"
            prob = f"{row.get('model_home_prob', 0.5):.0%}"
            edge = row.get('total_edge', row.get('edge_vs_market', 0))
            pick = str(row.get('final_pick', 'PASS'))[:30]

            # Clean pick text
            for prefix in ['STRONG:', 'LEAN:', 'SMALL:', '★★★', '★★', '★']:
                pick = pick.replace(prefix, '').strip()

            lines.append(f"| {game} | {spread} | {prob} | {edge:+.0%} | **{pick}** |")

        lines.append("")

    # Full card
    lines.append("## Full Card")
    lines.append("")
    lines.append("| Game | Spread | Prob | Edge | Conf | Action |")
    lines.append("|------|--------|------|------|------|--------|")

    for _, row in picks.iterrows():
        game = f"{row['away_team']}@{row['home_team']}"
        spread = f"{row.get('spread_line', 0):+.1f}"
        prob = f"{row.get('model_home_prob', 0.5):.0%}"
        edge = row.get('total_edge', row.get('edge_vs_market', 0))
        conf = row.get('confidence_score', 50)
        units = row.get('bet_units', 0)

        if units >= 1.5:
            action = f"**{units}u**"
        elif units >= 0.5:
            action = f"{units}u"
        else:
            action = "Pass"

        lines.append(f"| {game} | {spread} | {prob} | {edge:+.0%} | {conf:.0f} | {action} |")

    lines.append("")
    lines.append("---")
    lines.append("*Model: XGBoost + EPA/rest/divisional features. Track CLV for edge validation.*")

    return "\n".join(lines)


def format_html(picks_df: pd.DataFrame) -> str:
    """
    Format picks as HTML for web display.

    Clean, responsive design with color coding.
    """
    if 'confidence_score' in picks_df.columns:
        picks = picks_df.sort_values('confidence_score', ascending=False)
    else:
        picks = picks_df

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NFL Picks - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #1a1a1a; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; background: white;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 20px 0; }}
        th {{ background: #1a1a1a; color: white; padding: 12px 8px; text-align: left; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f8f9fa; }}
        .high {{ background: #d4edda; }}
        .med {{ background: #fff3cd; }}
        .low {{ background: #f8f9fa; }}
        .edge-pos {{ color: #28a745; font-weight: bold; }}
        .edge-neg {{ color: #dc3545; }}
        .pick {{ font-weight: bold; }}
        .notes {{ font-size: 0.85em; color: #666; }}
        .footer {{ font-size: 0.9em; color: #666; margin-top: 20px; padding-top: 20px;
                   border-top: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>NFL Picks - {datetime.now().strftime('%B %d, %Y')}</h1>

    <table>
        <tr>
            <th>Game</th>
            <th>Spread</th>
            <th>Model</th>
            <th>Edge</th>
            <th>Pick</th>
            <th>Units</th>
        </tr>
"""

    for _, row in picks.iterrows():
        game = f"{row['away_team']} @ {row['home_team']}"
        spread = f"{row.get('spread_line', 0):+.1f}"
        prob = f"{row.get('model_home_prob', 0.5):.0%}"
        edge = row.get('total_edge', row.get('edge_vs_market', 0))
        conf = row.get('confidence_score', 50)
        units = row.get('bet_units', 0)
        pick = str(row.get('final_pick', 'PASS'))

        # Clean pick
        for prefix in ['STRONG:', 'LEAN:', 'SMALL:', '★★★', '★★', '★']:
            pick = pick.replace(prefix, '').strip()

        # Row class
        if conf >= 70:
            row_class = "high"
        elif conf >= 55:
            row_class = "med"
        else:
            row_class = "low"

        # Edge class
        edge_class = "edge-pos" if edge > 0.03 else ("edge-neg" if edge < -0.03 else "")

        html += f"""        <tr class="{row_class}">
            <td>{game}</td>
            <td>{spread}</td>
            <td>{prob}</td>
            <td class="{edge_class}">{edge:+.1%}</td>
            <td class="pick">{pick[:35]}</td>
            <td>{units if units > 0 else 'Pass'}</td>
        </tr>
"""

    html += """    </table>

    <div class="footer">
        <strong>Methodology:</strong> XGBoost model with EPA, rest advantage, divisional factors.<br>
        <strong>Edge Types:</strong> Divisional underdogs (71% ATS), rest advantages, situational spots.<br>
        <strong>Validation:</strong> Track CLV (closing line value) to verify edge over time.<br>
        <em>For entertainment purposes. Gamble responsibly.</em>
    </div>
</body>
</html>"""

    return html


def save_outputs(picks_df: pd.DataFrame, output_dir: str = "data/outputs") -> Dict[str, str]:
    """
    Save picks in multiple formats.

    Returns dict of format -> filepath.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y%m%d')
    outputs = {}

    # Markdown
    md_path = output_path / f"picks_{date_str}.md"
    md_path.write_text(format_markdown(picks_df))
    outputs['markdown'] = str(md_path)

    # HTML
    html_path = output_path / f"picks_{date_str}.html"
    html_path.write_text(format_html(picks_df))
    outputs['html'] = str(html_path)

    # Plain text (no ANSI)
    txt_path = output_path / f"picks_{date_str}.txt"
    txt_content = format_terminal(picks_df)
    # Strip ANSI codes for plain text
    import re
    txt_content = re.sub(r'\033\[[0-9;]*m', '', txt_content)
    txt_path.write_text(txt_content)
    outputs['text'] = str(txt_path)

    logger.info(f"Saved outputs to {output_dir}: {list(outputs.keys())}")
    return outputs


def print_picks(picks_df: pd.DataFrame):
    """Print picks to terminal with colors."""
    print(format_terminal(picks_df))
