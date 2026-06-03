# Neo4j Graph Schema for TelecomOps-Agent

## 1. Design Goal

The Neo4j graph is used for GraphRAG-style multi-hop reasoning.

It connects telecom entities, symptoms, KPIs, alarms, fault modes, root causes, troubleshooting actions, and historical cases.

Core reasoning path:

```text
KPI anomaly / Alarm / Symptom
→ FaultMode
→ RootCause
→ CheckAction
→ RepairAction
→ HistoricalCase
```

---

## 2. Node Labels

### 2.1 `Region`

Represents a geographical region.

Properties:

```cypher
{
  region_id: STRING,
  name: STRING,
  city: STRING,
  province: STRING
}
```

---

### 2.2 `Site`

Represents a physical telecom site.

Properties:

```cypher
{
  site_id: STRING,
  name: STRING,
  vendor: STRING,
  site_type: STRING,
  longitude: FLOAT,
  latitude: FLOAT,
  status: STRING
}
```

---

### 2.3 `Cell`

Represents a 4G/5G cell.

Properties:

```cypher
{
  cell_id: STRING,
  name: STRING,
  rat: STRING,
  band: STRING,
  pci: INTEGER,
  azimuth: FLOAT,
  downtilt: FLOAT,
  tx_power_dbm: FLOAT,
  status: STRING
}
```

---

### 2.4 `KPI`

Represents a KPI type.

Examples:

```text
RSRP
SINR
PRB_UTILIZATION
CALL_DROP_RATE
HANDOVER_SUCCESS_RATE
RRC_SETUP_SUCCESS_RATE
DL_THROUGHPUT
```

Properties:

```cypher
{
  name: STRING,
  category: STRING,
  unit: STRING,
  normal_range: STRING,
  description: STRING
}
```

---

### 2.5 `KPIAnomaly`

Represents abnormal KPI patterns.

Examples:

```text
RSRP_DROP
SINR_DEGRADATION
CALL_DROP_RATE_INCREASE
HANDOVER_SUCCESS_RATE_DROP
HIGH_PRB_UTILIZATION
```

Properties:

```cypher
{
  anomaly_id: STRING,
  name: STRING,
  severity: STRING,
  detection_rule: STRING,
  description: STRING
}
```

---

### 2.6 `Alarm`

Represents an alarm type.

Examples:

```text
VSWR_HIGH
RRU_POWER_LOW
TRANSMISSION_LOSS
GPS_UNLOCKED
CELL_UNAVAILABLE
```

Properties:

```cypher
{
  alarm_code: STRING,
  name: STRING,
  severity: STRING,
  description: STRING
}
```

---

### 2.7 `FaultMode`

Represents abstract fault mode.

Examples:

```text
COVERAGE_DEGRADATION
INTERFERENCE
HARDWARE_FAILURE
TRANSMISSION_FAILURE
PARAMETER_MISCONFIGURATION
CAPACITY_CONGESTION
```

Properties:

```cypher
{
  fault_mode_id: STRING,
  name: STRING,
  description: STRING
}
```

---

### 2.8 `RootCause`

Represents possible root cause.

Examples:

```text
ANTENNA_FEEDER_ISSUE
RRU_POWER_AMPLIFIER_FAILURE
INCORRECT_DOWNTILT
NEIGHBOR_RELATION_MISSING
HIGH_TRAFFIC_LOAD
EXTERNAL_INTERFERENCE
```

Properties:

```cypher
{
  cause_id: STRING,
  name: STRING,
  category: STRING,
  description: STRING
}
```

---

### 2.9 `Action`

Represents troubleshooting or repair action.

Examples:

```text
CHECK_VSWR
CHECK_FEEDER_CONNECTION
ROLLBACK_PARAMETER
OPTIMIZE_NEIGHBOR_RELATION
DISPATCH_FIELD_ENGINEER
```

Properties:

```cypher
{
  action_id: STRING,
  name: STRING,
  action_type: STRING,
  priority: INTEGER,
  description: STRING
}
```

---

### 2.10 `Parameter`

Represents network configuration parameter.

Examples:

```text
tx_power_dbm
downtilt
handover_margin
cell_individual_offset
pci
```

Properties:

```cypher
{
  name: STRING,
  category: STRING,
  unit: STRING,
  description: STRING
}
```

---

### 2.11 `Case`

Represents historical trouble ticket or fault case.

Properties:

```cypher
{
  case_id: STRING,
  title: STRING,
  fault_type: STRING,
  symptom_summary: STRING,
  root_cause: STRING,
  resolution: STRING,
  created_at: DATETIME
}
```

---

## 3. Relationships

### 3.1 Topology

```text
(:Region)-[:CONTAINS]->(:Site)
(:Site)-[:HAS_CELL]->(:Cell)
(:Cell)-[:NEIGHBOR_OF]->(:Cell)
```

Relationship properties:

```cypher
(:Cell)-[:NEIGHBOR_OF {
  relation_type: STRING,
  handover_priority: INTEGER
}]->(:Cell)
```

---

### 3.2 KPI and alarm reasoning

```text
(:KPI)-[:HAS_ANOMALY]->(:KPIAnomaly)
(:KPIAnomaly)-[:INDICATES]->(:FaultMode)
(:Alarm)-[:INDICATES]->(:FaultMode)
(:FaultMode)-[:CAUSED_BY]->(:RootCause)
(:RootCause)-[:CHECKED_BY]->(:Action)
(:RootCause)-[:RESOLVED_BY]->(:Action)
```

---

### 3.3 Parameter reasoning

```text
(:Parameter)-[:AFFECTS]->(:KPI)
(:Parameter)-[:MAY_CAUSE]->(:FaultMode)
(:RootCause)-[:RELATED_PARAMETER]->(:Parameter)
```

---

### 3.4 Historical cases

```text
(:Case)-[:HAS_SYMPTOM]->(:KPIAnomaly)
(:Case)-[:HAS_ALARM]->(:Alarm)
(:Case)-[:ROOT_CAUSE_IS]->(:RootCause)
(:Case)-[:RESOLVED_BY]->(:Action)
(:Case)-[:OCCURRED_ON]->(:Cell)
```

---

## 4. Constraints and Indexes

```cypher
CREATE CONSTRAINT region_id_unique IF NOT EXISTS
FOR (r:Region) REQUIRE r.region_id IS UNIQUE;

CREATE CONSTRAINT site_id_unique IF NOT EXISTS
FOR (s:Site) REQUIRE s.site_id IS UNIQUE;

CREATE CONSTRAINT cell_id_unique IF NOT EXISTS
FOR (c:Cell) REQUIRE c.cell_id IS UNIQUE;

CREATE CONSTRAINT kpi_name_unique IF NOT EXISTS
FOR (k:KPI) REQUIRE k.name IS UNIQUE;

CREATE CONSTRAINT anomaly_id_unique IF NOT EXISTS
FOR (a:KPIAnomaly) REQUIRE a.anomaly_id IS UNIQUE;

CREATE CONSTRAINT alarm_code_unique IF NOT EXISTS
FOR (a:Alarm) REQUIRE a.alarm_code IS UNIQUE;

CREATE CONSTRAINT fault_mode_id_unique IF NOT EXISTS
FOR (f:FaultMode) REQUIRE f.fault_mode_id IS UNIQUE;

CREATE CONSTRAINT cause_id_unique IF NOT EXISTS
FOR (c:RootCause) REQUIRE c.cause_id IS UNIQUE;

CREATE CONSTRAINT action_id_unique IF NOT EXISTS
FOR (a:Action) REQUIRE a.action_id IS UNIQUE;

CREATE CONSTRAINT parameter_name_unique IF NOT EXISTS
FOR (p:Parameter) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT case_id_unique IF NOT EXISTS
FOR (c:Case) REQUIRE c.case_id IS UNIQUE;
```

---

## 5. Seed Data Examples

```cypher
MERGE (k:KPI {
  name: "RSRP",
  category: "coverage",
  unit: "dBm",
  normal_range: "-95 to -75",
  description: "Reference Signal Received Power"
});

MERGE (a:KPIAnomaly {
  anomaly_id: "RSRP_DROP",
  name: "RSRP Drop",
  severity: "major",
  detection_rule: "rsrp_avg_dbm decreases by more than 10 dB within 2 hours",
  description: "Coverage degradation symptom"
});

MERGE (fm:FaultMode {
  fault_mode_id: "COVERAGE_DEGRADATION",
  name: "Coverage Degradation",
  description: "Cell coverage quality becomes worse"
});

MERGE (rc:RootCause {
  cause_id: "ANTENNA_FEEDER_ISSUE",
  name: "Antenna Feeder Issue",
  category: "hardware",
  description: "Feeder or antenna connector may be loose, damaged, or waterlogged"
});

MERGE (act:Action {
  action_id: "CHECK_VSWR",
  name: "Check VSWR",
  action_type: "field_check",
  priority: 1,
  description: "Check VSWR value and antenna feeder connection"
});

MERGE (k)-[:HAS_ANOMALY]->(a)
MERGE (a)-[:INDICATES]->(fm)
MERGE (fm)-[:CAUSED_BY]->(rc)
MERGE (rc)-[:CHECKED_BY]->(act);
```

---

## 6. Typical GraphRAG Queries

### 6.1 Find root causes by KPI anomaly

```cypher
MATCH path = (:KPIAnomaly {anomaly_id: "RSRP_DROP"})
  -[:INDICATES]->(:FaultMode)
  -[:CAUSED_BY]->(:RootCause)
  -[:CHECKED_BY|RESOLVED_BY]->(:Action)
RETURN path
LIMIT 10;
```

### 6.2 Combine KPI anomaly and alarm

```cypher
MATCH (ka:KPIAnomaly {anomaly_id: "RSRP_DROP"})-[:INDICATES]->(fm:FaultMode)
MATCH (al:Alarm {alarm_code: "VSWR_HIGH"})-[:INDICATES]->(fm)
MATCH (fm)-[:CAUSED_BY]->(rc:RootCause)
OPTIONAL MATCH (rc)-[:CHECKED_BY]->(check:Action)
OPTIONAL MATCH (rc)-[:RESOLVED_BY]->(fix:Action)
RETURN fm.name AS fault_mode,
       rc.name AS root_cause,
       collect(DISTINCT check.name) AS check_actions,
       collect(DISTINCT fix.name) AS fix_actions;
```

### 6.3 Retrieve similar historical cases

```cypher
MATCH (c:Case)-[:HAS_SYMPTOM]->(:KPIAnomaly {anomaly_id: "RSRP_DROP"})
OPTIONAL MATCH (c)-[:HAS_ALARM]->(:Alarm {alarm_code: "VSWR_HIGH"})
OPTIONAL MATCH (c)-[:ROOT_CAUSE_IS]->(rc:RootCause)
OPTIONAL MATCH (c)-[:RESOLVED_BY]->(a:Action)
RETURN c.case_id, c.title, c.symptom_summary, rc.name, collect(a.name) AS actions
LIMIT 5;
```

### 6.4 Trace site topology

```cypher
MATCH (s:Site {site_id: "SZ-NS-023"})-[:HAS_CELL]->(c:Cell)
OPTIONAL MATCH (c)-[n:NEIGHBOR_OF]->(nc:Cell)
RETURN s.site_id, c.cell_id, collect(nc.cell_id) AS neighbors;
```

---

## 7. How the Agent Uses the Graph

The Graph Tool should return structured evidence, not raw graph objects only.

Example output:

```json
{
  "query_type": "root_cause_reasoning",
  "paths": [
    {
      "symptom": "RSRP_DROP",
      "fault_mode": "Coverage Degradation",
      "root_cause": "Antenna Feeder Issue",
      "actions": ["Check VSWR", "Check feeder connection"],
      "confidence_hint": "high"
    }
  ]
}
```

The LLM then uses this as grounded evidence for the final diagnosis report.
