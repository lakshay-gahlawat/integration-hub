"""
Tests the fetch -> validate/normalize -> downstream action -> record
result pipeline inside the provider implementations themselves, using
respx to mock the actual GitHub/Slack HTTP calls. These are the tests the
original pass didn't have: everything else exercises the pipeline through
routers with the provider entirely mocked out, which never actually proves
the normalization logic (skipping malformed entries, etc.) works.
"""
import pytest
import respx
from httpx import Response

from app.integrations.github_provider import GitHubProvider
from app.integrations.slack_provider import SlackProvider


@pytest.mark.asyncio
async def test_github_sync_normalizes_valid_repos_and_skips_malformed_ones():
    provider = GitHubProvider()

    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://api.github.com/user/repos").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "full_name": "octocat/good-repo",
                        "private": False,
                        "updated_at": "2026-01-01T00:00:00Z",
                        "stargazers_count": 12,
                    },
                    # Missing required fields -- should be skipped, not
                    # crash the whole sync.
                    {"full_name": "octocat/malformed-repo"},
                    {
                        "full_name": "octocat/another-good-repo",
                        "private": True,
                        "updated_at": "2026-02-01T00:00:00Z",
                        "stargazers_count": 0,
                    },
                ],
            )
        )
        mock.post("https://api.github.com/gists").mock(
            return_value=Response(200, json={"html_url": "https://gist.github.com/abc123"})
        )

        result = await provider.run_sync("fake-token")

    assert result["repo_count"] == 2
    assert set(result["repos"]) == {"octocat/good-repo", "octocat/another-good-repo"}
    assert result["skipped_invalid_entries"] == 1
    assert result["sync_log_gist_url"] == "https://gist.github.com/abc123"


@pytest.mark.asyncio
async def test_github_sync_raises_non_retryable_on_401():
    from app.integrations.base import ProviderAPIError

    provider = GitHubProvider()
    with respx.mock:
        respx.get("https://api.github.com/user/repos").mock(return_value=Response(401, json={}))

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.run_sync("revoked-token")

    assert exc_info.value.retryable is False
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_slack_sync_normalizes_channels_and_posts_summary():
    provider = SlackProvider()

    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://slack.com/api/conversations.list").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [
                        {"id": "C001", "name": "general", "is_private": False, "num_members": 10},
                        # Missing required "id" -- should be skipped.
                        {"name": "broken-channel"},
                    ],
                },
            )
        )
        mock.post("https://slack.com/api/chat.postMessage").mock(
            return_value=Response(200, json={"ok": True})
        )

        result = await provider.run_sync("fake-bot-token")

    assert result["channel_count"] == 1
    assert result["channels"] == ["general"]
    assert result["skipped_invalid_entries"] == 1
    assert result["demo_message"] == {"posted": True, "channel": "general"}


@pytest.mark.asyncio
async def test_slack_sync_handles_post_message_failure_without_failing_sync():
    """The bot not being in the target channel is a common, non-fatal
    condition -- the sync should still report success with the read half
    of the data, rather than treating a failed demo message as a hard
    sync failure."""
    provider = SlackProvider()

    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://slack.com/api/conversations.list").mock(
            return_value=Response(
                200, json={"ok": True, "channels": [{"id": "C001", "name": "general"}]}
            )
        )
        mock.post("https://slack.com/api/chat.postMessage").mock(
            return_value=Response(200, json={"ok": False, "error": "not_in_channel"})
        )

        result = await provider.run_sync("fake-bot-token")

    assert result["channel_count"] == 1
    assert result["demo_message"] == {"posted": False, "reason": "not_in_channel"}
