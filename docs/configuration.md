# Configuration and secrets

Kaleido reads deployment-specific configuration from environment variables. Do
not create a committed Python settings file containing secrets. Keep
`kaleido.env.example` in Git as the variable-name template, while real values live in
the operating system, CI/CD secret store, Docker/Kubernetes secret, or a
permission-restricted environment file outside the repository.

For local development, the application automatically loads `kaleido.env` from
the project root on both Windows and Linux. No `source` command is needed:

```powershell
D:\Python\PythonVirtualEnvironment\Kaleido\Scripts\python.exe manage.py runserver
```

Quote values containing spaces, `#`, `$`, `*`, or other shell metacharacters.
`kaleido.env` is ignored by Git. Process-level environment variables have higher
priority, so production-injected values are not overwritten by the local file.
Set `KALEIDO_ENV_FILE` only when a different local file path is required.

## Linux shell

Set variables for the current shell and child processes with `export`:

```bash
export KALEIDO_LLM_BASE_URL='https://provider.example/v1'
export KALEIDO_LLM_API_KEY='replace-with-the-real-key'
export DJANGO_SECRET_KEY='replace-with-a-long-random-value'
export KALEIDO_DB_PASSWORD='replace-with-the-database-password'
python manage.py runserver
```

This manual export method is optional because the project loads `kaleido.env`
itself. In a generic Bash workflow, `set -a` means "automatically export every
variable assigned after this point"; `set +a` turns that behavior off again.
That pair is commonly placed around `source some.env`, but it is not needed for
this project.

Environment variable names are case-sensitive on Linux. The legacy expression
`os.getenv("Kaleido_BASE_URL")` therefore requires the exact spelling:

```bash
export Kaleido_BASE_URL='https://provider.example/v1'
```

The code now prefers `KALEIDO_LLM_BASE_URL` and `KALEIDO_LLM_API_KEY`, following
the conventional uppercase naming style, while accepting the two legacy names
for compatibility.

Adding `export ...` to `~/.bashrc` makes it available to interactive Bash
sessions after `source ~/.bashrc`, but this is not recommended for production
secrets.

## systemd production service

Store real values outside the repository, for example in
`/etc/kaleido/kaleido.env`, owned by the service account with mode `600`:

```ini
DJANGO_SECRET_KEY=replace-with-a-long-random-value
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=api.example.com
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_HSTS_SECONDS=3600
KALEIDO_DB_PASSWORD=replace-with-the-database-password
KALEIDO_LLM_BASE_URL=https://provider.example/v1
KALEIDO_LLM_API_KEY=replace-with-the-real-key
```

Reference it from the systemd unit:

```ini
[Service]
EnvironmentFile=/etc/kaleido/kaleido.env
WorkingDirectory=/srv/kaleido
ExecStart=/srv/kaleido/.venv/bin/gunicorn Kaleido.wsgi:application
```

After changing the unit or environment file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart kaleido
```

Only enable HSTS after HTTPS works correctly for the whole site. Start with a
short duration and increase it gradually; add the subdomain and preload options
only when every applicable subdomain is permanently HTTPS-only.

Generate a new Django secret with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Use different secrets for development, testing, and production. If an API key,
database password, or Django secret was ever committed or shared, rotate it;
removing it from the current source file does not remove it from Git history.
