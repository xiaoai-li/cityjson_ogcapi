import psycopg2
import json 
from cjio.cityjson import CityJSON
from algorithms.replace_transform import transform_vertices_back
from algorithms.replace_transform import from_vertex_to_index

TOPLEVEL = ('Building',
            'Bridge',
            'CityObjectGroup',
            'CityFurniture',
            'GenericCityObject',
            'LandUse',
            'PlantCover',
            'Railway',
            'Road',
            'SolitaryVegetationObject',
            'TINRelief',
            'TransportSquare',
            'Tunnel',
            'WaterBody')

def convert_polygon_to_surface(geometry):
    geometry = geometry.replace("POLYGON Z ", "")
    geometry = geometry.replace("((", "")
    geometry = geometry.replace("))", "")
    geometry = geometry.split("),(")
    linestring_list = [] 
    for linestring in geometry: 
        linestring = linestring.split(',')
        vertices_list = [] 
        for vertex in linestring:
            vertex = vertex.split(' ')  
            vertices_list.append([float(vertex[0]), float(vertex[1]), float(vertex[2])])
        vertices_list.pop() # remove the last one of the list 
        linestring_list.append(vertices_list)
    return linestring_list

def from_multisurface_to_hierarchy(linestring, boundaries):
    boundaries.append(linestring)
    return boundaries 

def from_solid_to_hierarchy(shell_num, linestring, boundaries):
    if len(boundaries) == 0 or len(boundaries) - 1 < shell_num: 
        boundaries.append([])
    boundaries[shell_num].append(linestring)
    return boundaries 

def from_multisolid_to_hierarchy(solid_num, shell_num, linestring, boundaries):
    if len(boundaries) == 0 or len(boundaries) - 1 < solid_num: 
        boundaries.append([])
    if len(boundaries[solid_num]) == 0 or len(boundaries[solid_num]) -1 < shell_num:
        boundaries[solid_num].append([])
    boundaries[solid_num][shell_num].append(linestring)
    return boundaries 

#### Implementation: one JSONB document #####
def query_PostgreSQL(file_name, schema_name): 
    # #1. Connect to database
    # conn = psycopg2.connect("dbname=CityJSON user=postgres password=1234")
    # cur = conn.cursor() # Open a cursor to perform database operations
    queried_CityJSON = {}

    #A. metadata
    query_metadata = """SELECT object FROM {}.metadata""".format(schema_name)
    cur.execute(query_metadata)
    object_metadata = cur.fetchall()

    object_metadata = object_metadata[0][0]
    queried_CityJSON['type'] = object_metadata['type']
    if 'type' in object_metadata:
        del object_metadata['type']
    queried_CityJSON['version'] = object_metadata['version']
    if 'version' in object_metadata:
        del object_metadata['version']
    queried_CityJSON['metadata'] = object_metadata  

    #B. transform
    query_transform = """SELECT object FROM {}.transform""".format(schema_name)
    cur.execute(query_transform)
    object_transform = cur.fetchall()

    try: 
        queried_CityJSON['transform'] = object_transform[0][0]
    except: 
        pass

    #D. CityObjects 
    query_cityobjects = """select city_object.id, city_object.object, city_object.attributes
    from {}.city_object""".format(schema_name)
    cur.execute(query_cityobjects)
    object_cityobjects = cur.fetchall()

    verticesList = [] 
        
    queried_CityJSON['CityObjects'] = {}
    for CityObject in object_cityobjects:
        #D.a add object properties 
        objproperties = {} 
        
        for key in CityObject[1]:
            objproperties[key] = CityObject[1][key]
        #D.b add attributes 
        if CityObject[2] != {}:
            objproperties['attributes'] = CityObject[2]
        #E. Geometries 
        query_id = """
        SELECT geometries.id, geometries.object
        FROM {}.city_object
		LEFT JOIN  {}.geometries on city_object.id = geometries.city_object_id
        where '{}' = city_object.id
        """.format(schema_name, schema_name, CityObject[0])
        cur.execute(query_id)
        geometries = cur.fetchall()
        geometry_list = []
        
        for geometry in geometries:
            #E.a Does the city object have geometeries? 
            if type(geometry[0]) is None or geometry[0] is None:
                continue 
            else:
                geomproperties = {}
                #E.b add geometry object properties 
                for key in geometry[1]:
                    geomproperties[key] = geometry[1][key]

                geom_type = geometry[1]['type'] 

                #E.c obtain surfaces and semantic IDs
                query_surfaces = """
                SELECT surfaces.id, surfaces.solid_num, surfaces.shell_num_void, surfaces.surface_num , ST_asText(surfaces.geometry), surfaces.semantic_surface_id
                FROM {}.geometries
	            LEFT JOIN {}.surfaces on geometries.id = surfaces.geometries_id 
                where '{}' = geometries.id 
                order by solid_num ASC, shell_num_void ASC, surface_num ASC
                """.format(schema_name, schema_name, geometry[0])
                cur.execute(query_surfaces)
                surfaces = cur.fetchall()

                #F. Semantics 
                semantics = {}
                semantics['surfaces'] = [] 
                semantics['values'] = [] 

                boundaries = [] 
                for surface in surfaces:
                    # obtain indexes per surface
                    solid_num = surface[1]
                    shell_num = surface[2]
                    surface_num = surface[3]

                    # obtain polygon per surface 
                    linestring = convert_polygon_to_surface(surface[4])

                    # Does the surface have semantics? 
                    if surface[5] != None: 
                        # semantics['surfaces'] generated
                        query_semantic = """SELECT semantic_surface.object
                        FROM {}.semantic_surface
                        where '{}' = semantic_surface.id 
                        """.format(schema_name, surface[5])
                        cur.execute(query_semantic)
                        semantic_object = cur.fetchall()[0][0]    

                        if semantic_object not in semantics['surfaces']:
                            semantics['surfaces'].append(semantic_object)
                            value = len(semantics['surfaces']) - 1
                        else:
                            value = semantics['surfaces'].index(semantic_object)

                    #boundaries and semantic['values'] generated 
                    if geom_type == 'MultiSurface' or geom_type == 'CompositeSurface':
                        boundaries = from_multisurface_to_hierarchy(linestring, boundaries)
                        if surface[5] != None: 
                            semantics['values'] = from_multisurface_to_hierarchy(value, semantics['values'])
                    elif geom_type == 'Solid':
                        boundaries = from_solid_to_hierarchy(shell_num, linestring, boundaries)
                        if surface[5] != None:
                            semantics['values'] = from_solid_to_hierarchy(shell_num, value, semantics['values'])
                    elif geom_type == 'MultiSolid' or geom_type == 'CompositeSolid':
                        boundaries = from_multisolid_to_hierarchy(solid_num, shell_num, linestring, boundaries)
                        if surface[5]!= None: 
                            semantics['values'] = from_multisolid_to_hierarchy(solid_num, shell_num, value, semantics['values'])

                # convert vertices to indexes and reconstruct the verticesList 
                boundaries = from_vertex_to_index(boundaries, verticesList)
                geomproperties['boundaries'] = boundaries
                if semantics['surfaces'] != [] and semantics['values'] != []:
                    geomproperties['semantics'] = semantics 
                geometry_list.append(geomproperties)
            

        # add the geometries 
        objproperties['geometry'] = geometry_list    
        # add the cityobject 
        queried_CityJSON['CityObjects'][CityObject[0]] = objproperties 


    #G. vertices 
    if 'transform' in queried_CityJSON.keys():
        verticesList = transform_vertices_back(queried_CityJSON['transform'], verticesList)
    
    queried_CityJSON['vertices'] = verticesList

    cityjson = CityJSON(j=queried_CityJSON)
    cityjson.remove_duplicate_vertices()
    
    #3. Reconstruct CityJSON file 
    stringName = str('../datasets/new/' + file_name + '.json')
    
    with open(stringName, 'w') as output_file:
        json.dump(cityjson.j, output_file)
        output_file.close()


def query_collections(schema_name):
    collections = []
    query_metadata = """SELECT id,object FROM {}.metadata""".format(schema_name)
    cur.execute(query_metadata)
    object_metadata = cur.fetchall()
    for id,obj in object_metadata:
        if "datasetTitle" in obj:
            collections.append({"id":id.removeprefix('metadata_'),"title":obj["datasetTitle"]})
        else:
            collections.append({"id":id,"title":None})
    return collections


def query_items(file_name, schema_name,limit=20,offset=0,bbox=None):
    queried_CityJSON = {}

    # A. metadata
    query_metadata = """SELECT object FROM {}.metadata
                        WHERE id=LOWER(%s)""".format(schema_name)
    cur.execute(query_metadata,["metadata_"+file_name])
    object_metadata = cur.fetchall()

    object_metadata = object_metadata[0][0]
    queried_CityJSON['type'] = object_metadata['type']
    if 'type' in object_metadata:
        del object_metadata['type']
    queried_CityJSON['version'] = object_metadata['version']
    if 'version' in object_metadata:
        del object_metadata['version']
    queried_CityJSON['metadata'] = object_metadata

    # B. transform
    query_transform = """SELECT object FROM {}.transform
                        WHERE id=LOWER(%s)""".format(schema_name)
    cur.execute(query_transform,["transform_"+file_name])
    object_transform = cur.fetchall()

    try:
        queried_CityJSON['transform'] = object_transform[0][0]
    except:
        pass

    # D. CityObjects
    # TODO: offset should be within the total length
    if bbox: # TODO: modify later to add simblings
        query_cityobjects = """SELECT city_object.id, city_object.object, city_object.attributes
                               FROM {}.city_object
                               WHERE city_object.metadata_id=LOWER(%s) AND
                               ST_Intersects(convexhull,
                               ST_Envelope('SRID={};LINESTRING({} {},{} {})'::geometry))
                               LIMIT {} OFFSET {}""" \
            .format(schema_name, 7415,bbox[0], bbox[1],bbox[2],bbox[3],limit, offset)
    else:
        query_cityobjects = """SELECT city_object.id, city_object.object, city_object.attributes
                                     FROM {}.city_object
                                     WHERE object  ->> 'type' in {} 
                                     AND city_object.metadata_id = LOWER(%s)
                                     LIMIT {} OFFSET {}"""\
            .format(schema_name, TOPLEVEL, limit, offset)

    cur.execute(query_cityobjects,["metadata_"+file_name])
    object_cityobjects = cur.fetchall()

    verticesList = []

    queried_CityJSON['CityObjects'] = {}
    for CityObject in object_cityobjects:
        # D.a add object properties
        objproperties = {}

        for key in CityObject[1]:
            objproperties[key] = CityObject[1][key]
        # D.b add attributes
        if CityObject[2] != {}:
            objproperties['attributes'] = CityObject[2]
        # E. Geometries
        query_id = """
            SELECT geometries.id, geometries.object
            FROM {}.city_object
    		LEFT JOIN  {}.geometries on city_object.id = geometries.city_object_id
            where '{}' = city_object.id
            """.format(schema_name, schema_name, CityObject[0])
        cur.execute(query_id)
        geometries = cur.fetchall()
        geometry_list = []

        for geometry in geometries:
            # E.a Does the city object have geometeries?
            if type(geometry[0]) is None or geometry[0] is None:
                continue
            else:
                geomproperties = {}
                # E.b add geometry object properties
                for key in geometry[1]:
                    geomproperties[key] = geometry[1][key]

                geom_type = geometry[1]['type']

                # E.c obtain surfaces and semantic IDs
                query_surfaces = """
                    SELECT surfaces.id, surfaces.solid_num, surfaces.shell_num_void, surfaces.surface_num , ST_asText(surfaces.geometry), surfaces.semantic_surface_id
                    FROM {}.geometries
    	            LEFT JOIN {}.surfaces on geometries.id = surfaces.geometries_id 
                    where '{}' = geometries.id 
                    order by solid_num ASC, shell_num_void ASC, surface_num ASC
                    """.format(schema_name, schema_name, geometry[0])
                cur.execute(query_surfaces)
                surfaces = cur.fetchall()

                # F. Semantics
                semantics = {}
                semantics['surfaces'] = []
                semantics['values'] = []

                boundaries = []
                for surface in surfaces:
                    # obtain indexes per surface
                    solid_num = surface[1]
                    shell_num = surface[2]
                    surface_num = surface[3]

                    # obtain polygon per surface
                    linestring = convert_polygon_to_surface(surface[4])

                    # Does the surface have semantics?
                    if surface[5] != None:
                        # semantics['surfaces'] generated
                        query_semantic = """SELECT semantic_surface.object
                            FROM {}.semantic_surface
                            where '{}' = semantic_surface.id 
                            """.format(schema_name, surface[5])
                        cur.execute(query_semantic)
                        semantic_object = cur.fetchall()[0][0]

                        if semantic_object not in semantics['surfaces']:
                            semantics['surfaces'].append(semantic_object)
                            value = len(semantics['surfaces']) - 1
                        else:
                            value = semantics['surfaces'].index(semantic_object)

                    # boundaries and semantic['values'] generated
                    if geom_type == 'MultiSurface' or geom_type == 'CompositeSurface':
                        boundaries = from_multisurface_to_hierarchy(linestring, boundaries)
                        if surface[5] != None:
                            semantics['values'] = from_multisurface_to_hierarchy(value, semantics['values'])
                    elif geom_type == 'Solid':
                        boundaries = from_solid_to_hierarchy(shell_num, linestring, boundaries)
                        if surface[5] != None:
                            semantics['values'] = from_solid_to_hierarchy(shell_num, value, semantics['values'])
                    elif geom_type == 'MultiSolid' or geom_type == 'CompositeSolid':
                        boundaries = from_multisolid_to_hierarchy(solid_num, shell_num, linestring, boundaries)
                        if surface[5] != None:
                            semantics['values'] = from_multisolid_to_hierarchy(solid_num, shell_num, value,
                                                                               semantics['values'])

                # convert vertices to indexes and reconstruct the verticesList
                boundaries = from_vertex_to_index(boundaries, verticesList)
                geomproperties['boundaries'] = boundaries
                if semantics['surfaces'] != [] and semantics['values'] != []:
                    geomproperties['semantics'] = semantics
                geometry_list.append(geomproperties)

        # add the geometries
        objproperties['geometry'] = geometry_list
        # add the cityobject
        queried_CityJSON['CityObjects'][CityObject[0]] = objproperties

        # G. vertices
    if 'transform' in queried_CityJSON.keys():
        verticesList = transform_vertices_back(queried_CityJSON['transform'], verticesList)

    queried_CityJSON['vertices'] = verticesList

    cityjson = CityJSON(j=queried_CityJSON)
    cityjson.remove_duplicate_vertices()

    return cityjson

    # # 3. Reconstruct CityJSON file
    # stringName = str('datasets/new/' + file_name + '.json')
    #
    # with open(stringName, 'w') as output_file:
    #     json.dump(cityjson.j, output_file)
    #     output_file.close()


def query_feature(file_name, schema_name,featureID):
    queried_CityJSON = {}

    # A. metadata
    query_metadata = """SELECT object FROM {}.metadata
                        WHERE id=LOWER(%s)""".format(schema_name)
    cur.execute(query_metadata,["metadata_"+file_name])
    object_metadata = cur.fetchall()

    object_metadata = object_metadata[0][0]
    queried_CityJSON['type'] = object_metadata['type']
    if 'type' in object_metadata:
        del object_metadata['type']
    queried_CityJSON['version'] = object_metadata['version']
    if 'version' in object_metadata:
        del object_metadata['version']
    queried_CityJSON['metadata'] = object_metadata

    # B. transform
    query_transform = """SELECT object FROM {}.transform
                        WHERE id=LOWER(%s)""".format(schema_name)
    cur.execute(query_transform,["transform_"+file_name])
    object_transform = cur.fetchall()

    try:
        queried_CityJSON['transform'] = object_transform[0][0]
    except:
        pass

    # D. CityObjects
    # TODO: offset should be within the total length
    query_cityobject = """SELECT city_object.id, city_object.object, city_object.attributes
                                 FROM {}.city_object
                                 WHERE city_object.id = %s""".format(schema_name)

    cur.execute(query_cityobject,[featureID])
    query_cityobject = cur.fetchall()
    CityObject=query_cityobject[0]
    verticesList = []

    queried_CityJSON['CityObjects'] = {}
    # D.a add object properties
    objproperties = {}

    print(CityObject)
    for key in CityObject[1]:
        objproperties[key] = CityObject[1][key]
    # D.b add attributes
    if CityObject[2] != {}:
        objproperties['attributes'] = CityObject[2]
    # E. Geometries
    query_id = """
        SELECT geometries.id, geometries.object
        FROM {}.city_object
        LEFT JOIN  {}.geometries on city_object.id = geometries.city_object_id
        where '{}' = city_object.id
        """.format(schema_name, schema_name, CityObject[0])
    cur.execute(query_id)
    geometries = cur.fetchall()
    geometry_list = []

    for geometry in geometries:
        # E.a Does the city object have geometeries?
        if type(geometry[0]) is None or geometry[0] is None:
            continue
        else:
            geomproperties = {}
            # E.b add geometry object properties
            for key in geometry[1]:
                geomproperties[key] = geometry[1][key]

            geom_type = geometry[1]['type']

            # E.c obtain surfaces and semantic IDs
            query_surfaces = """
                SELECT surfaces.id, surfaces.solid_num, surfaces.shell_num_void, surfaces.surface_num , ST_asText(surfaces.geometry), surfaces.semantic_surface_id
                FROM {}.geometries
                LEFT JOIN {}.surfaces on geometries.id = surfaces.geometries_id 
                where '{}' = geometries.id 
                order by solid_num ASC, shell_num_void ASC, surface_num ASC
                """.format(schema_name, schema_name, geometry[0])
            cur.execute(query_surfaces)
            surfaces = cur.fetchall()

            # F. Semantics
            semantics = {}
            semantics['surfaces'] = []
            semantics['values'] = []

            boundaries = []
            for surface in surfaces:
                # obtain indexes per surface
                solid_num = surface[1]
                shell_num = surface[2]
                surface_num = surface[3]

                # obtain polygon per surface
                linestring = convert_polygon_to_surface(surface[4])

                # Does the surface have semantics?
                if surface[5] != None:
                    # semantics['surfaces'] generated
                    query_semantic = """SELECT semantic_surface.object
                        FROM {}.semantic_surface
                        where '{}' = semantic_surface.id 
                        """.format(schema_name, surface[5])
                    cur.execute(query_semantic)
                    semantic_object = cur.fetchall()[0][0]

                    if semantic_object not in semantics['surfaces']:
                        semantics['surfaces'].append(semantic_object)
                        value = len(semantics['surfaces']) - 1
                    else:
                        value = semantics['surfaces'].index(semantic_object)

                # boundaries and semantic['values'] generated
                if geom_type == 'MultiSurface' or geom_type == 'CompositeSurface':
                    boundaries = from_multisurface_to_hierarchy(linestring, boundaries)
                    if surface[5] != None:
                        semantics['values'] = from_multisurface_to_hierarchy(value, semantics['values'])
                elif geom_type == 'Solid':
                    boundaries = from_solid_to_hierarchy(shell_num, linestring, boundaries)
                    if surface[5] != None:
                        semantics['values'] = from_solid_to_hierarchy(shell_num, value, semantics['values'])
                elif geom_type == 'MultiSolid' or geom_type == 'CompositeSolid':
                    boundaries = from_multisolid_to_hierarchy(solid_num, shell_num, linestring, boundaries)
                    if surface[5] != None:
                        semantics['values'] = from_multisolid_to_hierarchy(solid_num, shell_num, value,
                                                                           semantics['values'])

            # convert vertices to indexes and reconstruct the verticesList
            boundaries = from_vertex_to_index(boundaries, verticesList)
            geomproperties['boundaries'] = boundaries
            if semantics['surfaces'] != [] and semantics['values'] != []:
                geomproperties['semantics'] = semantics
            geometry_list.append(geomproperties)

    # add the geometries
    objproperties['geometry'] = geometry_list
    # add the cityobject
    queried_CityJSON['CityObjects'][CityObject[0]] = objproperties

        # G. vertices
    if 'transform' in queried_CityJSON.keys():
        verticesList = transform_vertices_back(queried_CityJSON['transform'], verticesList)

    queried_CityJSON['vertices'] = verticesList

    cityjson = CityJSON(j=queried_CityJSON)
    cityjson.remove_duplicate_vertices()

    return cityjson

    # # 3. Reconstruct CityJSON file
    # stringName = str('datasets/new/' + file_name + '.json')
    #
    # with open(stringName, 'w') as output_file:
    #     json.dump(cityjson.j, output_file)
    #     output_file.close()


#1. Connect to database
conn = psycopg2.connect("dbname=CityJSON user=postgres password=1234")
cur = conn.cursor() # Open a cursor to perform database operations

# query_feature('delft','test','b0a8da4cc-2d2a-11e6-9a38-393caa90be70')