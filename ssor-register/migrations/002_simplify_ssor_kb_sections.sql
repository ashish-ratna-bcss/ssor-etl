-- =============================================================================
-- Real ACTS_SECTIONS data from the CCTNS API (sampled 2022-2026, ~132k crimes)
-- shows sub-clauses always as trailing parens on a bare leading section
-- number -- e.g. "64(2)(m) BNS", "65(1)", "5(l) POCSO ACT 2012" -- and none
-- of the sub-clauses in our scope change the tier (65(1) and 65(2) are both
-- RED; 70 and 70(2) are both RED). So the matcher normalizes incoming codes
-- down to the bare leading number, and ssor_kb only needs to store that.
-- =============================================================================

BEGIN;

DELETE FROM public.ssor_kb WHERE section_code IN ('65(1)', '65(2)', '70(2)');

INSERT INTO public.ssor_kb (act_name, section_code, tier, severity_rank, description) VALUES
    ('BNS', '65', 'RED', 100, 'Rape of a girl under 16/12 (sub-clauses (1)/(2))')
ON CONFLICT (act_name, section_code) DO NOTHING;

-- '70' already covers gang rape; 70(2) (victim under 18) folds into it, same tier.

COMMIT;
