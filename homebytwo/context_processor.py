from django.conf import settings


def gtm_context_processor(request):
    """
    Adds the GTM container ID from env to the context
    """
    return {'gtm_container_id': settings.GTM_CONTAINER_ID}
