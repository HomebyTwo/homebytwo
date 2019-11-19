from django.contrib.auth.models import User

import factory
from social_django.models import UserSocialAuth

from ..routes.models import Athlete


def get_field_choices(choices):
    """
    Return choices of Modelfield as a flattened list (generator),
    even if the choices are organized as groups.
    yes, I'm looking at you Place.place_type!
    """

    # iterate over the unpacked choices assuming they are groups.
    for groupname, group in choices:
        # if the group value is a string, it is not a group, it is a choice
        if isinstance(group, str):
            yield (groupname)
        else:
            for key, value in group:
                yield key


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: "testuser%s" % n)
    email = factory.LazyAttribute(lambda o: "%s@example.org" % o.username)
    password = "testpassword"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override the default ``_create`` with our custom call."""
        manager = cls._get_manager(model_class)
        # The default would use ``manager.create(*args, **kwargs)``
        return manager.create_user(*args, **kwargs)


class AthleteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Athlete
        exclude = ["place_types"]

    user = factory.SubFactory(UserFactory)

    @factory.post_generation
    def create_social_user(self, create, extracted, **kwargd):
        # check if the user has an associated Strava account and create one if missing
        if create:
            try:
                self.user.social_auth.get(provider="strava")
            except UserSocialAuth.DoesNotExist:
                """
                prevent duplicate entries for uid in the test database
                when tests run in parallel.
                """
                latest_social_user = UserSocialAuth.objects.order_by("-uid").first()

                if latest_social_user:
                    uid = int(latest_social_user.uid) + 1
                else:
                    uid = 1

                UserSocialAuth.objects.create(
                    user=self.user,
                    provider="strava",
                    uid=uid,
                )
