"""
Management command: python manage.py seed_data --tenant-id=<uuid>

Seeds default pipeline stages, sample jobs, applicants, applications,
call records, scorecards, and interviews for a given tenant.
"""
import uuid
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify


OWNER_USER_ID_DEFAULT = "00000000-0000-0000-0000-000000000001"


class Command(BaseCommand):
    help = "Seed demo data for a given tenant"

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True, help="Tenant UUID to seed data for")
        parser.add_argument(
            "--owner-id",
            default=OWNER_USER_ID_DEFAULT,
            help="Owner user UUID (defaults to a placeholder)",
        )

    def handle(self, *args, **options):
        tenant_id = options["tenant_id"]
        owner_user_id = options["owner_id"]

        try:
            uuid.UUID(tenant_id)
        except ValueError:
            raise CommandError(f"Invalid tenant-id: {tenant_id}")

        self.stdout.write(f"Seeding data for tenant {tenant_id}...")

        self._seed_pipeline_stages(tenant_id, owner_user_id)
        jobs = self._seed_jobs(tenant_id, owner_user_id)
        applicants = self._seed_applicants(tenant_id, owner_user_id)
        applications = self._seed_applications(tenant_id, owner_user_id, jobs, applicants)
        self._seed_call_records(tenant_id, owner_user_id, applications)
        self._seed_interviews(tenant_id, owner_user_id, applications)

        self.stdout.write(self.style.SUCCESS("Seed data created successfully."))

    # ------------------------------------------------------------------

    def _seed_pipeline_stages(self, tenant_id: str, owner_user_id: str) -> list:
        from pipeline.models import PipelineStage

        defaults = [
            {"name": "Applied", "color": "#6b7280", "order": 0, "is_default": True},
            {"name": "AI Screening", "color": "#8b5cf6", "order": 1},
            {"name": "Shortlisted", "color": "#3b82f6", "order": 2},
            {"name": "Interview", "color": "#f59e0b", "order": 3},
            {"name": "Offer", "color": "#10b981", "order": 4},
            {"name": "Hired", "color": "#059669", "order": 5, "is_terminal": True},
            {"name": "Rejected", "color": "#ef4444", "order": 6, "is_terminal": True},
        ]
        stages = []
        for data in defaults:
            slug = slugify(data["name"])
            stage, created = PipelineStage.objects.get_or_create(
                tenant_id=tenant_id,
                slug=slug,
                defaults={
                    "name": data["name"],
                    "color": data["color"],
                    "order": data["order"],
                    "is_default": data.get("is_default", False),
                    "is_terminal": data.get("is_terminal", False),
                    "owner_user_id": owner_user_id,
                },
            )
            stages.append(stage)
            if created:
                self.stdout.write(f"  Created pipeline stage: {stage.name}")
        return stages

    def _seed_jobs(self, tenant_id: str, owner_user_id: str) -> list:
        from jobs.models import Job

        jobs_data = [
            {
                "title": "Senior Python Developer",
                "department": "Engineering",
                "location": "Remote",
                "job_type": Job.JobType.FULL_TIME,
                "experience_level": Job.ExperienceLevel.SENIOR,
                "salary_min": Decimal("80000"),
                "salary_max": Decimal("120000"),
                "description": "We are looking for an experienced Python developer to join our backend team.",
                "requirements": "5+ years Python, Django/FastAPI, PostgreSQL, Redis, Docker",
                "status": Job.Status.OPEN,
                "published_at": timezone.now(),
            },
            {
                "title": "React Frontend Engineer",
                "department": "Engineering",
                "location": "New York, NY",
                "job_type": Job.JobType.FULL_TIME,
                "experience_level": Job.ExperienceLevel.MID,
                "salary_min": Decimal("70000"),
                "salary_max": Decimal("100000"),
                "description": "Join our product team building modern React applications.",
                "requirements": "3+ years React, TypeScript, REST APIs, CSS/Tailwind",
                "status": Job.Status.OPEN,
                "published_at": timezone.now(),
            },
            {
                "title": "Product Manager",
                "department": "Product",
                "location": "San Francisco, CA",
                "job_type": Job.JobType.FULL_TIME,
                "experience_level": Job.ExperienceLevel.SENIOR,
                "salary_min": Decimal("100000"),
                "salary_max": Decimal("150000"),
                "description": "Drive product strategy and roadmap for our SaaS platform.",
                "requirements": "5+ years product management, B2B SaaS, data-driven decision making",
                "status": Job.Status.OPEN,
                "published_at": timezone.now(),
            },
        ]

        jobs = []
        for data in jobs_data:
            job, created = Job.objects.get_or_create(
                tenant_id=tenant_id,
                title=data["title"],
                defaults={**data, "owner_user_id": owner_user_id},
            )
            jobs.append(job)
            if created:
                self.stdout.write(f"  Created job: {job.title}")
        return jobs

    def _seed_applicants(self, tenant_id: str, owner_user_id: str) -> list:
        from applicants.models import Applicant

        applicants_data = [
            {
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@example.com",
                "phone": "+14155550001",
                "skills": ["Python", "Django", "PostgreSQL", "Docker"],
                "experience_years": 6,
                "current_role": "Senior Software Engineer",
                "current_company": "TechCorp",
                "source": Applicant.Source.LINKEDIN,
            },
            {
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob.smith@example.com",
                "phone": "+14155550002",
                "skills": ["React", "TypeScript", "Node.js", "CSS"],
                "experience_years": 4,
                "current_role": "Frontend Developer",
                "current_company": "StartupXYZ",
                "source": Applicant.Source.WEBSITE,
            },
            {
                "first_name": "Carol",
                "last_name": "Williams",
                "email": "carol.williams@example.com",
                "phone": "+14155550003",
                "skills": ["Product Management", "Agile", "SQL", "Analytics"],
                "experience_years": 7,
                "current_role": "Product Manager",
                "current_company": "BigCo",
                "source": Applicant.Source.REFERRAL,
            },
            {
                "first_name": "David",
                "last_name": "Lee",
                "email": "david.lee@example.com",
                "phone": "+14155550004",
                "skills": ["Python", "FastAPI", "AWS", "Kubernetes"],
                "experience_years": 3,
                "current_role": "Backend Developer",
                "current_company": "MidCorp",
                "source": Applicant.Source.MANUAL,
            },
            {
                "first_name": "Eva",
                "last_name": "Martinez",
                "email": "eva.martinez@example.com",
                "phone": "+14155550005",
                "skills": ["React", "Vue.js", "JavaScript", "Figma"],
                "experience_years": 2,
                "current_role": "Junior Frontend Developer",
                "current_company": "AgencyABC",
                "source": Applicant.Source.WEBSITE,
            },
        ]

        applicants = []
        for data in applicants_data:
            applicant, created = Applicant.objects.get_or_create(
                tenant_id=tenant_id,
                email=data["email"],
                defaults={**data, "owner_user_id": owner_user_id},
            )
            applicants.append(applicant)
            if created:
                self.stdout.write(f"  Created applicant: {applicant.full_name}")
        return applicants

    def _seed_applications(self, tenant_id: str, owner_user_id: str, jobs: list, applicants: list) -> list:
        from applications.models import Application

        app_pairs = [
            (jobs[0], applicants[0], Application.Status.SHORTLISTED, Decimal("82.5")),
            (jobs[0], applicants[3], Application.Status.AI_COMPLETED, Decimal("74.0")),
            (jobs[1], applicants[1], Application.Status.INTERVIEW_SCHEDULED, None),
            (jobs[1], applicants[4], Application.Status.APPLIED, None),
            (jobs[2], applicants[2], Application.Status.OFFER, Decimal("91.0")),
            (jobs[0], applicants[2], Application.Status.REJECTED, Decimal("55.0")),
            (jobs[2], applicants[0], Application.Status.AI_SCREENING, None),
            (jobs[1], applicants[3], Application.Status.APPLIED, None),
        ]

        applications = []
        for job, applicant, status, score in app_pairs:
            app, created = Application.objects.get_or_create(
                tenant_id=tenant_id,
                job=job,
                applicant=applicant,
                defaults={
                    "status": status,
                    "score": score,
                    "owner_user_id": owner_user_id,
                },
            )
            applications.append(app)
            if created:
                self.stdout.write(f"  Created application: {applicant.full_name} → {job.title} [{status}]")

        # Update job application counts
        for job in jobs:
            count = Application.objects.filter(tenant_id=tenant_id, job=job).count()
            job.application_count = count
            job.save(update_fields=["application_count"])

        return applications

    def _seed_call_records(self, tenant_id: str, owner_user_id: str, applications: list) -> None:
        from calls.models import CallRecord, Scorecard

        # Find completed applications to attach calls to
        completed_apps = [a for a in applications if a.status in ["AI_COMPLETED", "SHORTLISTED", "OFFER", "REJECTED"]][:2]

        for i, app in enumerate(completed_apps):
            call, created = CallRecord.objects.get_or_create(
                tenant_id=tenant_id,
                application=app,
                defaults={
                    "provider": CallRecord.Provider.OMNIDIM,
                    "voice_agent_id": "agent_demo_001",
                    "provider_call_id": f"demo_call_{i+1:03d}",
                    "phone": app.applicant.phone,
                    "status": CallRecord.Status.COMPLETED,
                    "duration": 480 + i * 120,
                    "transcript": f"Interviewer: Hello, can you tell me about your experience?\n"
                                  f"Candidate: Sure! I have {app.applicant.experience_years} years of experience in {', '.join(app.applicant.skills[:2])}.\n"
                                  f"Interviewer: Great. What's your biggest achievement?\n"
                                  f"Candidate: I led a team that reduced deployment time by 60%.\n"
                                  f"Interviewer: Thank you! We'll be in touch.\n",
                    "summary": f"Strong candidate with solid {', '.join(app.applicant.skills[:2])} experience. "
                               f"Communicates well, technically sound.",
                    "owner_user_id": owner_user_id,
                },
            )
            if created:
                self.stdout.write(f"  Created call record for {app.applicant.full_name}")

                # Create scorecard
                sc, sc_created = Scorecard.objects.get_or_create(
                    tenant_id=tenant_id,
                    application=app,
                    call_record=call,
                    defaults={
                        "communication_score": Decimal("82.00"),
                        "knowledge_score": Decimal("78.00"),
                        "confidence_score": Decimal("85.00"),
                        "relevance_score": Decimal("80.00"),
                        "overall_score": app.score or Decimal("75.00"),
                        "summary": "Good candidate overall. Strong technical background.",
                        "strengths": ["Clear communication", "Strong technical skills"],
                        "weaknesses": ["Could improve on system design"],
                        "recommendation": Scorecard.Recommendation.YES,
                        "owner_user_id": owner_user_id,
                    },
                )
                if sc_created:
                    self.stdout.write(f"  Created scorecard for {app.applicant.full_name}")

    def _seed_interviews(self, tenant_id: str, owner_user_id: str, applications: list) -> None:
        from interviews.models import Interview

        interview_apps = [a for a in applications if a.status == "INTERVIEW_SCHEDULED"][:1]
        for app in interview_apps:
            interview, created = Interview.objects.get_or_create(
                tenant_id=tenant_id,
                application=app,
                defaults={
                    "interview_type": Interview.InterviewType.TECHNICAL,
                    "scheduled_at": timezone.now() + timezone.timedelta(days=3),
                    "duration_minutes": 60,
                    "interviewer_name": "Sarah Tech Lead",
                    "interviewer_email": "sarah@example.com",
                    "status": Interview.Status.SCHEDULED,
                    "meeting_link": "https://meet.google.com/demo-link",
                    "owner_user_id": owner_user_id,
                },
            )
            if created:
                self.stdout.write(f"  Created interview for {app.applicant.full_name}")
