"""Authoritative Woods Run Books & Apps rotation."""
import datetime
import html
import json
import sys

ITEMS = (
    {
        'kind': 'book',
        'title': 'Wet Woods',
        'authors': 'Steven Bick',
        'url': 'https://www.amazon.com/dp/B0FP98Y3YN',
        'description': 'Wet Woods follows loggers, foresters and mill operators adapting to wetter, less predictable conditions in the Northeast. It focuses on the practical decisions people are making as climate and operating conditions change.',
    },
    {
        'kind': 'book',
        'title': 'Timber Tempo',
        'authors': 'Steven Bick',
        'url': 'https://www.amazon.com/dp/B0DRYY34KW',
        'description': 'Timber Tempo applies Critical Chain Project Management to forestry and forest-products work through practical examples from timber procurement, land management and mill operations. It focuses on reducing delay, multitasking and workflow friction.',
    },
    {
        'kind': 'book',
        'title': 'After Wood',
        'authors': 'Steven Bick',
        'url': 'https://www.amazon.com/dp/B0DRYZLRTF',
        'description': 'After Wood is a practical retirement-planning guide for loggers, foresters, mill operators and other forest-products business owners. It addresses seasonal income, equipment-heavy businesses and the question of how much is enough for retirement.',
    },
    {
        'kind': 'book',
        'title': 'Continuous Improvement in Logging',
        'authors': 'Steven Bick and Jeffrey G. Benjamin',
        'url': 'https://cinl.loggingchance.com/',
        'description': 'Steven Bick and Jeffrey G. Benjamin apply the Theory of Constraints to logging operations, covering bottlenecks, productivity, throughput accounting and practical steps for continuous improvement.',
    },
    {
        'kind': 'app',
        'title': 'Woods-Ready Safety Plan',
        'authors': 'Northeastern Loggers’ Association / Northeast Forests LLC',
        'url': 'https://wrsp.lumbermen.org/',
        'description': 'The free Woods-Ready Safety Plan helps logging crews assemble coordinates, responder directions, contacts, hazards and emergency-equipment details into one shareable job-site plan. It runs in a browser and keeps saved plans and its Quick Guide available offline after the app has loaded.',
    },
)

# Preserve historical selections through October 13. Beginning October 14 the
# recurring sequence is Wet Woods -> Timber Tempo -> After Wood ->
# Continuous Improvement in Logging -> Woods-Ready Safety Plan -> repeat.
LEGACY_THREE = ITEMS[:3]
LEGACY_FOUR = ITEMS[:4]
FOUR_BOOK_EXPANSION_DATE = datetime.date(2026, 10, 13)
BOOKS_AND_APPS_START = datetime.date(2026, 10, 14)

# Backward-compatible name for callers that still import BOOKS.
BOOKS = LEGACY_FOUR


def featured_item(day):
    if isinstance(day, str):
        day = datetime.date.fromisoformat(day)
    if day < FOUR_BOOK_EXPANSION_DATE:
        return dict(LEGACY_THREE[(day - datetime.date(2026, 10, 3)).days % 3])
    if day < BOOKS_AND_APPS_START:
        # October 13, 2026 remains Continuous Improvement in Logging.
        return dict(LEGACY_FOUR[((day - FOUR_BOOK_EXPANSION_DATE).days + 3) % len(LEGACY_FOUR)])
    return dict(ITEMS[(day - BOOKS_AND_APPS_START).days % len(ITEMS)])


# Backward-compatible function name used by existing downstream code.
def featured_book(day):
    return featured_item(day)


def item_html(day):
    item = featured_item(day)
    verb = 'Open' if item['kind'] == 'app' else 'Explore'
    return (
        '<section class="wet-woods-box"><p class="section-kicker">BOOKS &amp; APPS</p>'
        '<h2>' + html.escape(item['title']) + '</h2><p>' + html.escape(item['description']) +
        '</p><p><a class="book-button" href="' + html.escape(item['url'], quote=True) + '">' +
        verb + ' ' + html.escape(item['title']) + ' →</a></p></section>'
    )


# Backward-compatible helper name.
def book_html(day):
    return item_html(day)


if __name__ == '__main__':
    day = sys.argv[1]
    print(json.dumps(featured_item(day), ensure_ascii=False))
    print(item_html(day))
