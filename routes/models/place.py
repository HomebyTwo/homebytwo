from __future__ import unicode_literals

from django.contrib.gis.db import models
from django.conf import settings

import googlemaps
import requests
import json
from datetime import datetime


class PlaceManager(models.Manager):
    """
    Manager to retrieve places.
    """
    def get_public_transport(self):
        self.filter(public_transport=True)

    def get_places_from_route(self, route, max_distance=100):

        sql = ('SELECT routes_place.id,'
               'ST_DISTANCE(routes_route.geom, routes_place.geom) AS distance_from_route, '
               'ST_LineLocatePoint(routes_route.geom, routes_place.geom) AS line_location '
               'FROM routes_route, routes_place '
               'WHERE routes_route.id = %s '
               'AND ST_DWithin(routes_route.geom, routes_place.geom, %s) '
               'ORDER BY ST_LineLocatePoint(routes_route.geom, routes_place.geom), '
               'ST_DISTANCE(routes_route.geom, routes_place.geom);'
               )
        # Execute the RAW query
        return self.raw(sql, [route.id, max_distance])


class Place(models.Model):
    """
    Places are geographic points along routes.
    They have a name, description and geom
    Places are used to create segments from routes and
    and for public transport connection.

    """
    type = models.CharField(max_length=50)
    altitude = models.FloatField()
    name = models.CharField(max_length=250)
    description = models.TextField('Text description of the Place', default='')
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of last creation', auto_now_add=True)
    public_transport = models.BooleanField(default=False)

    geom = models.PointField(srid=21781)

    objects = PlaceManager()

    # Returns altitude for a place and updates the database entry
    def get_gmaps_elevation(self):
        # Extract first geometry from Multipoint
        geom = self.geom

        # Transform coords to Gmaps SRID
        geom.transform(4326)

        # Query gmaps API for altitude
        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        coords = (geom.coords.y, geom.coords.x)
        result = gmaps.elevation(coords)

        # Update altitude information for point
        self.altitude = result[0]['elevation']
        self.save()

        return self.altitude

    def get_public_transport_connections(self,
                                         destination,
                                         via=[],
                                         travel_to_place=False,
                                         travel_datetime=datetime.now(),
                                         is_arrival_time=False,
                                         limit=1,
                                         bike=0):
        """
        Get connection information from the place to a destination
        using the public transport API.
        If travelling to the place instead of from the place,
        the connection can be queried using the travel_to_place=True flag
        An object is returned containing departure and arrival time
        """

        # Ensure the place is a public transport stop
        if not self.public_transport:
            print('Error: place is not connected to public transport network')
            return

        # Base public transport API URL
        url = '%s/connections' % settings.SWISS_PUBLIC_TRANSPORT_API_URL

        # Set origin and destination according to travel_to_place flag
        if travel_to_place:
            origin = destination
            destination = self.name
        else:
            origin = self.name

        # Define API call parameters
        args = {
            'from': origin,
            'to': destination,
            'date': str(travel_datetime.date()),
            'time': travel_datetime.strftime('%H:%S'),
            'isArrivalTime': is_arrival_time,
            'limit': limit,
            'bike': bike,
            'fields[]': [
                         'connections/from/departure',
                         'connections/to/arrival',
                         'connections/duration',
                         'connections/products',
                         ]
        }
        kwargs = {'params': args}

        # Call the API
        try:
            response = requests.get(url, **kwargs)
        except requests.exceptions.ConnectionError:
            print('Error: Could not reach network.')

        if not response.ok:
            print('Server Error: HTTP %s' %
                  (response.status_code, ))
            return

        try:
            data = json.loads(response.text)
        except ValueError:
            print('Error: Invalid API response (invalid JSON)')
            return

        if not data['connections']:
            msg = 'No connections found from "%s" to "%s".' % \
                  (data['from']['name'], data['to']['name'])
            print(msg)

        return data

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
