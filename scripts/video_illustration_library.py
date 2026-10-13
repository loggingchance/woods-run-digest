#!/usr/bin/env python3
"""Curated Woods Run topic art used by the daily Shorts/Reels renderer.

Place approved transparent WebP assets in assets/video-illustrations.
Story-specific editorial photographs take precedence in render_daily_reel.py.
"""
from pathlib import Path
import re

from PIL import Image, ImageOps

ART_FILES = {
    'bids': 'bids.webp',
    'feller_buncher': 'feller_buncher.webp',
    'sawmill': 'sawmill.webp',
    'log_truck': 'log_truck.webp',
    'forest_planning': 'forest_planning.webp',
    'biomass': 'biomass.webp',
    'research': 'research.webp',
    'logs': 'logs.webp',
}
# Specific subjects first; a generic mention of "forest" must not dominate.
TOPIC_CUES = (
    ('bids', r'\b(?:bids?|bidding|auction|tender|rfp|proposal|grant|funding|application|deadline|comment period|solicitation)\b'),
    ('feller_buncher', r'\b(?:feller[ -]?buncher|harvester|harvesting equipment|logging equipment|felling|forestry machine|equipment investment|tracked machine)\b'),
    ('log_truck', r'\b(?:log truck|log haul|log hauling|hauling|truckers?|trucking|freight|transportation|diesel)\b'),
    ('biomass', r'\b(?:biomass|bioenergy|wood energy|wood fuel|wood chips|pellets|pulpwood|boiler|firewood|district heat)\b'),
    ('sawmill', r'\b(?:sawmills?|lumber mill|wood products mill|mill closure|mill curtailment|mill expansion|mass timber|sawn lumber|lumber production|sawing)\b'),
    ('forest_planning', r'\b(?:forest management|management plan|timberland|forest inventory|silviculture|forest carbon|conservation|forest policy|water quality|landowner|forest land|parcel|forest planning|forest survey)\b'),
    ('research', r'\b(?:research|study|report|publication|sourcebook|analysis|university|scientists?|survey|data release|statistics)\b'),
    ('logs', r'\b(?:logs?|sawlogs?|timber sales?|stumpage|timber prices?|hardwood|softwood|forest products|log markets?)\b'),
)


def choose_topic(story):
    """Match the headline before the story body; return one approved category."""
    for field in ('headline', 'body'):
        text = str(story.get(field) or '').lower()
        for category, pattern in TOPIC_CUES:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return category
    return 'logs'


def illustration_asset(story, source):
    category = choose_topic(story)
    return Path(source) / 'assets' / 'video-illustrations' / ART_FILES[category]


def topic_illustration(story, source, size):
    """Compose the transparent illustration without stretching it or truncating its subject."""
    path = illustration_asset(story, source)
    if not path.is_file():
        raise ValueError('Approved Woods Run illustration missing: ' + str(path))
    with Image.open(path) as original:
        if original.size != (900, 900):
            raise ValueError('Approved Woods Run illustration has wrong dimensions: ' + str(path))
        art = ImageOps.contain(original.convert('RGBA'), (size[0] - 80, 520), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', size, '#d5ddcb')
        canvas.alpha_composite(art, ((size[0] - art.width) // 2, (size[1] - art.height) // 2))
        return canvas.convert('RGB')
