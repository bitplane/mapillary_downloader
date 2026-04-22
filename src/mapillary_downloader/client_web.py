"""Mapillary web frontend client for leaderboard and location search."""

import json
import logging
import re
import time
from functools import lru_cache

import requests

logger = logging.getLogger("mapillary_downloader")

GRAPHQL_URL = "https://graph.mapillary.com/graphql"
LOCATION_SEARCH_URL = "https://graph.mapillary.com/location_search"

# Meta's GraphQL endpoint expects a pre-registered `doc` string (whitespace-preserved,
# matched against server-side allowlist) alongside a canonical `query` string. Both are
# sent as separate request params; the two constants below are intentionally near-identical.
LEADERBOARD_DOC = """query getUserLeaderboard($key: String!) {
        user_leaderboards(key: $key) {
          lifetime {
            count
            user {
              id username profile_photo_url
              __typename
            }
            __typename
          }
          month {
            count
            user {
              id username profile_photo_url
              __typename
            }
            __typename
          }
          week {
            count
            user {
              id username profile_photo_url
              __typename
            }
            __typename
          }
        }
      }"""

LEADERBOARD_QUERY = """query getUserLeaderboard($key: String!) {
  user_leaderboards(key: $key) {
    lifetime {
      count
      user {
        id
        username
        profile_photo_url
        __typename
      }
      __typename
    }
    month {
      count
      user {
        id
        username
        profile_photo_url
        __typename
      }
      __typename
    }
    week {
      count
      user {
        id
        username
        profile_photo_url
        __typename
      }
      __typename
    }
    __typename
  }
}"""


@lru_cache(maxsize=1)
def get_web_token() -> str:
    """Extract the public OAuth token from Mapillary's web frontend.

    Fetches the app shell (with cookie consent set), finds the main JS
    bundle, and extracts the embedded client token.
    """
    session = requests.Session()
    session.cookies.set(
        "mly_cb",
        json.dumps(
            {
                "version": "1",
                "date": "2026_01_01",
                "third_party_consent": "withdrawn",
                "categories": {"content_and_media": "withdrawn"},
                "integration_controls": {"YOUTUBE": "withdrawn"},
            }
        ),
        domain="www.mapillary.com",
    )

    resp = session.get("https://www.mapillary.com/app/")
    resp.raise_for_status()

    match = re.search(r"(main\.[a-f0-9]+\.js)", resp.text)
    if not match:
        raise RuntimeError("Could not find main JS bundle in Mapillary app shell")

    js_resp = session.get(f"https://www.mapillary.com/app/{match.group(1)}")
    js_resp.raise_for_status()

    tokens = re.findall(r"MLY\|\d+\|[a-f0-9]+", js_resp.text)
    if not tokens:
        raise RuntimeError("Could not find OAuth token in Mapillary JS bundle")

    logger.debug("Extracted web token: %s...%s", tokens[0][:8], tokens[0][-6:])
    return tokens[0]


def location_search(query: str, locale: str = "en_US") -> list[dict]:
    """Search for locations by name.

    Returns a list of dicts with keys: key, coordinates, name, type.
    """
    token = get_web_token()
    resp = requests.get(
        LOCATION_SEARCH_URL,
        params={"query": query, "access_token": token, "locale": locale},
        headers={"Origin": "https://www.mapillary.com", "Referer": "https://www.mapillary.com/"},
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_leaderboard(key: str = "global") -> dict:
    """Get the leaderboard for a location key (or 'global').

    Returns a dict with keys: lifetime, month, week. Each is a list of
    dicts with keys: count, user (dict with id, username).
    """
    token = get_web_token()
    resp = requests.get(
        GRAPHQL_URL,
        params={
            "doc": LEADERBOARD_DOC,
            "query": LEADERBOARD_QUERY,
            "operationName": "getUserLeaderboard",
            "variables": json.dumps({"key": key}),
        },
        headers={
            "authorization": f"OAuth {token}",
            "content-type": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]["user_leaderboards"]


def call_with_retry(fn, *args, max_retries=3, base_delay=5.0):
    """Call fn with retries and exponential backoff.

    Stops immediately on HTTP 400 (raises SystemExit).
    Returns None if all retries are exhausted.
    """
    delay = base_delay
    for attempt in range(max_retries):
        try:
            return fn(*args)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                logger.error("Got 400, stopping.")
                raise SystemExit(1)
            logger.warning("Attempt %d/%d failed: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("All retries exhausted")
                return None
        except Exception as e:
            logger.warning("Attempt %d/%d failed: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("All retries exhausted")
                return None


def discover_users(key: str = "global") -> list[tuple[str, int]]:
    """Get (username, count) pairs from a leaderboard, sorted ascending by count.

    Convenience wrapper over get_leaderboard for the common use case.
    Uses lifetime counts.
    """
    leaderboard = get_leaderboard(key)
    return sorted(
        [(e["user"]["username"], e["count"]) for e in leaderboard["lifetime"]],
        key=lambda x: x[1],
    )
