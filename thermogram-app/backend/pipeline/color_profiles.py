"""
Color profiles for different thermogram templates.

Each template type has different ink colors, paper backgrounds, and grid colors.
These profiles define the color mask parameters for curve detection.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ColorProfile:
    """Color detection parameters for a specific template type."""

    # Intensity bounds
    max_intensity: int = 245
    min_intensity: int = 85

    # RGB difference thresholds
    rg_diff_min: int = 22       # R - G minimum
    rg_diff_max: int = 255      # R - G maximum (optional upper bound)
    rb_diff_min: int = 5        # R - B minimum
    bg_diff_min: int = -18      # B - G minimum
    bg_diff_max: int = 255      # B - G maximum

    # Saturation
    sat_min: int = 28
    sat_max: int = 255

    # Additional filters
    use_grayscale_detection: bool = False  # For pencil traces
    grayscale_max_sat: int = 40            # Max saturation for grayscale
    grayscale_max_intensity: int = 150     # Max intensity for dark pencil

    # Description
    description: str = ""


# Default profile (works for pinkish/reddish ink - haftalik, 4_gunluk)
DEFAULT_PROFILE = ColorProfile(
    max_intensity=245,
    min_intensity=85,
    rg_diff_min=22,
    rb_diff_min=5,
    bg_diff_min=-18,
    sat_min=28,
    description="Default: pinkish/reddish ink detection"
)


# gunluk-1: Faint pencil on yellow/cream background with tan grid
# Challenge: Distinguish gray pencil from brown/yellow grid
GUNLUK_1_PROFILE = ColorProfile(
    max_intensity=180,          # Darker pixels only
    min_intensity=40,
    rg_diff_min=-15,            # Allow slightly green-ish (pencil)
    rg_diff_max=20,             # Exclude too red (grid lines)
    rb_diff_min=-30,
    bg_diff_min=-40,
    bg_diff_max=30,             # Not too blue
    sat_min=0,                  # Low saturation for pencil
    sat_max=50,                 # Exclude colorful grid
    use_grayscale_detection=True,
    grayscale_max_sat=35,
    grayscale_max_intensity=140,
    description="gunluk-1: Faint pencil on yellow background"
)


# gunluk-2: Faint purple/violet ink on green-grid paper.

GUNLUK_2_PROFILE = ColorProfile(
    max_intensity=240,
    min_intensity=120,
    rg_diff_min=10,
    rg_diff_max=45,
    rb_diff_min=5,
    bg_diff_min=-25,
    bg_diff_max=25,
    sat_min=10,
    sat_max=80,
    use_grayscale_detection=False,
    description="gunluk-2: faint purple/violet ink on green grid"
)


# gunluk-3: Faint dark/purple line on orange-grid paper.
# Orange grid has B-G ~ -50..-90; the faded ink has B-G ~ -2..-35.
GUNLUK_3_PROFILE = ColorProfile(
    max_intensity=200,
    min_intensity=70,
    rg_diff_min=-15,
    rg_diff_max=45,
    rb_diff_min=0,
    bg_diff_min=-45,
    bg_diff_max=25,
    sat_min=0,
    sat_max=90,
    use_grayscale_detection=True,
    grayscale_max_intensity=185,
    grayscale_max_sat=45,
    description="gunluk-3: faint dark/purple ink on orange grid"
)


# haftalik-2: Near-black/dark-blue ink on orange-grid paper.
# Curve pixels are very dark (maxRGB ~ 60-100) and slightly blue-shifted
# compared to the orange grid (which is very B-deficient).
HAFTALIK_2_PROFILE = ColorProfile(
    max_intensity=120,
    min_intensity=0,
    rg_diff_min=-30,
    rg_diff_max=40,
    rb_diff_min=-40,
    bg_diff_min=-30,
    bg_diff_max=50,
    sat_min=5,
    sat_max=100,
    use_grayscale_detection=True,
    grayscale_max_intensity=110,
    grayscale_max_sat=45,
    description="haftalik-2: dark blue/black ink on orange grid"
)


# Template ID to profile mapping
TEMPLATE_PROFILES: Dict[str, ColorProfile] = {
    "gunluk-1": GUNLUK_1_PROFILE,
    "gunluk-2": GUNLUK_2_PROFILE,
    "gunluk-3": GUNLUK_3_PROFILE,
    "haftalik-2": HAFTALIK_2_PROFILE,
    # All other templates use default (pinkish ink)
}


def get_color_profile(template_id: Optional[str]) -> ColorProfile:
    """Get the color profile for a given template ID.

    Args:
        template_id: Template identifier (e.g., "gunluk-1", "haftalik-1")

    Returns:
        ColorProfile for the template, or DEFAULT_PROFILE if not found
    """
    if template_id is None:
        return DEFAULT_PROFILE

    return TEMPLATE_PROFILES.get(template_id, DEFAULT_PROFILE)


def get_all_profiles() -> Dict[str, ColorProfile]:
    """Get all defined color profiles."""
    return TEMPLATE_PROFILES.copy()
