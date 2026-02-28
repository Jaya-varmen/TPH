#!/usr/bin/env sh
set -eu

echo "[entrypoint] waiting for db"
python -m app.wait_for_db

echo "[entrypoint] migrating"
python -m app.migrate

echo "[entrypoint] loading data"
python -m app.load_data

echo "[entrypoint] starting bot"
python -m app.bot
