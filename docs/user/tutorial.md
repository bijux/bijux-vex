# End-to-End Tutorial

This tutorial is fully copy/pasteable. It shows an explicit, deterministic flow and an explicit VDB flow.

## Install

```
pip install bijux-vex
```

Optional extras:

```
pip install "bijux-vex[embeddings]"
pip install "bijux-vex[vdb]"
```

## Ingest (Bring Your Own Vectors)

```
bijux vex ingest --doc "hello world" --vector "[0.0, 1.0]"
```

## Materialize an Artifact

```
bijux vex materialize --execution-contract deterministic
```

## Execute (Exact)

```
bijux vex execute \
  --vector "[0.0, 1.0]" \
  --execution-contract deterministic \
  --execution-intent exact_validation
```

## Explain + Compare

```
bijux vex execute \
  --vector "[0.0, 1.0]" \
  --execution-contract deterministic \
  --execution-intent exact_validation \
  --explain
```

## Explicit Vector Store (FAISS)

```
bijux vex ingest \
  --doc "hello world" \
  --vector "[0.0, 1.0]" \
  --vector-store faiss
```

```
bijux vex materialize --execution-contract deterministic --vector-store faiss
```

```
bijux vex execute \
  --vector "[0.0, 1.0]" \
  --execution-contract deterministic \
  --execution-intent exact_validation \
  --vector-store faiss
```

## Documents-Only (Explicit Embeddings)

```
bijux vex ingest \
  --doc "hello world" \
  --embed-model "sentence-transformers/all-MiniLM-L6-v2" \
  --embed-provider sentence_transformers
```

## Provenance

```
bijux vex explain --result-id <result_id>
```
