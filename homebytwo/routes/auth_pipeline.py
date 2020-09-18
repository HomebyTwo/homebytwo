from .tasks import (
    import_strava_activities_streams_task,
    import_strava_activities_task,
    train_prediction_models_task,
)


def import_strava(backend, user, response, *args, **kwargs):
    print("import strava")
    (
        import_strava_activities_task.s(athlete_id=user.athlete.id)
        | import_strava_activities_streams_task.s()
        | train_prediction_models_task.si(athlete_id=user.athlete.id)
    ).delay()
