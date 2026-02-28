FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY trello_journal_migration/ trello_journal_migration/

# Output directory for the generated JSON
VOLUME /app/output

ENTRYPOINT ["python", "-m", "trello_journal_migration"]
