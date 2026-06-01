from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

import tenseal as ts
from hospital_client import (
    create_private_context,
    decrypt_scalar,
    decrypt_vector,
    encrypt_column,
    export_public_context,
)
from computation_server import (
    compute_encrypted_mean,
    compute_encrypted_variance,
    compute_batch_stats,
)

# Konfiguracja
SELECTED_FEATURES = [
    "mean radius",
    "mean texture",
    "mean perimeter",
    "mean area",
    "mean smoothness",
    "mean concavity",
]

DIAGNOSIS_LABELS = {"M": "Złośliwy (Malignant)", "B": "Łagodny (Benign)"}


def load_breast_cancer_data() -> pd.DataFrame:
    from sklearn.datasets import load_breast_cancer
    bc = load_breast_cancer()
    df = pd.DataFrame(bc.data, columns=bc.feature_names)
    df["diagnosis"] = ["M" if t == 0 else "B" for t in bc.target]
    return df


@dataclass
class TimingRecord:
    key_gen: float = 0.0
    encryption: float = 0.0
    server_computation: float = 0.0
    decryption: float = 0.0

    def total(self) -> float:
        return self.key_gen + self.encryption + self.server_computation + self.decryption


@dataclass
class FeatureStats:
    feature: str
    mean_enc: float = 0.0
    mean_plain: float = 0.0
    variance_enc: float = 0.0
    variance_plain: float = 0.0
    std_enc: float = 0.0
    std_plain: float = 0.0



def analyze_group(
    label: str,
    values_dict: dict[str, list[float]],
    timing: TimingRecord,
) -> list[FeatureStats]:
    """
    poufna analizq statystyczna dla jednej grupy pacjentow.
    Modyfikuje timing w miejscu - in-place
    """
    n = len(next(iter(values_dict.values())))

    #Generowanie kluczy i kontekstu 
    t0 = time.perf_counter()
    private_ctx = create_private_context()
    public_ctx_bytes = export_public_context(private_ctx)
    timing.key_gen += time.perf_counter() - t0

    #szyfrowanie
    t0 = time.perf_counter()
    encrypted_columns: dict[str, bytes] = {}
    for feature, values in values_dict.items():
        encrypted_columns[feature] = encrypt_column(private_ctx, values)
    timing.encryption += time.perf_counter() - t0

    #obliczenia na serwerze
    t0 = time.perf_counter()
    enc_means = compute_batch_stats(public_ctx_bytes, encrypted_columns, n)

    # Wariancja musi miec zaszyfrowanego wektora srednich broadcast 
    enc_variances: dict[str, bytes] = {}
    for feature, enc_col in encrypted_columns.items():
        mean_val = decrypt_scalar(private_ctx, enc_means[feature])  
        # Re-szyfruj srednia jako wektor broadcast po stronie szpitala
        enc_mean_broadcast = encrypt_column(private_ctx, [mean_val] * n)
        enc_variances[feature] = compute_encrypted_variance(
            public_ctx_bytes, enc_col, enc_mean_broadcast, n
        )
    timing.server_computation += time.perf_counter() - t0

    # Deszyfrowanie po stronie szpitala 
    t0 = time.perf_counter()
    results: list[FeatureStats] = []
    vals_list = list(values_dict.values())
    feats_list = list(values_dict.keys())

    for i, feature in enumerate(feats_list):
        vals = values_dict[feature]
        plain_mean = float(np.mean(vals))
        plain_var = float(np.var(vals))

        dec_mean = decrypt_scalar(private_ctx, enc_means[feature])
        dec_var = decrypt_scalar(private_ctx, enc_variances[feature])

        stat = FeatureStats(
            feature=feature,
            mean_enc=dec_mean,
            mean_plain=plain_mean,
            variance_enc=max(dec_var, 0.0),   
            variance_plain=plain_var,
            std_enc=math.sqrt(max(dec_var, 0.0)),
            std_plain=math.sqrt(plain_var),
        )
        results.append(stat)
    timing.decryption += time.perf_counter() - t0

    return results



# Formatowanie wyjscia
BOLD= "\033[1m"
CYAN= "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"
LINE = "─" * 78


def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{text}{RESET}")
    print(LINE)


def row(label: str, enc: float, plain: float, unit: str = "") -> None:
    err = abs(enc - plain)
    print(f"{label:<20} zaszyf.: {enc:>12.6f}{unit}   jawna: {plain:>12.6f}{unit}   Δ={err:.2e}")


def print_stats(label: str, stats: list[FeatureStats]) -> None:
    header(f"Wyniki dla grupy: {label}")
    for s in stats:
        print(f"\n  {BOLD}{s.feature}{RESET}")
        row("Średnia",    s.mean_enc,     s.mean_plain)
        row("Wariancja",  s.variance_enc, s.variance_plain)
        row("Odch. std.", s.std_enc,      s.std_plain)


def print_timing(timing: TimingRecord, n_patients: int) -> None:
    header("Pomiar wydajnosci")
    ms = lambda s: f"{s * 1000:>8.2f} ms"
    print(f"Generowanie kluczy i kontekstu : {ms(timing.key_gen)}")
    print(f"Szyfrowanie danych ({n_patients} pacjentow) : {ms(timing.encryption)}")
    print(f"Obliczenia na serwerze         : {ms(timing.server_computation)}")
    print(f"Deszyfrowanie wynikow          : {ms(timing.decryption)}")
    print(f"{LINE[:40]}")
    print(f"RAZEM                          : {ms(timing.total())}")


def print_security_note() -> None:
    header("Gwarancje bezpieczenstwa")
    notes = [
        "Serwer obliczeniowy nigdy nie widzial danych w postaci jawnej.",
        "Klucz tajny pozostal wylacznie po stronie szpitala.",
        "Serwer otrzymal tylko kontekst publiczny + szyfrogramy CKKS.",
        "Wyniki sa zaszyfrowane - tylko szpital moze je odszyfrować.",
        "Schemat: CKKS (Cheon-Kim-Kim-Song) - TenSEAL / Microsoft SEAL.",
    ]
    for note in notes:
        print(f"{RESET}  {note}")



def main() -> None:
    print(f"\n{BOLD}{'=' * 78}{RESET}")
    print(f"{BOLD}  POUFNA ANALIZA STATYSTYCZNA - Breast Cancer Wisconsin{RESET}")
    print(f"{BOLD}  Szyfrowanie homomorficzne CKKS / TenSEAL{RESET}")
    print(f"{BOLD}{'=' * 78}{RESET}\n")

    # Wczytanie danych
    df = load_breast_cancer_data()
    total = len(df)
    print(f"Dataset: {total} pacjentow,  cechy analizowane: {len(SELECTED_FEATURES)}")
    print(f"Grupa M (zlosliwy): {(df.diagnosis == 'M').sum()}  |  "
          f"Grupa B (lagodny): {(df.diagnosis == 'B').sum()}")
    print(f"\n  Analizowane cechy:")
    for f in SELECTED_FEATURES:
        print(f"    • {f}")

    timing_total = TimingRecord()
    all_stats: dict[str, list[FeatureStats]] = {}

    for diag_code, diag_label in DIAGNOSIS_LABELS.items():
        subset = df[df["diagnosis"] == diag_code]
        values_dict = {feat: subset[feat].tolist() for feat in SELECTED_FEATURES}

        print(f"\n\n{YELLOW}[...]{RESET} Analizuje grupe: {diag_label}  ({len(subset)} pacjentow)")
        stats = analyze_group(diag_label, values_dict, timing_total)
        all_stats[diag_code] = stats
        print_stats(diag_label, stats)

    print_timing(timing_total, total)
    print_security_note()

    # Podsumowanie porownawcze
    header("Porownanie grup M vs B (odszyfrowane srednie)")
    print(f"  {'Cecha':<30} {'Złośliwy (M)':>15} {'Łagodny (B)':>15} {'Różnica':>12}")
    print(f"  {'-'*72}")
    for feat, sm, sb in zip(
        SELECTED_FEATURES,
        all_stats["M"],
        all_stats["B"],
    ):
        diff = sm.mean_enc - sb.mean_enc
        sign = "+" if diff > 0 else ""
        print(f"  {feat:<30} {sm.mean_enc:>15.4f} {sb.mean_enc:>15.4f} {sign}{diff:>11.4f}")

    print(f"\n{BOLD}{'=' * 78}{RESET}\n")


if __name__ == "__main__":
    main()
