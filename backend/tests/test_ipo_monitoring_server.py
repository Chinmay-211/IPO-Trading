import base64
import json
import urllib.error
import urllib.request
from datetime import time
import pytest

from backend.collectors.market_data.angel_one_instrument_resolver import AngelOneInstrumentResolver
from backend.services.ipo_listing_day_orchestrator import IPOListingDayOrchestrator
from backend.services.ipo_monitoring_server import IPOMonitoringServer
from backend.services.market_session_service import MarketSessionService


class DummyResolver(AngelOneInstrumentResolver):
    def __init__(self):
        self.instruments = {
            "DASHIPO": {"token": "9999", "symbol": "DASHIPO", "name": "DASHIPO LTD"}
        }

    def find(self, symbol: str):
        sym = symbol.strip().upper()
        if sym in self.instruments:
            return self.instruments[sym]
        raise ValueError(f"Unknown {symbol}")


def auth_request(
    url: str,
    username: str = "Anish_5337",
    password: str = "Anish_9482",
    data: bytes | None = None,
    method: str | None = None,
    headers: dict | None = None,
) -> urllib.request.Request:
    req_headers = dict(headers or {})
    if username is not None and password is not None:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
        req_headers["Authorization"] = f"Basic {token}"
    return urllib.request.Request(url, data=data, headers=req_headers, method=method)


@pytest.fixture
def running_server():
    resolver = DummyResolver()
    session_svc = MarketSessionService.for_ipo_listing(
        listing_open=time(10, 0),
        market_close=time(15, 30),
    )
    orchestrator = IPOListingDayOrchestrator(
        instrument_resolver=resolver,
        session_service=session_svc,
        default_quantity=10,
        slippage_pct=0.001,
    )
    orchestrator.prepare_session([{"symbol": "DASHIPO"}])

    server = IPOMonitoringServer(
        orchestrator=orchestrator,
        host="127.0.0.1",
        port=0,
        auth_username="Anish_5337",
        auth_password="Anish_9482",
    )
    server.start()
    base_url = f"http://127.0.0.1:{server.port}"

    yield server, base_url, orchestrator

    server.stop()


def test_unauthorized_without_credentials_rejected(running_server):
    _, base_url, _ = running_server
    # API access without authorization must fail with 401
    req = urllib.request.Request(f"{base_url}/api/status")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 401


def test_unauthorized_with_wrong_password_rejected(running_server):
    _, base_url, _ = running_server
    # Invalid password must fail with 401
    req = auth_request(f"{base_url}/api/status", username="Anish_5337", password="wrongpassword")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 401


def test_dashboard_html_served_when_authenticated(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        assert "<!DOCTYPE html>" in content
        assert "100% Paper Trading Only" in content
        assert "IPO Intelligence Terminal" in content
        assert "Anish_5337" not in content  # Username must not be exposed in HTML


def test_api_status_endpoint(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/api/status")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["is_running"] is False
        assert data["status"] == "READY"
        assert "DASHIPO" in data["registered_symbols"]


def test_api_ipos_endpoint(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/api/ipos")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert len(data["registered_ipos"]) == 1
        assert data["registered_ipos"][0]["symbol"] == "DASHIPO"
        assert data["token_to_symbol"]["9999"] == "DASHIPO"


def test_api_report_and_orders_endpoint(running_server):
    _, base_url, _ = running_server
    req_report = auth_request(f"{base_url}/api/report")
    with urllib.request.urlopen(req_report) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["status"] == "READY"
        assert data["slippage_pct"] == 0.001
        assert "DASHIPO" in data["ipo_breakdown"]

    req_orders = auth_request(f"{base_url}/api/orders")
    with urllib.request.urlopen(req_orders) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert isinstance(data["orders"], list)


def test_api_404_not_found(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/api/unknown_route")
    try:
        urllib.request.urlopen(req)
        assert False, "Should have failed with 404"
    except urllib.error.HTTPError as err:
        assert err.code == 404


def test_cors_options_allowed_without_auth(running_server):
    _, base_url, _ = running_server
    req = urllib.request.Request(f"{base_url}/api/status", method="OPTIONS")
    with urllib.request.urlopen(req) as response:
        assert response.status == 204
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in response.headers.get("Access-Control-Allow-Methods", "")


def test_api_candles_endpoint(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/api/candles?symbol=DASHIPO")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["symbol"] == "DASHIPO"
        assert isinstance(data["candles"], list)


def test_api_post_tick_authenticated(running_server):
    _, base_url, _ = running_server
    payload = json.dumps({"symbol": "DASHIPO", "price": 102.5, "volume": 150}).encode("utf-8")
    req = auth_request(
        f"{base_url}/api/tick",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["status"] == "OK"
        assert data["tick"]["symbol"] == "DASHIPO"
        assert data["tick"]["price"] == 102.5


def test_api_post_tick_unauthorized_rejected(running_server):
    _, base_url, _ = running_server
    payload = json.dumps({"symbol": "DASHIPO", "price": 102.5, "volume": 150}).encode("utf-8")
    # POST without Authorization header must be rejected with 401
    req = urllib.request.Request(
        f"{base_url}/api/tick",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 401


def test_api_post_eod_exit_authenticated(running_server):
    _, base_url, _ = running_server
    req = auth_request(
        f"{base_url}/api/eod_exit",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["status"] == "CLOSED"


def test_api_matrix_endpoint(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/api/matrix")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "matrix" in data
        assert isinstance(data["matrix"], list)


def test_api_activity_endpoint(running_server):
    _, base_url, _ = running_server
    req = auth_request(f"{base_url}/api/activity")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "activity" in data
        assert isinstance(data["activity"], list)
        assert len(data["activity"]) >= 1


def test_api_post_ipo_select_and_deselect(running_server):
    _, base_url, _ = running_server
    # 1. Select a new IPO
    payload = json.dumps({
        "action": "select",
        "symbol": "MANUALIPO",
        "company_name": "Manual Selected Ltd",
        "issue_price": 250.0,
    }).encode("utf-8")
    req = auth_request(
        f"{base_url}/api/ipos/select",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["status"] == "OK"
        assert data["action"] == "selected"
        assert data["symbol"] == "MANUALIPO"
        assert "MANUALIPO" in data["registered_symbols"]
        assert any(r["symbol"] == "MANUALIPO" for r in data["registered_ipos"])

    # 2. Deselect the IPO
    deselect_payload = json.dumps({
        "action": "deselect",
        "symbol": "MANUALIPO",
    }).encode("utf-8")
    req2 = auth_request(
        f"{base_url}/api/ipos/select",
        data=deselect_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req2) as response2:
        assert response2.status == 200
        data2 = json.loads(response2.read().decode("utf-8"))
        assert data2["status"] == "OK"
        assert data2["action"] == "deselected"
        assert "MANUALIPO" not in data2["registered_symbols"]


def test_api_post_ipo_select_auto_derives_symbol(running_server):
    _, base_url, _ = running_server
    payload = json.dumps({
        "action": "select",
        "symbol": "",
        "company_name": "Pranav Constructions Limited",
        "issue_price": 120.0,
    }).encode("utf-8")
    req = auth_request(
        f"{base_url}/api/ipos/select",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data["status"] == "OK"
        assert data["symbol"] == "PRANAV"
        assert "PRANAV" in data["registered_symbols"]


def test_screening_matrix_chronological_listing_date_order(monkeypatch):
    from datetime import date, timedelta
    from backend.services.ipo_monitoring_server import get_recent_screening_matrix

    today = date.today()
    d1 = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    d2 = (today + timedelta(days=5)).strftime("%Y-%m-%d")

    fake_runs = [
        {
            "id": 1,
            "chittorgarh_ipo_id": 101,
            "company_name": "Far Future IPO Ltd.",
            "screened_at": "2026-09-12T10:00:00",
            "strategy_result": "PASS",
            "passed": 13,
            "failed": 0,
            "listing_date": d2,
            "ipo_open_date": "2026-09-10",
            "ipo_close_date": "2026-09-12",
            "issue_price": "500",
            "symbol": "FARFUT",
        },
        {
            "id": 2,
            "chittorgarh_ipo_id": 102,
            "company_name": "TBD Listing IPO Ltd.",
            "screened_at": "2026-09-12T10:05:00",
            "strategy_result": "WATCHING",
            "passed": 10,
            "failed": 3,
            "listing_date": "",
            "ipo_open_date": "",
            "ipo_close_date": "",
            "issue_price": "200",
            "symbol": "TBDIPO",
        },
        {
            "id": 3,
            "chittorgarh_ipo_id": 103,
            "company_name": "Near Future IPO Ltd.",
            "screened_at": "2026-09-12T10:10:00",
            "strategy_result": "PASS",
            "passed": 13,
            "failed": 0,
            "listing_date": d1,
            "ipo_open_date": "2026-09-08",
            "ipo_close_date": "2026-09-10",
            "issue_price": "1000",
            "symbol": "NEARFUT",
        },
    ]

    class FakeCursor:
        def fetchall(self):
            return fake_runs

    class FakeConn:
        def execute(self, query, params=None):
            if "ipo_screening_rule_results" in query:
                class EmptyCursor:
                    def fetchall(self):
                        return []
                return EmptyCursor()
            return FakeCursor()

        def close(self):
            pass

    import backend.storage.database as db_mod
    monkeypatch.setattr(db_mod, "get_connection", lambda: FakeConn())

    matrix = get_recent_screening_matrix()
    assert len(matrix) == 3
    # 1. Earliest upcoming listing date must be first
    assert matrix[0]["company_name"] == "Near Future IPO Ltd."
    assert matrix[0]["listing_date"] == (today + timedelta(days=2)).strftime("%d-%b-%Y")
    assert "(T+3)" not in matrix[0]["listing_date"]

    # 2. Subsequent upcoming listing date must be second
    assert matrix[1]["company_name"] == "Far Future IPO Ltd."
    assert matrix[1]["listing_date"] == (today + timedelta(days=5)).strftime("%d-%b-%Y")
    assert "(T+3)" not in matrix[1]["listing_date"]

    # 3. TBD IPO must be ordered last
    assert matrix[2]["company_name"] == "TBD Listing IPO Ltd."
    assert matrix[2]["listing_date"] == "TBD"

