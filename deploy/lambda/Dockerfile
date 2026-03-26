FROM public.ecr.aws/lambda/python:3.12

# Install wealthops with AWS extras
RUN pip install --no-cache-dir wealthops[aws]

# Copy handler
COPY handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
