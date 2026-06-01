from __future__ import annotations
import math
import tenseal as ts


def _load(public_ctx_bytes: bytes, enc_bytes: bytes) -> tuple[ts.Context, ts.CKKSVector]:
    ctx = ts.context_from(public_ctx_bytes)
    vec = ts.ckks_vector_from(ctx, enc_bytes)
    return ctx, vec


#publiczne API serwera

def compute_encrypted_sum(
    public_context_bytes: bytes,
    encrypted_column_bytes: bytes,
) -> bytes:
    _, vec = _load(public_context_bytes, encrypted_column_bytes)
    return vec.sum().serialize()


def compute_encrypted_mean(
    public_context_bytes: bytes,
    encrypted_column_bytes: bytes,
    n: int,
) -> bytes:
    # Zaszyfrowana srednia: sum(x) / n
    if n <= 0:
        raise ValueError("n musi byc > 0")
    _, vec = _load(public_context_bytes, encrypted_column_bytes)
    return (vec.sum() * (1.0 / n)).serialize()


def compute_encrypted_variance(
    public_context_bytes: bytes,
    encrypted_column_bytes: bytes,
    encrypted_mean_bytes: bytes,
    n: int,
) -> bytes:
    #Zaszyfrowana wariancja: sum((x_i - mean)^2) / n
    if n <= 0:
        raise ValueError("n musi byc > 0")
    ctx, vec = _load(public_context_bytes, encrypted_column_bytes)
    mean_vec = ts.ckks_vector_from(ctx, encrypted_mean_bytes)

    # Rozszerzamy srednia do wektora o dlugosci n (replikacja przez mnozenie skalarem 1)
    centred = vec - mean_vec  # CKKS: vec - broadcast_mean (ten sam rozmiar)
    sq = centred * centred
    variance = sq.sum() * (1.0 / n)
    return variance.serialize()


def compute_batch_stats(
    public_context_bytes: bytes,
    encrypted_columns: dict[str, bytes],   
    n: int,
) -> dict[str, bytes]:
    #oblicza srednia dla kazdej kolumny w jednym wywolaniu.
    results: dict[str, bytes] = {}
    for feature, enc_bytes in encrypted_columns.items():
        results[feature] = compute_encrypted_mean(
            public_context_bytes, enc_bytes, n
        )
    return results
