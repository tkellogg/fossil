"""
A FastAPI HTML server.

The streamlit version had issues around state management and was genrally slow
and inflexible. This gives us a lot more control.
"""
import datetime
import importlib
import json
from typing import Annotated
from fastapi import FastAPI, Form, responses, staticfiles, templating, Request

from fossil_mastodon import config, core, ui, algorithm
from fossil_mastodon.algorithm import topic_cluster


app = FastAPI()


app.mount("/static", staticfiles.StaticFiles(directory=config.ASSETS.assets_path), name="static")
templates = templating.Jinja2Templates(directory=config.ASSETS.templates_path)
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
        session=request.state.session,
    )
    session: core.Session = request.state.session
    return templates.TemplateResponse("index.html", {
        "request": request,
        "model_params": topic_cluster.TopicCluster.render_model_params(ctx).body.decode("utf-8"),
        "ui_settings": session.get_ui_settings(),
    })


@app.get("/toots")
async def toots():
    return staticfiles.FileResponse("public/toots.html")


@app.post("/toots/download")
async def toots_download(request: Request):
    core.create_database()
    core.download_timeline(datetime.datetime.utcnow() - datetime.timedelta(days=1))
    session: core.Session = request.state.session
    algorithm_spec = json.loads(session.algorithm_spec) if session.algorithm_spec else {}
    body_params: dict[str, str] = dict((await request.form()))
    session.set_ui_settings(body_params)
    print("algorithm_spec", algorithm_spec)
    if "module" in algorithm_spec and "class_name" in algorithm_spec:
        mod = importlib.import_module(algorithm_spec["module"])
        model: algorithm.BaseAlgorithm = getattr(mod, algorithm_spec["class_name"]).train(
            algorithm.TrainContext(
                end_time=datetime.datetime.utcnow(),
                timedelta=datetime.timedelta(days=1),
            ),
            algorithm_spec["kwargs"],
        )
        timespan = ui.timedelta(body_params["time_span"])
        timeline = core.Toot.get_toots_since(datetime.datetime.utcnow() - timespan)
        renderable = model.render(timeline, algorithm.RenderContext(
            templates=templates,
            request=request,
            link_style=ui.LinkStyle(body_params["link_style"] if "link_style" in body_params else "Desktop"),
            session=session,
        ))
        return renderable.render()
    else:
        return responses.HTMLResponse("<div>No Toots 😥</div>")


@app.post("/toots/train")
async def toots_train(
    link_style: Annotated[str, Form()],
    time_span: Annotated[str, Form()],
    request: Request,
):
    context = algorithm.TrainContext(
        end_time=datetime.datetime.utcnow(),
        timedelta=ui.timedelta(time_span),
    )

    algo_kwargs = {k: v for k, v in dict((await request.form())).items() 
                   if k not in {"link_style", "time_span"}}
    print("Algorithm kwargs:", algo_kwargs)

    # train
    session: core.Session = request.state.session
    model = topic_cluster.TopicCluster.train(context, algo_kwargs)
    session.algorithm = model.serialize()
    session.algorithm_spec = json.dumps({
        "module": model.__class__.__module__,
        "class_name": model.__class__.__qualname__,
        "kwargs": algo_kwargs,
    })
    session.save()

    # render
    timeline = core.Toot.get_toots_since(datetime.datetime.utcnow() - ui.timedelta(time_span))
    renderable = model.render(timeline, algorithm.RenderContext(
        templates=templates,
        request=request,
        link_style=ui.LinkStyle(link_style),
        session=session,
    ))
    return renderable.render()


@app.post("/toots/{id}/debug")
async def toots_debug(id: int):
    toot = core.Toot.get_by_id(id)
    if toot is not None:
        import json
        print(json.dumps(toot.orig_dict, indent=2))
    return responses.HTMLResponse("<div>💯</div>")