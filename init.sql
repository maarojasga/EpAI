/* =============================================================================
   Unified Smart Health Schema - FINAL VERSION + FULL STAGING + ADJUSTMENTS
   START HACK 2026
   ============================================================================= */

-- =============================================================================
-- 1. LIMPIEZA (Opcional - Úsese con precaución en producción)
-- =============================================================================
DROP TABLE IF EXISTS tbConversation CASCADE;
DROP TABLE IF EXISTS tbAlert CASCADE;
DROP TABLE IF EXISTS tbDeviceLocation CASCADE;
DROP TABLE IF EXISTS tbDevice CASCADE;
DROP TABLE IF EXISTS tbMedicationPlan CASCADE;
DROP TABLE IF EXISTS tbCareIntervention CASCADE;
DROP TABLE IF EXISTS tbProcedure CASCADE;
DROP TABLE IF EXISTS tbCondition CASCADE;
DROP TABLE IF EXISTS tbObservation CASCADE;
DROP TABLE IF EXISTS tbClinicConceptMapping CASCADE;
DROP TABLE IF EXISTS tbConcept CASCADE;
DROP TABLE IF EXISTS tbAssessment CASCADE;
DROP TABLE IF EXISTS tbPatientMapping CASCADE;
DROP TABLE IF EXISTS tbPerson CASCADE;
DROP TABLE IF EXISTS tbClinic CASCADE;
DROP TABLE IF EXISTS tbStaff CASCADE;
DROP TABLE IF EXISTS tbShift CASCADE;
DROP TABLE IF EXISTS tbResource CASCADE;
DROP TABLE IF EXISTS tbDataQualityLog CASCADE;
DROP TABLE IF EXISTS tbMappingCorrection CASCADE;
-- Staging
DROP TABLE IF EXISTS tbCaseData CASCADE;
DROP TABLE IF EXISTS tbImportAcData CASCADE;
DROP TABLE IF EXISTS tbImportLabsData CASCADE;
DROP TABLE IF EXISTS tbImportIcd10Data CASCADE;
DROP TABLE IF EXISTS tbImportDeviceMotionData CASCADE;
DROP TABLE IF EXISTS tbImportDevice1HzMotionData CASCADE;
DROP TABLE IF EXISTS tbImportMedicationInpatientData CASCADE;
DROP TABLE IF EXISTS tbImportNursingDailyReportsData CASCADE;

-- =============================================================================
-- 1. INFRAESTRUCTURA
-- =============================================================================

CREATE TABLE tbClinic
(
    coId              SERIAL PRIMARY KEY,
    coName            VARCHAR(256)   NOT NULL,
    coLocation        VARCHAR(256)   NULL,
    coSystemType      VARCHAR(256)   NULL,        -- ej: SAP, IID, CSV_SIMPLE
    coSourceFilePattern VARCHAR(256) NULL,         -- ej: 'clinic_1_*', 'epaAC-Data-2*'
    coCountry         VARCHAR(100)   NULL         -- ej: DE, CH, AT
);

CREATE TABLE tbPerson
(
    coId SERIAL PRIMARY KEY,
    coGlobalId UUID NOT NULL DEFAULT gen_random_uuid(),
    coIdentification VARCHAR(256) NULL,
    coFirstName VARCHAR(256) NULL,
    coLastName VARCHAR(256) NULL,
    coGender VARCHAR(256) NULL,
    coDateOfBirth TIMESTAMP NULL,
    CONSTRAINT uqTBPERSON_GlobalId UNIQUE (coGlobalId)
);

CREATE TABLE tbPatientMapping
(
    coId SERIAL PRIMARY KEY,
    coClinicId INT NOT NULL,
    coLocalPatientId VARCHAR(256) NOT NULL,
    coPersonId INT NOT NULL,
    CONSTRAINT fkTBPATIENTMAPPING_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId),
    CONSTRAINT fkTBPATIENTMAPPING_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT uqTBPATIENTMAPPING_Local UNIQUE (coClinicId, coLocalPatientId)
);

-- =============================================================================
-- 2. MODELO CLÍNICO ARMONIZADO
-- =============================================================================

CREATE TABLE tbAssessment
(
    coId BIGSERIAL PRIMARY KEY,
    coPersonId INT NOT NULL,
    coCaseId BIGINT NULL,
    coClinicId INT NOT NULL,
    coAssessmentType VARCHAR(256) NULL,
    coAssessmentDatetime TIMESTAMP NOT NULL,
    coSource VARCHAR(256) NULL,
    CONSTRAINT fkTBASSESSMENT_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT fkTBASSESSMENT_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

CREATE TABLE tbConcept
(
    coId SERIAL PRIMARY KEY,
    coCode VARCHAR(100) NOT NULL,
    coSystem VARCHAR(100) NOT NULL,
    coDisplayName VARCHAR(512) NOT NULL,
    coCatery VARCHAR(100) NULL,
    CONSTRAINT uqTBCONCEPT_Code UNIQUE (coCode, coSystem)
);

CREATE TABLE tbClinicConceptMapping
(
    coId SERIAL PRIMARY KEY,
    coClinicId INT NOT NULL,
    coLocalCode VARCHAR(100) NOT NULL,
    coLocalName VARCHAR(512) NULL,
    coConceptId INT NOT NULL,
    CONSTRAINT fkTBCCM_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId),
    CONSTRAINT fkTBCCM_Concept FOREIGN KEY (coConceptId) REFERENCES tbConcept(coId),
    CONSTRAINT uqTBCCM_Local UNIQUE (coClinicId, coLocalCode)
);

CREATE TABLE tbObservation
(
    coId BIGSERIAL PRIMARY KEY,
    coPersonId INT NOT NULL,
    coCaseId BIGINT NULL,
    coAssessmentId BIGINT NULL,
    coClinicId INT NOT NULL,
    coConceptId INT NOT NULL,
    coTimestamp TIMESTAMP NOT NULL,
    coValue TEXT NULL,
    coNumericValue NUMERIC(18,4) NULL,
    coUnit VARCHAR(50) NULL,
    coReferenceLow VARCHAR(50) NULL,
    coReferenceHigh VARCHAR(50) NULL,
    coFlag VARCHAR(50) NULL,
    coSourceSystem VARCHAR(256) NULL,
    coSourceRecordId VARCHAR(256) NULL,
    CONSTRAINT fkTBOBSERVATION_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT fkTBOBSERVATION_Assessment FOREIGN KEY (coAssessmentId) REFERENCES tbAssessment(coId),
    CONSTRAINT fkTBOBSERVATION_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId),
    CONSTRAINT fkTBOBSERVATION_Concept FOREIGN KEY (coConceptId) REFERENCES tbConcept(coId)
);

CREATE TABLE tbCondition
(
    coId                  BIGSERIAL PRIMARY KEY,
    coPersonId            INT             NOT NULL,
    coCaseId              BIGINT          NULL,
    coClinicId            INT             NOT NULL,
    coIcdCode             VARCHAR(100)   NOT NULL,
    coDescription         TEXT            NULL,
    coIsPrimary           BOOLEAN         NULL,      -- 1 = diagnóstico principal, 0 = secundario
    coRank                INT             NULL,      -- orden dentro del episodio (1 = primario)
    coOnsetTimestamp      TIMESTAMP        NULL,      -- = admission_date
    coDischargeTimestamp  TIMESTAMP        NULL,      -- = discharge_date
    coLengthOfStayDays    INT             NULL,      -- = length_of_stay_days
    coWard                VARCHAR(256)   NULL,      -- unidad / sala
    coStatus              VARCHAR(50)    NULL,
    CONSTRAINT fkTBCONDITION_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT fkTBCONDITION_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

CREATE TABLE tbProcedure
(
    coId BIGSERIAL PRIMARY KEY,
    coPersonId INT NOT NULL,
    coCaseId BIGINT NULL,
    coClinicId INT NOT NULL,
    coOpsCode VARCHAR(100) NOT NULL,
    coDescription TEXT NULL,
    coTimestamp TIMESTAMP NULL,        -- nullable: OPS dataset no trae timestamp de procedimiento
    CONSTRAINT fkTBPROCEDURE_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT fkTBPROCEDURE_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

CREATE TABLE tbCareIntervention
(
    coId        BIGSERIAL PRIMARY KEY,
    coPersonId  INT             NOT NULL,
    coCaseId    BIGINT          NULL,
    coClinicId  INT             NOT NULL,
    coTimestamp TIMESTAMP        NOT NULL,
    coType      VARCHAR(256)   NOT NULL,   -- ej: NursingReport, Intervention
    coWard      VARCHAR(256)   NULL,        -- unidad de enfermería
    coShift     VARCHAR(100)   NULL,        -- morning | afternoon | night
    coReportDate DATE           NULL,        -- fecha del reporte de enfermería
    coNote      TEXT            NULL,        -- nursing_note_free_text
    coStatus    VARCHAR(50)    NULL,
    CONSTRAINT fkTBCAREINTERVENTION_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT fkTBCAREINTERVENTION_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

CREATE TABLE tbMedicationPlan
(
    coId                    BIGSERIAL PRIMARY KEY,
    coPersonId              INT             NOT NULL,
    coCaseId                BIGINT          NULL,
    coClinicId              INT             NOT NULL,
    coRecordType            VARCHAR(50)    NULL,      -- ORDER | CHANGE | ADMIN
    coOrderId               VARCHAR(256)   NULL,      -- para agrupar ORDER+CHANGE+ADMIN
    coMedicationName        VARCHAR(512)   NOT NULL,
    coAtcCode               VARCHAR(100)   NULL,
    coDose                  VARCHAR(256)   NULL,
    coDoseUnit              VARCHAR(100)   NULL,
    coFrequency             VARCHAR(256)   NULL,
    coRoute                 VARCHAR(256)   NULL,      -- IV, oral, SC...
    coIsPrn                 BOOLEAN         NULL,      -- is_prn_0_1 (pro re nata / a demanda)
    coIndication            VARCHAR(512)   NULL,
    coPrescriberRole        VARCHAR(256)   NULL,
    coStartTimestamp        TIMESTAMP        NULL,
    coStopTimestamp         TIMESTAMP        NULL,
    coAdministrationTimestamp TIMESTAMP      NULL,      -- solo en ADMIN
    coAdministeredDose      VARCHAR(256)   NULL,      -- solo en ADMIN
    coAdministeredUnit      VARCHAR(100)   NULL,      -- solo en ADMIN (unidad de dosis administrada)
    coAdministrationStatus  VARCHAR(100)   NULL,      -- given | missed | held | refused
    coNote                  TEXT            NULL,
    coStatus                VARCHAR(50)    NULL,
    CONSTRAINT fkTBMEDICATIONPLAN_Person FOREIGN KEY (coPersonId) REFERENCES tbPerson(coId),
    CONSTRAINT fkTBMEDICATIONPLAN_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

-- =============================================================================
-- 3. DISPOSITIVOS Y UBICACIÓN
-- =============================================================================

CREATE TABLE tbDevice
(
    coId SERIAL PRIMARY KEY,
    coClinicId INT NOT NULL,
    coDeviceLocalId VARCHAR(256) NOT NULL,
    coDeviceType VARCHAR(256) NULL,
    coModelName VARCHAR(256) NULL,
    CONSTRAINT fkTBDEVICE_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId),
    CONSTRAINT uqTBDEVICE_Local UNIQUE (coClinicId, coDeviceLocalId)
);

CREATE TABLE tbDeviceLocation
(
    coId SERIAL PRIMARY KEY,
    coDeviceId INT NOT NULL,
    coLocationName VARCHAR(256) NOT NULL,
    coTimestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fkTBDEVICELOCATION_Device FOREIGN KEY (coDeviceId) REFERENCES tbDevice(coId)
);

CREATE TABLE tbAlert
(
    coId            BIGSERIAL PRIMARY KEY,
    coClinicId      INT NOT NULL,
    coPatientId     VARCHAR(256) NULL,
    coDeviceId      VARCHAR(256) NOT NULL,
    coType          VARCHAR(100) NOT NULL,    -- ej: FALL, IMMOBILITY, RECOVERY
    coSeverity      VARCHAR(50)  NOT NULL,    -- ej: CRITICAL, WARNING, INFO
    coTimestamp     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    coLocation      VARCHAR(256) NULL,
    coMessage       TEXT NULL,
    coStatus        VARCHAR(50)  DEFAULT 'ACTIVE', -- ej: ACTIVE, ACKNOWLEDGED, RESOLVED
    coScore         NUMERIC(5,2)  NULL,
    coCaseId        BIGINT NULL,
    CONSTRAINT fkTBALERT_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
)
;

CREATE TABLE tbConversation
(
    coId            SERIAL PRIMARY KEY,
    coConversationId UUID NOT NULL DEFAULT gen_random_uuid(),
    coClinicId      INT NOT NULL,
    coPatientId     VARCHAR(256) NULL,
    coHistoryJson   TEXT NOT NULL,    -- Almacena la lista de mensajes en formato JSON
    coUpdatedAt     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fkTBCOVERSATION_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId),
    CONSTRAINT uqTBCONVERSATION_Id UNIQUE (coConversationId)
);

-- Índices para búsqueda rápida en monitoreo
CREATE INDEX idx_alert_patient ON tbAlert(coPatientId);
CREATE INDEX idx_alert_timestamp ON tbAlert(coTimestamp);
CREATE INDEX idx_observation_patient ON tbObservation(coPersonId, coTimestamp);


-- =============================================================================
-- 4. STAFF Y RECURSOS
-- =============================================================================

CREATE TABLE tbStaff
(
    coId SERIAL PRIMARY KEY,
    coFirstName VARCHAR(256) NULL,
    coLastName VARCHAR(256) NULL,
    coRole VARCHAR(256) NULL,
    coExternalId VARCHAR(256) NULL
);

CREATE TABLE tbShift
(
    coId SERIAL PRIMARY KEY,
    coStaffId INT NOT NULL,
    coClinicId INT NOT NULL,
    coStartTimestamp TIMESTAMP NOT NULL,
    coEndTimestamp TIMESTAMP NOT NULL,
    coWard VARCHAR(256) NULL,
    CONSTRAINT fkTBSHIFT_Staff FOREIGN KEY (coStaffId) REFERENCES tbStaff(coId),
    CONSTRAINT fkTBSHIFT_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

CREATE TABLE tbResource
(
    coId SERIAL PRIMARY KEY,
    coClinicId INT NOT NULL,
    coResourceType VARCHAR(256) NULL,
    coResourceName VARCHAR(256) NULL,
    coStatus VARCHAR(50) NULL,
    CONSTRAINT fkTBRESOURCE_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

-- =============================================================================
-- 5. DATA QUALITY
-- =============================================================================

CREATE TABLE tbDataQualityLog
(
    coId SERIAL PRIMARY KEY,
    coClinicId INT NOT NULL,
    coFileSource VARCHAR(256) NULL,
    coEntityName VARCHAR(256) NULL,
    coFieldName VARCHAR(256) NULL,
    coRecordKey VARCHAR(256) NULL,
    coRuleName VARCHAR(256) NULL,
    coCheckType VARCHAR(100) NULL,
    coDescription TEXT NULL,
    coOldValue TEXT NULL,
    coNewValue TEXT NULL,
    coSeverity VARCHAR(50) NULL,
    coDetectedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fkTBDATAQUALITYLOG_Clinic FOREIGN KEY (coClinicId) REFERENCES tbClinic(coId)
);

CREATE TABLE tbMappingCorrection
(
    coId SERIAL PRIMARY KEY,
    coTable VARCHAR(100) NOT NULL,
    coField VARCHAR(100) NULL,
    coOriginalValue TEXT NULL,
    coCorrectedValue TEXT NULL,
    coConfidence NUMERIC(3,2) NULL,
    coReviewStatus VARCHAR(20) NULL,
    coReviewedBy INT NULL,
    CONSTRAINT fkTBMAPPINGCORRECTION_ReviewedBy FOREIGN KEY (coReviewedBy) REFERENCES tbStaff(coId)
);

-- =============================================================================
-- 6. STAGING (BASE PARA ETL - FULL VERSIONS PRESERVADAS)
-- =============================================================================

create table tbCaseData
(
    coCaseId				bigint			null,
    coE2I222				bigint			null,
    coPatientId				bigint			null,

    coPersonId				bigint			null,
    coClinicId				int             null,



    coE2I223				timestamp		null,
    coE2I228				timestamp		null,
    coAdmission_date		timestamp		null,
    coDischarge_date		timestamp		null,

    coLastname				varchar(256)	null,
    coFirstname				varchar(256)	null,
    coGender				varchar(256)	null,
    coDateOfBirth			timestamp		null,
	coAgeYears				int				null,
    coTypeOfStay			varchar(256)	null,
    coIcd					varchar(256)	null,
    coDrgName				varchar(256)	null,
    coRecliningType			varchar(256)	null,
    coState					varchar(256)	null
);

/* Tabelle tbAcData */

create table tbImportAcData 
(
	coId					BIGSERIAL PRIMARY KEY,
    coCaseId		    	bigint          null,
    coE0I001				smallint		null,
	coE0I002				smallint		null,
	coE0I003   			    smallint		null,
	coE0I004				smallint		null,
	coE0I005				numeric(6,3)    null,
	coE0I007				smallint		null,
	coE0I008				smallint		null,
	coE0I009				smallint		null,
	coE0I010				smallint		null,
	coE0I011				smallint		null,
	coE0I012				smallint		null,
	coE0I013				smallint		null,
	coE0I014				smallint		null,
	coE0I015				smallint		null,
	coE0I021				smallint		null,
	coE0I043				smallint		null,
	coE0I070				smallint		null,
	coE0I074				smallint		null,
	coE0I075				smallint		null,
	coE0I076				smallint		null,
	coE0I077				smallint		null,
	coE0I078				smallint		null,
	coE0I079				smallint		null,
	coE0I081				smallint		null,
	coE0I082				smallint		null,
	coE0I083				smallint		null,
	coE0I0116				smallint		null,
	coE0I0122				smallint		null,
	coE0I0134				smallint		null,
	coE0I0141				smallint		null,
	coE0I0150				smallint		null,
	coE0I0163				smallint		null,
	coE0I0168				smallint		null,
	coE0I0173				smallint		null,
	coE0I0178				smallint		null,
	coE0I0190				smallint		null,
	coE0I0241				smallint		null,
	coE0I0262				smallint		null,
	coE0I0266				smallint		null,
	coE0I0270				smallint		null,
	coE0I0276				smallint		null,
	coE0I0004				varchar(512)	null,
	coE0I0071				smallint		null,
	coE0I0077				smallint		null,
	coE0I0081				smallint		null,

	coE2I001				smallint        null,
	coE2I002				smallint        null,
	coE2I003				smallint        null,
	coE2I004				smallint        null,
	coE2I005				smallint        null,
	coE2I006				smallint        null,
	coE2I007				smallint        null,
	coE2I008				smallint        null,
	coE2I009			    smallint        null,
	coE2I010			    smallint        null,
	coE2I011			    smallint        null,
	coE2I012			    smallint        null,
	coE2I013				smallint        null,
	coE2I014				smallint        null,
	coE2I015				smallint        null,
	coE2I017				smallint        null,
	coE2I018				smallint        null,
	coE2I019				smallint        null,
	coE2I020				smallint        null,
	coE2I021				smallint        null,
	coE2I022				smallint        null,
	coE2I023				smallint        null,
	coE2I024			    smallint        null,
	coE2I025			    smallint        null,
	coE2I026			    smallint        null,
	coE2I027			    smallint        null,
	coE2I028			    smallint        null,
	coE2I029			    smallint        null,
	coE2I030			    smallint        null,
	coE2I031			    smallint        null,
	coE2I032			    smallint        null,
	coE2I033			    smallint        null,
	coE2I034			    smallint        null,
	coE2I035			    smallint        null,
	coE2I036			    smallint        null,
	coE2I037			    smallint        null,
	coE2I038			    smallint        null,
	coE2I039			    smallint        null,
	coE2I040			    smallint        null,
	coE2I041			    smallint        null,
	coE2I042			    smallint        null,
	coE2I043			    smallint        null,
	coE2I044			    smallint        null,
	coE2I045			    smallint        null,
	coE2I046			    smallint        null,
	coE2I047			    smallint        null,
	coE2I048			    smallint        null,
	coE2I049			    smallint        null,
	coE2I050			    smallint        null,
	coE2I051			    smallint        null,
	coE2I052			    smallint        null,
	coE2I053			    smallint        null,
	coE2I054			    smallint        null,
	coE2I055				smallint        null,
	coE2I056			    smallint        null,
	coE2I057			    smallint        null,
	coE2I058			    smallint        null,
	coE2I059			    smallint        null,
	coE2I060				smallint        null,
	coE2I061			    smallint        null,
	coE2I062			    smallint        null,
	coE2I063			    smallint        null,
	coE2I064			    smallint        null,
	coE2I065			    smallint        null,
	coE2I066			    smallint        null,
	coE2I067			    smallint        null,
	coE2I068			    smallint        null,
	coE2I069			    smallint        null,
	coE2I070			    smallint        null,
	coE2I071			    smallint        null,
	coE2I072			    smallint        null,
	coE2I073			    smallint        null,
	coE2I074			    smallint        null,
	coE2I075			    smallint        null,
	coE2I076			    smallint        null,
	coE2I077			    smallint        null,
	coE2I078			    smallint        null,
	coE2I079			    smallint        null,
	coE2I080			    smallint        null,
	coE2I081			    smallint        null,
	coE2I082			    smallint        null,
	coE2I083			    smallint        null,
	coE2I084			    smallint        null,
	coE2I085			    smallint        null,
	coE2I086			    smallint        null,
	coE2I087			    smallint        null,
	coE2I088			    smallint        null,
	coE2I089				varchar(512)	null,
	coE2I090				varchar(512)	null,
	coE2I091				varchar(512)	null,
	coE2I092				varchar(512)	null,
	coE2I093				varchar(512)	null,
	coE2I095				smallint		null,
	coE2I094				varchar(512)	null,
	coE2I096				varchar(512)	null,
	coE2I097				varchar(512)	null,
	coE2I098				varchar(512)	null,
	coE2I099				varchar(512)	null,
	coE2I100				varchar(512)	null,
	coE2I101  				varchar(512)	null,
	coE2I102				smallint		null,
	coE2I103				smallint		null,
	coE2I104				smallint		null,
	coE2I105				smallint		null,
	coE2I106				smallint		null,
	coE2I107				smallint		null,
	coE2I108				smallint		null,
	coE2I109				smallint		null,
	coE2I110				smallint		null,
	coE2I111				smallint		null,
	coE2I112				smallint		null,
	coE2I113				smallint		null,
	coE2I114				smallint		null,
	coE2I115				smallint		null,
	coE2I116				smallint		null,
	coE2I117				smallint		null,
	coE2I118				smallint		null,
	coE2I119				smallint		null,
	coE2I121				smallint		null,
	coE2I122				smallint		null,
	coE2I123				smallint		null,
	coE2I124				smallint		null,
	coE2I125				smallint		null,
	coE2I126				smallint		null,
	coE2I127				smallint		null,
	coE2I128				smallint		null,
	coE2I129				smallint		null,
	coE2I130				smallint		null,
	coE2I131				smallint		null,
	coE2I132				smallint		null,
	coE2I133				smallint		null,
	coE2I134				smallint		null,
	coE2I135				smallint		null,
	coE2I136				smallint		null,
	coE2I137				smallint		null,
	coE2I138				smallint		null,
	coE2I139				smallint		null,
	coE2I140				smallint		null,
	coE2I141				smallint		null,
	coE2I142				smallint		null,
	coE2I143				smallint		null,
	coE2I144				smallint		null,
	coE2I145				smallint		null,
	coE2I146				smallint		null,
	coE2I147				smallint		null,
	coE2I148				smallint		null,
	coE2I150				smallint		null,
	coE2I151				smallint		null,
	coE2I152				smallint		null,
	coE2I154				smallint		null,
	coE2I155				smallint		null,
	coE2I156				smallint		null,
	coE2I157				smallint		null,
	coE2I158				smallint		null,
	coE2I159				smallint		null,
	coE2I160				smallint        null,
	coE2I161				smallint        null,
	coE2I162				smallint        null,
	coE2I163				smallint        null,
	coE2I164				smallint        null,
	coE2I165				smallint        null,
	coE2I166				smallint        null,
	coE2I167				smallint        null,
	coE2I168				smallint        null,
	coE2I169				smallint        null,
	coE2I170				smallint        null,
	coE2I171				smallint        null,
	coE2I172				smallint        null,
	coE2I173				smallint        null,
	coE2I178				smallint        null,
	coE2I179				smallint        null,
	coE2I217				smallint        null,
	coE2I218				smallint        null,
	coE2I220				smallint        null,
	coE2I221				smallint        null,
	coE2I222				bigint			null,
	coE2I223				timestamp        null,
	coE2I224				smallint        null,
	coE2I225				timestamp		not null,
	coE2I226		        bigint          null,
	coE2I227				smallint		null,
	coE2I228				timestamp        null,
	coE2I229				smallint		null,
	coE2I230				varchar(256)	null,
	coE2I231				varchar(256)	null,
	coE2I232				varchar(256)	null,

	coE2I2000				smallint        null,
	coE2I2013				smallint        null,
	coE2I2022				smallint        null,
	coE2I2029				smallint		null,
	coE2I2033				smallint        null,
	coE2I2092				smallint        null,
	coE2I2099				smallint        null,
	coE2I2126				smallint		null,
	coE2I2134				smallint        null,
	coE2I2148				smallint        null,
	coE2I2154				smallint		null,
	coE2I2157				smallint		null,
	coE2I2165				smallint        null,
	coE2I2170				smallint		null,
	coE2I2175				smallint		null,
	coE2I2180				smallint		null,
	coE2I2188				smallint		null,
	coE2I2191				smallint		null,
	coE2I2195				smallint		null,
	coE2I2199				smallint        null,
	coE2I2203				smallint		null,
	coE2I2207				smallint		null,
	coE2I2211				smallint		null,
	coE2I2216				smallint		null,
	coE2I2222				smallint		null,
	coE2I2256				smallint		null,
	coE2I2267				smallint		null,
	coE2I2279				smallint		null,

	coMaxDekuGrad           smallint        null,
	coDekubitusWertTotal	smallint        null,
	coLastAssessment		smallint        null,
	coE3I0889				varchar(256)	null,
	coCaseIdAlpha			varchar(256)	null
);

create table tbImportLabsData
(
	coId					BIGSERIAL PRIMARY KEY,
    coCaseId		    	bigint          null,
	coPatientId		    	varchar(256)    null,
	coSpecimen_datetime		varchar(256)	null,

	coSodium_mmol_L			varchar(256)	null,
	coSodium_flag			varchar(256)	null,
	cosodium_ref_low		varchar(256)	null,
	cosodium_ref_high		varchar(256)	null,
	coPotassium_mmol_L		varchar(256)	null,
	coPotassium_flag		varchar(256)	null,
	coPotassium_ref_low		varchar(256)	null,
	coPotassium_ref_high	varchar(256)	null,
	coCreatinine_mg_dL		varchar(256)	null,
	coCreatinine_flag		varchar(256)	null,
	coCreatinine_ref_low	varchar(256)	null,
	coCreatinine_ref_high	varchar(256)	null,
	coEgfr_mL_min_1_73m2	varchar(256)	null,
	coEgfr_flag				varchar(256)	null,
	coEgfr_ref_low			varchar(256)	null,
	coEgfr_ref_high			varchar(256)	null,
	coGlucose_mg_dL			varchar(256)	null,
	coGlucose_flag			varchar(256)	null,
	coGlucose_ref_low		varchar(256)	null,
	coGlucose_ref_high		varchar(256)	null,
	coHemoglobin_g_dL		varchar(256)	null,
	coHb_flag				varchar(256)	null,
	coHb_ref_low			varchar(256)	null,
	coHb_ref_high			varchar(256)	null,
	coWbc_10e9_L			varchar(256)	null,
	coWbc_flag				varchar(256)	null,
	coWbc_ref_low			varchar(256)	null,
	coWbc_ref_high			varchar(256)	null,
	coPlatelets_10e9_L		varchar(256)	null,
	coPlatelets_flag		varchar(256)	null,
	coPlt_ref_low			varchar(256)	null,
	coPlt_ref_high			varchar(256)	null,
	coCrp_mg_L				varchar(256)	null,
	coCrp_flag				varchar(256)	null,
	coCrp_ref_low			varchar(256)	null,
	coCrp_ref_high			varchar(256)	null,
	coAlt_U_L				varchar(256)	null,
	coAlt_flag				varchar(256)	null,
	coAlt_ref_low			varchar(256)	null,
	coAlt_ref_high			varchar(256)	null,
	coAst_U_L				varchar(256)	null,
	coAst_flag				varchar(256)	null,
	coAst_ref_low			varchar(256)	null,
	coAst_ref_high			varchar(256)	null,
	coBilirubin_mg_dL		varchar(256)	null,
	coBilirubin_flag		varchar(256)	null,
	coBili_ref_low			varchar(256)	null,
	coBili_ref_high			varchar(256)	null,
	coAlbumin_g_dL			varchar(256)	null,
	coAlbumin_flag			varchar(256)	null,
	coAlbumin_ref_low		varchar(256)	null,
	coAlbumin_ref_high		varchar(256)	null,
	coInr					varchar(256)	null,
	coInr_flag				varchar(256)	null,
	coInr_ref_low			varchar(256)	null,
	coInr_ref_high			varchar(256)	null,
	coLactate_mmol_L		varchar(256)	null,
	coLactate_flag			varchar(256)	null,
	coLactate_ref_low		varchar(256)	null,
	coLactate_ref_high		varchar(256)	null
);

create table tbImportIcd10Data
(
	coId								BIGSERIAL PRIMARY KEY,
    coCaseId		    				bigint          null,
	coPatientId		    				varchar(256)    null,
	coWard								varchar(256)	null,

	coAdmission_date					varchar(256)	null,
	coDischarge_date					varchar(256)	null,
	coLength_of_stay_days				varchar(256)	null,
	coPrimary_icd10_code				varchar(256)	null,
	coPrimary_icd10_description_en		varchar(256)	null,
	coSecondary_icd10_codes				varchar(256)	null,
	coSecondary_icd10_descriptions_en	varchar(256)	null,
	coOps_codes							varchar(256)	null,
	coOps_descriptions_en				varchar(256)	null
);


create table tbImportDeviceMotionData
(
	coId							BIGSERIAL PRIMARY KEY,
    coCaseId		    			bigint          null,
	coTimestamp						timestamp		null,
	coPatientId						varchar(256)	null,

	coMovement_index_0_100			varchar(256)	null,
	coMicro_movements_count			varchar(256)	null,
	coBed_exit_detected_0_1			varchar(256)	null,
	coFall_event_0_1				varchar(256)	null,
	coImpact_magnitude_g			varchar(256)	null,
	coPost_fall_immobility_minutes	varchar(256)	null
);

create table tbImportDevice1HzMotionData
(
	coId					BIGSERIAL PRIMARY KEY,
    coCaseId		    	bigint          null,
	coTimestamp				timestamp		null,
	coPatientId				varchar(256)	null,

	coDevice_id				varchar(256)	null,
	coBed_occupied_0_1		varchar(256)	null,
	coMovement_score_0_100	varchar(256)	null,
	coAccel_x_m_s2			varchar(256)	null,
	coAccel_y_m_s2			varchar(256)	null,
	coAccel_z_m_s2			varchar(256)	null,
	coAccel_magnitude_g		varchar(256)	null,
	coPressure_zone1_0_100	varchar(256)	null,
	coPressure_zone2_0_100	varchar(256)	null,
	coPressure_zone3_0_100	varchar(256)	null,
	coPressure_zone4_0_100	varchar(256)	null,
	coBed_exit_event_0_1	varchar(256)	null,
	coBed_return_event_0_1	varchar(256)	null,
	coFall_event_0_1		varchar(256)	null,
	coImpact_magnitude_g	varchar(256)	null,
	coEvent_id				varchar(256)	null
);

create table tbImportMedicationInpatientData
(
	coId					BIGSERIAL PRIMARY KEY,
    coCaseId		    	bigint          null,
	coPatientId				varchar(256)	null,

	coRecord_type			varchar(256)	null,
	coEncounter_id			varchar(256)	null,
	coWard					varchar(256)	null,
	coAdmission_datetime	varchar(256)	null,
	coDischarge_datetime	varchar(256)	null,
	coOrder_id				varchar(256)	null,
	coOrder_uuid			varchar(256)	null,
	coMedication_code_atc	varchar(256)	null,
	coMedication_name		varchar(256)	null,
	coRoute					varchar(256)	null,
	coDose					varchar(256)	null,
	coDose_unit				varchar(256)	null,
	coFrequency				varchar(256)	null,
	coOrder_start_datetime	varchar(256)	null,
	coOrder_stop_datetime	varchar(256)	null,
	coIs_prn_0_1			varchar(256)	null,
	coIndication			varchar(256)	null,
	prescriber_role			varchar(256)	null,
	order_status			varchar(256)	null,
	administration_datetime	varchar(256)	null,
	administered_dose		varchar(256)	null,
	administered_unit		varchar(256)	null,
	administration_status	varchar(256)	null,
	note					varchar(256)	null
);

create table tbImportNursingDailyReportsData
(
	coId						BIGSERIAL PRIMARY KEY,
    coCaseId		    		bigint          null,
	coPatientId					varchar(256)	null,

	coWard						varchar(256)	null,
	coReport_date				varchar(256)	null,
	coShift						varchar(256)	null,
	coNursing_note_free_text	varchar(256)	null
);

-- Persistent Audit Log for Ingestion Processes
create table tbIngestionJob
(
    coId                BIGSERIAL PRIMARY KEY,
    coJobId             varchar(64) UNIQUE NOT NULL,
    coClinicId          int,
    coFilename          varchar(512),
    coFileFormat        varchar(16),
    coStatus            varchar(32),
    coTargetTable       varchar(128),
    coRowsLoaded        int DEFAULT 0,
    coRejectedCount     int DEFAULT 0,
    coNormalizationAudit jsonb,
    coRejectedRows      jsonb,
    coTimestamp         timestamp DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- FIN
-- =============================================================================

