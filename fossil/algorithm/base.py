import abc
import pickle

from fastapi import templating, Response, responses, Request
import pydantic

from fossil import core, ui


class RenderContext(pydantic.BaseModel):
    class Config:
        arbitrary_types_allowed = True
    templates: templating.Jinja2Templates
    request: Request
    link_style: ui.LinkStyle


class BaseAlgorithm(abc.ABC):
    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @abc.abstractmethod
    def render(self, toots: list[core.Toot], context: RenderContext) -> Response:
        ...

    @classmethod
    @abc.abstractmethod
    def train(cls, toots: list[core.Toot], args: dict[str, str]) -> "BaseAlgorithm":
        ...

    def render_model_params(self, context: RenderContext) -> Response:
        return responses.HTMLResponse("")

    def serialize(self) -> bytes:
        return pickle.dumps(self)
    
    @staticmethod
    def deserialize(data: bytes) -> "BaseAlgorithm":
        return pickle.loads(data)