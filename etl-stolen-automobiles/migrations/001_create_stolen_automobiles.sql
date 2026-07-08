-- =============================================================================
-- etl-stolen-automobiles: schema for GET /reports/stolen-automobiles(+{crimeId})
-- Column names/types follow the live conventions in DB-schema.sql
-- (crime_id character varying(50), FK to public.crimes).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.stolen_automobiles (
    stolen_property_id character varying(50) PRIMARY KEY,
    crime_id character varying(50) NOT NULL,
    auto_seq_no TEXT,
    auto_type TEXT,
    belongs_to_whom TEXT,
    chassis_no TEXT,
    classification TEXT,
    color TEXT,
    color_type TEXT,
    date_created TIMESTAMP,
    date_modified TIMESTAMP,
    date_of_seizure TIMESTAMP,
    district TEXT,
    driver_side TEXT,
    engine_capacity TEXT,
    engine_no TEXT,
    estimate_value NUMERIC,
    fuel TEXT,
    full_chassis_no TEXT,
    full_engine_no TEXT,
    insurance_certificate_no TEXT,
    insurance_company_name TEXT,
    license_class TEXT,
    lifting_capacity NUMERIC,
    location_type TEXT,
    made TEXT,
    make TEXT,
    manufactured TEXT,
    manufacturer TEXT,
    mfg_month TEXT,
    mfg_year TEXT,
    model TEXT,
    mv_utility TEXT,
    nature_of_stolen TEXT,
    over_all_length NUMERIC,
    owner_father_name TEXT,
    owner_name TEXT,
    particular_of_property TEXT,
    permanent_address TEXT,
    place_of_recovery TEXT,
    present_address TEXT,
    property_category TEXT,
    property_category_name TEXT,
    property_recovered_from TEXT,
    property_status TEXT,
    recovered_value NUMERIC,
    registered_at TEXT,
    registered_mobile_no TEXT,
    registered_owner TEXT,
    registration_date TIMESTAMP,
    registration_no TEXT,
    registration_number TEXT,
    registration_place TEXT,
    registration_valid_upto TIMESTAMP,
    remarks TEXT,
    rta_name TEXT,
    rta_verification_date TIMESTAMP,
    seat_capacity NUMERIC,
    seq_no TEXT,
    slogan_picture TEXT,
    special_identification TEXT,
    sub_classification TEXT,
    tmp_registration_no TEXT,
    total_estimated_value NUMERIC,
    ulw NUMERIC,
    variant TEXT,
    wheel_base NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_stolen_automobiles_crime_id ON public.stolen_automobiles (crime_id);
CREATE INDEX IF NOT EXISTS idx_stolen_automobiles_date_modified ON public.stolen_automobiles (date_modified);

-- MEDIA[] (1:M, array of string references -- API returns bare strings, not {FILE_ID} objects)
CREATE TABLE IF NOT EXISTS public.stolen_automobile_media (
    id BIGSERIAL PRIMARY KEY,
    stolen_property_id character varying(50) NOT NULL,
    media_ref TEXT,
    CONSTRAINT fk_stolen_automobile_media_parent
        FOREIGN KEY (stolen_property_id) REFERENCES public.stolen_automobiles(stolen_property_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stolen_automobile_media_parent ON public.stolen_automobile_media (stolen_property_id);

ALTER TABLE public.stolen_automobiles
    ADD CONSTRAINT fk_stolen_automobiles_crime FOREIGN KEY (crime_id) REFERENCES public.crimes(crime_id);

COMMIT;
