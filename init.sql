-- ============================================
-- PostgreSQL 初始化脚本
-- 在容器首次启动时自动执行
-- ============================================

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 设置时区为北京时间
SET timezone = 'Asia/Shanghai';

-- 创建索引（提升查询性能）
-- 周报表索引
CREATE INDEX IF NOT EXISTS idx_weekly_reports_author ON weekly_reports(author_name);
CREATE INDEX IF NOT EXISTS idx_weekly_reports_week ON weekly_reports(week_start);
CREATE INDEX IF NOT EXISTS idx_weekly_reports_status ON weekly_reports(status);
CREATE INDEX IF NOT EXISTS idx_weekly_reports_created ON weekly_reports(created_at DESC);

-- 聚合表索引
CREATE INDEX IF NOT EXISTS idx_weekly_aggregates_week ON weekly_aggregates(week_start);
CREATE INDEX IF NOT EXISTS idx_weekly_aggregates_dept ON weekly_aggregates(department_id);
CREATE INDEX IF NOT EXISTS idx_weekly_aggregates_composite ON weekly_aggregates(composite_score DESC);

-- 评分配置表索引
CREATE INDEX IF NOT EXISTS idx_scoring_configs_active ON scoring_configs(is_active) WHERE is_active = true;

-- 部门表索引
CREATE INDEX IF NOT EXISTS idx_departments_name ON departments(name);

-- 人员表索引
CREATE INDEX IF NOT EXISTS idx_persons_dept ON persons(department_id);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
