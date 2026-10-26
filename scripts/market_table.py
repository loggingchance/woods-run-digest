"""Six-row By the Numbers presentation, effective 2026-10-27.

Observations are verified by the daily editor, never inferred by this renderer.
Missing observations render unavailable; monthly dates and contracts are inputs.
"""
import html
from urllib.parse import urlsplit

START = '2026-10-27'
ROWS = (
    ('diesel', 'U.S. on-highway diesel', 'US$/gal'),
    ('lumber_futures', 'Lumber futures', 'US$/MBF; name the current contract'),
    ('madisons', 'Madison’s lumber index', 'US$/MBF'),
    ('hardwood_ppi', 'Hardwood lumber PPI', 'BLS WPU0812; index, 1982 = 100; not seasonally adjusted'),
    ('housing_starts', 'U.S. single-family housing starts', 'Units; seasonally adjusted annual rate'),
    ('cad_usd', 'Canadian dollar', 'C$ per US$1; daily average'),
)
TABLE_STYLE = 'width:100%;table-layout:fixed;border-collapse:collapse;border:1px solid #c7d1c0;font-family:Arial,Helvetica,sans-serif;'
DETAIL_STYLE = 'display:block;font-size:12px;line-height:17px;color:#596553;margin-top:6px;'
HEADER_STYLE = 'padding:11px 8px;background-color:#243f2c;color:#fffdf8;font-size:15px;line-height:21px;text-align:left;border-bottom:3px solid #b49757;'
SOURCE_URLS = dict(
    diesel='https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=EMD_EPD2D_PTE_NUS_DPG',
    lumber_futures='https://www.investing.com/commodities/lumber-historical-data',
    madisons='https://madisonsreport.com/',
    hardwood_ppi='https://fred.stlouisfed.org/series/WPU0812',
    housing_starts='https://www.census.gov/construction/nrc/current/index.html',
    cad_usd='https://www.bankofcanada.ca/rates/exchange/daily-exchange-rates/')


def detail(text):
    return '<span style="' + DETAIL_STYLE + '">' + html.escape(str(text)) + '</span>'


def table_html(rows):
    """Accept six ordered triples of already escaped/validated inline HTML."""
    if len(rows) != 6 or any(len(row) != 3 for row in rows):
        raise ValueError('By the Numbers requires six three-cell rows')
    output = '<table id="market-table" aria-label="By the Numbers market indicators" border="0" cellpadding="0" cellspacing="0" width="100%" style="' + TABLE_STYLE + '">'
    output += '<colgroup>' + ''.join('<col style="width:'+str(w)+'%">' for w in (35,33,32)) + '</colgroup><thead><tr>'
    for width, label in zip((35,33,32), ('Indicator','Latest','Change')):
        output += '<th scope="col" align="left" width="'+str(width)+'%" bgcolor="#243f2c" style="'+HEADER_STYLE+'">'+label+'</th>'
    output += '</tr></thead><tbody>'
    for index, row in enumerate(rows):
        color = '#f2f5ee' if index % 2 == 0 else '#fffdf8'
        output += '<tr>'
        for column, text in enumerate(row):
            tag = 'th' if column == 0 else 'td'
            style = 'padding:13px 8px;vertical-align:top;text-align:left;border-bottom:1px solid #d8dfd1;background-color:'+color+';overflow-wrap:break-word;'
            style += 'font-size:'+('14' if column == 2 else '15')+'px;line-height:21px;'
            if column == 0: style += 'font-weight:normal;'
            style += 'color:#24352a;'
            output += '<'+tag+(' scope="row" align="left"' if column == 0 else '')+' bgcolor="'+color+'" style="'+style+'">'+text+'</'+tag+'>'
        output += '</tr>'
    return output+'</tbody></table>'


def render_market_section(day, observations, caveats=()):
    """Render fresh, last-verified or unavailable inputs without inventing values.

    Each keyed observation: latest, observed, change (list), comparison, detail,
    status (verified/last_verified/unavailable), sources [{label,url}]. Optional
    data omissions produce dated unavailable cells, not a publication failure.
    """
    rows, sources = [], []
    for key, title, units in ROWS:
        item = observations.get(key) or {}
        status = item.get('status', 'unavailable')
        usable = status in ('verified','last_verified') and item.get('latest') and item.get('observed')
        latest = str(item['latest']) if usable else 'Unavailable'
        observed = str(item['observed']) if usable else 'Not verified as of '+day
        if usable and status == 'last_verified': observed += ' — last verified; update unavailable'
        changes = item.get('change') if usable else None
        if not isinstance(changes, list) or not changes or not item.get('comparison'):
            changes, comparison = ['Unavailable'], 'Comparison not verified as of '+day
        else:
            comparison = item['comparison']
        rows.append((html.escape(title)+detail(item.get('detail') or units),
                     html.escape(latest)+detail(observed),
                     '<br>'.join(html.escape(str(c)) for c in changes)+detail(comparison)))
        for source in item.get('sources') or [{'label': title, 'url': SOURCE_URLS[key]}]:
            url = source.get('url', '')
            if urlsplit(url).scheme == 'https' and urlsplit(url).hostname:
                sources.append('<a href="'+html.escape(url, quote=True)+'">'+html.escape(source.get('label') or title)+'</a>')
    notes = ['Housing starts are annualized estimates, not actual monthly units, and are subject to revision.',
             'The hardwood PPI is an index, not a dollar price. Exchange rates are daily averages. MBF means thousand board feet.']
    notes.extend(str(note) for note in caveats)
    return ('<section class="by-the-numbers"><h2>By the Numbers</h2><p>Latest available observations as of '+html.escape(day)+
            '. Dates and comparison periods vary by series; monthly figures remain unchanged between releases.</p>' +
            table_html(rows)+'<p>'+html.escape(' '.join(notes))+'</p><p>Sources:<br>'+('<br>'.join(dict.fromkeys(sources)) or 'Source observations unavailable; no values invented.')+'</p></section>')


def table_cells(table):
    if table.get('id') != 'market-table' or table.find('table'):
        raise ValueError('Unsupported or nested content table')
    headers = table.select('thead th')
    if [c.get_text(' ', strip=True) for c in headers] != ['Indicator','Latest','Change']:
        raise ValueError('Incorrect market table columns')
    body = table.find('tbody', recursive=False)
    rows = body.find_all('tr', recursive=False) if body else []
    cells = [row.find_all(['th','td'], recursive=False) for row in rows]
    if len(cells) != 6 or any(len(row) != 3 or row[0].name != 'th' for row in cells):
        raise ValueError('Expected six market rows with one indicator and two data cells')
    return cells


def validate_market_table(article, day):
    if day < START: return
    tables = article.select('table#market-table')
    if len(tables) != 1: raise ValueError('Expected exactly one By the Numbers table')
    cells = table_cells(tables[0])
    required = ('diesel','lumber futures','madison','hardwood','single-family','canadian dollar')
    for row, phrase in zip(cells, required):
        if phrase not in row[0].get_text(' ', strip=True).lower():
            raise ValueError('Incorrect market indicator order')
        if any(not cell.get_text(' ', strip=True) for cell in row):
            raise ValueError('Use explicit unavailable text for missing observations')
