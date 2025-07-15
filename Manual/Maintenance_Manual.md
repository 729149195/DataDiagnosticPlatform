前端启动：
cd /home/diag/DataDiagnostic/DataDiagnosticPlatform/frontend
npm install

MongoDB数据库配置：
cd /mnt/8f7d843a-cfa8-4a68-9fd2-9bf3ac52dee6/
numactl --interleave=all mongod --dbpath mongodb_errors_data --bind_ip 0.0.0.0 --port 27017

启动自动炮号异常检测：
cd /home/diag/DataDiagnostic/DataDiagnosticPlatform/
conda activate mdsplus
python auto_mg_md_sync.py

启动炮号监控服务：
cd /home/diag/DataDiagnostic/DataDiagnosticPlatform/
conda activate mdsplus
nohup python3 backend/monitor_service.py > monitor.log 2>&1 &

启动后端API服务器：
cd /home/diag/DataDiagnostic/DataDiagnosticPlatform/backend
conda activate mdsplus
python -m gunicorn -w 16 -b 0.0.0.0:5000  config.wsgi:application
