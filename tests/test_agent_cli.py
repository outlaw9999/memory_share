import pytest

from kit_agent.cli.main import main


def test_agent_cli_returns_exit_code_2_on_invalid_contract(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["kit-agent", "ask", "bad output", "--json"],
    )
    monkeypatch.setattr("kit_agent.cli.main.MetricsPersistence.load_all", lambda self, metrics: metrics)
    monkeypatch.setattr("kit_agent.cli.main.AMSBProtocol.run", lambda *args, **kwargs: "not json")

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert "not json" in capsys.readouterr().out
