class SwitzerlandMobilityError(Exception):
    """
    the connection to Switzerland Mobility Plus works but the server
    responds with an error code: 404, 500, etc.
    """

    pass


class StravaMissingCredentials(Exception):
    """
    the athlete has no Strava credentials connected with his account
    """

    pass


class SwitzerlandMobilityMissingCredentials(Exception):
    """
    the athlete is not logged-in to SwitzerlandMobility Plus
    """

    pass


class ElevationAPIError(Exception):
    """
    the request to the elevation API returned bad results
    """
