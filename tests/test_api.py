"""
Pytest test suite for the JustEats API.

Covers (≥ 10 tests):
  1.  register – success
  2.  register – duplicate email → 409
  3.  register – weak password → 422
  4.  login – success, tokens returned
  5.  login – wrong password → 401
  6.  JWT expiry – expired token → 401
  7.  CRUD restaurants – create / list / update / delete
  8.  Place order – happy path, total calculated correctly
  9.  Update order status – PENDING → CONFIRMED
  10. Customer profile – get & patch
  11. Favourites – add & list
  12. Recommendations – returns list

Run with:
    cd backend
    venv\\Scripts\\pytest          (Windows)
    source venv/bin/activate && pytest   (Unix)

Requires a reachable PostgreSQL instance at TEST_DATABASE_URL
(default: postgresql+asyncpg://postgres:postgres@localhost:5432/justeats_test).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import settings

PREFIX = "/api/v1"


# ─── Tiny helpers ─────────────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str, password: str, role: str = "customer"):
    return await client.post(
        f"{PREFIX}/auth/register",
        json={"email": email, "password": password, "role": role},
    )


async def _login(client: AsyncClient, email: str, password: str):
    return await client.post(
        f"{PREFIX}/auth/login",
        json={"email": email, "password": password},
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_token(client: AsyncClient, email: str = "owner@example.com") -> str:
    await _register(client, email, "Password123!", role="owner")
    r = await _login(client, email, "Password123!")
    return r.json()["access_token"]


async def _customer_token(client: AsyncClient, email: str = "cust@example.com") -> str:
    await _register(client, email, "Password123!")
    r = await _login(client, email, "Password123!")
    return r.json()["access_token"]


async def _ensure_profile(client: AsyncClient, token: str):
    """GET /profile creates the profile record automatically."""
    await client.get(f"{PREFIX}/profile", headers=_auth(token))


async def _create_restaurant(client: AsyncClient, token: str, name: str = "Test Bistro") -> dict:
    r = await client.post(
        f"{PREFIX}/restaurants",
        json={"name": name, "cuisine_type": "Fusion", "location": "London"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_menu_item(client: AsyncClient, token: str, restaurant_id: str, name: str = "Test Dish") -> dict:
    r = await client.post(
        f"{PREFIX}/restaurants/{restaurant_id}/menu-items",
        json={"name": name, "price": "9.99", "is_available": True},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════════
# 1 & 2 & 3 – Register
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_success(client):
    res = await _register(client, "new@example.com", "Secure123!")
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "new@example.com"
    assert data["role"] == "customer"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    await _register(client, "dup@example.com", "Secure123!")
    res = await _register(client, "dup@example.com", "Secure123!")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password_returns_422(client):
    res = await _register(client, "weak@example.com", "short")
    assert res.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 4 & 5 – Login
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_success_returns_token_pair(client):
    await _register(client, "login@example.com", "Secure123!")
    res = await _login(client, "login@example.com", "Secure123!")
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await _register(client, "badpw@example.com", "Secure123!")
    res = await _login(client, "badpw@example.com", "wrongpassword")
    assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 6 – JWT expiry
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_expired_jwt_returns_401(client):
    expired_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": "customer",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            "type": "access",
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    res = await client.get(f"{PREFIX}/auth/me", headers=_auth(expired_token))
    assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 7 – CRUD Restaurant
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_restaurant(client):
    token = await _owner_token(client)
    data = await _create_restaurant(client, token, "Burger Palace")
    assert data["name"] == "Burger Palace"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_list_restaurants_is_public(client):
    token = await _owner_token(client)
    await _create_restaurant(client, token, "Pizza Town")
    res = await client.get(f"{PREFIX}/restaurants")
    assert res.status_code == 200
    assert any(r["name"] == "Pizza Town" for r in res.json())


@pytest.mark.asyncio
async def test_update_restaurant(client):
    token = await _owner_token(client)
    restaurant = await _create_restaurant(client, token, "Old Name")
    res = await client.patch(
        f"{PREFIX}/restaurants/{restaurant['id']}",
        json={"name": "New Name", "cuisine_type": "Modern"},
        headers=_auth(token),
    )
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_restaurant(client):
    token = await _owner_token(client)
    restaurant = await _create_restaurant(client, token, "To Be Deleted")
    res = await client.delete(
        f"{PREFIX}/restaurants/{restaurant['id']}",
        headers=_auth(token),
    )
    assert res.status_code == 204
    # Confirm it no longer appears in list
    list_res = await client.get(f"{PREFIX}/restaurants")
    ids = [r["id"] for r in list_res.json()]
    assert restaurant["id"] not in ids


@pytest.mark.asyncio
async def test_create_restaurant_forbidden_for_customer(client):
    token = await _customer_token(client)
    res = await client.post(
        f"{PREFIX}/restaurants",
        json={"name": "Not Allowed"},
        headers=_auth(token),
    )
    assert res.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 8 – Place order
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_place_order_calculates_total(client):
    owner = await _owner_token(client, "owner2@example.com")
    cust = await _customer_token(client, "cust2@example.com")

    rest = await _create_restaurant(client, owner, "Order Test")
    item = await _create_menu_item(client, owner, rest["id"], "Test Dish")  # price 9.99

    await _ensure_profile(client, cust)

    res = await client.post(
        f"{PREFIX}/orders",
        json={
            "restaurant_id": rest["id"],
            "items": [{"menu_item_id": item["id"], "quantity": 2}],
        },
        headers=_auth(cust),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "PENDING"
    assert float(data["total_amount"]) == pytest.approx(19.98)
    assert len(data["order_items"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 9 – Update order status
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_update_order_status_pending_to_confirmed(client):
    owner = await _owner_token(client, "owner3@example.com")
    cust = await _customer_token(client, "cust3@example.com")

    rest = await _create_restaurant(client, owner, "Status Test")
    item = await _create_menu_item(client, owner, rest["id"])

    await _ensure_profile(client, cust)

    order_res = await client.post(
        f"{PREFIX}/orders",
        json={"restaurant_id": rest["id"], "items": [{"menu_item_id": item["id"], "quantity": 1}]},
        headers=_auth(cust),
    )
    order_id = order_res.json()["id"]

    res = await client.patch(
        f"{PREFIX}/orders/{order_id}/status",
        json={"status": "CONFIRMED"},
        headers=_auth(owner),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_invalid_order_status_transition_returns_422(client):
    owner = await _owner_token(client, "owner4@example.com")
    cust = await _customer_token(client, "cust4@example.com")

    rest = await _create_restaurant(client, owner, "Trans Test")
    item = await _create_menu_item(client, owner, rest["id"])
    await _ensure_profile(client, cust)

    order_res = await client.post(
        f"{PREFIX}/orders",
        json={"restaurant_id": rest["id"], "items": [{"menu_item_id": item["id"], "quantity": 1}]},
        headers=_auth(cust),
    )
    order_id = order_res.json()["id"]

    # Jump directly from PENDING → COMPLETED (invalid)
    res = await client.patch(
        f"{PREFIX}/orders/{order_id}/status",
        json={"status": "COMPLETED"},
        headers=_auth(owner),
    )
    assert res.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 10 – Customer profile
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_profile_creates_if_missing(client):
    token = await _customer_token(client, "prof@example.com")
    res = await client.get(f"{PREFIX}/profile", headers=_auth(token))
    assert res.status_code == 200
    assert "id" in res.json()
    assert "user_id" in res.json()


@pytest.mark.asyncio
async def test_update_profile(client):
    token = await _customer_token(client, "profupd@example.com")
    res = await client.patch(
        f"{PREFIX}/profile",
        json={"full_name": "Alice Smith", "phone": "+447911000099", "favourite_cuisine": "Japanese"},
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["full_name"] == "Alice Smith"
    assert data["favourite_cuisine"] == "Japanese"


# ═══════════════════════════════════════════════════════════════════════════════
# 11 – Favourites
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_add_and_list_favourites(client):
    owner = await _owner_token(client, "owner5@example.com")
    cust = await _customer_token(client, "cust5@example.com")
    await _ensure_profile(client, cust)

    rest = await _create_restaurant(client, owner, "Fave Spot")

    add_res = await client.post(f"{PREFIX}/favourites/{rest['id']}", headers=_auth(cust))
    assert add_res.status_code == 201

    list_res = await client.get(f"{PREFIX}/favourites", headers=_auth(cust))
    assert list_res.status_code == 200
    assert any(r["id"] == rest["id"] for r in list_res.json())


@pytest.mark.asyncio
async def test_add_favourite_twice_returns_409(client):
    owner = await _owner_token(client, "owner6@example.com")
    cust = await _customer_token(client, "cust6@example.com")
    await _ensure_profile(client, cust)

    rest = await _create_restaurant(client, owner, "Double Fave")

    await client.post(f"{PREFIX}/favourites/{rest['id']}", headers=_auth(cust))
    res = await client.post(f"{PREFIX}/favourites/{rest['id']}", headers=_auth(cust))
    assert res.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# 12 – Recommendations
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_recommendations_returns_list(client):
    """Without any completed orders, recommendations fall back to top-rated restaurants."""
    token = await _customer_token(client, "rec@example.com")
    await _ensure_profile(client, token)

    res = await client.get(f"{PREFIX}/recommendations", headers=_auth(token))
    assert res.status_code == 200
    assert isinstance(res.json(), list)
