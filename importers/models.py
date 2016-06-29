from __future__ import unicode_literals

from django.conf import settings

from django.contrib.gis.db import models
from django.contrib.gis.measure import Distance
from django.contrib.staticfiles import finders
from django.contrib.gis.geos import LineString

import googlemaps
import requests
import json

class SwitzerlandMobilityRouteManager(models.Manager):

    #login to Switzerlan Mobility and retrieve route list
    def get_routes_list_from_server(self, credentials):
        login_url = 'https://map.wanderland.ch/user/login'

        #login to map.wanderland.ch
        r = requests.post(login_url, data=json.dumps(credentials))

        #save cookies
        if r.status_code == requests.codes.ok:
            cookies = r.cookies
        else:
            sys.exit("Error: could not log-in to map.wanderland.ch")

        #retrieve route list
        routes_list_url = 'https://map.wanderland.ch/tracks_list'

        r = requests.post(routes_list_url, cookies=cookies)

        if r.status_code == requests.codes.ok:
            routes = r.json()
        else:
            sys.exit("Error: could not retrieve routes list from map.wanderland.ch")

        #Take routes list returned by map.wanderland.ch as list of 3 values
        #e.g. [2692136, u'Rochers de Nayes', None] and transform it into a dictionnary
        formatted_routes = []

        for route in routes:
            formatted_route = {'id': route[0], 'name': route[1], 'description': route[2]}
            formatted_routes.append(formatted_route)

            #update routes list in the database
            switzerland_mobility_route, created = SwitzerlandMobilityRoute.objects.get_or_create(
                    switzerland_mobility_id = formatted_route['id'],
                    defaults={
                            'name': formatted_route['name'],
                            'totalup': 0,
                            'totaldown': 0,
                            'length': 0,
                            'geom': LineString((0,0), (0,0)),
                        }

                )

            #update route name if it has changed
            if not(created) and switzerland_mobility_route.name != formatted_route['name']:
                switzerland_mobility_route.name = formatted_route['name']
                switzerland_mobility_route.save()

        return formatted_routes

class SwitzerlandMobilityRoute(models.Model):
    name = models.CharField(max_length=50)
    totalup = models.FloatField('Total elevation difference up in m', default=0)
    totaldown = models.FloatField('Total elevation difference down in m', default=0)
    length = models.FloatField('Total length of the track in m', default=0)
    description = models.TextField('Text description of the Route', default='')
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of last creation', auto_now_add=True)
    geom = models.LineStringField('line geometry', srid=21781)
    switzerland_mobility_id = models.BigIntegerField(unique=True)
    objects = SwitzerlandMobilityRouteManager()


    def get_distance(self, unit='m'):
        return Distance(**{unit: self.length})

    def get_point_elevation_on_line(self, location=0):
        sql = (
                'SELECT ST_Line_Interpolate_Point(%s, %s) '
                'FROM routes_place '
                'WHERE id = %s'
            )

        point = Route.objects.raw(sql,(self.geom, location, self.id))

        point.geom.transform(4326)

        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        result = gmaps.elevation(point.geom.coords)

        return result[0]['elevation']

    # Returns the string representation of the model.
    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
