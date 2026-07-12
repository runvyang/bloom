"""End-to-end audio test: send sine wave, receive TTS, save to file."""
import asyncio, ssl, struct, json, uuid, os, base64, math, wave

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

def build_audio(audio_data: bytes) -> bytes:
    """Audio-only, Raw serialization, no event/sid/seq."""
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

def make_speech_audio():
    """Generate ~2 seconds of mock speech (varying frequencies to simulate voice)."""
    samples = []
    sample_rate = 16000
    # Simulate "Hello?" with varying tones
    freqs = [(300, 400), (350, 500), (200, 600), (250, 450)]  # (duration_ms, freq_hz)
    for dur_ms, freq in freqs:
        n = int(sample_rate * dur_ms / 1000)
        for i in range(n):
            samples.append(int(8000 * math.sin(2 * math.pi * freq * i / sample_rate)))
    return struct.pack("<" + "h" * len(samples), *samples)

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
    print("✓ Connected!")

    sid = str(uuid.uuid4())

    # StartSession
    writer.write(ws_frame(build_text(100, sid, {
        "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}, "extra": {}},
        "dialog": {"bot_name": "test", "extra": {"model": "1.2.1.1"}},
        "tts": {"speaker": "zh_female_vv_jupiter_bigtts",
                "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000}, "extra": {}}
    }))); await writer.drain()

    raw = await ws_read(reader)
    f = parse_frame(raw)
    if not f or f.get("event_id") != 150:
        print(f"✗ SessionStart failed: {f}"); return
    print(f"✓ Session started")

    # Wait a beat, then send mock speech audio
    await asyncio.sleep(0.5)
    speech = make_speech_audio()
    print(f"→ Sending audio: {len(speech)} bytes ({len(speech)/32:.0f}ms)")

    # Send 10 chunks of audio (like real mic streaming)
    chunk_size = len(speech) // 10
    for i in range(10):
        chunk = speech[i*chunk_size:(i+1)*chunk_size]
        writer.write(ws_frame(build_audio(chunk)))
        await asyncio.sleep(0.1)  # simulate 100ms between chunks

    print(f"✓ Audio sent, waiting for response...")

    # Collect all responses
    all_audio = b""
    all_text = ""
    for i in range(30):
        try:
            raw = await asyncio.wait_for(ws_read(reader), timeout=3)
            f = parse_frame(raw)
            if not f: continue
            eid = f.get("event_id")
            p = f.get("json") or {}

            if p.get("error"):
                print(f"  ← ERROR: {p['error']}")
                continue

            if f.get("audio"):
                all_audio += f["audio"]
                print(f"  ← TTS audio: {len(f['audio'])} bytes (total: {len(all_audio)})")

            if eid == 550:  # Chat text
                text = p.get("content", "")
                all_text += text
                print(f"  ← Chat: {text}")

            if eid == 451:  # ASR recognized
                text = (p.get("results") or [{}])[0].get("text", "")
                print(f"  ← ASR: {text}")

            if eid in (359, 559):  # TTSEnded or ChatEnded
                print(f"  ← Response complete (event {eid})")
                break

        except asyncio.TimeoutError:
            print("  (timeout — no more data)")
            break
        except Exception as e:
            print(f"  Connection error: {e}")
            break

    writer.write(ws_frame(build_text(102, sid, {}))); await writer.drain()
    writer.close()

    # Save audio
    if all_audio:
        fname = "/tmp/volc_tts.wav"
        with wave.open(fname, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # 16-bit
            w.setframerate(24000)
            w.writeframes(all_audio)
        print(f"\n✓ TTS audio saved to {fname} ({len(all_audio)} bytes)")
        print(f"  Play with: afplay {fname}")

    if all_text:
        print(f"✓ Response text: {all_text}")

asyncio.run(main())
