import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
HF_CHAT_MODEL = os.getenv("HF_CHAT_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")


def generate_hf_chat(messages: list[dict]) -> str:
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN is missing in the .env file")

    from huggingface_hub import InferenceClient

    client = InferenceClient(api_key=HF_TOKEN)

    response = client.chat.completions.create(
        model=HF_CHAT_MODEL,
        messages=messages,
        max_tokens=180,
    )

    return response.choices[0].message.content