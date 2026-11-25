-- Synthetic development data. Safe to run repeatedly.
BEGIN;
INSERT INTO sources VALUES
 ('source_a','http://mock-sources:4000/a','Synthetic SME platform'),
 ('source_b','http://mock-sources:4000/b','Synthetic freelancer export') ON CONFLICT DO NOTHING;
INSERT INTO source_records (id,source,source_id,raw,hash,resolved_hash,original_url) VALUES
 ('a0000000-0000-4000-8000-000000000001','source_a','a-1','{}','h1','h1','https://example.org/a/1'),
 ('a0000000-0000-4000-8000-000000000002','source_a','a-2','{}','h2','h2','https://example.org/a/2'),
 ('a0000000-0000-4000-8000-000000000003','source_b','b-1','{}','h3','h3','https://example.org/b/1'),
 ('a0000000-0000-4000-8000-000000000004','source_b','b-2','{}','h4','h4','https://example.org/b/2') ON CONFLICT DO NOTHING;
INSERT INTO profiles (id,type,name,description,sector,region,skills,services,needs,languages) VALUES
 ('b0000000-0000-4000-8000-000000000001','sme','Αρτοποιείο Παράδειγμα','Παραδοσιακό ψωμί και γλυκά','food','Attica','{baking}','{"φρέσκο ψωμί"}','{"web development"}','{el}'),
 ('b0000000-0000-4000-8000-000000000002','young_entrepreneur','AgroSense Demo','Αισθητήρες για έξυπνη γεωργία','agritech','Thessaly','{IoT,backend}','{"field monitoring"}','{"UX design"}','{el,en}'),
 ('b0000000-0000-4000-8000-000000000003','freelancer','Demo Web Studio','Σχεδιασμός ιστοσελίδων','software','Attica','{"web development",React}','{websites}','{}','{el,en}'),
 ('b0000000-0000-4000-8000-000000000004','freelancer','Demo UX Designer','User research and interface design','software','Crete','{"UX design"}','{prototypes}','{"web development"}','{en}') ON CONFLICT DO NOTHING;
INSERT INTO profile_sources
 SELECT ('a0000000-0000-4000-8000-00000000000'||i)::uuid, ('b0000000-0000-4000-8000-00000000000'||i)::uuid, 'new', 1
 FROM generate_series(1,4) i ON CONFLICT DO NOTHING;
INSERT INTO ml_batches (id,data_version,status) VALUES
 ('c0000000-0000-4000-8000-000000000000',0,'succeeded') ON CONFLICT DO NOTHING;
INSERT INTO ml_runs (id,batch_id,kind,data_version,status) VALUES
 ('d0000000-0000-4000-8000-000000000001','c0000000-0000-4000-8000-000000000000','similarity',0,'succeeded'),
 ('d0000000-0000-4000-8000-000000000002','c0000000-0000-4000-8000-000000000000','matching',0,'succeeded'),
 ('d0000000-0000-4000-8000-000000000003','c0000000-0000-4000-8000-000000000000','clustering',0,'succeeded') ON CONFLICT DO NOTHING;
INSERT INTO ml_current
 SELECT kind, id FROM ml_runs WHERE batch_id='c0000000-0000-4000-8000-000000000000' ON CONFLICT DO NOTHING;
INSERT INTO similar_profiles VALUES
 ('d0000000-0000-4000-8000-000000000001','b0000000-0000-4000-8000-000000000003','b0000000-0000-4000-8000-000000000004',1,0.71),
 ('d0000000-0000-4000-8000-000000000001','b0000000-0000-4000-8000-000000000004','b0000000-0000-4000-8000-000000000003',1,0.71) ON CONFLICT DO NOTHING;
INSERT INTO potential_partners VALUES
 ('d0000000-0000-4000-8000-000000000002','b0000000-0000-4000-8000-000000000001','b0000000-0000-4000-8000-000000000003',1,0.93,'{"matched_needs":["web development"]}'),
 ('d0000000-0000-4000-8000-000000000002','b0000000-0000-4000-8000-000000000002','b0000000-0000-4000-8000-000000000004',1,0.90,'{"matched_needs":["UX design"]}') ON CONFLICT DO NOTHING;
INSERT INTO cluster_assignments
 SELECT 'd0000000-0000-4000-8000-000000000003', id,
        CASE sector WHEN 'software' THEN 0 WHEN 'food' THEN 1 ELSE 2 END, sector
 FROM profiles WHERE id::text LIKE 'b0000000-0000-4000-8000-%' ON CONFLICT DO NOTHING;
COMMIT;
