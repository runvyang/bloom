"""
WebSocket proxy between browser and Volcengine real-time voice API.

Browser <--ws (FastAPI)--> This Server <--ws (binary protocol)--> Volcengine API
"""
import asyncio
import json
import os
import struct
import uuid
import traceback
import websockets
from auth import validate_session

VOLC_APP_ID = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")
VOLC_API_URL = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
VOLC_RESOURCE_ID = "volc.speech.dialog"
VOLC_APP_KEY = os.getenv("VOLC_APP_KEY", "")


def build_text_frame(event_id: int, session_id: str, payload: dict) -> bytes:
    """Build text frame. For Connect events (1,2), session_id is ignored (no sid field).
    For Session events (100,102,300,etc), session_id is included."""
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header = bytes([0x11, 0x14, 0x10, 0x00])
    event_bytes = struct.pack(">I", event_id)

    # Connect events (1,2) have NO session_id per doc example
    if event_id in (1, 2):
        payload_size_bytes = struct.pack(">I", len(payload_bytes))
        return header + event_bytes + payload_size_bytes + payload_bytes

    sid_bytes = session_id.encode("utf-8")
    sid_size_bytes = struct.pack(">I", len(sid_bytes))
    payload_size_bytes = struct.pack(">I", len(payload_bytes))
    return header + event_bytes + sid_size_bytes + sid_bytes + payload_size_bytes + payload_bytes


def build_audio_frame(session_id: str, audio_data: bytes, sequence: int = 0) -> bytes:
    # Audio frames (msg_type=0b0010): header + payload only — NO sequence, let server track
    # flags = 0b0000 (no sequence, no event)
    header = bytes([0x11, 0x20, 0x10, 0x00])
    payload_size_bytes = struct.pack(">I", len(audio_data))
    return header + payload_size_bytes + audio_data


def parse_frame(data: bytes):
    if len(data) < 4:
        return None
    msg_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    offset = 4

    # Error frames (msg_type=0x0F): code(4) then payload_size+payload
    error_code = None
    if msg_type == 0x0F and len(data) >= offset + 4:
        error_code = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        payload = None
        if len(data) >= offset + 4:
            payload_size = struct.unpack(">I", data[offset:offset + 4])[0]
            offset += 4
            if payload_size > 0 and len(data) >= offset + payload_size:
                payload = data[offset:offset + payload_size]
        result = {"type": msg_type, "error_code": error_code}
        if payload:
            try:
                result["json"] = json.loads(payload.decode("utf-8"))
            except Exception:
                result["text"] = payload.decode("utf-8", errors="replace")
        return result

    has_event = (flags & 0x04) != 0
    event_id = None
    if has_event and len(data) >= offset + 4:
        event_id = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
    if len(data) >= offset + 4:
        sid_size = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        if sid_size > 0 and len(data) >= offset + sid_size:
            offset += sid_size
    payload = None
    if len(data) >= offset + 4:
        payload_size = struct.unpack(">I", data[offset:offset + 4])[0]
        offset += 4
        if payload_size > 0 and len(data) >= offset + payload_size:
            payload = data[offset:offset + payload_size]
    result = {"type": msg_type, "event_id": event_id}
    if payload:
        if msg_type in (0x09, 0x01):
            try:
                result["json"] = json.loads(payload.decode("utf-8"))
            except Exception:
                result["text"] = payload.decode("utf-8", errors="replace")
        elif msg_type == 0x0B:
            result["audio"] = payload
    return result


def get_oral_english_prompt() -> str:
    path = "courses/oral_english/world_model.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()[:500]
    return "You are an English teacher helping a student practice spoken English."


async def handle_voice(ws):
    """Handle browser WebSocket. ws is FastAPI WebSocket (already accepted)."""
    token = ws.query_params.get("token", "")
    print(f"[voice] token={token[:20] if token else 'MISSING'}...")

    if not token:
        await ws.send_text(json.dumps({"type": "error", "message": "Missing token"}))
        await ws.close()
        return

    user = validate_session(token)
    print(f"[voice] user={user}")
    if not user:
        await ws.send_text(json.dumps({"type": "error", "message": "Invalid token"}))
        await ws.close()
        return

    username = user["username"]
    session_id = str(uuid.uuid4())
    volc_ws = None
    print(f"[voice] {username} connected, connecting to Volcengine...")

    try:
        headers = {
            "X-Api-App-ID": VOLC_APP_ID,
            "X-Api-Access-Key": VOLC_ACCESS_KEY,
            "X-Api-Resource-Id": VOLC_RESOURCE_ID,
            "X-Api-App-Key": VOLC_APP_KEY,
        }
        print(f"[voice] Volc headers: APP_ID={VOLC_APP_ID}, ACCESS_KEY={VOLC_ACCESS_KEY[:8]}..., RESOURCE={VOLC_RESOURCE_ID}, APP_KEY={VOLC_APP_KEY[:8]}...")
        volc_ws = await websockets.connect(VOLC_API_URL, additional_headers=headers)
        print(f"[voice] Volcengine WS connected, starting session...")

        # Start directly with StartSession (WebSocket connect = Connection)
        # per docs: "客户端发送StartSession事件初始化会话"
        ss_payload = {
            "asr": {
                "audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1},
                "extra": {}
            },
            "dialog": {
                "bot_name": "Teacher",
                "system_role": "You are an English teacher.",
                "speaking_style": "friendly",
                "extra": {"model": "1.2.1.1"}
            },
            "tts": {
                "speaker": "zh_female_vv_jupiter_bigtts",
                "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000},
                "extra": {}
            }
        }
        print(f"[voice] -> StartSession payload: {json.dumps(ss_payload, ensure_ascii=False)[:100]}...")
        ss_frame = build_text_frame(100, session_id, ss_payload)
        print(f"[voice] -> StartSession ({len(ss_frame)} bytes), hex: {ss_frame[:40].hex()}...")
        print(f"[voice] -> session_id={session_id}, sid_len={len(session_id)}")
        await volc_ws.send(ss_frame)

        # Wait for SessionStarted (event 150)
        print(f"[voice] Waiting for SessionStarted...")
        try:
            raw = await asyncio.wait_for(volc_ws.recv(), timeout=10)
            frame = parse_frame(raw)
            print(f"[voice] <- after StartSession: type={frame.get('type')}, event={frame.get('event_id')}")
            if frame.get("json"):
                print(f"[voice] <- JSON: {json.dumps(frame['json'], ensure_ascii=False)[:200]}")
            if frame.get("event_id") != 150:
                print(f"[voice] !!! Expected SessionStarted(150), got {frame.get('event_id')}")
                return
            dialog_id = (frame.get("json") or {}).get("dialog_id", "")
            print(f"[voice] Volc session started, dialog_id={dialog_id}")
        except asyncio.TimeoutError:
            print(f"[voice] !!! Timeout waiting for SessionStarted")
            return

        # If we got here, connection is alive
        hello_frame = build_text_frame(300, session_id, {
            "content": "Hello! Welcome to your English speaking practice. How are you today?"
        })
        print(f"[voice] -> SayHello ({len(hello_frame)} bytes)")
        await volc_ws.send(hello_frame)

        await ws.send_text(json.dumps({"type": "ready", "session_id": session_id}))
        print(f"[voice] Relay started (browser <-> Volcengine)")

        seq = [0]

        async def browser_to_volc():
            print(f"[voice] browser_to_volc relay started")
            while True:
                try:
                    data = await ws.receive()
                except Exception as e:
                    print(f"[voice] browser_to_volc recv error: {e}")
                    break
                if "bytes" in data:
                    audio = data["bytes"]
                    print(f"[voice] -> Volc audio: {len(audio)} bytes, seq={seq[0]}")
                    await volc_ws.send(build_audio_frame(session_id, audio, seq[0]))
                    seq[0] += 1
                elif "text" in data:
                    try:
                        msg = json.loads(data["text"])
                        if msg.get("type") == "end_session":
                            await volc_ws.send(build_text_frame(102, session_id, {}))
                            break
                    except Exception:
                        pass

        async def volc_to_browser():
            print(f"[voice] volc_to_browser relay started")
            while True:
                try:
                    raw = await asyncio.wait_for(volc_ws.recv(), timeout=60)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break
                frame = parse_frame(raw)
                if not frame:
                    continue
                eid = frame.get("event_id")
                p = frame.get("json") or {}

                # Log ALL events for debugging
                print(f"[voice] <- Volc event={eid}, has_audio={'audio' in frame}, json={json.dumps(p, ensure_ascii=False)[:300]}")

                if eid == 451:  # ASR
                    text = (p.get("results") or [{}])[0].get("text", "")
                    print(f"[voice] <- Volc ASR: {text}")
                    await ws.send_text(json.dumps({"type": "asr", "text": text}, ensure_ascii=False))
                elif eid == 550:  # Chat text
                    await ws.send_text(json.dumps({"type": "chat_text", "content": p.get("content", "")}, ensure_ascii=False))
                elif eid == 350:  # TTS sentence start
                    await ws.send_text(json.dumps({"type": "tts_start", "text": p.get("text", "")}, ensure_ascii=False))
                elif eid == 352:  # TTS audio
                    if frame.get("audio"):
                        await ws.send_bytes(frame["audio"])
                elif eid == 359:  # TTS ended
                    await ws.send_text(json.dumps({"type": "tts_ended"}))

        await asyncio.gather(browser_to_volc(), volc_to_browser())

    except websockets.exceptions.ConnectionClosed as e:
        print(f"[voice] Volcengine closed: code={e.code}, reason={e.reason}")
    except Exception as e:
        print(f"[voice] Error: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if volc_ws:
            try:
                await volc_ws.send(build_text_frame(102, session_id, {}))
                await volc_ws.close()
            except Exception:
                pass
        print(f"[voice] {username} disconnected")
