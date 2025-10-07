from sqlmodel import Field, SQLModel
from datetime import datetime

class Job(SQLModel, table=True):
  id: int | None = Field(default=None, primary_key=True)
  job_id: str | None = Field(default=None, unique=True)  # ID from the scraper/job site
  date_posted: datetime | None = None
  site: str | None = None
  job_url: str | None = None
  job_url_direct: str | None = None
  title: str | None = None
  company: str | None = None
  location: str | None = None
  job_type: str | None = None
  salary_source: str | None = None
  interval: str | None = None
  min_amount: int | None = None
  max_amount: int | None = None
  currency: str | None = None
  is_remote: bool | None = None
  job_level: str | None = None
  job_function: str | None = None
  listing_type: str | None = None
  description: str | None = None
  company_industry: str | None = None
  company_url: str | None = None
  company_logo: str | None = None
  company_url_direct: str | None = None
  company_addresses: str | None = None
  company_num_employees: str | None = None
  company_revenue: str | None = None
  company_description: str | None = None
  experience_range: str | None = None
  company_rating: float | None = None
  company_reviews_count: int | None = None
  vacancy_count: int | None = None
  work_from_home_type: str | None = None
  # emails: list[str] | None = None
  # skills: list[str] | None = None
