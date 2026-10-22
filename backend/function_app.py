import json
import logging
import os
import uuid

import azure.functions as func
from datetime import datetime, timezone
from azure.identity import DefaultAzureCredential
from azure.data.tables import TableClient
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

# Azure Storage configuration
ACCOUNT_NAME = os.environ["STORAGE_ACCOUNT_NAME"]
TABLE_NAME = os.environ.get("TABLE_NAME", "StudentNotes")

# Authenticate using your Azure account locally,
# or the Function App's managed identity when deployed.
credential = DefaultAzureCredential()

table = TableClient(
    endpoint=f"https://{ACCOUNT_NAME}.table.core.windows.net",
    table_name=TABLE_NAME,
    credential=credential
)


@app.route(
    route="notes",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def list_notes(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Read all note records from Azure Table Storage
        entities = table.query_entities(
            query_filter="PartitionKey eq 'notes'"
        )

        notes = []

        for entity in entities:
            notes.append({
                "noteId": entity.get("RowKey", ""),
                "title": entity.get("title", ""),
                "subject": entity.get("subject", ""),
                "uploader": entity.get("uploader", ""),
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "fileName": entity.get("fileName", "")
            })

        return func.HttpResponse(
            body=json.dumps({"notes": notes}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception:
        logging.exception("Could not retrieve notes")

        return func.HttpResponse(
            body=json.dumps({
                "error": "Could not retrieve notes"
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.route(
    route="upload-note",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def upload_note(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get details from the request URL
        title = req.params.get("title")
        subject = req.params.get("subject")
        uploader = req.params.get("uploader")
        file_name = req.params.get("fileName")

        if not title or not subject or not uploader or not file_name:
            return func.HttpResponse(
                "Missing title, subject, uploader, or fileName",
                status_code=400
            )

        # Read the uploaded file's raw contents
        file_data = req.get_body()

        if not file_data:
            return func.HttpResponse(
                "No file was uploaded",
                status_code=400
            )

        # Create a unique file name to avoid overwriting files
        safe_file_name = os.path.basename(file_name)
        note_id = str(uuid.uuid4())
        blob_name = f"{note_id}_{safe_file_name}"

        # Connect to Azure Blob Storage
        blob_service = BlobServiceClient(
            account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
            credential=credential
        )

        blob_client = blob_service.get_blob_client(
            container="notes",
            blob=blob_name
        )

        # Upload the file
        blob_client.upload_blob(file_data, overwrite=False)

        # Save note details in Azure Table Storage
        entity = {
            "PartitionKey": "notes",
            "RowKey": note_id,
            "title": title,
            "subject": subject,
            "uploader": uploader,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "fileName": safe_file_name,
            "blobName": blob_name
        }

        table.create_entity(entity=entity)

        return func.HttpResponse(
            json.dumps({
                "message": "Note uploaded successfully",
                "noteId": note_id,
                "fileName": safe_file_name
            }),
            status_code=201,
            mimetype="application/json"
        )

    except Exception:
        logging.exception("Could not upload note")
        return func.HttpResponse(
            "Could not upload note",
            status_code=500
        )


@app.route(
    route="download-note/{note_id}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def download_note(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Get the note ID from the URL
        note_id = req.route_params.get("note_id")

        # Find the note's metadata in Azure Table Storage
        entity = table.get_entity(
            partition_key="notes",
            row_key=note_id
        )

        # Get the stored Blob name
        blob_name = entity.get("blobName")

        if not blob_name:
            return func.HttpResponse(
                "File information not found",
                status_code=404
            )

        # Connect to Azure Blob Storage
        blob_service = BlobServiceClient(
            account_url=f"https://{ACCOUNT_NAME}.blob.core.windows.net",
            credential=credential
        )

        # Retrieve the file
        blob_client = blob_service.get_blob_client(
            container="notes",
            blob=blob_name
        )

        file_data = blob_client.download_blob().readall()

        # Return the file as a downloadable response
        return func.HttpResponse(
            body=file_data,
            status_code=200,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{entity.get("fileName", "note.pdf")}"'
                )
            }
        )

    except Exception as e:
        logging.exception("Could not download note")

        # Note doesn't exist in Table Storage
        if "ResourceNotFoundError" in type(e).__name__:
            return func.HttpResponse(
                "Note not found",
                status_code=404
            )

        return func.HttpResponse(
            "Could not download note",
            status_code=500
        )