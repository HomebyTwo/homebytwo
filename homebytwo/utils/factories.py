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

    username = factory.Sequence(lambda n: "test_user_%s" % n)
    email = factory.LazyAttribute(lambda o: "%s@example.org" % o.username)
    password = "test_password"
    athlete = factory.RelatedFactory(
        "homebytwo.utils.factories.AthleteFactory", factory_related_name="user"
    )

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override the default ``_create`` with our custom call."""
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, **kwargs)

    @factory.post_generation
    def social_auth(self, create, extracted, **kwargs):
        if not create:
            return

        # check if the user has an associated Strava account and create one if missing
        social_auth, created = self.social_auth.get_or_create(
            provider="strava", uid=factory.Sequence(lambda n: 1000 + n)
        )
        return social_auth


class AthleteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Athlete

    user = factory.SubFactory(UserFactory, athlete=None)
