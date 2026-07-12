"""Minimal Volcengine voice API test. Run: python test_volc.py"""
import asyncio, websockets, struct, json, uuid, os

async def main():
    headers = {
        "X-Api-App-ID": os.getenv("VOLC_APP_ID", ""),
        "X-Api-Access-Key": os.getenv("VOLC_ACCESS_KEY", ""),
        "X-Api-Resource-Id": "volc.speech.dialog",
        "X-Api-App-Key": os.getenv("VOLC_APP_KEY", ""),
    }
    uri = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"

    ws = await websockets.connect(uri, additional_headers=headers, compression=None)
    print("Connected!")

    sid = str(uuid.uuid4())
    sb = sid.encode()
    # Minimal payload — match doc example
    payload = json.dumps({
        "dialog": {"bot_name": "test", "dialog_id": "", "extra": {"model": "1.2.1.1"}}
    })
    pb = payload.encode()

    # Build frame per doc: header(4) + event(4) + sid_size(4) + sid(var) + payload_size(4) + payload(var)
    frame = (bytes([0x11, 0x14, 0x10, 0x00]) +
             struct.pack("<I", 100) +
             struct.pack("<I", len(sb)) + sb +
             struct.pack("<I", len(pb)) + pb)
    print(f"Frame: {len(frame)} bytes, hex[0:40]={frame[:40].hex()}")
    print(f"session_id={sid} len={len(sb)}")
    print(f"payload len={len(pb)}")

    # Try as text frame — volc might expect text opcode for binary protocol data
    await ws.send(frame.decode('latin-1'))  # force text frame
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    mt = (raw[1] >> 4) & 0x0F
    print(f"Response (text): {len(raw)} bytes, msg_type={mt}")
    if mt != 0x0F:
        print("TEXT FRAME WORKED!")
        await ws.close()
        return

    # If text didn't work, try raw binary again for comparison
    print("Text frame failed, trying binary again...")
    await ws.send(frame)
    raw = await asyncio.wait_for(ws.recv(), timeout=10)
    mt = (raw[1] >> 4) & 0x0F
    print(f"Response: {len(raw)} bytes, msg_type={mt}, hex[0:40]={raw[:40].hex()}")

    # Try to parse
    if mt == 0x0F:  # Error
        offset = 4
        code = struct.unpack("<I", raw[offset:offset+4])[0]
        offset += 4
        psize = struct.unpack("<I", raw[offset:offset+4])[0]
        offset += 4
        err = raw[offset:offset+psize].decode()
        print(f"ERROR: code={code}, msg={err}")

    await ws.close()

asyncio.run(main())
