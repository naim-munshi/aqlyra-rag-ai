"""Non-secret browser startup canary is disabled by default and bounded."""
from app.config.settings import settings
from app.services import browser_html_canary as canary


def test_browser_canary_off_does_not_touch_network(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_AGENT_HTML_CANARY_ON_STARTUP", False)
    assert canary.run_browser_html_canary() is False


def test_browser_canary_requires_all_three_security_gates(monkeypatch):
    monkeypatch.setattr(settings, "BROWSER_AGENT_HTML_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "BROWSER_AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSER_AGENT_HTML_ONLY_PRODUCTION_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSER_APPROVAL_REDIS_ENABLED", False)
    monkeypatch.setattr(settings, "BROWSER_AGENT_ALLOWED_HOSTS", "example.com")
    assert canary.run_browser_html_canary() is False


def test_browser_canary_uses_only_public_test_page(monkeypatch, caplog):
    import redis
    from app.services import browser_agent_service, browser_public_html_service
    monkeypatch.setattr(settings, "BROWSER_AGENT_HTML_CANARY_ON_STARTUP", True)
    monkeypatch.setattr(settings, "BROWSER_AGENT_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSER_AGENT_HTML_ONLY_PRODUCTION_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSER_APPROVAL_REDIS_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSER_AGENT_ALLOWED_HOSTS", "example.com")
    monkeypatch.setattr(settings, "REDIS_URL", "rediss://localhost:6379")
    class FakeRedis:
        def ping(self):
            return True
    monkeypatch.setattr(redis.Redis,"from_url",lambda *args,**kwargs:FakeRedis())
    async def pin(host):
        assert host=="example.com"
        return "93.184.216.34"
    monkeypatch.setattr(browser_agent_service,"_validate_public_dns",pin)
    seen=[]
    def read(url,host,ip):
        seen.append(url)
        return {"text":"Public documentation content"}
    monkeypatch.setattr(browser_public_html_service,"_read_public_snapshot",read)
    with caplog.at_level("INFO"):
        assert canary.run_browser_html_canary() is True
    assert seen==["https://example.com/"]
    assert "status=PASS" in caplog.text
    assert "localhost:6379" not in caplog.text
