"""Public exports and dependency injection registration for the OpenAI AI client."""

from openai_ai_client_impl.client_impl import OpenAiClient as OpenAiClient
from openai_ai_client_impl.client_impl import get_openai_client as get_openai_client
from openai_ai_client_impl.client_impl import register_openai_client as register_openai_client

register_openai_client()
