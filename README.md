Commands to run locally after cloning / pulling:
bash# 1. Create virtual environment
cd smarthrin
python -m venv venv

# Windows activation:
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file and fill in values
copy .env.example .env
# Edit .env with your Neon DB URL, JWT_SECRET_KEY, Redis URL, etc.

# 4. Run migrations
python manage.py migrate

# 5. Seed default data (replace with your actual tenant UUID)
python manage.py seed_data --tenant-id=59b24488-ad8e-4540-94b7-3237e8afc360

# 6. Start the server
python manage.py runserver 0.0.0.0:8000

# 7. (Separate terminal) Start Celery worker
celery -A config worker --loglevel=info --pool=solo

# 8. (Optional) Start Celery beat for periodic tasks
celery -A config beat --loglevel=info
Models created by migration:
TableAppKey Fieldsjobsjobstitle, department, status, voice_agent_idapplicantsapplicantsfirst_name, last_name, email, phone, skillsapplicationsapplicationsjob_id, applicant_id, status, scorecall_recordscallsapplication_id, provider_call_id, transcript, durationscorecardscallsapplication_id, communication/knowledge/confidence/overall scoresinterviewsinterviewsapplication_id, interview_type, scheduled_at, meeting_linkpipeline_stagespipelinename, slug, order, is_terminalnotificationsnotificationsrecipient_user_id, title, message, is_read
All tables have: id (UUID), tenant_id (UUID), owner_user_id (UUID), created_at, updated_at.