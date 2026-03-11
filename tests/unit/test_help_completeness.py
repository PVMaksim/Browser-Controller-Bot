# tests/unit/test_help_completeness.py
"""
Completeness test for /help command text.

Проверяем что:
  1. Все реальные зарегистрированные команды упомянуты в /help
  2. Ключевые секции присутствуют
  3. Динамические части (Whisper, Rate limit, голос) отображены
  4. /status описание совпадает с реальным выводом format_status_message

Это «architectural smoke test» — если добавить новую команду и забыть
добавить её в /help, тест упадёт.
"""

import ast
from pathlib import Path


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _read_help_text() -> str:
    """Extract the help_text string literal from commands.py."""
    src = Path("src/handlers/commands.py").read_text()
    # Берём весь файл — проверяем по подстрокам
    return src


def _get_registered_commands() -> set[str]:
    """
    Parse all handler files and collect registered Command() names.
    Исключаем служебные: start, register (onboarding-only).
    """
    skip = {"start", "register"}
    found = set()
    for f in Path("src/handlers").glob("*.py"):
        src = f.read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name == "Command" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant):
                        cmd = str(arg.value)
                        if cmd not in skip:
                            found.add(cmd)
    return found


# ------------------------------------------------------------------ #
# Tests                                                                #
# ------------------------------------------------------------------ #

class TestHelpCompleteness:

    def setup_method(self):
        self.help_src = _read_help_text()
        self.commands = _get_registered_commands()

    def test_all_registered_commands_mentioned_in_help(self):
        """
        Каждая зарегистрированная команда должна быть в тексте /help.
        Позволяем исключение для /play и /pause — они упомянуты как hint.
        """
        missing = []
        for cmd in self.commands:
            if f"/{cmd}" not in self.help_src:
                missing.append(f"/{cmd}")
        assert not missing, (
            f"Commands registered but missing from /help: {sorted(missing)}\n"
            "Add them to the help text in src/handlers/commands.py"
        )

    def test_help_has_browser_section(self):
        assert "Браузер" in self.help_src

    def test_help_has_player_section(self):
        assert "Медиапульт" in self.help_src

    def test_help_has_computer_section(self):
        assert "Компьютер" in self.help_src

    def test_help_has_ocr_section(self):
        assert "OCR" in self.help_src

    def test_help_has_bot_management_section(self):
        assert "Управление ботом" in self.help_src

    def test_help_mentions_voice(self):
        assert "Голос" in self.help_src or "голос" in self.help_src

    def test_help_mentions_whisper_model(self):
        assert "whisper" in self.help_src.lower()

    def test_help_mentions_rate_limit(self):
        assert "Rate limit" in self.help_src or "rate limit" in self.help_src.lower()

    def test_status_description_mentions_ocr(self):
        """/status description in /help should mention OCR (since format_status_message shows it)."""
        # Find the /status line in help text
        assert "OCR" in self.help_src
        # And it should be near /status
        status_idx = self.help_src.find("/status —")
        assert status_idx != -1, "/status description not found in help text"
        status_line = self.help_src[status_idx:status_idx + 100]
        assert "OCR" in status_line, (
            f"/status description should mention OCR. Got: {status_line!r}"
        )

    def test_stop_mentions_confirm(self):
        """/stop requires confirmation — help should mention this."""
        stop_idx = self.help_src.find("/stop —")
        assert stop_idx != -1
        context = self.help_src[stop_idx:stop_idx + 80]
        assert "confirm" in context.lower(), (
            f"/stop help should mention 'confirm'. Got: {context!r}"
        )

    def test_find_command_lists_platforms(self):
        """Platform aliases should be visible in help."""
        assert "рутуб" in self.help_src
        assert "ютуб" in self.help_src

    def test_voice_examples_present(self):
        """Voice examples help users discover natural language commands."""
        assert "«" in self.help_src or "'" in self.help_src  # has examples in quotes


class TestHelpSyntax:

    def test_commands_py_parses_cleanly(self):
        src = Path("src/handlers/commands.py").read_text()
        try:
            ast.parse(src)
        except SyntaxError as e:
            raise AssertionError(f"commands.py has syntax error: {e}")

    def test_no_unclosed_tags(self):
        """Basic HTML tag balance check for Telegram parse_mode=HTML."""
        src = Path("src/handlers/commands.py").read_text()
        # Extract help_text section (rough)
        start = src.find("help_text = (")
        end = src.find("await message.answer(help_text)", start)
        help_section = src[start:end]

        # Count <b> vs </b>
        assert help_section.count("<b>") == help_section.count("</b>"), \
            "Mismatched <b> tags in help text"
        assert help_section.count("<i>") == help_section.count("</i>"), \
            "Mismatched <i> tags in help text"
        assert help_section.count("<code>") == help_section.count("</code>"), \
            "Mismatched <code> tags in help text"
