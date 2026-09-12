"""
Pydantic models the sync flow validates raw provider responses against
before anything downstream touches them.

Why this exists, concretely: GitHub and Slack's APIs are large, loosely
typed JSON blobs. Blindly trusting `response.json()` and indexing into it
(as the sync flow did before this pass) means a provider changing a field
name, returning a null where a string was expected, or including a
malformed entry in a list silently produces garbage in the sync result --
or crashes the whole sync over one bad record. Validating against an
explicit shape here means:

- malformed entries are skipped and logged individually rather than
  failing the entire sync
- the summary stored on the SyncJob is a normalized, typed shape, not a
  pass-through of whatever the provider happened to send
- if a provider's response shape changes in a way that matters, it fails
  loudly at the validation boundary instead of quietly downstream
"""
from datetime import datetime

from pydantic import BaseModel, Field


class GitHubRepoSummary(BaseModel):
    full_name: str
    private: bool
    updated_at: datetime
    stargazers_count: int = Field(ge=0)


class SlackChannelSummary(BaseModel):
    id: str
    name: str
    is_private: bool = False
    num_members: int | None = None
