#[out:json][bbox:{{bbox}}];(way[name=Marschnergasse];way[name=Erdbrustgasse]);out geom meta;

def node_geom(lat, lon):
    global geom_plan

    try:
        geom_plan
    except NameError:
        geom_plan = plpy.prepare('select ST_GeomFromText($1, 4326) as geom', [ 'text' ])

    res = plpy.execute(geom_plan, [ 'POINT({} {})'.format(lon, lat) ])

    return res[0]['geom']

def way_geom(r, is_polygon):
    global geom_plan

    try:
        geom_plan
    except NameError:
        geom_plan = plpy.prepare('select ST_GeomFromText($1, 4326) as geom', [ 'text' ])

    geom_str = ','.join([
        str(p['lon']) + ' ' + str(p['lat'])
        for p in r['geometry']
    ])

    if is_polygon:
        geom_str = 'POLYGON((' + geom_str + '))'
    else:
        geom_str = 'LINESTRING('+ geom_str + ')'

    res = plpy.execute(geom_plan, [ geom_str ])

    return res[0]['geom']

def linestring(geom):
    return 'LINESTRING(' + ','.join([
                '{} {}'.format(g['lon'], g['lat'])
                for g in geom
            ]) + ')'

def relation_geom(r):
    global geom_plan

    try:
        geom_plan_makepoly
    except NameError:
        geom_plan_makepoly = plpy.prepare('select ST_SetSRID(ST_MakePolygon(ST_GeomFromText($1)), 4326) as geom', [ 'text' ])
        geom_plan_collect = plpy.prepare('select ST_Collect($1) as geom', [ 'geometry[]' ])
        geom_plan_substract = plpy.prepare('select ST_Difference($1, $2) as geom', [ 'geometry', 'geometry' ])
        # merge all lines together, return all closed rings (but remove unconnected lines)
        geom_plan_linemerge = plpy.prepare('select geom from (select (ST_Dump((ST_LineMerge(ST_Collect(geom))))).geom as geom from (select ST_GeomFromText(unnest($1), 4326) geom) t offset 0) t where ST_NPoints(geom) > 3 and ST_IsClosed(geom)', [ 'text[]' ])

    if 'tags' in r and 'type' in r['tags'] and r['tags']['type'] in ('multipolygon', 'boundary'):
        t = 'MULTIPOLYGON'
    else:
        return None

    polygons = []
    lines = []
    inner_polygons = []
    inner_lines = []

    for m in r['members']:
        if m['role'] in ('outer', ''):
            if m['geometry'][0] == m['geometry'][-1]:
                polygons.append(linestring(m['geometry']))
            else:
                lines.append(linestring(m['geometry']))

        elif m['role'] in ('inner'):
            if m['geometry'][0] == m['geometry'][-1]:
                inner_polygons.append(linestring(m['geometry']))
            else:
                inner_lines.append(linestring(m['geometry']))

    polygons = [
            plpy.execute(geom_plan_makepoly, [ p ])[0]['geom']
            for p in polygons
        ]

    lines = plpy.execute(geom_plan_linemerge, [ lines ])
    for r in lines:
        polygons.append(r['geom'])

    polygons = plpy.execute(geom_plan_collect, [ polygons ])[0]['geom']
    inner_polygons = [
            plpy.execute(geom_plan_makepoly, [ p ])[0]['geom']
            for p in inner_polygons
        ]

    inner_lines = plpy.execute(geom_plan_linemerge, [ inner_lines ])
    for r in inner_lines:
        inner_polygons.append(r['geom'])

    for p in inner_polygons:
        polygons = plpy.execute(geom_plan_substract, [ polygons, p ])[0]['geom']
    inner_polygons = None

    return polygons

def assemble_object(r):
    t = {
        'tags': r['tags'] if 'tags' in r else {},
    }
    if r['type'] == 'node':
        t['id'] = 'n' + str(r['id'])
        t['types'] = ['area', 'line', 'way']
        t['geo'] = node_geom(r['lat'], r['lon']),
    elif r['type'] == 'way':
        is_polygon = len(r['nodes']) > 3 and r['nodes'][0] == r['nodes'][-1]
        t['id'] = 'w' + str(r['id'])
        t['types'] = ['line', 'way']
        if is_polygon:
            t['types'].append('area')
        t['geo'] = way_geom(r, is_polygon)
        t['members'] = [
                {
                    'member_id': 'n' + str(m),
                    'sequence_id': str(i),
                }
                for i, m in enumerate(r['nodes'])
            ]
    elif r['type'] == 'relation':
        t['id'] = 'r' + str(r['id'])
        t['types'] = ['area', 'relation']
        t['geo'] = relation_geom(r)
        t['members'] = [
                {
                    'member_id': m['type'][0] + str(m['ref']),
                    'role': m['role'],
                    'sequence_id': str(i),
                }
                for i, m in enumerate(r['members'])
            ]
    t['tags']['osm:id'] = t['id']
    t['tags']['osm:version'] = str(r['version']) if 'version' in r else ''
    t['tags']['osm:user_id'] = str(r['uid']) if 'uid' in r else ''
    t['tags']['osm:user'] = r['user'] if 'user' in r else ''
    t['tags']['osm:timestamp'] = r['timestamp'] if 'timestamp' in r else ''
    t['tags']['osm:changeset'] = str(r['changeset']) if 'changeset' in r else ''

    return t

def objects(_bbox, where_clauses, add_columns={}, add_param_type=[], add_param_value=[]):
    import urllib.request
    import urllib.parse
    import json
    time_start = datetime.datetime.now() # profiling
    non_relevant_tags = {'type', 'source', 'source:ref', 'source_ref', 'note', 'comment', 'created_by', 'converted_by', 'fixme', 'FIXME', 'description', 'attribution', 'osm:id', 'osm:version', 'osm:user_id', 'osm:user', 'osm:timestamp', 'osm:changeset'}
    ways_done = []
    rels_done = []

    qry = '[out:json]'

    if _bbox:
        plan = plpy.prepare("select ST_YMin($1::geometry) || ',' || ST_XMIN($1::geometry) || ',' || ST_YMAX($1::geometry) || ',' || ST_XMAX($1::geometry) as bbox_string", [ 'geometry' ])
        res = plpy.execute(plan, [ _bbox ])
        qry += '[bbox:' + res[0]['bbox_string'] + ']'

    qry += ';__QRY__;out meta geom;'

    # nodes
    w = []
    for t in ('*', 'node', 'point'):
        if t in where_clauses:
            w.append(where_clauses[t])

    if len(w):
        q = qry.replace('__QRY__', '((' + ');('.join(w) + ');)')
        q = q.replace('__TYPE__', 'node')

        url = '{db.overpass-url}?' +\
            urllib.parse.urlencode({ 'data': q })
        f = urllib.request.urlopen(url).read().decode('utf-8')
        res = json.loads(f)

        for r in res['elements']:
            yield(assemble_object(r))

        #'http://overpass-turbo.eu/?Q=' + q).read()

    # way areas and multipolygons based on outer tags
    w = []
    for t in ('*', 'area'):
        if t in where_clauses:
            w.append(where_clauses[t])

    if len(w):
        # query for ways which match query, also get their parent relations and
        # again all child ways. if a way is outer way of a multipolygon, the
        # multipolygon has no (relevant) tags and all outer ways share the same
        # tags (save non relevant tags) the ways are discarded and the relation
        # is used - as type 'multipolygon' and a 'm' prefixed to the ID
        q = qry.replace('__QRY__',
                'relation[type=multipolygon] -> .rel;' +
                '((' + ');('.join(w) + ');) -> .outer;relation(bw.outer)[type=multipolygon]') + '.outer out tags qt;'
        q = q.replace('__TYPE__', 'way(r.rel:"outer")')
        plpy.warning(q)

        url = '{db.overpass-url}?' +\
            urllib.parse.urlencode({ 'data': q })
        f = urllib.request.urlopen(url).read().decode('utf-8')
        res = json.loads(f)

        _ways = {}
        _rels = {}

        for r in res['elements']:
            if r['type'] == 'way':
                _ways[r['id']] = r
            elif r['type'] == 'relation':
                _rels[r['id']] = r

        for rid, r in _rels.items():
            if r['tags']['type'] in ('multipolygon', 'boundary') and len([
                    v
                    for v in r['tags']
                    if v not in non_relevant_tags
                ]) == 0:
                is_valid_mp = True
                outer_tags = None

                for outer in r['members']:
                    if outer['role'] in ('', 'outer'):
                        if not outer['ref'] in _ways:
                            continue

                        outer_way = _ways[outer['ref']]
                        tags = {
                                vk: vv
                                for vk, vv in outer_way['tags'].items()
                                if vk not in non_relevant_tags
                            } if 'tags' in outer_way else {}

                        if outer_tags is None:
                            outer_tags = tags
                        elif outer_tags != tags:
                            is_valid_mp = True

                if is_valid_mp:
                    rels_done.append(rid)
                    for outer in r['members']:
                        if outer['role'] in ('', 'outer'):
                            ways_done.append(outer['ref'])

                    t = assemble_object(r)
                    t['types'] = ['multipolygon', 'area']
                    t['tags'] = outer_tags

                    yield(t)
                else:
                    plpy.warning('tag-less multipolygon with non-similar outer ways: {}'.format(rid))

        _ways = None
        _rels = None

    # ways
    w = []
    for t in ('*', 'line', 'way', 'area'):
        if t in where_clauses:
            w.append(where_clauses[t])

    if len(w):
        q = qry.replace('__QRY__', '((' + ');('.join(w) + ');)')
        q = q.replace('__TYPE__', 'way')
        plpy.warning(q)

        url = '{db.overpass-url}?' +\
            urllib.parse.urlencode({ 'data': q })
        f = urllib.request.urlopen(url).read().decode('utf-8')
        res = json.loads(f)

        for r in res['elements']:
            if r['id'] in ways_done:
                pass
            ways_done.append(r['id'])

            yield(assemble_object(r))

    # relations
    w = []
    for t in ('*', 'relation', 'area'):
        if t in where_clauses:
            w.append(where_clauses[t])

    if len(w):
        q = qry.replace('__QRY__', '((' + ');('.join(w) + ');)')
        q = q.replace('__TYPE__', 'relation')
        plpy.warning(q)

        url = '{db.overpass-url}?' +\
            urllib.parse.urlencode({ 'data': q })
        f = urllib.request.urlopen(url).read().decode('utf-8')
        res = json.loads(f)

        for r in res['elements']:
            if r['id'] in rels_done:
                pass
            rels_done.append(r['id'])

            yield(assemble_object(r))

    # areas
    w = []
    for t in ('*', 'relation', 'area'):
        if t in where_clauses:
            w.append(where_clauses[t])

    if len(w):
        plan = plpy.prepare("select ST_Y(ST_Centroid($1::geometry)) || ',' || ST_X(ST_Centroid($1::geometry)) as geom", [ 'geometry' ])
        res = plpy.execute(plan, [ _bbox ])

        q = qry.replace('__QRY__', 'is_in({0});way(pivot);out meta geom;is_in({0});relation(pivot)'.format(res[0]['geom']))
        plpy.warning(q)

        url = '{db.overpass-url}?' +\
            urllib.parse.urlencode({ 'data': q })
        f = urllib.request.urlopen(url).read().decode('utf-8')

        try:
            res = json.loads(f)
        except ValueError:
            print(f)
            if re.search('osm3s_v[0-9\.]+_areas', f):
                res = { 'elements': [] }
            else:
                raise

        for r in res['elements']:
            if (r['type'] == 'way' and r['id'] in ways_done) or\
               (r['type'] == 'relation' and r['id'] in rels_done):
                continue

            yield(assemble_object(r))

    time_stop = datetime.datetime.now() # profiling
    plpy.notice('querying db objects took %.2fs' % (time_stop - time_start).total_seconds())

def objects_by_id(id_list):
    import urllib.request
    import urllib.parse
    import json
    q = ''
    multipolygons = []
    for i in id_list:
        if i[0:1] == 'n':
            q += 'node({});out meta geom;'.format(i[1:])
        elif i[0:1] == 'w':
            q += 'way({});out meta geom;'.format(i[1:])
        elif i[0:1] == 'r':
            q += 'relation({});out meta geom;'.format(i[1:])

    if q == '':
        return
    q = '[out:json];' + q

    plpy.warning(q)

    url = 'http://overpass-api.de/api/interpreter?' +\
        urllib.parse.urlencode({ 'data': q })
    f = urllib.request.urlopen(url).read().decode('utf-8')
    res = json.loads(f)

    for r in res['elements']:
        yield(assemble_object(r))

def objects_member_of(member_id, parent_type, parent_conditions):
    import urllib.request
    import urllib.parse
    import json

    q = '[out:json];'

    if member_id[0] == 'n':
        ob_type = 'node'
        ob_id = int(member_id[1:])
        q += 'node(' + member_id[1:] + ')->.a;'
    elif member_id[0] == 'w':
        ob_type = 'way'
        ob_id = int(member_id[1:])
        q += 'way(' + member_id[1:] + ')->.a;'
    elif member_id[0] == 'r':
        ob_type = 'relation'
        ob_id = int(member_id[1:])
        q += 'relation(' + member_id[1:] + ')->.a;'

    q += '(' + parent_conditions.replace('__TYPE__', parent_type + '(b' +
            member_id[0] + '.a)') + ');'
    q += 'out meta qt geom;'

    plpy.warning(q)

    url = 'http://overpass-api.de/api/interpreter?' +\
        urllib.parse.urlencode({ 'data': q })
    f = urllib.request.urlopen(url).read().decode('utf-8')
    plpy.warning(f)
    res = json.loads(f)

    for r in res['elements']:
        t = assemble_object(r)
        if parent_type == 'relation':
            for i, m in enumerate(r['members']):
                if m['type'] == ob_type and m['ref'] == ob_id:
                    t['link_tags'] = {
                            'sequence_id': str(i),
                            'role': m['role'],
                            'member_id': m['type'][0] + str(m['ref']),
                    }
                    yield(t)

        elif parent_type == 'way':
            for i, m in enumerate(r['nodes']):
                if m == ob_id:
                    t['link_tags'] = {
                            'sequence_id': str(i),
                            'member_id': 'n' + str(m),
                    }
                    yield(t)

def objects_members(relation_id, parent_type, parent_conditions):
    import urllib.request
    import urllib.parse
    import json

    q = '[out:json];'

    if relation_id[0] == 'n':
        ob_type = 'node'
        ob_id = int(relation_id[1:])
        q += 'node(' + relation_id[1:] + ')->.a;'
    elif relation_id[0] == 'w':
        ob_type = 'way'
        ob_id = int(relation_id[1:])
        q += 'way(' + relation_id[1:] + ')->.a;'
    elif relation_id[0] == 'r':
        ob_type = 'relation'
        ob_id = int(relation_id[1:])
        q += 'relation(' + relation_id[1:] + ')->.a;'

    q += '(' + parent_conditions.replace('__TYPE__', parent_type + '(' +
            relation_id[0] + '.a)') + ');'
    q += '.a out meta qt geom;out meta qt geom;'
    # TODO: .a out body qt; would be sufficient, but need to adapt assemble_object

    url = 'http://overpass-api.de/api/interpreter?' +\
        urllib.parse.urlencode({ 'data': q })
    f = urllib.request.urlopen(url).read().decode('utf-8')
    plpy.warning(f)
    res = json.loads(f)

    relation = None
    relation_type = None

    for r in res['elements']:
        t = assemble_object(r)

        if t['id'] == relation_id:
            relation = t
            relation_type = r['type']

        else:
            for m in relation['members']:
                if m['member_id'] == t['id']:
                    t['link_tags'] = {
                            'sequence_id': m['sequence_id'],
                            'member_id': m['member_id'],
                    }
                    if 'role' in m:
                        t['link_tags']['role'] = m['role']

                    yield(t)

def objects_near(max_distance, ob, parent_selector, where_clause, check_geo=None):
    if ob:
        geom = ob['geo']
    elif 'geo' in current['properties'][current['pseudo_element']]:
        geom = current['properties'][current['pseudo_element']]['geo']
    else:
        geom = current['object']['geo']

    if where_clause == '':
        where_clause = 'true'

    max_distance = to_float(eval_metric([ max_distance, 'u' ]))
    if max_distance is None:
        return []
    elif max_distance == 0:
        bbox = geom
    else:
        plan = plpy.prepare('select ST_Transform(ST_Buffer(ST_Transform(ST_Envelope($1), {unit.srs}), $2), {db.srs}) as r', ['geometry', 'float'])
        res = plpy.execute(plan, [ geom, max_distance ])
        bbox = res[0]['r']

    if check_geo == 'within':
        where_clause += " and ST_DWithin(way, $2, 0.0)"
    elif check_geo == 'surrounds':
        where_clause += " and ST_DWithin($2, way, 0.0)"
    elif check_geo == 'overlaps':
        where_clause += " and ST_Overlaps($2, way)"

    obs = []
    for ob in objects(
        bbox,
        { parent_selector: where_clause },
        { # add_columns
            '__distance': 'ST_Distance(ST_Transform($2::geometry, {unit.srs}), ST_Transform(__geo__, {unit.srs}))'
        },
        [ 'geometry' ],
        [ geom ]
    ):
        if ob['id'] != current['object']['id'] and ob['__distance'] <= max_distance:
            ob['link_tags'] = {
                'distance': eval_metric([ str(ob['__distance']) + 'u', 'px' ])
            }
            obs.append(ob)

    obs = sorted(obs, key=lambda ob: ob['__distance'] )
    return obs
