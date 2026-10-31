"""CPU-only multilingual E5 INT8 model, one shared instance per worker.

Build downloads only specific public model files. Runtime is offline and no
user text is sent to Hugging Face. No deterministic/synthetic embeddings.
"""
from functools import lru_cache
import os
import threading

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

REPO = "hotchpotch/bekko-static-embedding-v1"
MODEL = "bekko-static-multilingual-int8-mrl384-v1"
DIMENSION = 384
MODEL_FILE = "onnx/model_int8_dim512.onnx"
_MODEL_LOCK = threading.Lock()


def download_public_model() -> None:
    for filename in (MODEL_FILE, "tokenizer.json"):
        hf_hub_download(repo_id=REPO, filename=filename)


class Encoder:
    def __init__(self) -> None:
        offline = os.environ.get("HF_HUB_OFFLINE") == "1"
        weights = hf_hub_download(
            repo_id=REPO, filename=MODEL_FILE, local_files_only=offline,
        )
        tokenizer_path = hf_hub_download(
            repo_id=REPO, filename="tokenizer.json", local_files_only=offline,
        )
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_truncation(max_length=512)
        # Static embedding ONNX is evaluated one short text at a time;
        # avoid padding and extra memory-heavy batch buffers.
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        # Bound startup memory: avoid CPU allocator arenas, graph optimizer
        # workspace duplication, pre-packed weights and persistent patterns.
        options.enable_cpu_mem_arena = False
        options.enable_mem_pattern = False
        options.enable_mem_reuse = False
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        options.add_session_config_entry("session.disable_prepacking", "1")
        self.session = ort.InferenceSession(
            str(weights), sess_options=options, providers=["CPUExecutionProvider"],
        )
        self.names = set(x.name for x in self.session.get_inputs())
        if not {"input_ids", "attention_mask"}.issubset(self.names):
            raise RuntimeError("Unsupported E5 model inputs")

    def encode(self, texts: list[str], mode: str) -> list[list[float]]:
        if not 1 <= len(texts) <= 8 or mode not in ("query", "passage"):
            raise ValueError("Invalid embedding batch")
        # This pretrained static retrieval model does NOT use E5 prefixes.
        # Its MRL dimensions 512 and 256 are established; 384 is an
        # intermediate 384-d truncation for the existing pgvector schema,
        # accepted only after real semantic ranking tests.
        result = []
        for text in texts:
            token = self.tokenizer.encode(text)
            ids = np.asarray([token.ids], dtype=np.int64)
            mask = np.asarray([token.attention_mask], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.names:
                feed["token_type_ids"] = np.zeros_like(ids, dtype=np.int64)
            feed = {key: val for key, val in feed.items() if key in self.names}
            if self.names - set(feed):
                raise RuntimeError("Unsupported static semantic ONNX inputs")
            with _MODEL_LOCK:
                raw = self.session.run(None, feed)[0]
            if raw.ndim == 3 and raw.shape[:2] == mask.shape:
                weight = mask[:, :, None].astype(np.float32)
                raw = (raw * weight).sum(axis=1) / np.maximum(weight.sum(axis=1), 1)
            if raw.ndim != 2 or raw.shape[0] != 1 or raw.shape[1] < DIMENSION:
                raise RuntimeError("Unexpected static semantic ONNX vector shape")
            vector = raw[0, :DIMENSION].astype(np.float32)
            length = np.linalg.norm(vector)
            if not np.isfinite(vector).all() or not np.isfinite(length) or length < 1e-8:
                raise RuntimeError("Invalid static semantic vector magnitude")
            result.append((vector / length).tolist())
        return result


@lru_cache(maxsize=1)
def get_encoder() -> Encoder:
    return Encoder()
