# Portal fixtures

Four self-contained, static HTML/JS fixtures that simulate the AmTrust,
Markel, Applied Epic, and Vertafore AMS360 producer portals. Used by:

* the backend integration suite (`backend/tests/integration/`)
* the browser extension content-script fixture tests
* local demos and operator training

## Run

```
docker compose up portal-fixtures
```

Each portal is served on its own port so the env vars used by the production
submitters map 1:1 to the fixture URLs:

| Portal             | URL                                  |
|--------------------|--------------------------------------|
| AmTrust            | http://localhost:8101/               |
| Markel             | http://localhost:8102/               |
| Applied Epic       | http://localhost:8103/               |
| Vertafore AMS360   | http://localhost:8104/               |
| Vertafore Sircon   | http://localhost:8105/               |

Login credentials for **every** fixture: `demo` / `demo`.

## Simulation flags (query string)

| Flag         | Effect                                                                       |
|--------------|------------------------------------------------------------------------------|
| `?auth_fail=1` | Login always rejects, even with `demo`/`demo`.                              |
| `?captcha=1` | Injects a fake reCAPTCHA iframe + `.g-recaptcha` div on login & form pages. |
| `?drift=1`   | Hides the new-submission form (selector-drift simulation).                  |

The flags propagate across navigation; the `submit.js` reads them at load time.

## Layout

```
fixtures/portals/
├── amtrust/
│   ├── index.html
│   ├── login.js
│   ├── dashboard.html
│   ├── new-submission.html
│   ├── confirmation.html
│   ├── submit.js
│   └── styles.css
├── markel/             (same layout)
├── applied-epic/       (same layout)
├── vertafore-ams360/   (same layout)
└── _nginx/
    ├── nginx.conf
    └── Dockerfile
```

Each fixture has intentionally heterogeneous field labels — see the
`FIELD_MAP` constants in `backend/app/automation/submitters/*.py` for the
canonical-key → portal-label mapping each submitter relies on.
