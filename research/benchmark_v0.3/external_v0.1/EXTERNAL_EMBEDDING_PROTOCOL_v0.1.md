# External Embedding Protocol v0.1

Status: research protocol
Purpose: reproducible external retrieval validation

## Encoder

Model:
ibm-granite/granite-embedding-97m-multilingual-r2

Pinned revision:
c61e626a6255c490879d0af885078b61929d51f6

Embedding dimension:
384

Similarity:
cosine

Normalization:
L2-normalized embeddings

## Execution environment

External evaluation embeddings are generated with the pinned model
locally through Sentence Transformers.

Remote embedding inference is not used during the measured
retrieval evaluation.

The research environment is Python 3.12.x with the pinned package
versions recorded in:

research/granite_local_environment_v0.1.json

## Reproducibility requirements

The exact model revision must remain fixed.

Input corpus/query files must be hashed before the run.

Embedding dimensionality must equal 384.

All generated vectors must be finite and L2-normalized within tolerance.

No model weights are committed to Git.

Generated embedding artifacts are treated as reproducible build
outputs and can be regenerated from the pinned model revision.

## Interpretation

External benchmark results are validation evidence for transferability
of the observed retrieval behavior. They are not, by themselves,
evidence of novelty, causal superiority, or state-of-the-art performance.
