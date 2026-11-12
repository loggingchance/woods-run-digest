"""A separate native image for striking posts, never the morning issue card.

X crawls a bare dated URL into the morning card even when Buffer assets is [].
A native photo keeps the clickable URL in the caption but replaces that preview.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

POLICY_START = '2026-11-12'
WIDTH, HEIGHT = 1200, 675


def asset_path(root, date):
    return Path(root) / 'assets/striking' / (date + '.png')


def observation(text):
    # Caption retains all URLs. Only the visual omits URLs for readable typography.
    result = re.sub(r'https?://\S+', '', text).strip()
    result = ' '.join(result.split())
    if not result:
        raise ValueError('Striking visual needs substantive observation text')
    return result


def render(issue, root):
    from PIL import Image, ImageDraw, ImageFont
    text = observation(issue['strikingText'])
    image = Image.new('RGB', (WIDTH, HEIGHT), '#173d32')
    draw = ImageDraw.Draw(image)
    fonts = Path('/usr/share/fonts/truetype/dejavu')
    sans = lambda size: ImageFont.truetype(str(fonts/'DejaVuSans.ttf'), size)
    bold = lambda size: ImageFont.truetype(str(fonts/'DejaVuSans-Bold.ttf'), size)
    draw.rectangle((64, 57, 72, 110), fill='#e5b76e')
    draw.text((94, 66), 'ONE THING WORTH KNOWING', font=bold(25), fill='#e5b76e')
    for size in range(59, 35, -1):
        font = sans(size)
        lines, line = [], ''
        for word in text.split():
            trial = (line + ' ' + word).strip()
            if draw.textlength(trial, font=font) <= 1040:
                line = trial
            else:
                if line: lines.append(line)
                line = word
        if line: lines.append(line)
        leading = size + 14
        if len(lines)*leading <= 395 and all(draw.textlength(s, font=font) <= 1040 for s in lines):
            break
    else:
        raise ValueError('Striking observation does not fit in full; never truncate qualifications')
    y = 146 + (395-len(lines)*leading)//2
    for line in lines:
        draw.text((80, y), line, font=font, fill='#fcf6e9')
        y += leading
    draw.line((80, 575, 1120, 575), fill='#749486', width=2)
    draw.text((80, 602), 'The Woods Run Digest', font=bold(24), fill='#fcf6e9')
    date = issue['date']
    draw.text((1120-draw.textlength(date, font=sans(22)), 604), date, font=sans(22), fill='#bdd0c7')
    path = asset_path(root, date)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, 'PNG', optimize=True)
    return path


def describe(issue, root):
    path = asset_path(root, issue['date'])
    data = path.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Striking visual is not a PNG')
    return {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(data).hexdigest(),
            'url': 'https://raw.githubusercontent.com/loggingchance/woods-run-digest/main/' + str(path.relative_to(root)),
            'policy': 'distinct-native-striking-image-v1'}


def validate_provider_asset(post, expected):
    sources = [a.get('source') for a in post.get('assets') or []]
    if expected['url'] not in sources:
        raise ValueError('Buffer did not return the exact distinct striking image; no resubmission')
    if any('/assets/cards/' in str(s) for s in sources):
        raise ValueError('Morning WRD card is prohibited on striking posts')
