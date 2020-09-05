from .tasks import import_strava_activities_task, import_strava_activities_streams_task


def import_strava(backend, user, response, *args, **kwargs):
    print("import strava")
    (
        import_strava_activities_task.s(athlete_id=user.athlete.id)
        | import_strava_activities_streams_task.s()
    ).delay()
