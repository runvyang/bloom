"""Quick audio frame test — connect, send mock audio, see response."""
import asyncio, ssl, struct, json, uuid, os, base64, math

def ws_frame(data: bytes, opcode: int = 0x2) -> bytes:
    length = len(data)
    mask = os.urandom(4)
    b0 = 0x80 | opcode
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

def build_text(event_id: int, sid: str, payload: dict) -> bytes:
    pb = json.dumps(payload, ensure_ascii=False).encode()
    sb = sid.encode()
    return (bytes([0x11, 0x14, 0x10, 0x00]) +
            struct.pack(">I", event_id) +
            struct.pack(">I", len(sb)) + sb +
            struct.pack(">I", len(pb)) + pb)

def parse_frame(data: bytes):
    if len(data) < 4: return None
    mt = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    off = 4
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

def make_sine_wave(duration_ms=100, freq=440, sample_rate=16000):
    """Generate PCM int16 LE sine wave."""
    samples = int(sample_rate * duration_ms / 1000)
    return struct.pack("<" + "h" * samples, *[
        int(16000 * math.sin(2 * math.pi * freq * i / sample_rate))
        for i in range(samples)
    ])

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
    writer.write(ws_frame(build_text(100, sid, {
        "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}, "extra": {}},
        "dialog": {"bot_name": "test", "extra": {"model": "1.2.1.1"}},
        "tts": {"speaker": "zh_female_vv_jupiter_bigtts", "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000}, "extra": {}}
    }))); await writer.drain()
    op, raw = await ws_read(reader)
    f = parse_frame(raw)
    print(f"SessionStarted: event={f.get('event_id')}, {f.get('json')}")

    # Test 1: Full-client audio frame (event 200 + session_id + audio payload)
    print("\n--- Test 1: Full-client event=200 with session_id ---")
    audio = make_sine_wave(100)  # 100ms of 440Hz
    sb = sid.encode()
    frame = (bytes([0x11, 0x14, 0x10, 0x00]) +  # Full-client, has event
             struct.pack(">I", 200) +              # TaskRequest
             struct.pack(">I", len(sb)) + sb +     # session_id
             struct.pack(">I", len(audio)) + audio) # payload
    writer.write(ws_frame(frame)); await writer.drain()
    print(f"Sent: header+event(200)+sid({len(sb)})+payload({len(audio)}bytes)")
    try:
        op, raw = await asyncio.wait_for(ws_read(reader), timeout=5)
        f = parse_frame(raw)
        eid = f.get('event_id')
        print(f"Response: event={eid}, json={json.dumps(f.get('json',''), ensure_ascii=False)[:200]}")
        if f.get('audio'): print(f"  AUDIO: {len(f['audio'])} bytes")
    except asyncio.TimeoutError:
        print("  (timeout — no response)")

    # Test 2: Audio-only frame (msg_type=0b0010, no event, no sid)
    print("\n--- Test 2: Audio-only msg_type=2, no event/sid ---")
    audio2 = make_sine_wave(100, 880)
    frame2 = (bytes([0x11, 0x20, 0x10, 0x00]) +  # Audio-only, flags=0
              struct.pack(">I", len(audio2)) + audio2)
    writer.write(ws_frame(frame2)); await writer.drain()
    print(f"Sent: header+payload({len(audio2)}bytes)")
    try:
        op, raw = await asyncio.wait_for(ws_read(reader), timeout=5)
        f = parse_frame(raw)
        eid = f.get('event_id')
        print(f"Response: event={eid}, json={json.dumps(f.get('json',''), ensure_ascii=False)[:200]}")
        if f.get('audio'): print(f"  AUDIO: {len(f['audio'])} bytes")
    except asyncio.TimeoutError:
        print("  (timeout — no response)")

    # Test 3: Audio frame with session_id but no event
    print("\n--- Test 3: Audio with session_id, no event ---")
    audio3 = make_sine_wave(100, 220)
    frame3 = (bytes([0x11, 0x20, 0x10, 0x00]) +
              struct.pack(">I", len(sb)) + sb +
              struct.pack(">I", len(audio3)) + audio3)
    writer.write(ws_frame(frame3)); await writer.drain()
    print(f"Sent: header+sid({len(sb)})+payload({len(audio3)}bytes)")
    try:
        op, raw = await asyncio.wait_for(ws_read(reader), timeout=5)
        f = parse_frame(raw)
        eid = f.get('event_id')
        print(f"Response: event={eid}, json={json.dumps(f.get('json',''), ensure_ascii=False)[:200]}")
        if f.get('audio'): print(f"  AUDIO: {len(f['audio'])} bytes")
    except asyncio.TimeoutError:
        print("  (timeout — no response)")

    writer.write(ws_frame(build_text(102, sid, {}))); await writer.drain()
    writer.close()
    print("\nDone!")

asyncio.run(main())
