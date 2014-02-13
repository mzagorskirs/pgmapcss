def stat_all_scale_denominators(stat):
    return sorted(list(set([
            v['selector']['min_scale']
            for v in stat['statements']
        ] + \
        [
            v['selector']['max_scale']
            for v in stat['statements']
            if v['selector']['max_scale'] != None
        ])),
        reverse=True)

def stat_properties(stat):
    return list(set([
        p['key']
        for v in stat['statements']
        for p in v['properties']
        if p['assignment_type'] == 'P'
    ]))

def stat_property_values(prop, stat, include_illegal_values=False, value_type=None, pseudo_element=None):
    """Returns set of all values used on this property in any statement.
    Returns boolean 'True' if property is result of an eval expression."""
    values = {
        True if p['value_type'] == 'eval' else p['value']
        for v in stat['statements']
        for p in v['properties']
        if pseudo_element == None or v['selector']['pseudo_element'] in ('*', pseudo_element)
        if p['assignment_type'] == 'P' and p['key'] == prop
        if value_type == None or value_type == p['value_type']
    }

    if 'default_other' in stat['defines'] and prop in stat['defines']['default_other']:
        other = stat['defines']['default_other'][prop]['value']
        other = stat_property_values(other, stat, include_illegal_values, value_type, pseudo_element)
        values = values.union(other)

    if 'generated_properties' in stat and prop in stat['generated_properties']:
        gen = stat['generated_properties'][prop]
        combinations = stat_properties_combinations(gen[0], stat, include_illegal_values, value_type, pseudo_element)
        values = values.union({
            gen[1](combination)
            for combination in combinations
        })

    if include_illegal_values:
        return values

    if 'values' in stat['defines'] and prop in stat['defines']['values']:
        allowed_values = stat['defines']['values'][prop]['value'].split(';')

        if True in values:
            values = values.union(allowed_values)

        values = {
            v if v in allowed_values else allowed_values[0]
            for v in values
        }

    values = {
        v
        for v in values
        if v != None
    }

    return values

def stat_properties_combinations(keys, stat, include_illegal_values=False, value_type=None, pseudo_element=None):
    combinations_list = [{}]

    for k in keys:
        new_combinations_list = []

        for combination in combinations_list:
            for v in stat_property_values(k, stat, include_illegal_values, value_type, pseudo_element):
                c = combination.copy()
                c[k] = v
                new_combinations_list.append(c)

        combinations_list = new_combinations_list

    return combinations_list

def stat_properties_combinations_smart(keys, stat, include_illegal_values=False, value_type=None, pseudo_elements=None):
    combinations = []

    if pseudo_elements is None:
        pseudo_elements = stat['pseudo_elements']

    for pseudo_element in pseudo_elements:
        combinations += stat_properties_combinations(keys, stat, include_illegal_values, value_type, pseudo_element)

    ret = []
    for combination in combinations:
        if not combination in ret:
            ret += [ combination ]

    return ret

def stat_add_generated_property(key, keys, fun, stat):
    if not 'generated_properties' in stat:
        stat['generated_properties'] = {}

    stat['generated_properties'][key] = ( keys, fun )
    print(stat['generated_properties'])
