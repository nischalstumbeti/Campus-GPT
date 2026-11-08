"""End-to-end Campus-GPT chatbot verification (all desks + voice)."""
from __future__ import annotations

import asyncio
import math
import struct
import wave
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8002"
EMAIL = "student.demo@klu.ac.in"
PASSWORD = "campus123"

AGENTS = [
    ("general", "What facilities does the campus have?"),
    ("academic", "What is my attendance?"),
    ("faculty", "Show faculty office hours"),
    ("admission", "What is the admission process?"),
    ("reception", "Tell me complete information about KARE college"),
    ("reception", "Where is the library and examination branch?"),
    ("reception", "Give department contact emails and phones"),
    ("hostel", "What is my hostel room?"),
    ("hostel", "What is my attendance?"),  # should redirect
    ("warden", "What are the hostel rules?"),
]


def _tone_wav(path: Path, seconds: float = 1.0, sr: int = 16000) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(int(sr * seconds)):
            val = int(10000 * math.sin(2 * math.pi * 440 * i / sr))
            w.writeframes(struct.pack("<h", val))
    return path.read_bytes()


async def main() -> None:
    results: list[str] = []
    async with httpx.AsyncClient(timeout=120.0) as c:
        login = await c.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code >= 400:
            print("LOGIN FAIL", login.status_code, login.text[:300])
            return
        token = login.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        results.append(f"LOGIN ok role={login.json().get('user', {}).get('role')}")

        for agent, message in AGENTS:
            r = await c.post(
                f"{BASE}/api/chat",
                headers=h,
                json={"message": message, "agent_type": agent, "history": []},
            )
            body = r.json() if r.content else {}
            ans = (body.get("answer") or "")[:180].replace("\n", " ")
            bad = "temporary AI error" in ans.lower() or r.status_code >= 400
            intent = body.get("intent")
            results.append(
                f"{'FAIL' if bad else 'OK  '} [{agent}] q={message!r} status={r.status_code} intent={intent} | {ans}"
            )

        # Voice STT
        wav = _tone_wav(Path("data/_e2e_tone.wav"))
        stt = await c.post(
            f"{BASE}/api/voice",
            files={"file": ("tone.wav", wav, "audio/wav")},
        )
        results.append(
            f"{'OK  ' if stt.status_code == 200 else 'FAIL'} [voice-stt] status={stt.status_code} body={stt.text[:120]}"
        )

        # Voice TTS
        tts = await c.post(f"{BASE}/api/tts", json={"text": "Welcome to Kalasalingam University reception desk."})
        results.append(
            f"{'OK  ' if tts.status_code == 200 and len(tts.content) > 500 else 'FAIL'} [voice-tts] status={tts.status_code} bytes={len(tts.content)}"
        )

        # Rebuild knowledge with expanded seed (admin)
        # Prefer existing admin account via UIS-linked login if possible
        admin_login = await c.post(
            f"{BASE}/api/auth/login",
            json={"email": "admin@example.com", "password": "campus123"},
        )
        if admin_login.status_code < 400:
            ah = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
            train = await c.post(f"{BASE}/api/admin/train/public", headers=ah, json={})
            results.append(
                f"{'OK  ' if train.status_code == 200 else 'FAIL'} [train] status={train.status_code} body={train.text[:180]}"
            )
        else:
            results.append(f"SKIP [train] admin login {admin_login.status_code}")

    print("\n".join(results))
    fails = [x for x in results if x.startswith("FAIL")]
    print(f"\nSUMMARY: {len(results) - len(fails)}/{len(results)} checks passed, {len(fails)} failed")


if __name__ == "__main__":
    asyncio.run(main())
