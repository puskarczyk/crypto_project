# System poufnej analizy danych medycznych z wykorzystaniem szyfrowania homomorficznego

*Projekt realizowany w ramach kursu Metody Kryptografii na AGH*


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
Serwer otrzymuje zaszyfrowany wektor danych $\text{enc\_x}$ o długości $n$. Wykorzystując homomorficzne dodawanie oraz mnożenie przez jawny skalar, serwer realizuje algorytm:

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


