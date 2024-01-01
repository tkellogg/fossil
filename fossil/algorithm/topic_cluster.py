from fastapi import Response, responses
import numpy as np
import openai
import pydantic
from sklearn.cluster import KMeans
import tiktoken
from fossil import config, core, ui
from fossil.algorithm import base


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
        toots = [toot for toot in toots if toot.embedding is not None]
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

        client = openai.OpenAI(api_key=config.OPENAI_KEY)
        labels: dict[int, str] = {}
        for i_clusters in range(n_clusters):
            clustered_toots = [toot for toot, cluster_label in zip(toots, cluster_labels) if cluster_label == i_clusters]
            combined_text = "\n\n".join([toot.content for toot in clustered_toots])

            # Use GPT-3.5-turbo to summarize the combined text
            prompt = f"Create a single label that describes all of these related tweets, make it succinct but descriptive. The label should describe all {len(clustered_toots)} of these\n\n{combined_text}"
            response = client.chat.completions.create(
                model=config.SUMMARIZE_MODEL.name,
                messages=[{"role": "user", "content": reduce_size(prompt)}],
                max_tokens=100,
            )
            summary = response.choices[0].message.content.strip()
            labels[i_clusters] = summary

        return cls(kmeans=kmeans, labels=labels)

    @staticmethod
    def render_model_params(context: base.RenderContext) -> Response:
        return responses.HTMLResponse("""
            <div class="slider">
                <input type="range" name="num_clusters" id="num_clusters" min="0" max="20" value="15" onchange="document.getElementById('num_clusters_value').innerHTML = this.value">
                <span><span class="slider-value" id="num_clusters_value">15</span> clusters</span>
            </div>
        """)


ENCODING = tiktoken.encoding_for_model(config.SUMMARIZE_MODEL.name)

def reduce_size(text: str, model_limit: int = config.SUMMARIZE_MODEL.context_length, est_output_size: int = 500) -> str:
    tokens = ENCODING.encode(text)
    return ENCODING.decode(tokens[:model_limit - est_output_size])


class NoopKMeans(KMeans):
    def predict(self, X, y=None, sample_weight=None):
        return np.zeros(len(X), dtype=int)
