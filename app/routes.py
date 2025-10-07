from typing import List
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlmodel import Session
import requests
from sqlmodel.ext.asyncio.session import AsyncSession
from db.database import get_session
from app.controller import JobController, max_results_wanted

router = APIRouter()

@router.get("/")
def read_root():
    return {"Hello": "World"}

@router.get("/jobs")
async def get_jobs(
    search_term: str = Query(..., description="Job search term"),
    site_name: List[str] = Query(default=["indeed", "linkedin"]),
    is_remote: bool = Query(default=False),
    location: str = Query(default=""),
    results_wanted: int = Query(default=max_results_wanted),
    interval: str = Query(default="yearly"),
    country: str = Query(default="USA"),
    job_type: str = Query(default=""),
    hours_old: int = Query(default=72),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_session)
):
    """Search and return job listings"""

    try:
        result = await JobController.search_jobs(
            session=session,
            search_term=search_term,
            site_name=site_name,
            is_remote=is_remote,
            location=location,
            results_wanted=results_wanted,
            interval=interval,
            country=country,
            job_type=job_type,
            hours_old=hours_old,
            offset=offset
        )
        return result

    except (requests.exceptions.RetryError, requests.exceptions.RequestException) as e:
        raise HTTPException(
            status_code=503,
            detail=f"Job scraping service temporarily unavailable after 3 attempts: {str(e)}"
        )