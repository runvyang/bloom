"""
Voice proxy using Volcengine binary protocol — based on official realtime_dialog_client.py.
Key: ALL payloads MUST be gzip compressed with GZIP flag in header.
"""
import asyncio, struct, json, uuid, os, gzip, traceback
import websockets
from auth import validate_session
from session_store import append_to_session
from utils import read_file, append_file, copy_file
from llm import OpenRouterClient

VOLC_APP_ID = os.getenv("VOLC_APP_ID", "")
VOLC_ACCESS_KEY = os.getenv("VOLC_ACCESS_KEY", "")
VOLC_API_URL = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
VOLC_APP_KEY = os.getenv("VOLC_APP_KEY", "")

# ─── Protocol constants (matching official protocol.py) ───

CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
NO_SEQUENCE = 0b0000
MSG_WITH_EVENT = 0b0100
NO_SERIALIZATION = 0b0000
JSON = 0b0001
NO_COMPRESSION = 0b0000
GZIP = 0b0001

def generate_header(message_type=CLIENT_FULL_REQUEST,
                    flags=MSG_WITH_EVENT,
                    serial=JSON,
                    compression=GZIP):
    """Match official protocol.generate_header() exactly."""
    header = bytearray()
    header.append((0b0001 << 4) | 1)  # version=1, header_size=1
    header.append((message_type << 4) | flags)
    header.append((serial << 4) | compression)
    header.append(0x00)  # reserved
    return header

def compress(data: bytes) -> bytes:
    return gzip.compress(data)

# ─── Frame builders (matching official realtime_dialog_client.py) ───

def build_text_frame(event_id: int, session_id: str, payload: dict) -> bytes:
    """Full-client text event with GZIP compression."""
    pb = compress(str.encode(json.dumps(payload)))
    sb = str.encode(session_id)
    frame = bytearray(generate_header())
    frame.extend(event_id.to_bytes(4, 'big'))
    frame.extend(len(sb).to_bytes(4, 'big'))
    frame.extend(sb)
    frame.extend(len(pb).to_bytes(4, 'big'))
    frame.extend(pb)
    return bytes(frame)

def build_audio_frame(session_id: str, audio_data: bytes) -> bytes:
    """Audio-only request with GZIP compression — matching official task_request()."""
    pb = compress(audio_data)
    sb = str.encode(session_id)
    frame = bytearray(generate_header(message_type=CLIENT_AUDIO_ONLY_REQUEST,
                                       serial=NO_SERIALIZATION))
    frame.extend((200).to_bytes(4, 'big'))  # TaskRequest event
    frame.extend(len(sb).to_bytes(4, 'big'))
    frame.extend(sb)
    frame.extend(len(pb).to_bytes(4, 'big'))
    frame.extend(pb)
    return bytes(frame)

# ─── Response parser (matching official protocol.py) ───

def parse_response(data: bytes):
    if isinstance(data, str): return {}
    mt = data[1] >> 4
    flags = data[1] & 0x0f
    serial = data[2] >> 4
    compression = data[2] & 0x0f

    # Error frame
    if mt == 0b1111:
        code = int.from_bytes(data[4:8], 'big')
        psize = int.from_bytes(data[8:12], 'big')
        pdata = data[12:12+psize]
        if compression == GZIP: pdata = gzip.decompress(pdata)
        return {"type": mt, "error_code": code, "json": json.loads(str(pdata, 'utf-8'))}

    # Full response / ACK
    result = {"type": mt, "event": None, "session_id": None, "payload_msg": None, "audio": None}
    start = 4
    if flags & MSG_WITH_EVENT:
        result["event"] = int.from_bytes(data[start:start+4], 'big')
        start += 4
    sid_size = int.from_bytes(data[start:start+4], 'big', signed=True)
    result["session_id"] = str(data[start+4:start+4+sid_size])
    start += 4 + sid_size
    psize = int.from_bytes(data[start:start+4], 'big')
    payload = data[start+4:start+4+psize]
    if compression == GZIP: payload = gzip.decompress(payload)
    if serial == JSON:
        result["payload_msg"] = json.loads(str(payload, 'utf-8'))
    elif serial == NO_SERIALIZATION:
        result["audio"] = payload  # raw audio
    return result


def get_prompt(username: str = "") -> str:
    """Build system prompt including student's current state."""
    base = "You are a friendly English teacher helping a young Chinese student practice spoken English for the PET exam. Speak clearly at moderate speed. Encourage the student."

    # Course prompt
    path = "courses/oral_english/world_model.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            base = f.read()[:400]

    # Student state
    if username:
        map_path = f"data/student/{username}/oral_english_map.md"
        template = "courses/oral_english/course_map.md"
        if not os.path.exists(map_path) and os.path.exists(template):
            copy_file(template, map_path)
        if os.path.exists(map_path):
            content = read_file(map_path)
            # Extract the most relevant part (first 300 chars after header)
            lines = content.split('\n')
            body = '\n'.join(lines[10:]) if len(lines) > 10 else content
            base += f"\n\nStudent's current level:\n{body[:400]}"

    return base[:1000]

# ─── Main handler ───

async def handle_voice(ws):
    token = ws.query_params.get("token", "")
    if not token:
        await ws.send_text(json.dumps({"type": "error", "message": "Missing token"})); await ws.close(); return
    user = validate_session(token)
    if not user:
        await ws.send_text(json.dumps({"type": "error", "message": "Invalid token"})); await ws.close(); return

    username = user["username"]; sid = str(uuid.uuid4())
    volc_ws = None
    print(f"[voice] {username} connecting...")

    try:
        headers = {
            "X-Api-App-ID": VOLC_APP_ID, "X-Api-Access-Key": VOLC_ACCESS_KEY,
            "X-Api-Resource-Id": "volc.speech.dialog", "X-Api-App-Key": VOLC_APP_KEY,
        }
        volc_ws = await websockets.connect(VOLC_API_URL, additional_headers=headers, ping_interval=None)
        print(f"[voice] Volc connected")

        # StartConnection (matching official demo)
        sc = bytearray(generate_header())
        sc.extend((1).to_bytes(4, 'big'))
        pb = compress(b"{}")
        sc.extend(len(pb).to_bytes(4, 'big')); sc.extend(pb)
        await volc_ws.send(bytes(sc))
        resp = await volc_ws.recv()
        print(f"[voice] StartConnection: {parse_response(resp).get('event')}")

        # StartSession
        ss_payload = {
            "asr": {"audio_info": {"format": "pcm", "sample_rate": 16000, "channel": 1}, "extra": {}},
            "dialog": {"bot_name": "Teacher", "system_role": get_prompt(username),
                       "speaking_style": "friendly", "extra": {"model": "1.2.1.1"}},
            "tts": {"speaker": "zh_female_vv_jupiter_bigtts",
                    "audio_config": {"channel": 1, "format": "pcm_s16le", "sample_rate": 24000,
                                     "speech_rate": -10},
                    "extra": {}}
        }
        await volc_ws.send(build_text_frame(100, sid, ss_payload))
        resp = await volc_ws.recv()
        r = parse_response(resp)
        print(f"[voice] StartSession: event={r.get('event')}")

        # Track conversation for session log + eval
        transcript = []  # list of {role, content}
        pending_teacher = []  # buffer teacher text until student actually responds
        student_spoke = [False]
        last_teacher_text = [""]
        last_student_text = [""]

        def flush_pending():
            for t in pending_teacher:
                transcript.append(t)
                append_to_session(username, "oral_english", t["role"], t["content"], sid)
            pending_teacher.clear()

        def save_turn(role, text):
            if not text.strip(): return
            entry = {"role": role, "content": text.strip()}
            if role == "teacher":
                if student_spoke[0]:
                    # Student spoke — save immediately
                    transcript.append(entry)
                    append_to_session(username, "oral_english", role, text.strip(), sid)
                else:
                    # Buffer teacher text until student responds
                    pending_teacher.append(entry)
            else:
                # Student spoke — flush any pending teacher turns first
                if not student_spoke[0]:
                    student_spoke[0] = True
                    flush_pending()
                transcript.append(entry)
                append_to_session(username, "oral_english", role, text.strip(), sid)

        # Relay
        async def browser_to_volc():
            n = 0
            while True:
                try: data = await ws.receive()
                except Exception: break
                if "bytes" in data:
                    n += 1
                    await volc_ws.send(build_audio_frame(sid, data["bytes"]))
                    if n <= 3 or n % 100 == 0:
                        print(f"[voice] audio #{n}: {len(data['bytes'])} bytes")
                elif "text" in data:
                    try:
                        msg = json.loads(data["text"])
                        if msg.get("type") == "end_session":
                            await volc_ws.send(build_text_frame(102, sid, {})); break
                        elif msg.get("type") == "update_config":
                            # UpdateConfig event (201) — change speaker/speed mid-call
                            await volc_ws.send(build_text_frame(201, sid, {
                                "tts": {
                                    "speaker": msg.get("speaker", "zh_female_vv_jupiter_bigtts"),
                                    "audio_config": {
                                        "speech_rate": int((msg.get("speed", 1.0) - 1.0) * 100)
                                    }
                                }
                            }))
                    except Exception: pass

        async def volc_to_browser():
            while True:
                try: raw = await asyncio.wait_for(volc_ws.recv(), timeout=60)
                except asyncio.TimeoutError: continue
                except Exception: break
                r = parse_response(raw)
                evt = r.get("event"); p = r.get("payload_msg") or {}
                if r.get("audio"): await ws.send_bytes(r["audio"])
                elif evt == 451:
                    # Only forward final (non-interim) ASR results
                    results = p.get("results") or [{}]
                    for r in results:
                        if not r.get("is_interim", True) and r.get("text", "").strip():
                            text = r["text"].strip()
                            print(f"[voice] ASR final: {text}")
                            await ws.send_text(json.dumps({"type": "asr", "text": text}, ensure_ascii=False))
                            nonlocal last_student_text
                            if text != last_student_text[0]:
                                last_student_text[0] = text
                                save_turn("student", text)
                elif evt == 550:
                    content = p.get("content", "")
                    last_teacher_text[0] += content
                    await ws.send_text(json.dumps({"type": "chat_text", "content": content}, ensure_ascii=False))
                elif evt == 359:  # TTS ended — flush teacher text (only if student spoke)
                    if last_teacher_text[0].strip() and student_spoke[0]:
                        save_turn("teacher", last_teacher_text[0])
                    last_teacher_text[0] = ""
                elif evt == 350:
                    await ws.send_text(json.dumps({"type": "tts_start", "text": p.get("text", "")}, ensure_ascii=False))

        b2v = asyncio.create_task(browser_to_volc())
        v2b = asyncio.create_task(volc_to_browser())

        # Send initial greeting (like official demo's say_hello)
        await volc_ws.send(build_text_frame(300, sid, {
            "content": "Hello! Welcome to English speaking practice. How are you today?"
        }))

        await ws.send_text(json.dumps({"type": "ready", "session_id": sid}))
        print(f"[voice] Ready!")

        done, pending = await asyncio.wait([b2v, v2b], return_when=asyncio.FIRST_COMPLETED)
        for t in pending: t.cancel()

    except Exception as e:
        print(f"[voice] Error: {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        if volc_ws:
            try: await volc_ws.send(build_text_frame(102, sid, {})); await volc_ws.close()
            except: pass

        # Run eval if student actually spoke
        if student_spoke[0] and transcript:
            try:
                await eval_conversation(username, transcript)
            except Exception as e:
                print(f"[voice] eval error: {e}")

        print(f"[voice] {username} disconnected")


async def eval_conversation(username: str, transcript: list):
    """After a voice call, evaluate progress and update student state."""
    if len(transcript) < 2:
        return

    # Build eval prompt
    convo_text = "\n".join([f"{'学生' if m['role']=='student' else '老师'}: {m['content'][:200]}" for m in transcript[-10:]])

    progress_path = f"data/student/{username}/oral_english_progress.md"
    state_path = progress_path
    template = "courses/oral_english/course_map.md"
    map_path = f"data/student/{username}/oral_english_map.md"
    if not os.path.exists(map_path) and os.path.exists(template):
        copy_file(template, map_path)
    current_state = read_file(state_path) if os.path.exists(state_path) else ""

    prompt = f"""你是英语教学评估专家。根据以下口语课对话，评估学生的表现并更新学习状态。

当前学生状态:
{current_state[:1500]}

本次口语课对话:
{convo_text}

请用 JSON 格式输出评估结果（只输出 JSON，不要其他文字）:
{{
  "observations": ["观察1", "观察2"],
  "skills_updated": [
    {{"skill": "技能名", "previous": "之前等级", "new": "新等级", "reason": "原因"}}
  ],
  "next_focus": "下次课应该重点练习什么",
  "summary": "一句话总结本次课"
}}"""

    llm = OpenRouterClient()
    try:
        resp = llm.chat([{"role": "user", "content": prompt}], stream=False)
        result = json.loads(resp.choices[0].message.content)

        # Append eval to state file
        summary = result.get("summary", "")
        next_focus = result.get("next_focus", "")
        updates = result.get("skills_updated", [])

        delta = f"\n\n## 口语课评估 ({__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
        delta += f"**总结**: {summary}\n"
        delta += f"**下次重点**: {next_focus}\n"
        if updates:
            delta += "\n**技能变化**:\n"
            for u in updates:
                delta += f"- {u['skill']}: {u['previous']} → {u['new']} ({u['reason']})\n"

        append_file(progress_path, delta)
        print(f"[voice] Eval saved: {summary[:80]}")
    except Exception as e:
        print(f"[voice] Eval parse error: {e}")
