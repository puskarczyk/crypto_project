# System poufnej analizy danych medycznych z wykorzystaniem szyfrowania homomorficznego

*Projekt realizowany w ramach kursu Metody Kryptografii na AGH*

## Cel Projektu
Celem projektu jest pokazanie możliwości wykonywania podstawowych analiz statystycznych na danych medycznych (średnie, wariancje) bez ujawniania danych pacjentów, poprzez zastosowanie szyfrowania homomorficznego (schemat CKKS) z wykorzystaniem biblioteki TenSEAL.

## Opis datasetu
Użyty zbiór danych: Breast Cancer Wisconsin. Zbiór zawiera cechy obrazów cytologicznych guzów piersi oraz etykietę diagnozy: M (*malignant*, złośliwy) lub B (*benign*, łagodny). Zbiór liczy standardowo 569 próbek i około 30 cech opisujących m.in. rozmiar i kształt zmian.

**Wybór zmiennych do analizy**
W projekcie analizowano podzbiór cech związanych z rozmiarem i kształtem guza, które często korelują z charakterem zmiany:
	- mean radius
	- mean texture
	- mean perimeter
	- mean area
	- mean smoothness
	- mean concavity

Wybór tych cech umożliwia porównanie statystyk (średnich i wariancji) pomiędzy grupami M i B w kontekście diagnostycznym.

**Opis algorytmów i działania projektu**
- Schemat szyfrowania: CKKS (TenSEAL / Microsoft SEAL) - umożliwia operacje arytmetyczne na liczbach zmiennoprzecinkowych w postaci zaszyfrowanej.
- Podział kodu:
	- `hospital_client.py`: generuje prywatny kontekst CKKS, eksportuje kontekst publiczny, szyfruje kolumny (wektory cech) oraz odszyfrowuje wyniki (funkcje: `create_private_context`, `export_public_context`, `encrypt_column`, `decrypt_scalar`, `decrypt_vector`). Parametry kontekstu użyte w implementacji: `poly_modulus_degree=8192`, `coeff_mod_bit_sizes=[60, 40, 40, 60]`, `global_scale=2**40`.
	- `computation_server.py`: serwer obliczeniowy operuje na kontekście publicznym i szyfrogramach; implementuje funkcje: `compute_encrypted_mean`, `compute_encrypted_variance`, `compute_batch_stats`. Operacje wykonywane są wektorowo z użyciem CKKS (sumy, mnożenia przez skalar, odejmowanie wektorów).
	- `demo.py`: skrypt demonstracyjny łączący komponenty: wczytuje dane, dzieli je na grupy M/B, po stronie szpitala generuje kontekst i szyfruje kolumny, serwer oblicza zaszyfrowane statystyki, szpital odszyfrowuje i porównuje wyniki.

## Wyniki i wnioski
- Skrypt demonstracyjny oblicza dla wybranych cech średnie i wariancje dla grup M i B w formie zaszyfrowanej (po stronie serwera) oraz odszyfrowanej (po stronie szpitala). Wyniki wyświetlane są w konsoli wraz z porównaniem średnich pomiędzy grupami.
- Interpretacja: istotne różnice średnich między grupami mogą wskazywać cechy skorelowane z charakterem zmiany (złośliwa vs łagodna). Projekt pokazuje, że takie porównania można przeprowadzić bez ujawniania surowych danych pacjentów serwerowi obliczeniowemu.
- Wnioski dotyczące bezpieczeństwa i wydajności:
	- Serwer nigdy nie otrzymuje danych w postaci jawnej - otrzymuje jedynie kontekst publiczny i szyfrogramy.
	- Klucz prywatny pozostaje po stronie szpitala.
	- Operacje CKKS mają koszty obliczeniowe i ograniczony budżet szumu; dobrane parametry (`poly_modulus_degree=8192`, odpowiednie `coeff_mod_bit_sizes`) zapewniają wystarczający margines na proste operacje statystyczne użyte w tym projekcie.

## Instrukcja uruchomienia
- Stwórz środowisko wirtualne i aktywuj je:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
- Zainstaluj wymagania:
```powershell
pip install -r requirements.txt
```
- Uruchom demo:
```powershell
python demo.py
```

Pliki projektu: [demo.py](demo.py), [hospital_client.py](hospital_client.py), [computation_server.py](computation_server.py), [requirements.txt](requirements.txt)


