# Vinted Market Panel

Ciemny, responsywny dashboard do analizy rynku Vinted. Wygląda jak aplikacja mobilna (PWA).

## Funkcje

- **Dashboard** — statystyki, trend cenowy, top marki
- **Przedmioty** — przegląd, szukanie, filtrowanie, sortowanie
- **Wyszukiwania** — dodawanie/usuwanie zapytań, manualny fetch
- **Analiza** — porównanie marek (średnia, min, max cena)
- **PWA** — dodajesz do ekranu głównego i działa jak appka

## Stack

- Backend: FastAPI + SQLAlchemy + vinted_scraper
- Frontend: Vanilla JS + CSS (ciemny motyw)
- Baza: SQLite
- Deploy: Docker

## Szybki start (lokalnie)

```bash
docker compose up --build
# Otwórz http://localhost:8080
```

## Deploy na Hetzner

```bash
# Na VPS:
scp -r vinted-panel/ root@<TWÓJ-IP>:/opt/
ssh root@<TWÓJ-IP>
cd /opt/vinted-panel
chmod +x scripts/install-hetzner.sh
./scripts/install-hetzner.sh
```

## Struktura

```
vinted-panel/
├── backend/
│   ├── main.py           — FastAPI app + API endpoints
│   ├── database.py       — SQLAlchemy models
│   └── requirements.txt  — zależności Python
├── frontend/
│   ├── index.html        — główny szablon
│   ├── css/style.css     — ciemny motyw
│   ├── js/app.js         — logika frontendu
│   ├── manifest.json     — PWA manifest
│   └── icons/            — ikony PWA
├── scripts/
│   └── install-hetzner.sh — skrypt instalacyjny
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## API Endpoints

| Method | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/stats` | Ogólne statystyki |
| GET | `/api/items` | Lista przedmiotów (paginacja, filtry) |
| GET | `/api/price-trends` | Trend cenowy (30 dni) |
| GET | `/api/brand-analysis` | Analiza marek |
| GET | `/api/queries` | Lista zapytań |
| POST | `/api/queries` | Dodaj zapytanie |
| DELETE | `/api/queries/{id}` | Usuń zapytanie |
| POST | `/api/queries/{id}/toggle` | Włącz/wyłącz |
| POST | `/api/fetch/{id}` | Uruchom fetch teraz |

## Bezpieczeństwo

Domyślnie panel jest otwarty. Dla produkcji dodaj:
- Basic Auth lub OAuth
- Reverse proxy (Caddy/Nginx) z HTTPS
- Firewall na port 8080
