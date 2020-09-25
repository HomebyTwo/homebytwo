from homebytwo.routes.tests.factories import RouteFactory, ActivityFactory
from homebytwo.utils.factories import AthleteFactory


def test_coda_client():
    athletes = AthleteFactory.create_batch(5)
    for athlete in athletes:
        RouteFactory.create_batch(5, athlete=athlete)
        ActivityFactory.create_batch(5, athlete=athlete)

