import os
import re
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from api.security import authorize
router=APIRouter(prefix="/media",tags=["media"])
UPLOAD_DIR=Path(os.getenv("UPLOAD_DIR","/app/uploads")); UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
@router.post("/upload",dependencies=[Depends(authorize)])
async def upload(file:UploadFile=File(...)):
 if file.content_type not in {'image/jpeg','image/png','image/webp','image/gif'}: raise HTTPException(415,"Only image uploads are allowed")
 content=await file.read()
 if len(content)>5*1024*1024: raise HTTPException(413,"Image limit is 5MB")
 ext={"image/jpeg":".jpg","image/png":".png","image/webp":".webp","image/gif":".gif"}[file.content_type]
 name=f"{uuid.uuid4().hex}{ext}"; (UPLOAD_DIR/name).write_bytes(content); return {"url":f"/api/v1/media/{name}"}
@router.get("/{filename}")
def serve(filename:str):
 if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|png|webp|gif)",filename): raise HTTPException(404,"Not found")
 path=UPLOAD_DIR/filename
 if not path.is_file(): raise HTTPException(404,"Not found")
 return FileResponse(path)
