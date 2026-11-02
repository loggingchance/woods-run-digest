"""Compact market explanations; retain the complete notes on the web."""
import re
import html
from bs4 import BeautifulSoup
START = '2026-11-02'
SCRIPT = '<script src="/assets/market-notes.js" defer></script>'

def compact_market_notes(page, day):
    if day < START: return page
    pattern = r'(<section\b[^>]*class=["\'][^"\']*(?:by-the-numbers|price-tracker)[^"\']*["\'][^>]*>)(.*?)(</section>)'
    def wrap(m):
        body=m[2]
        if 'id="market-notes"' in body: return m[0]
        end=body.find('</table>')
        if end < 0: return m[0]
        end+=len('</table>')
        tail=body[end:]
        notes=[]
        for p in re.finditer(r'\s*<p\b[^>]*>.*?</p>',tail,re.S):
            if p.start() != sum(map(len, notes)): break
            text=BeautifulSoup(p[0],'html.parser').get_text(' ',strip=True)
            if text.lower().startswith('sources:'): break
            notes.append(p[0])
        if not notes: return m[0]
        length=sum(map(len,notes))
        disclosure='<details id="market-notes" class="market-notes" style="margin:10px 0 16px;scroll-margin-top:20px;"><summary style="cursor:pointer;padding:10px 0;color:#1f5b3a;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:24px;text-decoration:underline;">About these numbers</summary>'+''.join(notes)+'</details>'
        return m[1]+body[:end]+disclosure+tail[length:]+m[3]
    page=re.sub(pattern,wrap,page,flags=re.S)
    if 'id="market-notes"' in page and '/assets/market-notes.js' not in page:
        page=page.replace('</body>',SCRIPT+'</body>')
    return page

def email_notes_link(page, issue_url):
    """Replace only the identified notes, never table cells or story paragraphs."""
    url=html.escape(issue_url+'#market-notes',quote=True)
    return re.sub(r'<details\b(?=[^>]*\bid=["\']market-notes["\'])[^>]*>.*?</details>', '<p class="market-notes-link"><a href="'+url+'" style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:24px;color:#1f5b3a;text-decoration:underline;">About these numbers</a></p>',page,flags=re.S)
