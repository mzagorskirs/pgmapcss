from .parse_selectors import parse_selectors
from .parse_properties import parse_properties
import re

def parse_file(stat, file):
    content = open(file).read()
    to_parse = content
    stat['statements'] = []

# read statements until there's only whitespace left
    while not re.match('\s*$', to_parse):
        selectors = []
        to_parse = parse_selectors(selectors, to_parse)

        properties = []
        to_parse = parse_properties(properties, to_parse)

        for i in selectors:
            stat['statements'].append({
                'selectors': i,
                'properties': properties
            })

    return stat
