from fastapi import responses

from fossil_mastodon import plugins, core


plugin = plugins.Plugin(
    name="Toot Debug Button",
    description="Adds a button to toots that prints the toot's JSON to the server's console.",
)


@plugin.api_operation.post("/plugins/toot_debug/{id}")
async def toots_debug(id: int):
    toot = core.Toot.get_by_id(id)
    if toot is not None:
        import json
        print(json.dumps(toot.orig_dict, indent=2))
    return responses.HTMLResponse("<div>💯</div>")


@plugin.toot_display_button
def get_response(toot: core.Toot, context: plugins.RenderContext) -> responses.Response:
    return responses.HTMLResponse(f"""
        <button hx-post="/plugins/toot_debug/{ toot.id }">🪲</button>
    """)