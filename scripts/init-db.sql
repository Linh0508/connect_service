-- ============================================================
-- B6 Core Business Database - Complete Schema
-- Version: 1.3.0
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Table: audit_logs
-- Stores all access decisions for audit and compliance
-- Retention: Online 30 days, then cold storage for 2 years
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gate_id VARCHAR(50) NOT NULL,
    card_id VARCHAR(50) NOT NULL,
    card_id_masked VARCHAR(100),
    decision VARCHAR(10) NOT NULL CHECK (decision IN ('ALLOW', 'DENY')),
    reason_code VARCHAR(50),
    latency_ms INTEGER,
    correlation_id UUID,
    request_context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table: quota_records
-- Tracks daily quota usage per cardholder
-- Reset daily at UTC 00:00
-- ============================================================
CREATE TABLE IF NOT EXISTS quota_records (
    card_id VARCHAR(50) NOT NULL,
    quota_date DATE NOT NULL,
    remaining_quota INTEGER DEFAULT 5,
    used_today INTEGER DEFAULT 0,
    last_reset TIMESTAMPTZ,
    PRIMARY KEY (card_id, quota_date)
);

-- ============================================================
-- Table: policies
-- Stores access policies with time windows and gate restrictions
-- ============================================================
CREATE TABLE IF NOT EXISTS policies (
    policy_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    quota_per_day INTEGER DEFAULT 5,
    allowed_time_windows JSONB,
    allowed_gate_ids JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table: alerts
-- Stores generated alerts for audit and analysis
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    user_id VARCHAR(50),
    gate_id VARCHAR(50),
    alert_details JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_by VARCHAR(100),
    resolution_note TEXT,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Table: idempotency_cache
-- Stores processed correlation IDs for idempotency (60s window)
-- ============================================================
CREATE TABLE IF NOT EXISTS idempotency_cache (
    correlation_id UUID PRIMARY KEY,
    response JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Insert default policies
-- ============================================================
INSERT INTO policies (policy_id, name, quota_per_day, allowed_time_windows, allowed_gate_ids) VALUES
('POL_STUDENT_001', 'Student Access Policy - Lab Hours', 5, 
 '[{"start": "08:00:00", "end": "22:00:00"}]',
 '["LAB_01", "LAB_02", "LIB_01"]')
ON CONFLICT (policy_id) DO NOTHING;

INSERT INTO policies (policy_id, name, quota_per_day, allowed_time_windows, allowed_gate_ids) VALUES
('POL_STAFF_001', 'Staff Access Policy - Extended Hours', 10,
 '[{"start": "06:00:00", "end": "23:59:00"}]',
 '["LAB_01", "LAB_02", "LIB_01", "LOBBY_01", "OFFICE_01"]')
ON CONFLICT (policy_id) DO NOTHING;

INSERT INTO policies (policy_id, name, quota_per_day, allowed_time_windows, allowed_gate_ids) VALUES
('POL_ADMIN_001', 'Admin Access Policy - 24/7', 20,
 '[{"start": "00:00:00", "end": "23:59:59"}]',
 '["*"]')
ON CONFLICT (policy_id) DO NOTHING;

-- ============================================================
-- Create indexes for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_gate_id ON audit_logs(gate_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_card_id ON audit_logs(card_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_decision ON audit_logs(decision);
CREATE INDEX IF NOT EXISTS idx_quota_records_card_id ON quota_records(card_id);
CREATE INDEX IF NOT EXISTS idx_quota_records_date ON quota_records(quota_date);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_idempotency_cache_expires_at ON idempotency_cache(expires_at);

-- ============================================================
-- Create function to automatically update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_policies_updated_at
    BEFORE UPDATE ON policies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Create function to clean expired idempotency records
-- ============================================================
CREATE OR REPLACE FUNCTION clean_expired_idempotency()
RETURNS void AS $$
BEGIN
    DELETE FROM idempotency_cache WHERE expires_at < NOW();
END;
$$ language 'plpgsql';

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO b6_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO b6_user;

-- ============================================================
-- Table: device_registry
-- Stores all IoT devices from B1
-- ============================================================
CREATE TABLE IF NOT EXISTS device_registry (
    device_id VARCHAR(100) PRIMARY KEY,
    device_type VARCHAR(50) NOT NULL,
    location VARCHAR(255) NOT NULL,
    room VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Insert initial device registry data
-- ============================================================
INSERT INTO device_registry (device_id, device_type, location, room, status) VALUES
('esp32-lab-a101', 'environment_sensor', 'Lab A101', 'A101', 'active'),
('esp32-lab-a102', 'environment_sensor', 'Lab A102', 'A102', 'active'),
('esp32-gate-a', 'environment_sensor', 'Main Gate A', 'GATE-A', 'active'),
('esp32-library-01', 'environment_sensor', 'Library 01', 'LIB-01', 'active'),
('esp32-hall-b201', 'environment_sensor', 'Hall B201', 'B201', 'active'),
('esp32-lab-b202', 'environment_sensor', 'Lab B202', 'B202', 'active'),
('esp32-office-01', 'environment_sensor', 'Office 01', 'OFF-01', 'active')
ON CONFLICT (device_id) DO NOTHING;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_device_registry_device_id ON device_registry(device_id);
CREATE INDEX IF NOT EXISTS idx_device_registry_status ON device_registry(status);