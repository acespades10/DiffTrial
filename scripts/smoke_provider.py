import argparse
import asyncio
import json
import os
from pathlib import Path

from difftrial.config import local_codex_defaults
from difftrial.providers import ProviderError, adapter
from difftrial.schemas import ProviderConfig


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".local/provider-checks.json"))
    args = parser.parse_args()
    endpoint, model = local_codex_defaults()
    configs = (
        [ProviderConfig(kind="codexlb", transport="responses", endpoint=endpoint, model=model)]
        if endpoint and model
        else []
    )
    results = []
    for config in configs:
        try:
            result = await adapter(config).check()
            results.append({"provider": config.kind, **result})
        except ProviderError as e:
            results.append({"provider": config.kind, "verified": False, "code": e.code, "message": str(e)})
    if (
        os.environ.get("OPENAI_API_KEY")
        and os.environ.get("DIFFTRIAL_COMPATIBLE_ENDPOINT")
        and os.environ.get("DIFFTRIAL_COMPATIBLE_MODEL")
    ):
        for transport in ("responses", "chat"):
            config = ProviderConfig(
                kind="compatible",
                transport=transport,
                endpoint=os.environ["DIFFTRIAL_COMPATIBLE_ENDPOINT"],
                model=os.environ["DIFFTRIAL_COMPATIBLE_MODEL"],
                key_env="OPENAI_API_KEY",
            )
            try:
                results.append({"provider": "compatible", **await adapter(config).check()})
            except ProviderError as e:
                results.append(
                    {"provider": "compatible", "transport": transport, "verified": False, "message": str(e)}
                )
    else:
        results.append(
            {
                "provider": "compatible",
                "verified": False,
                "message": "No separate endpoint, model and credential configured",
            }
        )
    try:
        config = ProviderConfig(
            kind="ollama",
            transport="ollama",
            endpoint="http://127.0.0.1:11434",
            model="discovery",
            key_env="",
        )
        models = await adapter(config).models()
        if models:
            config.model = models[0]
            results.append({"provider": "ollama", **await adapter(config).check()})
        else:
            results.append({"provider": "ollama", "verified": False, "message": "No installed models"})
    except ProviderError as e:
        results.append({"provider": "ollama", "verified": False, "message": str(e)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
