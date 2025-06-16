# 数据诊断平台维护手册 (Data Diagnostic Platform Maintenance Manual)

## 维护概述

本维护手册面向系统管理员和运维人员，提供数据诊断平台的日常维护、故障排除、性能优化和升级部署等方面的详细指导。

### 维护目标
- 确保系统7×24小时稳定运行
- 保障数据安全和完整性
- 优化系统性能和响应速度
- 及时处理故障和异常情况

---

## 系统架构与组件

### 核心组件
1. **前端服务** (Vue3 + Vite)
   - 端口: 5173
   - 服务类型: 开发服务器/静态文件服务
   - 依赖: Node.js 14+

2. **后端API服务** (Django + Gunicorn)
   - 端口: 5000
   - 服务类型: HTTP Web服务
   - 依赖: Python 3.8+

3. **监控服务** (Python独立进程)
   - 功能: 数据监控、自动检测调度
   - 运行模式: 后台daemon进程
   - 状态文件: `backend/monitor_status.json`

4. **数据库服务**
   - **MongoDB**: 端口27017, 存储检测结果
   - **SQLite**: 存储系统配置和用户信息

5. **数据源**
   - **MDSplus树**: 实验数据读取
   - **数据库配置**: DBS字典中定义的多个数据源

---

## 日常维护任务

### 每日检查 (Daily Checks)

#### 1. 系统状态检查
```bash
# 检查监控服务状态

# 检查Web服务进程
ps aux | grep gunicorn
ps aux | grep npm

# 检查端口占用情况
netstat -tlnp | grep -E ':5000|:5173|:27017'
```

#### 2. 日志文件检查
```bash
# 监控服务日志
tail -n 50 monitor.log

# Django服务日志 (如有输出到文件)
tail -n 50 django.log

# 系统错误日志
dmesg | tail -n 20
```

#### 3. 磁盘空间检查
```bash
# 检查磁盘使用情况
df -h

# 检查数据目录大小
du -sh mongodb_errors_data/
du -sh backend/static/
du -sh uploads/
```

#### 4. 内存和CPU使用检查
```bash
# 内存使用情况
free -h

# CPU使用情况
top -n 1 | head -20

# 进程资源使用
ps aux --sort=-%cpu | head -10
ps aux --sort=-%mem | head -10
```

### 每周维护 (Weekly Maintenance)

#### 1. 数据库优化
```bash
# MongoDB数据库统计
mongo --port 27017 --eval "
db.adminCommand('listCollections').cursor.firstBatch.forEach(
  function(collection) {
    print(collection.name + ': ' + db[collection.name].count() + ' documents');
  }
)"

# 清理过期数据 (可选)
mongo --port 27017 --eval "
db.detection_results.deleteMany({
  'created_at': {
    \$lt: new Date(Date.now() - 30*24*60*60*1000)
  }
})
"
```

#### 2. 日志轮转
```bash
# 监控日志轮转
if [ -f monitor.log ] && [ $(stat -f%z monitor.log 2>/dev/null || stat -c%s monitor.log) -gt 10485760 ]; then
    mv monitor.log monitor.log.$(date +%Y%m%d)
    touch monitor.log
fi

# 清理旧日志文件
find . -name "*.log.*" -mtime +7 -delete
```

#### 3. 系统更新检查
```bash
# 检查Python包更新
pip list --outdated

# 检查Node.js依赖更新
cd frontend && npm outdated

# 检查系统安全更新
yum check-update  # CentOS/RHEL
apt list --upgradable  # Ubuntu/Debian
```

### 每月维护 (Monthly Maintenance)

#### 1. 性能分析
```bash
# 分析MongoDB性能
mongo --port 27017 --eval "db.runCommand({serverStatus: 1})"

# 分析Web服务性能
# 查看gunicorn worker状态和处理的请求数

# 系统性能统计
iostat -x 1 5
vmstat 1 5
```

#### 2. 备份管理
```bash
# MongoDB数据备份
mongodump --port 27017 --out backup_$(date +%Y%m%d)/

# 配置文件备份
tar -czf config_backup_$(date +%Y%m%d).tar.gz \
  backend/config/ \
  frontend/package.json \
  *.pem \
  start.bat

# SQLite数据库备份
cp backend/db.sqlite3 backup/db.sqlite3.$(date +%Y%m%d)
```

#### 3. 证书检查
```bash
# SSL证书有效期检查
openssl x509 -in 10.1.108.231.pem -text -noout | grep -A 2 "Validity"

# 证书过期提醒（30天内）
cert_expire=$(openssl x509 -in 10.1.108.231.pem -noout -enddate | cut -d= -f2)
expire_seconds=$(date -d "$cert_expire" +%s)
current_seconds=$(date +%s)
days_until_expire=$(( (expire_seconds - current_seconds) / 86400 ))

if [ $days_until_expire -lt 30 ]; then
    echo "警告: SSL证书将在 $days_until_expire 天后过期"
fi
```

---

## 故障诊断与排除

### 常见故障场景

#### 1. Web服务无法访问

**症状表现**:
- 浏览器显示连接超时或拒绝连接
- 页面加载失败或白屏

**诊断步骤**:
```bash
# 1. 检查服务进程状态
ps aux | grep -E 'gunicorn|npm'

# 2. 检查端口监听状态
netstat -tlnp | grep -E ':5000|:5173'

# 3. 检查防火墙设置
iptables -L -n | grep -E '5000|5173'

# 4. 检查SSL证书
openssl s_client -connect 10.1.108.231:5000 -servername 10.1.108.231

# 5. 查看错误日志
journalctl -u your-service-name -f
```

**解决方案**:
```bash
# 重启前端服务
cd frontend && npm run dev

# 重启后端服务
cd backend
python -m gunicorn -w 16 -b 0.0.0.0:5000 \
  --certfile=../10.1.108.231.pem \
  --keyfile=../10.1.108.231-key.pem \
  config.wsgi:application

# 检查并修复证书权限
chmod 600 10.1.108.231-key.pem
chmod 644 10.1.108.231.pem
```

#### 2. 监控服务异常

**症状表现**:
- 监控状态显示服务未运行
- 自动检测停止工作
- MDS+数据更新不及时

**诊断步骤**:
```bash
# 1. 检查监控服务状态
python start_monitor_service.py status

# 2. 查看监控日志
tail -n 100 monitor.log

# 3. 检查状态文件
cat backend/monitor_status.json

# 4. 检查相关进程
ps aux | grep monitor_service

# 5. 检查系统资源
free -h && df -h
```

**解决方案**:
```bash
# 重启监控服务
python start_monitor_service.py restart

# 如果无法重启，强制停止后重新启动
pkill -f monitor_service.py
sleep 2
python start_monitor_service.py start

# 清理可能的锁文件
rm -f /tmp/monitor_service.lock
```

#### 3. 数据库连接问题

**症状表现**:
- 页面显示数据库连接错误
- 检测结果无法保存
- MongoDB连接超时

**诊断步骤**:
```bash
# 1. 检查MongoDB服务状态
systemctl status mongod

# 2. 检查MongoDB进程
ps aux | grep mongod

# 3. 检查MongoDB日志
tail -n 50 /var/log/mongodb/mongod.log

# 4. 测试数据库连接
mongo --port 27017 --eval "db.runCommand({ping: 1})"

# 5. 检查数据目录权限
ls -la mongodb_errors_data/
```

**解决方案**:
```bash
# 重启MongoDB服务
systemctl restart mongod

# 手动启动MongoDB (如果系统服务不可用)
numactl --interleave=all mongod --dbpath mongodb_errors_data \
  --bind_ip 0.0.0.0 --port 27017 --fork --logpath mongodb.log

# 修复数据目录权限
chown -R mongodb:mongodb mongodb_errors_data/
chmod 755 mongodb_errors_data/

# 修复数据库
mongod --dbpath mongodb_errors_data --repair
```

#### 4. 算法检测失败

**症状表现**:
- 批量检测进程异常退出
- 单个算法运行错误
- 检测结果不完整

**诊断步骤**:
```bash
# 1. 检查算法文件完整性
ls -la RunDetectAlgorithm/algorithm/*/

# 2. 检查算法日志
find RunDetectAlgorithm/ -name "*.log" -exec tail -n 20 {} \;

# 3. 测试单个算法
python RunDetectAlgorithm/Single_algorithm_to_channel.py \
  --channel-type MP --algorithm error_magnetics_drift --shot 1000

# 4. 检查数据源连接
python -c "
from RunDetectAlgorithm.mdsConn import MdsTree, DBS
tree = MdsTree(1000, 'exl50u', DBS['exl50u']['path'], DBS['exl50u']['subtrees'])
print('连接成功')
tree.close()
"

# 5. 检查系统资源限制
ulimit -a
```

**解决方案**:
```bash
# 重新运行失败的检测
python run_batch_processing.py --start 1000 --end 1010 --concurrent 1

# 单独测试算法模块
cd RunDetectAlgorithm/algorithm/MP/
python -c "
import error_magnetics_drift
import numpy as np
test_data = np.random.random(1000)
result = error_magnetics_drift.func(test_data)
print('算法测试成功:', result)
"

# 清理临时文件
rm -f RunDetectAlgorithm/temp/*
rm -f /tmp/mds_*
```

### 性能问题诊断

#### 1. 系统响应缓慢

**诊断工具**:
```bash
# CPU分析
top -p $(pgrep -d',' -f 'gunicorn|node|mongod|python')

# 内存分析
pmap -x $(pgrep gunicorn | head -1)

# 磁盘I/O分析
iotop -a

# 网络连接分析
ss -tulpn | grep -E ':5000|:5173|:27017'
netstat -i
```

**优化措施**:
```bash
# 调整gunicorn worker数量
# 编辑启动命令，根据CPU核心数调整worker数量
workers=$(($(nproc) * 2 + 1))

# MongoDB索引优化
mongo --port 27017 --eval "
db.detection_results.createIndex({shot_number: 1, channel_name: 1});
db.detection_results.createIndex({created_at: 1});
"

# 清理系统缓存
sync && echo 3 > /proc/sys/vm/drop_caches
```

#### 2. 内存泄漏问题

**监控脚本**:
```bash
#!/bin/bash
# memory_monitor.sh
while true; do
    echo "$(date): $(ps aux --no-headers -C gunicorn,node,mongod | awk '{sum+=$6} END {print "Memory usage: " sum/1024 " MB"}')"
    sleep 300
done
```

**内存清理**:
```bash
# 重启高内存占用的进程
pkill -f "gunicorn.*config.wsgi"
cd backend && python -m gunicorn -w 16 -b 0.0.0.0:5000 \
  --certfile=../10.1.108.231.pem --keyfile=../10.1.108.231-key.pem config.wsgi:application &

# 清理系统内存
echo 1 > /proc/sys/vm/drop_caches
```

---

## 部署与升级

### 生产环境部署

#### 1. 环境准备
```bash
# 创建专用用户
useradd -m -s /bin/bash datadiag
usermod -aG sudo datadiag

# 创建目录结构
mkdir -p /opt/datadiag/{app,logs,backup,ssl}
chown -R datadiag:datadiag /opt/datadiag/

# 安装系统依赖
yum install -y epel-release
yum install -y python3 python3-pip nodejs npm mongodb-server nginx

# 配置防火墙
firewall-cmd --permanent --add-port=5000/tcp
firewall-cmd --permanent --add-port=5173/tcp
firewall-cmd --permanent --add-port=27017/tcp
firewall-cmd --reload
```

#### 2. 应用部署
```bash
# 切换到专用用户
su - datadiag

# 部署应用代码
cd /opt/datadiag/app/
git clone <repository-url> DataDiagnosticPlatform
cd DataDiagnosticPlatform/

# 安装Python依赖
cd backend/
python3 -m pip install --user -r requirements.txt

# 安装Node.js依赖
cd ../frontend/
npm install --production

# 配置SSL证书
cp /path/to/certs/* /opt/datadiag/ssl/
chmod 600 /opt/datadiag/ssl/*.key
chmod 644 /opt/datadiag/ssl/*.pem
```

#### 3. 系统服务配置

**MongoDB服务** (`/etc/systemd/system/datadiag-mongo.service`):
```ini
[Unit]
Description=DataDiag MongoDB Service
After=network.target

[Service]
Type=forking
User=datadiag
Group=datadiag
ExecStart=/usr/bin/mongod --config /opt/datadiag/app/mongodb.conf
ExecReload=/bin/kill -HUP $MAINPID
PIDFile=/opt/datadiag/logs/mongod.pid
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**后端API服务** (`/etc/systemd/system/datadiag-api.service`):
```ini
[Unit]
Description=DataDiag API Service
After=network.target datadiag-mongo.service
Requires=datadiag-mongo.service

[Service]
Type=notify
User=datadiag
Group=datadiag
WorkingDirectory=/opt/datadiag/app/DataDiagnosticPlatform/backend
ExecStart=/usr/bin/python3 -m gunicorn -w 16 -b 0.0.0.0:5000 \
    --certfile=/opt/datadiag/ssl/10.1.108.231.pem \
    --keyfile=/opt/datadiag/ssl/10.1.108.231-key.pem \
    config.wsgi:application
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**监控服务** (`/etc/systemd/system/datadiag-monitor.service`):
```ini
[Unit]
Description=DataDiag Monitor Service
After=network.target datadiag-mongo.service
Requires=datadiag-mongo.service

[Service]
Type=simple
User=datadiag
Group=datadiag
WorkingDirectory=/opt/datadiag/app/DataDiagnosticPlatform
ExecStart=/usr/bin/python3 backend/monitor_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 4. 启动服务
```bash
# 重载systemd配置
systemctl daemon-reload

# 启动并启用服务
systemctl enable datadiag-mongo datadiag-api datadiag-monitor
systemctl start datadiag-mongo datadiag-api datadiag-monitor

# 检查服务状态
systemctl status datadiag-mongo datadiag-api datadiag-monitor
```

### 版本升级流程

#### 1. 升级前准备
```bash
# 创建完整备份
backup_dir="/opt/datadiag/backup/upgrade_$(date +%Y%m%d_%H%M%S)"
mkdir -p $backup_dir

# 备份数据库
mongodump --port 27017 --out $backup_dir/mongodb/

# 备份应用代码
cp -r /opt/datadiag/app/DataDiagnosticPlatform $backup_dir/app/

# 备份配置文件
cp -r /opt/datadiag/ssl $backup_dir/

# 记录当前版本
cd /opt/datadiag/app/DataDiagnosticPlatform/
git log --oneline -1 > $backup_dir/current_version.txt
```

#### 2. 执行升级
```bash
# 停止服务
systemctl stop datadiag-api datadiag-monitor

# 更新代码
cd /opt/datadiag/app/DataDiagnosticPlatform/
git fetch origin
git checkout main
git pull origin main

# 更新依赖
cd backend/
pip install --user -r requirements.txt --upgrade

cd ../frontend/
npm install

# 数据库迁移 (如需要)
cd ../backend/
python3 manage.py migrate

# 重启服务
systemctl start datadiag-api datadiag-monitor
systemctl status datadiag-api datadiag-monitor
```

#### 3. 升级验证
```bash
# 健康检查
curl -k http://192.168.20.49:5000/api/system-monitor-status

# 功能测试
python start_monitor_service.py status

# 检查日志
journalctl -u datadiag-api -f --lines=20
journalctl -u datadiag-monitor -f --lines=20

# 性能测试
ab -n 100 -c 10 -k http://192.168.20.49:5000/api/system-monitor-status
```

#### 4. 回滚程序 (如需要)
```bash
# 停止服务
systemctl stop datadiag-api datadiag-monitor

# 恢复代码
cd /opt/datadiag/app/
rm -rf DataDiagnosticPlatform
cp -r $backup_dir/app/DataDiagnosticPlatform .

# 恢复数据库
mongo --port 27017 --eval "db.dropDatabase()" DataDiagnosticPlatform
mongorestore --port 27017 $backup_dir/mongodb/

# 重启服务
systemctl start datadiag-api datadiag-monitor
```

---

## 安全维护

### 1. 系统安全检查

#### 定期安全审计
```bash
# 检查系统用户
cat /etc/passwd | grep -E 'datadiag|mongodb'

# 检查sudo权限
sudo -l -U datadiag

# 检查网络端口
nmap -sT 10.1.108.231

# 检查文件权限
find /opt/datadiag/ -type f -perm /o+w -ls

# 检查SSL证书安全性
openssl x509 -in /opt/datadiag/ssl/10.1.108.231.pem -text -noout | grep -E 'Algorithm|Key Size'
```

#### 密码和密钥管理
```bash
# 更新SSL证书 (annually)
# 1. 获取新证书
# 2. 备份旧证书
cp /opt/datadiag/ssl/10.1.108.231.pem /opt/datadiag/ssl/10.1.108.231.pem.backup
cp /opt/datadiag/ssl/10.1.108.231-key.pem /opt/datadiag/ssl/10.1.108.231-key.pem.backup

# 3. 部署新证书
# 4. 重启服务
systemctl restart datadiag-api

# Django密钥轮换
cd /opt/datadiag/app/DataDiagnosticPlatform/backend/
python3 -c "
from django.core.management.utils import get_random_secret_key
print('SECRET_KEY =', repr(get_random_secret_key()))
"
```

### 2. 数据安全

#### 数据备份策略
```bash
#!/bin/bash
# 自动备份脚本 backup.sh

BACKUP_ROOT="/opt/datadiag/backup"
DATE=$(date +%Y%m%d)
BACKUP_DIR="$BACKUP_ROOT/daily_$DATE"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 数据库备份
mongodump --port 27017 --out $BACKUP_DIR/mongodb/

# 配置文件备份
tar -czf $BACKUP_DIR/config.tar.gz \
  /opt/datadiag/app/DataDiagnosticPlatform/backend/config/ \
  /opt/datadiag/ssl/

# SQLite备份
cp /opt/datadiag/app/DataDiagnosticPlatform/backend/db.sqlite3 $BACKUP_DIR/

# 清理老备份 (保留30天)
find $BACKUP_ROOT -type d -name "daily_*" -mtime +30 -exec rm -rf {} \;

# 记录备份日志
echo "$(date): Backup completed to $BACKUP_DIR" >> $BACKUP_ROOT/backup.log
```

#### 数据恢复测试
```bash
# 每月进行数据恢复测试
TEST_DB="DataDiagnosticPlatform_test"

# 恢复到测试数据库
mongorestore --port 27017 --db $TEST_DB /opt/datadiag/backup/latest/mongodb/DataDiagnosticPlatform/

# 验证数据完整性
mongo --port 27017 $TEST_DB --eval "
print('Collections:');
db.getCollectionNames().forEach(function(name) {
  print(name + ': ' + db[name].count() + ' documents');
});
"

# 清理测试数据库
mongo --port 27017 $TEST_DB --eval "db.dropDatabase()"
```

---

## 监控与告警

### 1. 系统监控脚本

#### 服务状态监控
```bash
#!/bin/bash
# service_monitor.sh

SERVICES=("datadiag-mongo" "datadiag-api" "datadiag-monitor")
LOG_FILE="/opt/datadiag/logs/service_monitor.log"

for service in "${SERVICES[@]}"; do
    if ! systemctl is-active --quiet $service; then
        echo "$(date): WARNING - $service is not running" >> $LOG_FILE
        # 尝试重启服务
        systemctl start $service
        sleep 5
        if systemctl is-active --quiet $service; then
            echo "$(date): INFO - $service restarted successfully" >> $LOG_FILE
        else
            echo "$(date): ERROR - Failed to restart $service" >> $LOG_FILE
            # 发送告警邮件
            echo "Service $service failed to restart on $(hostname)" | \
              mail -s "DataDiag Service Alert" admin@example.com
        fi
    fi
done
```

#### 性能监控脚本
```bash
#!/bin/bash
# performance_monitor.sh

LOG_FILE="/opt/datadiag/logs/performance_monitor.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# CPU使用率
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')

# 内存使用率
MEM_USAGE=$(free | grep Mem | awk '{printf("%.2f", $3/$2 * 100.0)}')

# 磁盘使用率
DISK_USAGE=$(df -h /opt/datadiag | awk 'NR==2 {print $5}' | sed 's/%//')

# MongoDB连接状态
MONGO_STATUS=$(mongo --port 27017 --eval "db.runCommand({ping: 1})" --quiet | grep '"ok" : 1' | wc -l)

# 记录监控数据
echo "$TIMESTAMP,CPU:$CPU_USAGE%,MEM:$MEM_USAGE%,DISK:$DISK_USAGE%,MONGO:$MONGO_STATUS" >> $LOG_FILE

# 告警阈值检查
if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo "$(date): WARNING - High CPU usage: $CPU_USAGE%" >> $LOG_FILE
fi

if (( $(echo "$MEM_USAGE > 85" | bc -l) )); then
    echo "$(date): WARNING - High memory usage: $MEM_USAGE%" >> $LOG_FILE
fi

if [ $DISK_USAGE -gt 90 ]; then
    echo "$(date): WARNING - High disk usage: $DISK_USAGE%" >> $LOG_FILE
fi

if [ $MONGO_STATUS -eq 0 ]; then
    echo "$(date): ERROR - MongoDB connection failed" >> $LOG_FILE
fi
```

### 2. 自动化监控部署

#### Crontab配置
```bash
# 编辑cron任务
crontab -e -u datadiag

# 添加监控任务
# 每5分钟检查服务状态
*/5 * * * * /opt/datadiag/scripts/service_monitor.sh

# 每分钟记录性能数据
* * * * * /opt/datadiag/scripts/performance_monitor.sh

# 每日备份
0 2 * * * /opt/datadiag/scripts/backup.sh

# 每周日志清理
0 3 * * 0 find /opt/datadiag/logs/ -name "*.log" -mtime +7 -delete

# 每月证书检查
0 4 1 * * /opt/datadiag/scripts/cert_check.sh
```

#### 日志轮转配置
```bash
# 创建logrotate配置
cat > /etc/logrotate.d/datadiag << EOF
/opt/datadiag/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    postrotate
        systemctl reload datadiag-api > /dev/null 2>&1 || true
    endscript
}
EOF
```

---

## 故障应急预案

### 1. 紧急故障响应流程

#### 严重故障 (P1)
- **定义**: 系统完全不可用，影响所有用户
- **响应时间**: 15分钟内
- **处理流程**:
  1. 立即确认故障范围
  2. 启动应急恢复程序
  3. 通知相关人员
  4. 实施临时修复方案
  5. 监控系统恢复状态

#### 重要故障 (P2)  
- **定义**: 核心功能受影响，部分用户受影响
- **响应时间**: 1小时内
- **处理流程**:
  1. 评估故障影响范围
  2. 制定修复计划
  3. 实施修复方案
  4. 验证修复效果

#### 一般故障 (P3)
- **定义**: 非核心功能故障，少数用户受影响  
- **响应时间**: 4小时内
- **处理流程**:
  1. 记录故障信息
  2. 计划修复时间
  3. 实施修复
  4. 更新文档

### 2. 应急恢复程序

#### 快速重启脚本
```bash
#!/bin/bash
# emergency_restart.sh

echo "开始应急重启程序..."

# 停止所有服务
systemctl stop datadiag-api datadiag-monitor

# 检查进程是否完全停止
sleep 5
pkill -f "gunicorn.*config.wsgi"
pkill -f "monitor_service"

# 清理临时文件
rm -f /tmp/gunicorn.pid
rm -f /tmp/monitor_service.lock

# 检查关键文件
if [ ! -f "/opt/datadiag/ssl/10.1.108.231.pem" ]; then
    echo "ERROR: SSL证书文件缺失"
    exit 1
fi

# 检查MongoDB状态
if ! systemctl is-active --quiet datadiag-mongo; then
    systemctl start datadiag-mongo
    sleep 10
fi

# 重启应用服务
systemctl start datadiag-api
sleep 5
systemctl start datadiag-monitor

# 验证服务状态
echo "验证服务状态..."
for service in datadiag-mongo datadiag-api datadiag-monitor; do
    if systemctl is-active --quiet $service; then
        echo "✓ $service 运行正常"
    else
        echo "✗ $service 启动失败"
        systemctl status $service
    fi
done

# 健康检查
echo "执行健康检查..."
curl -k http://192.168.20.49:5000/api/system-monitor-status
```

#### 数据恢复脚本
```bash
#!/bin/bash
# emergency_data_restore.sh

BACKUP_DIR=${1:-"/opt/datadiag/backup/latest"}

if [ ! -d "$BACKUP_DIR" ]; then
    echo "错误: 备份目录不存在: $BACKUP_DIR"
    exit 1
fi

echo "开始从 $BACKUP_DIR 恢复数据..."

# 停止相关服务
systemctl stop datadiag-api datadiag-monitor

# 备份当前数据
CURRENT_BACKUP="/tmp/emergency_backup_$(date +%Y%m%d_%H%M%S)"
mongodump --port 27017 --out $CURRENT_BACKUP/

# 恢复MongoDB数据
mongorestore --port 27017 --drop $BACKUP_DIR/mongodb/

# 恢复SQLite数据
cp $BACKUP_DIR/db.sqlite3 /opt/datadiag/app/DataDiagnosticPlatform/backend/

# 重启服务
systemctl start datadiag-api datadiag-monitor

echo "数据恢复完成"
```

---

## 维护工具和脚本

### 1. 系统信息收集脚本
```bash
#!/bin/bash
# system_info.sh

OUTPUT_FILE="/tmp/datadiag_system_info_$(date +%Y%m%d_%H%M%S).txt"

echo "数据诊断平台系统信息报告" > $OUTPUT_FILE
echo "生成时间: $(date)" >> $OUTPUT_FILE
echo "======================================" >> $OUTPUT_FILE

# 系统基本信息
echo -e "\n系统基本信息:" >> $OUTPUT_FILE
uname -a >> $OUTPUT_FILE
cat /etc/os-release >> $OUTPUT_FILE

# 硬件信息
echo -e "\n硬件信息:" >> $OUTPUT_FILE
echo "CPU: $(grep 'model name' /proc/cpuinfo | head -1 | cut -d':' -f2)" >> $OUTPUT_FILE
echo "内存: $(free -h | grep Mem | awk '{print $2}')" >> $OUTPUT_FILE
echo "磁盘: $(df -h | grep -E '^/dev')" >> $OUTPUT_FILE

# 服务状态
echo -e "\n服务状态:" >> $OUTPUT_FILE
for service in datadiag-mongo datadiag-api datadiag-monitor; do
    echo "$service: $(systemctl is-active $service)" >> $OUTPUT_FILE
done

# 网络状态
echo -e "\n网络监听端口:" >> $OUTPUT_FILE
netstat -tlnp | grep -E ':5000|:5173|:27017' >> $OUTPUT_FILE

# 进程信息
echo -e "\n相关进程:" >> $OUTPUT_FILE
ps aux | grep -E 'gunicorn|mongod|monitor_service|npm' | grep -v grep >> $OUTPUT_FILE

# 磁盘使用
echo -e "\n磁盘使用情况:" >> $OUTPUT_FILE
du -sh /opt/datadiag/* >> $OUTPUT_FILE

# 最近日志
echo -e "\n最近错误日志:" >> $OUTPUT_FILE
journalctl --since "1 hour ago" --priority=err --no-pager >> $OUTPUT_FILE

echo "系统信息已保存到: $OUTPUT_FILE"
```

### 2. 性能测试脚本
```bash
#!/bin/bash
# performance_test.sh

echo "开始性能测试..."

# API响应时间测试
echo "测试API响应时间..."
curl -w "@curl-format.txt" -o /dev/null -s http://192.168.20.49:5000/api/system-monitor-status

# curl-format.txt内容:
cat > curl-format.txt << EOF
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF

# 并发测试
echo "执行并发测试..."
ab -n 1000 -c 10 -k http://192.168.20.49:5000/api/system-monitor-status

# 数据库性能测试
echo "测试MongoDB性能..."
mongo --port 27017 --eval "
var start = new Date();
for(var i = 0; i < 1000; i++) {
    db.test.insert({test: i, timestamp: new Date()});
}
var end = new Date();
print('插入1000条记录耗时: ' + (end - start) + 'ms');
db.test.drop();
"

echo "性能测试完成"
```

---

## 维护计划模板

### 季度维护计划
```
第一季度维护计划:
□ 系统安全更新
□ SSL证书续期检查
□ 性能基准测试
□ 备份恢复演练
□ 监控告警测试
□ 文档更新
□ 用户培训

第二季度维护计划:
□ 硬件健康检查
□ 数据库优化
□ 日志分析总结
□ 容量规划评估
□ 版本升级计划
□ 灾备演练
□ 安全审计

第三季度维护计划:
□ 系统架构优化
□ 性能调优
□ 存储清理
□ 网络优化
□ 算法更新
□ 用户反馈收集
□ 运维流程改进

第四季度维护计划:
□ 年度总结报告
□ 次年规划制定
□ 硬件更换计划
□ 预算申请
□ 技术培训
□ 应急预案更新
□ 合规性检查
```

### 维护记录模板
```
维护记录表

日期: ____________________
维护人员: ________________
维护类型: □ 定期维护 □ 故障处理 □ 版本升级 □ 其他

维护内容:
1. ________________________________
2. ________________________________
3. ________________________________

发现问题:
1. ________________________________
2. ________________________________

解决方案:
1. ________________________________
2. ________________________________

后续建议:
________________________________

维护结果: □ 成功 □ 部分成功 □ 失败

备注:
________________________________

签名: ____________________
```

---

## 联系信息与技术支持

### 紧急联系方式
- **系统管理员**: 
- **技术负责人**: 
- **应急响应团队**: 

### 外部支持
- **MongoDB技术支持**: 
- **SSL证书提供商**: 
- **网络服务商**: 

### 相关文档
- **用户手册**: `User_Manual.md`
- **API文档**: 在线文档地址
- **开发文档**: 代码库README文件

---

*本维护手册最后更新时间: $(date +%Y-%m-%d)*
*版本: v1.0.0*
