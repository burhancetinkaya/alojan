-- AGP-03/06: the management deployment assigns publications to its trusted voice node.
-- Existing publications retain explicit operator targets until assigned by publication.
ALTER TABLE agent_publications ADD COLUMN node_id text
    CHECK (node_id ~ '^[a-z0-9][a-z0-9-]{0,63}$');
CREATE INDEX publication_node ON agent_publications(node_id,scope_id,release_id)
    WHERE node_id IS NOT NULL;
