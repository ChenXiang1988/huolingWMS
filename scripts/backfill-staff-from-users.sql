-- 为已存在的用户账号补建人员档案（幂等，可重复执行）。
-- 只补未软删、非预置 admin、未绑货主且尚无同名工号／对应档案的账号。

INSERT INTO wms_master_data_staff (code, name, phone, user_id, status, created_at, updated_at)
SELECT u.username, u.nickname, u.phone, u.id, 1, NOW(), NOW()
FROM sys_user u
WHERE u.deleted_at IS NULL
  AND u.username <> 'admin'
  AND NOT EXISTS (
      SELECT 1 FROM wms_master_data_staff s WHERE s.user_id = u.id
  )
  AND NOT EXISTS (
      SELECT 1 FROM wms_master_data_staff s WHERE s.code = u.username
  )
  AND NOT EXISTS (
      SELECT 1 FROM wms_master_data_user_owner o WHERE o.user_id = u.id
  );
