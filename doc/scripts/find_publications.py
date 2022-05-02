# Author: Christian Brodbeck <christianbrodbeck@nyu.edu>
"""
Reuires https://github.com/maenu/scholar.py::

    pip install https://github.com/maenu/scholar.py/archive/master.zip

!! Run from interpreter to retain data for debugging access

run find_publications.py, then copy-paste download function

"""
from argparse import ArgumentParser
import json
from pathlib import Path
import pickle
import random
import re
import time

from eelbrain._utils import ask
from pybtex.database import BibliographyData, parse_bytes, parse_file
import requests


# Query
API_KEY_PATH = Path('~/.serpapi_key').expanduser()
API_KEY = API_KEY_PATH.read_text().strip()
DIR = Path(__file__).absolute().parent
SEARCH_CACHE = DIR / 'cache.json'
SELECTION_PATH = DIR / 'selection.json'
BIBTEX_CACHE = DIR / 'bibtex.pickle'
# Parse
DST = DIR.parent / 'publications.bib'
BIORXIV_OBSOLETE = """
10.1101/326785
2018/10/09/439158
10.1101/2020.08.17.254482
10.1101/421727
10.1101/2021.10.15.464457
""".split()
ACRONYMS = ['EEG', 'MEG', 'MRI']


def search():
    entries = []
    # download entries
    total_results = None
    num = 20
    start = 0
    while True:
        r = requests.get(f"https://serpapi.com/search.json?engine=google_scholar&q=%22eelbrain%22&as_ylo=2015&hl=en&start={start}&num={num}&as_vis=1&api_key={API_KEY}")
        content = json.loads(r.content)
        if not total_results:
            total_results = content['search_information']['total_results']
        entries.extend(content['organic_results'])
        # next page
        start += num
        if start >= total_results:
            break
    # write to file
    with SEARCH_CACHE.open('wt') as file:
        json.dump(entries, file)


def select():
    if SELECTION_PATH.exists():
        with SELECTION_PATH.open('rt') as file:
            selection = json.load(file)
    else:
        selection = {}
    with SEARCH_CACHE.open('rt') as file:
        entries = json.load(file)
    # ask for each new entry
    for entry in entries:
        result_id = entry['result_id']
        if result_id in selection:
            continue
        print(entry['title'])
        print(entry['publication_info']['summary'])
        print(entry['link'])
        response = ask("Add?", {'y': 'Include in bibliography', 'n': 'Skip', 'x': 'Abort selection'})
        if response == 'x':
            break
        elif response == 'y':
            selection[result_id] = True
        elif response == 'n':
            selection[result_id] = False
        else:
            raise RuntimeError(f'{response=}')
    with SELECTION_PATH.open('wt') as file:
        json.dump(selection, file)


def download():
    "Download BiBTeX entries"
    if BIBTEX_CACHE.exists():
        with BIBTEX_CACHE.open('rb') as file:
            bibtex_cache = pickle.load(file)
    else:
        bibtex_cache = {}
    with SELECTION_PATH.open('rt') as file:
        selections = json.load(file)
    # download missing citations
    new = 0
    for result_id, include in selections.items():
        if not include or result_id in bibtex_cache:
            continue
        r = requests.get(f'https://serpapi.com/search.json?engine=google_scholar_cite&q={result_id}&api_key={API_KEY}')
        content = json.loads(r.content)
        if 'links' not in content:
            print(f"Links not found:\n{content}")
            break
        for style_entry in content['links']:
            if style_entry['name'] == 'BibTeX':
                bibtex_url = style_entry['link']
                break
        else:
            print(f"BibTeX link not found in:\n{r.content.decode()}")
            break
        r = requests.get(bibtex_url)
        if r.status_code == 403:
            print(r.content.decode())
            break
        print(result_id, end=', ')
        bibtex_cache[result_id] = r.content
        new += 1
        time.sleep(random.uniform(5.432, 15.476))
    if not new:
        print("No new reference")
        return
    with BIBTEX_CACHE.open('wb') as file:
        pickle.dump(bibtex_cache, file)


def parse():
    with BIBTEX_CACHE.open('rb') as file:
        bibtex_entries = pickle.load(file)
    with SEARCH_CACHE.open('rt') as file:
        raw_entries = json.load(file)
    with SELECTION_PATH.open('rt') as file:
        selection = json.load(file)
    raw_entries = {entry['result_id']: entry for entry in raw_entries}
    # extract citation data
    bib = parse_file(DST, 'bibtex')
    unseen_keys = set(bib.entries.keys())
    for result_id, raw_bibtex in bibtex_entries.items():
        if not selection[result_id]:
            continue
        raw_bibtex = re.sub(rb'[^\x00-\x7F]+', b' ', raw_bibtex)
        # parse entry
        data = parse_bytes(raw_bibtex, 'bibtex')
        assert len(data.entries) == 1
        ((key, entry),) = data.entries.items()
        if key in bib.entries:
            if key not in unseen_keys:
                raise NotImplementedError('Duplicate cite key')
            unseen_keys.remove(key)
            continue
        url = raw_entries[result_id]['link']
        journal = entry.fields.get('journal', '').lower()
        doi = None
        if entry.type == 'phdthesis':
            pass
        elif journal == 'biorxiv':
            if match := re.match(r"https://www\.biorxiv\.org/content/([\d./]+)\.abstract", url):
                doi = match.group(1)
            elif match := re.match(r"https://www\.biorxiv\.org/content/biorxiv/early/([\d./]+)\.full.pdf", url):
                pass  # DOI unknown
            else:
                raise RuntimeError(f"Can't identify DOI from {url=}")
        elif not journal:
            if entry.fields.get('publisher') == 'PsyArXiv':
                entry.fields['journal'] = '{PsyArXiv}'
            else:
                entry.fields['journal'] = '???'
                print('Warning: missing journal')
        if doi:
            if doi in BIORXIV_OBSOLETE:
                continue
            entry.fields['doi'] = doi
        else:
            entry.fields['url'] = url
        entry.fields['google_result_id'] = result_id
        # store
        if key in bib.entries:
            i = 2
            while f'{key}_{i}' in bib.entries:
                i += 1
            key = f'{key}_{i}'
        # fix title
        for repl in ACRONYMS:
            entry.fields['title'] = re.sub(repl, '{' + repl + '}', entry.fields['title'])
        bib.add_entry(key, entry)
    # Fix escape-char bug in PybTex
    out = bib.to_bytes('bibtex')
    for bad_char in [br'\&', b'_']:
        out = out.replace(b'\\' + bad_char, bad_char)
    DST.write_bytes(out)


if __name__ == '__main__':
    parser = ArgumentParser(description="Find publications that used Eelbrain on Google Scholar")
    parser.add_argument('task', choices=('search', 'select', 'download', 'parse'))
    args = parser.parse_args()
    if args.task == 'search':
        search()
    elif args.task == 'select':
        select()
    elif args.task == 'download':
        download()
    elif args.task == 'parse':
        parse()
