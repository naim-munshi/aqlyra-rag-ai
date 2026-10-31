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

REPO = "Xenova/multilingual-e5-small"
MODEL = "multilingual-e5-small-int8-v1"
DIMENSION = 384
MODEL_FILE = "onnx/model_quantized.onnx"
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
        pad_id = self.tokenizer.token_to_id("<pad>")
        if pad_id is None:
            raise RuntimeError("Unsupported multilingual E5 tokenizer")
        self.tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(weights), sess_options=options, providers=["CPUExecutionProvider"],
        )
        self.names = set(x.name for x in self.session.get_inputs())
        if not {"input_ids", "attention_mask"}.issubset(self.names):
            raise RuntimeError("Unsupported E5 model inputs")

    def encode(self, texts: list[str], mode: str) -> list[list[float]]:
        if not 1 <= len(texts) <= 8 or mode not in ("query", "passage"):
            raise ValueError("Invalid embedding batch")
        prefix = "query: " if mode == "query" else "passage: "
        encoded = self.tokenizer.encode_batch([prefix + text for text in texts])
        ids = np.asarray([sample.ids for sample in encoded], dtype=np.int64)
        mask = np.asarray([sample.attention_mask for sample in encoded], dtype=np.int64)
        inputs = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.names:
            inputs["token_type_ids"] = np.zeros_like(ids, dtype=np.int64)
        if self.names - set(inputs):
            raise RuntimeError("Unsupported E5 ONNX input signature")
        with _MODEL_LOCK:
            output = self.session.run(None, inputs)[0]
        if output.ndim == 3 and output.shape[:2] == mask.shape:
            weights = mask[:, :, None].astype(np.float32)
            output = (output * weights).sum(axis=1) / np.maximum(
                weights.sum(axis=1), 1,
            )
        if output.shape != (len(texts), DIMENSION):
            raise RuntimeError("Unexpected E5 ONNX output shape")
        norms = np.linalg.norm(output, axis=1, keepdims=True)
        if not np.isfinite(output).all() or np.any(norms < 1e-8):
            raise RuntimeError("Invalid E5 vector magnitude")
        return (output / norms).tolist()


@lru_cache(maxsize=1)
def get_encoder() -> Encoder:
    return Encoder()
