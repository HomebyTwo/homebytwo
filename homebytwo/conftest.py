from pytest import fixture

from .utils.factories import AthleteFactory


@fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@fixture()
def test_athlete(db, client):
    athlete = AthleteFactory(user__password="testpassword")
    client.login(username=athlete.user.username, password="testpassword")
    return athlete
