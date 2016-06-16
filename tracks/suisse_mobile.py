import requests
import json
import os
from tracks.models import Track
from django.contrib.gis.geos import GEOSGeometry


def get_tracks_list(credentials):
    """logs-in to map.wanderland.ch and retieves user tracks list as json"""

    print "Logging-in to map.wanderland.ch"

    login_url = 'https://map.wanderland.ch/user/login'

    r = requests.post(login_url, data=json.dumps(credentials))

    if r.status_code == requests.codes.ok:
        print "Successfully logged to map.wanderland.ch"
        cookies = r.cookies

    else:
        sys.exit("Error: could not log-in to map.wanderland.ch")

    print "Retrieving tracks from map.wanderland.ch"

    tracks_list_url = 'https://map.wanderland.ch/tracks_list'

    r = requests.post(tracks_list_url, cookies=cookies)

    if r.status_code == requests.codes.ok:
        print "Successfully retrieved " + str(len(r.json())) + " tracks"
        return r.json()

def get_track(track_id):
    """retrieves map.wanderland.ch track information for a given track id"""

    print "Retrieving information for track " + str(track_id)

    track_base_url = 'https://map.wanderland.ch/track/'
    track_url = track_base_url + str(track_id) + "/show"

    r = requests.get(track_url)

    if r.status_code == requests.codes.ok:
        return r.json()

def write_json_file(file_name, json_data, json_folder='data/json'):
    """Write to file"""

    print "Writing to file: " + json_folder + '/' + file_name

    content = json.dumps(json_data, indent=4)
    target = open(os.path.join('tracks', json_folder, file_name), 'w')
    target.write(content)
    target.close()

def read_json_file(file_name, json_folder='data/json'):
    """Load json file into Python dict"""

    json_file = open(os.path.join('tracks', json_folder, file_name), 'r')
    json_content = json_file.read()

    json_file.close()

    return json.loads(json_content)


def add_labels_to_tracks_list(tracks):
    """takes to tracks list returned by map.wanderland.ch as list of 3 values e.g. [2692136, u'Rochers de Nayes', None] and transform into a dictionnary """

    print "Formatting labels for tracks"

    formatted_tracks = []

    for track in tracks:
        formatted_track = {'id': track[0], 'name': track[1], 'description': track[2]}
        formatted_tracks.append(formatted_track)

    return formatted_tracks

def retrieve_tracks(credentials):
    tracks = get_tracks_list(credentials)
    tracks = add_labels_to_tracks_list(tracks)
    tracks = get_tracks_detail(tracks)

    return tracks


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
    """Retrive track altitude indormation from profile json data from map.wanderland.ch"""

    altitude = []

    for point in json.loads(profile):
        altitude.append(point[2])

    return altitude


def get_tracks_detail(tracks):
    """Add track details to tracks in a tracks list"""
    updated_tracks = []

    for track in tracks:
        # Retrieve track json from map.wanderland.ch
        track_json = get_track(track['id'])

        # Add track information to tracks list
        track['totalup'] = track_json['properties']['meta']['totalup']
        track['totaldown'] = track_json['properties']['meta']['totaldown']
        track['length'] = track_json['properties']['meta']['length']
        track['owner'] = track_json['properties']['owner']

        # Find out the number of points in the track
        track['num_points'] = len(track_json['properties']['profile'])

        # Add GeoJSON line linestring from profile
        track['geometry'] = transform_profile_into_polyline(track_json['properties']['profile'])

        # Record altitude infromation to a list as long as the LineString
        track['altitude'] = retrieve_altitude_information(track_json['properties']['profile'])

        # Compile description for Sketch design
        track['description'] = '%.1fkm' % (track['length']/1000) + ' - ' + '%.fm+' % track['totalup'] + ' ' +  '%.fm-' % track['totaldown']

        # Add generic image path for Sketch design
        track['image'] = 'assets/' + str(track['id']) + '.jpg'

        updated_tracks.append(track)

    return updated_tracks

def save_all_tracks_to_db(tracks):
    """Write to DB"""

    for track in tracks:

        track, created = Track.objects.get_or_create(
            swissmobility_id = track['id'],
            name = track['name'],
            totalup = track['totalup'],
            totaldown = track['totaldown'],
            length = track['length'],
            geom = GEOSGeometry(json.dumps(track['geometry']), srid=21781)
        )

        track.save()


def get_tracks():
    wanderland_credentials = {"username":"cedric.hofstetter@mac.com","password":"JKEHOE66"}
    tracks = retrieve_tracks(wanderland_credentials)
    write_json_file('tracks.json', tracks)

def read_and_save():
    tracks = read_json_file('tracks.json')
    save_all_tracks_to_db(tracks)
