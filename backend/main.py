import os
import base64
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from bson import ObjectId
import httpx

# --- CONFIG ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
WAHA_API_URL = os.getenv("WAHA_API_URL", "http://waha:3000")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "secret123")

app = FastAPI()

# CORS (Allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE CONNECTION ---
client = AsyncIOMotorClient(MONGO_URI)
db = client.whatsdoc
customers = db.customers

# --- MODELS ---
class CustomerCreate(BaseModel):
    name: str
    phone: str
    videoName: str

class CustomerResponse(BaseModel):
    id: str
    customerName: str
    phoneNumber: str
    videoName: str
    status: str
    requestedAt: str

# --- HELPERS ---
def pydantic_encoder(item):
    """Convert Mongo Object to JSON compatible dict"""
    return {
        "id": str(item["_id"]),
        "customerName": item["customerName"],
        "phoneNumber": item["phoneNumber"],
        "videoName": item["videoName"],
        "status": item.get("status", "pending"),
        "requestedAt": item.get("requestedAt")
    }

async def send_whatsapp_message(phone: str, name: str, video_name: str, file_content: bytes, mime_type: str, filename: str):
    """Sends the file via WAHA"""
    
    # Clean phone number
    chat_id = f"{phone.replace('+', '').replace('-', '').strip()}@c.us"
    
    # Convert file to base64
    b64_data = base64.b64encode(file_content).decode('utf-8')
    data_uri = f"data:{mime_type};base64,{b64_data}"

    payload = {
        "chatId": chat_id,
        "caption": f"Hi {name}! Here is the document you requested: {video_name}. Thanks for visiting us!",
        "session": "default",
        "file": {
            "mimetype": mime_type,
            "filename": filename,
            "data": data_uri
        }
    }

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": WAHA_API_KEY
    }

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        try:
            print(f"Sending to WAHA: {chat_id}")
            response = await http_client.post(f"{WAHA_API_URL}/api/sendFile", json=payload, headers=headers)
            response.raise_for_status()
            print(f"WAHA Response: {response.text}")
            return True
        except Exception as e:
            print(f"WAHA Error: {str(e)}")
            return False

# --- ENDPOINTS ---

@app.post("/api/register-customer")
async def register_customer(request: CustomerCreate):
    new_customer = {
        "customerName": request.name,
        "phoneNumber": request.phone,
        "videoName": request.videoName,
        "status": "pending",
        "requestedAt": datetime.utcnow().isoformat()
    }
    result = await customers.insert_one(new_customer)
    return {"success": True, "id": str(result.inserted_id)}

@app.get("/api/get-pending")
async def get_pending():
    pending_docs = await customers.find({"status": "pending"}).sort("requestedAt", 1).limit(100).to_list(length=100)
    return [pydantic_encoder(doc) for doc in pending_docs]

@app.post("/api/upload-document")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    requestId: str = Form(...),
    phoneNumber: str = Form(...),
    videoName: str = Form(...)
):
    # 1. Read file
    content = await file.read()
    
    # 2. Verify Request Exists
    try:
        req_oid = ObjectId(requestId)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")

    customer = await customers.find_one({"_id": req_oid})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer request not found")

    # 3. Send to WhatsApp (Async to not block response)
    # Note: We await here for simplicity to ensure success before updating DB, 
    # but in high load, this could be a background task.
    success = await send_whatsapp_message(
        phone=phoneNumber,
        name=customer['customerName'],
        video_name=videoName,
        file_content=content,
        mime_type=file.content_type,
        filename=file.filename
    )

    if success:
        # 4. Update DB
        await customers.update_one(
            {"_id": req_oid},
            {"$set": {"status": "completed", "completedAt": datetime.utcnow().isoformat()}}
        )
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to send WhatsApp message")

@app.get("/health")
def health_check():
    return {"status": "ok"}
