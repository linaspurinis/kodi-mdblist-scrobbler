import json

import xbmc


SUPPORTED_IDS = {
    "movie": {"imdb", "tmdb", "trakt", "kitsu", "mdblist"},
    "episode": {"imdb", "tmdb", "trakt", "tvdb", "mdblist"},
}

ID_ALIASES = {
    "imdbnumber": "imdb",
    "imdb_id": "imdb",
    "themoviedb": "tmdb",
    "tmdb_id": "tmdb",
    "tvdb_id": "tvdb",
    "trakt_id": "trakt",
    "kitsu_id": "kitsu",
    "mdblist_id": "mdblist",
}


def jsonrpc_request(method: str, params=None):
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1
    }

    if params is not None:
        request["params"] = params

    request_json = json.dumps(request)

    xbmc.log("Sending JSON-RPC request: {}".format(request_json), level=xbmc.LOGDEBUG)
    response_json = xbmc.executeJSONRPC(request_json)
    xbmc.log("Response from JSON-RPC request: {}".format(response_json), level=xbmc.LOGDEBUG)

    return json.loads(response_json).get("result", {})


def _coerce_unknown_id(unique_id, media_type: str):
    if unique_id is None:
        return None, None

    if isinstance(unique_id, str):
        cleaned = unique_id.strip()
        if not cleaned:
            return None, None

        if cleaned.startswith("tt"):
            return "imdb", cleaned
        if cleaned.isdigit():
            return ("tvdb", cleaned) if media_type == "episode" else ("tmdb", cleaned)
        return None, None

    if isinstance(unique_id, int):
        return ("tvdb", unique_id) if media_type == "episode" else ("tmdb", unique_id)

    return None, None


def fix_unique_ids(unique_ids: dict, media_type: str):
    if not isinstance(unique_ids, dict):
        return {}

    canonical = {}

    for raw_key, raw_value in unique_ids.items():
        if raw_value in (None, ""):
            continue

        key = str(raw_key).strip().lower()
        key = ID_ALIASES.get(key, key)

        if key == "unknown":
            continue

        canonical[key] = raw_value

    # Backward-compatible fallback: map Kodi "unknown" id when no canonical ids exist.
    if not canonical and "unknown" in unique_ids:
        mapped_key, mapped_value = _coerce_unknown_id(unique_ids.get("unknown"), media_type)
        if mapped_key:
            canonical[mapped_key] = mapped_value

    allowed = SUPPORTED_IDS.get(media_type, set())
    filtered = {key: value for key, value in canonical.items() if key in allowed}

    return filtered
