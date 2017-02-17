from django.conf import settings
from django.contrib.staticfiles import finders

from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .segment import Segment
from .place import Place
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point
from django.utils.translation import gettext_lazy as _

import googlemaps
from pandas import read_hdf, DataFrame
import uuid
import os


class DataFrameFileField(models.FileField):
    """
    Custom Filefield to save the DataFramen to the hdf5 file format as adviced
    here: http://pandas.pydata.org/pandas-docs/stable/io.html#io-perf
    """

    default_error_messages = {
        'invalid': _('Provide a DataFrame'),
        'io_error': _('Could not write to file')
    }

    def generate_unique_filename(self):
        """
        generate a unique filename for the saved file.
        """
        filename = uuid.uuid4().hex + '.h5'

        return filename

    def get_fullpath(self, filename):
        """
        returns the full os path based on the MEDIA_ROOT setting,
        the upload_to attribute of the Model Field and the filename.
        """
        dirname = os.path.join(settings.MEDIA_ROOT, self.upload_to)
        fullpath = os.path.join(dirname, filename)

        return fullpath

    def write_hdf5(self, data, filename):
        dirname = os.path.join(settings.MEDIA_ROOT, self.upload_to)
        fullpath = self.get_fullpath(filename)

        if not isinstance(data, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            data.to_hdf(fullpath, 'df', mode='w', format='fixed')
        except Exception as exc:
            raise IOError(
                self.error_messages['io_error']
            ) from exc

    def get_prep_value(self, value):
        """
        let's save the DataFrame as a file with in the MEDIA_ROOT folder
        and put the filename in the valuebase.
        """

        if value is None:
            return value

        if not isinstance(value, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        # if the valueframe was loaded from the database before,
        # it will has a filename attribute.
        if hasattr(value, 'filename'):
            filename = value.filename

        else:
            # create a new filename
            filename = self.generate_unique_filename()

        self.write_hdf5(value, filename)

        return filename

    def to_python(self, filename):
        """
        get the file location from the database
        and load the DataFrame from the file.
        """
        dirname = os.path.join(settings.MEDIA_ROOT, self.upload_to)
        fullpath = os.path.join(dirname, filename)

        # try to load the pandas DataFrame into memory
        try:
            data = read_hdf(fullpath)

        except Exception:
            raise

        if not isinstance(data, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        # set attribute on for saving later
        data.filename = filename

        return data


class Track(models.Model):

    class Meta:
        abstract = True

    name = models.CharField(max_length=100)
    description = models.TextField('Textual description', default='')

    # link to user
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # elevation gain in m
    totalup = models.FloatField('Total elevation gain in m', default=0)
    # elevation loss in m
    totaldown = models.FloatField('Total elevation loss in m', default=0)
    # route distance in m
    length = models.FloatField('Total length of the track in m', default=0)

    # creation and update date
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of creation', auto_now_add=True)

    # geographic information
    geom = models.LineStringField('line geometry', srid=21781)

    # Start and End-place
    start_place = models.ForeignKey(
        Place,
        null=True,
        related_name='starts_%(class)s'
    )

    end_place = models.ForeignKey(
        Place,
        null=True,
        related_name='ends_%(class)s'
    )

    # track data as a pandas DataFrame
    # data = DataFrameField(save_to='data/')

    # Returns poster picture for the list view
    def get_poster_picture(self):
        if finders.find('routes/images/' + str(self.id) + '.jpg'):
            return 'routes/images/' + str(self.id) + '.jpg'
        else:
            return 'routes/images/default.jpg'

    def get_length(self):
        return D(m=self.length)

    def get_totalup(self):
        return D(m=self.totalup)

    def get_totaldown(self):
        return D(m=self.totaldown)

    def get_start_altitude(self):
        start_altitude = self.get_point_altitude_along_track(0)
        return start_altitude

    def get_end_altitude(self):
        end_altitude = self.get_point_altitude_along_track(1)
        return end_altitude

    def get_closest_places_along_track(self, track_location=0,
                                       max_distance=100):

        # create the point from location
        point = self.geom.interpolate_normalized(track_location)

        # get closest places to the point
        places = Place.objects.get_places_within(point, max_distance)

        return places

    def get_point_altitude_along_track(self, track_location=0):
        point = self.geom.interpolate_normalized(track_location)

        # format coordoinates for Google Maps API
        point.transform(4326)
        coords = (point.y, point.x)

        # request altitude
        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        result = gmaps.elevation(coords)
        altitude = result[0]['elevation']

        # return distance object
        return D(m=altitude)

    def segment_route_with_points(self, places):
        """
        Creates segments from a list of places.

        The list of places should be annotated with their location
        along the line: line_location a float between 0 and 1.
        """
        # SQL to create a subline along a route using ST_Line_Substring
        sql = ('SELECT id, ST_Line_Substring(routes_route.geom, %s, %s) as geom'
               'FROM routes_route WHERE routes_route.id = %s')

        # Calculate distance between route start and first place
        first_place = places[0]
        starting_point = Point(self.geom[0])
        distance_to_first_place = starting_point.distance(first_place.geom)

        # Create a private first segment if start
        # is more than 50m away from first place.
        if distance_to_first_place > 50:
            rawquery = self.objects.raw(sql, [0, first_place.line_location,
                                              self.id])

            # First result returns the geometry
            geom = rawquery[0].geom
            name = 'start of %s to %s' % [self.name, first_place.name]
            args = {
                'name': name,
                'start_place': None,
                'end_place': first_place,
                'geom': geom,
                'elevation_up': 0,
                'elevation_down': 0,
                'private': True
            }

            segment = Segment.objects.create(args)
            segment.get_elevation_data()

        # Save segments
        for i, place in enumerate(places[:-1]):
            # Raw query to create the segment geom
            rawquery = self.objects.raw(sql, [place.line_location,
                                              places[i+1].line_location,
                                              self.id])

            # First result returns the geometry
            geom = rawquery[0].geom

            # By default, the name of the segment is 'Start Place - End Place'
            name = place.name + ' - ' + places[i+1].name
            args = {
                    'name': name,
                    'start_place': place,
                    'end_place': places[i+1],
                    'geom': geom,
                    'elevation_up': 0,
                    'elevation_down': 0,
                    'private': False,
            }

            segment = Segment.objects.create(args)
            segment.get_elevation_data()

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
