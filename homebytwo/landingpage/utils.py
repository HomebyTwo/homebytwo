from django.conf import settings


def get_mailchimp_base_url():
    """
    Construct MailChimp API Base URI from the API key: "12345678987abc-usXX"
    """
    key, data_center = settings.MAILCHIMP_API_KEY.split("-")
    return "https://{data_center}.api.mailchimp.com/3.0".format(
        data_center=data_center.lower()
    )


def get_mailchimp_post_url():
    """
    Construct MailChimp API url for adding a new subscriber
    """
    return "{api_base_url}/lists/{mailchimp_list_id}/members/".format(
        api_base_url=get_mailchimp_base_url(),
        mailchimp_list_id=settings.MAILCHIMP_LIST_ID,
    )


def get_mailchimp_search_url(email):
    """
    Construct MailChimp API url for searching for an exiisting subscriber
    """

    return "{api_base_url}/search-members?query={email}".format(
        api_base_url=get_mailchimp_base_url(), email=email
    )
