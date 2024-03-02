import abc
import contextlib
import functools
import inspect
import logging
import pathlib
import re
import sys
import traceback
from typing import Callable, Type, TYPE_CHECKING

from fastapi import FastAPI, Request, responses, templating
import pkg_resources
import pydantic

from fossil_mastodon import algorithm, config, ui, core

if TYPE_CHECKING:
    from fossil_mastodon import server


logger = logging.getLogger(__name__)


def title_case_to_spaced(string):
    # The regex pattern looks for any lowercase letter followed by an uppercase letter
    # and inserts a space between them
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', string)


TootDisplayFn = Callable[[core.Toot, "RenderContext"], responses.Response]
class TootDisplayPlugin(pydantic.BaseModel):
    fn: TootDisplayFn
    fn_name: str

    def render_str(self, toot: core.Toot, context: "RenderContext") -> str:
        obj = self.fn(toot, context)
        content = obj.body.decode("utf-8")
        return content


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
            "ctx": self,
        }

    def render_toot_display_plugins(self, toot: core.Toot) -> str:
        return "".join(
            plugin.render_str(toot, self)
            for plugin in get_toot_display_plugins()
        )


_app: FastAPI | None = None


class Plugin(pydantic.BaseModel):
    """
    Plugin registration API
    
    Example:

        plugin = Plugin(name="My Plugin", description="Add button to toot that triggers an API POST operation")

        @plugin.api_operation.post("/my_plugin")
        def my_plugin(request: Request):
            return responses.HTMLResponse("<div>💯</div>")

        @plugin.toot_display_button
        def my_toot_display(toot: core.Toot, context: RenderContext):
            return responses.HTMLResponse("<div>💯</div>")

    """
    name: str
    display_name: str | None = None
    description: str | None = None
    author: str | None = None
    author_url: str | None = None
    enabled_by_default: bool = True
    _toot_display_buttons: list[TootDisplayPlugin] = pydantic.PrivateAttr(default_factory=list)
    _algorithms: list[Type[algorithm.BaseAlgorithm]] = pydantic.PrivateAttr(default_factory=list)
    _lifecycle_hooks: list[callable] = pydantic.PrivateAttr(default_factory=list)
    _menu_items: list[str] = pydantic.PrivateAttr(default_factory=list)
    _head_html: list[str] = pydantic.PrivateAttr(default_factory=list)

    @pydantic.validator("display_name", always=True)
    def _set_display_name(cls, v, values):
        return v or values["name"]

    @property
    def api_operation(self) -> FastAPI:
        assert _app is not None
        return _app

    @property
    def TemplateResponse(self) -> Type["server.templates.TemplateResponse"]:
        from fossil_mastodon import server
        return server.templates.TemplateResponse

    def toot_display_button(self, impl: TootDisplayFn) -> TootDisplayFn:
        """
        Decorator for adding a button to the toot display UI. This function should return a
        fastapi.responses.Response object. The result will be extracted and inserted into the
        toot display UI.
        """
        name = impl.__name__

        @functools.wraps(impl)
        def wrapper(toot: core.Toot, context: RenderContext):
            try:
                return impl(toot, context)
            except TypeError as e:
                raise BadPluginFunction(self, impl, "example_function(toot: fossil_mastodon.core.Toot, context: fossil_mastodon.plugins.RenderContext)") from e
            except Exception as e:
                import inspect
                print(inspect.signature(impl))
                raise RuntimeError(f"Error in toot display plugin '{self.name}', function '{name}'") from e

        self._toot_display_buttons.append(TootDisplayPlugin(fn=wrapper, fn_name=name))
        return wrapper

    def algorithm(self, algo: Type[algorithm.BaseAlgorithm]) -> Type[algorithm.BaseAlgorithm]:
        """
        Decorator for adding an algorithm class.
        """
        if not issubclass(algo, algorithm.BaseAlgorithm):
            raise ValueError(f"Algorithm {algo} is not a subclass of algorithm.BaseAlgorithm")
        self._algorithms.append(algo)
        algo.plugin = self
        return algo

    def lifecycle_hook(self, fn: callable) -> callable:
        """
        Decorator for adding a lifecycle hook. Lifecycle hooks are called when the server starts
        up, and can be used to perform initialization tasks.
        """
        self._lifecycle_hooks.append(fn)
        return fn

    def add_templates_dir(self, path: pathlib.Path):
        """
        Add a directory of templates to the plugin. These will be accessible from FastAPI response
        objects. For example, if you add a directory of templates at `<path>/templates`, then you
        can return a template from a FastAPI route like this:

            @plugin.api_operation.get("/my_route")
            def my_route():
                return plugin.TemplateResponse("my_template.html", {"request": request})
        """
        config.ASSETS.add_dir(path, "templates")

    def add_static_dir(self, path: pathlib.Path):
        """
        Add a directory of static files to the plugin. These will be downloadable by the browser at
        the path `GET /static/example.css`, assuming the example.css exists at `<path>/example.css`
        as a local path.
        """
        config.ASSETS.add_dir(path, "static")

    def add_menu_item(self, raw_html: str):
        self._menu_items.append(raw_html)

    def add_head_html(self, raw_html: str):
        self._head_html.append(raw_html)


def init_plugins(app: FastAPI):
    global _app
    _app = app
    get_plugins()


@functools.lru_cache
def get_plugins() -> list[Plugin]:
    if _app is None:
        raise RuntimeError("Plugins not initialized")

    plugins = []
    for entry_point in pkg_resources.iter_entry_points("fossil_mastodon.plugins"):
        print("Loading plugin", entry_point.name)
        try:
            plugin = entry_point.load()
            if isinstance(plugin, Plugin):
                plugins.append(plugin)
            else:
                print(f"Error loading toot display plugin '{entry_point.name}': not a subclass of Plugin")
        except:
            print(f"Error loading toot display plugin {entry_point.name}")
            traceback.print_exc()
    return plugins


def get_toot_display_plugins() -> list[TootDisplayPlugin]:
    return [
        b 
        for p in get_plugins() 
        for b in p._toot_display_buttons
    ]


def get_algorithms() -> list[Type[algorithm.BaseAlgorithm]]:
    return [
        algo
        for p in get_plugins()
        for algo in p._algorithms
    ]


def get_menu_items() -> list[str]:
    return [
        algo
        for p in get_plugins()
        for algo in p._menu_items
    ]


def get_head_html() -> list[str]:
    return [
        algo
        for p in get_plugins()
        for algo in p._head_html
    ]


def get_lifecycle_hooks() -> list[callable]:
    return [
        contextlib.contextmanager(hook)
        for p in get_plugins()
        for hook in p._lifecycle_hooks
    ]

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    hooks = get_lifecycle_hooks()

    objects = []
    for hook in hooks:
        try:
            obj = hook(app)
            obj.__enter__()
            objects.append(obj)
        except:
            logger.exception(f"Error running lifecycle hook {hook}")

    yield

    exc_info = sys.exc_info()
    exc = exc_info[1] if exc_info else None
    exc_type = exc_info[0] if exc_info else None
    tb = exc_info[2] if exc_info else None
    for obj in objects:
        try:
            obj.__exit__(exc_type, exc, tb)
        except:
            logger.exception(f"Error running lifecycle hook {hook}")


class BadPluginFunction(Exception):
    def __init__(self, plugin: Plugin, function: callable, expected_signature: str):
        super().__init__(f"Bad function call: {plugin.name}.{function.__name__} should have signature {expected_signature}")
        self.plugin = plugin
        self.function = function
        self.signature = inspect.signature(function)
        self.expected_signature = expected_signature
        self.function_name = function.__name__
