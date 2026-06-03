-- PostgreSQL DDL for TelecomOps-Agent
-- Purpose: simulate structured telecom operation data for KPI query, alarm analysis,
-- parameter change tracking, and historical trouble ticket retrieval.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================
-- 1. Region / Site / Cell
-- =========================

CREATE TABLE regions (
    region_id           VARCHAR(32) PRIMARY KEY,
    region_name         VARCHAR(128) NOT NULL,
    city                VARCHAR(128) NOT NULL,
    province            VARCHAR(128),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sites (
    site_id             VARCHAR(64) PRIMARY KEY,
    region_id           VARCHAR(32) REFERENCES regions(region_id),
    site_name           VARCHAR(128) NOT NULL,
    vendor              VARCHAR(64),
    site_type           VARCHAR(64), -- macro, micro, indoor, repeater
    longitude           NUMERIC(10, 6),
    latitude            NUMERIC(10, 6),
    address             TEXT,
    status              VARCHAR(32) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cells (
    cell_id             VARCHAR(64) PRIMARY KEY,
    site_id             VARCHAR(64) REFERENCES sites(site_id),
    cell_name           VARCHAR(128),
    rat                 VARCHAR(16), -- 4G, 5G
    band                VARCHAR(32),
    pci                 INTEGER,
    tac                 INTEGER,
    azimuth             NUMERIC(6, 2),
    downtilt            NUMERIC(6, 2),
    tx_power_dbm        NUMERIC(6, 2),
    bandwidth_mhz       NUMERIC(6, 2),
    status              VARCHAR(32) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cells_site_id ON cells(site_id);
CREATE INDEX idx_cells_rat_band ON cells(rat, band);

-- =========================
-- 2. KPI time series
-- =========================

CREATE TABLE kpi_hourly (
    id                  BIGSERIAL PRIMARY KEY,
    ts                  TIMESTAMP NOT NULL,
    region_id           VARCHAR(32) REFERENCES regions(region_id),
    site_id             VARCHAR(64) REFERENCES sites(site_id),
    cell_id             VARCHAR(64) REFERENCES cells(cell_id),

    rsrp_avg_dbm        NUMERIC(6, 2),
    sinr_avg_db         NUMERIC(6, 2),
    prb_utilization     NUMERIC(6, 4), -- 0-1
    call_drop_rate      NUMERIC(6, 4), -- 0-1
    handover_success_rate NUMERIC(6, 4), -- 0-1
    rrc_setup_success_rate NUMERIC(6, 4), -- 0-1
    throughput_dl_mbps  NUMERIC(10, 2),
    throughput_ul_mbps  NUMERIC(10, 2),
    active_users        INTEGER,

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_kpi_hourly_cell_ts ON kpi_hourly(cell_id, ts DESC);
CREATE INDEX idx_kpi_hourly_site_ts ON kpi_hourly(site_id, ts DESC);
CREATE INDEX idx_kpi_hourly_region_ts ON kpi_hourly(region_id, ts DESC);

-- =========================
-- 3. Alarm records
-- =========================

CREATE TABLE alarms (
    alarm_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alarm_code          VARCHAR(64) NOT NULL,
    alarm_name          VARCHAR(128) NOT NULL,
    severity            VARCHAR(32) NOT NULL, -- critical, major, minor, warning
    region_id           VARCHAR(32) REFERENCES regions(region_id),
    site_id             VARCHAR(64) REFERENCES sites(site_id),
    cell_id             VARCHAR(64) REFERENCES cells(cell_id),
    first_seen_at       TIMESTAMP NOT NULL,
    cleared_at          TIMESTAMP,
    status              VARCHAR(32) DEFAULT 'active', -- active, cleared
    description         TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alarms_cell_time ON alarms(cell_id, first_seen_at DESC);
CREATE INDEX idx_alarms_site_time ON alarms(site_id, first_seen_at DESC);
CREATE INDEX idx_alarms_code ON alarms(alarm_code);
CREATE INDEX idx_alarms_status ON alarms(status);

-- =========================
-- 4. Parameter changes
-- =========================

CREATE TABLE parameter_changes (
    change_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id             VARCHAR(64) REFERENCES sites(site_id),
    cell_id             VARCHAR(64) REFERENCES cells(cell_id),
    parameter_name      VARCHAR(128) NOT NULL,
    old_value           VARCHAR(128),
    new_value           VARCHAR(128),
    changed_by          VARCHAR(128),
    change_reason       TEXT,
    changed_at          TIMESTAMP NOT NULL,
    rollback_available  BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_param_changes_cell_time ON parameter_changes(cell_id, changed_at DESC);
CREATE INDEX idx_param_changes_param ON parameter_changes(parameter_name);

-- =========================
-- 5. Neighbor relations
-- =========================

CREATE TABLE neighbor_relations (
    id                  BIGSERIAL PRIMARY KEY,
    source_cell_id      VARCHAR(64) REFERENCES cells(cell_id),
    target_cell_id      VARCHAR(64) REFERENCES cells(cell_id),
    relation_type       VARCHAR(32), -- intra_freq, inter_freq, inter_rat
    handover_priority   INTEGER,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_cell_id, target_cell_id)
);

CREATE INDEX idx_neighbor_source ON neighbor_relations(source_cell_id);
CREATE INDEX idx_neighbor_target ON neighbor_relations(target_cell_id);

-- =========================
-- 6. Trouble tickets
-- =========================

CREATE TABLE trouble_tickets (
    ticket_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(256) NOT NULL,
    region_id           VARCHAR(32) REFERENCES regions(region_id),
    site_id             VARCHAR(64) REFERENCES sites(site_id),
    cell_id             VARCHAR(64) REFERENCES cells(cell_id),
    fault_type          VARCHAR(128), -- coverage, interference, hardware, transmission, parameter
    severity            VARCHAR(32),
    status              VARCHAR(32) DEFAULT 'open',
    symptom_summary     TEXT,
    root_cause          TEXT,
    resolution          TEXT,
    opened_at           TIMESTAMP NOT NULL,
    closed_at           TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickets_cell_time ON trouble_tickets(cell_id, opened_at DESC);
CREATE INDEX idx_tickets_fault_type ON trouble_tickets(fault_type);
CREATE INDEX idx_tickets_status ON trouble_tickets(status);

-- =========================
-- 7. Agent logs and feedback
-- =========================

CREATE TABLE agent_query_logs (
    query_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          VARCHAR(128),
    user_query          TEXT NOT NULL,
    intent              VARCHAR(128),
    site_id             VARCHAR(64),
    cell_id             VARCHAR(64),
    selected_tools      JSONB,
    final_answer        TEXT,
    confidence          VARCHAR(32),
    latency_ms          NUMERIC(12, 2),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_logs_session ON agent_query_logs(session_id);
CREATE INDEX idx_agent_logs_created_at ON agent_query_logs(created_at DESC);

CREATE TABLE agent_feedback (
    feedback_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id            UUID REFERENCES agent_query_logs(query_id),
    rating              INTEGER CHECK (rating BETWEEN 1 AND 5),
    is_correct          BOOLEAN,
    comment             TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- 8. Example views
-- =========================

CREATE VIEW latest_cell_kpi AS
SELECT DISTINCT ON (cell_id)
    cell_id,
    site_id,
    ts,
    rsrp_avg_dbm,
    sinr_avg_db,
    prb_utilization,
    call_drop_rate,
    handover_success_rate,
    throughput_dl_mbps,
    active_users
FROM kpi_hourly
ORDER BY cell_id, ts DESC;

CREATE VIEW active_cell_alarms AS
SELECT
    alarm_id,
    alarm_code,
    alarm_name,
    severity,
    site_id,
    cell_id,
    first_seen_at,
    description
FROM alarms
WHERE status = 'active';

-- =========================
-- 9. Typical query patterns
-- =========================

-- KPI trend for one cell:
-- SELECT ts, rsrp_avg_dbm, sinr_avg_db, call_drop_rate
-- FROM kpi_hourly
-- WHERE cell_id = 'SZ-NS-023-2'
--   AND ts BETWEEN '2026-05-01 10:00:00' AND '2026-05-01 12:00:00'
-- ORDER BY ts;

-- Active alarms around incident:
-- SELECT alarm_code, alarm_name, severity, first_seen_at, cleared_at, description
-- FROM alarms
-- WHERE cell_id = 'SZ-NS-023-2'
--   AND first_seen_at >= '2026-05-01 09:00:00'
-- ORDER BY first_seen_at DESC;

-- Parameter changes before incident:
-- SELECT parameter_name, old_value, new_value, changed_by, changed_at, change_reason
-- FROM parameter_changes
-- WHERE cell_id = 'SZ-NS-023-2'
--   AND changed_at BETWEEN '2026-05-01 00:00:00' AND '2026-05-01 12:00:00'
-- ORDER BY changed_at DESC;
