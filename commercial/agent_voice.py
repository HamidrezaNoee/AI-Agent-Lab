"""Bounded voice input/output using the configured official OpenAI client."""

from .meeting_agent import configured_client, AgentUnavailable, AgentInvalid
from .setup_console import get_setting

MAX_AUDIO = 8 * 1024 * 1024
FORMATS = {
    "audio/webm": ("webm", b"\x1aE\xdf\xa3"),
    "audio/ogg": ("ogg", b"OggS"),
    "audio/wav": ("wav", b"RIFF"),
    "audio/x-wav": ("wav", b"RIFF"),
    "audio/mpeg": ("mp3", None),
    "audio/mp4": ("m4a", None),
    "video/mp4": ("mp4", None),
}


def configuration():
    cfg = get_setting("ai") or {}
    if not cfg.get("voice_enabled"):
        raise AgentUnavailable("قابلیت صوت در تنظیمات مدیر فعال نیست.")
    return cfg


def audio_format(data, content_type):
    mime = content_type.split(";")[0].lower()
    if mime not in FORMATS or not 16 <= len(data) <= MAX_AUDIO:
        raise AgentInvalid("Invalid audio size or type")
    extension, magic = FORMATS[mime]
    valid = (
        data.startswith(magic)
        if magic
        else (
            (data.startswith(b"ID3") or data[0] == 255 and data[1] & 224 == 224)
            if mime == "audio/mpeg"
            else data[4:8] == b"ftyp"
        )
    )
    if not valid:
        raise AgentInvalid("Audio content does not match its type")
    return extension, mime


def transcribe(data, content_type):
    cfg = configuration()
    extension, mime = audio_format(data, content_type)
    client, _ = configured_client()
    try:
        response = client.audio.transcriptions.create(
            model=cfg.get("transcription_model", "gpt-4o-mini-transcribe"),
            file=("recording." + extension, data, mime),
            language="fa",
            response_format="json",
            timeout=60,
        )
        text = response.text.strip()
        if not text or len(text) > 18000:
            raise AgentInvalid("Transcript empty or too long")
        return text
    except AgentInvalid:
        raise
    except Exception as exc:
        raise AgentUnavailable(
            "تبدیل صوت به متن انجام نشد؛ اتصال و مدل صوت بررسی شود."
        ) from exc
    finally:
        client.close()


def speech_parts(answer):
    # No fresh generation: read exactly the already reviewed structured answer.
    text = "\n".join(
        [
            {"fact": "یافته: ", "analysis": "تحلیل: ", "recommendation": "پیشنهاد: "}[
                c["kind"]
            ]
            + c["text"]
            for c in answer.get("claims", [])
        ]
    )
    if answer.get("clarification"):
        text += "\n" + answer["clarification"]
    text += "\n" + "\n".join(answer.get("notes", []))
    return [text[i : i + 3000] for i in range(0, len(text), 3000)]


def speak(answer, part):
    cfg = configuration()
    parts = speech_parts(answer)
    if not 0 <= part < len(parts):
        raise AgentInvalid("Invalid speech segment")
    client, _ = configured_client()
    try:
        response = client.audio.speech.create(
            model=cfg.get("speech_model", "gpt-4o-mini-tts"),
            voice=cfg.get("voice", "alloy"),
            input=parts[part],
            response_format="mp3",
            timeout=60,
        )
        data = response.content
        if not data or len(data) > MAX_AUDIO:
            raise AgentInvalid("Invalid speech response")
        return data, len(parts)
    except AgentInvalid:
        raise
    except Exception as exc:
        raise AgentUnavailable(
            "تولید پاسخ صوتی انجام نشد؛ اتصال و مدل صوت بررسی شود."
        ) from exc
    finally:
        client.close()
