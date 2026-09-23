from __future__ import annotations

import concurrent.futures
import logging
import time
from typing import TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from backend.core.exceptions import AgentForgeException, LLMError
from backend.core.run_context import LLMCallInfo, record_llm_call
from backend.llms.model_registry import ModelRegistry
from backend.services.tracing_service import TracingService


logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMService:
    def __init__(
        self,
        model_registry: ModelRegistry,
        *,
        tracing_service: TracingService | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.tracing_service = tracing_service or TracingService.disabled()

    def invoke(
        self,
        *,
        model_role: str,
        prompt: str,
        context: str,
        response_schema: type[SchemaT] | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        extra_messages: list[BaseMessage] | None = None,
    ) -> AIMessage | SchemaT:

        logger.debug("Invoking model for role '%s'", model_role)

        messages = self._build_messages(
            prompt=prompt,
            context=context,
            extra_messages=extra_messages,
        )

        role_config = getattr(self.model_registry, "config", {}).get(model_role, {})
        candidates = [role_config, *self.model_registry.get_fallback_configs(model_role)]

        failures: list[str] = []
        runnable_candidates: list[tuple[dict, BaseChatModel]] = []

        for candidate_config in candidates:
            provider = candidate_config.get("provider")
            model_name = candidate_config.get("model")

            try:
                model = self._build_model(candidate_config, model_role)
            except AgentForgeException as error:
                failures.append(f"{provider}/{model_name}: {error}")
                continue

            if response_schema is not None:
                model = model.with_structured_output(response_schema)

            if tools:
                try:
                    bind_kwargs = {"tool_choice": tool_choice} if tool_choice is not None else {}
                    model = model.bind_tools(tools, **bind_kwargs)
                except Exception as error:
                    raise LLMError(
                        f"Model for role '{model_role}' does not support tool calling: {error}",
                        details={"model_role": model_role},
                    ) from error

            runnable_candidates.append((candidate_config, model))

        if not runnable_candidates:
            raise LLMError(
                f"LLM invocation failed for role '{model_role}': no candidate model could be "
                f"built. " + " | ".join(failures),
                details={"model_role": model_role},
            )

        # Race every candidate provider concurrently and take whichever
        # responds first -- bounded by the single slowest timeout instead of
        # the sum of every provider's timeout, the way sequential fallback was.
        started_at = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(runnable_candidates)) as executor:
            future_to_candidate = {
                executor.submit(model.invoke, messages): (config, model)
                for config, model in runnable_candidates
            }

            response = None
            winning_config: dict | None = None

            try:
                for future in concurrent.futures.as_completed(future_to_candidate):
                    config, _model = future_to_candidate[future]
                    provider = config.get("provider")
                    model_name = config.get("model")

                    try:
                        response = future.result()

                        if response_schema is None:
                            _normalize_message_content(response)

                        winning_config = config
                        break

                    except Exception as error:
                        logger.warning(
                            "Candidate %s/%s lost the race for role '%s': %s",
                            provider, model_name, model_role, error,
                        )
                        failures.append(f"{provider}/{model_name}: {error}")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        if response is None or winning_config is None:
            raise LLMError(
                f"LLM invocation failed for role '{model_role}' on all "
                f"{len(runnable_candidates)} candidate model(s): " + " | ".join(failures),
                details={"model_role": model_role},
            )

        provider = winning_config.get("provider")
        model_name = winning_config.get("model")

        if len(runnable_candidates) > 1:
            logger.info(
                "Role '%s' won the race via %s/%s (%d candidate(s) raced)",
                model_role, provider, model_name, len(runnable_candidates),
            )

        with self.tracing_service.trace(
            f"llm:{model_role}",
            run_type="llm",
            tags=[tag for tag in (f"agent:{model_role}", f"provider:{provider}" if provider else None) if tag],
            metadata={
                "agent": model_role,
                "model_role": model_role,
                "provider": provider,
                "model": model_name,
                "prompt_chars": len(prompt) + len(context),
                "candidates_raced": len(runnable_candidates),
            },
        ) as run:
            self.tracing_service.set_outputs(
                run,
                {
                    "completion_chars": _content_length(response),
                    "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )

        record_llm_call(
            _llm_call_info(
                response,
                provider=provider,
                model=model_name,
                prompt_characters=len(prompt) + len(context),
            )
        )

        return response

    def _build_model(
        self,
        model_config: dict,
        model_role: str,
    ) -> BaseChatModel:
        try:
            return self.model_registry.build_model(model_config, role=model_role)

        except AgentForgeException:
            raise

        except Exception as error:
            raise LLMError(
                f"Failed to load model for role '{model_role}': {error}",
                details={"model_role": model_role},
            ) from error

    @staticmethod
    def _build_messages(
        *,
        prompt: str,
        context: str,
        extra_messages: list[BaseMessage] | None = None,
    ) -> list[BaseMessage]:
        messages: list[BaseMessage] = [
            SystemMessage(content=prompt),
            HumanMessage(content=context),
        ]

        if extra_messages:
            messages.extend(extra_messages)

        return messages


def _normalize_message_content(response: object) -> None:

    content = getattr(response, "content", None)

    if not isinstance(content, list):
        return

    parts: list[str] = []

    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])

    response.content = "".join(parts)


def _content_length(response: object) -> int:

    content = getattr(response, "content", None)

    return len(str(content if content is not None else response))


def _llm_call_info(
    response: object,
    *,
    provider: str | None,
    model: str | None,
    prompt_characters: int,
) -> LLMCallInfo:

    usage = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}

    return LLMCallInfo(
        provider=provider,
        model=model,
        provider_request_id=response_metadata.get("id"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        prompt_characters=prompt_characters,
        response_characters=_content_length(response),
    )
