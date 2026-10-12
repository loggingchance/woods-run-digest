"""Authoritative featured-book rotation; preserve selections before the expansion."""
import datetime
import html
import json
import sys

BOOKS = (
    {'title': 'Wet Woods', 'authors': 'Steven Bick', 'url': 'https://www.amazon.com/dp/B0FP98Y3YN', 'description': 'Today’s featured title from Steven Bick.'},
    {'title': 'Timber Tempo', 'authors': 'Steven Bick', 'url': 'https://www.amazon.com/dp/B0DRYY34KW', 'description': 'Today’s featured title from Steven Bick.'},
    {'title': 'After Wood', 'authors': 'Steven Bick', 'url': 'https://www.amazon.com/dp/B0DRYZLRTF', 'description': 'Today’s featured title from Steven Bick.'},
    {'title': 'Continuous Improvement in Logging', 'authors': 'Steven Bick and Jeffrey G. Benjamin', 'url': 'https://cinl.loggingchance.com/', 'description': 'Steven Bick and Jeffrey G. Benjamin apply the Theory of Constraints to logging operations, covering bottlenecks, productivity, throughput accounting and practical steps for continuous improvement.'},
)
EXPANSION_DATE = datetime.date(2026, 10, 13)

def featured_book(day):
    if isinstance(day, str):
        day = datetime.date.fromisoformat(day)
    if day < EXPANSION_DATE:
        return dict(BOOKS[(day - datetime.date(2026, 10, 3)).days % 3])
    return dict(BOOKS[((day - EXPANSION_DATE).days + 3) % len(BOOKS)])

def book_html(day):
    book = featured_book(day)
    return ('<section class="wet-woods-box"><p class="section-kicker">FEATURED BOOK</p>'
            '<h2>' + html.escape(book['title']) + '</h2><p>' + html.escape(book['description']) +
            '</p><p><a class="book-button" href="' + html.escape(book['url'], quote=True) + '">Explore ' +
            html.escape(book['title']) + ' →</a></p></section>')

if __name__ == '__main__':
    day = sys.argv[1]
    print(json.dumps(featured_book(day), ensure_ascii=False))
    print(book_html(day))
