"""Raw WebSocket test — manual handshake + framing, no websockets library."""
import asyncio, ssl, struct, json, uuid, os, base64

def ws_frame(data: bytes, opcode: int = 0x2) -> bytes:
    """Build a masked WebSocket frame (client→server)."""
    b0 = 0x80 | opcode  # FIN=1
    length = len(data)
    mask = os.urandom(4)
    if length < 126:
        header = bytes([b0, 0x80 | length])
    elif length < 65536:
        header = bytes([b0, 0x80 | 126]) + struct.pack(">H", length)
    else:
        header = bytes([b0, 0x80 | 127]) + struct.pack(">Q", length)
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return header + masked

async def ws_read(reader):
    """Read one WebSocket frame, return (opcode, payload)."""
    hdr = await reader.readexactly(2)
    opcode = hdr[0] & 0x0F
    masked = (hdr[1] & 0x80) != 0
    plen = hdr[1] & 0x7F
    if plen == 126:
        plen = struct.unpack(">H", await reader.readexactly(2))[0]
    elif plen == 127:
        plen = struct.unpack(">Q", await reader.readexactly(8))[0]
    mk = await reader.readexactly(4) if masked else b""
    payload = await reader.readexactly(plen)
    if mk:
        payload = bytes(b ^ mk[i % 4] for i, b in enumerate(payload))
    return opcode, payload

async def main():
    host = "openspeech.bytedance.com"
    path = "/api/v3/realtime/dialogue"
    ws_key = base64.b64encode(os.urandom(16)).decode()

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"X-Api-App-ID: {os.getenv('VOLC_APP_ID','')}\r\n"
        f"X-Api-Access-Key: {os.getenv('VOLC_ACCESS_KEY','')}\r\n"
        f"X-Api-Resource-Id: volc.speech.dialog\r\n"
        f"X-Api-App-Key: {os.getenv('VOLC_APP_KEY','')}\r\n"
        f"\r\n"
    ).encode()

    ctx = ssl.create_default_context()
    reader, writer = await asyncio.open_connection(host, port=443, ssl=ctx)
    writer.write(request)
    await writer.drain()

    # Read HTTP response
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += await reader.read(4096)
    print(f"HTTP: {resp.decode()[:150]}")

    if b"101" not in resp:
        print("Upgrade failed!")
        return
    print("WebSocket connected!")

    # Build and send StartSession frame
    sid = str(uuid.uuid4())
    pld = json.dumps({"dialog": {"bot_name": "test", "dialog_id": "", "extra": {"model": "1.2.1.1"}}})
    sb = sid.encode()
    pb = pld.encode()
    volc_frame = (bytes([0x11, 0x14, 0x10, 0x00]) +
                  struct.pack(">I", 100) +
                  struct.pack(">I", len(sb)) + sb +
                  struct.pack(">I", len(pb)) + pb)
    print(f"\nVolc frame: {len(volc_frame)} bytes")
    print(f"  header: {volc_frame[0:4].hex()}")
    print(f"  event=100: {volc_frame[4:8].hex()}")
    print(f"  sid_size={len(sb)}: {volc_frame[8:12].hex()}")
    print(f"  payload_size={len(pb)}")

    writer.write(ws_frame(volc_frame, 0x2))
    await writer.drain()

    # Read response
    op, payload = await ws_read(reader)
    print(f"\nResponse: opcode={op}, len={len(payload)}")

    if len(payload) >= 4:
        mt = (payload[1] >> 4) & 0x0F
        print(f"  msg_type={mt}, hex[0:30]={payload[:30].hex()}")
        if mt == 0x0F and len(payload) >= 12:
            offset = 4
            code = struct.unpack(">I", payload[offset:offset+4])[0]
            offset += 4
            psize = struct.unpack(">I", payload[offset:offset+4])[0]
            offset += 4
            err = payload[offset:offset+psize].decode()
            print(f"  ERROR code={code}, msg={err}")
    else:
        print(f"  Short payload: {payload.hex()}")

    writer.close()

asyncio.run(main())
