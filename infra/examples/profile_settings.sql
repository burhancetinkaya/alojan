-- PostgreSQL, not SQL Server T-SQL. Apply migrations first.
-- Optional, repeatable demonstration data: no routes, credentials or sends.
BEGIN;
INSERT INTO recipient_scopes (id, display_name) VALUES
    ('10000000-0000-4000-8000-000000000001', 'Burhan'),
    ('10000000-0000-4000-8000-000000000002', 'Serkan')
ON CONFLICT (id) DO NOTHING;
INSERT INTO assistant_profiles (id, scope_id, label) VALUES
    ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'Kübra'),
    ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', 'Berkcan')
ON CONFLICT (id) DO NOTHING;
INSERT INTO assistant_profile_revisions (
    scope_id, profile_id, revision, owner_display_name, agent_name,
    owner_address, owner_dative, owner_genitive, role_description, tone_description,
    greeting_template, availability_text
) VALUES
    ('10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 1,
     'Burhan', 'Kübra', 'Burhan Bey', 'Burhan Bey''e', 'Burhan Bey''in',
     'Executive assistant who collects messages and callback requests.',
     'Warm, composed, respectful and concise; use everyday Turkish.',
     'Merhaba, ben {agent_name}. {owner_genitive} yapay zekâ asistanıyım. Size nasıl yardımcı olabilirim?',
     'Burhan Bey şu anda müsait değil, bir toplantıda olabilir.'),
    ('10000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', 1,
     'Serkan', 'Berkcan', 'Serkan Bey', 'Serkan Bey''e', 'Serkan Bey''in',
     'Executive assistant who collects messages and callback requests.',
     'Warm, composed, respectful and concise; use everyday Turkish.',
     'Merhaba, ben {agent_name}. {owner_genitive} yapay zekâ asistanıyım. Size nasıl yardımcı olabilirim?',
     'Serkan Bey için mesajınızı alabilirim.')
ON CONFLICT (profile_id, revision) DO NOTHING;
COMMIT;

-- Read profiles without treating a name as an identifier.
SELECT p.id, r.revision, r.owner_display_name, r.agent_name, p.enabled
FROM assistant_profiles p JOIN assistant_profile_revisions r ON r.profile_id = p.id
ORDER BY p.id, r.revision;
SELECT llm_model, llm_provider, max_call_seconds, answer_delay_ms FROM system_settings WHERE id = 1;

-- Example administrative edit (intentionally not executed):
-- UPDATE system_settings SET max_call_seconds = 180,
--     revision = revision + 1, updated_at = now() WHERE id = 1 AND revision = 1;
-- Check exactly one affected row; otherwise reload and resolve the stale edit.
-- A profile rename must INSERT a new revision, never UPDATE an old revision.
