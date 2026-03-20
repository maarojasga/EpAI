"""
profiles.py — Target staging table schemas, column aliases, and fingerprints.

Each profile defines:
- target_table: the staging table name in the unified schema
- columns: list of target DB columns
- fingerprint: set of header keywords that identify this source type
- aliases: dict of known header synonyms (German → English DB column)
"""

# ---------------------------------------------------------------------------
# TARGET STAGING TABLE DEFINITIONS
# ---------------------------------------------------------------------------

STAGING_SCHEMAS = {
    "tbCaseData": {
        "columns": [
            "coId", "coE2I222", "coPatientId", "coE2I223", "coE2I228",
            "coLastname", "coFirstname", "coGender", "coDateOfBirth",
            "coAgeYears", "coTypeOfStay", "coIcd", "coDrgName",
            "coRecliningType", "coState",
        ],
        "fingerprint": {"lastname", "firstname", "gender", "dateofbirth", "typeofstay", "icd", "drg", "e2_i_222", "e2_i_228", "fallnr", "aufndat"},
    },
    "tbImportLabsData": {
        "columns": [
            "coId", "coCaseId", "coPatientId", "coSpecimen_datetime",
            "coSodium_mmol_L", "coSodium_flag", "cosodium_ref_low", "cosodium_ref_high",
            "coPotassium_mmol_L", "coPotassium_flag", "coPotassium_ref_low", "coPotassium_ref_high",
            "coCreatinine_mg_dL", "coCreatinine_flag", "coCreatinine_ref_low", "coCreatinine_ref_high",
            "coEgfr_mL_min_1_73m2", "coEgfr_flag", "coEgfr_ref_low", "coEgfr_ref_high",
            "coGlucose_mg_dL", "coGlucose_flag", "coGlucose_ref_low", "coGlucose_ref_high",
            "coHemoglobin_g_dL", "coHb_flag", "coHb_ref_low", "coHb_ref_high",
            "coWbc_10e9_L", "coWbc_flag", "coWbc_ref_low", "coWbc_ref_high",
            "coPlatelets_10e9_L", "coPlatelets_flag", "coPlt_ref_low", "coPlt_ref_high",
            "coCrp_mg_L", "coCrp_flag", "coCrp_ref_low", "coCrp_ref_high",
            "coAlt_U_L", "coAlt_flag", "coAlt_ref_low", "coAlt_ref_high",
            "coAst_U_L", "coAst_flag", "coAst_ref_low", "coAst_ref_high",
            "coBilirubin_mg_dL", "coBilirubin_flag", "coBili_ref_low", "coBili_ref_high",
            "coAlbumin_g_dL", "coAlbumin_flag", "coAlbumin_ref_low", "coAlbumin_ref_high",
            "coInr", "coInr_flag", "coInr_ref_low", "coInr_ref_high",
            "coLactate_mmol_L", "coLactate_flag", "coLactate_ref_low", "coLactate_ref_high",
        ],
        "fingerprint": {"sodium", "potassium", "creatinine", "hemoglobin", "specimen_datetime", "labs"},
    },
    "tbImportIcd10Data": {
        "columns": [
            "coId", "coCaseId", "coPatientId", "coWard", "coAdmission_date", "coDischarge_date",
            "coLength_of_stay_days", "coPrimary_icd10_code",
            "coPrimary_icd10_description_en", "coSecondary_icd10_codes",
            "coSecondary_icd10_descriptions_en", "coOps_codes", "coOps_descriptions_en",
        ],

        "fingerprint": {"icd10", "admission_date", "discharge_date", "ops_codes", "length_of_stay", "d_m", "d_s", "proc", "los", "date_ad"},
    },
    "tbImportDeviceMotionData": {
        "columns": [
            "coId", "coCaseId", "coTimestamp", "coPatientId",
            "coMovement_index_0_100", "coMicro_movements_count",
            "coBed_exit_detected_0_1", "coFall_event_0_1",
            "coImpact_magnitude_g", "coPost_fall_immobility_minutes",
        ],
        "fingerprint": {"movement_index", "micro_movements", "bed_exit_detected", "fall_event", "impact_magnitude"},
    },
    "tbImportDevice1HzMotionData": {
        "columns": [
            "coId", "coCaseId", "coTimestamp", "coPatientId", "coDevice_id",
            "coBed_occupied_0_1", "coMovement_score_0_100",
            "coAccel_x_m_s2", "coAccel_y_m_s2", "coAccel_z_m_s2", "coAccel_magnitude_g",
            "coPressure_zone1_0_100", "coPressure_zone2_0_100",
            "coPressure_zone3_0_100", "coPressure_zone4_0_100",
            "coBed_exit_event_0_1", "coBed_return_event_0_1",
            "coFall_event_0_1", "coImpact_magnitude_g", "coEvent_id",
        ],
        "fingerprint": {"device_id", "accel_x", "accel_y", "accel_z", "pressure_zone", "bed_occupied", "1hz"},
    },
    "tbImportMedicationInpatientData": {
        "columns": [
            "coId", "coCaseId", "coPatientId", "coRecord_type", "coEncounter_id",
            "coWard", "coAdmission_datetime", "coDischarge_datetime",
            "coOrder_id", "coOrder_uuid", "coMedication_code_atc", "coMedication_name",
            "coRoute", "coDose", "coDose_unit", "coFrequency",
            "coOrder_start_datetime", "coOrder_stop_datetime",
            "coIs_prn_0_1", "coIndication",
            "prescriber_role", "order_status",
            "administration_datetime", "administered_dose",
            "administered_unit", "administration_status", "note",
        ],
        "fingerprint": {"medication", "atc", "order_id", "route", "dose", "prn", "encounter_id", "prescriber"},
    },
    "tbImportNursingDailyReportsData": {
        "columns": [
            "coId", "coCaseId", "coPatientId", "coWard",
            "coReport_date", "coShift", "coNursing_note_free_text",
        ],
        "fingerprint": {"nursing", "report_date", "shift", "nursing_note", "free_text"},
    },
    "tbImportEpaAcData": {
        "columns": [
            "coId", "coCaseId", "coPatientId", "coClinicId", "coE0I001", "coE0I002", "coE0I003", "coE0I004", "coE0I005", "coE0I007", "coE0I008", "coE0I009", "coE0I010", "coE0I011", "coE0I012", "coE0I013", "coE0I014", "coE0I015", "coE0I021", "coE0I043", "coE0I070", "coE0I074", "coE0I075", "coE0I076", "coE0I077", "coE0I078", "coE0I079", "coE0I081", "coE0I082", "coE0I083", "coE0I0116", "coE0I0122", "coE0I0134", "coE0I0141", "coE0I0150", "coE0I0163", "coE0I0168", "coE0I0173", "coE0I0178", "coE0I0190", "coE0I0241", "coE0I0262", "coE0I0266", "coE0I0270", "coE0I0276", "coE0I0004", "coE0I0071", "coE0I0077", "coE0I0081", "coE2I001", "coE2I002", "coE2I003", "coE2I004", "coE2I005", "coE2I006", "coE2I007", "coE2I008", "coE2I009", "coE2I010", "coE2I011", "coE2I012", "coE2I013", "coE2I014", "coE2I015", "coE2I017", "coE2I018", "coE2I019", "coE2I020", "coE2I021", "coE2I022", "coE2I023", "coE2I024", "coE2I025", "coE2I026", "coE2I027", "coE2I028", "coE2I029", "coE2I030", "coE2I031", "coE2I032", "coE2I033", "coE2I034", "coE2I035", "coE2I036", "coE2I037", "coE2I038", "coE2I039", "coE2I040", "coE2I041", "coE2I042", "coE2I043", "coE2I044", "coE2I045", "coE2I046", "coE2I047", "coE2I048", "coE2I049", "coE2I050", "coE2I051", "coE2I052", "coE2I053", "coE2I054", "coE2I055", "coE2I056", "coE2I057", "coE2I058", "coE2I059", "coE2I060", "coE2I061", "coE2I062", "coE2I063", "coE2I064", "coE2I065", "coE2I066", "coE2I067", "coE2I068", "coE2I069", "coE2I070", "coE2I071", "coE2I072", "coE2I073", "coE2I074", "coE2I075", "coE2I076", "coE2I077", "coE2I078", "coE2I079", "coE2I080", "coE2I081", "coE2I082", "coE2I083", "coE2I084", "coE2I085", "coE2I086", "coE2I087", "coE2I088", "coE2I089", "coE2I090", "coE2I091", "coE2I092", "coE2I093", "coE2I095", "coE2I094", "coE2I096", "coE2I097", "coE2I098", "coE2I099", "coE2I100", "coE2I101", "coE2I102", "coE2I103", "coE2I104", "coE2I105", "coE2I106", "coE2I107", "coE2I108", "coE2I109", "coE2I110", "coE2I111", "coE2I112", "coE2I113", "coE2I114", "coE2I115", "coE2I116", "coE2I117", "coE2I118", "coE2I119", "coE2I121", "coE2I122", "coE2I123", "coE2I124", "coE2I125", "coE2I126", "coE2I127", "coE2I128", "coE2I129", "coE2I130", "coE2I131", "coE2I132", "coE2I133", "coE2I134", "coE2I135", "coE2I136", "coE2I137", "coE2I138", "coE2I139", "coE2I140", "coE2I141", "coE2I142", "coE2I143", "coE2I144", "coE2I145", "coE2I146", "coE2I147", "coE2I148", "coE2I150", "coE2I151", "coE2I152", "coE2I154", "coE2I155", "coE2I156", "coE2I157", "coE2I158", "coE2I159", "coE2I160", "coE2I161", "coE2I162", "coE2I163", "coE2I164", "coE2I165", "coE2I166", "coE2I167", "coE2I168", "coE2I169", "coE2I170", "coE2I171", "coE2I172", "coE2I173", "coE2I178", "coE2I179", "coE2I217", "coE2I218", "coE2I220", "coE2I221", "coE2I222", "coE2I223", "coE2I224", "coE2I225", "coE2I226", "coE2I227", "coE2I228", "coE2I229", "coE2I230", "coE2I231", "coE2I232", "coE2I2000", "coE2I2013", "coE2I2022", "coE2I2029", "coE2I2033", "coE2I2092", "coE2I2099", "coE2I2126", "coE2I2134", "coE2I2148", "coE2I2154", "coE2I2157", "coE2I2165", "coE2I2170", "coE2I2175", "coE2I2180", "coE2I2188", "coE2I2191", "coE2I2195", "coE2I2199", "coE2I2203", "coE2I2207", "coE2I2211", "coE2I2216", "coE2I2222", "coE2I2256", "coE2I2267", "coE2I2279", "coMaxDekuGrad", "coDekubitusWertTotal", "coLastAssessment", "coE3I0889", "coCaseIdAlpha",
        ],
        "fingerprint": {"epaac", "einschidfall", "fallnr", "einschdat", "e0_i_", "e2_i_"},
    },
}


# ---------------------------------------------------------------------------
# KNOWN ALIASES  (source header → target DB column)
# Covers: English CSV headers, German headers, common typos
# ---------------------------------------------------------------------------

COLUMN_ALIASES = {
    # --- Universal IDs ---
    "case_id":          "coCaseId",
    "caseid":           "coCaseId",
    "fallid":           "coCaseId",
    "fallnr":           "coCaseId",
    "fallnr (string)":  "coCaseId",
    "einschidfall":     "coCaseId",
    "e2_i_222":         "coCaseId",
    "einschdat":        "coAdmission_date",
    "e2_i_225":         "coAdmission_date",

    "patient_id":       "coPatientId",
    "patientid":        "coPatientId",
    "pid":              "coPatientId",
    "patientnr":        "coPatientId",
    "id_pat":           "coPatientId",
    "id_cas":           "coCaseId",

    # --- Demographics ---
    "sex":              "coGender",
    "gender":           "coGender",
    "geschlecht":       "coGender",
    "age_years":        "coAgeYears",
    "alter":            "coAgeYears",
    "date_of_birth":    "coDateOfBirth",
    "dateofbirth":      "coDateOfBirth",
    "patgeb":           "coDateOfBirth",
    "geburtsdatum":     "coDateOfBirth",
    "lastname":         "coLastname",
    "nachname":         "coLastname",
    "firstname":        "coFirstname",
    "vorname":          "coFirstname",

    # --- Dates / Times ---
    "timestamp":        "coTimestamp",
    "zeitstempel":      "coTimestamp",
    "aufnahme":         "coAdmission_date",
    "aufndat":          "coAdmission_date",
    "admission_date":   "coAdmission_date",
    "admission_datetime": "coAdmission_datetime",
    "entlassund":       "coDischarge_date",
    "entlassdat":       "coDischarge_date",
    "discharge_date":   "coDischarge_date",
    "discharge_datetime": "coDischarge_datetime",
    "date_ad":          "coAdmission_date",
    "date_dis":         "coDischarge_date",
    "specimen_datetime": "coSpecimen_datetime",
    "report_date":      "coReport_date",
    "order_start_datetime": "coOrder_start_datetime",
    "order_stop_datetime": "coOrder_stop_datetime",

    # --- Ward / Location ---
    "station":          "coWard",
    "abteilung":        "coWard",
    "ward":             "coWard",

    # --- Clinical ---
    "shift":            "coShift",
    "schicht":          "coShift",
    "nursing_note_free_text": "coNursing_note_free_text",
    "pflegebericht":    "coNursing_note_free_text",
    "record_type":      "coRecord_type",
    "encounter_id":     "coEncounter_id",
    "order_id":         "coOrder_id",
    "order_uuid":       "coOrder_uuid",
    "medication_name":  "coMedication_name",
    "medication_code_atc": "coMedication_code_atc",
    "route":            "coRoute",
    "dose":             "coDose",
    "dose_unit":        "coDose_unit",
    "frequency":        "coFrequency",
    "is_prn_0_1":       "coIs_prn_0_1",
    "indication":       "coIndication",
    "prescriber_role":  "prescriber_role",
    "order_status":     "order_status",
    "administration_datetime": "administration_datetime",
    "administered_dose": "administered_dose",
    "administered_unit": "administered_unit",
    "administration_status": "administration_status",
    "note":             "note",

    # --- Labs ---
    "sodium_mmol_l":    "coSodium_mmol_L",
    "sodium_flag":      "coSodium_flag",
    "sodium_ref_low":   "cosodium_ref_low",
    "sodium_ref_high":  "cosodium_ref_high",
    "na":               "coSodium_mmol_L",
    "na_flag":          "coSodium_flag",
    "na_low":           "coSodium_ref_low",
    "na_high":          "coSodium_ref_high",

    "potassium_mmol_l": "coPotassium_mmol_L",
    "potassium_flag":   "coPotassium_flag",
    "potassium_ref_low": "coPotassium_ref_low",
    "potassium_ref_high": "coPotassium_ref_high",
    "k":                "coPotassium_mmol_L",
    "k_flag":           "coPotassium_flag",
    "k_low":            "coPotassium_ref_low",
    "k_high":           "coPotassium_ref_high",

    "creatinine_mg_dl": "coCreatinine_mg_dL",
    "creatinine_flag":  "coCreatinine_flag",
    "creatinine_ref_low": "coCreatinine_ref_low",
    "creatinine_ref_high": "coCreatinine_ref_high",
    "creat":            "coCreatinine_mg_dL",
    "creat_flag":       "coCreatinine_flag",
    "creat_low":        "coCreatinine_ref_low",
    "creat_high":       "coCreatinine_ref_high",

    "egfr_ml_min_1_73m2": "coEgfr_mL_min_1_73m2",
    "egfr_flag":        "coEgfr_flag",
    "egfr_ref_low":     "coEgfr_ref_low",
    "egfr_ref_high":    "coEgfr_ref_high",
    "egfr":             "coEgfr_mL_min_1_73m2",

    "glucose_mg_dl":    "coGlucose_mg_dL",
    "glucose_flag":     "coGlucose_flag",
    "glucose_ref_low":  "coGlucose_ref_low",
    "glucose_ref_high": "coGlucose_ref_high",
    "gluc":             "coGlucose_mg_dL",
    "gluc_flag":        "coGlucose_flag",
    "gluc_low":         "coGlucose_ref_low",
    "gluc_high":        "coGlucose_ref_high",

    "hemoglobin_g_dl":  "coHemoglobin_g_dL",
    "hb_flag":          "coHb_flag",
    "hb_ref_low":       "coHb_ref_low",
    "hb_ref_high":      "coHb_ref_high",
    "hb":               "coHemoglobin_g_dL",
    "hb_low":           "coHb_ref_low",
    "hb_high":          "coHb_ref_high",

    "wbc_10e9_l":       "coWbc_10e9_L",
    "wbc_flag":         "coWbc_flag",
    "wbc_ref_low":      "coWbc_ref_low",
    "wbc_ref_high":     "coWbc_ref_high",
    "wbc":              "coWbc_10e9_L",
    "wbc_low":          "coWbc_ref_low",
    "wbc_high":         "coWbc_ref_high",

    "platelets_10e9_l": "coPlatelets_10e9_L",
    "platelets_flag":   "coPlatelets_flag",
    "plt_ref_low":      "coPlt_ref_low",
    "plt_ref_high":     "coPlt_ref_high",
    "plt":              "coPlatelets_10e9_L",
    "plt_low":          "coPlt_ref_low",
    "plt_high":         "coPlt_ref_high",

    "crp_mg_l":         "coCrp_mg_L",
    "crp_flag":         "coCrp_flag",
    "crp_ref_low":      "coCrp_ref_low",
    "crp_ref_high":     "coCrp_ref_high",
    "crp":              "coCrp_mg_L",
    "crp_low":          "coCrp_ref_low",
    "crp_high":         "coCrp_ref_high",

    "alt_u_l":          "coAlt_U_L",
    "alt_flag":         "coAlt_flag",
    "alt_ref_low":      "coAlt_ref_low",
    "alt_ref_high":     "coAlt_ref_high",
    "alt":              "coAlt_U_L",
    "alt_low":          "coAlt_ref_low",
    "alt_high":         "coAlt_ref_high",

    "ast_u_l":          "coAst_U_L",
    "ast_flag":         "coAst_flag",
    "ast_ref_low":      "coAst_ref_low",
    "ast_ref_high":     "coAst_ref_high",
    "ast":              "coAst_U_L",
    "ast_low":          "coAst_ref_low",
    "ast_high":         "coAst_ref_high",

    "bilirubin_mg_dl":  "coBilirubin_mg_dL",
    "bilirubin_flag":   "coBilirubin_flag",
    "bili_ref_low":     "coBili_ref_low",
    "bili_ref_high":    "coBili_ref_high",
    "bili":             "coBilirubin_mg_dL",
    "bili_low":         "coBili_ref_low",
    "bili_high":        "coBili_ref_high",

    "albumin_g_dl":     "coAlbumin_g_dL",
    "albumin_flag":     "coAlbumin_flag",
    "albumin_ref_low":  "coAlbumin_ref_low",
    "albumin_ref_high": "coAlbumin_ref_high",
    "alb":              "coAlbumin_g_dL",

    "inr":              "coInr",
    "inr_flag":         "coInr_flag",
    "inr_ref_low":      "coInr_ref_low",
    "inr_ref_high":     "coInr_ref_high",

    "lactate_mmol_l":   "coLactate_mmol_L",
    "lactate_flag":     "coLactate_flag",
    "lactate_ref_low":  "coLactate_ref_low",
    "lactate_ref_high": "coLactate_ref_high",

    # --- ICD / OPS ---
    "primary_icd10_code":             "coPrimary_icd10_code",
    "primary_icd10_description_en":   "coPrimary_icd10_description_en",
    "secondary_icd10_codes":          "coSecondary_icd10_codes",
    "secondary_icd10_descriptions_en":"coSecondary_icd10_descriptions_en",
    "ops_codes":                      "coOps_codes",
    "ops_descriptions_en":            "coOps_descriptions_en",

    "d_m":                            "coPrimary_icd10_code",
    "d_m_str":                        "coPrimary_icd10_description_en",
    "d_s":                            "coSecondary_icd10_codes",
    "d_s_str":                        "coSecondary_icd10_descriptions_en",
    "proc":                           "coOps_codes",
    "proc_str":                       "coOps_descriptions_en",

    "los":                            "coLength_of_stay_days",
    "length_of_stay_days":            "coLength_of_stay_days",

    # --- Device Motion ---
    "movement_index_0_100":       "coMovement_index_0_100",
    "micro_movements_count":      "coMicro_movements_count",
    "bed_exit_detected_0_1":      "coBed_exit_detected_0_1",
    "fall_event_0_1":             "coFall_event_0_1",
    "impact_magnitude_g":         "coImpact_magnitude_g",
    "post_fall_immobility_minutes": "coPost_fall_immobility_minutes",

    # --- Device 1Hz ---
    "device_id":              "coDevice_id",
    "bed_occupied_0_1":       "coBed_occupied_0_1",
    "movement_score_0_100":   "coMovement_score_0_100",
    "accel_x_m_s2":           "coAccel_x_m_s2",
    "accel_y_m_s2":           "coAccel_y_m_s2",
    "accel_z_m_s2":           "coAccel_z_m_s2",
    "accel_magnitude_g":      "coAccel_magnitude_g",
    "pressure_zone1_0_100":   "coPressure_zone1_0_100",
    "pressure_zone2_0_100":   "coPressure_zone2_0_100",
    "pressure_zone3_0_100":   "coPressure_zone3_0_100",
    "pressure_zone4_0_100":   "coPressure_zone4_0_100",
    "bed_exit_event_0_1":     "coBed_exit_event_0_1",
    "bed_return_event_0_1":   "coBed_return_event_0_1",
    "event_id":               "coEvent_id",
}
