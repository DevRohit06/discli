from discli.security import is_command_allowed


def test_readonly_denies_voice_join():
    assert not is_command_allowed("voice join", profile_override="readonly")


def test_readonly_allows_voice_status():
    assert is_command_allowed("voice status", profile_override="readonly")


def test_chat_allows_interact():
    assert is_command_allowed("interact modal", profile_override="chat")


def test_chat_denies_voice():
    assert not is_command_allowed("voice join", profile_override="chat")


def test_full_allows_voice():
    assert is_command_allowed("voice join", profile_override="full")


def test_full_allows_interact():
    assert is_command_allowed("interact dashboard create", profile_override="full")


def test_moderation_allows_voice():
    assert is_command_allowed("voice join", profile_override="moderation")


def test_moderation_allows_interact():
    assert is_command_allowed("interact workflow start", profile_override="moderation")
