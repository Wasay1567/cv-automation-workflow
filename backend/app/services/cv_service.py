from typing import Optional
from uuid import uuid4

# In-memory store for demonstration purposes.
# NOTE: Not thread-safe. For production use with multiple workers,
# replace with a persistent store (e.g., a database) or protect
# mutations with a threading.Lock.
_cv_store: dict = {}


def create_cv(data: dict) -> dict:
    cv_id = str(uuid4())
    cv = {"id": cv_id, **data}
    _cv_store[cv_id] = cv
    return cv


def get_cv(cv_id: str) -> Optional[dict]:
    return _cv_store.get(cv_id)


def list_cvs() -> list[dict]:
    return list(_cv_store.values())


def delete_cv(cv_id: str) -> bool:
    if cv_id in _cv_store:
        del _cv_store[cv_id]
        return True
    return False
