-- TTS-01: permit only the qualified bundled Pocket voices; keep old revisions intact.
ALTER TABLE assistant_profile_revisions
    DROP CONSTRAINT assistant_profile_revisions_voice_ref_check;
ALTER TABLE assistant_profile_revisions
    ADD CONSTRAINT assistant_profile_revisions_voice_ref_check CHECK (voice_ref IN (
        'ema-default', 'pocket-female_1', 'pocket-female_2', 'pocket-female_3',
        'pocket-male_1', 'pocket-male_2', 'pocket-male_3'
    ));
