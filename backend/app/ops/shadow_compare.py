"""
Shadow-mode provider comparison.

Runs one prompt through two LLM providers and reports whether they agree, how
long each took, and which failed. This is the migration's A/B check: point it
at "gemini" and "strands" to see whether the Strands runtime produces
equivalent structured output before cutting over.

Evaluation tooling only -- it reads nothing from and writes nothing to the
domain model.

    python -m app.ops.shadow_compare "Ravi will send the report by Friday."
"""
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.prompt_registry import PromptRegistry
from app.schemas.llm import ObligationProposal
from app.services.llm.provider_registry import LLMProviderRegistry

T = TypeVar("T", bound=BaseModel)


class ProviderResult(BaseModel):
    provider: str
    resolved_provider: str
    ok: bool
    latency_ms: float
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ShadowComparison(BaseModel):
    agreed: bool
    degraded: List[str] = []
    results: Dict[str, ProviderResult]


async def _run_one(provider, name: str, system_prompt: str, user_prompt: str,
                   schema_cls: Type[T]) -> ProviderResult:
    # The registry silently degrades an unconfigured provider to the mock. Record
    # who actually answered, so a comparison can never pass off mock-vs-mock as
    # agreement between two real providers.
    resolved = getattr(provider, "provider_name", name)
    started = time.perf_counter()
    try:
        out = await provider.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_cls=schema_cls,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
        return ProviderResult(
            provider=name, resolved_provider=resolved, ok=True,
            latency_ms=(time.perf_counter() - started) * 1000,
            output=out.model_dump(mode="json"),
        )
    except Exception as e:
        return ProviderResult(
            provider=name, resolved_provider=resolved, ok=False,
            latency_ms=(time.perf_counter() - started) * 1000,
            error=str(e),
        )


async def compare_providers(
    system_prompt: str,
    user_prompt: str,
    schema_cls: Type[T],
    provider_names: Sequence[str] = ("gemini", "strands"),
    provider_lookup: Optional[Callable[[str], Any]] = None,
) -> ShadowComparison:
    """Runs the same prompt through each provider concurrently and compares."""
    lookup = provider_lookup or LLMProviderRegistry.get

    results = await asyncio.gather(*[
        _run_one(lookup(name), name, system_prompt, user_prompt, schema_cls)
        for name in provider_names
    ])
    by_name = {r.provider: r for r in results}

    # A provider that degraded to the mock is not the provider you asked about, so
    # its output says nothing about the real one. Never report agreement in that case.
    degraded = [r.provider for r in results if r.resolved_provider != r.provider]

    outputs = [r.output for r in results if r.ok]
    agreed = (
        not degraded
        and len(outputs) == len(results)
        and all(o == outputs[0] for o in outputs)
    )
    return ShadowComparison(agreed=agreed, degraded=degraded, results=by_name)


async def _main(text: str) -> None:
    tmpl = PromptRegistry.get("obligation_extraction", version="v1")
    system_prompt = tmpl.system_prompt if tmpl else "Extract obligation structured proposal."
    user_prompt = tmpl.format_user_prompt(
        source_ref="shadow", sender="shadow", channel="default", text=text,
    ) if tmpl else text

    comparison = await compare_providers(system_prompt, user_prompt, ObligationProposal)

    print(f"agreed: {comparison.agreed}")
    if comparison.degraded:
        print(f"WARNING: {', '.join(comparison.degraded)} degraded to a fallback "
              f"provider (missing API key?). This comparison proves nothing about "
              f"the real providers -- do not cut over on it.")
    for name, r in comparison.results.items():
        status = "ok" if r.ok else f"FAILED ({r.error})"
        resolved = "" if r.resolved_provider == name else f" -> {r.resolved_provider}!"
        print(f"  {name:10s}{resolved:12s} {r.latency_ms:8.0f} ms  {status}")
        if r.ok:
            print(f"    {r.output}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(_main(sys.argv[1]))
