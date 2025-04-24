# api/tts.py
import os, json, asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from google import genai

MODEL = "models/gemini-2.0-flash-live-001"
client = genai.Client(http_options={"api_version": "v1beta"})

app = FastAPI()

async def pcm_chunks(text: str):
    prompt = f"Please say this verbatim: {text}"
    async with client.aio.live.connect(
        model=MODEL, config={"response_modalities": ["AUDIO"]}
    ) as sess:
        await sess.send(input=prompt, end_of_turn=True)
        async for part in sess.receive():
            if part.data:
                yield part.data    # raw 24-kHz 16-bit PCM

@app.post("/api/tts")
async def tts(req: Request):
    body = await req.body()
    text = json.loads(body).get("text", "").strip()
    if not text:
        raise HTTPException(400, "text required")
    return StreamingResponse(
        pcm_chunks(text),
        media_type="audio/l16;rate=24000"
    )
