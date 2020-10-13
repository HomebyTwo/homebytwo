from datetime import timedelta

from django import template

register = template.Library()


@register.filter(name="duration")
def display_timedelta(value, display_format="long"):
    if value is None:
        return value
    return nice_repr(value, display_format)


def base_round(x, base=5):
    return int(base * round(float(x) / base))


def nice_repr(value, display_format="long", sep=" "):
    """
    Turn a timedelta object into a human readable string
    available formats are long [default] or hike.

    the hike display_format follows the format displayed on hiking signs
    as defined by wandern.ch:

    > Les indications des temps de marche (unités h, min) sont arrondies
    > aux 5 minutes les plus proches. A partir d’un temps de marche de
    > trois heures, les indications x h 5 min ou x h 55 min sont arrondies
    > à l’heure la plus proche.
    (source: https://www.randonner.ch/download.php?id=3331_3e0faeba)

    >>> from datetime import timedelta as td
    >>> nice_repr(td(days=1, hours=2, minutes=3, seconds=4))
    '1 day, 2 hours, 3 minutes, 4 seconds'
    >>> nice_repr(td(days=1, seconds=1), "hike")
    '1 day 2 h 5  min'
    """
    if not isinstance(value, timedelta):
        try:
            value = timedelta(seconds=value)
        except TypeError:
            raise TypeError("value should be a timedelta or a number")

    result = []

    weeks = int(value.days / 7)
    days = value.days % 7
    hours = int(value.seconds / 3600)
    minutes = int((value.seconds % 3600) / 60)
    seconds = value.seconds % 60

    values = [weeks, days, hours, minutes]

    if display_format == "hike":
        # round up seconds
        if seconds >= 30:
            minutes += 1

        # make minutes a multiple of 5
        minutes = base_round(minutes)
        if minutes == 60:
            hours += 1
            minutes = 0

        # from 3 hours upwards, round 05 and 55 the next hour
        if hours >= 3:
            if minutes == 55:
                hours += 1
                minutes = 0
            if minutes == 5:
                minutes = 0

        values = [weeks, days, hours, minutes]
        words = [" wks", " days", " h", " min"]

    else:
        values = [weeks, days, hours, minutes, seconds]
        words = [" weeks", " days", " hours", " minutes", " seconds"]

    for i in range(len(values)):
        if values[i]:
            if values[i] == 1 and len(words[i]) > 1:
                result.append("%i%s" % (values[i], words[i].rstrip("s")))
            else:
                result.append("%i%s" % (values[i], words[i]))

    # values with less than one second, which are considered zeroes
    if len(result) == 0:
        # display as 0 of the smallest unit
        result.append("0%s" % (words[-1]))

    return sep.join(result)
