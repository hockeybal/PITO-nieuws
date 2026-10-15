"""Local football destinations, separate from PITO's editorial coverage."""
from html import escape
from urllib.parse import urlparse
import news


def block(municipality=''):
    names = {m['slug']: m['name'] for m in news.read('municipalities')}
    clubs = [c for c in news.read('sports-sources')
             if c.get('sport') == 'voetbal'
             and c.get('municipality') in names
             and (not municipality or c['municipality'] == municipality)]
    groups = {}
    for club in sorted(clubs, key=lambda c: c['name'].casefold()):
        url = club.get('url', '')
        if urlparse(url).scheme not in ('http', 'https'):
            continue
        groups.setdefault(club['municipality'], []).append(
            '<a href="'+escape(url, quote=True)+'" target="_blank" rel="noopener">'
            +escape(club['name'])+'<span>Clubwebsite ›</span></a>')
    if not groups:
        return ''
    cards = ''.join('<div class="football-club-group"><h3>'+escape(names[slug])+'</h3>'
                    +''.join(groups[slug])+'</div>'
                    for slug in sorted(groups, key=lambda s: names[s]))
    area = names.get(municipality, 'de provincie Utrecht')
    return ('<section class="football-directory"><details><summary>Voetbalclubs in '
            +escape(area)+'<span>Bekijk de clubs</span></summary>'
            '<p>Rechtstreeks naar je club voor programma, uitslagen en afgelastingen.</p>'
            '<div class="football-club-grid">'+cards+'</div></details></section>')
