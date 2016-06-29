import requests
import json
import os
import sys
from .models import SwitzerlandMobilityRoute
from django.contrib.gis.geos import GEOSGeometry


def get_routes_list(credentials):
    """logs-in to map.wanderland.ch and retieves user routes list as json"""

    print "Logging-in to map.wanderland.ch"

    login_url = 'https://map.wanderland.ch/user/login'

    r = requests.post(login_url, data=json.dumps(credentials))

    if r.status_code == requests.codes.ok:
        print "Successfully logged to map.wanderland.ch"
        cookies = r.cookies

    else:
        sys.exit("Error: could not log-in to map.wanderland.ch")

    print "Retrieving routes from map.wanderland.ch"

    routes_list_url = 'https://map.wanderland.ch/tracks_list'

    r = requests.post(routes_list_url, cookies=cookies)

    if r.status_code == requests.codes.ok:
        print "Successfully retrieved " + str(len(r.json())) + " routes"
        return r.json()
    else:
        sys.exit("Error: could not retrieve routes list from map.wanderland.ch")

def get_route(route_id):
    """retrieves map.wanderland.ch route information for a given route id"""

    print "Retrieving information for route " + str(route_id)

    route_base_url = 'https://map.wanderland.ch/track/'
    route_url = route_base_url + str(route_id) + "/show"

    r = requests.get(route_url)

    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        sys.exit("Error: could not retrieve route information from map.wanderland.ch for route " + str(roue_id))

def write_json_file(file_name, json_data, json_folder='data/json'):
    """Write to file"""

    print "Writing to file: " + json_folder + '/' + file_name

    content = json.dumps(json_data, indent=4)
    target = open(os.path.join(os.path.dirname(__file__), json_folder, file_name), 'w')
    target.write(content)
    target.close()

def read_json_file(file_name, json_folder='data/json'):
    """Load json file into Python dict"""

    json_file = open(os.path.join(os.path.dirname(__file__), json_folder, file_name), 'r')
    json_content = json_file.read()

    json_file.close()

    return json.loads(json_content)


def add_labels_to_routes_list(routes):
    """takes to routes list returned by map.wanderland.ch as list of 3 values e.g. [2692136, u'Rochers de Nayes', None] and transform into a dictionnary """

    print "Formatting labels for routes"

    formatted_routes = []

    for route in routes:
        formatted_route = {'id': route[0], 'name': route[1], 'description': route[2]}
        formatted_routes.append(formatted_route)

    return formatted_routes

def retrieve_routes(credentials):
    routes = get_routes_list(credentials)
    routes = add_labels_to_routes_list(routes)
    routes = get_routes_detail(routes)

    return routes


def transform_profile_into_polyline(profile):
    """Transform profile json data from map.wanderland.ch into postgis linestring geometry"""
    polyline = {}

    # Set geometry type to LineString
    polyline['type'] = 'LineString'

    # Specify proper SRID
    polyline['crs'] = json.loads('{"type":"name","properties":{"name":"EPSG:21781"}}')

    coordinates = []

    for point in json.loads(profile):
        position = [point[0], point[1]]
        coordinates.append(position)

    polyline['coordinates'] = coordinates

    return polyline

def retrieve_altitude_information(profile):
    """Retrive route altitude indormation from profile json data from map.wanderland.ch"""

    altitude = []

    for point in json.loads(profile):
        altitude.append(point[2])

    return altitude


def get_routes_detail(routes):
    """Add route details to routes in a routes list"""
    updated_routes = []

    for route in routes:
        # Retrieve route json from map.wanderland.ch
        route_json = get_route(route['id'])

        # Add route information to routes list
        route['totalup'] = route_json['properties']['meta']['totalup']
        route['totaldown'] = route_json['properties']['meta']['totaldown']
        route['length'] = route_json['properties']['meta']['length']
        route['owner'] = route_json['properties']['owner']

        # Find out the number of points in the route
        route['num_points'] = len(route_json['properties']['profile'])

        # Add GeoJSON line linestring from profile
        route['geometry'] = transform_profile_into_polyline(route_json['properties']['profile'])

        # Record altitude infromation to a list as long as the LineString
        route['altitude'] = retrieve_altitude_information(route_json['properties']['profile'])

        # Compile description for Sketch design
        route['description'] = '%.1fkm' % (route['length']/1000) + ' - ' + '%.fm+' % route['totalup'] + ' ' +  '%.fm-' % route['totaldown']

        # Add generic image path for Sketch design
        route['image'] = 'assets/' + str(route['id']) + '.jpg'

        updated_routes.append(route)

    return updated_routes

def save_all_routes_to_db(routes):
    """Write to DB"""

    for route in routes:

        route, created = SwitzerlandMobilityRoute.objects.get_or_create(
            switzerland_mobility_id = route['id'],
            name = route['name'],
            totalup = route['totalup'],
            totaldown = route['totaldown'],
            length = route['length'],
            geom = GEOSGeometry(json.dumps(route['geometry']), srid=21781)
        )

        route.save()


def get_routes():
    wanderland_credentials = {"username":"cedric.hofstetter@mac.com","password":"JKEHOE66"}
    routes = retrieve_routes(wanderland_credentials)
    write_json_file('routes.json', routes)

def read_and_save():
    routes = read_json_file('routes.json')
    save_all_routes_to_db(routes)
