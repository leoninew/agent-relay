ALTER TABLE deliveries ADD COLUMN submission_method TEXT
    CHECK(submission_method IS NULL OR submission_method IN ('queue', 'steer'))
    CHECK(submission_method IS NOT 'steer' OR (
        queued_submission_id IS NULL AND receipt_metadata IS NULL
        AND queued_at IS NULL AND activation_attempted_at IS NULL
    ));

ALTER TABLE deliveries ADD COLUMN steered_turn_id TEXT
    CHECK(steered_turn_id IS NULL OR (
        submission_method IS 'steer' AND length(trim(steered_turn_id)) > 0
    ))
    CHECK(submission_method IS NOT 'steer' OR status <> 'queued'
        OR steered_turn_id IS NOT NULL)
    CHECK(submission_method IS NOT 'steer' OR status <> 'received' OR (
        received_at IS NOT NULL AND received_item_id IS NOT NULL AND received_turn_id IS NOT NULL
    ));

UPDATE deliveries SET submission_method = 'queue' WHERE status <> 'pending';
