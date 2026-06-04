"""color_profiles: per-template lookup + default fallback."""

import pytest

from pipeline.color_profiles import (
    DEFAULT_PROFILE,
    GUNLUK_1_PROFILE,
    GUNLUK_2_PROFILE,
    GUNLUK_3_PROFILE,
    HAFTALIK_2_PROFILE,
    TEMPLATE_PROFILES,
    ColorProfile,
    get_color_profile,
)


def test_default_for_none():
    assert get_color_profile(None) is DEFAULT_PROFILE


def test_default_for_unknown_template():
    assert get_color_profile("does-not-exist") is DEFAULT_PROFILE


def test_default_for_templates_without_overrides():
    """haftalik-1 and 4_gunluk-* use the default profile."""
    for tid in ["haftalik-1", "4_gunluk-1", "4_gunluk-2", "4_gunluk-3", "4_gunluk-4"]:
        assert get_color_profile(tid) is DEFAULT_PROFILE, tid


@pytest.mark.parametrize(
    "template_id, expected",
    [
        ("gunluk-1", GUNLUK_1_PROFILE),
        ("gunluk-2", GUNLUK_2_PROFILE),
        ("gunluk-3", GUNLUK_3_PROFILE),
        ("haftalik-2", HAFTALIK_2_PROFILE),
    ],
)
def test_specific_template_lookup(template_id, expected):
    assert get_color_profile(template_id) is expected


def test_grayscale_fallback_enabled_only_for_faint_templates():
    """Profiles that target a faint pencil/dark trace enable the grayscale fb;
    the default and gunluk-2 (purple-on-green) do not."""
    assert DEFAULT_PROFILE.use_grayscale_detection is False
    assert GUNLUK_2_PROFILE.use_grayscale_detection is False
    assert GUNLUK_1_PROFILE.use_grayscale_detection is True
    assert GUNLUK_3_PROFILE.use_grayscale_detection is True
    assert HAFTALIK_2_PROFILE.use_grayscale_detection is True


def test_profile_dataclass_defaults():
    """ColorProfile() with no arguments should give the same thresholds as
    DEFAULT_PROFILE for the fields DEFAULT_PROFILE inherits unchanged."""
    blank = ColorProfile()
    assert blank.max_intensity == DEFAULT_PROFILE.max_intensity
    assert blank.min_intensity == DEFAULT_PROFILE.min_intensity
    assert blank.sat_min == DEFAULT_PROFILE.sat_min
    assert blank.use_grayscale_detection is False


def test_template_profiles_table_contains_overrides():
    assert set(TEMPLATE_PROFILES) == {"gunluk-1", "gunluk-2", "gunluk-3", "haftalik-2"}
