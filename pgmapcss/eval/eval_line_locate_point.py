class config_eval_line_locate_point(config_base):
    mutable = 2

def eval_line_locate_point(param):
    if len(param) < 2:
        return ''

    if not param[0] or not param[1]:
        return ''

    plan = plpy.prepare('select ST_Line_Locate_Point($1, $2) * ST_Length(ST_Transform($1, {unit.srs})) as r', ['geometry', 'geometry'])
    res = plpy.execute(plan, [ param[0], param[1] ])

    return eval_metric([ repr(res[0]['r']) + 'u' ])

# IN ['010200002031BF0D0002000000EC51B8DE163A3A410AD7A36078B45641295C8F826E393A4152B81E8573B45641', '010100002031BF0D00EC51B8DE163A3A410AD7A36078B45641']
# OUT '0'
# IN ['010200002031BF0D0002000000EC51B8DE163A3A410AD7A36078B45641295C8F826E393A4152B81E8573B45641', '010100002031BF0D0096A850FF0A3A3A414E8FF20878B45641']
# OUT '5.000000565986081'
# IN ['010200002031BF0D0002000000EC51B8DE163A3A410AD7A36078B45641295C8F826E393A4152B81E8573B45641', '']
# OUT ''
# IN ['', '010100002031BF0D0096A850FF0A3A3A414E8FF20878B45641']
# OUT ''
# IN ['', '']
# OUT ''

# IN [ '010200002031BF0D0003000000C3F5281C3C3C3A410AD7A3C0B1B55641666666A6B13B3A41EC51B8FEB9B556415C8FC235823B3A4185EB51B8BCB55641', '010100002031BF0D0011F36855BA3B3A4191E01B3EB1B55641' ]
# OUT '52.61864905625409'
# IN [ '010200002031BF0D000300000085EB51789E3B3A4148E17A749AB556413D0AD763E83B3A4133333373A1B55641000000C0233C3A41C3F5280CA7B55641', '010100002031BF0D001E313E43A43B3A41F14D01FAA2B55641' ]
# OUT '7.314706354219713'
