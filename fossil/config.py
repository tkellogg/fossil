import dataclasses
import functools

import pydantic


@functools.lru_cache()
def get_config():
    import os
    import dotenv
    dotenv.load_dotenv()
    return os.environ


def headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


class Model(pydantic.BaseModel):
    name: str
    context_length: int


ALL_MODELS: dict[str, Model] = {m.name: m for m in [
    Model(name="gpt-3.5-turbo", context_length=4097),
    Model(name="text-embedding-ada-002", context_length=8191),
]}


# Required keys in either .env or environment variables
ACCESS_TOKEN = get_config()["ACCESS_TOKEN"]
OPENAI_KEY = get_config()["OPENAI_KEY"]

# Optional keys in either .env or environment variables
OPENAI_API_BASE = get_config().get("OPENAI_API_BASE", "https://api.openai.com/v1")
MASTO_API_BASE = get_config().get("MASTO_API_BASE", "https://hachyderm.io/api")
EMBEDDING_MODEL = ALL_MODELS[get_config().get("EMBEDDING_MODEL", "text-embedding-ada-002")]
SUMMARIZE_MODEL = ALL_MODELS[get_config().get("SUMMARIZE_MODEL", "gpt-3.5-turbo")]
