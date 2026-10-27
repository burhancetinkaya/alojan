-- AGP-08: unanswered finalization is explicit, without invoking a summary model.
ALTER TABLE summary_jobs DROP CONSTRAINT summary_jobs_status_check;
ALTER TABLE summary_jobs ADD CONSTRAINT summary_jobs_status_check
    CHECK(status IN ('pending','processing','done','failed','not_requested'));
ALTER TABLE call_finalizations DROP CONSTRAINT call_finalizations_summary_status_check;
ALTER TABLE call_finalizations ADD CONSTRAINT call_finalizations_summary_status_check
    CHECK(summary_status IN ('done','failed','not_requested'));
