import abc
import functools
import re
import traceback
from typing import Type

from fastapi import FastAPI, Request, responses, templating
import pkg_resources
import pydantic

from fossil_mastodon import ui, core


def title_case_to_spaced(string):
    # The regex pattern looks for any lowercase letter followed by an uppercase letter
    # and inserts a space between them
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', string)


class PluginMetadata:
    """
    Base class for a plugin's metadata. This information is used to display the plugin
    on the settings page.
    """
    @classmethod
    def get_name(cls) -> str:
        return cls.__qualname__

    @classmethod
    def get_display_name(cls) -> str:
        return title_case_to_spaced(cls.get_name())

    @classmethod
    def get_description(cls) -> str:
        return cls.__doc__


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
            plugin.render_html(toot, self)
            for plugin in get_toot_display_plugins()
        )


class BaseTootDisplayPlugin(abc.ABC, PluginMetadata):
    """
    Base class for a plugin that adds buttons to the toot display.
    """
    @abc.abstractmethod
    def _get_response(self, toot: core.Toot, context: RenderContext) -> responses.Response:
        """
        Display a toot.

        :param toot: The toot to display.
        :param context: The context in which to display the toot.
        """
        raise NotImplementedError()

    def render_html(self, toot: core.Toot, context: RenderContext) -> str:
        """
        Get the HTML for this plugin's button.

        :param toot: The toot to display.
        :param context: The context in which to display the toot.
        """
        return self._get_response(toot, context).body.decode("utf-8")


@functools.lru_cache
def get_toot_display_plugins() -> list[BaseTootDisplayPlugin]:
    plugins = []
    for entry_point in pkg_resources.iter_entry_points("fossil_mastodon.toot_display_plugins"):
        try:
            algo = entry_point.load()
            if issubclass(algo, BaseTootDisplayPlugin):
                plugins.append(algo())
            else:
                print(f"Error loading toot display plugin '{entry_point.name}': not a subclass of BaseTootDisplayPlugin")
        except:
            print(f"Error loading toot display plugin {entry_point.name}")
            traceback.print_exc()
    return plugins


class BaseAPIOperationPlugin(abc.ABC, PluginMetadata):
    """
    Base class for a plugin that adds an API operation.
    """
    @abc.abstractmethod
    def add_operations(self, app: FastAPI):
        """
        Add an API operation to the app.

        :param app: The FastAPI app.
        """
        raise NotImplementedError()


@functools.lru_cache
def get_api_operation_plugins() -> list[BaseAPIOperationPlugin]:
    plugins = []
    for entry_point in pkg_resources.iter_entry_points("fossil_mastodon.api_operation_plugins"):
        try:
            algo = entry_point.load()
            if issubclass(algo, BaseAPIOperationPlugin):
                plugins.append(algo())
            else:
                print(f"Error loading API operation plugin '{entry_point.name}': not a subclass of BaseAPIOperationPlugin")
        except:
            print(f"Error loading API operation plugin {entry_point.name}")
            traceback.print_exc()
    return plugins