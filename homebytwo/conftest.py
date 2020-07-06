import pytest

from .utils.factories import AthleteFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture()
def test_athlete(db, client):
    athlete = AthleteFactory(user__password="testpassword")
    client.login(username=athlete.user.username, password="testpassword")
    return athlete
