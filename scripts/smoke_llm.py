import os, sys, json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
    if not os.getenv(k):
        sys.exit(f"{k} belum diisi di file .env")

client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
model = os.environ["LLM_MODEL"]
print("Model:", model)

r = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "What is 2+2? Answer in one word."}],
)
print("Tes 1:", r.choices[0].message.content)

tools = [{"type": "function", "function": {
    "name": "echo", "description": "Echo text back.",
    "parameters": {"type": "object",
                   "properties": {"text": {"type": "string"}},
                   "required": ["text"]}}}]
r = client.chat.completions.create(
    model=model, tools=tools, tool_choice="auto",
    messages=[{"role": "user", "content": "Use the echo tool with text 'hello'."}],
)
calls = r.choices[0].message.tool_calls or []
print("Tes 2:", [(c.function.name, json.loads(c.function.arguments)) for c in calls])
print("OK" if calls else "Tool call tidak muncul")
