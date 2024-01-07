"""
A FastAPI HTML server.

The streamlit version had issues around state management and was genrally slow
and inflexible. This gives us a lot more control.
"""
import datetime
import importlib
import json
from typing import Annotated
from fastapi import FastAPI, Form, responses, staticfiles, templating, Request, HTTPException
import llm
import requests


from fossil_mastodon import config, core, ui, algorithm


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
    session: core.Session = request.state.session
    ctx = algorithm.RenderContext(
        templates=templates,
        request=request,
        link_style=ui.LinkStyle("Desktop"),
        session=session,
    )
    algo = session.get_algorithm_type() or algorithm.get_algorithms()[0]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "model_params": algo.render_model_params(ctx).body.decode("utf-8"),
        "ui_settings": session.get_ui_settings(),
        "selected_algorithm": algo,
        "algorithms": [
            {"name": algo.get_name(), "display_name": algo.get_display_name()}
            for algo in algorithm.get_algorithms()
        ],
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
    algo = session.get_algorithm_type() or algorithm.get_algorithms()[0]
    model = algo.train(context, algo_kwargs)
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


@app.get("/algorithm/{name}/form")
async def algorithm_form(name: str, request: Request):
    session: core.Session = request.state.session
    algo_type = session.get_algorithm_type() or algorithm.get_algorithms()[0]
    ctx = algorithm.RenderContext(
        templates=templates,
        request=request,
        link_style=ui.LinkStyle(session.get_ui_settings().get("link_style", "Desktop")),
        session=session,
    )
    return algo_type.render_model_params(ctx)


@app.get("/settings")
async def get_settings(request: Request):
    session: core.Session = request.state.session
    keys = {"openai": "", **llm.load_keys()}
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": session.settings,
        "embedding_models": config.get_installed_embedding_models(),
        "embedding_model": session.settings.embedding_model,
        "summarize_models": config.get_installed_llms(),
        "summarize_model": session.settings.summarize_model,
        "keys": keys,
    })

@app.post("/settings")
async def post_settings(settings: core.Settings, request: Request):
    session: core.Session = request.state.session
    session.settings = settings
    session.save()
    return responses.HTMLResponse("<div>👍</div>")

@app.post("/keys")
async def post_keys(request: Request):
    body_params: dict[str, str] = dict((await request.form()))
    key_path = llm.user_dir() / "keys.json"
    key_path.write_text(json.dumps(body_params))
    return responses.HTMLResponse("<div>👍</div>")


@app.post("/toots/{id}/debug")
async def toots_debug(id: int):
    toot = core.Toot.get_by_id(id)
    if toot is not None:
        import json
        print(json.dumps(toot.orig_dict, indent=2))
    return responses.HTMLResponse("<div>💯</div>")

@app.post("/toots/{id}/boost")
async def toots_boost(id: int):
    toot = core.Toot.get_by_id(id)
    if toot is not None:
        from fossil_mastodon.config import MASTO_BASE, headers
        url = f'{MASTO_BASE}/api/v1/statuses/{toot.toot_id}/reblog'
        data = {
            'visibility': 'public'
        }
        response = requests.post(url, json=data, headers=headers())
        try:
            response.raise_for_status()
            return responses.HTMLResponse("<div>🚀</div>")
        except:
            print("ERROR:", response.json())
            raise
    raise HTTPException(status_code=404, detail="Toot not found")
    