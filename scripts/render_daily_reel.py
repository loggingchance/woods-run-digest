#!/usr/bin/env python3
"""Render approved v4 daily Reels/Shorts locally; never publish or queue posts."""
from pathlib import Path
import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / 'assets/video-brand'
W, H, FPS = 1080, 1920, 30
GREEN = '#103a25'
PAPER = '#eee8d5'
GOLD = '#ad8733'
DURATIONS = (2.5, 7, 7, 7, 7, 7, 4)


def font(size, bold=False, sans=False):
    name = ('DejaVuSans' if sans else 'DejaVuSerif') + ('-Bold' if bold else '') + '.ttf'
    linux = Path('/usr/share/fonts/truetype/dejavu') / name
    mac = Path('/System/Library/Fonts/Supplemental') / (('Arial' if sans else 'Georgia') + (' Bold' if bold else '') + '.ttf')
    return ImageFont.truetype(str(linux if linux.exists() else mac), size)


def lines(draw, text, ft, width):
    result, line = [], ''
    for word in text.split():
        trial = (line + ' ' + word).strip()
        if draw.textlength(trial, font=ft) > width and line:
            result.append(line)
            line = word
        else:
            line = trial
    return result + ([line] if line else [])


def block(draw, text, box, size, bold=False, sans=False):
    x, y, right, bottom = box
    for n in range(size, 29, -1):
        ft = font(n, bold, sans)
        rows = lines(draw, text, ft, right-x)
        step = math.ceil(n * 1.22)
        if y + step * len(rows) <= bottom:
            for row in rows:
                draw.text((x, y), row, font=ft, fill=GREEN)
                y += step
            return y
    raise ValueError('Story text does not fit; editorial summary required')


def center(draw, text, y, size, bold=False, fill=GREEN):
    ft = font(size, bold)
    draw.text(((W-draw.textlength(text, font=ft))/2, y), text, font=ft, fill=fill)


def tree(draw, x, y, scale, hardwood=False, fill=GREEN):
    draw.rectangle((x-5*scale,y-45*scale,x+5*scale,y), fill=fill)
    if hardwood:
        for dx,dy,r in [(0,-65,25),(-18,-48,20),(18,-48,21)]:
            draw.ellipse((x+(dx-r)*scale,y+(dy-r)*scale,x+(dx+r)*scale,y+(dy+r)*scale),fill=fill)
    else:
        draw.polygon([(x,y-100*scale),(x-35*scale,y-35*scale),(x+35*scale,y-35*scale)],fill=fill)
        draw.polygon([(x,y-75*scale),(x-43*scale,y-12*scale),(x+43*scale,y-12*scale)],fill=fill)


def footer(im, opening=False):
    d=ImageDraw.Draw(im)
    if opening:
        for i,x in enumerate(range(0,1120,75)):
            tree(d,x,1600,1.2+(i%3)*.2,i%3!=1)
    d.rectangle((0,1605,W,H),fill=GREEN)
    d.line((80,1652,1000,1652),fill=GOLD,width=3)
    if opening:
        center(d,'from The Forest Business School',1667,42,fill=PAPER)
        center(d,'woodsrun.forestenterprise.org',1755,38,True,PAPER)
        center(d,'Story 1 begins in 2.5 seconds',1830,32,fill=PAPER)
    else:
        center(d,'woodsrun.forestenterprise.org',1693,30,True,PAPER)
        center(d,"Read the full story in today’s edition",1755,27,fill=PAPER)
        center(d,'on screen about 7 seconds',1825,25,fill=PAPER)
        d.polygon([(355,1834),(355,1858),(378,1846)],fill=GOLD)


def read_stories(source, date):
    page=source/date.replace('-','/')/'index.html'
    soup=BeautifulSoup(page.read_text(encoding='utf-8'),'html.parser')
    stories=[]
    for sec in soup.select('section.issue-section:not(.special-opportunity)'):
        for art in sec.select('article.story'):
            h=art.find('h3')
            paras=[p.get_text(' ',strip=True) for p in art.find_all('p') if not set(p.get('class',[])) & {'region-label','story-source','watch-line'}]
            if not h or not paras: continue
            body=paras[0]
            if len(body)>245: body=body[:242].rsplit(' ',1)[0]+'…'
            img=art.find('img')
            region=art.select_one('.region-label')
            stories.append(dict(headline=h.get_text(' ',strip=True),body=body,region=region.get_text(' ',strip=True) if region else 'WOODS RUN', image=img.get('src') if img else None))
    if len(stories)<5: raise ValueError('Approved format requires five stories')
    return stories[:5]


def illustration(story, source):
    """Use supplied story art, otherwise draw an editorial illustration by subject."""
    if story['image']:
        path=(source/story['image'].lstrip('/')).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError('Missing local story image: '+story['image'])
        art=Image.open(path).convert('RGB')
        return ImageOps.pad(art,(W,480),color=PAPER)
    im=Image.new('RGB',(W,480),'#d5ddcb'); d=ImageDraw.Draw(im)
    words=(story['headline']+' '+story['body']).lower()
    for i,x in enumerate(range(20,1100,95)): tree(d,x,340,.8+(i%3)*.15,i%2==0,fill='#7e9776')
    d.rectangle((0,350,W,480),fill='#c3b28e')
    if any(w in words for w in ['application','bids','bid opening','fund','deadline']):
        d.rounded_rectangle((370,55,740,435),radius=14,fill=PAPER,outline=GREEN,width=4)
        d.rectangle((455,35,655,85),fill='#776345')
        for y in range(135,390,55):
            d.rectangle((405,y,425,y+20),outline=GREEN,width=2)
            d.line((450,y+10,690,y+10),fill='#8c8d76',width=3)
        d.polygon([(800,355),(955,190),(975,213),(820,375)],fill=GOLD)
        if 'bid' in words:
            d.rectangle((110,220,330,360),fill='#f4efdf',outline=GREEN,width=3)
            d.line((110,220,220,305,330,220),fill=GREEN,width=3)
            d.text((425,91),'BID REVIEW',font=font(28,True),fill=GREEN)
        else:
            d.rectangle((80,130,310,320),fill=PAPER,outline=GREEN,width=3)
            d.rectangle((80,130,310,180),fill='#a86e55')
            d.text((105,200),'DEADLINE',font=font(25,True),fill=GREEN)
            d.line((105,260,285,260),fill=GOLD,width=3)
    elif any(w in words for w in ['equipment','investment','technology','machine']):
        d.rounded_rectangle((220,300,800,410),radius=40,fill='#3b473b')
        for x in range(265,780,85):d.ellipse((x-25,326,x+25,380),fill='#939b88')
        d.rectangle((370,150,625,315),fill='#bd9a4d')
        d.rectangle((395,170,590,270),fill='#d8e4df')
        d.line((625,190,830,95,955,255),fill='#bd9a4d',width=40)
        d.polygon([(925,245),(1020,270),(970,310),(900,290)],fill='#3b473b')
    else:
        # Timber sales, supply and mill stories: stacked sawlogs in a working forest.
        for row in range(3):
            for col in range(7-row):
                x=180+col*110+row*55; y=382-row*82
                d.rectangle((x,y-37,x+230,y+37),fill='#886e48',outline='#5c513b',width=2)
                d.ellipse((x-40,y-38,x+40,y+38),fill='#d5b67e',outline='#6e593d',width=3)
                d.ellipse((x-24,y-23,x+24,y+23),outline='#9d7c4f',width=2)
    return im


def render(source, date, display, output, frames_dir=None):
    stories=read_stories(source,date)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='woodsrun-v4-') as td:
        folder=Path(td) if frames_dir is None else frames_dir
        folder.mkdir(parents=True,exist_ok=True)
        frames=[]
        im=Image.new('RGB',(W,H),PAPER);d=ImageDraw.Draw(im)
        for i,x in enumerate([390,460,530,600,670]):tree(d,x,145,.75,i%2==1)
        center(d,'WOODS RUN',180,108,True);center(d,'DIGEST',320,82,True)
        center(d,display,455,55,True)
        center(d,'Daily forestry & forest products intelligence',540,38)
        art=Image.open(BRAND/'forester.webp').convert('RGB')
        im.paste(ImageOps.fit(art,(680,1010)),(250,590))
        d=ImageDraw.Draw(im)
        for i,t in enumerate(['PEOPLE','MARKETS','FORESTS']):d.text((55,1260+i*60),t,font=font(32),fill=GREEN)
        footer(im,True); frames.append(im)
        for i,story in enumerate(stories,1):
            im=Image.new('RGB',(W,H),PAPER);im.paste(Image.open(BRAND/'masthead.webp'),(0,0));d=ImageDraw.Draw(im)
            block(d,story['region'].upper(),(90,405,895,510),30,True,True)
            d.text((922,407),f'{i}/5',font=font(38,True),fill=GREEN)
            d.line((90,515,990,515),fill=GOLD,width=3)
            y=block(d,story['headline'],(90,545,990,855),68,True)
            d.line((90,y+18,990,y+18),fill=GOLD,width=3)
            block(d,story['body'],(90,y+45,990,1110),49)
            im.paste(illustration(story,source),(0,1125));footer(im);frames.append(im)
        frames.append(Image.open(BRAND/'closing.webp').convert('RGB'))
        # Derive every segment from seconds, preserving timing at 30 fps.
        counts=segment_frame_counts()
        ffmpeg=os.environ.get('FFMPEG') or shutil.which('ffmpeg')
        if not ffmpeg:raise RuntimeError('ffmpeg is required')
        command=[ffmpeg,'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
        proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for i,(im,count) in enumerate(zip(frames,counts)):
            im.save(folder/f'{i:02d}.png')
            data=im.tobytes()
            for _ in range(count):proc.stdin.write(data)
        proc.stdin.close();err=proc.stderr.read();rc=proc.wait()
        if rc:raise RuntimeError(err.decode())
        manifest=dict(date=date,format='approved-v4',dimensions=[W,H],fps=FPS,frames=sum(counts),duration_seconds=sum(counts)/FPS,segment_frames=counts,stories=stories,publication_attempted=False)
        output.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return output


def segment_frame_counts():
    if FPS < 23:
        raise ValueError("Instagram Reels require at least 23 fps")
    return [round(seconds * FPS) for seconds in DURATIONS]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,default=ROOT)
    p.add_argument('--date');p.add_argument('--output',type=Path);p.add_argument('--frames-dir',type=Path)
    a=p.parse_args();source=a.source_root.resolve()
    issues=json.loads((source/'data/issues.json').read_text())
    issue=next((i for i in issues if i['date']==a.date),None) if a.date else issues[0]
    if not issue:raise ValueError('Requested issue missing')
    print(render(source,issue['date'],issue['displayDate'],a.output or ROOT/'assets/videos'/f"{issue['date']}.mp4",a.frames_dir))

if __name__=='__main__':main()
