# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.

## Run TrustVault

Start the FastAPI backend from the `backend` directory after configuring
`DATABASE_URL` and `JWT_SECRET_KEY` in its environment:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The backend defaults to the Vite development origins on ports 5173 and 5174.
Set `CORS_ORIGINS` to a comma-separated list of exact frontend origins when
using another local port or deploying.

Start the frontend from the `frontend` directory:

```powershell
npm install
npm run dev
```

The frontend uses `http://127.0.0.1:8000` by default for the API. Set
`VITE_API_BASE_URL` before building to use a different backend URL. Build with
`npm run build`; run backend tests from `backend` with `python -m pytest -v`.

For production, provide a strong secret key and production database URL through
the hosting environment, set `CORS_ORIGINS` and `VITE_API_BASE_URL` to the
deployed origins, and serve the frontend and API over HTTPS.

## Administrator dashboard

Accounts are registered as `USER`. An administrator must be assigned through a
trusted administrative process before opening `/admin`; every admin API is
independently protected by the backend. The dashboard manages account roles and
status and document metadata, but does not grant admins access to private file
contents. On ownership transfer, existing viewer grants are retained, except an
active viewer grant belonging to the new owner is marked revoked (not deleted).
