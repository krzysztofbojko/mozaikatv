# Mozaika TV

Aplikacja badawcza budująca mozaikę 2×2 z lokalnych filmów, filmów YouTube
i transmisji YouTube Live. Backend publikuje wspólną partię czterech klatek
w losowym odstępie od 3 do 5 sekund.

## Szybkie uruchomienie na Windows

Wymagany jest uruchomiony Docker Desktop.

1. Umieść co najmniej cztery filmy w katalogu `filmy`.
2. Uruchom `Uruchom mozaike.bat`.
3. Otwórz widok prezentacyjny: <http://localhost:8090>.
4. Ustawienia są dostępne pod <http://localhost:8090/admin>.

Do zatrzymania aplikacji służy `Zatrzymaj mozaike.bat`.

Można też uruchomić aplikację z terminala:

```bash
docker compose up -d --build
```

## Zasady działania

- obsługiwane rozszerzenia: MP4, MKV, MOV, WebM, AVI i M4V;
- przy pierwszym uruchomieniu wybierane są cztery pliki posortowane alfabetycznie;
- wszystkie cztery klatki są generowane równolegle przez FFmpeg;
- każda partia otrzymuje wspólny numer i jest publikowana jednocześnie;
- klatki mają format WebP i domyślnie rozdzielczość 960×540;
- po awarii źródła widoczna pozostaje jego ostatnia poprawna klatka;
- przechowywane jest ostatnich 30 partii;
- panel `/admin` pozwala bez restartu wybrać plik lokalny albo wkleić adres
  filmu/transmisji YouTube oraz zmienić nazwy, interwał,
  rozdzielczość i jakość WebP;
- zwykłe filmy YouTube są przesuwane i zapętlane tak jak pliki lokalne;
- dla transmisji YouTube Live przechwytywana jest bieżąca klatka;
- wygasający techniczny adres strumienia YouTube jest automatycznie odświeżany
  przez `yt-dlp` po błędzie przechwytywania;
- konfiguracja panelu jest trwale zapisywana w wolumenie `mosaic-runtime`.

## Konfiguracja

Skopiuj `.env.example` do `.env`, aby zmienić ustawienia:

```env
MOSAIC_PORT=8090
MOSAIC_REFRESH_MIN=3
MOSAIC_REFRESH_MAX=5
MOSAIC_FRAME_WIDTH=960
MOSAIC_FRAME_HEIGHT=540
MOSAIC_RETAINED_BATCHES=30
```

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
.venv/bin/python -m pytest
cd frontend
npm run check
npm run build
npm audit --omit=dev
```

## Interfejs backendu

- `GET /api/mosaic` — aktualna partia mozaiki;
- `GET /api/events` — powiadomienia SSE o nowych partiach;
- `GET /api/health` — stan silnika i źródeł;
- `GET /api/admin/config` — konfiguracja i lista dostępnych filmów;
- `PUT /api/admin/config` — walidacja, zapis i zastosowanie konfiguracji;
- `GET /frames/...` — niezmienne pliki WebP.

Zakres i kryteria MVP opisuje [docs/MVP.md](docs/MVP.md).

## Źródła YouTube

W panelu `/admin` ustaw dla wybranego kafelka typ `YouTube / YouTube Live`,
wklej publiczny adres z `youtube.com` albo `youtu.be`, ustaw nazwę ekranową i
wybierz `ZAPISZ I ZASTOSUJ`. Typ filmu lub transmisji live jest rozpoznawany
automatycznie. Materiał prywatny, wymagający logowania albo ograniczony dla
danego regionu może nie być dostępny.

## Następny etap

Docelowo można dodać źródła RTSP/ONVIF oraz kanały DVB-T2 udostępniane przez
Tvheadend bez zmiany interfejsu WWW.

## Pomocniczy downloader

Istniejące pliki `Uruchom downloader.bat` i `YouTubeDownloader.ps1` pozostają
oddzielnym narzędziem do przygotowania materiałów testowych. Nie są używane
przez Mozaikę TV.
