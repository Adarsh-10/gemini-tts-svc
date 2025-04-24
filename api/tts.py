# api/tts.py
import asyncio, json, base64
from http.server import BaseHTTPRequestHandler
from io import BytesIO
from google import genai

MODEL  = "models/gemini-2.0-flash-live-001"
RATE   = 24_000                # 24-kHz 16-bit PCM
client = genai.Client(http_options={"api_version": "v1beta"})

async def pcm_chunks(text: str):
    prompt = f"Please say this verbatim: {text}"
    async with client.aio.live.connect(
        model  = MODEL,
        config = {"response_modalities": ["AUDIO"]},
    ) as sess:
        await sess.send(input=prompt, end_of_turn=True)
        async for part in sess.receive():
            if part.data:
                yield part.data               # raw bytes

class handler(BaseHTTPRequestHandler):        # ← Vercel looks for this name
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body   = json.loads(self.rfile.read(length))
            text   = body.get("text", "").strip()
            if not text:
                self.send_error(400, "text required")
                return

            # --- start streaming response headers ---
            self.send_response(200)
            self.send_header("Content-Type", "audio/l16;rate=24000")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            # --- stream PCM chunks via HTTP/1.1 chunked encoding ---
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def stream():
                async for chunk in pcm_chunks(text):
                    size_hex = f"{len(chunk):X}\r\n".encode()
                    self.wfile.write(size_hex + chunk + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")   # terminator

            loop.run_until_complete(stream())

        except Exception as e:
            self.send_error(500, f"server error {e}")
