# Mozaika TV

Aplikacja budująca mozaikę 2×2 z lokalnych filmów, filmów YouTube i transmisji
YouTube Live. Backend publikuje wspólną partię czterech klatek w losowym
odstępie od 3 do 5 sekund.

Projekt jest przygotowany do uruchamiania na Linuxie i macOS przez Docker
Compose.

## Wymagania

- Linux: Docker Engine z pluginem Docker Compose;
- macOS: Docker Desktop;
- Bash 3.2 lub nowszy;
- cztery lokalne pliki startowe w katalogu `filmy`.

## Szybkie uruchomienie

1. Sklonuj repozytorium i przejdź do katalogu projektu.
2. Umieść w katalogu `filmy` cztery pliki MP4 o dokładnych nazwach:
   `film1.mp4`, `film2.mp4`, `film3.mp4` i `film4.mp4` (`filmX.mp4`, gdzie
   `X` ma wartość od 1 do 4).
3. Nadaj skryptom prawo wykonania i uruchom aplikację:

```bash
chmod +x start.sh stop.sh download_youtube.sh
./start.sh
```

4. Otwórz:

- mozaika: <http://localhost:8090>;
- panel administracyjny: <http://localhost:8090/admin>.

Zatrzymanie aplikacji:

```bash
./stop.sh
```

Skrypt `start.sh` buduje obrazy, uruchamia kontenery i otwiera stronę w domyślnej
przeglądarce. Aby nie otwierać przeglądarki:

```bash
NO_BROWSER=1 ./start.sh
```

## Wdrożenie przez Docker Compose

Opcjonalną konfigurację utwórz na podstawie przykładu:

```bash
cp .env.example .env
```

Uruchomienie lub aktualizacja wdrożenia:

```bash
docker compose up -d --build
docker compose ps
```

Podgląd logów:

```bash
docker compose logs -f
```

Zatrzymanie i usunięcie kontenerów:

```bash
docker compose down
```

Pliki z `filmy/` są montowane do backendu tylko do odczytu. Konfiguracja panelu
i wygenerowane klatki są przechowywane w nazwanym wolumenie
`mosaic-runtime`, dzięki czemu przetrwają przebudowę kontenerów.

## Konfiguracja

Zmienne obsługiwane w pliku `.env`:

```env
MOSAIC_PORT=8090
MOSAIC_REFRESH_MIN=3
MOSAIC_REFRESH_MAX=5
MOSAIC_FRAME_WIDTH=960
MOSAIC_FRAME_HEIGHT=540
MOSAIC_RETAINED_BATCHES=30
# Opcjonalny plik Netscape cookies.txt dla YouTube (np. /runtime/youtube-cookies.txt)
MOSAIC_YOUTUBE_COOKIEFILE=
```

Jeżeli YouTube zgłasza „Sign in to confirm you’re not a bot”, wyeksportuj
cookies z zalogowanej przeglądarki do formatu Netscape `cookies.txt` i wskaż
ich ścieżkę przez `MOSAIC_YOUTUBE_COOKIEFILE`. Pliku nie dodawaj do repozytorium.

## Zasady działania

- obsługiwane rozszerzenia: MP4, MKV, MOV, WebM, AVI i M4V;
- przy pierwszym uruchomieniu wybierane są cztery pliki posortowane
  alfabetycznie;
- wszystkie cztery klatki są generowane równolegle przez FFmpeg;
- każda partia otrzymuje wspólny numer i jest publikowana jednocześnie;
- klatki mają format WebP i domyślnie rozdzielczość 960×540;
- po awarii źródła widoczna pozostaje jego ostatnia poprawna klatka;
- przechowywane jest ostatnich 30 partii;
- panel `/admin` pozwala bez restartu pozostawić pusty kafelek, wybrać plik
  lokalny albo wkleić adres filmu/transmisji YouTube oraz zmienić nazwę,
  interwał, rozdzielczość i jakość;
- zwykłe filmy YouTube są przesuwane i zapętlane tak jak pliki lokalne;
- dla transmisji YouTube Live przechwytywana jest bieżąca klatka;
- wygasający techniczny adres strumienia YouTube jest automatycznie odświeżany
  przez `yt-dlp` po błędzie przechwytywania.

## Źródła YouTube w mozaice

W panelu `/admin` ustaw dla wybranego kafelka typ `YouTube / YouTube Live`,
wklej publiczny adres z `youtube.com` albo `youtu.be`, ustaw nazwę ekranową i
wybierz `ZAPISZ I ZASTOSUJ`. Typ filmu lub transmisji live jest rozpoznawany
automatycznie.

Materiał prywatny, wymagający logowania albo ograniczony dla danego regionu
może nie być dostępny.

## Pomocniczy downloader YouTube

Skrypt `download_youtube.sh` pobiera pojedynczy film do MP4 w jakości do 1080p.
Jeżeli `yt-dlp` nie jest zainstalowany w systemie, skrypt pobiera odpowiedni
oficjalny plik wykonywalny dla Linuxa x86_64/ARM64 albo macOS do ignorowanego
katalogu `tools/`.

Wymagane lokalnie są `curl`, `ffmpeg` i `ffprobe`.

```bash
./download_youtube.sh "https://www.youtube.com/watch?v=ID"
./download_youtube.sh "https://www.youtube.com/watch?v=ID" /ścieżka/docelowa
```

Domyślnym katalogiem docelowym jest `filmy/`. Downloader jest narzędziem
pomocniczym i nie jest używany przez kontenery Mozaiki TV.

## Tryb deweloperski

Backend:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend w drugim terminalu:

```bash
cd frontend
npm install
npm run dev
```

Interfejs deweloperski będzie dostępny pod <http://localhost:5173>.

## Kontrola jakości

```bash
bash -n start.sh stop.sh download_youtube.sh
./download_youtube.sh --self-test
PYTHONPATH=backend .venv/bin/python -m pytest -q
.venv/bin/ruff check backend
cd frontend
npm run check
npm run build
```

## Interfejs backendu

- `GET /api/mosaic` — aktualna partia mozaiki;
- `GET /api/events` — powiadomienia SSE o nowych partiach;
- `GET /api/health` — stan silnika i źródeł;
- `GET /api/admin/config` — konfiguracja i lista dostępnych filmów;
- `PUT /api/admin/config` — walidacja, zapis i zastosowanie konfiguracji;
- `GET /frames/...` — niezmienne pliki WebP.

Zakres i kryteria MVP opisuje [docs/MVP.md](docs/MVP.md).

## Następny etap

Docelowo można dodać źródła RTSP/ONVIF oraz kanały DVB-T2 udostępniane przez
Tvheadend bez zmiany interfejsu WWW.
