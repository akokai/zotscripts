"""
Code for transforming Zotero scannable cites into Pandoc Markdown citations
"""

import json
import re

SCAN_RX = r"(\{.*?\|zu:\d+:[A-Z0-9]+\})(?:[^{])"
CITE_RX = r"\{?\s?(?P<pre>.*?)\s?\|\s?(?P<noauth>[-]?)(?:.*?)\|\s?(?P<loc>.*?)\s?\|(?:.*?)\|zu:\d+:(?P<key>[A-Z0-9]+)\}?"


def parse_scannable(cites):
    if "}{" in cites:
        return [parse_scannable(cite) for cite in cites.split("}{")]
    return re.match(CITE_RX, cites).groupdict()


def format_citation(parsed):
    ret = " ".join([parsed["pre"], parsed["noauth"] + "@" + parsed["citekey"]]).strip()
    if parsed["loc"]:
        return ", ".join([ret, parsed["loc"]])
    return ret


def process_citation(parsed, collected, bib):
    """
    Perform side effects on a Zotero scannable citation.

    Look up and add the ``citekey`` for the citation, as set by Better BibTeX
    in Zotero. Also add the Zotero unique key to a running collection of items.

    Arguments:
        parsed (dict): Citation represented as a dict, which will be mutated
        collected (set): A collection of Zotero citation keys
        bib (dict): Bibliography, via custom JSON export from Zotero with BBT
    """
    collected.add(parsed["key"])
    matching = [item for item in bib if item["zoteroKey"] == parsed["key"]]
    if matching:
        parsed["citekey"] = matching[0]["id"]
    return parsed


def sub_scannable(parsed, *args):
    if isinstance(parsed, dict):
        process_citation(parsed, *args)
        return format_citation(parsed)
    elif isinstance(parsed, list):
        return "; ".join([sub_scannable(item, *args) for item in parsed])


def subst(parsed, *args):
    return f"[{sub_scannable(parsed, *args)}]"
