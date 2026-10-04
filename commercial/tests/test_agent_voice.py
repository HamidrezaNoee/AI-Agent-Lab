from commercial import agent_voice
from commercial.meeting_agent import AgentInvalid
import pytest


def test_browser_webm_is_detected_even_when_content_type_is_generic():
    data=b"\x1aE\xdf\xa3"+b"\x00"*128
    extension,mime=agent_voice.audio_format(data,"application/octet-stream")
    assert extension=="webm"
    assert mime=="audio/webm"


def test_browser_webm_can_recover_from_wrong_declared_audio_type():
    data=b"\x1aE\xdf\xa3"+b"\x00"*128
    extension,mime=agent_voice.audio_format(data,"audio/mp4")
    assert extension=="webm"
    assert mime=="audio/webm"


def test_mp4_ftyp_is_sniffed_with_browser_container_header():
    data=b"\x00\x00\x00\x18ftypM4A "+b"\x00"*128
    extension,mime=agent_voice.audio_format(data,"application/octet-stream")
    assert extension=="m4a"
    assert mime=="audio/mp4"


def test_invalid_audio_returns_validation_error():
    with pytest.raises(AgentInvalid):
        agent_voice.audio_format(b"not audio bytes at all","application/octet-stream")
