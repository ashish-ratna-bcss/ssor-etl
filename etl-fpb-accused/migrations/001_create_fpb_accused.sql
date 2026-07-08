-- =============================================================================
-- etl-fpb-accused: schema for GET /fpb/accused (Finger Print Bureau lookup by
-- firNum+psCode, not a date-range endpoint -- driven by iterating (fir_num,
-- ps_code) pairs already present in public.crimes).
--
-- POST /fpb/accused/pcn shares the identical response shape but is a POST
-- (write/trigger semantics on the source system) -- intentionally NOT synced
-- by this ETL. See etl_fpb_accused.py module docstring.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.fpb_accused (
    fpb_accused_id BIGSERIAL PRIMARY KEY,
    crime_id character varying(50),
    person_id character varying(50),
    fir_num character varying(50) NOT NULL,
    ps_code character varying(20) NOT NULL,
    age TEXT,
    alias TEXT,
    caste TEXT,
    cc_kd_dc_no TEXT,
    confession_statement TEXT,
    date_fingerprinted TIMESTAMP,
    date_of_arrest TIMESTAMP,
    dob DATE,
    father_husband_name TEXT,
    fir_reg_num TEXT,
    fp_unit TEXT,
    full_name TEXT,
    mo TEXT,
    nationality TEXT,
    occupation TEXT,
    phone_number TEXT,
    place_of_birth TEXT,
    property_recovered TEXT,
    ps_where_fps_obtained TEXT,
    religion TEXT,
    remarks TEXT,
    sex TEXT,
    slip_type TEXT,
    surname TEXT,
    -- AADHAAR_OR_OTHER_ID
    aadhaar_or_other_id_number TEXT,
    aadhaar_or_other_id_type TEXT,
    -- ARREST_DETAILS
    arrest_details_crime_no TEXT,
    arrest_details_crime_year TEXT,
    arrest_details_district TEXT,
    arrest_details_ps_name TEXT,
    arrest_details_section_of_law TEXT,
    arrest_details_state_of_arrest TEXT,
    -- PERMANENT_ADDRESS
    permanent_address_address TEXT,
    permanent_address_district TEXT,
    permanent_address_state_ut TEXT,
    -- PRESENT_ADDRESS
    present_address_address TEXT,
    present_address_district TEXT,
    present_address_state_ut TEXT,
    -- PHYSICAL_FEATURES
    pf_beard TEXT,
    pf_chin TEXT,
    pf_complexion_of_face TEXT,
    pf_ear TEXT,
    pf_eyebrows TEXT,
    pf_forehead TEXT,
    pf_hair TEXT,
    pf_hair_color TEXT,
    pf_height TEXT,
    pf_jaws TEXT,
    pf_lips TEXT,
    pf_moustaches TEXT,
    pf_mouth TEXT,
    pf_neck TEXT,
    pf_nose TEXT,
    pf_shape_of_face TEXT,
    pf_weight TEXT,
    date_fetched TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT uq_fpb_accused_fir_ps_name UNIQUE (fir_num, ps_code, full_name)
);

CREATE INDEX IF NOT EXISTS idx_fpb_accused_crime_id ON public.fpb_accused (crime_id);
CREATE INDEX IF NOT EXISTS idx_fpb_accused_fir_ps ON public.fpb_accused (fir_num, ps_code);

-- ADDITIONAL_CRIMES[] (1:M)
CREATE TABLE IF NOT EXISTS public.fpb_additional_crimes (
    id BIGSERIAL PRIMARY KEY,
    fpb_accused_id BIGINT NOT NULL,
    crime_no TEXT,
    district TEXT,
    police_station TEXT,
    section_of_law TEXT,
    state TEXT,
    year TEXT,
    CONSTRAINT fk_fpb_additional_crimes_parent
        FOREIGN KEY (fpb_accused_id) REFERENCES public.fpb_accused(fpb_accused_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fpb_additional_crimes_parent ON public.fpb_additional_crimes (fpb_accused_id);

ALTER TABLE public.fpb_accused
    ADD CONSTRAINT fk_fpb_accused_crime FOREIGN KEY (crime_id) REFERENCES public.crimes(crime_id);

COMMIT;
