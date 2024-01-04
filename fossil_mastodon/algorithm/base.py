import abc
import datetime
import functools
import pickle
import sqlite3
import traceback
import typing

from fastapi import templating, Response, responses, Request
import pkg_resources
import pydantic

from fossil_mastodon import config, core, ui


class RenderContext(pydantic.BaseModel):
    """
    A context object for rendering a template.
    """
    class Config:
        arbitrary_types_allowed = True
    templates: templating.Jinja2Templates
    request: Request
    link_style: ui.LinkStyle
    session: core.Session

    def template_args(self) -> dict:
        return {
            "request": self.request,
            "link_style": self.link_style,
        }


class Renderable(abc.ABC):
    """
    A base class for a "shape" of data to be rendered as HTML.
    """
    @abc.abstractmethod
    def render(self, **response_args) -> Response:
        """
        Render this object as a FastAPI Response.

        :param response_args: Additional arguments to pass to the Response constructor.
        """
        raise NotImplementedError()


class TrainContext(pydantic.BaseModel):
    """
    A context object for training a model. This is passed to train().
    """
    end_time: datetime.datetime
    timedelta: datetime.timedelta

    def get_toots(self) -> list[core.Toot]:
        return core.Toot.get_toots_since(self.end_time - self.timedelta)

    def sqlite_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(config.DATABASE_PATH)


class BaseAlgorithm(abc.ABC):
    """
    Base class for an algorithms that render your timeline. You should implemnet
    this class to create your own algorithm.

    Abstract methods:
    - render: Run the model
    - train: Train the model

    Additionally, you may want to override this method to provide a custom UI for
    your algorithm:

    - render_model_params

    Note that objects of this class must be serializable, via pickle. However, you
    can control how serialization works by overriding these methods:

    - serialize
    - deserialize
    """
    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @classmethod
    def get_display_name(cls) -> str:
        return cls.get_name()

    @abc.abstractmethod
    def render(self, toots: list[core.Toot], context: RenderContext) -> Renderable:
        """
        Run the model and return a Renderable object. This object is typically
        deserialized before this method is called.

        :param toots: The toots to run the model on. This is typically 1 day of toots,
            or 6 hours, or whatever the user (you) has selected.

        :param context: A RenderContext object that you can use to render HTML. This
            is generally just passed to the Renderable object you return.
        """
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def train(cls, context: TrainContext, http_args: dict[str, str]) -> "BaseAlgorithm":
        """
        Create an instance of this algorithm, and train it on the given toots.

        :param context: Context object where training data can be obtained.
        """
        raise NotImplementedError()

    @classmethod
    def render_model_params(cls, context: RenderContext) -> Response:
        """
        Optionally, you can render HTML input elements that capture http_args passed 
        to train(). This is useful if your agorithm has hyperparameters that you want
        to experiment with.
        """
        return responses.HTMLResponse("")

    def serialize(self) -> bytes:
        return pickle.dumps(self)
    
    @staticmethod
    def deserialize(data: bytes) -> "BaseAlgorithm":
        return pickle.loads(data)


@functools.lru_cache
def get_algorithms() -> list[typing.Type[BaseAlgorithm]]:
    """
    Load all algorithms from the fossil_mastodon.algorithm package.
    """
    algorithms = []
    for entry_point in pkg_resources.iter_entry_points("fossil_mastodon.algorithms"):
        try:
            algo = entry_point.load()
            if issubclass(algo, BaseAlgorithm):
                algorithms.append(algo)
            else:
                print(f"Error loading algorithm {entry_point.name}: not a subclass of BaseAlgorithm")
        except:
            print(f"Error loading algorithm {entry_point.name}")
            traceback.print_exc()
    return algorithms