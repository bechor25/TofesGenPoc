"""Photographic-difficulty conditions for the test bank.

A difficulty level (1-10) selects a varied, severity-scaled set of real-world capture
conditions that get appended to the gpt-image-2 edit prompt, so the SAME source yields
test images that are progressively harder for an EXTERNAL recognition model to read.

Level 1 = a clean reproduction (empty clause) — identical to the plain value-edit, so
there is no regression when difficulty is not requested. The chosen level is also stated
verbatim in the clause (it is the score sent to the model)."""
from __future__ import annotations

import random

# Condition ingredients per axis; natural-language fragments the model can enact.
_GEOMETRY = [
    "photographed at a slight tilt",
    "shot from a steep oblique angle so the page looks keystoned",
    "rotated about 90 degrees",
    "photographed upside-down (rotated 180 degrees)",
    "skewed with strong perspective distortion",
]
_LIGHTING = [
    "in dim indoor light",
    "in low, poor lighting",
    "in a nearly dark room so text is hard to read",
    "with harsh camera-flash glare and hotspots",
    "under warm tungsten light with a strong color cast",
    "with an uneven shadow falling across the page",
]
_BACKGROUNDS = [
    "lying on a wooden table",
    "on a cluttered office desk",
    "on an outdoor bench with the ground visible around it",
    "held in one hand outdoors",
    "on a car seat",
    "on a tiled floor",
]
_ARTIFACTS = [
    "with mild motion blur",
    "slightly out of focus",
    "with visible phone-camera noise and grain",
    "with heavy JPEG compression artifacts",
    "with the paper wrinkled and folded",
    "with a finger partially covering one corner",
    "with a faint coffee stain on the paper",
]

# axes are consumed in this order as the level rises: geometry + lighting form the
# backbone of "photographed in the wild", then background, then capture artifacts.
_AXES = [_GEOMETRY, _LIGHTING, _BACKGROUNDS, _ARTIFACTS]


def _num_conditions(level: int) -> int:
    """1 fragment at level 2, scaling up to 5 at level 10."""
    return max(1, min(5, 1 + (level - 2) * 4 // 8))


def photo_condition_clause(level: int, seed: int = 0) -> str:
    """Prompt clause for a difficulty ``level`` (1-10). '' for level <= 1 (clean).
    Deterministic per (level, seed) so a batch varies across variants but reproduces."""
    level = max(1, min(10, int(level)))
    if level <= 1:
        return ""
    rng = random.Random(seed * 97 + level)
    n = _num_conditions(level)
    picks: list[str] = []
    for axis in _AXES:
        if len(picks) >= n:
            break
        picks.append(rng.choice(axis))
    while len(picks) < n:  # very hard levels pile on extra capture artifacts
        picks.append(rng.choice(_ARTIFACTS))
    scene = ", ".join(picks)
    return (
        "Then re-render the whole result as a REAL PHOTOGRAPH of that form as if captured "
        f"with a phone camera {scene}. Difficulty level {level} of 10: the higher the "
        "level, the harder it should be for an OCR / vision model to read the document — "
        "but the replaced values must still be physically present on the page. Apply the "
        "lighting, angle, background and blur so it looks authentically photographed in "
        "that condition, not a clean scan."
    )
