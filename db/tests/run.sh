#!/bin/bash
# Runs inside the postgres container.
exec psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$1"
