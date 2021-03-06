"""Scripts & operations for maintaining my Zotero library using Pyzotero."""

import re
import argparse
from itertools import chain
from pyzotero import zotero
from boltons.iterutils import remap

import settings

# Regex patterns for words in a title that shouldn't be lowercased
# e.g. all-caps, CamelCase, etc.
CONSERVE_RX = [
    r"(?P<head>\w+)(?(head)(?P<hump>[A-Z0-9][a-z]*)|(?P=hump){2,})",
    r"[A-Z\.]{2,}",  # 'E.U.'
    r"\bI\b",
]
# Fails:
# - chemistry: 'C–H', 'bisphenol A',
# - proper nouns

CONSERVE = [re.compile(i) for i in CONSERVE_RX]

SEPARATORS = re.compile(r"([\:\?\!\.]\s|\s+\|\s|\s+[-–—]\s|—)")


def all_coll_items(zot, *args, **kwargs):
    """
    Lazy generator for all items in a collection.

    Modified from: https://gist.github.com/rdhyee/404573708a805861edb5
    """
    for page in chain([zot.collection_items(*args, **kwargs)], zot.iterfollow()):
        for item in page:
            yield item


def coll_names_keys(colls_list):
    """
    Return dict of names: keys for all collections in the given list.

    Warning: if multiple collections in the list share the same name,
    only one will be returned.
    """
    return {i["data"]["name"]: i["data"]["key"] for i in colls_list}


def coll_key_from_name(name, colls_list):
    """
    Find the key of a collection by name, from a list of collections.

    Return a list if more than one found, None if none found.
    """
    keys = []

    for coll in colls_list:
        if coll["data"]["name"] == name:
            keys.append(coll["data"]["key"])

    if len(keys) == 1:
        return keys[0]
    elif len(keys) > 1:
        return keys
    else:
        return None


def autotag_subcoll_items(zot, key):
    """
    Tag items with the name of the containing subcollection.

    Operates on every item in each subcollection of the collection
    identified by the key.
    """
    subcolls = zot.collections_sub(key)
    subcoll_names_keys = coll_names_keys(subcolls)
    for (name, key) in subcoll_names_keys.items():
        items = all_coll_items(zot, key)
        for item in items:
            zot.add_tags(item, name)
            try:
                print("Adding tag", name, "to", item["data"]["title"])
            except KeyError:
                pass


# def add_members_to_coll(zot, from_coll, to_coll, *args, **kwargs):
#     # Doesn't work because Zotero.collection_items only returns
#     # top-level items (contrary to docs).
#     items = all_coll_items(from_coll, *args, **kwargs)
#     for item in items:
#         zot.addto_collection(item, to_coll)


def get_all_titles(items):
    """Get all main titles from a list of Zotero items."""
    titles = []

    def visit(path, key, value):
        if key == "title":
            titles.append(value)
        return False

    remap(items, visit=visit)
    return titles


def sentence_case(text):
    """Convert a fragmentary phrase to sentence case, somewhat sensibly."""
    if SEPARATORS.match(text):
        return text

    words = []

    for word in text.split():
        if any([p.search(word) for p in CONSERVE]):
            words.append(word)
        else:
            words.append(word.lower())

    try:
        if words[0][0] in "'\"“‘":
            words[0] = words[0][0] + words[0][1].upper() + words[0][2:]
        else:
            words[0] = words[0][0].upper() + words[0][1:]
        result = " ".join(words)
    except (IndexError, TypeError):
        result = text

    return result


def to_sentence_case(title):
    """Attempt to sensibly convert a title to sentence case."""
    if title == "":
        return title

    parts = SEPARATORS.split(title)
    new_title = "".join([sentence_case(part) for part in parts])
    return new_title


def item_titles_to_sentence(item, keys=["title", "shortTitle", "bookTitle"]):
    """
    Change an item's various titles to sentence case.

    Only return the item if it has been changed, otherwise return None.
    Ignore notes and attachments.
    """
    if item["data"]["itemType"] in ["attachment", "note"]:
        return None

    mod = False

    for key in keys:
        try:
            new_title = to_sentence_case(item["data"][key])
            if new_title != item["data"][key]:
                item["data"][key] = new_title
                print("{:<10}".format(key), item["data"][key])
                mod = True
        except KeyError:
            pass

    return item if mod else None


def zot_titles_to_sentence(zot, coll_id=settings.TEST_COLL_ID, dry_run=False):
    """
    Get items from a Zotero collection & change their titles to sentence case.

    Changes items on the server (or not at all) and does not return anything.
    """
    print(zot.num_collectionitems(coll_id), "items in collection.")
    items = all_coll_items(zot, coll_id)

    for item in items:
        new_item = item_titles_to_sentence(item)
        if new_item and not dry_run:
            zot.update_item(new_item)


def journal_cleanup(item):
    """
    If item is journal article, delete the URL if there's a DOI.

    Only return the item if it has been changed, otherwise return None.
    """
    if item["data"]["itemType"] != "journalArticle":
        return None

    mod = False

    try:
        if item["data"]["DOI"] and item["data"]["url"]:
            print("DOI:  ", item["data"]["DOI"])
            print("- URL:", item["data"]["url"])
            item["data"]["url"] = ""
            mod = True
        # if item['data']['accessDate']:
        #     item['data']['accessDate'] = ''
        #     print('Cleared accessDate:', item['data']['key'])
        #     mod = True
    except KeyError:
        pass

    return item if mod else None


def zot_journal_cleanup(zot, coll_id=settings.TEST_COLL_ID, dry_run=False):
    """
    Get items from a collection & clean up some fields for journal articles.

    Changes items on the server (or not at all) and does not return anything.
    """
    print(zot.num_collectionitems(coll_id), "items in collection.")
    items = all_coll_items(zot, coll_id)

    for item in items:
        new_item = journal_cleanup(item)
        if new_item and not dry_run:  # Only update if there was a change.
            zot.update_item(new_item)
