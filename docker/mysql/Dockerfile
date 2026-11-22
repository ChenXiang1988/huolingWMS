# MySQL 配置固化：把 my.cnf 复制进镜像，避免 Windows 挂载导致文件 0777 被 MySQL 忽略
FROM mysql:8.0

COPY my.cnf /etc/mysql/conf.d/my.cnf
RUN chmod 644 /etc/mysql/conf.d/my.cnf
