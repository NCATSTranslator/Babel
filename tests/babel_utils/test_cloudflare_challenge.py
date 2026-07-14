"""Unit tests for detecting a Cloudflare bot-challenge response during download.

HMDB (and possibly other sources later) now fronts its download URL with a Cloudflare
challenge page instead of a plain 403 -- see docs at
https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/.
Retrying or changing the User-Agent doesn't help, so `pull_via_urllib` must recognize this
specific case (via the `cf-mitigated: challenge` response header) and fail immediately with
an actionable message, instead of burning through its retry budget on a URL that will never
succeed automatically.
"""

import io
import urllib.error

import pytest

from src.babel_utils import raise_if_cloudflare_challenge


def _http_error(headers: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.com/file.zip",
        code=403,
        msg="Forbidden",
        hdrs=headers,
        fp=io.BytesIO(b""),
    )


@pytest.mark.unit
def test_cloudflare_challenge_raises_actionable_error():
    """A 403 with `cf-mitigated: challenge` should raise a RuntimeError naming the URL and local path."""
    error = _http_error({"cf-mitigated": "challenge"})

    with pytest.raises(RuntimeError, match="Cloudflare bot challenge"):
        raise_if_cloudflare_challenge("https://example.com/file.zip", "/downloads/SOURCE/file.zip", error)


@pytest.mark.unit
def test_plain_403_is_not_treated_as_a_challenge():
    """A regular 403 (e.g. wrong URL) without the Cloudflare header should not raise -- let it retry as before."""
    error = _http_error({})

    raise_if_cloudflare_challenge("https://example.com/file.zip", "/downloads/SOURCE/file.zip", error)
