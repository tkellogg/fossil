import atexit
import json
import os
import pathlib
import random
import shutil
import sqlite3
import string
from collections import defaultdict

import llm
import pydantic
from dotenv import dotenv_values


def get_config_var(var_name: str, default):
    return dotenv_values().get(var_name, os.environ.get(var_name, default))

class Model(pydantic.BaseModel):
    name: str
    context_length: int

class _ConfigValueNotFound():
    pass

ConfigValueNotFound = _ConfigValueNotFound()

class _ConfigHandler():
    # Default fallbacks for variables defined in either .env or environment
    _config_var_defaults = {
        "DATABASE_PATH": "fossil.db",
        "OPENAI_KEY": "",
        "OPENAI_API_BASE": "https://api.openai.com/v1",
        "MASTO_BASE": "https://hachyderm.io",
    }
    
    _model_lengths = defaultdict(
        lambda: 2048, 
        {"gpt-3.5-turbo": 4097, "ada-002": 8191}
    )
    
    _model_cache = {}
    
    def __getattr__(self, item: str):
        c_val = get_config_var(item, self._config_var_defaults.get(item, ConfigValueNotFound))
        
        if isinstance(c_val, _ConfigValueNotFound):
            raise AttributeError(f"{item} is not defined in either the enviroment or .env file")
        return c_val

    def _get_from_session(self, session_id: str| None, item: str) -> str:
        if not session_id:
            return ""
        with sqlite3.connect(self.DATABASE_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT settings FROM sessions WHERE id = ?', [session_id])
            row = c.fetchone()
            try:
                return json.loads(row[0]).get(item, "")
            except (json.decoder.JSONDecodeError, IndexError, TypeError):
                return ""
    
    def EMBEDDING_MODEL(self, session_id: str|None = None) -> Model:
        c_val = self._get_from_session(session_id, "embedding_model")
        if not c_val:
            c_val = get_config_var("EMBEDDING_MODEL", "ada-002")
        
        if c_val not in self._model_cache:
            self._model_cache[c_val] = Model(name=c_val, context_length=self._model_lengths[c_val])
        
        return self._model_cache[c_val]
    
    def SUMMARIZE_MODEL(self, session_id: str|None = None) -> Model:
        c_val = self._get_from_session(session_id, "summarize_model")
        if not c_val:
            c_val = get_config_var("SUMMARIZE_MODEL", "gpt-3.5-turbo")
            
        if c_val not in self._model_cache:
            self._model_cache[c_val] = Model(name=c_val, context_length=self._model_lengths[c_val])
        
        return self._model_cache[c_val]


ConfigHandler = _ConfigHandler()


def headers():
    return {"Authorization": f"Bearer {ConfigHandler.ACCESS_TOKEN}"}

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

    # HACK: Alright, I admit it, this is crazy. Here's the thing: we need to use shutil.rmtree in
    # the destructor, but the destructor runs at a very weird time. I observed it running after
    # the shutil module had been unloaded, so I was getting NullType for the module. Obvs the
    # simple solution is this — make the function live longer than this object by capturing a reference.
    rmtree = shutil.rmtree

    @classmethod
    def from_env(cls) -> "StaticFiles":
        src_path = pathlib.Path(__file__).parent / "app"
        # I used to use tempfile, but MacOS deletes temp files every 3 days, so I needed to move
        # to a more permanent location.
        dst_path = pathlib.Path(os.path.expanduser(f"~/.cache/fossil-mastodon/{''.join(random.choices(string.ascii_lowercase, k=10))}"))
        dst_path.mkdir(parents=True)
        shutil.copytree(src_path / "static", dst_path / "static")
        shutil.copytree(src_path / "templates", dst_path / "templates")
        
        obj = cls(
            base_path=dst_path,
            assets_path=dst_path / "static",
            templates_path=dst_path / "templates",
        )

        atexit.register(obj.cleanup)

        return obj

    def cleanup(self):
        self.rmtree(self.assets_path.parent)

    def __del__(self):
        self.cleanup()


ASSETS = StaticFiles.from_env()