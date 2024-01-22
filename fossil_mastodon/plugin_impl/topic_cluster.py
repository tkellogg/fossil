import functools
import random
import sqlite3
import string
import llm
import numpy as np
import pydantic
import tiktoken
from fastapi import Response, responses
from sklearn.cluster import KMeans
from tqdm import trange

from fossil_mastodon import config, core, plugins, ui
from fossil_mastodon import algorithm


plugin = plugins.Plugin(
    name="Topic Cluster",
    description="Cluster toots by topic",
)


class ClusterRenderer(algorithm.Renderable, pydantic.BaseModel):
    clusters: list[ui.TootCluster]
    context: plugins.RenderContext

    def render(self, **response_args) -> Response:
        toot_clusters = ui.TootClusters(clusters=self.clusters)
        return self.context.templates.TemplateResponse("toot_clusters.html", {
            "clusters": toot_clusters,
            **self.context.template_args(),
        },
        **response_args)


@functools.lru_cache
def _create_table():
    with config.ConfigHandler.open_db() as conn:
        c = conn.cursor()

        # Create the toots table if it doesn't exist
        c.execute('''
            CREATE TABLE IF NOT EXISTS topic_cluster_toots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                toot_id INTEGER NOT NULL,
                model_version TEXT NOT NULL,
                cluster_id INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()


class TootModel(pydantic.BaseModel):
    """
    Cache for the cluster id of a toot. The model_version is used to invalidate the cache if 
    the model is retrained, since that would lead to an incompatible set of clusters.

    We can't store this inside the model because it's dynamic and created after the model is
    trained.
    """
    id: int | None
    toot_id: int
    model_version: str
    cluster_id: int | None

    @classmethod
    def for_toots(cls, toots: list[core.Toot], model_version: str) -> list["TootModel"]:
        _create_table()
        with config.ConfigHandler.open_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT id, toot_id, model_version, cluster_id
                FROM topic_cluster_toots
                WHERE model_version = ?
            ''', (model_version, ))
            from_db = {row[1]: cls(id=row[0], toot_id=row[1], model_version=row[2], cluster_id=row[3]) for row in c.fetchall()}
            return [
                from_db.get(
                    toot.id, 
                    cls(id=None, toot_id=toot.id, model_version=model_version, cluster_id=None),
                ) 
                for toot in toots
            ]

    def save(self):
        _create_table()
        if self.cluster_id is None:
            raise ValueError("Cannot save a toot model without a cluster_id")

        if isinstance(self.cluster_id, np.number):
            raise ValueError("cluster_id must be an int, not a numpy type")

        with config.ConfigHandler.open_db() as conn:
            c = conn.cursor()
            if self.id is None:
                c.execute('''
                    INSERT INTO topic_cluster_toots (toot_id, model_version, cluster_id)
                    VALUES (?, ?, ?)
                ''', (self.toot_id, self.model_version, self.cluster_id))
                self.id = c.lastrowid
            else:
                c.execute('''
                    UPDATE topic_cluster_toots
                    SET cluster_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (self.cluster_id, self.id))
            conn.commit()


@plugin.algorithm
class TopicCluster(algorithm.BaseAlgorithm):
    def __init__(self, kmeans: KMeans, labels: dict[int, str], model_version: str | None = None):
        self.kmeans = kmeans
        self.labels = labels
        self.model_version = model_version

    def render(self, toots: list[core.Toot], context: plugins.RenderContext) -> ClusterRenderer:
        before = len(toots)
        toots = [toot for toot in toots if toot.embedding is not None]
        toot_models = TootModel.for_toots(toots, model_version=self.model_version)
        print("Removed", before - len(toots), "toots with no embedding (probably image-only).", f"{len(toots)} toots remaining.")
        
        # Assign clusters to the uncached toots
        unassigned = [toot for toot, toot_model in zip(toots, toot_models) if toot_model.cluster_id is None]
        if len(unassigned) > 0:
            unassigned_models = [toot_model for toot_model in toot_models if toot_model.cluster_id is None]
            cluster_indices = self.kmeans.predict(np.array([toot.embedding for toot in unassigned]))
            print(f"Assigning clusters for {len(unassigned)} toots; model_version={self.model_version}")
            for toot, cluster_index, toot_model in zip(unassigned, cluster_indices, unassigned_models):
                toot.cluster = self.labels[cluster_index]
                toot_model.cluster_id = int(cluster_index)
                toot_model.save()

        toot_clusters = ui.TootClusters(
            clusters=[
                ui.TootCluster(
                    id=i_cluster,
                    name=cluster_label,
                    toots=[toot for toot, toot_model in zip(toots, toot_models) if toot_model.cluster_id == i_cluster],
                )
                for i_cluster, cluster_label in self.labels.items()
            ]
        )
        return ClusterRenderer(clusters=toot_clusters.clusters, context=context)

    @classmethod
    def train(cls, context: algorithm.TrainContext, args: dict[str, str]) -> "TopicCluster":
        toots = [toot for toot in context.get_toots() if toot.embedding is not None]

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
            labels[int(i_clusters)] = summary

        model_version = "".join(random.choice(string.ascii_lowercase) for _ in range(12))
        return cls(kmeans=kmeans, labels=labels, model_version=model_version)

    @staticmethod
    def render_model_params(context: plugins.RenderContext) -> Response:
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
