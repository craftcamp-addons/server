FROM --platform=linux/amd64 python:3.10-alpine3.16 as builder

RUN apk add --update alpine-sdk
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM --platform=linux/amd64 python:3.10-alpine3.16 as runner
COPY --from=builder /root/.local /root/.local
ENV PYTHONPATH="/app:$PYTHONPATH"
WORKDIR /app/backend
ENV PATH=/root/.local/bin:$PATH

COPY general_settings.json /app/backend
