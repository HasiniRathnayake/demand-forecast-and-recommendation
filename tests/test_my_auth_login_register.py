"""
Tests owned by customer auth scope:
- registration and login workflows
- input validation and password checks
"""

from __future__ import annotations


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, store: dict[str, list[dict]], table_name: str):
        self.store = store
        self.table_name = table_name
        self._op = None
        self._payload = None
        self._columns = None
        self._filters = []
        self._limit = None
        self._on_conflict = None

    def select(self, columns: str):
        self._op = "select"
        self._columns = columns
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def ilike(self, key, value):
        self._filters.append(("ilike", key, value))
        return self

    def in_(self, key, values):
        self._filters.append(("in", key, list(values)))
        return self

    def limit(self, n):
        self._limit = int(n)
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, payload: dict):
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def upsert(self, payload: dict, on_conflict: str | None = None):
        self._op = "upsert"
        self._payload = dict(payload)
        self._on_conflict = on_conflict
        return self

    def update(self, payload: dict):
        self._op = "update"
        self._payload = dict(payload)
        return self

    def execute(self):
        table = self.store.setdefault(self.table_name, [])

        def _match(row):
            for ftype, key, value in self._filters:
                rv = row.get(key)
                if ftype == "eq" and rv != value:
                    return False
                if ftype == "ilike":
                    if str(rv or "").lower() != str(value or "").lower():
                        return False
                if ftype == "in" and rv not in value:
                    return False
            return True

        if self._op == "insert":
            payload = dict(self._payload or {})
            if self.table_name == "users" and "user_id" not in payload:
                max_id = max([int(r.get("user_id", 0)) for r in table], default=0)
                payload["user_id"] = max_id + 1
            table.append(payload)
            return _Response([payload])

        if self._op == "upsert":
            payload = dict(self._payload or {})
            if self._on_conflict:
                key = self._on_conflict
                existing = next((r for r in table if r.get(key) == payload.get(key)), None)
                if existing:
                    existing.update(payload)
                    return _Response([existing])
            table.append(payload)
            return _Response([payload])

        if self._op == "update":
            matched = [r for r in table if _match(r)]
            for r in matched:
                r.update(self._payload or {})
            return _Response(matched)

        rows = [r.copy() for r in table if _match(r)]
        if self._limit is not None:
            rows = rows[: self._limit]
        if self._columns and self._columns != "*":
            cols = [c.strip() for c in self._columns.split(",")]
            rows = [{c: row.get(c) for c in cols} for row in rows]
        return _Response(rows)


class _FakeClient:
    def __init__(self, initial_store: dict[str, list[dict]] | None = None):
        self.store = initial_store or {
            "users": [],
            "customers": [],
            "staff_approvals": [],
            "suppliers": [],
        }

    def table(self, table_name: str):
        return _Query(self.store, table_name)


def test_hash_and_verify_password_roundtrip():
    from services.auth_service import hash_password, verify_password

    hashed = hash_password("secret123")
    assert isinstance(hashed, str)
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_validate_registration_inputs_detects_common_errors():
    from services.auth_service import validate_registration_inputs

    errors = validate_registration_inputs("ab", "bad-email", "123", "456", "unknown")
    assert len(errors) >= 4


def test_validate_login_inputs_requires_username_and_password():
    from services.auth_service import validate_login_inputs

    errs = validate_login_inputs("", "")
    assert len(errs) == 2


def test_register_customer_success_updates_user_customer_link(monkeypatch):
    from services import auth_service

    fake_client = _FakeClient()
    monkeypatch.setattr(auth_service, "get_client", lambda: fake_client)
    monkeypatch.setattr(auth_service, "hash_password", lambda _pw: "hashed_pw")
    monkeypatch.setattr(auth_service, "_create_customer_profile", lambda *_args, **_kwargs: "CUST0001")

    ok, msg = auth_service.register_user("Nimal", "nimal@example.com", "secret123", role="customer")

    assert ok is True
    assert "Account created" in msg
    users = fake_client.store["users"]
    assert len(users) == 1
    assert users[0]["username"] == "nimal"
    assert users[0]["email"] == "nimal@example.com"
    assert users[0]["customer_id"] == "CUST0001"


def test_register_user_rejects_duplicate_username(monkeypatch):
    from services import auth_service

    fake_client = _FakeClient(
        {
            "users": [
                {"user_id": 1, "username": "existing", "email": "x@example.com", "password_hash": "h", "role": "customer"}
            ],
            "customers": [],
            "staff_approvals": [],
            "suppliers": [],
        }
    )
    monkeypatch.setattr(auth_service, "get_client", lambda: fake_client)

    ok, msg = auth_service.register_user("existing", "new@example.com", "secret123", role="customer")

    assert ok is False
    assert "Username already taken" in msg


def test_register_supplier_requires_supplier_id(monkeypatch):
    from services import auth_service

    fake_client = _FakeClient()
    monkeypatch.setattr(auth_service, "get_client", lambda: fake_client)

    ok, msg = auth_service.register_user("supp1", "supp@example.com", "secret123", role="supplier", supplier_id="")

    assert ok is False
    assert "Supplier ID" in msg


def test_login_customer_success_resolves_and_persists_customer_id(monkeypatch):
    from services import auth_service

    hashed = auth_service.hash_password("secret123")
    fake_client = _FakeClient(
        {
            "users": [
                {
                    "user_id": 10,
                    "username": "nimal",
                    "email": "nimal@example.com",
                    "role": "customer",
                    "password_hash": hashed,
                    "customer_id": None,
                    "supplier_id": None,
                }
            ],
            "customers": [
                {"customer_id": "CUST0042", "email": "nimal@example.com"}
            ],
            "staff_approvals": [],
            "suppliers": [],
        }
    )

    monkeypatch.setattr(auth_service, "get_client", lambda: fake_client)

    ok, msg, user = auth_service.login_user("nimal", "secret123")

    assert ok is True
    assert "Welcome back" in msg
    assert user is not None
    assert user.get("customer_id") == "CUST0042"
    assert "password_hash" not in user
    assert fake_client.store["users"][0].get("customer_id") == "CUST0042"


def test_login_staff_blocked_when_pending_approval(monkeypatch):
    from services import auth_service

    hashed = auth_service.hash_password("secret123")
    fake_client = _FakeClient(
        {
            "users": [
                {
                    "user_id": 12,
                    "username": "staff1",
                    "email": "staff@example.com",
                    "role": "staff",
                    "password_hash": hashed,
                    "customer_id": None,
                    "supplier_id": None,
                }
            ],
            "customers": [],
            "staff_approvals": [
                {"user_id": 12, "approval_status": auth_service.APPROVAL_PENDING}
            ],
            "suppliers": [],
        }
    )
    monkeypatch.setattr(auth_service, "get_client", lambda: fake_client)

    ok, msg, user = auth_service.login_user("staff1", "secret123")

    assert ok is False
    assert user is None
    assert "pending" in msg.lower()
