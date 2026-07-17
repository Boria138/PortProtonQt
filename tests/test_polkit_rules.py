from pathlib import Path


def test_polkit_rule_does_not_grant_application_privileges() -> None:
    rule_path = Path(__file__).parents[1] / (
        "build-aux/share/polkit-1/rules.d/ru.linux_gaming.PortProtonQt.rules"
    )
    rule = rule_path.read_text()

    assert "polkit.spawn" not in rule
    assert "ppqtos" not in rule
    assert "!subject.local || !subject.active ||" in rule
    assert '!subject.isInGroup("portprotonqt")' in rule


def test_portprotonqt_group_is_provisioned() -> None:
    sysusers_path = Path(__file__).parents[1] / (
        "build-aux/lib/sysusers.d/portprotonqt.conf"
    )

    assert sysusers_path.read_text() == "g portprotonqt - -\n"
