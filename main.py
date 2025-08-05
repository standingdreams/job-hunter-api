from typing import Union, List
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from jobspy import scrape_jobs

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allows requests from your frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/jobs")
def get_jobs(
    search_term: str = Query(..., description="Job search term"),
    site_name: List[str] = Query(default=["indeed", "linkedin"]),
    is_remote: bool = Query(default=False),
    location: str = Query(default=""),
    results_wanted: int = Query(default=20),
    interval: str = Query(default="yearly"),
    country: str = Query(default="USA"),
    job_type: str = Query(default=""),
    hours_old: int = Query(default=72),
    offset: int = Query(default=0)
):
    """Scrape and return job listings"""
    jobs = scrape_jobs(
        site_name=site_name,
        search_term=search_term,
        # search_term="software engineer (javascript OR typescript OR react OR nodejs OR express OR python OR postgresql OR mysql OR mongo OR redis)",
        # google_search_term="software engineer jobs near Atlanta, GA",
        location=location,
        results_wanted=results_wanted,
        interval=interval,
        job_type=job_type,
        hours_old=hours_old,
        country_indeed=country,
        is_remote=is_remote,
        offset=offset,
        enforce_annual_salary=True,
        description_format="html"

        # linkedin_fetch_description=True # gets more info such as description, direct job url (slower)
        # proxies=["208.195.175.46:65095", "208.195.175.45:65095", "localhost"],
    )

    # Convert DataFrame to dict for JSON response
    # Handle NaN values by converting to dict first, then replacing
    if not jobs.empty:
        jobs_dict = jobs.to_dict('records')
        # Replace NaN values with None for JSON serialization
        import math
        for job in jobs_dict:
            for key, value in job.items():
                if isinstance(value, float) and math.isnan(value):
                    job[key] = None
        return {
            "jobs": jobs_dict
        }
    else:
        return {
            "jobs": []
        }

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}