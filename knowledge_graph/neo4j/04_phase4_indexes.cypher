// Phase 4 — Constraints and indexes for new node types

CREATE CONSTRAINT taxpayerprofile_profile_type_unique IF NOT EXISTS
FOR (n:TaxpayerProfile) REQUIRE n.profile_type IS UNIQUE;

CREATE CONSTRAINT concept_concept_id_unique IF NOT EXISTS
FOR (n:Concept) REQUIRE n.concept_id IS UNIQUE;

CREATE CONSTRAINT relief_relief_id_unique IF NOT EXISTS
FOR (n:Relief) REQUIRE n.relief_id IS UNIQUE;

CREATE CONSTRAINT rateband_rate_band_id_unique IF NOT EXISTS
FOR (n:RateBand) REQUIRE n.rate_band_id IS UNIQUE;

CREATE CONSTRAINT proceduremilestone_milestone_id_unique IF NOT EXISTS
FOR (n:ProcedureMilestone) REQUIRE n.milestone_id IS UNIQUE;

CREATE CONSTRAINT irdhubsummary_summary_id_unique IF NOT EXISTS
FOR (n:IrdHubSummary) REQUIRE n.summary_id IS UNIQUE;

CREATE INDEX concept_canonical_name IF NOT EXISTS
FOR (n:Concept) ON (n.canonical_name);

CREATE INDEX relief_display_name IF NOT EXISTS
FOR (n:Relief) ON (n.display_name);

CREATE INDEX rateband_band_type IF NOT EXISTS
FOR (n:RateBand) ON (n.band_type);

CREATE INDEX rateband_effective_start IF NOT EXISTS
FOR (n:RateBand) ON (n.effective_start_date);

CREATE INDEX proceduremilestone_kind IF NOT EXISTS
FOR (n:ProcedureMilestone) ON (n.milestone_kind);

CREATE INDEX taxpayerprofile_display_name IF NOT EXISTS
FOR (n:TaxpayerProfile) ON (n.display_name);
