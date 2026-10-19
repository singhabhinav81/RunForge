from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.config.logger import logger

router = APIRouter()

@router.get("/")
def root():
    return {"message": "Welcome to the RunForge API!"}
