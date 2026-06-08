# System poufnej analizy danych medycznych z wykorzystaniem szyfrowania homomorficznego

*Projekt realizowany w ramach kursu Metody Kryptografii na AGH*
**Autorzy: Patrycja Puskarczyk, Kinga Orłowicz**


## Opis i cel projektu
Głównym celem projektu jest projekt i implementacja systemu bezpiecznego outsourcingu obliczeń statystycznych na wrażliwych danych medycznych przy użyciu szyfrowania homomorficznego (schemat CKKS).

Projekt demonstruje architekturę typu Zero-Knowledge poprzez ścisły podział ról, odpowiedzialności oraz zasobów informacyjnych pomiędzy dwie niezależne strony:

### Strona Szpitala (Klient – Właściciel Danych):
Szpital jest jedynym podmiotem, który posiada pełne zaufanie oraz fizyczny dostęp do surowych danych pacjentów w postaci jawnej. Do jego zadań i uprawnień należy:

- Zarządzanie kluczami: Generowanie prywatnego kontekstu kryptograficznego CKKS. Klucz prywatny nigdy nie opuszcza lokalnej infrastruktury szpitala.
- Szyfrowanie u źródła: Przekształcanie jawnych wektorów cech medycznych pacjentów w zabezpieczone szyfrogramy przed ich wysłaniem do sieci.
- Eksport kontekstu publicznego: Udostępnianie serwerowi wyłącznie parametrów matematycznych i kluczy publicznych, które umożliwiają wykonywanie operacji na szyfrogramach, ale nie pozwalają na ich podejrzenie.
- Odszyfrowanie i interpretacja: Odbieranie od serwera zaszyfrowanych wyników końcowych i ich lokalne deszyfrowanie za pomocą klucza prywatnego.

### Strona Serwera ( Dostawca Usług Obliczeniowych)
Serwer jest traktowany jako podmiot niezaufany pod względem poufności. Oznacza to, że poprawnie wykonuje powierzone mu algorytmy, ale może próbować poznać analizowane dane. Architektura systemu całkowicie to uniemożliwia, ponieważ serwer:
- Operuje w ciemno: Nie ma dostępu do klucza prywatnego ani do surowych danych w postaci jawnej. Przez cały czas przetwarza szyfrogramy.
- Wykonuje obliczenia homomorficzne: Realizuje  operacje algebraiczne bezpośrednio na zaszyfrowanych danych, wykorzystując właściwości schematu CKKS.
- Zwraca zaszyfrowany wynik: Wyniki pośrednie oraz wynik końcowy (np. zaszyfrowana średnia czy wariancja) opuszczają serwer w formie uniemożliwiającej odczytanie ich przez kogokolwiek poza szpitalem.

## Opis datasetu
Użyty zbiór danych: Breast Cancer Wisconsin. Zbiór zawiera cechy obrazów cytologicznych guzów piersi oraz etykietę diagnozy: M (*malignant*, złośliwy) lub B (*benign*, łagodny). Zbiór liczy standardowo 569 próbek i około 30 cech opisujących m.in. rozmiar i kształt zmian.

### Wybór zmiennych do analizy
W projekcie analizowano podzbiór cech związanych z rozmiarem i kształtem guza, które często korelują z charakterem zmiany:
	- mean radius
	- mean texture
	- mean perimeter
	- mean area
	- mean smoothness
	- mean concavity

Wybór tych cech umożliwia porównanie statystyk (średnich i wariancji) pomiędzy grupami M i B w kontekście diagnostycznym.

## Opis algorytmów i działania projektu
Implementacja opiera się na architekturze rozproszonej, w której operacje wymagające znajomości klucza prywatnego są odizolowane po stronie klienta `hospital_client.py`, a operacje czysto homomorficzne są wykonywane przez serwer `computation_server.py`

W projekcie wykorzystano schemat CKKS (*Cheon-Kim-Kim-Song*) zaimplementowany w bibliotece TenSEAL (opartej na Microsoft SEAL). CKKS jest schematem typu *Homomorphic Encryption for Arithmetic of Approximate Numbers*, co oznacza, że pozwala na wykonywanie operacji na liczbach zmiennoprzecinkowych z określoną dokładnością przybliżenia, idealnie nadając się do obliczeń statystycznych.

Konfiguracja parametrów kryptograficznych po stronie szpitala zapewnia optymalny kompromis pomiędzy bezpieczeństwem, rozmiarem kluczy a tzw. budżetem szumu (ang. noise budget):
- `poly_modulus_degree` = 8192: Definiuje stopień wielomianu nadrzędnego. Wpływa bezpośrednio na poziom bezpieczeństwa oraz na maksymalną długość wektora danych (w jednym szyfrogramie możemy upakować do $8192 / 2 = 4096$ wartości typu float za pomocą techniki SIMD).
- `coeff_mod_bit_sizes` = [60, 40, 40, 60]: Łączny budżet bitowy modułów (200 bitów). Liczba warstw (modułów pośrednich) określa głębokość multiplikatywną algorytmu.
- `global_scale` = 2  40: Skala kodowania (mnożnik), która pozwala reprezentować liczby zmiennoprzecinkowe jako wielomiany o współczynnikach całkowitych z dokładnością do 40 bitów po przecinku.

### Protokół obliczeniowy i przepływ danych
Ze względu na ograniczenia szyfrowania homomorficznego (brak możliwości łatwego dzielenia szyfrogramu przez szyfrogram czy wyciągania pierwiastka), w projekcie zaimplementowano interakcyjny protokół obliczeniowy:

 ```mermaid
sequenceDiagram
    autonumber
    participant H as Szpital
    participant S as Serwer

    H->>S: Szyfrogramy kolumn + Kontekst publiczny
    Note over S: Oblicza sumę oraz średnią
    S->>H: Zaszyfrowana średnia (skalar)
    
    Note over H: Deszyfruje średnią u źródła<br/>Tworzy wektor broadcast
    
    H->>S: Zaszyfrowany wektor średniej (broadcast)
    Note over S: Oblicza wariancję
    S->>H: Zaszyfrowana wariancja (skalar)
    
    Note over H: Deszyfruje wariancję<br/>Oblicza lokalnie STD
```

### Obliczenie średniej
Serwer otrzymuje zaszyfrowany wektor danych $X$ o długości $n$. Wykorzystując homomorficzne dodawanie oraz mnożenie przez jawny skalar, serwer realizuje algorytm:

$$\mu_{enc} = \left( \sum_{i=1}^{n} X_{enc, i} \right) \cdot \frac{1}{n}$$

Wynikowy szyfrogram reprezentuje pojedynczą wartość (skalar) średniej.

### Wyznaczenie wariancji ($\sigma^2$) i odchylenia standardowego ($\sigma$)
Obliczenie wariancji wymaga operacji wycentrowania danych: $(x_i - \mu)^2$. Ponieważ serwer posiada średnią jako pojedynczy skalar, a operacje wektorowe w TenSEAL wymagają zgodności wymiarów, zastosowano bezpieczny protokół hybrydowy:
1. Szpital odbiera enc_mean, odszyfrowuje go lokalnie do wartości jawnej $\mu$.
2. Szpital generuje w pamięci jawny wektor o długości $n$ wypełniony tą samą wartością (tzw. broadcast): $[\mu, \mu, \dots, \mu]$, szyfruje go jako enc_mean_broadcast i odsyła na serwer.
3. Serwer wykonuje homomorficzne odejmowanie wektorów, mnożenie szyfrogramu przez sam siebie (podniesienie do kwadratu, co zużywa jedną warstwę budżetu szumu) oraz uśrednienie wyników:

$$\sigma^2_{enc} = \left( \sum_{i=1}^{n} (X_{enc, i} - \mu_{broadcast, i})^2 \right) \cdot \frac{1}{n}$$

4. Szpital odbiera i deszyfruje wariancję. Operacja pierwiastkowania w celu uzyskania odchylenia standardowego ($\sigma = \sqrt{\sigma^2}$) jest wykonywana lokalnie po stronie szpitala, ponieważ wyznaczenie pierwiastka na szyfrogramie CKKS wymagałoby kosztownej i niedokładnej aproksymacji wielomianowej.

## Walidacja i wyniki skryptu demonstracyjnego
Głównym zadaniem skryptu `demo.py` jest pełna weryfikacja poprawności matematycznej oraz wydajnościowej zaimplementowanego systemu. Program ładuje rzeczywisty zbiór danych medycznych Breast Cancer Wisconsin i dzieli pacjentów na dwie grupy diagnostyczne: M (zmiany złośliwe) oraz B (zmiany łagodne). W celach porównawczych, dla każdej z 6 wybranych cech (np. mean radius, mean texture), skrypt oblicza metryki równolegle dwoma torami:
- w sposób jawny,
- w sposób poufny poprzez zasymulowany protokół sieciowy.

Po uruchomieniu skrypt generuje w konsoli szczegółowy raport podzielony na sekcje:
- Wyniki statystyczne dla grup M i B: Dla każdej cechy wypisywana jest średnia, wariancja oraz odchylenie standardowe obliczone na szyfrogramach oraz w sposób jawny. Obok nich program kalkuluje błąd bezwzględny przybliżenia CKKS.
- Pomiar wydajności: Raport zawiera precyzyjny podział czasu spędzonego na poszczególnych etapach: generowanie kluczy, szyfrowanie danych pacjentów, obliczenia homomorficzne na serwerze oraz deszyfrowanie wyników. Pokazuje to narzut procesowy kryptografii asymetrycznej.
- Podsumowanie porównawcze: Na samym końcu generowana jest czytelna tabela porównująca bezpośrednio odszyfrowane średnie grupy M i B wraz z ich różnicą, co pozwala ocenić, które cechy geometryczne guza mają największą wartość diagnostyczną.

## Analiza wyników i wnioski

Wynik działania `demo.py`:
```
==============================================================================
  POUFNA ANALIZA STATYSTYCZNA - Breast Cancer Wisconsin
  Szyfrowanie homomorficzne CKKS / TenSEAL
==============================================================================

Dataset: 569 pacjentow,  cechy analizowane: 6
Grupa M (zlosliwy): 212  |  Grupa B (lagodny): 357

  Analizowane cechy:
    • mean radius
    • mean texture
    • mean perimeter
    • mean area
    • mean smoothness
    • mean concavity


[...] Analizuje grupe: Złośliwy (Malignant)  (212 pacjentow)

Wyniki dla grupy: Złośliwy (Malignant)
──────────────────────────────────────────────────────────────────────────────

  mean radius
Średnia              zaszyf.:    17.462833   jawna:    17.462830   Δ=2.37e-06
Wariancja            zaszyf.:    10.217017   jawna:    10.217009   Δ=8.25e-06
Odch. std.           zaszyf.:     3.196407   jawna:     3.196406   Δ=1.29e-06

  mean texture
Średnia              zaszyf.:    21.604909   jawna:    21.604906   Δ=2.92e-06
Wariancja            zaszyf.:    14.217025   jawna:    14.217014   Δ=1.15e-05
Odch. std.           zaszyf.:     3.770547   jawna:     3.770546   Δ=1.52e-06

  mean perimeter
Średnia              zaszyf.:   115.365393   jawna:   115.365377   Δ=1.55e-05
Wariancja            zaszyf.:   475.373301   jawna:   475.372918   Δ=3.83e-04
Odch. std.           zaszyf.:    21.803057   jawna:    21.803048   Δ=8.77e-06

  mean area
Średnia              zaszyf.:   978.376546   jawna:   978.376415   Δ=1.31e-04
Wariancja            zaszyf.: 134739.886645   jawna: 134739.778217   Δ=1.08e-01
Odch. std.           zaszyf.:   367.069321   jawna:   367.069174   Δ=1.48e-04

  mean smoothness
Średnia              zaszyf.:     0.102899   jawna:     0.102898   Δ=3.89e-08
Wariancja            zaszyf.:     0.000158   jawna:     0.000158   Δ=2.65e-08
Odch. std.           zaszyf.:     0.012580   jawna:     0.012578   Δ=1.05e-06

  mean concavity
Średnia              zaszyf.:     0.160775   jawna:     0.160775   Δ=4.81e-08
Wariancja            zaszyf.:     0.005601   jawna:     0.005601   Δ=3.01e-08
Odch. std.           zaszyf.:     0.074842   jawna:     0.074842   Δ=2.01e-07


[...] Analizuje grupe: Łagodny (Benign)  (357 pacjentow)

Wyniki dla grupy: Łagodny (Benign)
──────────────────────────────────────────────────────────────────────────────

  mean radius
Średnia              zaszyf.:    12.146525   jawna:    12.146524   Δ=1.64e-06
Wariancja            zaszyf.:     3.161344   jawna:     3.161342   Δ=2.55e-06
Odch. std.           zaszyf.:     1.778017   jawna:     1.778016   Δ=7.17e-07

  mean texture
Średnia              zaszyf.:    17.914764   jawna:    17.914762   Δ=2.41e-06
Wariancja            zaszyf.:    15.916325   jawna:    15.916312   Δ=1.28e-05
Odch. std.           zaszyf.:     3.989527   jawna:     3.989525   Δ=1.61e-06

  mean perimeter
Średnia              zaszyf.:    78.075417   jawna:    78.075406   Δ=1.05e-05
Wariancja            zaszyf.:   139.025174   jawna:   139.025062   Δ=1.12e-04
Odch. std.           zaszyf.:    11.790894   jawna:    11.790889   Δ=4.74e-06

  mean area
Średnia              zaszyf.:   462.790258   jawna:   462.790196   Δ=6.21e-05
Wariancja            zaszyf.: 17982.531883   jawna: 17982.517411   Δ=1.45e-02
Odch. std.           zaszyf.:   134.098963   jawna:   134.098909   Δ=5.40e-05

  mean smoothness
Średnia              zaszyf.:     0.092478   jawna:     0.092478   Δ=1.81e-08
Wariancja            zaszyf.:     0.000180   jawna:     0.000180   Δ=8.30e-09
Odch. std.           zaszyf.:     0.013428   jawna:     0.013427   Δ=3.09e-07

  mean concavity
Średnia              zaszyf.:     0.046058   jawna:     0.046058   Δ=1.19e-08
Wariancja            zaszyf.:     0.001882   jawna:     0.001882   Δ=6.24e-09
Odch. std.           zaszyf.:     0.043381   jawna:     0.043381   Δ=7.19e-08

Pomiar wydajnosci
──────────────────────────────────────────────────────────────────────────────
Generowanie kluczy i kontekstu :  1246.98 ms
Szyfrowanie danych (569 pacjentow) :    67.46 ms
Obliczenia na serwerze         :  7855.91 ms
Deszyfrowanie wynikow          :    24.63 ms
────────────────────────────────────────
RAZEM                          :  9194.98 ms

Gwarancje bezpieczenstwa
──────────────────────────────────────────────────────────────────────────────
  Serwer obliczeniowy nigdy nie widzial danych w postaci jawnej.
  Klucz tajny pozostal wylacznie po stronie szpitala.
  Serwer otrzymal tylko kontekst publiczny + szyfrogramy CKKS.
  Wyniki sa zaszyfrowane - tylko szpital moze je odszyfrować.
  Schemat: CKKS (Cheon-Kim-Kim-Song) - TenSEAL / Microsoft SEAL.

Porownanie grup M vs B (odszyfrowane srednie)
──────────────────────────────────────────────────────────────────────────────
  Cecha                             Złośliwy (M)     Łagodny (B)      Różnica
  ------------------------------------------------------------------------
  mean radius                            17.4628         12.1465 +     5.3163
  mean texture                           21.6049         17.9148 +     3.6901
  mean perimeter                        115.3654         78.0754 +    37.2900
  mean area                             978.3765        462.7903 +   515.5863
  mean smoothness                         0.1029          0.0925 +     0.0104
  mean concavity                          0.1608          0.0461 +     0.1147

==============================================================================
```


### 1. Dokładność obliczeń homomorficznych i analiza błędu ($\Delta$)
Analiza wykazała, że zastosowanie schematu CKKS pozwala na osiągnięcie bardzo wysokiej precyzji obliczeń, w zupełności wystarczającej do celów zaawansowanej analityki medycznej i diagnostyki. Błąd bezwzględny dla większości metryk oscyluje w granicach od $10^{-8}$ do $10^{-5}$.   W logach widoczna jest jednak wyraźna zależność: błąd bezwzględny obliczania wariancji jest zawsze większy niż błąd obliczania średniej. Zjawisko to wynika bezpośrednio ze specyfikacji algorytmu CKKS. Obliczenie wariancji wymaga dwukrotnego mnożenia zaszyfrowanych danych (głębokość mnożeń 2), co skutkuje dużym przyrostem szumu kryptograficznego wewnątrz szyfrogramu.

### 2. Analiza wydajności
Całkowity czas wykonania potoku obliczeniowego dla pełnego zbioru 569 pacjentów i 6 cech wyniósł 9194.98 ms. Struktura wydatków czasowych rozkłada się następująco:
- Generowanie kluczy i kontekstu 1246.98 ms
- Szyfrowanie 67.46 ms i Deszyfrowanie 24.63 ms
- Obliczenia na serwerze 7855.91 ms

Obliczenia na serwerze zajmują około 85% całkowitego czasu działania systemu. Operacje na szyfrogramach CKKS są ekstremalnie wymagające dla CPU serwera. Wynik poniżej 8 sekund dla przetwarzania tysięcy spakowanych punktów danych potwierdza jednak, że zaimplementowane podejście wektorowe w computation_server.py działa efektywnie.

### 3. Interpretacja kliniczna
Najważniejszym wnioskiem z punktu widzenia medycznego jest fakt, że system w 100% zachował wartość diagnostyczną danych, pomimo ich całkowitego utajnienia. Wygenerowana na końcu raportu tabela porównawcza jasno wskazuje na drastyczne różnice w profilach statystycznych obu grup:

```
  Cecha                             Złośliwy (M)     Łagodny (B)      Różnica
  ------------------------------------------------------------------------
  mean radius                            17.4628         12.1465 +     5.3163
  mean texture                           21.6049         17.9148 +     3.6901
  mean perimeter                        115.3654         78.0754 +    37.2900
  mean area                             978.3765        462.7903 +   515.5863
  mean smoothness                         0.1029          0.0925 +     0.0104
  mean concavity                          0.1608          0.0461 +     0.1147
```

Dzięki zaimplementowanemu systemowi, lekarz lub badacz medyczny pracujący na danych odszyfrowanych otrzymał precyzyjne, czytelne ekstrema różnicujące oba typy nowotworów, podczas gdy serwer przetwarzający te dane nie poznał ani jednej wartości promienia, powierzchni czy tożsamości pacjentów.

## Instrukcja uruchomienia
Wymagane: Python (projekt testowano zarówno na Pythonie 3.11 jak i 3.13 i działał)
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


