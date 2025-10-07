from typing import List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text
from datetime import datetime, timedelta
from jobspy import scrape_jobs
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
import math
from db.schema import Job

max_results_wanted = 10

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((requests.exceptions.RetryError, requests.exceptions.RequestException))
)
def _scrape_jobs_with_retry(**kwargs):
    """Internal function to scrape jobs with retry logic"""
    return scrape_jobs(**kwargs)

class JobController:
    """Controller for job-related business logic"""

    @staticmethod
    async def search_jobs(
        session: AsyncSession,
        search_term: str,
        site_name: List[str],
        is_remote: bool,
        location: str,
        results_wanted: int,
        interval: str,
        country: str,
        job_type: str,
        hours_old: int,
        offset: int
    ) -> Dict[str, Any]:
        """
        Search for jobs, combining database results with scraped results as needed
        """

        # Get jobs from database first
        db_jobs_dict = await JobController._get_jobs_from_database(
            session, search_term, location, is_remote, job_type,
            hours_old, offset, results_wanted
        )

        # Debug logging
        print(f"🔍 DEBUG: results_wanted = {results_wanted}")
        print(f"🔍 DEBUG: db_jobs_dict length = {len(db_jobs_dict)}")

        # 🚨 DEBUGGING MODE: BYPASSING SCRAPER - ONLY RETURNING DATABASE RESULTS
        print(f"🚨 DEBUG MODE: Bypassing scraper, only returning database results")
        print(f"🔍 DEBUG: Found {len(db_jobs_dict)} jobs from database")
        print(f"🔍 DEBUG: results_wanted = {results_wanted}")

        # Return all database results (up to results_wanted)
        final_jobs = db_jobs_dict[:results_wanted] if len(db_jobs_dict) > results_wanted else db_jobs_dict

        print(f"🔍 DEBUG: Returning {len(final_jobs)} jobs from database only")

        return {
            "jobs": final_jobs,
            "source": {
                "database": len(final_jobs),
                "scraped": 0,
                "total": len(final_jobs)
            },
            "debug_mode": "scraper_bypassed"
        }

        # COMMENTED OUT FOR DEBUGGING - ORIGINAL SCRAPER LOGIC:
        # # Check if we have enough results from the database
        # if len(db_jobs_dict) >= results_wanted:
        #     print(f"🔍 DEBUG: Returning {len(db_jobs_dict)} jobs from database (sufficient)")
        #     return {
        #         "jobs": db_jobs_dict
        #     }

        # # We need more results - scrape additional jobs
        # additional_needed = results_wanted - len(db_jobs_dict)

        # try:
        #     scraped_jobs_dict = await JobController._scrape_additional_jobs(
        #         session, db_jobs_dict, additional_needed, site_name, search_term,
        #         location, interval, job_type, hours_old, country, is_remote, offset
        #     )

        #     # Combine results
        #     combined_jobs = db_jobs_dict + scraped_jobs_dict
        #     final_jobs = combined_jobs[:results_wanted]

        #     print(f"🔍 DEBUG: combined_jobs length = {len(combined_jobs)}")
        #     print(f"🔍 DEBUG: final_jobs length = {len(final_jobs)}")
        #     print(f"🔍 DEBUG: results_wanted = {results_wanted}")

        #     return {
        #         "jobs": final_jobs,
        #         "source": {
        #             "database": len(db_jobs_dict),
        #             "scraped": len(scraped_jobs_dict),
        #             "total": len(final_jobs)
        #         }
        #     }

        # except (requests.exceptions.RetryError, requests.exceptions.RequestException) as e:
        #     # If scraping fails but we have some db results, return what we have
        #     if db_jobs_dict:
        #         return {
        #             "jobs": db_jobs_dict,
        #             "warning": f"Scraping service unavailable, returning {len(db_jobs_dict)} cached results"
        #         }
        #     # If no db results and scraping fails, raise the error
        #     raise e

    @staticmethod
    async def _get_jobs_from_database(
        session: AsyncSession,
        search_term: str,
        location: str,
        is_remote: bool,
        job_type: str,
        hours_old: int,
        offset: int,
        results_wanted: int
    ) -> List[Dict[str, Any]]:
        """Query jobs from database with filters"""

        print(f"🔍 DEBUG DB QUERY: Starting database query with parameters:")
        print(f"🔍 DEBUG DB QUERY: search_term='{search_term}', location='{location}', is_remote={is_remote}")
        print(f"🔍 DEBUG DB QUERY: job_type='{job_type}', hours_old={hours_old}, offset={offset}, results_wanted={results_wanted}")

        # First, let's check how many total jobs are in the database
        total_count_query = select(Job)
        total_result = await session.execute(total_count_query)
        total_jobs = total_result.scalars().all()
        print(f"🔍 DEBUG DB QUERY: Total jobs in database: {len(total_jobs)}")

        # Show a few sample jobs for debugging
        if total_jobs:
            print(f"🔍 DEBUG DB QUERY: Sample jobs in database:")
            for i, job in enumerate(total_jobs[:5]):  # Show first 5 jobs
                print(f"🔍 DEBUG DB QUERY: Sample {i+1}: title='{job.title}', company='{job.company}', location='{job.location}', job_id='{job.job_id}'")

        # Create query to find jobs matching the parameters
        db_jobs_query = select(Job)

        # Filter by search term using PostgreSQL full-text search
        if search_term:
            print(f"🔍 DEBUG DB QUERY: Adding full-text search filter for '{search_term}'")
            
            # Create a full-text search query using PostgreSQL's to_tsvector and plainto_tsquery
            # This searches across title, company, and description fields
            # plainto_tsquery handles complex terms like "javascript OR typescript OR react"
            
            full_text_condition = text("""
                (to_tsvector('english', COALESCE(title, '')) @@ plainto_tsquery('english', :search_term)) OR
                (to_tsvector('english', COALESCE(company, '')) @@ plainto_tsquery('english', :search_term)) OR
                (to_tsvector('english', COALESCE(description, '')) @@ plainto_tsquery('english', :search_term))
            """).bindparams(search_term=search_term)
            
            db_jobs_query = db_jobs_query.where(full_text_condition)

        # Filter by location
        if location:
            print(f"🔍 DEBUG DB QUERY: Adding location filter for '{location}'")
            db_jobs_query = db_jobs_query.where(Job.location.ilike(f"%{location}%"))

        # Filter by remote status
        if is_remote is not None:
            print(f"🔍 DEBUG DB QUERY: Adding is_remote filter for {is_remote}")
            db_jobs_query = db_jobs_query.where(Job.is_remote == is_remote)

        # Filter by job type
        if job_type:
            print(f"🔍 DEBUG DB QUERY: Adding job_type filter for '{job_type}'")
            db_jobs_query = db_jobs_query.where(Job.job_type.ilike(f"%{job_type}%"))

        # Filter by hours_old (jobs posted within the specified hours)
        if hours_old > 0:
            cutoff_date = datetime.utcnow() - timedelta(hours=hours_old)
            print(f"🔍 DEBUG DB QUERY: Adding hours_old filter - cutoff_date: {cutoff_date}")
            db_jobs_query = db_jobs_query.where(Job.date_posted >= cutoff_date)

        # Apply offset and limit
        print(f"🔍 DEBUG DB QUERY: Applying offset={offset} and limit={results_wanted}")
        db_jobs_query = db_jobs_query.offset(offset).limit(results_wanted)

        # Debug: Show the compiled SQL query
        try:
            compiled_query = str(db_jobs_query.compile(compile_kwargs={"literal_binds": True}))
            print(f"🔍 DEBUG DB QUERY: SQL Query: {compiled_query}")
        except Exception as e:
            print(f"🔍 DEBUG DB QUERY: Could not compile query for debugging: {e}")

        # Execute the query
        print(f"🔍 DEBUG DB QUERY: Executing database query...")
        result = await session.execute(db_jobs_query)
        db_jobs = result.scalars().all()
        return [job.dict() for job in db_jobs] if db_jobs else []

    @staticmethod
    async def _scrape_additional_jobs(
        session: AsyncSession,
        db_jobs_dict: List[Dict[str, Any]],
        additional_needed: int,
        site_name: List[str],
        search_term: str,
        location: str,
        interval: str,
        job_type: str,
        hours_old: int,
        country: str,
        is_remote: bool,
        offset: int
    ) -> List[Dict[str, Any]]:
        """Scrape additional jobs when database doesn't have enough results"""

        # Console log when scraping is needed
        print("=" * 60)
        print("🔍 SCRAPING NEEDED!")
        print(f"📊 Database results: {len(db_jobs_dict)}")
        print(f"🎯 Results wanted: {len(db_jobs_dict) + additional_needed}")
        print(f"⚡ Additional needed: {additional_needed}")
        print(f"🔎 Search term: {search_term}")
        print(f"📍 Location: {location}")
        print("=" * 60)

        # Calculate scraper offset: if we have db results, start from where they left off
        scraper_offset = offset + len(db_jobs_dict) if db_jobs_dict else offset

        jobs = _scrape_jobs_with_retry(
            site_name=site_name,
            search_term=search_term,
            location=location,
            results_wanted=additional_needed,  # Request exactly what we need
            interval=interval,
            job_type=job_type,
            hours_old=hours_old,
            country_indeed=country,
            is_remote=is_remote,
            offset=scraper_offset,
            enforce_annual_salary=True,
            description_format="html"
        )

        scraped_jobs_dict = []

        # Process scraped results
        if not jobs.empty:
            scraped_jobs_dict = jobs.to_dict('records')
            print(f"🔍 DEBUG: Raw scraped jobs count: {len(scraped_jobs_dict)}")

            # Replace NaN values with None for JSON serialization
            for job in scraped_jobs_dict:
                for key, value in job.items():
                    if isinstance(value, float) and math.isnan(value):
                        job[key] = None

            # Filter out duplicates based on job_id (scraper ID)
            scraped_jobs_dict = await JobController._filter_duplicate_jobs(
                session, scraped_jobs_dict, additional_needed
            )
            print(f"🔍 DEBUG: Filtered scraped jobs count: {len(scraped_jobs_dict)}")

            # Log scraping success
            print("✅ SCRAPING COMPLETED!")
            print(f"🎉 Found {len(scraped_jobs_dict)} new unique jobs")
            print("=" * 60)

            # Insert new scraped jobs into the database
            print(f"🔍 DEBUG: About to save {len(scraped_jobs_dict)} scraped jobs to database")
            await JobController._save_jobs_to_database(session, scraped_jobs_dict)
        else:
            print("🔍 DEBUG: No jobs returned from scraper (jobs.empty)")

        return scraped_jobs_dict

    @staticmethod
    async def _filter_duplicate_jobs(
        session: AsyncSession,
        scraped_jobs: List[Dict[str, Any]],
        additional_needed: int
    ) -> List[Dict[str, Any]]:
        """Filter out duplicate jobs based on job_id (scraper ID) by checking against entire database"""

        if not scraped_jobs:
            return []

        # Get all job_ids from scraped jobs
        scraper_job_ids = [job.get('id') for job in scraped_jobs if job.get('id')]

        if not scraper_job_ids:
            print("🔍 DEBUG: No job IDs found in scraped jobs")
            return scraped_jobs[:additional_needed]

        print(f"🔍 DEBUG: Checking {len(scraper_job_ids)} scraped job IDs against database")

        # Query database to find existing job_ids
        existing_job_ids_query = select(Job.job_id).where(Job.job_id.in_(scraper_job_ids))
        result = await session.execute(existing_job_ids_query)
        existing_job_ids = set(result.scalars().all())

        print(f"🔍 DEBUG: Found {len(existing_job_ids)} existing job_ids in database: {existing_job_ids}")

        filtered_jobs = []
        processed_ids = set()  # Track IDs we've already processed in this batch

        for job in scraped_jobs:
            scraper_job_id = job.get('id')  # Get ID from scraper

            # Skip if no job ID
            if not scraper_job_id:
                print(f"🔍 DEBUG: Skipping job without ID: {job.get('title', 'Unknown title')}")
                continue

            # Skip if duplicate in database
            if scraper_job_id in existing_job_ids:
                print(f"🔍 DEBUG: Skipping duplicate job_id '{scraper_job_id}' (exists in database)")
                continue

            # Skip if duplicate in current batch
            if scraper_job_id in processed_ids:
                print(f"🔍 DEBUG: Skipping duplicate job_id '{scraper_job_id}' (duplicate in current batch)")
                continue

            filtered_jobs.append(job)
            processed_ids.add(scraper_job_id)

            print(f"🔍 DEBUG: Added job_id '{scraper_job_id}' to filtered jobs")

            # Stop when we have enough additional results
            if len(filtered_jobs) >= additional_needed:
                break

        print(f"🔍 DEBUG: Filtered {len(scraped_jobs)} scraped jobs down to {len(filtered_jobs)} unique jobs")
        return filtered_jobs

    @staticmethod
    async def _save_jobs_to_database(session: AsyncSession, jobs_dict: List[Dict[str, Any]]) -> None:
        """Save scraped jobs to database"""

        if not jobs_dict:
            print("🔍 DEBUG: No jobs to save (jobs_dict is empty)")
            return

        print(f"🔍 DEBUG: Attempting to save {len(jobs_dict)} jobs to database")

        try:
            new_db_jobs = []
            for i, job_data in enumerate(jobs_dict):
                try:
                    # Map scraper's 'id' to 'job_id' and exclude the original 'id'
                    job_dict = {k: v for k, v in job_data.items() if k != 'id'}
                    if 'id' in job_data:
                        job_dict['job_id'] = job_data['id']
                        print(f"🔍 DEBUG: Job {i+1}: Mapping scraper ID '{job_data['id']}' to job_id")
                    else:
                        print(f"🔍 DEBUG: Job {i+1}: No 'id' field found in job_data")

                    # Print a few key fields to debug
                    print(f"🔍 DEBUG: Job {i+1}: title='{job_dict.get('title', 'N/A')}', company='{job_dict.get('company', 'N/A')}'")

                    new_job = Job(**job_dict)
                    new_db_jobs.append(new_job)
                    print(f"🔍 DEBUG: Job {i+1}: Successfully created Job object")
                except Exception as job_error:
                    print(f"❌ ERROR: Failed to create Job object for job {i+1}: {job_error}")
                    print(f"❌ ERROR: Job data keys: {list(job_data.keys())}")
                    continue

            print(f"🔍 DEBUG: Created {len(new_db_jobs)} Job objects")

            if new_db_jobs:
                session.add_all(new_db_jobs)
                print("🔍 DEBUG: Added jobs to session, committing...")
                await session.commit()
                print("✅ DEBUG: Successfully committed jobs to database!")
            else:
                print("⚠️ DEBUG: No valid jobs to save")

        except Exception as e:
            print(f"❌ ERROR: Failed to save jobs to database: {e}")
            print(f"❌ ERROR: Exception type: {type(e)}")

            # Check if it's a unique constraint violation
            error_message = str(e).lower()
            if 'unique' in error_message or 'duplicate' in error_message:
                print("⚠️ DEBUG: Detected unique constraint violation - some jobs may already exist")
                # Try to save jobs individually to identify which ones are duplicates
                await session.rollback()
                await JobController._save_jobs_individually(session, new_db_jobs)
            else:
                await session.rollback()
                print("🔄 DEBUG: Rolled back transaction")
                raise e

    @staticmethod
    async def _save_jobs_individually(session: AsyncSession, jobs: List[Job]) -> None:
        """Save jobs individually to handle unique constraint violations gracefully"""

        saved_count = 0
        duplicate_count = 0

        for i, job in enumerate(jobs):
            try:
                session.add(job)
                await session.commit()
                saved_count += 1
                print(f"✅ DEBUG: Successfully saved job {i+1} individually (job_id: {job.job_id})")
            except Exception as e:
                await session.rollback()
                error_message = str(e).lower()
                if 'unique' in error_message or 'duplicate' in error_message:
                    duplicate_count += 1
                    print(f"⚠️ DEBUG: Skipped duplicate job {i+1} (job_id: {job.job_id})")
                else:
                    print(f"❌ ERROR: Failed to save job {i+1} individually: {e}")

        print(f"📊 DEBUG: Individual save results - Saved: {saved_count}, Duplicates: {duplicate_count}, Total: {len(jobs)}")
