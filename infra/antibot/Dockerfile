FROM python:3.13-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
RUN pip install --no-cache-dir altcha==2.1.0 \
 && addgroup -g 10002 -S antibot \
 && adduser -u 10002 -S -D -H -G antibot antibot
COPY --chown=10002:10002 infra/antibot/server.py /srv/server.py
USER 10002:10002
EXPOSE 8090
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=5 \
 CMD python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8090/health',timeout=2).status==200" || exit 1
CMD ["python","/srv/server.py"]
