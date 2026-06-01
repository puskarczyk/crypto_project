from __future__ import annotations
import tenseal as ts

# Generowanie i eksport kontekstu
def create_private_context() -> ts.Context:
    """
    Generuje prywatny kontekst CKKS po stronie szpitala.
    poly_modulus_degree=8192 i 4 warstwy koeficjentow daja dostateczny
    budzet szumow dla operacji: szyfrowanie -> suma -> mnozenie przez skalar.
    """
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60],
    )
    context.global_scale = 2 ** 40
    context.generate_galois_keys()   
    return context


def export_public_context(private_context: ts.Context) -> bytes:
    return private_context.serialize(save_secret_key=False)



# Szyfrowanie i deszyfrowanie
def encrypt_column(context: ts.Context, values: list[float]) -> bytes:
    return ts.ckks_vector(context, values).serialize()


def decrypt_vector(context: ts.Context, encrypted_bytes: bytes) -> list[float]:
    return ts.ckks_vector_from(context, encrypted_bytes).decrypt()


def decrypt_scalar(context: ts.Context, encrypted_bytes: bytes) -> float:
    return decrypt_vector(context, encrypted_bytes)[0]
