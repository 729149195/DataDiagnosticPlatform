numactl --interleave=all mongod --dbpath mongodb_errors_data --bind_ip 0.0.0.0 --port 27017

nohup python3 backend/monitor_service.py > monitor.log 2>&1 &

python -m gunicorn -w 16 -b 0.0.0.0:5000 --certfile=10.1.108.231.pem --keyfile=10.1.108.231-key.pem config.wsgi:application

npm run dev


python run_batch_processing.py --start 11001 --end 11100 --batch-size 100 --concurrent 1



python start_batch_with_monitoring.py --start 9001 --end 10000 --batch-size 100 --concurrent 5

