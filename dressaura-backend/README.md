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

Older listings may still reference those local files. To migrate images that
are still available locally, configure the backend database and Cloudinary
environment variables in a trusted local environment, then run from
`dressaura-backend`:

```powershell
python -m scripts.migrate_legacy_images
python -m scripts.migrate_legacy_images --dry-run
```

Without `--apply`, the script is read-only: it reports eligible references and
missing local files without uploading or changing database rows. `--dry-run`
explicitly requests this same report. To perform uploads and update database
URLs, add `--apply` only after reviewing the report:

```powershell
python -m scripts.migrate_legacy_images --apply
```

Do not combine `--apply` with `--dry-run`; the script rejects conflicting
flags. The migration uses the actual `dresses`
and `dress_images` URL columns, preserves image order, skips existing
Cloudinary URLs, and assigns a deterministic content-hash public ID so an
interrupted migration can safely be rerun. It only resolves relative
`/uploads/dresses/` paths and absolute URLs from the configured
`--backend-origin` (defaulting to this deployment); files that are missing
from the selected local uploads directory are reported as unrecoverable.
Review the report and keep a database backup before running against production.

The Vercel frontend defaults to this backend origin. Set `VITE_API_URL` in
Vercel only when deploying against a different backend origin; do not include
an `/api` prefix.

Install `requirements-test.txt` to run the backend regression suite, then run
`python -m unittest discover -s tests -v` from the backend directory.
