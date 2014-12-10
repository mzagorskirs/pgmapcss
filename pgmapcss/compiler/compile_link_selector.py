from .compile_selector_part import compile_selector_part
from .compile_conditions import compile_conditions
from .compile_eval import compile_eval
import pgmapcss.db as db

def compile_link_selector(statement, stat):
    # create statement where selector is build from parent_selector for compiling
    _statement = statement.copy()
    _statement['selector'] = _statement['parent_selector']
    del _statement['link_selector']
    del _statement['parent_selector']

    parent_conditions = stat['database'].merge_conditions([(
        statement['parent_selector']['type'],
        stat['database'].compile_selector(_statement)
    )])

    if statement['parent_selector']['type'] in parent_conditions:
        parent_conditions = parent_conditions[statement['parent_selector']['type']]
    else:
        parent_conditions = None

    child_conditions = stat['database'].merge_conditions([(
        statement['selector']['type'],
        stat['database'].compile_selector(statement)
    )])
    if statement['selector']['type'] in child_conditions:
        child_conditions = child_conditions[statement['selector']['type']]
    else:
        child_conditions = None

    if statement['link_selector']['type'] in ('>', ''):
        return "objects_member_of(object['id'], " +\
            repr(statement['parent_selector']['type']) + ", " +\
            repr(parent_conditions) + ", " +\
            repr(child_conditions) + ")"

    elif statement['link_selector']['type'] == '<':
        return "objects_members(object['id'], " +\
            repr(statement['parent_selector']['type']) + ", " +\
            repr(parent_conditions) + ", " +\
            repr(child_conditions) + ")"

    elif statement['link_selector']['type'] == 'near':
        distance = { 'value': '100' }

        for r in statement['link_selector']['conditions']:
            if r['key'] == 'distance' and r['op'] in ('<', '<=', '='):
                distance = r

        if distance.get('value_type') == 'eval':
            distance = compile_eval(distance['value'], {
                    'statement': statement ,
                    'id': statement['id']
                }, stat)
        else:
            distance = repr(distance['value'])

        return "objects_near(" + distance + ", None, "+\
            repr(statement['parent_selector']['type']) + ", " +\
            repr(parent_conditions) + ", " +\
            repr(child_conditions) + ")"

    elif statement['link_selector']['type'] in ('within', 'surrounds', 'overlaps'):
        return "objects_near(\"0\", None, "+\
            repr(statement['parent_selector']['type']) + ", " +\
            repr(parent_conditions) + ", " +\
            repr(child_conditions) + ", check_geo=" +\
            repr(statement['link_selector']['type']) + ")"

    else:
        raise Exception('Unknown link selector "{type}"'.format(**selector['link_selector']))
