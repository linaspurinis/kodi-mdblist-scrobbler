import requests
import urllib.parse
import xbmc
import xbmcaddon

from resources.lib import oauth


REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_BASE_URL = "https://api.mdblist.com"


class MDBListApiError(Exception):
    pass


def _addon():
    return xbmcaddon.Addon()


def get_string_setting(setting_id: str, default: str = ""):
    try:
        value = _addon().getSettings().getString(setting_id)
        return value or default
    except TypeError:
        return default


def base_url():
    url = get_string_setting("url", DEFAULT_BASE_URL)
    return url[:-1] if url.endswith("/") else url


def auth_params():
    access_token = oauth.ensure_valid_token()
    apikey = "" if access_token else get_string_setting("apikey")

    if access_token:
        return {"headers": {"Authorization": "Bearer {}".format(access_token)}, "query": ""}
    if apikey:
        return {"headers": None, "query": urllib.parse.urlencode({"apikey": apikey})}

    raise MDBListApiError("Not authenticated. Open addon settings to connect.")


def request(method: str, endpoint: str, params=None, json_data=None):
    auth = auth_params()
    url = "{}{}".format(base_url(), endpoint)

    query = auth["query"]
    if params:
        filtered = {key: value for key, value in params.items() if value not in (None, "")}
        encoded = urllib.parse.urlencode(filtered)
        if encoded:
            query = "{}&{}".format(query, encoded) if query else encoded
    if query:
        url = "{}?{}".format(url, query)

    try:
        response = requests.request(
            method,
            url,
            json=json_data,
            headers=auth["headers"],
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exception:
        raise MDBListApiError(str(exception))

    if response.status_code >= 400:
        xbmc.log(
            "MDBList Scrobbler: API error {} on {} response={}".format(
                response.status_code, endpoint, response.text[:200]
            ),
            level=xbmc.LOGERROR,
        )
        raise MDBListApiError("API Error {}: {}".format(response.status_code, response.text[:80]))

    try:
        return response.json()
    except ValueError:
        return {}


def fetch_watchlist(mediatype=None, limit=100):
    endpoint = "/watchlist/items/{}".format(mediatype) if mediatype else "/watchlist/items"
    cursor = None
    movies = []
    shows = []

    while True:
        params = {"limit": limit, "append_to_response": "poster"}
        if cursor:
            params["cursor"] = cursor

        data = request("GET", endpoint, params=params)
        if isinstance(data, list):
            movies.extend([item for item in data if item.get("mediatype") == "movie"])
            shows.extend([item for item in data if item.get("mediatype") == "show"])
        else:
            movies.extend(data.get("movies") or [])
            shows.extend(data.get("shows") or [])

        pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
        cursor = pagination.get("next_cursor")
        if not cursor:
            break

    return {"movies": movies, "shows": shows}


def modify_watchlist(action: str, mediatype: str, ids: dict):
    if mediatype == "movie":
        payload = {"movies": [ids]}
    elif mediatype == "show":
        payload = {"shows": [ids]}
    else:
        raise MDBListApiError("Unsupported watchlist type: {}".format(mediatype))

    return request("POST", "/watchlist/items/{}".format(action), json_data=payload)
