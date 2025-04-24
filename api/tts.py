# # api/tts.py
# import os, json, asyncio
# from fastapi import FastAPI, Request, HTTPException
# from fastapi.responses import StreamingResponse
# from google import genai

# MODEL = "models/gemini-2.0-flash-live-001"
# client = genai.Client(http_options={"api_version": "v1beta"})

# app = FastAPI()

# async def pcm_chunks(text: str):
#     prompt = f"Please say this verbatim: {text}"
#     async with client.aio.live.connect(
#         model=MODEL, config={"response_modalities": ["AUDIO"]}
#     ) as sess:
#         await sess.send(input=prompt, end_of_turn=True)
#         async for part in sess.receive():
#             if part.data:
#                 yield part.data    # raw 24-kHz 16-bit PCM

# @app.post("/api/tts")
# async def tts(req: Request):
#     body = await req.body()
#     text = json.loads(body).get("text", "").strip()
#     if not text:
#         raise HTTPException(400, "text required")
#     return StreamingResponse(
#         pcm_chunks(text),
#         media_type="audio/l16;rate=24000"
#     )
# api/tts.py
import asyncio
import json
from http.server import BaseHTTPRequestHandler

from google import genai   # new genai SDK

MODEL  = "models/gemini-2.0-flash-live-001"
client = genai.Client(http_options={"api_version": "v1beta"})


async def pcm_chunks(text: str):
    """Yield raw PCM chunks from Gemini Live (AUDIO modality)."""
    prompt = f"Please say this verbatim: {text}"

    async with client.aio.live.connect(
        model=MODEL,
        config={"response_modalities": ["AUDIO"]},
    ) as sess:
        await sess.send(input=prompt, end_of_turn=True)
        async for part in sess.receive():
            if part.data:
                yield part.data          # 24 000 Hz, 16-bit, mono PCM


class handler(BaseHTTPRequestHandler):   # ← required name for Vercel Python runtime
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body   = json.loads(self.rfile.read(length))
            text   = body.get("text", "").strip()
            if not text:
                self.send_error(400, "text required")
                return

            # ——— start HTTP/1.1 chunked stream ———
            self.send_response(200)
            self.send_header("Content-Type", "audio/l16;rate=24000")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            # run the async generator in its own loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def stream():
                async for chunk in pcm_chunks(text):
                    # send each PCM chunk as a separate HTTP chunk:
                    #   <hex-size>\r\n<data>\r\n
                    size = f"{len(chunk):X}\r\n".encode()
                    self.wfile.write(size + chunk + b"\r\n")
                # terminator chunk
                self.wfile.write(b"0\r\n\r\n")

            loop.run_until_complete(stream())

        except Exception as e:
            self.send_error(500, f"server error: {e}")
