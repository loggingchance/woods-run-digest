#!/usr/bin/env python3
"""Compile complete public edition content into email payloads; sends no email."""
from __future__ import annotations
import hashlib
import html
import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://woods-run-digest.steve760060.chatgpt.site'
BOOKS = [('Wet Woods', 'https://www.amazon.com/dp/B0FP98Y3YN'),
         ('Timber Tempo', 'https://www.amazon.com/dp/B0DRYY34KW'),
         ('After Wood', 'https://www.amazon.com/dp/B0DRYZLRTF')]
UNSUB = '{{{RESEND_UNSUBSCRIBE_URL}}}'
BODY_STYLE='font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:25px;color:#333333;'
LINK_STYLE='font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:25px;color:#1f5b3a;'


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
        return f'<a href="{html.escape(address,quote=True)}" style="{LINK_STYLE}">{children}</a>'
    if node.name=='br':return '<br>'
    if node.name in ('em','i'):return '<em>'+children+'</em>'
    return children


def compile_payload(page: str, issue: dict) -> dict:
    soup=BeautifulSoup(page,'html.parser')
    article=soup.select_one('article.edition-wrap')
    if article is None:raise ValueError('Complete edition article not found')
    if issue['displayDate'] not in article.get_text(' ',strip=True):raise ValueError('Edition date mismatch')
    for element in article.select('nav, .edition-nav, .growth-strip'):
        element.decompose()
    urls=set(); body=[]; plain=[]; source_paragraphs=[]
    for node in article.find_all(['h1','h2','h3','p','li','blockquote']):
        if any(p.name in ('p','li','blockquote') for p in node.parents if p is not article):continue
        text=' '.join(node.get_text(' ',strip=True).split())
        if not text:continue
        source_paragraphs.append(text)
        rendered=inline(node,urls)
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
    title,link=BOOKS[(date.fromisoformat(issue['date'])-date(2026,10,3)).days%3]
    if link not in urls:
        body.append(f'<h2 style="font-family:Georgia,Times New Roman,serif;font-size:22px;line-height:28px;color:#1f3b2b;">Featured book: {html.escape(title)}</h2><p style="{BODY_STYLE}"><a href="{link}" style="{LINK_STYLE}">View {html.escape(title)} on Amazon</a></p>')
        plain.extend(['FEATURED BOOK: '+title,link]);urls.add(link)
    page_url=SITE+issue['url'];subscribe=SITE+'/subscribe/'
    body.append(f'<p style="{BODY_STYLE}"><a href="{page_url}" style="{LINK_STYLE}">Read today’s web edition</a> · <a href="{subscribe}" style="{LINK_STYLE}">Subscribe</a></p>')
    plain.extend(['Read today’s web edition: '+page_url,'Subscribe: '+subscribe]);urls.update([page_url,subscribe])
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
            'featured_book':{'title':title,'url':link},'links_preserved':True}


def main():
    today=datetime.now(ZoneInfo('America/Denver')).date().isoformat()
    issue=next((i for i in json.loads((ROOT/'data/issues.json').read_text()) if i.get('date')==today),None)
    if not issue:raise ValueError('Current-date edition is missing')
    page=(ROOT/today.replace('-','/')/'index.html').read_bytes()
    payload=compile_payload(page.decode('utf-8'),issue)
    payload['source_sha256']=hashlib.sha256(json.dumps(issue,sort_keys=True,ensure_ascii=False).encode()+b'\n'+page).hexdigest()
    output=ROOT/'data/email-payloads'/f'{today}.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'email_payload_ready':str(output.relative_to(ROOT)),'date':today,'links_preserved':True,'source_paragraph_count':payload['source_paragraph_count'],'featured_book':payload['featured_book'],'email_sent':False}))

if __name__=='__main__':main()
