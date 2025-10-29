import os
import time
import re
import sys
from flask import Flask, request, jsonify, render_template
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from azure.storage.blob import BlobServiceClient
import uuid
## Add required imports
connection_string = 'DefaultEndpointsProtocol=https;AccountName=tyv8xecase7;AccountKey=Rs1ONKFXccWpphCP3aMdcIPZ6cCwYj6QZ3YuoUR7oGv8tQP/UXLFVSaiV9braoJ2gYR1Ne1nO6gi+ASt+m8lZQ==;EndpointSuffix=core.windows.net'
CONTAINER_NAME = 'lanternfly-images-451gfoo2'
NEW_PORT = 8080
cc = None
azure_connection_ok = False

class DummyBlobClient:
    def download_blob(self):
        raise Exception("Dummy Client: Cannot download because Azure connection is not available.")
        
    def upload_blob(self, stream, content_settings, overwrite):
        print("DUMMY UPLOAD: Azure connection unavailable. Skipping actual upload.")
        pass 
    
class DummyContainerClient:
    def __init__(self):
        self.url = "http://127.0.0.1:8080/gallery/dummy-base" 

    def exists(self):
        return True 

    def create_container(self):
        pass

    def list_blobs(self):
        print("DUMMY GALLERY: Returning mock data.")
        return [
            type('DummyBlob', (object,), {'name': '1730105000000-dummy-placeholder.jpg', 'content_settings': type('CS', (object,), {'content_type': 'image/jpeg'})})(),
        ]
    def get_blob_client(self, blob_name):
        return DummyBlobClient()

def initialize_azure_blob_storage():
    global cc, azure_connection_ok
    cc = DummyContainerClient()
    azure_connection_ok = False
    try:
        print("Connecting to Azure Blob Storage...") 
        bsc = BlobServiceClient.from_connection_string(connection_string)
        cc = bsc.get_container_client(CONTAINER_NAME)  # Replace with Container name cc.url will get you the url path to the container.  
        cc.exists()
        if not cc.exists():
            print(f"Container {CONTAINER_NAME} does not exist. Creating new container.")
            cc.create_container(public_access='container')
        azure_connection_ok = True
        print("Connected to Azure Blob Storage successfully. Container URL:", cc.url)
    except HttpResponseError as e:
        if e.error is not None and e.error.code == 'AccountIsDisabled':
            print('-' * 50)
            print("The Azure Storage account is disabled. Using Dummy Container Client.")
            print('-' * 50)
            azure_connection_ok = False
    except Exception as e:  
        print("Error connecting to Azure Blob Storage:", e)
        azure_connection_ok = False

initialize_azure_blob_storage()

app = Flask(__name__)

def get_blob_url(blob_name):
    """Constructs the public URL assuming the container allows public read access."""
    return f"http://127.0.0.1:{NEW_PORT}/gallery/{blob_name}"

def sanitize_filename(filename):
    filename = filename.strip().lower()
    filename = re.sub(r'[^a-z0-9\._-]', '_', filename)
    filename = re.sub(r'_{2,}', '_', filename)
    return filename

@app.post("/api/v1/upload")
def upload():
    if not azure_connection_ok:
        return jsonify(ok=False, error="Azure Blob Storage connection not available"), 503
    try:
        if "file" not in request.files:
            return jsonify(ok=False, error="No file part in the request"), 400
        f = request.files["file"]
        if f.filename == "":
            return jsonify(ok=False, error="No selected file"), 400 
        timestamp = int(time.time()*1000)
        sanitized_filename = sanitize_filename(f.filename)
        blob_name = f"{timestamp}-{sanitized_filename}"
        blob_client = cc.get_blob_client(blob_name)
        blob_client.upload_blob(f.stream, overwrite=True)
        url = get_blob_url(blob_name)
        return jsonify(ok=True, url=url), 200
    except KeyError:
        return jsonify(ok=False, error="File part missing"), 400
    except Exception as e:
        print("Error during file upload:", e)
        return jsonify(ok=False, error=f"Internal Server Error during upload: {str(e)}"), 500


## Add other API end points. (/api/v1/gallery)  and (/api/v1/health)
@app.get("/api/v1/gallery")
def gallery():
    if not azure_connection_ok:
        return jsonify(ok=False, error="Azure Blob Storage connection not available"), 503
    try:
        blob_list = cc.list_blobs()
        urls = [get_blob_url(blob.name) for blob in blob_list]
        return jsonify(ok=True, images=urls), 200
    except Exception as e:
        print("Error retrieving gallery:", e)
        return jsonify(ok=False, error=str(e)), 500

@app.get("/gallery/<blob_name>")
def serve_image(blob_name):
    if not azure_connection_ok:
        return jsonify(ok=False, error="Azure Blob Storage connection not available"), 503
    try:
        blob_client = cc.get_blob_client(blob_name)
        download_stream = blob_client.download_blob()
        image_data = download_stream.readall()
        from flask import Response
        return Response(image_data, mimetype='image/jpeg')
    except Exception as e:
        print("Error serving image:", e)
        return jsonify(ok=False, error=str(e)), 500

@app.get("/api/v1/health")
def health():
    return jsonify({"status":"ok"}), 200

@app.get("/")
def index():
    return render_template("index.html")

# create a virtual environment
# if name = main: run app
if __name__ == "__main__":
    print("Creating Flask App...")
    print(f"Container URL: {cc.url if cc else 'N/A'}")
    print(f"Starting Flask App...")
    app.run(debug=True, port=NEW_PORT)
