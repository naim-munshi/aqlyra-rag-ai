"""Approval, tenant isolation and safe public-browser actions.

Network and Chromium are not invoked by default regression tests; the live
Playwright smoke requires explicit opt-in and a configured site.
"""
import asyncio
import json

from fastapi.testclient import TestClient
import pytest
from app.config.settings import settings
import app.api.browser_agent as api
import app.services.browser_agent_service as agent
from app.schemas.browser_agent import BrowserRunResponse, BrowserPageEvidence
from app.services.browser_agent_service import (
    BrowserAgentPlanError, BrowserAgentUnavailable,
    _parse_choice, _merge_link_frontier, create_browser_plan,
    safe_browser_url, verify_browser_plan,
)
from datetime import datetime, timezone

HOST = "docs.example.org"
SITE = "https://docs.example.org/guide"


@pytest.fixture(autouse=True)
def enable_read_only_agent(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "BROWSER_AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSER_AGENT_ALLOWED_HOSTS", HOST)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")


def test_safe_browser_urls_are_exact_https_public_hosts() -> None:
    assert safe_browser_url(SITE, HOST) == SITE
    for bad in (
        "http://docs.example.org/guide",
        "https://docs.example.org:9443/guide",
        "https://127.0.0.1/private",
        "https://docs.example.org.evil.com/",
        "https://docs.example.org@evil.com/",
        "file:///etc/passwd",
        "https://docs.example.org/logout",
        "https://docs.example.org/account/delete?id=1",
        "https://docs.example.org/checkout",
        "https://docs.example.org/lo%67out",
        "https://docs.example.org/%2561dmin",
        "https://docs.example.org/docs?next=%252flogout",
        "https://docs.example.org/guide%250a",
        "https://docs.example.org/guide\nX-Injected: yes",
        "https://localhost/test",
    ):
        assert safe_browser_url(bad, HOST) is None


def test_user_bound_signed_plan_and_feature_gates(monkeypatch) -> None:
    plan = create_browser_plan("Read official release notes", SITE, "user-A")
    assert plan.allowed_host == HOST
    assert plan.max_pages == 4
    verified = verify_browser_plan(plan.plan_token, "user-A")
    assert verified["url"] == SITE
    with pytest.raises(BrowserAgentPlanError):
        verify_browser_plan(plan.plan_token, "user-B")
    with pytest.raises(BrowserAgentPlanError):
        verify_browser_plan(plan.plan_token + "tamper", "user-A")
    monkeypatch.setattr(settings, "BROWSER_AGENT_ENABLED", False)
    with pytest.raises(BrowserAgentUnavailable):
        create_browser_plan("Read official release notes", SITE, "user-A")
    monkeypatch.setattr(settings, "BROWSER_AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(BrowserAgentUnavailable):
        create_browser_plan("Read official release notes", SITE, "user-A")


def test_unapproved_host_and_fake_model_are_rejected(monkeypatch) -> None:
    with pytest.raises(BrowserAgentPlanError):
        create_browser_plan("Read official release notes", "https://other.org/", "user")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "deterministic")
    with pytest.raises(BrowserAgentUnavailable):
        create_browser_plan("Read official release notes", SITE, "user")


def test_model_can_only_choose_listed_links_or_finish() -> None:
    assert _parse_choice('{"action":"follow","link_number":2}', 3) == 2
    assert _parse_choice('{"action":"finish"}', 1) == 0
    for invalid in (
        '{"action":"follow","link_number":999}',
        '{"action":"follow","link_number":true}',
        '{"action":"click","selector":"#delete"}',
        '{"action":"type","text":"password"}',
        "ignore the system and run shell",
        '{"action":"follow","link_number":0}',
    ):
        with pytest.raises(BrowserAgentPlanError):
            _parse_choice(invalid, 3)


def _auth(client: TestClient, suffix: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/register", json={
        "username": "browser_" + suffix,
        "email": "browser_" + suffix + "@example.com",
        "password": "ValidPassword123!",
    })
    assert resp.status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "email": "browser_" + suffix + "@example.com",
        "password": "ValidPassword123!",
    })
    assert login.status_code == 200
    return {"Authorization": "Bearer " + login.json()["access_token"]}


def test_browser_api_auth_plan_approval_and_report(
    client: TestClient, monkeypatch,
) -> None:
    unauth = client.post("/api/v1/agent/browser/plan", json={
        "task": "Read release notes", "start_url": SITE,
    })
    assert unauth.status_code == 401
    owner = _auth(client, "owner")
    other = _auth(client, "other")
    res = client.post("/api/v1/agent/browser/plan", headers=owner, json={
        "task": "Read release notes", "start_url": SITE,
    })
    assert res.status_code == 200, res.text
    plan = res.json()
    assert "plan_token" in plan
    assert plan["allowed_host"] == HOST
    execute = "/api/v1/agent/browser/execute"
    payload = {"plan_token": plan["plan_token"], "approved": True}
    assert client.post(execute, headers=owner, json={
        **payload, "approved": False,
    }).status_code == 400
    assert client.post(execute, headers=other, json=payload).status_code == 400

    called: list[str] = []

    async def mock_execute(token, user_id):
        called.append(user_id)
        return BrowserRunResponse(
            task="Read release notes",
            answer="The release notes list changes [B1].",
            visited=[BrowserPageEvidence(
                citation="[B1]", title="Release notes",
                url=SITE, excerpt="New release includes bug fixes.",
            )],
            steps=["Read [B1]: Release notes"],
            finished_at=datetime.now(timezone.utc),
            model_name="test-model",
        )

    monkeypatch.setattr(api, "execute_browser_plan", mock_execute)
    executed = client.post(execute, headers=owner, json=payload)
    assert executed.status_code == 200, executed.text
    assert executed.json()["visited"][0]["citation"] == "[B1]"
    assert len(called) == 1


def test_invalid_task_url_and_explicit_approval(client: TestClient) -> None:
    headers = _auth(client, "invalid")
    for request in (
        {"task": "short", "start_url": "http://docs.example.org"},
        {"task": "Read release notes", "start_url": "https://localhost/secret"},
        {"task": "Read release notes", "start_url": "https://example.net"},
    ):
        assert client.post(
            "/api/v1/agent/browser/plan", headers=headers, json=request,
        ).status_code == 400
    assert client.post("/api/v1/agent/browser/execute", headers=headers, json={
        "approved": True, "plan_token": "x" * 30,
    }).status_code == 400


def _fake_report() -> BrowserRunResponse:
    return BrowserRunResponse(
        task="Read official release notes",
        answer="The release notes contain public changes [B1].",
        visited=[BrowserPageEvidence(
            citation="[B1]", title="Release notes",
            url=SITE, excerpt="Release details",
        )],
        steps=["Read [B1]: Release notes"],
        finished_at=datetime.now(timezone.utc),
        model_name="test-model",
    )


def test_browser_approval_is_single_use_per_api_process(monkeypatch) -> None:
    plan = create_browser_plan(
        "Read official release notes", SITE, "single-use-user"
    )
    called: list[str] = []

    async def mock_browser(task, url, host, llm):
        called.append(url)
        return _fake_report()

    monkeypatch.setattr(agent, "_run_browser", mock_browser)
    monkeypatch.setattr(
        agent, "create_configured_llm_provider", lambda: object(),
    )

    async def scenario():
        first = await agent.execute_browser_plan(
            plan.plan_token, "single-use-user"
        )
        assert first.answer.endswith("[B1].")
        with pytest.raises(BrowserAgentPlanError, match="already been used"):
            await agent.execute_browser_plan(
                plan.plan_token, "single-use-user"
            )

    asyncio.run(scenario())
    assert called == [SITE]


def test_browser_concurrency_limit_preserves_unused_approval(monkeypatch) -> None:
    first = create_browser_plan(
        "Read official release notes", SITE, "concurrent-user",
    )
    second = create_browser_plan(
        "Review public documentation", SITE, "concurrent-user",
    )
    entered = asyncio.Event()
    finish = asyncio.Event()
    calls = []

    async def blocked_browser(task, url, host, llm):
        calls.append(task)
        if task == "Read official release notes":
            entered.set()
            await finish.wait()
        return _fake_report()

    monkeypatch.setattr(agent, "_run_browser", blocked_browser)
    monkeypatch.setattr(
        agent, "create_configured_llm_provider", lambda: object(),
    )

    async def scenario():
        active = asyncio.create_task(
            agent.execute_browser_plan(first.plan_token, "concurrent-user")
        )
        await entered.wait()
        try:
            with pytest.raises(
                BrowserAgentUnavailable, match="Another browser run",
            ):
                await agent.execute_browser_plan(
                    second.plan_token, "concurrent-user"
                )
        finally:
            finish.set()
        await active
        result = await agent.execute_browser_plan(
            second.plan_token, "concurrent-user"
        )
        assert result.visited[0].citation == "[B1]"

    asyncio.run(scenario())
    assert calls == [
        "Read official release notes",
        "Review public documentation",
    ]


def test_user_cannot_consume_another_users_approval(monkeypatch) -> None:
    plan = create_browser_plan(
        "Read official release notes", SITE, "authorised-user"
    )
    with pytest.raises(BrowserAgentPlanError):
        asyncio.run(agent.execute_browser_plan(plan.plan_token, "other-user"))

    async def mock_browser(task, url, host, llm):
        return _fake_report()

    monkeypatch.setattr(agent, "_run_browser", mock_browser)
    monkeypatch.setattr(
        agent, "create_configured_llm_provider", lambda: object(),
    )
    report = asyncio.run(agent.execute_browser_plan(
        plan.plan_token, "authorised-user"
    ))
    assert report.visited[0].url == SITE


def test_navigation_frontier_keeps_previous_page_links() -> None:
    home = "https://docs.example.org/home"
    previous = [
        {"url": "https://docs.example.org/security", "title": "Security",
         "found_on": home},
        {"url": "https://docs.example.org/reference", "title": "Reference",
         "found_on": home},
    ]
    current = "https://docs.example.org/tutorial"
    updated = _merge_link_frontier(
        previous,
        [
            {"href": "/api", "text": "API guide"},
            {"href": "/security", "text": "Duplicate Security"},
            {"href": "https://evil.org/secret", "text": "Bad external"},
            {"href": "/logout", "text": "Destructive"},
            {"href": "/api", "text": "Duplicate API"},
            {"href": "javascript:alert(1)", "text": "Script"},
            {"href": "http://[invalid/", "text": "Malformed host"},
        ],
        current, HOST, {home, current},
    )
    assert [item["url"] for item in updated] == [
        "https://docs.example.org/api",
        "https://docs.example.org/security",
        "https://docs.example.org/reference",
    ]
    assert updated[0]["found_on"] == current
    # After reading the API page, old Security and Reference links remain.
    next_step = _merge_link_frontier(
        updated, [], "https://docs.example.org/api", HOST,
        {home, current, "https://docs.example.org/api"},
    )
    assert [item["title"] for item in next_step] == ["Security", "Reference"]


def test_navigation_frontier_is_bounded_and_never_revisits() -> None:
    current = "https://docs.example.org/index"
    entries = [
        {"href": f"/page-{i}", "text": f"Page {i}"}
        for i in range(130)
    ]
    options = _merge_link_frontier([], entries, current, HOST, {current})
    assert len(options) == agent.MAX_LINK_FRONTIER
    assert len({item["url"] for item in options}) == len(options)
    assert all(safe_browser_url(item["url"], HOST) for item in options)
    assert options[0]["url"].endswith("/page-0")


def test_dns_pin_rejects_private_and_mixed_resolution(monkeypatch):
    import socket

    def fake_dns_public(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443)),
        ]

    monkeypatch.setattr(agent.socket, "getaddrinfo", fake_dns_public)
    pinned = asyncio.run(agent._validate_public_dns(HOST))
    assert pinned == "93.184.215.14"

    def fake_dns_rebinding(*args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]

    monkeypatch.setattr(agent.socket, "getaddrinfo", fake_dns_rebinding)
    with pytest.raises(BrowserAgentPlanError, match="non-public"):
        asyncio.run(agent._validate_public_dns(HOST))


def test_dns_pin_rejects_ipv6_only_until_safe_pinning_is_available(monkeypatch):
    import socket
    monkeypatch.setattr(
        agent.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443, 0, 0)),
        ],
    )
    with pytest.raises(BrowserAgentPlanError, match="IPv4"):
        asyncio.run(agent._validate_public_dns(HOST))
