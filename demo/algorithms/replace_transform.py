def from_index_to_vertex(boundaries, verticesList):
    #needed for every geometry 
    for i, temp_list in enumerate(boundaries):
        if not isinstance(temp_list, list):
            index = temp_list
            #always append the vertex to the verticesList 
            x, y, z = verticesList[index]
            #the index is the length of the verticesList minus one. 
            #In this way, the vertex does not have to be found 
            boundaries[i] = [x, y, z]
        else:
            boundaries[i] = from_index_to_vertex(temp_list, verticesList)
    return boundaries

def from_vertex_to_index(boundaries, verticesList):
    for i, temp_list in enumerate(boundaries):
        if not isinstance(temp_list[0], list):
            vertex = temp_list
            verticesList.append(vertex)
            boundaries[i] = len(verticesList) - 1
        else:
            boundaries[i] = from_vertex_to_index(temp_list, verticesList)
    return boundaries

def transform_vertices(transform, vertices):
    #decimals: only once needed 
    max_scale_number = 0
    max_translate_number = 0
    i = 0 
    while i < 3:
        scale_number = len(str(transform["scale"][i]).split('.')[1])
        translate_number = len(str(transform["translate"][i]).split('.')[1])
        if scale_number > max_scale_number:
            max_scale_number = scale_number
        if translate_number > max_translate_number:
            max_translate_number = translate_number
        i = i + 1 
    decimals = max_scale_number + max_translate_number
    #loop through the vertices 
    new_vertices = []
    for vi in vertices:
        v_x = round((vi[0] * transform["scale"][0]) + transform["translate"][0], decimals)
        v_y = round((vi[1] * transform["scale"][1]) + transform["translate"][1], decimals)
        v_z = round((vi[2] * transform["scale"][2]) + transform["translate"][2], decimals)
        v = [v_x, v_y, v_z]
        new_vertices.append(v)
    return new_vertices 

def transform_boundaries(transform, boundaries):
    for i, temp_list in enumerate(boundaries):
        if not isinstance(temp_list[0], list):
            v_x = (temp_list[0] * transform["scale"][0]) + transform["translate"][0]
            v_y = (temp_list[1] * transform["scale"][1]) + transform["translate"][1]
            v_z = (temp_list[2] * transform["scale"][2]) + transform["translate"][2]
            vertex = [v_x, v_y, v_z]
            boundaries[i] = vertex
        else:
            boundaries[i] = transform_boundaries(transform, temp_list)
    return boundaries


def transform_vertices_back(transform, vertices):
        new_vertices = []
        for vi in vertices:
            # vertices must be integers 
            v_x = int(round((vi[0] - transform["translate"][0])/ transform["scale"][0], 0))
            v_y = int(round((vi[1] - transform["translate"][1])/ transform["scale"][1], 0))
            v_z = int(round((vi[2] - transform["translate"][2])/ transform["scale"][2], 0))
            v = [v_x, v_y, v_z]
            new_vertices.append(v)
        return new_vertices 

def from_index_to_surface(values, surfaces):
    for i, value_list in enumerate(values):
        if not isinstance(value_list, list):
            index = value_list
            values[i] = surfaces[index]
        else:
            values[i] = from_index_to_surface(value_list, surfaces)
    return values
    
def from_surface_to_index(values, surfaces):
    for i, value_list in enumerate(values):
        if not isinstance(value_list, list):
            surface = value_list
            if surface not in surfaces: 
                surfaces.append(surface)
                values[i] = len(surfaces) - 1
            else:
                index = surfaces.index(surface)
                values[i] = index 
        else:
            values[i] = from_surface_to_index(value_list, surfaces)
    return values

def from_boundaries_to_POLYHEDRALSURFACEZ(boundaries, referenceSystem):

    
    exterior_shell = boundaries[0]
    # surface = [] (multiple surfaces --> 2D holes)
    surfaces_list = [] 
    for surface in exterior_shell:
        # linestring [] (multiple linestrings in one list) 
        linestring_list = [] 
        for linestring in surface:

            # vertex [] (multiple vertices --> list of vertices)  
            vertex_list = []
            first_vertex = "{0} {1} {2}".format(linestring[0][0], linestring[0][1], linestring[0][2])
            for vertex in linestring: 
                vertex = "{0} {1} {2}".format(vertex[0], vertex[1], vertex[2])
                vertex_list.append(vertex)
            vertex_list.append(first_vertex)
            linestring_list.append(tuple(vertex_list)) 
            # vertex [] (multiple vertices --> list of vertices)

        if len(linestring_list) == 1:
            surfaces_list.append('(' + str(linestring_list[0]) + ')')
        else:
            surfaces_list.append(str(tuple(linestring_list))) 
        # linestring [] (multiple linestrings or linestring in one list) 
    if len(surfaces_list) == 1:
        final = '(' + str(surfaces_list[0]) + ')'
    else:
        final = str(tuple(surfaces_list))
    # surface = [] (multiple surfaces --> 2D holes)
    final = final.replace("'", "")
    final = final.replace('"', "")
    if referenceSystem is None: 
        final = 'POLYHEDRALSURFACEZ {}'.format(final)
    else:
        final = 'SRID={}; POLYHEDRALSURFACEZ {}'.format(referenceSystem, final)
    return final


def from_boundaries_to_MULTISURFACEZ(boundaries, referenceSystem):
    # surface = [] (multiple surfaces --> 2D holes)
    surfaces_list = [] 
    for surface in boundaries:
        # linestring [] (multiple linestrings in one list) 
        linestring_list = [] 
        for linestring in surface:

            # vertex [] (multiple vertices --> list of vertices)  
            vertex_list = []
            first_vertex = "{0} {1} {2}".format(linestring[0][0], linestring[0][1], linestring[0][2])
            for vertex in linestring: 
                vertex = "{0} {1} {2}".format(vertex[0], vertex[1], vertex[2])
                vertex_list.append(vertex)
            vertex_list.append(first_vertex)
            linestring_list.append(tuple(vertex_list)) 
            # vertex [] (multiple vertices --> list of vertices)

        if len(linestring_list) == 1:
            surfaces_list.append('(' + str(linestring_list[0]) + ')')
        else:
            surfaces_list.append(str(tuple(linestring_list))) 
        # linestring [] (multiple linestrings or linestring in one list) 
    if len(surfaces_list) == 1:
        final = '(' + str(surfaces_list[0]) + ')'
    else:
        final = str(tuple(surfaces_list))
    # surface = [] (multiple surfaces --> 2D holes)
    final = final.replace("'", "")
    final = final.replace('"', "")
    if referenceSystem is None: 
        final = 'MULTISURFACEZ {}'.format(final)
    else:
        final = 'SRID={}; MULTISURFACEZ {}'.format(referenceSystem, final)
    return final
