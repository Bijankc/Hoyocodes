"""Checks the Ennead API for new HoYoverse codes and pushes them to ntfy.

Only reads public code lists - no game account or cookies involved.
"""
import json
import os
import sys
import urllib.request

GAMES = {
    'genshin': {'name': 'Genshin Impact', 'url': 'https://genshin.hoyoverse.com/en/gift?code='},
    'starrail': {'name': 'Honkai: Star Rail', 'url': 'https://hsr.hoyoverse.com/gift?code='},
    'zenless': {'name': 'Zenless Zone Zero', 'url': 'https://zenless.hoyoverse.com/redemption?code='},
    'honkai': {'name': 'Honkai Impact 3rd', 'url': ''},  # In-game redemption only
    'themis': {'name': 'Tears of Themis', 'url': 'https://tot.hoyoverse.com/gift/?code='},
}

STATE_FILE = os.environ.get('STATE_FILE', 'seen-codes.json')
NTFY_TOPIC = os.environ.get('NTFY_TOPIC', '').strip()
NTFY_SERVER = os.environ.get('NTFY_SERVER', 'https://ntfy.sh').rstrip('/')
WATCH = [g.strip() for g in os.environ.get('WATCH_GAMES', 'genshin').split(',') if g.strip()]


def fetch_active_codes(slug):
    req = urllib.request.Request(
        f'https://api.ennead.cc/mihoyo/{slug}/codes',
        headers={'User-Agent': 'Hoyocodes-notifier'},
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.load(res).get('active', [])


def notify(title, message, click_url='', tags='gift'):
    if not NTFY_TOPIC:
        print(f'[dry run] {title}: {message} {click_url}')
        return
    headers = {'Title': title, 'Tags': tags}
    if click_url:
        headers['Click'] = click_url
    req = urllib.request.Request(
        f'{NTFY_SERVER}/{NTFY_TOPIC}',
        data=message.encode('utf-8'),
        headers=headers,
        method='POST',
    )
    urllib.request.urlopen(req, timeout=20).close()


def main():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            seen = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        seen = {}
    first_run = not seen
    changed = False

    for slug in WATCH:
        game = GAMES.get(slug)
        if not game:
            print(f'Unknown game "{slug}", skipping')
            continue
        try:
            active = fetch_active_codes(slug)
        except Exception as err:
            # Leave this game's state untouched so nothing is missed next run
            print(f'Failed to fetch {game["name"]}: {err}')
            continue

        # A game with no saved state is seeded silently instead of sending every current code
        known = set(seen.get(slug, []))
        is_new_game = slug not in seen
        for item in active:
            code = item['code']
            if code in known:
                continue
            known.add(code)
            changed = True
            if is_new_game:
                continue
            rewards = ', '.join(item.get('rewards', [])) or 'Unknown rewards'
            link = game['url'] + code if game['url'] else ''
            hint = 'Tap to redeem' if link else 'Redeem in-game'
            notify(f'New {game["name"]} code', f'{code}\n{rewards}\n{hint}', link)
            print(f'Notified: {slug} {code}')

        seen[slug] = sorted(known)

    if first_run and changed:
        notify('Hoyocodes notifier is set up',
               f'Watching: {", ".join(GAMES[s]["name"] for s in WATCH if s in GAMES)}. '
               'You will get a notification here when a new code appears.',
               tags='white_check_mark')

    if changed:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(seen, f, indent=2)

    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f'changed={"true" if changed else "false"}\n')


if __name__ == '__main__':
    sys.exit(main())
