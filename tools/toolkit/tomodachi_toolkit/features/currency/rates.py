"""Live exchange rates."""
import json
import urllib.request


RATE_URL = 'https://open.er-api.com/v6/latest/JPY'


def fetch_rates():
    with urllib.request.urlopen(RATE_URL, timeout=10) as r:
        return json.load(r)['rates']
