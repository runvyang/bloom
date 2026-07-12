"""
WebSocket proxy: Browser <--FastAPI WS--> Server <--raw WS--> Volcengine
Uses manual WebSocket framing for Volcengine (matching working test_volc.py).
"""
import asyncio, ssl, struct, json, uuid, os, base64, traceback
from auth import validate_session

VOLC_APP_ID = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")
VOLC_HOST = "openspeech.bytedance.com"
VOLC_PATH = "/api/v3/realtime/dialogue"
VOLC_APP_KEY = os.getenv("VOLC_APP_KEY", "")

# ─── Raw WebSocket helpers (match test_volc.py exactly) ───

def ws_frame(data: bytes, opcode: int = 0x2) -> bytes:
    length = len(data); mask = os.urandom(4)
    b0 = 0x80 | opcode
    if length < 126: header = bytes([b0, 0x80 | length])
    elif length < 65536: header = bytes([b0, 0x80 | 126]) + struct.pack(">H", length)
    else: header = bytes([b0, 0x80 | 127]) + struct.pack(">Q", length)
    return header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data))

async def ws_read(reader):
    hdr = await reader.readexactly(2)
    plen = hdr[1] & 0x7F
    if plen == 126: plen = struct.unpack(">H", await reader.readexactly(2))[0]
    elif plen == 127: plen = struct.unpack(">Q", await reader.readexactly(8))[0]
    mk = await reader.readexactly(4) if (hdr[1] & 0x80) else b""
    payload = await reader.readexactly(plen)
    return bytes(b ^ mk[i % 4] for i, b in enumerate(payload)) if mk else payload

# ─── Volc binary protocol ───

def build_text(event_id: int, sid: str, payload: dict) -> bytes:
    pb = json.dumps(payload, ensure_ascii=False).encode(); sb = sid.encode()
    return (bytes([0x11, 0x14, 0x10, 0x00]) + struct.pack(">I", event_id) +
            struct.pack(">I", len(sb)) + sb + struct.pack(">I", len(pb)) + pb)

def build_audio(audio_data: bytes) -> bytes:
    return bytes([0x11, 0x20, 0x00, 0x00]) + struct.pack(">I", len(audio_data)) + audio_data

def parse_frame(data: bytes):
    if len(data) < 4: return None
    mt = (data[1] >> 4) & 0x0F; flags = data[1] & 0x0F; off = 4
    if mt == 0x0F:
        code = struct.unpack(">I", data[off:off+4])[0]; off += 4
        psize = struct.unpack(">I", data[off:off+4])[0]; off += 4
        return {"type": mt, "error_code": code, "json": json.loads(data[off:off+psize].decode())}
    eid = None
    if (flags & 0x04) and len(data) >= off + 4:
        eid = struct.unpack(">I", data[off:off+4])[0]; off += 4
    if len(data) >= off + 4:
        ssz = struct.unpack(">I", data[off:off+4])[0]; off += 4
        if ssz > 0 and len(data) >= off + ssz: off += ssz
    psize = struct.unpack(">I", data[off:off+4])[0]; off += 4
    payload = data[off:off+psize]
    result = {"type": mt, "event_id": eid}
    if payload:
        if mt in (0x09, 0x01):
            try: result["json"] = json.loads(payload.decode())
            except: result["text"] = payload.decode(errors="replace")
        elif mt == 0x0B: result["audio"] = payload
    return result

def get_prompt() -> str:
    path = "courses/oral_english/world_model.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return f.read()[:500]
    return "You are an English teacher."

# ─── Main handler ───

async def handle_voice(ws):
    token = ws.query_params.get("token", "")
    print(f"[voice] token={token[:20] if token else 'MISSING'}...")

    if not token:
        await ws.send_text(json.dumps({"type": "error", "message": "Missing token"})); await ws.close(); return

    user = validate_session(token)
    if not user:
        await ws.send_text(json.dumps({"type": "error", "message": "Invalid token"})); await ws.close(); return

    username = user["username"]; sid = str(uuid.uuid4())
    reader = writer = None
    print(f"[voice] {username} connecting to Volcengine...")

    try:
        # Manual WebSocket to Volcengine (matching test_volc.py exactly)
        ws_key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {VOLC_PATH} HTTP/1.1\r\nHost: {VOLC_HOST}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\nSec-WebSocket-Version: 13\r\n"
            f"X-Api-App-ID: {VOLC_APP_ID}\r\n"
            f"X-Api-Access-Key: {VOLC_ACCESS_KEY}\r\n"
            f"X-Api-Resource-Id: volc.speech.dialog\r\n"
            f"X-Api-App-Key: {VOLC_APP_KEY}\r\n\r\n"
        ).encode()
        reader, writer = await asyncio.open_connection(VOLC_HOST, 443, ssl=ssl.create_default_context())
        writer.write(request); await writer.drain()
        resp = b""
        while b"\r\n\r\n" not in resp: resp += await reader.read(4096)
        if b"101" not in resp:
            print(f"[voice] Volc upgrade failed!"); return
        print(f"[voice] Volcengine connected")

        # StartSession
        writer.write(ws_frame(build_text(100, sid, {
            "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}, "extra": {}},
            "dialog": {"bot_name": "Teacher", "system_role": get_prompt(),
                       "speaking_style": "friendly", "extra": {"model": "1.2.1.1"}},
            "tts": {"speaker": "zh_female_vv_jupiter_bigtts",
                    "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000}, "extra": {}}
        }))); await writer.drain()

        raw = await ws_read(reader)
        f = parse_frame(raw)
        if not f or f.get("event_id") != 150:
            print(f"[voice] SessionStart failed: {f}"); return
        print(f"[voice] Session started")

        # Warm-up: text query (matching test_volc.py)
        writer.write(ws_frame(build_text(501, sid, {"content": "Hello! Greet the student briefly."})))
        await writer.drain()

        # Drain response completely
        drained = 0
        while True:
            try:
                raw = await asyncio.wait_for(ws_read(reader), timeout=0.5)
                f = parse_frame(raw)
                if f:
                    if f.get("audio"): await ws.send_bytes(f["audio"]); drained += 1
                    elif f.get("event_id") in (359, 559): drained += 1
            except asyncio.TimeoutError:
                break
        print(f"[voice] Drained {drained}, starting relay...")

        # Relay
        async def browser_to_volc():
            n = 0
            while True:
                try: data = await ws.receive()
                except Exception: break
                if "bytes" in data:
                    n += 1
                    writer.write(ws_frame(build_audio(data["bytes"])))
                    if n <= 3 or n % 100 == 0:
                        print(f"[voice] b2v #{n}: {len(data['bytes'])} bytes")
                elif "text" in data:
                    try:
                        if json.loads(data["text"]).get("type") == "end_session":
                            writer.write(ws_frame(build_text(102, sid, {}))); break
                    except: pass

        async def volc_to_browser():
            n = 0
            while True:
                try: raw = await asyncio.wait_for(ws_read(reader), timeout=60)
                except asyncio.TimeoutError: continue
                except Exception: break
                f = parse_frame(raw)
                if not f: continue
                n += 1; eid = f.get("event_id"); p = f.get("json") or {}
                if n <= 3 or n % 50 == 0:
                    print(f"[voice] v2b #{n}: eid={eid}, audio={'audio' in f}")

                if f.get("audio"):
                    await ws.send_bytes(f["audio"])
                elif eid == 451:
                    text = (p.get("results") or [{}])[0].get("text", "")
                    print(f"[voice] ASR: {text}")
                    await ws.send_text(json.dumps({"type": "asr", "text": text}, ensure_ascii=False))
                elif eid == 550:
                    await ws.send_text(json.dumps({"type": "chat_text", "content": p.get("content", "")}, ensure_ascii=False))
                elif eid == 350:
                    await ws.send_text(json.dumps({"type": "tts_start", "text": p.get("text", "")}, ensure_ascii=False))

        b2v = asyncio.create_task(browser_to_volc())
        v2b = asyncio.create_task(volc_to_browser())
        await ws.send_text(json.dumps({"type": "ready", "session_id": sid}))
        print(f"[voice] Ready!")

        done, pending = await asyncio.wait([b2v, v2b], return_when=asyncio.FIRST_COMPLETED)
        for t in pending: t.cancel()

    except Exception as e:
        print(f"[voice] Error: {type(e).__name__}: {e}")
        traceback.print_exc()
        try: await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except: pass
    finally:
        if writer:
            try: writer.write(ws_frame(build_text(102, sid, {}))); writer.close()
            except: pass
        print(f"[voice] {username} disconnected")
