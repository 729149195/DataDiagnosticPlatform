numactl --interleave=all mongod --dbpath mongodb_errors_data --bind_ip 0.0.0.0 --port 27017

python -m gunicorn -w 8 -b 0.0.0.0:5000 --certfile=10.1.108.231.pem --keyfile=10.1.108.231-key.pem config.wsgi:application

npm run dev

python run_batch_processing.py --start 1501 --end 1600 --batch-size 100 --concurrent 2