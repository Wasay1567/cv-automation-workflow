# cv-automation-workflow

## API Documentation (Frontend)

- `backend/API_FRONTEND.md`

## Local Installation

1. Copy `.env.example` to `.env` and set the values for your environment.

2. Start Docker containers:
    ```bash
    docker compose up -d
    ```

3. Create a virtual environment:
    ```bash
    python -m venv venv
    ```

4. Activate the virtual environment:
    ```bash
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

5. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

6. Run database migrations in the API server folder:
    ```bash
    cd apiserver
    alembic upgrade head
    ```

## EC2 Deployment

The `main` branch runs CI before deployment. CI compiles both Python services, validates Compose, and builds both images. The deployment job then connects to EC2 and:

- Installs Docker if the host is new and clones the repository if it is missing.
- Writes the GitHub secret `APP_ENV` to the host's `.env` file with restrictive permissions.
- Starts PostgreSQL once and waits for its health check. The named `postgres_data` volume is never removed by the workflow.
- Runs `alembic upgrade head` as a disposable backend container on the initial deployment or when `apiserver/alembic/` changes.
- Rebuilds and recreates only `backend` for API changes and only `cvgen` for generator changes. Environment changes recreate both application services, but never deliberately recreate PostgreSQL.

Create these GitHub repository secrets:

- `EC2_HOST`: public DNS name or IP address.
- `EC2_USER`: SSH user with Docker access or passwordless `sudo`.
- `EC2_SSH_KEY`: private SSH key for that user.
- `APP_ENV`: the complete contents of the production `.env` file, based on `.env.example`.

The EC2 security group should expose only the application ports required by clients (`8000` and, if direct cvGen access is needed, `8080`). PostgreSQL is internal to the Compose network and is not published to the host. Configure regular backups for the `postgres_data` volume; persistence prevents container recreation from deleting data, but it is not a backup strategy.