l
FROM ghcr.io/home-assistant/home-assistant:stable

RUN pip install --no-cache-dir boto3

COPY start.sh /start.sh
COPY backup_b2.py /backup_b2.py

RUN chmod +x /start.sh /backup_b2.py

ENTRYPOINT ["/start.sh"]