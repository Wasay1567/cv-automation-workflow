# cv-automation-workflow

## Installation

1. Start Docker containers:
    ```bash
    docker compose up -d
    ```

2. Create a virtual environment:
    ```bash
    python -m venv venv
    ```

3. Activate the virtual environment:
    ```bash
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

4. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

5. Run database migrations in the backend folder:
    ```bash
    cd backend
    alembic upgrade head
    ```