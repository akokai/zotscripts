# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import re
import argparse
from itertools import chain

from pyzotero import zotero
from boltons.iterutils import remap

import settings

CONSERVE_RX = [
    r'(?P<head>\w+)(?(head)(?P<hump>[A-Z0-9][a-z]*)|(?P=hump){2,})',
    r'[A-Z\.]{2,}',  # 'E.U.'
    r'\bI\b'
]
# Fails:
# - chemistry: 'C–H', 'bisphenol A',
# - proper nouns

CONSERVE = [re.compile(i) for i in CONSERVE_RX]

SEPARATORS = re.compile(r'([\:\?\!\.]\s|\s+\|\s|\s+[-–—]\s|—)')


def all_coll_items(zot, *args, **kwargs):
    '''
    Lazy generator for all items in a collection.

    Modified from: https://gist.github.com/rdhyee/404573708a805861edb5
    '''
    for page in chain([zot.collection_items(*args, **kwargs)],
                      zot.iterfollow()):
        for item in page:
            yield item


def get_all_titles(items):
    '''Get all main titles from a list of Zotero items.'''
    titles = []

    def visit(path, key, value):
        if key == 'title':
            titles.append(value)
        return False

    remap(items, visit=visit)
    return titles


def sentence_case(text):
    '''Convert a fragmentary phrase to sentence case, somewhat sensibly.'''
    if SEPARATORS.match(text):
        return text

    words = []

    for word in text.split():
        if any([p.search(word) for p in CONSERVE]):
            words.append(word)
        else:
            words.append(word.lower())

    try:
        if words[0][0] in '\'"“‘':
            words[0] = words[0][0] + words[0][1].upper() + words[0][2:]
        else:
            words[0] = words[0][0].upper() + words[0][1:]
        result = ' '.join(words)
    except (IndexError, TypeError):
        result = text

    return result


def to_sentence_case(title):
    '''Attempt to sensibly convert a title to sentence case.'''
    if title == '':
        return title

    parts = SEPARATORS.split(title)
    new_title = ''.join([sentence_case(part) for part in parts])
    return new_title


def item_titles_to_sentence(item, keys=['title', 'shortTitle', 'bookTitle']):
    '''
    Change an item's various titles to sentence case.

    Only return the item if it has been changed, otherwise return None.
    Ignore notes and attachments.
    '''
    if item['data']['itemType'] in ['attachment', 'note']:
        return None

    mod = False

    for key in keys:
        try:
            new_title = to_sentence_case(item['data'][key])
            if new_title != item['data'][key]:
                item['data'][key] = new_title
                print('{:<10}'.format(key), item['data'][key])
                mod = True
        except KeyError:
            pass

    return item if mod else None


def zot_titles_to_sentence(zot, coll_id=settings.TEST_COLL_ID, dry_run=False):
    '''
    Get items from a Zotero collection & change their titles to sentence case.

    Changes items on the server (or not at all) and does not return anything.
    '''
    print(zot.num_collectionitems(coll_id), 'items in collection.')
    items = all_coll_items(zot, coll_id)

    for item in items:
        new_item = item_titles_to_sentence(item)
        if new_item and not dry_run:
            zot.update_item(new_item)


def journal_cleanup(item):
    '''
    If item is journal article, delete the URL if there's a DOI.

    Only return the item if it has been changed, otherwise return None.
    '''
    if item['data']['itemType'] != 'journalArticle':
        return None

    mod = False

    try:
        if item['data']['DOI'] and item['data']['url']:
            print('DOI:  ', item['data']['DOI'])
            print('- URL:', item['data']['url'])
            item['data']['url'] = ''
            mod = True
        # if item['data']['accessDate']:
        #     item['data']['accessDate'] = ''
        #     print('Cleared accessDate:', item['data']['key'])
        #     mod = True
    except KeyError:
        pass

    return item if mod else None


def zot_journal_cleanup(zot, coll_id=settings.TEST_COLL_ID, dry_run=False):
    '''
    Get items from a collection & clean up some fields for journal articles.

    Changes items on the server (or not at all) and does not return anything.
    '''
    print(zot.num_collectionitems(coll_id), 'items in collection.')
    items = all_coll_items(zot, coll_id)

    for item in items:
        new_item = journal_cleanup(item)
        if new_item and not dry_run:    # Only update if there was a change.
            zot.update_item(new_item)


def main():
    '''
    Perform batch operations on a Zotero collection.
    '''
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('-c', '--collection', action='store', type=str,
                        help='collection ID', default=settings.TEST_COLL_ID)
    parser.add_argument('-d', '--dry_run', action='store_true',
                        help='only print info, don\'t update',
                        default=False)
    parser.add_argument('-t', '--titles', action='store_true',
                        help='process titles', default=False)
    parser.add_argument('-j', '--journal', action='store_true',
                        help='process journal articles', default=False)
    args = parser.parse_args()

    zot = zotero.Zotero(settings.USER_ID, 'user', settings.API_KEY)

    if args.titles:
        zot_titles_to_sentence(zot, args.collection, args.dry_run)

    if args.journal:
        zot_journal_cleanup(zot, args.collection, args.dry_run)


if __name__ == '__main__':
    main()
