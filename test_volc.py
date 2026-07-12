"""Audio frame format test — try different Audio-only (msg_type=0x02) variants."""
import asyncio, ssl, struct, json, uuid, os, base64, math

def ws_frame(data: bytes, opcode: int = 0x2) -> bytes:
    length = len(data)
    mask = os.urandom(4)
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

def build_text(event_id: int, sid: str, payload: dict) -> bytes:
    pb = json.dumps(payload, ensure_ascii=False).encode(); sb = sid.encode()
    return (bytes([0x11, 0x14, 0x10, 0x00]) + struct.pack(">I", event_id) +
            struct.pack(">I", len(sb)) + sb + struct.pack(">I", len(pb)) + pb)

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

async def do_test(reader, writer, name, frame):
    print(f"\n--- {name} ---")
    print(f"  hex: {frame[:20].hex()}...")
    writer.write(ws_frame(frame))
    try:
        await asyncio.wait_for(writer.drain(), timeout=3)
    except:
        print("  ✗ Connection died on send!")
        return False
    try:
        raw = await asyncio.wait_for(ws_read(reader), timeout=5)
        f = parse_frame(raw)
        if f:
            eid = f.get('event_id')
            if f.get('json'):
                print(f"  ← event={eid}, json={json.dumps(f['json'], ensure_ascii=False)[:200]}")
            elif f.get('audio'):
                print(f"  ← AUDIO {len(f['audio'])} bytes ✓")
            else:
                print(f"  ← event={eid}, text={f.get('text','')[:100]}")
            return f.get('event_id') not in (None,)
        else:
            print(f"  ← unparseable: {raw[:40].hex()}")
            return True
    except asyncio.TimeoutError:
        print("  (timeout — server accepted?)")
        return True
    except:
        print("  ✗ Connection lost!")
        return False

def make_audio(duration_ms=100, freq=440):
    samples = int(16000 * duration_ms / 1000)
    return struct.pack("<" + "h" * samples, *[
        int(16000 * math.sin(2 * math.pi * freq * i / 16000)) for i in range(samples)
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

    sid = str(uuid.uuid4()); sb = sid.encode()
    writer.write(ws_frame(build_text(100, sid, {
        "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}, "extra": {}},
        "dialog": {"bot_name": "test", "extra": {"model": "1.2.1.1"}},
        "tts": {"speaker": "zh_female_vv_jupiter_bigtts", "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000}, "extra": {}}
    }))); await writer.drain()
    raw = await ws_read(reader)
    f = parse_frame(raw)
    print(f"SessionStarted: event={f.get('event_id')}, {f.get('json')}")

    # Test FIRST: Simple text query — does chat work at all?
    if not await do_test(reader, writer, "FIRST: Text query (event 501)",
                         build_text(501, sid, {"content": "Hello, how are you?"})):
        print("Even text query failed — something fundamentally wrong"); return

    # Read a few responses to the text query
    for i in range(5):
        try:
            raw = await asyncio.wait_for(ws_read(reader), timeout=5)
            f = parse_frame(raw)
            if f:
                print(f"  ← event={f.get('event_id')}, json={json.dumps(f.get('json',''), ensure_ascii=False)[:200]}")
                if f.get('audio'): print(f"  ← AUDIO {len(f['audio'])} bytes!")
        except asyncio.TimeoutError: break
        except: break

    audio = make_audio(100, 440)

    # Test A: Audio-only, flags=0x00 (no sequence, no event), just payload
    frame_a = bytes([0x11, 0x20, 0x10, 0x00]) + struct.pack(">I", len(audio)) + audio
    if not await do_test(reader, writer, "A: Audio-only, no flags, bare payload", frame_a):
        print("Connection died — restart for more tests"); return

    # Test B: Audio-only, flags=0x01 (has sequence=1), just seq+payload
    frame_b = bytes([0x11, 0x21, 0x10, 0x00]) + struct.pack(">I", 1) + struct.pack(">I", len(audio)) + audio
    if not await do_test(reader, writer, "B: Audio-only, seq=1, bare payload", frame_b):
        return

    # Test C: Audio-only, flags=0x01 (seq=1), WITH session_id
    frame_c = (bytes([0x11, 0x21, 0x10, 0x00]) + struct.pack(">I", 1) +
               struct.pack(">I", len(sb)) + sb + struct.pack(">I", len(audio)) + audio)
    if not await do_test(reader, writer, "C: Audio-only, seq=1 + session_id + audio", frame_c):
        return

    # Test D: Full-client event=200, but with JSON payload (text) not audio
    frame_d = build_text(501, sid, {"content": "Hello, how are you?"})
    if not await do_test(reader, writer, "D: Full-client text query (control test)", frame_d):
        return

    writer.write(ws_frame(build_text(102, sid, {}))); await writer.drain()
    writer.close(); print("\nDone!")

asyncio.run(main())
