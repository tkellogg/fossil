"""
A FastAPI HTML server.

The streamlit version had issues around state management and was genrally slow
and inflexible. This gives us a lot more control.
"""
import datetime
import re
from typing import Annotated
from fastapi import FastAPI, Form, responses, staticfiles, templating, Request
import pydantic

from fossil import core, ui, science
from fossil import algorithm
from fossil.algorithm import topic_cluster


app = FastAPI()


app.mount("/static", staticfiles.StaticFiles(directory="app/static"), name="static")
templates = templating.Jinja2Templates(directory="app/templates")
templates.env.filters["rel_date"] = ui.time_ago


@app.middleware("http")
async def session_middleware(request: Request, call_next):
    session_id = request.cookies.get("fossil_session_id")
    session = core.Session.get_by_id(session_id) if session_id else None
    if session is None:
        session = core.Session.create()
        session.save()
        request.state.session = session
        response = await call_next(request)
        response.set_cookie("fossil_session_id", session.id)  
        return response
    else:
        request.state.session = session
        return await call_next(request)


@app.get("/")
async def root(request: Request):
    ctx = algorithm.RenderContext(
        templates=templates,
        request=request,
        link_style=ui.LinkStyle("Desktop"),
    )
    return templates.TemplateResponse("index.html", {
        "request": request,
        "model_params": topic_cluster.TopicCluster.render_model_params(ctx).body.decode("utf-8"),
    })


@app.get("/toots")
async def toots():
    return staticfiles.FileResponse("public/toots.html")


@app.post("/toots/download")
async def toots_download(request: Request):
    core.create_database()
    core.download_timeline(datetime.datetime.utcnow() - datetime.timedelta(days=1))
    return responses.HTMLResponse("<div>Load More</div>")


def timedelta(time_span: str) -> datetime.timedelta:
    hour_pattern = re.compile(r"(\d+)h")
    day_pattern = re.compile(r"(\d+)d")
    week_pattern = re.compile(r"(\d+)w")
    if m := hour_pattern.match(time_span):
        return datetime.timedelta(hours=int(m.group(1)))
    elif m := day_pattern.match(time_span):
        return datetime.timedelta(days=int(m.group(1)))
    elif m := week_pattern.match(time_span):
        return datetime.timedelta(weeks=int(m.group(1)))
    raise ValueError("Invalid time frame")


@app.post("/toots/train")
async def toots_train(
    link_style: Annotated[str, Form()],
    time_span: Annotated[str, Form()],
    request: Request,
):
    toots = core.Toot.get_toots_since(datetime.datetime.utcnow() - timedelta(time_span))

    algo_kwargs = {k: v for k, v in dict((await request.form())).items() 
                   if k not in {"link_style", "time_span"}}
    print("Algorithm kwargs:", algo_kwargs)

    # train
    session: core.Session = request.state.session
    model = topic_cluster.TopicCluster.train(toots, algo_kwargs)
    session.algorithm = model.serialize()

    # render
    return model.render(toots, algorithm.RenderContext(
        templates=templates,
        request=request,
        link_style=ui.LinkStyle(link_style),
    ))


@app.post("/toots/{id}/debug")
async def toots_debug(id: int):
    toot = core.Toot.get_by_id(id)
    if toot is not None:
        import json
        print(json.dumps(toot.orig_dict, indent=2))
    return responses.JSONResponse({"data": "ok."})