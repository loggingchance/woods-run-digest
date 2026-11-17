#!/usr/bin/env python3
"""Compile complete public edition content into email payloads; sends no email."""
from __future__ import annotations
import hashlib
import html
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://woodsrun.forestenterprise.org'
from book_rotation import featured_item, resource_heading
from daily_resources import START as RESOURCE_START, validate_feature
from market_table import table_cells, table_html, DETAIL_STYLE, validate_market_table
from brandx_sponsor import validate_sponsor, sponsor_plain
UNSUB = '{{{RESEND_UNSUBSCRIBE_URL}}}'
BODY_STYLE='font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:25px;color:#333333;'
SUPPORT_STYLE='display:block;box-sizing:border-box;width:100%;padding:16px 20px;border:2px solid #b49757;border-radius:6px;background-color:#244631;color:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:18px;font-weight:700;line-height:26px;text-align:center;text-decoration:none;'
LINK_STYLE='font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:25px;color:#1f5b3a;'


SOCIAL_FOLLOW_START = '2026-11-11'
SOCIAL_FOLLOW_LINKS = (
    ('X', 'https://x.com/ForestBizSchool'),
    ('Instagram', 'https://www.instagram.com/northeastforests/'),
    ('LinkedIn', 'https://www.linkedin.com/in/steve-bick-loggingchance/'),
    ('YouTube', 'https://www.youtube.com/channel/UCq-PscVBAKjmVE39qb2NyCg'),
)


def validate_social_follow(soup):
    """Validate supplied navigation, then consume it once in the email footer."""
    panels = soup.select('.social-follow')
    if len(panels) > 1:
        raise ValueError('Duplicate social-follow navigation')
    for panel in panels:
        links = []
        for anchor in panel.find_all('a', recursive=False):
            label = anchor.get_text(' ', strip=True)
            if not label:
                image = anchor.find('img')
                label = ' '.join((image.get('alt') if image else '').split())
            links.append((label, anchor.get('href')))
        if (panel.name != 'nav' or len(links) != len(SOCIAL_FOLLOW_LINKS)
                or set(links) != set(SOCIAL_FOLLOW_LINKS)):
            raise ValueError('Social-follow navigation must contain the four approved profiles')
        panel.decompose()


def social_follow_html():
    """Two fixed-width columns with readable text, no icon or CSS dependency."""
    style = ('display:block;padding:12px 4px;border:1px solid #1f5b3a;'
             'border-radius:4px;background-color:#1f3b2b;color:#ffffff;'
             'font-family:Arial,Helvetica,sans-serif;font-size:16px;'
             'font-weight:bold;line-height:22px;text-align:center;text-decoration:none;')
    rows = []
    for offset in (0, 2):
        cells = ''.join(
            f'<td width="50%" style="width:50%;padding:4px;">'
            f'<a href="{url}" aria-label="Follow on {name}" style="{style}">{name}</a></td>'
            for name, url in SOCIAL_FOLLOW_LINKS[offset:offset + 2])
        rows.append('<tr>' + cells + '</tr>')
    return (f'<p style="{BODY_STYLE}">Follow along</p>'
            '<table class="social-follow" width="100%" cellpadding="0" cellspacing="0" '
            'border="0" role="presentation" style="width:100%;table-layout:fixed;">'
            + ''.join(rows) + '</table>')


def normalize_url(value: str) -> str:
    value=urljoin(SITE+'/', value.strip())
    parsed=urlsplit(value)
    if parsed.scheme not in ('https','http','mailto'):
        raise ValueError('Unsafe link in public issue')
    if parsed.hostname in ('woodsrun.forestenterprise.org','woods-run-digest.steve760060.chatgpt.site'):
        value=SITE+parsed.path+('?' + parsed.query if parsed.query else '')+('#'+parsed.fragment if parsed.fragment else '')
    if parsed.hostname == 'unsubscribe.resend.com' or 'token=' in parsed.query:
        raise ValueError('Personalized token must not enter a public email artifact')
    return value


def inline(node, urls: set[str]) -> str:
    if isinstance(node,NavigableString):return html.escape(str(node))
    if node.name in ('script','style','iframe','form','input','button','video'):
        raise ValueError('Active content is not allowed in the email source')
    children=''.join(inline(child,urls) for child in node.children)
    if node.name=='a':
        address=normalize_url(node.get('href',''))
        urls.add(address)
        style = SUPPORT_STYLE if "support-cta" in node.get("class", []) else LINK_STYLE
        return f'<a href="{html.escape(address,quote=True)}" style="{style}">{children}</a>'
    if node.name=='img':
        address=normalize_url(node.get('src',''))
        urls.add(address)
        alt=' '.join(node.get('alt','').split())
        return f'<img src="{html.escape(address,quote=True)}" alt="{html.escape(alt,quote=True)}" style="display:block;max-width:100%;height:auto;">'
    if node.name=='span' and node.find_parent('table', id='market-table'):
        return '<span style="'+DETAIL_STYLE+'">'+children+'</span>'
    if node.name=='br':return '<br>'
    if node.name in ('em','i'):return '<em>'+children+'</em>'
    return children


def newsletter_service_panel(article, day):
    """Recognize the canonical service ad without treating its layout as market data."""
    panels = article.select('section.newsletter-service-ad')
    if not panels:
        return None
    panel = panels[0]
    heading = panel.select_one('h2')
    link = panel.select('a[href]')
    expected_link = 'mailto:steve@northeastforests.com?subject=Weekly%20newsletter%20service'
    sharing = panel.find_next_sibling()
    top = panel.find_all(recursive=False)
    if (len(panels) != 1 or day < '2026-11-17'
            or date.fromisoformat(day).weekday() not in (1, 4)
            or panel.attrs != {'class': ['newsletter-service-ad'], 'data-service': 'newsletter',
                               'data-service-date': day}
            or not heading or heading.get_text(' ', strip=True) != 'Your news. Your audience. No extra work.'
            or len(link) != 1 or link[0]['href'] != expected_link
            or not sharing or 'growth-strip' not in sharing.get('class', [])
            or len(top) != 1 or top[0].name != 'table' or top[0].get('id') != 'newsletter-service-panel'):
        raise ValueError('Invalid canonical newsletter-service panel')
    # Preserve its authored markup, but permit only the inert elements and
    # attributes of the approved presentation table.
    allowed = {
        'table': {'cellpadding', 'cellspacing', 'id', 'role', 'style', 'width'},
        'tr': set(), 'td': {'bgcolor', 'style'}, 'p': {'style'},
        'h2': {'style'}, 'a': {'href', 'style'},
    }
    for node in panel.find_all():
        if (node.name not in allowed or node.attrs.keys() - allowed[node.name]
                or re.search(r'url\s*\(|expression\s*\(|@|\\', node.get('style', ''), re.I)):
            raise ValueError('Unsupported markup in canonical newsletter-service panel')
    return panel


def compile_payload(page: str, issue: dict) -> dict:
    soup=BeautifulSoup(page,'html.parser')
    article=soup.select_one('article.edition-wrap')
    if article is None:raise ValueError('Complete edition article not found')
    if issue['displayDate'] not in article.get_text(' ',strip=True):raise ValueError('Edition date mismatch')
    if issue['date'] >= SOCIAL_FOLLOW_START:
        validate_social_follow(soup)
    service_footers = soup.select('p.newsletter-service-footer')
    if len(service_footers) > 1:
        raise ValueError('Duplicate newsletter-service footer')
    service_footer = service_footers[0] if service_footers else None
    service_text = 'Click here to setup a weekly custom email newsletter for your organization.'
    service_url = 'https://news.forestenterprise.org/'
    if service_footer:
        anchors = service_footer.find_all('a')
        if (len(anchors) != 1 or anchors[0].get('href') != service_url
                or service_footer.get_text(' ', strip=True) != service_text):
            raise ValueError('Invalid newsletter-service footer')
        service_footer.decompose()
    sponsor = validate_sponsor(article, issue['date'])
    service_panel = newsletter_service_panel(article, issue['date'])
    # Approved cards retain the sharing section immediately after the card.
    for element in article.select('nav, .edition-nav' if sponsor or service_panel else 'nav, .edition-nav, .growth-strip'):
        element.decompose()
    validate_market_table(article, issue['date'])
    urls=set(); body=[]; plain=[]; source_paragraphs=[]
    for node in article.find_all(['section','div','h1','h2','h3','p','li','blockquote','figure','table']):
        if node is sponsor:
            body.append(str(sponsor))
            texts = sponsor_plain(sponsor)
            plain.extend(texts); source_paragraphs.extend(texts)
            urls.update(a['href'] for a in sponsor.find_all('a', href=True))
            urls.update(i['src'] for i in sponsor.find_all('img', src=True))
            continue
        if node is service_panel:
            body.append(str(service_panel))
            lines = [part.get_text(' ', strip=True) for part in service_panel.select('p,h2,a[href]')]
            links = [normalize_url(a['href']) for a in service_panel.find_all('a', href=True)]
            plain.extend(lines + links)
            source_paragraphs.extend(lines)
            urls.update(links)
            continue
        if node.name == 'section' or node.find_parent('section', class_=('brandx-sponsor', 'newsletter-service-ad')):
            continue
        if node.name == 'div' and not ((sponsor or service_panel) and 'growth-actions' in node.get('class', [])):
            continue
        if any(p.name in ('p','li','blockquote','figure') for p in node.parents if p is not article):continue
        if node.find_parent('table'):continue
        if node.name == 'table':
            rows = table_cells(node)
            body.append(table_html([[inline(cell, urls) for cell in row] for row in rows]))
            plain.append('Indicator | Latest | Change')
            for row in rows:
                texts = [' '.join(cell.get_text(' ', strip=True).split()) for cell in row]
                source_paragraphs.extend(texts)
                plain.append(' | '.join(texts))
                for cell in row:
                    for anchor in cell.find_all('a', href=True):
                        plain.append(normalize_url(anchor['href']))
            continue
        text=' '.join(node.get_text(' ',strip=True).split())
        rendered=inline(node,urls)
        if node.name=='figure':
            if not node.find('img',src=True):continue
            body.append(f'<div style="margin-top:20px;margin-bottom:20px;">{rendered}</div>')
            alt=' '.join((node.find('img').get('alt') or '').split())
            if alt:plain.append('Image: '+alt)
            continue
        if not text:continue
        source_paragraphs.append(text)
        if node.name.startswith('h'):
            level=node.name
            style='font-family:Georgia,Times New Roman,serif;font-size:24px;line-height:30px;color:#1f3b2b;'
        else:level='p';style=BODY_STYLE
        body.append(f'<{level} style="{style}">{rendered}</{level}>')
        plain.append(text)
        for anchor in node.find_all('a',href=True):plain.append(normalize_url(anchor['href']))
    if len(source_paragraphs)<5:raise ValueError('Edition content is too short')
    expected={normalize_url(a['href']) for a in article.find_all('a',href=True)}
    if expected-urls:raise ValueError('Source link lost while compiling email')
    item = (validate_feature(article, issue) if issue['date'] >= RESOURCE_START
            else featured_item(issue['date']))
    title, link = (item['title'], item['url']) if item else (None, None)
    if issue['date'] < RESOURCE_START and link not in urls:
        label=('Open '+html.escape(title)) if item.get('kind')=='app' else ('Explore '+html.escape(title))
        heading = resource_heading(issue['date'])
        title_html = (f'Books &amp; Apps: {html.escape(title)}</h2>' if heading == 'BOOKS & APPS'
                      else f'{html.escape(heading)}</h2><h3>{html.escape(title)}</h3>')
        body.append(f'<h2 style="font-family:Georgia,Times New Roman,serif;font-size:22px;line-height:28px;color:#1f3b2b;">{title_html}<p style="{BODY_STYLE}">{html.escape(item["description"])}</p><p style="{BODY_STYLE}"><a href="{link}" style="{LINK_STYLE}">{label}</a></p>')
        plain.extend((['BOOKS & APPS: '+title] if heading == 'BOOKS & APPS' else [heading,title])+[item['description'],link]);urls.add(link)
    page_url=SITE+issue['url'];subscribe=SITE+'/subscribe/'
    body.append(f'<p style="{BODY_STYLE}"><a href="{page_url}" style="{LINK_STYLE}">Read today’s web edition</a> · <a href="{subscribe}" style="{LINK_STYLE}">Subscribe</a></p>')
    plain.extend(['Read today’s web edition: '+page_url,'Subscribe: '+subscribe]);urls.update([page_url,subscribe])
    if issue['date'] >= SOCIAL_FOLLOW_START:
        body.append(social_follow_html())
        plain.extend(['Follow along'] + [f'{name}: {url}' for name, url in SOCIAL_FOLLOW_LINKS])
        urls.update(url for _, url in SOCIAL_FOLLOW_LINKS)
    if service_footer is not None:
        body.append(f'<p class="newsletter-service-footer" style="margin:20px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:20px;"><a href="{service_url}" style="font-size:13px;color:#365644;text-decoration:underline;">{service_text}</a></p>')
        plain.append(service_text + ' ' + service_url)
        urls.add(service_url)
    marker='<!-- OWNER_TEST_BANNER -->'
    wrapper='<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><meta http-equiv="X-UA-Compatible" content="IE=edge"></head><body style="margin-top:0;margin-right:0;margin-bottom:0;margin-left:0;background-color:#f2eee5;"><table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation"><tr><td bgcolor="#f2eee5" align="center" style="background-color:#f2eee5;padding-top:24px;padding-bottom:24px;"><table width="600" cellpadding="0" cellspacing="0" border="0" role="presentation" style="max-width:600px;width:100%;"><tr><td bgcolor="#fffdf8" style="background-color:#fffdf8;padding-top:28px;padding-right:30px;padding-bottom:28px;padding-left:30px;">'+marker+'<h1 style="font-family:Georgia,Times New Roman,serif;font-size:28px;line-height:34px;color:#1f3b2b;">WOODS RUN DIGEST</h1>'
    footer='</td></tr></table></td></tr></table></body></html>'
    full='\n'.join(body);text='\n\n'.join(plain)
    for paragraph in source_paragraphs:
        if paragraph not in text:raise ValueError('A source paragraph was lost')
    return {'date':issue['date'],'subject':'Woods Run Digest — '+issue['displayDate'],
            'html':wrapper+full+f'<p style="{BODY_STYLE}"><a href="{UNSUB}" style="{LINK_STYLE}">Unsubscribe</a></p>'+footer,
            'text':text+'\n\nUnsubscribe: '+UNSUB,
            'owner_test_html':wrapper+full+footer,'owner_test_text':text,
            'source_urls':sorted(expected),'all_urls':sorted(urls),'source_paragraph_count':len(source_paragraphs),
            'featured_item':dict(item) if item else None, 'featured_book':{'title':title,'url':link} if item else None,'links_preserved':True}


def main():
    today=datetime.now(ZoneInfo('America/Denver')).date().isoformat()
    issue=next((i for i in json.loads((ROOT/'data/issues.json').read_text()) if i.get('date')==today),None)
    if not issue:raise ValueError('Current-date edition is missing')
    page=(ROOT/today.replace('-','/')/'index.html').read_bytes()
    payload=compile_payload(page.decode('utf-8'),issue)
    payload['source_sha256']=hashlib.sha256(json.dumps(issue,sort_keys=True,ensure_ascii=False).encode()+b'\n'+page).hexdigest()
    output=ROOT/'data/email-payloads'/f'{today}.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'email_payload_ready':str(output.relative_to(ROOT)),'date':today,'links_preserved':True,'source_paragraph_count':payload['source_paragraph_count'],'featured_item':payload['featured_item'],'featured_book':payload['featured_book'],'email_sent':False}))

if __name__=='__main__':main()


