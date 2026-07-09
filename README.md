# Blue cloud Softech - DOPAMS ADVANCE ETL

## Local PostgreSQL + pgAdmin

This repository includes a local Docker stack for Postgres, pgvector, and pgAdmin.

1. Copy `.env.example` to `.env` and adjust the passwords or ports if needed.
2. Start the stack with `docker compose up -d`.
3. Open pgAdmin at `http://localhost:5050` and sign in with `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` from `.env`.
4. Add a new server in pgAdmin with host `postgres` if you are connecting from inside the Docker network, or `localhost` and port `5433` if you are connecting from your host machine.

The default local database is `cctns_etl` with user `cctns_local`. The host port is `5433` so it can coexist with a PostgreSQL service already using the standard `5432` port.

The ETL code already reads the standard `POSTGRES_*` variables, so no application code changes are required for local database use.
