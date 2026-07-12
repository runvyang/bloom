"""Minimal end-to-end test: connect, send text, get TTS audio."""
import asyncio, ssl, struct, json, uuid, os, base64

def ws_frame(data: bytes, opcode: int = 0x2) -> bytes:
    b0 = 0x80 | opcode
    length = len(data)
    mask = os.urandom(4)
    if length < 126:
        header = bytes([b0, 0x80 | length])
    elif length < 65536:
        header = bytes([b0, 0x80 | 126]) + struct.pack(">H", length)
    else:
        header = bytes([b0, 0x80 | 127]) + struct.pack(">Q", length)
    header += mask
    return header + bytes(b ^ mask[i % 4] for i, b in enumerate(data))

async def ws_read(reader):
    hdr = await reader.readexactly(2)
    opcode = hdr[0] & 0x0F
    plen = hdr[1] & 0x7F
    if plen == 126: plen = struct.unpack(">H", await reader.readexactly(2))[0]
    elif plen == 127: plen = struct.unpack(">Q", await reader.readexactly(8))[0]
    mk = await reader.readexactly(4) if (hdr[1] & 0x80) else b""
    payload = await reader.readexactly(plen)
    return opcode, bytes(b ^ mk[i % 4] for i, b in enumerate(payload)) if mk else payload

def build_text_frame(event_id: int, sid: str, payload: dict) -> bytes:
    pb = json.dumps(payload, ensure_ascii=False).encode()
    sb = sid.encode()
    header = bytes([0x11, 0x14, 0x10, 0x00])
    event_bytes = struct.pack(">I", event_id)
    sid_size = struct.pack(">I", len(sb))
    payload_size = struct.pack(">I", len(pb))
    return header + event_bytes + sid_size + sb + payload_size + pb

def parse_frame(data: bytes):
    if len(data) < 4: return None
    mt = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    off = 4
    code = None
    if mt == 0x0F and len(data) >= off + 4:
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

async def main():
    host, path = "openspeech.bytedance.com", "/api/v3/realtime/dialogue"
    ws_key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\nSec-WebSocket-Version: 13\r\n"
        f"X-Api-App-ID: {os.getenv('VOLC_APP_ID','')}\r\n"
        f"X-Api-Access-Key: {os.getenv('VOLC_ACCESS_KEY','')}\r\n"
        f"X-Api-Resource-Id: volc.speech.dialog\r\n"
        f"X-Api-App-Key: {os.getenv('VOLC_APP_KEY','')}\r\n\r\n"
    ).encode()

    reader, writer = await asyncio.open_connection(host, 443, ssl=ssl.create_default_context())
    writer.write(request); await writer.drain()
    resp = b""
    while b"\r\n\r\n" not in resp: resp += await reader.read(4096)
    if b"101" not in resp: print("Upgrade failed!"); return
    print("Connected!")

    sid = str(uuid.uuid4())

    # StartSession
    ss = build_text_frame(100, sid, {
        "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}, "extra": {}},
        "dialog": {"bot_name": "test", "extra": {"model": "1.2.1.1"}},
        "tts": {"speaker": "zh_female_vv_jupiter_bigtts", "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000}, "extra": {}}
    })
    writer.write(ws_frame(ss)); await writer.drain()
    op, raw = await ws_read(reader)
    f = parse_frame(raw)
    print(f"SessionStarted: event={f.get('event_id')}, json={f.get('json')}")

    # Send text query
    tq = build_text_frame(501, sid, {"content": "Hello! How are you?"})
    writer.write(ws_frame(tq)); await writer.drain()
    print("Sent: Hello! How are you?")

    # Read responses
    for _ in range(10):
        op, raw = await ws_read(reader)
        f = parse_frame(raw)
        if not f: continue
        print(f"event={f.get('event_id')}", end="")
        if f.get("json"): print(f" json={json.dumps(f['json'], ensure_ascii=False)[:200]}")
        elif f.get("audio"): print(f" AUDIO {len(f['audio'])} bytes")
        elif f.get("text"): print(f" text={f['text'][:200]}")
        else: print()
        if f.get("event_id") == 359: break  # TTSEnded

    # Send FinishSession
    writer.write(ws_frame(build_text_frame(102, sid, {}))); await writer.drain()
    writer.close()

asyncio.run(main())
