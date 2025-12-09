import os
import random
import uuid
import uuid as uuid_lib
import json
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import firestore
from google.cloud import pubsub_v1
from pydantic import BaseModel

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "dummy-project")
COLLECTION_NAME = "junbanapp"
PUBSUB_TOPIC_ID = os.environ.get("PUBSUB_TOPIC_ID")

# Initialize Clients (lazily or globally if safely possible)
# Note: In a real container, we expect ADC credentials. 
# For local dev without creds, this might fail, so we wrap in try-except or let it fail if critical.
try:
    db = firestore.Client(project=PROJECT_ID)
except Exception as e:
    print(f"Warning: Could not initialize Firestore client: {e}")
    db = None

try:
    publisher = pubsub_v1.PublisherClient()
except Exception as e:
    print(f"Warning: Could not initialize Pub/Sub client: {e}")
    publisher = None

class LikeRequest(BaseModel):
    page_id: str
    id: str # The name being liked

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit")
async def submit(
    names: str = Form(...),
    enable_likes: bool = Form(False)
):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore not configured")

    # Process names
    name_list = [n.strip() for n in names.splitlines() if n.strip()]
    if not name_list:
        # Return to form with error? For now just redirect back
        return RedirectResponse(url="/", status_code=303)

    # Shuffle
    random.shuffle(name_list)

    # Create document
    page_uuid = str(uuid_lib.uuid4())
    doc_ref = db.collection(COLLECTION_NAME).document(page_uuid)
    
    doc_data = {
        "names": name_list,
        "enable_likes": enable_likes,
        "created_at": datetime.utcnow()
    }
    doc_ref.set(doc_data)

    return RedirectResponse(url=f"/pages/{page_uuid}", status_code=303)

@app.get("/pages/{page_id}", response_class=HTMLResponse)
async def read_page(request: Request, page_id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore not configured")

    doc_ref = db.collection(COLLECTION_NAME).document(page_id)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Page not found")

    data = doc.to_dict()
    
    return templates.TemplateResponse("result.html", {
        "request": request, 
        "names": data.get("names", []), 
        "enable_likes": data.get("enable_likes", False),
        "page_id": page_id
    })

@app.post("/api/like")
async def like_api(like_req: LikeRequest):
    if not publisher:
        # If pubsub is not configured, we might log and return success to not break UI, or error.
        # User requirement implies this is core, so erroring might be better if truly broken,
        # but for local dev we might want to just print.
        print(f"PubSub not configured. Like event: {like_req}")
        return JSONResponse({"status": "ignored", "reason": "PubSub not configured"})

    if not PUBSUB_TOPIC_ID:
         print(f"PUBSUB_TOPIC_ID not set. Like event: {like_req}")
         return JSONResponse({"status": "ignored", "reason": "PUBSUB_TOPIC_ID not set"})

    topic_path = publisher.topic_path(PROJECT_ID, PUBSUB_TOPIC_ID)
    
    message_json = {
        "timestamp": datetime.utcnow().isoformat(),
        "page_id": like_req.page_id,
        "id": like_req.id
    }
    data = json.dumps(message_json).encode("utf-8")
    
    try:
        future = publisher.publish(topic_path, data)
        message_id = future.result()
        return JSONResponse({"status": "success", "message_id": message_id})
    except Exception as e:
        print(f"Error publishing to PubSub: {e}")
        raise HTTPException(status_code=500, detail=str(e))
