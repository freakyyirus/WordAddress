"""
AWS Lambda Handler for Open3Words
Wraps the FastAPI app for deployment on AWS Lambda + API Gateway.

Deploy with:
    pip install mangum
    zip -r lambda.zip api/ -x '*.pyc' '__pycache__/*'
    aws lambda create-function --function-name open3words ...

Or use SAM / Serverless Framework for easier deployment.
"""

try:
    from mangum import Mangum
except ImportError:
    raise ImportError("Install mangum for Lambda support: pip install mangum")

import sys
import os

# Add api/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from main import app

# Mangum wraps FastAPI for AWS Lambda + API Gateway
handler = Mangum(app, lifespan="off")
