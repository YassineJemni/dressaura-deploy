# DressAura backend deployment

Render should use `dressaura-backend` as its root directory and start the ASGI
application with `uvicorn main:app --host 0.0.0.0 --port $PORT`.

Configure `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` in the
Render environment. `SECRET_KEY` is also required; set it to a unique,
cryptographically random value in Render's environment settings and do not
commit it. Changing the key invalidates existing login tokens, so users will
need to sign in again.

Uploaded listing images are written under `app/uploads/dresses`. This is local
container storage, not durable object storage. Render's filesystem is
ephemeral unless a persistent disk is configured and mounted at that location;
use object storage for images that must survive deployments or instance
replacement.

The Vercel frontend defaults to this backend origin. Set `VITE_API_URL` in
Vercel only when deploying against a different backend origin; do not include
an `/api` prefix.

Install `requirements-test.txt` to run the backend regression suite, then run
`python -m unittest discover -s tests -v` from the backend directory.
