-- =============================================================================
-- ssor_kb: section knowledge-base for the State Sexual Offender Register
-- (women's wing) concept note. Every row here is a section named in the
-- note's S5 classification table -- BNS 2023, POCSO 2012, IT Act 2000, ITPA
-- 1956. Nothing else is in scope for this register.
--
-- IPC-era sections (pre-2024-07-01, before BNS took effect) are deliberately
-- NOT included -- the note only classifies against BNS/POCSO/IT Act/ITPA.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.ssor_kb (
    id SERIAL PRIMARY KEY,
    act_name TEXT NOT NULL,       -- 'BNS' | 'POCSO' | 'IT_ACT' | 'ITPA'
    section_code TEXT NOT NULL,   -- normalized, e.g. '65(1)', '66E'
    tier TEXT NOT NULL,           -- 'RED' | 'ORANGE' | 'BLUE' | 'BLACK' | 'PINK'
    severity_rank INT NOT NULL,   -- higher = graver; picks highest tier per person
    description TEXT,
    CONSTRAINT uq_ssor_kb_section UNIQUE (act_name, section_code)
);

INSERT INTO public.ssor_kb (act_name, section_code, tier, severity_rank, description) VALUES
    -- RED -- dangerous predator / gang offender (concept note S5.1)
    ('BNS', '63', 'RED', 100, 'Rape - definition'),
    ('BNS', '64', 'RED', 100, 'Rape - punishment'),
    ('BNS', '65(1)', 'RED', 100, 'Rape of girl under 16'),
    ('BNS', '65(2)', 'RED', 100, 'Rape of girl under 12'),
    ('BNS', '66', 'RED', 100, 'Rape causing death or persistent vegetative state'),
    ('BNS', '70', 'RED', 100, 'Gang rape'),
    ('BNS', '70(2)', 'RED', 100, 'Gang rape - victim under 18'),
    ('POCSO', '5', 'RED', 100, 'Aggravated penetrative sexual assault'),
    ('POCSO', '6', 'RED', 100, 'Aggravated penetrative sexual assault - punishment'),

    -- ORANGE -- repeat / habitual offender (S5.2)
    ('BNS', '71', 'ORANGE', 80, 'Repeat/habitual sexual offender'),

    -- BLACK -- organised crime / trafficking (S5.4)
    ('BNS', '111', 'BLACK', 90, 'Organised crime'),
    ('BNS', '143', 'BLACK', 90, 'Trafficking of persons'),
    ('BNS', '144', 'BLACK', 90, 'Exploitation of a trafficked person'),
    ('ITPA', '3', 'BLACK', 90, 'Keeping a brothel'),
    ('ITPA', '4', 'BLACK', 90, 'Living on earnings of prostitution'),
    ('ITPA', '5', 'BLACK', 90, 'Procuring / inducing person for prostitution'),
    ('ITPA', '6', 'BLACK', 90, 'Detention of a person in premises where prostitution is carried on'),
    ('ITPA', '7', 'BLACK', 90, 'Prostitution in or near public places'),

    -- BLUE -- cyber sexual offender (S5.3)
    ('IT_ACT', '66E', 'BLUE', 60, 'Capturing/transmitting image of private area without consent'),
    ('IT_ACT', '67', 'BLUE', 60, 'Publishing obscene material in electronic form'),
    ('IT_ACT', '67A', 'BLUE', 60, 'Publishing sexually explicit material'),
    ('IT_ACT', '67B', 'BLUE', 60, 'Child sexual abuse material'),
    ('BNS', '77', 'BLUE', 60, 'Voyeurism'),
    ('POCSO', '11', 'BLUE', 60, 'Sexual harassment of a child'),
    ('POCSO', '12', 'BLUE', 60, 'Punishment for sexual harassment of a child'),
    ('POCSO', '13', 'BLUE', 60, 'Use of child for pornographic purposes'),
    ('POCSO', '14', 'BLUE', 60, 'Punishment for pornographic purposes involving a child'),

    -- PINK -- non-contact / harassment offender (S5.6)
    ('BNS', '74', 'PINK', 40, 'Assault/criminal force to woman with intent to outrage modesty'),
    ('BNS', '75', 'PINK', 40, 'Sexual harassment'),
    ('BNS', '76', 'PINK', 40, 'Assault with intent to disrobe'),
    ('BNS', '78', 'PINK', 40, 'Stalking'),
    ('BNS', '79', 'PINK', 40, 'Insult to modesty of a woman')
ON CONFLICT (act_name, section_code) DO NOTHING;

-- GREEN (S5.7, isolated first-time low-severity offender) is not seeded here:
-- it shares sections 74/75 with PINK and is only distinguished by the
-- offender having a single qualifying conviction -- that's a runtime
-- rollup rule, not a static section mapping. SILVER (juvenile) is likewise
-- not a section -- it's the accused.is_ccl flag overriding disclosability.

COMMIT;
