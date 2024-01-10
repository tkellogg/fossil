import llm
import numpy as np
import pydantic
import tiktoken
from fastapi import Response, responses
from sklearn.cluster import KMeans
from tqdm import trange

from fossil_mastodon import config, core, ui
from fossil_mastodon.algorithm import base


class ClusterRenderer(base.Renderable, pydantic.BaseModel):
    clusters: list[ui.TootCluster]
    context: base.RenderContext

    def render(self, **response_args) -> Response:
        toot_clusters = ui.TootClusters(clusters=self.clusters)
        return self.context.templates.TemplateResponse("toot_clusters.html", {
            "clusters": toot_clusters,
            **self.context.template_args(),
        },
        **response_args)


class TopicCluster(base.BaseAlgorithm):
    def __init__(self, kmeans: KMeans, labels: dict[int, str]):
        self.kmeans = kmeans
        self.labels = labels

    def render(self, toots: list[core.Toot], context: base.RenderContext) -> ClusterRenderer:
        before = len(toots)
        toots = [toot for toot in toots if toot.embedding is not None]
        print("Removed", before - len(toots), "toots with no embedding (probably image-only).", f"{len(toots)} toots remaining.")
        cluster_indices = self.kmeans.predict(np.array([toot.embedding for toot in toots]))
        for toot, cluster_index in zip(toots, cluster_indices):
            toot.cluster = self.labels[cluster_index]

        toot_clusters = ui.TootClusters(
            clusters=[
                ui.TootCluster(
                    id=i_cluster,
                    name=cluster_label,
                    toots=[toot for toot, cluster_index in zip(toots, cluster_indices) if cluster_index == i_cluster],
                )
                for i_cluster, cluster_label in self.labels.items()
            ]
        )
        return ClusterRenderer(clusters=toot_clusters.clusters, context=context)

    @classmethod
    def train(cls, context: base.TrainContext, args: dict[str, str]) -> "TopicCluster":
        toots = [toot for toot in context.get_toots() if toot.embedding is not None]
        print("lengths:", {len(toot.embedding) for toot in toots})

        n_clusters = int(args["num_clusters"])
        if len(toots) < n_clusters:
            return cls(kmeans=NoopKMeans(n_clusters=1), labels={0: "All toots"})

        embeddings = np.array([toot.embedding for toot in toots])
        kmeans = KMeans(n_clusters=n_clusters)
        cluster_labels = kmeans.fit_predict(embeddings)

        labels: dict[int, str] = {}
        model = llm.get_model(config.ConfigHandler.SUMMARIZE_MODEL(context.session_id).name)
        for i_clusters in trange(n_clusters):
            clustered_toots = [toot for toot, cluster_label in zip(toots, cluster_labels) if cluster_label == i_clusters]
            combined_text = "\n\n".join([toot.content for toot in clustered_toots])

            # Use the summarizing model to summarize the combined text
            prompt = f"Create a single label that describes all of these related tweets, make it succinct but descriptive. The label should describe all {len(clustered_toots)} of these\n\n{combined_text}"
            summary = model.prompt(reduce_size(context.session_id, prompt)).text().strip()
            labels[i_clusters] = summary

        return cls(kmeans=kmeans, labels=labels)

    @staticmethod
    def render_model_params(context: base.RenderContext) -> Response:
        default = context.session.get_ui_settings().get("num_clusters", "15")
        return responses.HTMLResponse(f"""
            <div class="slider">
                <input type="range" name="num_clusters" id="num_clusters" min="0" max="20" value="{default}" onchange="document.getElementById('num_clusters_value').innerHTML = this.value">
                <span><span class="slider-value" id="num_clusters_value">{default}</span> clusters</span>
            </div>
        """)

def get_encoding(session_id: str):
    try:
        return tiktoken.encoding_for_model(config.ConfigHandler.SUMMARIZE_MODEL(session_id).name)
    except KeyError:
        encoding_name = tiktoken.list_encoding_names()[-1]
        return tiktoken.get_encoding(encoding_name)

def reduce_size(session_id: str, text: str, model_limit: int = -1, est_output_size: int = 500) -> str:
    if model_limit < 0:
        model_limit = config.ConfigHandler.SUMMARIZE_MODEL(session_id).context_length
    tokens = get_encoding(session_id).encode(text)
    return get_encoding(session_id).decode(tokens[:model_limit - est_output_size])


class NoopKMeans(KMeans):
    def predict(self, X, y=None, sample_weight=None):
        return np.zeros(len(X), dtype=int)
