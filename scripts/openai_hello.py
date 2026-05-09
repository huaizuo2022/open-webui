from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from openai import OpenAI
from openai import APIStatusError


DEFAULT_PROMPT = "Reply with exactly: hello"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal OpenAI-compatible hello-world connectivity check."
    )
    parser.add_argument("--base-url", dest="base_url")
    parser.add_argument("--api-key", dest="api_key")
    parser.add_argument("--model")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=32)
    parser.add_argument(
        "--list-models-only",
        action="store_true",
        help="Only fetch and print the remote model list.",
    )
    return parser


def resolve_settings(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url or os.environ.get("OPENAI_COMPAT_BASE_URL") or os.environ.get("OPENAI_API_BASE_URL")
    api_key = args.api_key or os.environ.get("OPENAI_COMPAT_API_KEY") or os.environ.get("OPENAI_API_KEY")
    model = args.model or os.environ.get("OPENAI_COMPAT_MODEL") or os.environ.get("OPENAI_MODEL")

    if not base_url:
        raise SystemExit(
            "Missing base URL. Set OPENAI_COMPAT_BASE_URL or pass --base-url."
        )
    if not api_key:
        raise SystemExit(
            "Missing API key. Set OPENAI_COMPAT_API_KEY or pass --api-key."
        )

    return {
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "model": model,
    }


def pick_default_model(model_ids: list[str]) -> str | None:
    if not model_ids:
        return None

    for candidate in model_ids:
        lowered = candidate.lower()
        if lowered.startswith("gpt") or "gpt-" in lowered:
            return candidate

    return model_ids[0]


def extract_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    data = response.model_dump() if hasattr(response, "model_dump") else response
    output = data.get("output", []) if isinstance(data, dict) else []
    parts: list[str] = []

    for item in output:
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])

    return "\n".join(parts).strip()


def extract_chat_text(response: Any) -> str:
    data = response.model_dump() if hasattr(response, "model_dump") else response
    choices = data.get("choices", []) if isinstance(data, dict) else []
    parts: list[str] = []

    for choice in choices:
        message = choice.get("message", {})
        content = message.get("content")

        if isinstance(content, str) and content.strip():
            parts.append(content.strip())
        elif isinstance(content, list):
            for item in content:
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]).strip())

    return "\n".join(part for part in parts if part)


def call_responses_api(client: OpenAI, selected_model: str, args: argparse.Namespace) -> tuple[str, str]:
    response = client.responses.create(
        model=selected_model,
        input=args.prompt,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
    )
    text = extract_text(response)
    raw = json.dumps(response.model_dump(), ensure_ascii=True, indent=2)
    return text, raw


def call_chat_completions_api(
    client: OpenAI, selected_model: str, args: argparse.Namespace
) -> tuple[str, str]:
    response = client.chat.completions.create(
        model=selected_model,
        messages=[{"role": "user", "content": args.prompt}],
        temperature=args.temperature,
        max_completion_tokens=args.max_output_tokens,
    )
    text = extract_chat_text(response)
    raw = json.dumps(response.model_dump(), ensure_ascii=True, indent=2)
    return text, raw


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = resolve_settings(args)

    client = OpenAI(
        api_key=settings["api_key"],
        base_url=settings["base_url"],
    )

    models_response = client.models.list()
    model_ids = [model.id for model in models_response.data]
    selected_model = settings["model"] or pick_default_model(model_ids)

    print(
        json.dumps(
            {
                "base_url": settings["base_url"],
                "model_count": len(model_ids),
                "selected_model": selected_model,
                "models": model_ids,
            },
            ensure_ascii=True,
            indent=2,
        )
    )

    if args.list_models_only:
        return 0

    if not selected_model:
        raise SystemExit("No remote models available to test.")

    text = ""
    raw = ""
    used_api = "responses"

    try:
        text, raw = call_responses_api(client, selected_model, args)
        if not text:
            used_api = "chat.completions"
            text, raw = call_chat_completions_api(client, selected_model, args)
    except APIStatusError:
        used_api = "chat.completions"
        text, raw = call_chat_completions_api(client, selected_model, args)

    print(f"--- api ---\n{used_api}")
    print("--- response ---")
    print(text)
    if not text:
        print("--- raw ---")
        print(raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
