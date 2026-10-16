import os, json, time, hashlib, pathlib
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv()
_client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
MODEL = os.environ["LLM_MODEL"]
CACHE = pathlib.Path(".llm_cache")
CACHE.mkdir(exist_ok=True)


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMResult:
    text: str | None
    tool_calls: list[ToolCall]
    raw_message: dict  # pesan asisten apa adanya, dimasukkan lagi ke history


def _wrap(tools):  # skema internal: {"name", "description", "parameters"}
    return [{"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in tools]


def chat(system, messages, tools=None, use_cache=True) -> LLMResult:
    kwargs = dict(model=MODEL, messages=[{"role": "system", "content": system}] + messages)
    if tools:
        kwargs.update(tools=_wrap(tools), tool_choice="auto")
    key = hashlib.sha256(json.dumps(kwargs, sort_keys=True, default=str).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if use_cache and f.exists():
        msg = json.loads(f.read_text())
    else:
        for attempt in range(5):
            try:
                resp = _client.chat.completions.create(**kwargs)
                break
            except RateLimitError:
                time.sleep(5 * 2 ** attempt)
        else:
            raise RuntimeError("Kena rate limit terus. Tunggu beberapa menit atau pakai model lebih ringan.")
        msg = resp.choices[0].message.model_dump(exclude_none=True)
        f.write_text(json.dumps(msg))
    calls = [ToolCall(c["id"], c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"))
             for c in msg.get("tool_calls", [])]
    return LLMResult(msg.get("content"), calls, msg)
