"""
WebSocket proxy between browser and Volcengine (火山) real-time voice API.

Browser <--ws--> This Server <--ws (binary protocol)--> Volcengine API

Protocol: Custom 4-byte header + optional fields + payload
"""
import asyncio
import json
import os
import struct
import uuid
import websockets
from auth import validate_session

VOLC_APP_ID = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")
VOLC_API_URL = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
VOLC_RESOURCE_ID = "volc.speech.dialog"
VOLC_APP_KEY = os.getenv("VOLC_APP_KEY", "")

# ─── Binary Protocol Helpers ─────────────────────────────

def build_text_frame(event_id: int, session_id: str, payload: dict) -> bytes:
    """Build a Full-client request frame (MessageType=0b0001) with event + session_id + JSON payload."""
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sid_bytes = session_id.encode("utf-8")
    sid_size = len(sid_bytes)

    # Header: [version|header_size] [msg_type|flags] [serial|compress] [reserved]
    # msg_type=0b0001 (Full-client), flags=0b0100 (has event)
    header = bytes([0x11, 0x14, 0x10, 0x00])

    # Event ID (4 bytes, little-endian)
    event_bytes = struct.pack("<I", event_id)

    # Session ID size (4 bytes) + Session ID
    sid_size_bytes = struct.pack("<I", sid_size)

    # Payload size (4 bytes)
    payload_size_bytes = struct.pack("<I", len(payload_bytes))

    return header + event_bytes + sid_size_bytes + sid_bytes + payload_size_bytes + payload_bytes


def build_audio_frame(session_id: str, audio_data: bytes, sequence: int = 0) -> bytes:
    """Build an Audio-only request frame (MessageType=0b0010)."""
    sid_bytes = session_id.encode("utf-8")
    sid_size = len(sid_bytes)

    # msg_type=0b0010 (Audio-only), flags=0b0001 (has sequence, not last)
    header = bytes([0x11, 0x21, 0x10, 0x00])

    # Sequence (4 bytes)
    seq_bytes = struct.pack("<I", sequence)

    # Session ID size + Session ID
    sid_size_bytes = struct.pack("<I", sid_size)

    # Payload size + Payload
    payload_size_bytes = struct.pack("<I", len(audio_data))

    return header + seq_bytes + sid_size_bytes + sid_bytes + payload_size_bytes + audio_data


def parse_frame(data: bytes):
    """Parse a server response frame. Returns dict with type, payload, etc."""
    if len(data) < 4:
        return None

    msg_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F

    offset = 4

    # Check for event (flags & 0b0100)
    has_event = (flags & 0x04) != 0
    event_id = None
    if has_event and len(data) >= offset + 4:
        event_id = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4

    # Check for sequence (flags & 0b0001 or 0b0010 or 0b0011)
    has_seq = (flags & 0x03) != 0 and not has_event  # simplified
    if has_seq and len(data) >= offset + 4:
        offset += 4  # skip sequence

    # Session ID
    if len(data) >= offset + 4:
        sid_size = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        if sid_size > 0 and len(data) >= offset + sid_size:
            offset += sid_size

    # Payload size + Payload
    payload = None
    if len(data) >= offset + 4:
        payload_size = struct.unpack("<I", data[offset:offset + 4])[0]
        offset += 4
        if payload_size > 0 and len(data) >= offset + payload_size:
            payload = data[offset:offset + payload_size]

    result = {"type": msg_type, "event_id": event_id}
    if payload:
        if msg_type == 0x09 or msg_type == 0x01:  # JSON text response
            try:
                result["json"] = json.loads(payload.decode("utf-8"))
            except Exception:
                result["text"] = payload.decode("utf-8", errors="replace")
        elif msg_type == 0x0B:  # Audio response
            result["audio"] = payload
        else:
            result["raw"] = payload
    return result


# ─── Active connections ──────────────────────────────────

active_calls = {}  # username -> {"volc_ws": ws, "session_id": str}


async def handle_voice(ws):
    """Handle a browser voice WebSocket connection."""
    await ws.accept()

    # Parse token from query
    token = ws.query_params.get("token", "")
    print(f"[voice] token={token[:20]}...")

    if not token:
        await ws.send_text(json.dumps({"type": "error", "message": "Missing token"}))
        await ws.close(4001)
        return

    user = validate_session(token)
    print(f"[voice] user={user}")
    if not user:
        await ws.send_text(json.dumps({"type": "error", "message": "Invalid or expired token"}))
        await ws.close(4001)
        return

    username = user["username"]
    print(f"[voice] {username} connected for oral_english")

    session_id = str(uuid.uuid4())
    volc_ws = None

    try:
        # Connect to Volcengine
        headers = {
            "X-Api-App-ID": VOLC_APP_ID,
            "X-Api-Access-Key": VOLC_ACCESS_KEY,
            "X-Api-Resource-Id": VOLC_RESOURCE_ID,
            "X-Api-App-Key": VOLC_APP_KEY,
        }
        volc_ws = await websockets.connect(VOLC_API_URL, extra_headers=headers)
        active_calls[username] = {"volc_ws": volc_ws, "session_id": session_id}

        # Start session: StartConnection + StartSession
        start_conn = build_text_frame(1, session_id, {})
        await volc_ws.send(start_conn)

        start_session = build_text_frame(100, session_id, {
            "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}},
            "dialog": {
                "bot_name": "English Teacher",
                "system_role": get_oral_english_prompt(),
                "speaking_style": "You are a friendly and patient English teacher helping a young Chinese student practice spoken English for the PET exam. Speak clearly and slowly. Encourage the student.",
                "extra": {"model": "1.2.1.1"}
            },
            "tts": {
                "speaker": "zh_female_vv_jupiter_bigtts",
                "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000}
            }
        })
        await volc_ws.send(start_session)

        # Send SayHello to greet the student
        hello = build_text_frame(300, session_id, {
            "content": "Hello! Welcome to your English speaking practice. How are you today?"
        })
        await volc_ws.send(hello)

        # Notify browser that we're connected
        await ws.send(json.dumps({"type": "ready", "session_id": session_id}))

        # Relay: browser audio → volc, volc responses → browser
        async def browser_to_volc():
            """Forward audio from browser to Volcengine."""
            seq = 0
            async for message in ws:
                if isinstance(message, bytes):
                    frame = build_audio_frame(session_id, message, seq)
                    await volc_ws.send(frame)
                    seq += 1
                elif isinstance(message, str):
                    data = json.loads(message)
                    if data.get("type") == "end_session":
                        finish = build_text_frame(102, session_id, {})
                        await volc_ws.send(finish)
                        break
                    elif data.get("type") == "text_query":
                        query = build_text_frame(501, session_id, {"content": data["content"]})
                        await volc_ws.send(query)

        async def volc_to_browser():
            """Forward text/audio from Volcengine to browser."""
            async for raw in volc_ws:
                frame = parse_frame(raw)
                if not frame:
                    continue

                event_id = frame.get("event_id")
                payload = frame.get("json") or {}

                if event_id == 150:  # SessionStarted
                    await ws.send(json.dumps({"type": "session_started", "dialog_id": payload.get("dialog_id", "")}))
                elif event_id == 451:  # ASRResponse — user speech recognized
                    await ws.send(json.dumps({"type": "asr", "text": payload.get("results", [{}])[0].get("text", "") if payload.get("results") else ""}))
                elif event_id == 550:  # ChatResponse — model text reply
                    await ws.send(json.dumps({"type": "chat_text", "content": payload.get("content", "")}))
                elif event_id == 350:  # TTSSentenceStart
                    await ws.send(json.dumps({"type": "tts_start", "text": payload.get("text", "")}))
                elif event_id == 352:  # TTSResponse — audio
                    if frame.get("audio"):
                        await ws.send(frame["audio"])
                elif event_id == 359:  # TTSEnded
                    await ws.send(json.dumps({"type": "tts_ended"}))
                elif event_id == 154:  # UsageResponse
                    pass  # ignore usage

        # Run both directions concurrently
        await asyncio.gather(browser_to_volc(), volc_to_browser())

    except websockets.exceptions.ConnectionClosed as x:
        print(f"[voice] conn closed: {x}")
    except Exception as e:
        print(f"[voice] Error: {e}")
        try:
            await ws.send(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if volc_ws:
            try:
                finish = build_text_frame(102, session_id, {})
                await volc_ws.send(finish)
                await asyncio.sleep(0.5)
                await volc_ws.close()
            except Exception:
                pass
        active_calls.pop(username, None)
        print(f"[voice] {username} disconnected")


def get_oral_english_prompt() -> str:
    """Load oral English system prompt."""
    path = "courses/oral_english/world_model.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Take first 500 chars as concise prompt for voice model
        return content[:500]
    return "You are an English teacher helping a student practice spoken English for the PET exam."
