"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


# Pydantic models for request bodies
class AnnouncementCreate(BaseModel):
    message: str = Field(..., max_length=500, description="Announcement message (max 500 characters)")
    expiration_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Expiration date in YYYY-MM-DD format")
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Optional start date in YYYY-MM-DD format")


class AnnouncementUpdate(BaseModel):
    message: str = Field(..., max_length=500, description="Announcement message (max 500 characters)")
    expiration_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Expiration date in YYYY-MM-DD format")
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Optional start date in YYYY-MM-DD format")


# Dependency for authentication
def verify_teacher(x_user_name: str = Header(..., alias="X-User-Name")) -> str:
    """Verify that the user is an authenticated teacher"""
    teacher = teachers_collection.find_one({"_id": x_user_name})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_user_name


# Helper function for date validation
def validate_dates(expiration_date: str, start_date: Optional[str] = None) -> None:
    """Validate date formats and ensure start date is before expiration date"""
    try:
        expiration_datetime = datetime.strptime(expiration_date, "%Y-%m-%d")
        if start_date:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            if start_datetime > expiration_datetime:
                raise HTTPException(
                    status_code=400,
                    detail="Start date must be before expiration date"
                )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@router.get("/active")
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all currently active announcements based on date range"""
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Find announcements where current date is within range
    query = {
        "expiration_date": {"$gte": current_date}
    }
    
    announcements = list(announcements_collection.find(query))
    
    # Filter by start date if present
    active_announcements = []
    for announcement in announcements:
        start_date = announcement.get("start_date")
        if not start_date or start_date <= current_date:
            # Convert ObjectId to string for JSON serialization
            announcement["_id"] = str(announcement["_id"])
            active_announcements.append(announcement)
    
    return active_announcements


@router.get("/all")
def get_all_announcements(username: str = Depends(verify_teacher)) -> List[Dict[str, Any]]:
    """Get all announcements (requires authentication)"""
    announcements = list(announcements_collection.find().sort("created_at", -1))
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.post("/")
def create_announcement(
    announcement_data: AnnouncementCreate,
    username: str = Depends(verify_teacher)
) -> Dict[str, Any]:
    """Create a new announcement (requires authentication)"""
    # Validate dates
    validate_dates(announcement_data.expiration_date, announcement_data.start_date)
    
    announcement = {
        "message": announcement_data.message,
        "start_date": announcement_data.start_date,
        "expiration_date": announcement_data.expiration_date,
        "created_by": username,
        "created_at": datetime.now().isoformat()
    }
    
    result = announcements_collection.insert_one(announcement)
    announcement["_id"] = str(result.inserted_id)
    
    return announcement


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    announcement_data: AnnouncementUpdate,
    username: str = Depends(verify_teacher)
) -> Dict[str, Any]:
    """Update an announcement (requires authentication)"""
    # Validate dates
    validate_dates(announcement_data.expiration_date, announcement_data.start_date)
    
    # Convert string ID to ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Check if announcement exists
    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    update_data = {
        "message": announcement_data.message,
        "start_date": announcement_data.start_date,
        "expiration_date": announcement_data.expiration_date
    }
    
    announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )
    
    updated = announcements_collection.find_one({"_id": obj_id})
    updated["_id"] = str(updated["_id"])
    
    return updated


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, username: str = Depends(verify_teacher)) -> Dict[str, str]:
    """Delete an announcement (requires authentication)"""
    # Convert string ID to ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
