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

