-- STAGING ONLY: do not execute in production until the runtime role, migration

-- and synthetic cross-tenant API acceptance checks are reviewed. No FORCE RLS:

-- neondb_owner/BYPASSRLS remains a deliberate admin/background-worker boundary.

CREATE ROLE aqlyra_tenant_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

GRANT aqlyra_tenant_runtime TO CURRENT_USER;

GRANT USAGE ON SCHEMA public TO aqlyra_tenant_runtime;

GRANT SELECT, UPDATE ON TABLE public.users TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.users FOR ALL TO aqlyra_tenant_runtime USING (id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.documents TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.documents FOR ALL TO aqlyra_tenant_runtime USING (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.conversations TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.conversations FOR ALL TO aqlyra_tenant_runtime USING (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.projects TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.projects FOR ALL TO aqlyra_tenant_runtime USING (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.memories TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.memories FOR ALL TO aqlyra_tenant_runtime USING (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.cloud_upload_intents TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.cloud_upload_intents FOR ALL TO aqlyra_tenant_runtime USING (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.cloud_upload_intents ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.study_cases TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.study_cases FOR ALL TO aqlyra_tenant_runtime USING (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) WITH CHECK (user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''));

ALTER TABLE public.study_cases ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.document_units TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.document_units FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.document_units ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.document_chunks TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.document_chunks FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.embedding_records TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.embedding_records FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.document_chunks c JOIN public.documents d ON d.id = c.document_id WHERE c.id = chunk_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.document_chunks c JOIN public.documents d ON d.id = c.document_id WHERE c.id = chunk_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.embedding_records ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.memory_embeddings TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.memory_embeddings FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.memories m WHERE m.id = memory_id AND m.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.memories m WHERE m.id = memory_id AND m.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.memory_embeddings ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.messages TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.messages FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.conversations c WHERE c.id = conversation_id AND c.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.conversations c WHERE c.id = conversation_id AND c.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.conversation_documents TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.conversation_documents FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.conversations c WHERE c.id = conversation_id AND c.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) AND EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.conversations c WHERE c.id = conversation_id AND c.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) AND EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.conversation_documents ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.message_attachments TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.message_attachments FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.messages m JOIN public.conversations c ON c.id = m.conversation_id WHERE m.id = message_id AND c.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) AND EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.messages m JOIN public.conversations c ON c.id = m.conversation_id WHERE m.id = message_id AND c.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) AND EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.message_attachments ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.study_case_documents TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.study_case_documents FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.study_cases s WHERE s.id = case_id AND s.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) AND EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.study_cases s WHERE s.id = case_id AND s.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')) AND EXISTS (SELECT 1 FROM public.documents d WHERE d.id = document_id AND d.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.study_case_documents ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.study_research_reports TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.study_research_reports FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.study_cases s WHERE s.id = case_id AND s.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.study_cases s WHERE s.id = case_id AND s.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.study_research_reports ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.study_universities TO aqlyra_tenant_runtime;

CREATE POLICY aqlyra_tenant_scope ON public.study_universities FOR ALL TO aqlyra_tenant_runtime USING (EXISTS (SELECT 1 FROM public.study_cases s WHERE s.id = case_id AND s.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), ''))) WITH CHECK (EXISTS (SELECT 1 FROM public.study_cases s WHERE s.id = case_id AND s.user_id = NULLIF(current_setting('aqlyra.tenant_user_id', true), '')));

ALTER TABLE public.study_universities ENABLE ROW LEVEL SECURITY;

-- No grants to PUBLIC, token tables (password_reset_codes/email_verification_codes), or migrations.
