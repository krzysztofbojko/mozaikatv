# Mozaika TV — zakres MVP

## Cel

Aplikacja prezentuje cztery wybrane źródła jako mozaikę 2×2. Źródłem może być
lokalny film, film YouTube albo transmisja YouTube Live. Aplikacja publikuje
wspólną partię czterech klatek w losowym odstępie od 3 do 5 sekund.

## Wymagania

- źródła są automatycznie wykrywane w katalogu `filmy`;
- przy pierwszym uruchomieniu używane są cztery filmy posortowane po nazwie;
- panel `/admin` pozwala przypisać dowolne cztery wykryte filmy do kafelków,
  zastąpić dowolny z nich publicznym adresem YouTube, zmienić nazwy oraz
  parametry generowania klatek;
- zmiany są stosowane bez restartu i zapisywane trwale;
- wszystkie kafelki należą do jednej zsynchronizowanej partii;
- filmy są traktowane jak zapętlone źródła i przewijają się zgodnie z czasem
  działania aplikacji;
- transmisja YouTube Live zawsze zwraca klatkę z bieżącego momentu;
- wynikowe klatki mają format WebP i rozmiar 960×540;
- awaria pojedynczego źródła nie zatrzymuje pozostałych kafelków;
- publiczny interfejs `/` pokazuje wyłącznie mozaikę, stan źródeł i czas klatki,
  bez przycisków sterujących;
- backend udostępnia stan przez HTTP oraz powiadomienia SSE;
- aplikacja uruchamia się przez Docker Compose albo lokalnie w trybie
  deweloperskim.

## Poza zakresem MVP

- obsługa DVB-T2, RTSP i ONVIF;
- uwierzytelnianie i role panelu administracyjnego;
- baza danych i trwałe archiwum klatek;
- odtwarzanie dźwięku lub ciągłego wideo.
