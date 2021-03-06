import pgmapcss.db as db
from .compile_eval import compile_eval
from .compile_value import compile_value
from .CompileError import CompileError

def compile_properties(statement, stat, indent=''):
    ret = ''

    for prop in statement['properties']:
        if prop['assignment_type'] == 'P':
            c = compile_value(prop, stat)

            if c == None:
                raise CompileError('Illegal value for property "%s" found: "%s"' % ( prop['key'], prop['value'] ))

            ret += indent + "current['properties'][" + statement['current_pseudo_element'] + ']' +\
                '[' + repr(prop['key']) + '] = ' + c + '\n'

        elif prop['assignment_type'] == 'T':
            c = compile_value(prop, stat)
            ret += indent

            # JOSM classes ("set foo" => set ".foo" too)
            if stat['config'].get('josm_classes', '') == 'true' \
              and prop['key'][0] != '.':
                ret += "current['tags']" +\
                    '[' + repr('.' + prop['key']) + '] = '

            ret += "current['tags']" +\
                '[' + repr(prop['key']) + '] = ' + c + '\n'

        elif prop['assignment_type'] == 'U':
            # JOSM classes ("set foo" => set ".foo" too)
            if stat['config'].get('josm_classes', '') == 'true' \
              and prop['key'][0] != '.':
                ret += indent + "current['tags'].pop(" + repr('.' + prop['key']) + ', None)\n'

            ret += indent + "current['tags'].pop(" + repr(prop['key']) + ', None)\n'

        elif prop['assignment_type'] == 'C':
            ret += indent + '''yield(( 'combine', ''' + repr(prop['key']) + \
            ', ' + compile_value(prop, stat) + ''', {
    'id': object['id'],
    'tags': current['tags'],
    'geo': current['properties'][''' + statement['current_pseudo_element'] + ''']['geo'] if 'geo' in current['properties'][''' + statement['current_pseudo_element'] + '''] else current['object']['geo']
}))
'''

    return ret
