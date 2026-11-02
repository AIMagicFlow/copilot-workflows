import json
import os
import uuid

import azure.functions as func
from azure.identity import DefaultAzureCredential

from app import api
from app.config import load_settings
from app.extraction.document_intelligence import AzureDocumentReader

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
_reader: AzureDocumentReader | None = None


def _document_reader(settings):
    """One reader per worker, created on first use so that a missing endpoint fails per request."""
    global _reader
    if _reader is None and settings.document_intelligence_endpoint:
        _reader = AzureDocumentReader(settings.document_intelligence_endpoint, DefaultAzureCredential())
    return _reader


@app.route(route="v1/documents/sanitize", methods=["POST"])
def sanitize_document(req: func.HttpRequest) -> func.HttpResponse:
    try:
        settings = load_settings(os.environ)
    except ValueError:
        body = {"status": "failed", "error": {"code": "INTERNAL", "message": "invalid configuration"}}
        return func.HttpResponse(json.dumps(body), status_code=500, mimetype="application/json")

    result = api.handle_sanitize(
        req.get_body(),
        settings,
        _document_reader(settings),
        str(uuid.uuid4()),
    )
    return func.HttpResponse(
        json.dumps(result.body),
        status_code=result.status,
        mimetype="application/json",
        headers=result.headers,
    )
