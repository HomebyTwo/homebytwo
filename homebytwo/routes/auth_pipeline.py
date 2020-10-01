from .tasks import (
    import_strava_activities_streams_task,
    import_strava_activities_task,
    train_prediction_models_task,
)


def import_strava(user, *args, **kwargs):
    """
    Final step of the social authentication pipeline

    Import all Strava activities of new athletes and their corresponding
    streams. Then train the prediction models.
    For existing athletes, there is no need to update activities as they
    are kept up-to-date by the Strava Webhook. We only fetch missing
    activity streams and finally train the prediction models.
    """

    # new athlete, created by social auth
    if not user.athlete.activities_imported:
        (
            import_strava_activities_task.s(athlete_id=user.athlete.id)
            | import_strava_activities_streams_task.s()
            | train_prediction_models_task.si(athlete_id=user.athlete.id)
        ).delay()

    # existing athlete
    else:
        activities = user.athlete.activities.filter(
            streams__isnull=True, skip_streams_import=False
        )
        activity_ids = activities.values_list("strava_id", flat=True)
        (
            import_strava_activities_streams_task.s(list(activity_ids))
            | train_prediction_models_task.si(athlete_id=user.athlete.id)
        ).delay()
