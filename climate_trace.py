import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.climatetrace.org/v7"
API_DOCS_URL = "https://api.climatetrace.org/v7/docs/index.html"
API_TIMEOUT_SECONDS = 20


class ClimateTraceAPIError(RuntimeError):
    pass


def _get_json(endpoint, params=None):
    query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
    url = f"{API_BASE_URL}{endpoint}"
    if query:
        url = f"{url}?{query}"
    request = Request(url, headers={"User-Agent": "UN Data Commons dashboard"})

    try:
        with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            payload = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()
        if (
            endpoint == "/owners"
            and error.code == 404
            and "No owners matched" in detail
        ):
            return []
        raise ClimateTraceAPIError(
            f"Climate TRACE API returned HTTP {error.code}: {detail[:300]}"
        ) from error
    except (TimeoutError, URLError) as error:
        raise ClimateTraceAPIError(f"Climate TRACE API request failed: {error}") from error

    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise ClimateTraceAPIError("Climate TRACE API returned invalid JSON.") from error


def search_owners(name, limit=20):
    result = _get_json("/owners", {"name": name, "limit": limit})
    if not isinstance(result, list):
        raise ClimateTraceAPIError("Climate TRACE owner search returned an unexpected response.")
    return result


def get_owner_emissions(owner_id, year, gas):
    result = _get_json(
        "/sources/emissions",
        {"ownerIds": owner_id, "year": year, "gas": gas},
    )
    if not isinstance(result, dict):
        raise ClimateTraceAPIError("Climate TRACE emissions query returned an unexpected response.")
    return result


def get_owner_sources(owner_id, year, gas, limit=100):
    result = _get_json(
        "/sources",
        {
            "ownerIds": owner_id,
            "year": year,
            "gas": gas,
            "limit": limit,
            "offset": 0,
        },
    )
    if not isinstance(result, list):
        raise ClimateTraceAPIError("Climate TRACE asset query returned an unexpected response.")
    return result


def get_source_history(source_id, start_year, end_year, gas):
    result = _get_json(
        f"/sources/{quote(str(source_id), safe='')}",
        {
            "start": start_year,
            "end": end_year,
            "timeGranularity": "year",
            "gas": gas,
        },
    )
    if not isinstance(result, dict):
        raise ClimateTraceAPIError("Climate TRACE asset history returned an unexpected response.")
    return result
