from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import re
import google.generativeai as genai
from typing import Dict, AsyncGenerator
import json
import asyncio
from mangum import Mangum

# Initialize FastAPI app
app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Use environment variable for Gemini API key
GEMINI_API_KEY = "AIzaSyBIt3R4o4PfgMM398jhgGQRzh742yAArcQ"  # Add your Gemini API key here
genai.configure(api_key=GEMINI_API_KEY)

# In-memory storage
repo_data: Dict[str, Dict] = {"files": {}, "explanations": {}}

def parse_github_url(url: str) -> tuple[str, str]:
    pattern = r"https://github.com/([^/]+)/([^/]+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid GitHub URL")
    return match.groups()

async def fetch_repo_contents(username: str, repo: str, path: str = "") -> Dict[str, str]:
    api_url = f"https://api.github.com/repos/{username}/{repo}/contents/{path}"
    async with httpx.AsyncClient() as client:
        response = await client.get(api_url, headers={"Accept": "application/vnd.github.v3+json"})
        if response.status_code != 200:
            raise Exception(f"Failed to fetch repo contents at {path}: {response.status_code}")
        files = response.json()
        file_data = {}
        for item in files:
            if item["type"] == "file":
                content_url = item["download_url"]
                content_response = await client.get(content_url)
                file_path = item["path"]
                file_data[file_path] = content_response.text if content_response.status_code == 200 else "Unable to fetch content."
            elif item["type"] == "dir":
                subdir_data = await fetch_repo_contents(username, repo, item["path"])
                file_data.update(subdir_data)
        return file_data

def explain_file(file_name: str, content: str) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Explain the purpose of a file named '{file_name}' with this content:\n\n{content[:2000]}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Gemini API Error: {str(e)}"

async def stream_file_explanations(files: Dict[str, str]) -> AsyncGenerator[str, None]:
    explanations = {}
    for file_name, content in files.items():
        explanation = explain_file(file_name, content)
        explanations[file_name] = explanation
        yield json.dumps({"status": "success", "file": file_name, "explanation": explanation}) + "\n"
        await asyncio.sleep(0.1)
    repo_data["explanations"] = explanations

def answer_question(question: str) -> str:
    model = genai.GenerativeModel("gemini-1.5-flash")
    context = "Repository files and explanations:\n"
    for file_name, explanation in repo_data["explanations"].items():
        context += f"{file_name}: {explanation}\n"
    prompt = f"Based on this repository info:\n{context}\nAnswer this question: {question}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Gemini API Error: {str(e)}"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze")
async def analyze(github_url: str = Form(...)):
    try:
        username, repo = parse_github_url(github_url)
        files = await fetch_repo_contents(username, repo)
        repo_data["files"] = files
        return StreamingResponse(stream_file_explanations(files), media_type="text/event-stream")
    except Exception as e:
        async def error_stream():
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

@app.post("/ask")
async def ask(question: str = Form(...)):
    try:
        answer = answer_question(question)
        return {"status": "success", "answer": answer}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Vercel handler
handler = Mangum(app, lifespan="off")  # Explicitly disable lifespan events
