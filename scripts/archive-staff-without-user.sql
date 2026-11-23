-- 账号来源改造的一次性封存脚本（幂等，可重复执行）。
-- 执行前先导出受影响名单：
-- SELECT id, code, name, team_id, status FROM wms_master_data_staff
-- WHERE user_id IS NULL AND status = 1;

START TRANSACTION;

INSERT INTO wms_master_data_staff_log (staff_id, kind, reason, occurred_at)
SELECT id, 'team', '账号来源改造：无账号档案封存', NOW()
FROM wms_master_data_staff
WHERE user_id IS NULL AND status = 1;

UPDATE wms_master_data_team
SET leader_staff_id = NULL, updated_at = NOW()
WHERE leader_staff_id IN (
    SELECT id FROM wms_master_data_staff WHERE user_id IS NULL AND status = 1
);

UPDATE wms_master_data_staff
SET status = 0, updated_at = NOW()
WHERE user_id IS NULL AND status = 1;

COMMIT;
