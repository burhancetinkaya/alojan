-- PostgreSQL 17: synthetic authoring fragment, not SQL Server T-SQL.
-- Read-only. Merge this into an owned draft through the authenticated API;
-- never insert releases, execution records or grants directly.
SELECT '{
  "outputs": [
    {"name":"products","type":"string_array","source":"conversation",
     "description":"Product names explicitly stated by the caller.","tool_alias":null,"path":null}
  ],
  "body_mapping_example": {
    "products":{"kind":"source","source":"outputs.products","on_missing":"null"},
    "products_status":{"kind":"source","source":"output_status.products","on_missing":"fail"}
  }
}'::jsonb AS authoring_example;
-- Move body_mapping_example into an HTTP action body; it is not a draft property.
-- The HTTP destination and exact owner grant remain separate. This sends nothing.
