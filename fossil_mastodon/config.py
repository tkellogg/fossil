import atexit
import functools
import pathlib
import shutil
import tempfile
import llm

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
    Model(name="ada-002", context_length=8191),
]}

DATABASE_PATH = get_config().get("DATABASE_PATH", "fossil.db")


# Required keys in either .env or environment variables
ACCESS_TOKEN = get_config()["ACCESS_TOKEN"]
OPENAI_KEY = get_config()["OPENAI_KEY"]

# Optional keys in either .env or environment variables
OPENAI_API_BASE = get_config().get("OPENAI_API_BASE", "https://api.openai.com/v1")
MASTO_BASE = get_config().get("MASTO_BASE", "https://hachyderm.io")
EMBEDDING_MODEL = ALL_MODELS[get_config().get("EMBEDDING_MODEL", "ada-002")]
SUMMARIZE_MODEL = ALL_MODELS[get_config().get("SUMMARIZE_MODEL", "gpt-3.5-turbo")]

def get_installed_llms() -> set[str]:
    return {m.model.model_id for m in llm.get_models_with_aliases()}

def get_installed_embedding_models() -> set[str]:
    return {m.model.model_id for m in llm.get_embedding_models_with_aliases()}


# Static files
class StaticFiles(pydantic.BaseModel):
    """
    This manages static files so that the user can `pip install fossil-mastodon` and it runs
    fine. 

    This copies all files into a temp directory and then deletes them as the program exits. This 
    seems to work fine even in the dev workflow, since this module gets re-run every time
    uvicorn reloads the server.
    """
    class Config:
        arbitrary_types_allowed = True
    base_path: pathlib.Path
    assets_path: pathlib.Path
    templates_path: pathlib.Path
    temp_dir: tempfile.TemporaryDirectory

    @classmethod
    def from_env(cls) -> "StaticFiles":
        src_path = pathlib.Path(__file__).parent / "app"
        temp_dir = tempfile.TemporaryDirectory()
        dst_path = pathlib.Path(temp_dir.name)
        shutil.copytree(src_path / "static", dst_path / "static")
        shutil.copytree(src_path / "templates", dst_path / "templates")
        
        obj = cls(
            base_path=dst_path,
            assets_path=dst_path / "static",
            templates_path=dst_path / "templates",
            temp_dir=temp_dir,
        )

        atexit.register(obj.cleanup)

        return obj

    def cleanup(self):
        self.temp_dir.cleanup()

    def __del__(self):
        self.cleanup()


ASSETS = StaticFiles.from_env()