"""
The only place in the application that maps a ProviderType to a concrete
IntegrationProvider. Adding a third provider is: write NewProvider(...),
add one line here, add the enum value in app/models/enums.py -- nothing
else in routers/services/workers needs to change.
"""
from app.integrations.base import IntegrationProvider
from app.integrations.github_provider import GitHubProvider
from app.integrations.slack_provider import SlackProvider
from app.models.enums import ProviderType

_PROVIDERS: dict[ProviderType, IntegrationProvider] = {
    ProviderType.GITHUB: GitHubProvider(),
    ProviderType.SLACK: SlackProvider(),
}


def get_provider(provider_type: ProviderType) -> IntegrationProvider:
    provider = _PROVIDERS.get(provider_type)
    if provider is None:
        raise ValueError(f"No provider registered for {provider_type}")
    return provider
