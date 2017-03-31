from django import template
import datetime
register = template.Library()


@register.filter(name='duration')
def timedelta(value, display_format="long"):
    if value is None:
        return value
    return nice_repr(value, display_format)


def baseround(x, base=5):
    return int(base * round(float(x)/base))


def nice_repr(timedelta, display_format="long", sep=" "):
    """
    Turn a datetime.timedelta object into a human readable string
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

    assert isinstance(timedelta, datetime.timedelta), "First argument must be a timedelta."

    result = []

    weeks = timedelta.days / 7
    days = timedelta.days % 7
    hours = timedelta.seconds / 3600
    minutes = (timedelta.seconds % 3600) / 60
    seconds = timedelta.seconds % 60

    values = [weeks, days, hours, minutes]

    if display_format == 'hike':
        values[-1] = baseround(values[-1])
        words = [" wks", " days", " h", " min"]

    else:
        values.append(seconds)
        words = [" weeks", " days", " hours", " minutes", " seconds"]

    for i in range(len(values)):
        if values[i]:
            if values[i] == 1 and len(words[i]) > 1:
                result.append("%i%s" % (values[i], words[i].rstrip('s')))
            else:
                result.append("%i%s" % (values[i], words[i]))

    return sep.join(result)
