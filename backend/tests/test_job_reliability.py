"""Background-job reliability: a job must never be permanently stuck in
queued/processing, and a failed job must be retryable. Covers the startup
stale-job sweep and the POST /api/lectures/{id}/retry endpoint added to
satisfy that requirement.
"""
import time


def _create_lecture(client, auth_headers, course_id, title="Reliability test lecture"):
    res = client.post("/api/lectures", headers=auth_headers, json={
        "course_id": course_id,
        "title": title,
        "transcript_text": "A short lecture about Queues and Stacks for reliability testing.",
    })
    assert res.status_code in (200, 201)
    return res.json()


def test_sweep_stale_jobs_marks_orphaned_jobs_failed(client, auth_headers, seed_course, db):
    from app.models import ProcessingJob, Lecture
    from app.tasks.processing import sweep_stale_jobs, STALE_JOB_MESSAGE

    cid = seed_course["id"]
    # Insert the lecture/job rows directly rather than via POST /api/lectures:
    # TestClient runs FastAPI BackgroundTasks inline, so going through the API
    # would let the real processing job finish before this test can simulate
    # an abandoned "processing" row left by a killed worker process.
    lecture = Lecture(course_id=cid, title="Reliability test lecture", status="pending")
    db.add(lecture)
    db.flush()
    job = ProcessingJob(lecture_id=lecture.id, job_type="full_processing", status="processing", progress=40)
    db.add(job)
    db.commit()

    swept = sweep_stale_jobs()
    assert swept >= 1

    db.expire_all()
    refreshed = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
    assert refreshed.status == "failed"
    assert refreshed.error_message == STALE_JOB_MESSAGE

    lec = db.query(Lecture).filter(Lecture.id == lecture.id).first()
    assert lec.status == "error"


def test_sweep_stale_jobs_leaves_completed_jobs_alone(client, auth_headers, seed_course, db):
    from app.models import ProcessingJob
    from app.tasks.processing import process_lecture_job, sweep_stale_jobs

    cid = seed_course["id"]
    lecture = _create_lecture(client, auth_headers, cid)
    job = db.query(ProcessingJob).filter(ProcessingJob.lecture_id == lecture["id"]).first()
    process_lecture_job(job.id)

    db.expire_all()
    before = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
    assert before.status == "completed"

    sweep_stale_jobs()

    db.expire_all()
    after = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
    assert after.status == "completed"


def test_retry_requeues_a_failed_job_and_it_can_complete(client, auth_headers, seed_course, db):
    from app.models import ProcessingJob
    from app.tasks.processing import process_lecture_job

    cid = seed_course["id"]
    lecture = _create_lecture(client, auth_headers, cid)
    job = db.query(ProcessingJob).filter(ProcessingJob.lecture_id == lecture["id"]).first()
    job.status = "failed"
    job.error_message = "Document processing failed. Please retry."
    db.commit()

    res = client.post(f"/api/lectures/{lecture['id']}/retry", headers=auth_headers)
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "queued"
    new_job_id = body["id"]
    assert new_job_id != job.id

    # BackgroundTasks doesn't run under TestClient the same way it does under
    # uvicorn, so drive it directly the same way the rest of this suite does.
    process_lecture_job(new_job_id)

    status = client.get(f"/api/lectures/{lecture['id']}/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "completed", status.json().get("error_message")


def test_retry_rejected_while_job_already_in_progress(client, auth_headers, seed_course, db):
    from app.models import ProcessingJob

    cid = seed_course["id"]
    lecture = _create_lecture(client, auth_headers, cid)
    job = db.query(ProcessingJob).filter(ProcessingJob.lecture_id == lecture["id"]).first()
    job.status = "processing"
    db.commit()

    res = client.post(f"/api/lectures/{lecture['id']}/retry", headers=auth_headers)
    assert res.status_code == 409


def test_retry_rejected_for_demo_user(client, demo_headers, db):
    from app.models import Course, Lecture, ProcessingJob

    course = db.query(Course).filter(Course.user_id == 0).first()
    if not course:
        import pytest
        pytest.skip("No demo course seeded in this test DB")
    lecture = db.query(Lecture).filter(Lecture.course_id == course.id).first()
    if not lecture:
        import pytest
        pytest.skip("No demo lecture seeded in this test DB")

    res = client.post(f"/api/lectures/{lecture.id}/retry", headers=demo_headers)
    assert res.status_code == 403


def test_retry_requires_ownership(client, auth_headers, auth_headers_u2, seed_course, db):
    from app.models import ProcessingJob

    cid = seed_course["id"]
    lecture = _create_lecture(client, auth_headers, cid)
    job = db.query(ProcessingJob).filter(ProcessingJob.lecture_id == lecture["id"]).first()
    job.status = "failed"
    db.commit()

    res = client.post(f"/api/lectures/{lecture['id']}/retry", headers=auth_headers_u2)
    assert res.status_code == 403
