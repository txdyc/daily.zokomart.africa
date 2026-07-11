from app.scheduler import build_scheduler


def test_build_scheduler_registers_all_jobs():
    sched = build_scheduler()
    jobs = {j.id: j for j in sched.get_jobs()}
    assert set(jobs) == {
        "crawl-tier-1",
        "crawl-tier-2",
        "crawl-tier-3",
        "translation-sweep",
        "lg-daily",
    }
    for job in jobs.values():
        assert job.max_instances == 1
        assert job.coalesce is True
