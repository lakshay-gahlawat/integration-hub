"""
Celery application instance shared by the API process (which enqueues tasks)
and the worker process (which executes them). Using Celery + Redis lets
webhook processing and synchronization run outside the HTTP request/response
cycle, which is required so slow external API calls never block a webhook
delivery (most providers time out and disable webhooks after repeated slow
responses).
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "integration_hub",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
)
