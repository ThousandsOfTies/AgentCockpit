"""NXP Universal Update Utility setup option."""

from __future__ import annotations

from scripts.gar_lib.environments.setup_option import TargetEnvironmentSetupOption


class UuuEnvironment(TargetEnvironmentSetupOption):
    environment_id = "uuu"
    display_name = "NXP UUU image flash"
    description = "Target manifestが定義したhost-native UUUでNXP full imageを書き込みます"
    display_order = 10
    required_commands = ("uuu",)

    @classmethod
    def install_hint(cls, missing: list[str]) -> str:
        commands = ", ".join(missing)
        return (
            f"不足: {commands}\n"
            "WindowsではNXP mfgtoolsのuuu.exeをPATHへ追加してください。"
            " Linuxではuuuとlibusbを導入し、必要ならudev ruleを設定してください。"
            " Target manifestのcommand設定にsudoを埋め込まないでください。"
        )
